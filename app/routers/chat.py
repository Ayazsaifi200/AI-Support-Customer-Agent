"""Chat endpoint that drives the LangGraph customer-support agent."""
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.agent.graph import run_agent, stream_agent
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        result = run_agent(
            user_message=req.message,
            customer_id=req.customer_id,
            history=[m.model_dump() for m in req.history],
        )
    except Exception as exc:  # surface agent/LLM errors as 502
        raise HTTPException(status_code=502, detail=f"Agent error: {exc}") from exc
    return ChatResponse(**result)


@router.post("/chat/stream")
def chat_stream(req: ChatRequest):
    """Stream the agent's reasoning steps live as Server-Sent Events."""

    def event_source():
        try:
            for event in stream_agent(
                user_message=req.message,
                customer_id=req.customer_id,
                history=[m.model_dump() for m in req.history],
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

