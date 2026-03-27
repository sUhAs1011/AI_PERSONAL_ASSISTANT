import logging
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from groq import BadRequestError
from langchain_core.messages import AIMessage, HumanMessage

from app.core.logging import configure_logging
from app.graph.builder import build_graph
from app.schemas import (
    ChatRequest,
    ChatResponse,
    HitlResponse,
    PreferencesUpsertRequest,
)
from app.services.hitl.pending_repo import pending_repo
from app.services.memory.preferences_repo import PreferencesRepo
from app.tools.calendar_proxy import book_event

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Intelligent PA")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
booking_graph = build_graph()
preferences_repo = PreferencesRepo()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    trace_id = uuid4().hex[:8]
    logger.info(
        "chat.start trace_id=%s user_id=%s timezone=%s history_len=%s message=%r",
        trace_id,
        payload.user_id,
        payload.timezone,
        len(payload.conversation_history),
        payload.message[:200],
    )
    prefs = preferences_repo.get_preferences(payload.user_id)
    message_history = []
    for item in payload.conversation_history:
        if item.get("role") == "user":
            message_history.append(HumanMessage(content=item.get("content", "")))
        elif item.get("role") == "assistant":
            message_history.append(AIMessage(content=item.get("content", "")))
    message_history.append(HumanMessage(content=payload.message))

    state = {
        "trace_id": trace_id,
        "user_id": payload.user_id,
        "timezone": payload.timezone,
        "messages": message_history,
        "preferences": prefs,
        "iteration_count": 0,
    }
    try:
        result = booking_graph.invoke(state)
    except BadRequestError as exc:
        body = getattr(exc, "body", None)
        error_code = None
        if isinstance(body, dict):
            err = body.get("error")
            if isinstance(err, dict):
                error_code = err.get("code")
        if error_code == "tool_use_failed":
            logger.warning(
                "chat.tool_use_failed trace_id=%s user_id=%s body=%s",
                trace_id,
                payload.user_id,
                body,
            )
            updated_history = [
                *payload.conversation_history,
                {"role": "user", "content": payload.message},
                {
                    "role": "assistant",
                    "content": "Please rephrase with explicit date, time, and attendees.",
                },
            ]
            return ChatResponse(
                status="needs_clarification",
                summary="Please rephrase with explicit date, time, and attendees.",
                response_mode="calendar_action",
                conversation_history=updated_history,
            )
        logger.exception(
            "chat.invoke_error trace_id=%s user_id=%s",
            trace_id,
            payload.user_id,
        )
        raise
    summary = result.get("summary") or "I need one more detail to help with that."
    response_mode = result.get("response_mode", "general_chat")
    event = result.get("execution_result", {}).get("event", {})
    latest_event_id = event.get("id")
    assistant_text = f"{summary} [event_id={latest_event_id}]" if latest_event_id else summary
    updated_history = [
        *payload.conversation_history,
        {"role": "user", "content": payload.message},
        {"role": "assistant", "content": assistant_text},
    ]
    logger.info(
        "chat.end trace_id=%s user_id=%s response_mode=%s status=%s iteration_count=%s summary=%r",
        trace_id,
        payload.user_id,
        response_mode,
        result.get("execution_result", {}).get("status", "ok"),
        result.get("iteration_count"),
        summary[:220],
    )
    return ChatResponse(
        status=result.get("execution_result", {}).get("status", "ok"),
        summary=summary,
        response_mode=response_mode,
        meet_link=event.get("meet_link"),
        invite_status=event.get("invite_status"),
        latest_event_id=latest_event_id,
        hitl_action_id=result.get("hitl_action_id"),
        alternatives=result.get("alternatives", []),
        conversation_history=updated_history,
    )


@app.post("/hitl/respond", response_model=ChatResponse)
def respond_hitl(payload: HitlResponse) -> ChatResponse:
    trace_id = uuid4().hex[:8]
    logger.info(
        "hitl.respond.start trace_id=%s action_id=%s decision=%s selected_start_iso=%s",
        trace_id,
        payload.action_id,
        payload.decision,
        payload.selected_start_iso,
    )
    pending = pending_repo.get(payload.action_id)
    if not pending:
        logger.warning("hitl.respond.invalid_action trace_id=%s action_id=%s", trace_id, payload.action_id)
        return ChatResponse(status="error", summary="Invalid action id", response_mode="calendar_action")
    if payload.decision != "reschedule" or not payload.selected_start_iso:
        logger.info("hitl.respond.no_rebooking trace_id=%s action_id=%s", trace_id, payload.action_id)
        return ChatResponse(
            status="cancelled", summary="No rebooking action taken", response_mode="calendar_action"
        )

    result = book_event.invoke(
        {
            "user_id": pending["user_id"],
            "timezone": pending.get("timezone", "Asia/Kolkata"),
            "title": pending["payload"]["title"],
            "start_iso": payload.selected_start_iso,
            "duration_minutes": pending["payload"].get("duration_minutes", 30),
            "attendees": pending["payload"].get("attendees", []),
            "send_invites": pending["payload"].get("send_invites", False),
            "add_meet_link": pending["payload"].get("add_meet_link", False),
        }
    )
    event = result.get("event", {})
    logger.info(
        "hitl.respond.end trace_id=%s action_id=%s status=%s event_id=%s",
        trace_id,
        payload.action_id,
        result.get("status", "ok"),
        event.get("id"),
    )
    return ChatResponse(
        status=result.get("status", "ok"),
        summary="Rescheduled successfully",
        response_mode="calendar_action",
        meet_link=event.get("meet_link"),
        invite_status=event.get("invite_status"),
    )


@app.get("/preferences/{user_id}")
def get_preferences(user_id: str) -> dict:
    return preferences_repo.get_preferences(user_id)


@app.put("/preferences/{user_id}")
def put_preferences(user_id: str, payload: PreferencesUpsertRequest) -> dict:
    preferences_repo.upsert_preferences(user_id, payload.model_dump())
    return preferences_repo.get_preferences(user_id)
