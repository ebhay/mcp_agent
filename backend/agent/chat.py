"""Query mode: the LLM chooses coach tools in a bounded loop. Emits events so the UI can show each step."""
import json

from .tools import TOOLS, CoachContext, dispatch

MAX_STEPS = 10
SYSTEM = (
    "You are the TrainMate assistant for the coach and admin accounts. Use the tools to act; do not say you cannot do something "
    "when a tool exists. Look up ids and codes with list or get tools before acting; never invent them. "
    "Actions that delete, cancel, or reassign a trainer must be described to the user first, and you may pass confirmed=true only "
    "after the user's latest message clearly agrees. Reallocate and create are fine when the user asked for them. "
    "When done, reply with a short summary: what changed, the cohort codes or ids, and any problems."
) + "\n"

def summarize(result) -> str:
    if isinstance(result, dict) and result.get("needs_confirmation"):
        return "waiting for your confirmation"
    if isinstance(result, list):
        return f"{len(result)} item(s)"
    if isinstance(result, dict):
        if "cohortCode" in result:
            text = f"{result['cohortCode']} · {result.get('status', '')}"
            if result.get("assignedTrainerName"):
                text += f" · {result['assignedTrainerName']}"
            return text
        if "subject" in result:
            return "mail sent"
    return "done"


def stream_query(history: list[dict]):
    ctx = CoachContext()
    convo = [{"role": "system", "content": SYSTEM}] + history

    for step in range(1, MAX_STEPS + 1):
        yield {"type": "thinking", "step": step}
        response = ctx.llm.chat.completions.create(
            model=ctx.s.openai_model, messages=convo, tools=TOOLS, tool_choice="auto"
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            yield {"type": "reply", "text": msg.content or ""}
            return

        if msg.content:
            yield {"type": "note", "text": msg.content}
        convo.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
        })
        for call in msg.tool_calls:
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            yield {"type": "tool_call", "id": call.id, "tool": call.function.name, "args": args}
            try:
                result = dispatch(call.function.name, args, ctx)
                content = json.dumps(result, default=str)[:4000]
                event = {"type": "tool_result", "id": call.id, "tool": call.function.name, "ok": True, "summary": summarize(result)}
            except Exception as err:  # the model sees the error and can explain or retry
                content = json.dumps({"error": str(err)})
                event = {"type": "tool_result", "id": call.id, "tool": call.function.name, "ok": False, "summary": str(err)}
            yield event
            convo.append({"role": "tool", "tool_call_id": call.id, "content": content})

    yield {"type": "reply", "text": "Stopped after several steps. Please narrow the request."}
