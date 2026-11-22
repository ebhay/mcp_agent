import json

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from openai import APIConnectionError, APIStatusError
from pydantic import BaseModel, Field

from ..deps import require_role

router = APIRouter(prefix="/api/agent", tags=["agent"])


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class ChatIn(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)


def _provider_error(err: Exception) -> HTTPException:
    if isinstance(err, APIStatusError) and err.status_code in (429, 503):
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The AI provider is busy right now. Wait a minute and send again.")
    if isinstance(err, APIConnectionError):
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Could not reach the AI provider. Check the network and OPENAI_BASE_URL.")
    return HTTPException(status.HTTP_502_BAD_GATEWAY, "AI provider error. Check the backend log.")


@router.post("/chat/stream")
def chat_stream(payload: ChatIn, user: dict = Depends(require_role("coach", "admin"))):
    """Query mode with live steps, sent as newline-delimited JSON events."""
    from agent.chat import stream_query

    history = [m.model_dump() for m in payload.messages]

    def events():
        try:
            for event in stream_query(history):
                yield json.dumps(event, default=str) + "\n"
        except (APIStatusError, APIConnectionError) as err:
            yield json.dumps({"type": "error", "message": _provider_error(err).detail}) + "\n"

    return StreamingResponse(events(), media_type="application/x-ndjson")


@router.post("/run-mail")
def run_mail(user: dict = Depends(require_role("coach"))):
    """Mail mode: reads coach mail, creates batches, reallocates unassigned cohorts, reports to admin."""
    from agent.clients import TrainMateUnavailable
    from agent.workflow import run_workflow
    try:
        return {"report": run_workflow()}
    except TrainMateUnavailable as err:
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, str(err))
    except httpx.HTTPError:
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, "Could not reach TrainMate. Check TRAINMATE_BASE_URL and try again.")
    except (APIStatusError, APIConnectionError) as err:
        raise _provider_error(err)
