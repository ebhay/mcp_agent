"""Coach agent workflow: process unread coach mail (batch requests), reallocate unassigned cohorts, report to admin."""
import json

from openai import OpenAI

from app.config import get_settings
from app.llm import get_llm_client

from .clients import CoachMailClient, TrainMateClient, TrainMateError
from .cohort_mail import is_template, normalize, parse_template


def validate_request(data: dict) -> list[str]:
    """Problems with a cohort request. Used by query mode and the MCP server."""
    return normalize(data)[1]


def cohort_payload(data: dict) -> dict:
    """TrainMate create-cohort body built from checked fields."""
    return normalize(data)[0]

EXTRACT_PROMPT = (
    "Read the mail and decide whether it asks to create, set up, or open a new training batch or cohort. "
    "Return a JSON object with keys: isBatchRequest (boolean), cohortCode, serviceLine, stream, requiredSkill, "
    "numberOfTrainees (integer), startDate (YYYY-MM-DD), endDate (YYYY-MM-DD), vertical, location. "
    "Set isBatchRequest to false for greetings, lunch invitations, status updates, or anything that is not a request to create a batch. "
    "Required fields: cohortCode, requiredSkill, numberOfTrainees, startDate, endDate. "
    "Never invent values: leave a field out if the mail does not state it."
)


def extract_request(llm: OpenAI, model: str, subject: str, body: str) -> dict:
    response = llm.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": EXTRACT_PROMPT},
            {"role": "user", "content": f"Subject: {subject}\n\n{body}"},
        ],
    )
    data = json.loads(response.choices[0].message.content or "{}")
    return data if isinstance(data, dict) else {}


def read_request(llm: OpenAI, model: str, subject: str, body: str) -> tuple[bool, dict, list[str]]:
    """Returns (is_batch_request, cohort data, problems). Filled-in templates skip the LLM."""
    fields = parse_template(body)
    if is_template(fields):
        data, problems = normalize(fields)
        return True, data, problems
    extracted = extract_request(llm, model, subject, body)
    if not extracted.get("isBatchRequest"):
        return False, {}, []
    data, problems = normalize(extracted)
    return True, data, problems


def run_workflow() -> list[dict]:
    s = get_settings()
    llm = get_llm_client()
    mail = CoachMailClient(s.app_base_url, s.coach_login_id, s.coach_password)
    trainmate = TrainMateClient(s.trainmate_base_url, s.coach_login_id, s.coach_password)
    report: list[dict] = []

    # 1) Unread mail, newest first -> batch requests create cohorts and get a reply to the admin.
    #    Mail that is not a batch request stays unread and is reported as ignored.
    for msg in mail.unread_inbox():
        try:
            is_batch, data, problems = read_request(llm, s.openai_model, msg["subject"], msg["body"])
        except Exception as err:  # one bad mail must not stop the run; it stays unread
            report.append({"action": "failed", "mail": msg["id"], "error": f"could not read mail: {err}"})
            continue

        if not is_batch:
            report.append({"action": "ignored", "mail": msg["id"], "subject": msg["subject"]})
            continue

        if problems:
            mail.reply(msg["from_username"], f"Re: {msg['subject']}",
                       "Batch not created. Please fix: " + "; ".join(problems)
                       + ". Send the mail again using the batch request template.")
            report.append({"action": "asked_for_details", "mail": msg["id"], "problems": problems})
        else:
            try:
                cohort = trainmate.create_cohort(data)
                mail.reply(msg["from_username"], f"Re: {msg['subject']}",
                           f"Batch {cohort['cohortCode']} created. Trainer: {cohort.get('assignedTrainerName') or 'not assigned yet'}. Status: {cohort['status']}.")
                report.append({"action": "created", "cohortCode": cohort["cohortCode"], "status": cohort["status"]})
            except TrainMateError as err:
                mail.reply(msg["from_username"], f"Re: {msg['subject']}", f"Batch not created: {err}")
                report.append({"action": "failed", "mail": msg["id"], "error": str(err)})
        mail.mark_read(msg["id"])

    # 2) Unallocated cohorts of this coach -> reallocate -> report to admin
    for cohort in trainmate.list_cohorts():
        if cohort.get("status") != "UNASSIGNED":
            continue
        try:
            updated = trainmate.reallocate(cohort["id"])
            outcome = f"assigned to {updated.get('assignedTrainerName')}" if updated.get("assignedTrainerName") else "still unassigned"
            report.append({"action": "reallocated", "cohortCode": cohort["cohortCode"], "outcome": outcome})
        except TrainMateError as err:
            outcome = f"reallocation failed: {err}"
            report.append({"action": "failed", "cohortCode": cohort["cohortCode"], "error": str(err)})
        mail.reply(s.admin_login_id, f"Unallocated cohort {cohort['cohortCode']}", f"{cohort['cohortCode']}: {outcome}.")

    return report
