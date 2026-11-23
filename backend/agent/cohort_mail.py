"""Batch request mail: the admin template, its parser, and the checks that match the TrainMate cohort form.

The labels and option lists mirror TrainMate's create-cohort form. Keep them in sync with
frontend-mcp/src/cohortTemplate.js, which uses the same rules in the Compose screen.
"""
import re
from datetime import datetime

# Template label (as shown to the admin) -> canonical key used by the agent and TrainMate.
TEMPLATE_FIELDS = [
    ("Cohort Code", "cohortCode"),
    ("Trainees Count", "numberOfTrainees"),
    ("Required Skill(s)", "requiredSkill"),
    ("Service Line", "serviceLine"),
    ("Stream", "stream"),
    ("Start Date", "startDate"),
    ("End Date", "endDate"),
    ("Industry Vertical", "vertical"),
    ("Training Location", "location"),
]

REQUIRED_LABELS = {"cohortCode": "Cohort Code", "numberOfTrainees": "Trainees Count",
                   "requiredSkill": "Required Skill(s)", "startDate": "Start Date", "endDate": "End Date"}

SERVICE_LINES = ["QEA", "ADM", "CDE", "CIS"]
STREAMS = ["Software Development", "Web Development", "Cloud Infrastructure", "Data Engineering"]
VERTICALS = ["Healthcare", "Banking", "Retail", "Insurance", "Communications"]
LOCATIONS = ["Chennai", "Pune", "Bangalore", "Hyderabad", "Kolkata", "Virtual"]

# Names people type that map to the option TrainMate expects (lower-case keys).
VERTICAL_ALIASES = {
    "banking & financial services": "Banking",
    "banking and financial services": "Banking",
    "retail & consumer goods": "Retail",
    "communications & media": "Communications",
    "communications and media": "Communications",
}
LOCATION_ALIASES = {"virtual / online": "Virtual", "virtual/online": "Virtual", "online": "Virtual"}

_LABELS = {label.lower(): key for label, key in TEMPLATE_FIELDS}
_LABELS.update({
    "trainees": "numberOfTrainees",
    "number of trainees": "numberOfTrainees",
    "required skill": "requiredSkill",
    "required skills": "requiredSkill",
    "vertical": "vertical",
    "location": "location",
})
_LINE = re.compile(r"^\s*[-*]?\s*([A-Za-z()/ ]+?)\s*:\s*(.*?)\s*$")


def parse_template(body: str) -> dict:
    """Reads 'Label: value' lines. Empty lines are ignored, so unused optional fields fall back to defaults."""
    found: dict = {}
    for line in body.splitlines():
        match = _LINE.match(line)
        if not match:
            continue
        key = _LABELS.get(match.group(1).strip().lower())
        value = match.group(2).strip()
        if key and value and key not in found:
            found[key] = value
    return found


def is_template(fields: dict) -> bool:
    """Three or more template labels with values means the mail is a filled-in template."""
    return len(fields) >= 3


def _parse_date(value: str):
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            pass
    return None


def _choose(value, options, aliases, label, problems):
    text = str(value or "").strip()
    if not text:
        return None
    lookup = text.lower()
    if lookup in aliases:
        return aliases[lookup]
    for option in options:
        if option.lower() == lookup:
            return option
    problems.append(f"{label} '{text}' must be one of: {', '.join(options)}")
    return None


def normalize(raw: dict) -> tuple[dict, list[str]]:
    """Checks the cohort fields. Returns (data ready for TrainMate, problems). Create only when problems is empty."""
    problems: list[str] = []
    data: dict = {}

    code = str(raw.get("cohortCode") or "").strip()
    if not code:
        problems.append("Cohort Code is missing")
    elif len(code) > 30:
        problems.append("Cohort Code is longer than 30 characters")
    else:
        data["cohortCode"] = code

    trainees = str(raw.get("numberOfTrainees") or "").strip()
    number = re.search(r"\d+", trainees)
    if not trainees:
        problems.append("Trainees Count is missing")
    elif not number or not 1 <= int(number.group()) <= 500:
        problems.append("Trainees Count must be a whole number from 1 to 500")
    else:
        data["numberOfTrainees"] = int(number.group())

    skill = str(raw.get("requiredSkill") or "").strip()
    if not skill:
        problems.append("Required Skill(s) is missing")
    elif len(skill) > 300:
        problems.append("Required Skill(s) is longer than 300 characters")
    else:
        data["requiredSkill"] = skill

    start = end = None
    if not str(raw.get("startDate") or "").strip():
        problems.append("Start Date is missing")
    else:
        start = _parse_date(str(raw["startDate"]))
        if start is None:
            problems.append(f"Start Date '{raw['startDate']}' is not a real date; use YYYY-MM-DD, e.g. 2027-01-04")
        else:
            data["startDate"] = start.isoformat()
    if not str(raw.get("endDate") or "").strip():
        problems.append("End Date is missing")
    else:
        end = _parse_date(str(raw["endDate"]))
        if end is None:
            problems.append(f"End Date '{raw['endDate']}' is not a real date; use YYYY-MM-DD, e.g. 2027-03-31")
        else:
            data["endDate"] = end.isoformat()
    if start and end and end < start:
        problems.append("End Date is before Start Date")

    chosen = {
        "serviceLine": _choose(raw.get("serviceLine"), SERVICE_LINES, {}, "Service Line", problems),
        "stream": _choose(raw.get("stream"), STREAMS, {}, "Stream", problems),
        "vertical": _choose(raw.get("vertical"), VERTICALS, VERTICAL_ALIASES, "Industry Vertical", problems),
        "location": _choose(raw.get("location"), LOCATIONS, LOCATION_ALIASES, "Training Location", problems),
    }
    data.update({key: value for key, value in chosen.items() if value})
    return data, problems
