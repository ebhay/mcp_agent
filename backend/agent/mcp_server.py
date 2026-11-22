"""MCP server exposing coach-only tools. Run with: python -m agent.mcp_server (stdio transport)."""
from functools import lru_cache

from mcp.server.fastmcp import FastMCP

from app.config import get_settings
from app.llm import get_llm_client

from .clients import CoachMailClient, TrainMateClient
from .semantic import IntentMatcher
from .workflow import cohort_payload, extract_request, validate_request

mcp = FastMCP("trainmate-coach-agent")


@lru_cache
def _clients():
    s = get_settings()
    llm = get_llm_client()
    return {
        "llm": llm,
        "matcher": IntentMatcher(llm, s.embedding_model, s.batch_match_threshold),
        "mail": CoachMailClient(s.app_base_url, s.coach_login_id, s.coach_password),
        "trainmate": TrainMateClient(s.trainmate_base_url, s.coach_login_id, s.coach_password),
    }


@mcp.tool()
def read_coach_inbox(unread_only: bool = True) -> list[dict]:
    """Coach mailbox messages (subject, body, sender). Only the coach's own mail is visible."""
    messages = _clients()["mail"].inbox()
    return [m for m in messages if not (unread_only and m["is_read"])]


@mcp.tool()
def find_batch_requests() -> list[dict]:
    """Semantic search over unread coach mail: returns messages that look like batch-creation requests."""
    c = _clients()
    hits = []
    for m in c["mail"].inbox():
        if not m["is_read"] and c["matcher"].match(f"{m['subject']}\n{m['body']}") == "create_batch":
            hits.append(m)
    return hits


@mcp.tool()
def extract_batch_request(message_id: str) -> dict:
    """Extracts cohort fields from a mail and lists any problems blocking creation."""
    c = _clients()
    msg = next((m for m in c["mail"].inbox() if m["id"] == message_id), None)
    if msg is None:
        raise ValueError("Message not found in coach inbox")
    data = extract_request(c["llm"], get_settings().openai_model, msg["subject"], msg["body"])
    return {"fields": data, "problems": validate_request(data)}


@mcp.tool()
def create_cohort(fields: dict) -> dict:
    """Creates a cohort for this coach. Fields follow TrainMate's CreateCohortRequest. Runs auto-allocation."""
    problems = validate_request(fields)
    if problems:
        raise ValueError("; ".join(problems))
    return _clients()["trainmate"].create_cohort(cohort_payload(fields))


@mcp.tool()
def list_my_cohorts(status: str | None = None) -> list[dict]:
    """Cohorts owned by this coach, optionally filtered by status (e.g. UNASSIGNED)."""
    cohorts = _clients()["trainmate"].list_cohorts()
    return [c for c in cohorts if status is None or c.get("status") == status]


@mcp.tool()
def reallocate_my_cohort(cohort_id: int) -> dict:
    """Re-runs allocation for one of this coach's cohorts. Refuses cohorts owned by others."""
    c = _clients()
    if not any(co["id"] == cohort_id for co in c["trainmate"].list_cohorts()):
        raise ValueError("Cohort does not belong to this coach")
    return c["trainmate"].reallocate(cohort_id)


@mcp.tool()
def reply_to_admin(subject: str, body: str) -> dict:
    """Sends a mail from the coach to the admin account. Coaches can only reply to admins."""
    return _clients()["mail"].reply(get_settings().admin_login_id, subject, body)


if __name__ == "__main__":
    mcp.run()
