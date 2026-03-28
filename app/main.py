import logging
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from groq import BadRequestError
from langchain_core.messages import AIMessage, HumanMessage

from app.core.logging import configure_logging
from app.graph.builder import build_graph
from app.graph.nodes.finalizer_node import finalizer_node
from app.schemas import (
    ChatRequest,
    ChatResponse,
    HitlResponse,
    PreferencesUpsertRequest,
)
from app.services.hitl.pending_repo import pending_repo
from app.services.hitl.resolve_action import resolve_hitl_action
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


def _normalized_final_response(result: dict, default_response_mode: str) -> dict:
    execution_result = result.get("execution_result", {}) if isinstance(result, dict) else {}
    event = execution_result.get("event", {}) if isinstance(execution_result, dict) else {}
    final_response = result.get("final_response", {}) if isinstance(result, dict) else {}
    if not isinstance(final_response, dict):
        final_response = {}

    status = final_response.get("status")
    if not status:
        status = execution_result.get("status", "ok") if isinstance(execution_result, dict) else "ok"
    response_mode = final_response.get("response_mode") or result.get("response_mode", default_response_mode)
    summary = final_response.get("summary") or result.get("summary") or "I need one more detail to help with that."
    latest_event_id = final_response.get("latest_event_id")
    if latest_event_id is None and isinstance(event, dict):
        latest_event_id = event.get("id")
    latest_start_iso = final_response.get("latest_start_iso")
    if latest_start_iso is None and isinstance(execution_result, dict):
        latest_start_iso = execution_result.get("start_iso")
    if latest_start_iso is None and isinstance(event, dict):
        latest_start_iso = event.get("start_iso")

    return {
        "status": status,
        "summary": summary,
        "response_mode": response_mode,
        "meet_link": final_response.get("meet_link")
        if "meet_link" in final_response
        else (event.get("meet_link") if isinstance(event, dict) else None),
        "invite_status": final_response.get("invite_status")
        if "invite_status" in final_response
        else (event.get("invite_status") if isinstance(event, dict) else None),
        "latest_event_id": latest_event_id,
        "latest_start_iso": latest_start_iso,
        "hitl_action_id": final_response.get("hitl_action_id", result.get("hitl_action_id")),
        "alternatives": final_response.get("alternatives", result.get("alternatives", [])),
    }


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
    normalized = _normalized_final_response(result, default_response_mode="general_chat")
    summary = normalized["summary"]
    response_mode = normalized["response_mode"]
    latest_event_id = normalized["latest_event_id"]
    latest_start_iso = normalized.get("latest_start_iso")
    if latest_event_id and latest_start_iso:
        assistant_text = f"{summary} [event_id={latest_event_id} start_iso={latest_start_iso}]"
    elif latest_event_id:
        assistant_text = f"{summary} [event_id={latest_event_id}]"
    else:
        assistant_text = summary
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
        normalized["status"],
        result.get("iteration_count"),
        summary[:220],
    )
    return ChatResponse(
        status=normalized["status"],
        summary=summary,
        response_mode=response_mode,
        meet_link=normalized["meet_link"],
        invite_status=normalized["invite_status"],
        latest_event_id=latest_event_id,
        hitl_action_id=normalized["hitl_action_id"],
        alternatives=normalized["alternatives"],
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
    resolved = resolve_hitl_action(
        pending=pending,
        decision=payload.decision,
        selected_start_iso=payload.selected_start_iso,
        action_id=payload.action_id,
        book_event_tool=book_event,
    )

    finalized = finalizer_node(
        {
            "trace_id": trace_id,
            "user_id": resolved.get("user_id"),
            "timezone": resolved.get("timezone", "Asia/Kolkata"),
            "response_mode": "calendar_action",
            "execution_result": resolved.get("execution_result", {}),
            "hitl_action_id": resolved.get("hitl_action_id"),
            "alternatives": resolved.get("alternatives", []),
        }
    )
    normalized = _normalized_final_response(finalized, default_response_mode="calendar_action")

    logger.info(
        "hitl.respond.end trace_id=%s action_id=%s status=%s event_id=%s",
        trace_id,
        payload.action_id,
        normalized["status"],
        normalized["latest_event_id"],
    )
    return ChatResponse(
        status=normalized["status"],
        summary=normalized["summary"],
        response_mode=normalized["response_mode"],
        meet_link=normalized["meet_link"],
        invite_status=normalized["invite_status"],
        latest_event_id=normalized["latest_event_id"],
        hitl_action_id=normalized["hitl_action_id"],
        alternatives=normalized["alternatives"],
    )


# ...
@app.get("/events")
def get_events(user_id: str, start_iso: str, end_iso: str) -> dict:
    from app.tools.calendar_proxy import _client

    logger.info("api.get_events user_id=%s start_iso=%s end_iso=%s", user_id, start_iso, end_iso)
    raw = _client().call_tool(
        "mcp_google_calendar_find_events",
        {"user_id": user_id, "start_iso": start_iso, "end_iso": end_iso},
    )
    events = raw.get("events", []) if isinstance(raw, dict) else []
    return {"events": events}


@app.get("/preferences/{user_id}")
def get_preferences(user_id: str) -> dict:
    return preferences_repo.get_preferences(user_id)


@app.put("/preferences/{user_id}")
def put_preferences(user_id: str, payload: PreferencesUpsertRequest) -> dict:
    preferences_repo.upsert_preferences(user_id, payload.model_dump())
    return preferences_repo.get_preferences(user_id)
