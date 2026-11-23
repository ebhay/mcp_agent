// Batch request template for admin mail. The labels and options mirror TrainMate's create-cohort form
// and backend/agent/cohort_mail.py. Keep them in sync.

export const TEMPLATE_FIELDS = [
  { label: "Cohort Code", required: true, hint: "Unique code, up to 30 characters, e.g. QEA26SD010" },
  { label: "Trainees Count", required: true, hint: "Whole number from 1 to 500" },
  { label: "Required Skill(s)", required: true, hint: "Separate multiple skills with commas, e.g. Java, Spring Boot, MySQL" },
  { label: "Service Line", hint: "QEA, ADM, CDE or CIS. Optional, defaults to QEA" },
  { label: "Stream", hint: "Software Development, Web Development, Cloud Infrastructure or Data Engineering. Optional" },
  { label: "Start Date", required: true, hint: "YYYY-MM-DD, e.g. 2027-01-04" },
  { label: "End Date", required: true, hint: "YYYY-MM-DD, on or after the start date" },
  { label: "Industry Vertical", hint: "Healthcare, Banking, Retail, Insurance or Communications. Optional" },
  { label: "Training Location", hint: "Chennai, Pune, Bangalore, Hyderabad, Kolkata or Virtual. Optional" },
];

export const SERVICE_LINES = ["QEA", "ADM", "CDE", "CIS"];
export const STREAMS = ["Software Development", "Web Development", "Cloud Infrastructure", "Data Engineering"];
export const VERTICALS = ["Healthcare", "Banking", "Retail", "Insurance", "Communications"];
export const LOCATIONS = ["Chennai", "Pune", "Bangalore", "Hyderabad", "Kolkata", "Virtual"];
const VERTICAL_ALIASES = {
  "banking & financial services": "Banking",
  "banking and financial services": "Banking",
  "retail & consumer goods": "Retail",
  "communications & media": "Communications",
  "communications and media": "Communications",
};
const LOCATION_ALIASES = { "virtual / online": "Virtual", "virtual/online": "Virtual", online: "Virtual" };

const LINE = /^\s*[-*]?\s*([A-Za-z()/ ]+?)\s*:\s*(.*?)\s*$/;
const LABEL_LOOKUP = Object.fromEntries(TEMPLATE_FIELDS.map((f) => [f.label.toLowerCase(), f.label]));

// Dropdown choices for the form. Fields not listed here are free text or dates.
export const FIELD_OPTIONS = {
  "Service Line": SERVICE_LINES,
  Stream: STREAMS,
  "Industry Vertical": VERTICALS,
  "Training Location": LOCATIONS,
};

// Message text built from the form values, in the same "Label: value" format the agent reads.
export function buildFilledTemplate(values) {
  const lines = TEMPLATE_FIELDS.map((f) => `${f.label}: ${(values[f.label] || "").trim()}`).join("\n");
  return `Hi Coach,\n\nPlease create a new batch with the details below.\n\n${lines}\n\nThanks`;
}

// Same rule as TrainMate's create-cohort form: prefix plus a random number from 100 to 999.
export function generateCohortCode(prefix = "QEA26SD") {
  return prefix + Math.floor(100 + Math.random() * 900);
}

export function buildTemplate() {
  const lines = TEMPLATE_FIELDS.map((f) => `${f.label}: `).join("\n");
  return `Hi Coach,\n\nPlease create a new batch with the details below.\n\n${lines}\n\nThanks`;
}

// Reads "Label: value" lines. Empty values are ignored, so unused optional fields fall back to defaults.
export function parseTemplate(body) {
  const values = {};
  for (const line of body.split("\n")) {
    const match = line.match(LINE);
    if (!match) continue;
    const label = LABEL_LOOKUP[match[1].trim().toLowerCase()];
    if (label && match[2] && !(label in values)) values[label] = match[2];
  }
  return values;
}

// Three or more template labels with values means the mail is a filled-in template.
export function isCohortTemplate(values) {
  return Object.keys(values).length >= 3;
}

function parseDate(text) {
  const value = text.trim();
  let match = value.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  let year, month, day;
  if (match) [, year, month, day] = match.map(Number);
  else {
    match = value.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/);
    if (!match) return null;
    [, day, month, year] = match.map(Number);
  }
  const date = new Date(year, month - 1, day);
  const real = date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day;
  return real ? date : null;
}

function pickOption(text, options, aliases) {
  const lookup = text.trim().toLowerCase();
  if (aliases[lookup]) return aliases[lookup];
  return options.find((option) => option.toLowerCase() === lookup) ?? null;
}

// Same checks as the backend. Returns a list of problems; empty means the batch can be created.
export function validateCohortMail(values) {
  const problems = [];
  const get = (label) => (values[label] || "").trim();

  if (!get("Cohort Code")) problems.push("Cohort Code is missing");
  else if (get("Cohort Code").length > 30) problems.push("Cohort Code is longer than 30 characters");

  const trainees = get("Trainees Count");
  const count = trainees.match(/\d+/);
  if (!trainees) problems.push("Trainees Count is missing");
  else if (!count || Number(count[0]) < 1 || Number(count[0]) > 500) problems.push("Trainees Count must be a whole number from 1 to 500");

  if (!get("Required Skill(s)")) problems.push("Required Skill(s) is missing");
  else if (get("Required Skill(s)").length > 300) problems.push("Required Skill(s) is longer than 300 characters");

  const start = get("Start Date") ? parseDate(get("Start Date")) : null;
  const end = get("End Date") ? parseDate(get("End Date")) : null;
  if (!get("Start Date")) problems.push("Start Date is missing");
  else if (!start) problems.push(`Start Date '${get("Start Date")}' is not a real date; use YYYY-MM-DD, e.g. 2027-01-04`);
  if (!get("End Date")) problems.push("End Date is missing");
  else if (!end) problems.push(`End Date '${get("End Date")}' is not a real date; use YYYY-MM-DD, e.g. 2027-03-31`);
  if (start && end && end < start) problems.push("End Date is before Start Date");

  const optional = [
    ["Service Line", SERVICE_LINES, {}],
    ["Stream", STREAMS, {}],
    ["Industry Vertical", VERTICALS, VERTICAL_ALIASES],
    ["Training Location", LOCATIONS, LOCATION_ALIASES],
  ];
  for (const [label, options, aliases] of optional) {
    const text = get(label);
    if (text && !pickOption(text, options, aliases)) {
      problems.push(`${label} '${text}' must be one of: ${options.join(", ")}`);
    }
  }
  return problems;
}
