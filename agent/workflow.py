"""Coach agent workflow: read coach mail, act on batch requests and unallocated cohorts, report to admin."""
import json
from datetime import date

from openai import OpenAI

from app.config import get_settings
from app.llm import get_llm_client

from .clients import CoachMailClient, TrainMateClient, TrainMateError

REQUIRED_FIELDS = ["cohortCode", "requiredSkill", "numberOfTrainees", "startDate", "endDate"]

EXTRACT_PROMPT = (
    "Read the mail and decide whether it asks to create, set up, or open a new training batch or cohort. "
    "Return a JSON object with keys: isBatchRequest (boolean), cohortCode, serviceLine, stream, requiredSkill, "
    "numberOfTrainees (integer), startDate (YYYY-MM-DD), endDate (YYYY-MM-DD), vertical, location, "
    "missing (list of required fields the mail does not state). "
    "Set isBatchRequest to false for greetings, lunch invitations, status updates, or anything that is not a request to create a batch. "
    "Required fields: cohortCode, requiredSkill, numberOfTrainees, startDate, endDate. "
    "Never invent values: leave a field out if the mail does not state it. Optional fields may be omitted."
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


def validate_request(data: dict) -> list[str]:
    """Returns a list of problems. Empty list means the request can be created."""
    problems = [f"missing {f}" for f in REQUIRED_FIELDS if not data.get(f)]
    if problems:
        return problems
    try:
        start, end = date.fromisoformat(data["startDate"]), date.fromisoformat(data["endDate"])
    except (ValueError, TypeError):
        return ["dates must be YYYY-MM-DD"]
    if end < start:
        problems.append("endDate is before startDate")
    try:
        trainees = int(data["numberOfTrainees"])
    except (ValueError, TypeError):
        return problems + ["numberOfTrainees must be a whole number"]
    if not (1 <= trainees <= 500):
        problems.append("numberOfTrainees must be between 1 and 500")
    return problems


def cohort_payload(data: dict) -> dict:
    keys = ["cohortCode", "serviceLine", "stream", "requiredSkill", "startDate", "endDate", "vertical", "location"]
    payload = {k: data[k] for k in keys if data.get(k)}
    payload["numberOfTrainees"] = int(data["numberOfTrainees"])
    return payload


def run_workflow() -> list[dict]:
    s = get_settings()
    llm = get_llm_client()
    mail = CoachMailClient(s.app_base_url, s.coach_login_id, s.coach_password)
    trainmate = TrainMateClient(s.trainmate_base_url, s.coach_login_id, s.coach_password)
    report: list[dict] = []

    # 1) Batch requests from mail -> create cohort -> reply to sender.
    #    The LLM decides whether a mail is a batch request, so no embedding threshold is needed.
    for msg in mail.inbox():
        if msg["is_read"]:
            continue
        try:
            data = extract_request(llm, s.openai_model, msg["subject"], msg["body"])
        except Exception as err:  # one bad mail must not stop the run; it is reported and left unread
            report.append({"action": "failed", "mail": msg["id"], "error": f"could not read mail: {err}"})
            continue

        if not data.get("isBatchRequest"):
            report.append({"action": "ignored", "mail": msg["id"], "subject": msg["subject"]})
            continue

        problems = validate_request(data)
        if problems:
            mail.reply(msg["from_username"], f"Re: {msg['subject']}",
                       "Batch not created. Please send: " + "; ".join(problems) + ".")
            report.append({"action": "asked_for_details", "mail": msg["id"], "problems": problems})
        else:
            try:
                cohort = trainmate.create_cohort(cohort_payload(data))
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
