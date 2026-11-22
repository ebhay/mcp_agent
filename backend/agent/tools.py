"""Tools the LLM can call in query mode. Coach and admin accounts come from .env; destructive actions need confirmation."""
from app.config import get_settings
from app.llm import get_llm_client

from .clients import (AdminMailClient, CoachMailClient, TrainMateAdminClient,
                      TrainMateClient)
from .semantic import IntentMatcher
from .workflow import cohort_payload, validate_request


class CoachContext:
    """Lazy clients for one request. Each is created on first use and reused within the request."""

    def __init__(self):
        self.s = get_settings()
        self.llm = get_llm_client()
        self._cache: dict = {}

    def _get(self, key, factory):
        if key not in self._cache:
            self._cache[key] = factory()
        return self._cache[key]

    @property
    def coach_mail(self) -> CoachMailClient:
        return self._get("coach_mail", lambda: CoachMailClient(self.s.app_base_url, self.s.coach_login_id, self.s.coach_password))

    @property
    def admin_mail(self) -> AdminMailClient:
        return self._get("admin_mail", lambda: AdminMailClient(self.s.app_base_url, self.s.admin_login_id, self.s.admin_password))

    @property
    def coach(self) -> TrainMateClient:
        return self._get("coach", lambda: TrainMateClient(self.s.trainmate_base_url, self.s.coach_login_id, self.s.coach_password))

    @property
    def admin(self) -> TrainMateAdminClient:
        return self._get("admin", lambda: TrainMateAdminClient(self.s.trainmate_base_url, self.s.admin_login_id, self.s.admin_password))

    @property
    def matcher(self) -> IntentMatcher:
        return self._get("matcher", lambda: IntentMatcher(self.llm, self.s.embedding_model, self.s.batch_match_threshold))


def _fn(name, description, properties=None, required=None):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties or {}, "required": required or []}}}


CONFIRM = {"confirmed": {"type": "boolean", "description": "Set true only after the user explicitly confirmed this action in their latest message."}}
ACCOUNT = {"type": "string", "enum": ["coach", "admin"]}

TOOLS = [
    _fn("list_notifications", "TrainMate's own mailbox for the coach or admin, including allocation notices. Use for 'latest allocation mail'.",
        {"account": ACCOUNT}, ["account"]),
    _fn("read_mail", "Read this app's mailbox for the coach or admin account.",
        {"account": ACCOUNT, "unread_only": {"type": "boolean"}}, ["account"]),
    _fn("find_batch_requests", "Semantic search over unread coach mail for batch-creation requests.", {}),
    _fn("reply_to_admin", "Send a mail from the coach to the admin.",
        {"subject": {"type": "string"}, "body": {"type": "string"}}, ["subject", "body"]),
    _fn("admin_send_mail", "Send a mail as admin to any user (coach or trainer).",
        {"to_username": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}}, ["to_username", "subject", "body"]),
    _fn("list_my_cohorts", "List this coach's cohorts from TrainMate. Optional status filter: UNASSIGNED, ASSIGNED, PENDING, ACTIVE, COMPLETED, CANCELLED.",
        {"status": {"type": "string"}}),
    _fn("create_cohort", "Create a cohort for the coach. TrainMate runs automatic trainer allocation. Required: cohortCode, requiredSkill, numberOfTrainees, startDate (YYYY-MM-DD), endDate (YYYY-MM-DD).",
        {"cohortCode": {"type": "string"}, "serviceLine": {"type": "string"}, "stream": {"type": "string"},
         "requiredSkill": {"type": "string"}, "numberOfTrainees": {"type": "integer"},
         "startDate": {"type": "string"}, "endDate": {"type": "string"},
         "vertical": {"type": "string"}, "location": {"type": "string"}},
        ["cohortCode", "requiredSkill", "numberOfTrainees", "startDate", "endDate"]),
    _fn("reallocate_cohort", "Re-run automatic trainer allocation for any cohort by numeric id (admin). Use for UNASSIGNED cohorts.",
        {"cohort_id": {"type": "integer"}}, ["cohort_id"]),
    _fn("admin_list_cohorts", "List all cohorts in the system (admin). Optional status filter.", {"status": {"type": "string"}}),
    _fn("admin_get_cohort", "Get one cohort's details, trainer, and score breakdown (admin).", {"cohort_id": {"type": "integer"}}, ["cohort_id"]),
    _fn("admin_list_trainers", "List all trainers with workload and availability (admin).", {}),
    _fn("admin_override_trainer", "Manually assign a trainer to a cohort (admin). Requires a reason. Needs confirmation.",
        {"cohort_id": {"type": "integer"}, "trainer_id": {"type": "integer"}, "reason": {"type": "string"}, **CONFIRM},
        ["cohort_id", "trainer_id", "reason"]),
    _fn("admin_set_status", "Change a cohort's status (admin). CANCELLED frees the trainer. Needs confirmation.",
        {"cohort_id": {"type": "integer"}, "status": {"type": "string"}, **CONFIRM}, ["cohort_id", "status"]),
    _fn("admin_delete_cohort", "Permanently delete a cohort (admin). Needs confirmation.",
        {"cohort_id": {"type": "integer"}, **CONFIRM}, ["cohort_id"]),
]

DESTRUCTIVE = {"admin_override_trainer", "admin_set_status", "admin_delete_cohort"}
ASK_FIRST = {"needs_confirmation": True,
             "message": "Not done yet. Describe this action to the user and ask for a yes. Call again with confirmed=true only after they agree."}


def _mailbox(ctx: CoachContext, account: str):
    return ctx.admin_mail if account == "admin" else ctx.coach_mail


def _trainmate(ctx: CoachContext, account: str):
    return ctx.admin if account == "admin" else ctx.coach


def dispatch(name: str, args: dict, ctx: CoachContext):
    if name in DESTRUCTIVE and not args.get("confirmed"):
        return ASK_FIRST

    if name == "list_notifications":
        return _trainmate(ctx, args["account"]).notifications()[:30]
    if name == "read_mail":
        messages = _mailbox(ctx, args["account"]).inbox()
        return [m for m in messages if not (args.get("unread_only", False) and m["is_read"])]
    if name == "find_batch_requests":
        return [m for m in ctx.coach_mail.inbox()
                if not m["is_read"] and ctx.matcher.match(f"{m['subject']}\n{m['body']}") == "create_batch"]
    if name == "reply_to_admin":
        return ctx.coach_mail.send(ctx.s.admin_login_id, args["subject"], args["body"])
    if name == "admin_send_mail":
        return ctx.admin_mail.send(args["to_username"], args["subject"], args["body"])

    if name == "list_my_cohorts":
        status = args.get("status")
        return [c for c in ctx.coach.list_cohorts() if status is None or c.get("status") == status]
    if name == "create_cohort":
        problems = validate_request(args)
        if problems:
            raise ValueError("; ".join(problems))
        return ctx.coach.create_cohort(cohort_payload(args))
    if name == "reallocate_cohort":
        return ctx.admin.reallocate(int(args["cohort_id"]))

    if name == "admin_list_cohorts":
        status = args.get("status")
        return [c for c in ctx.admin.list_all_cohorts() if status is None or c.get("status") == status]
    if name == "admin_get_cohort":
        return ctx.admin.get_cohort(int(args["cohort_id"]))
    if name == "admin_list_trainers":
        return ctx.admin.list_trainers()
    if name == "admin_override_trainer":
        return ctx.admin.override_trainer(int(args["cohort_id"]), int(args["trainer_id"]), args["reason"])
    if name == "admin_set_status":
        return ctx.admin.set_status(int(args["cohort_id"]), args["status"])
    if name == "admin_delete_cohort":
        return ctx.admin.delete_cohort(int(args["cohort_id"]))

    raise ValueError(f"Unknown tool: {name}")
