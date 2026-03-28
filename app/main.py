import logging
import re
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from groq import BadRequestError
from langchain_core.messages import AIMessage, HumanMessage

from app.core.logging import configure_logging
from app.graph.builder import build_graph
from app.graph.nodes.finalizer_node import finalizer_node
from app.graph.nodes.hitl_node import hitl_node
from app.schemas import (
    CalendarCachePrimeRequest,
    CalendarCachePrimeResponse,
    ChatRequest,
    ChatResponse,
    HitlResponse,
    PreferencesUpsertRequest,
)
from app.services.calendar.event_cache import event_cache
from app.services.hitl.pending_repo import pending_repo
from app.services.hitl.resolve_action import resolve_hitl_action
from app.services.memory.preferences_repo import PreferencesRepo
from app.services.time_utils import parse_natural_time
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
HITL_MARKER_RE = re.compile(r"\[hitl_action_id=(?P<action_id>[^\s\]]+)\]")
TIME_TOKEN_RE = re.compile(r"\b(?:[01]?\d|2[0-3])(?::[0-5]\d)?\s*(?:am|pm)?\b", re.IGNORECASE)


def _extract_latest_hitl_action_id(conversation_history: list[dict]) -> str | None:
    for item in reversed(conversation_history):
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, str):
            continue
        matches = list(HITL_MARKER_RE.finditer(content))
        if not matches:
            continue
        return matches[-1].group("action_id")
    return None


def _parse_iso_local(value: str | None, timezone: str) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except Exception:
        return None
    tz = ZoneInfo(timezone)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def _selected_option_index(user_message: str) -> int | None:
    text = (user_message or "").strip().lower()
    if not text:
        return None
    words_map = {"first": 1, "second": 2, "third": 3}
    for word, idx in words_map.items():
        if re.search(rf"\b{word}\b", text):
            return idx
    match = re.search(r"\b([1-3])\b", text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None


def _parse_time_token_with_anchor(
    token: str,
    anchor: datetime,
    timezone: str,
    day_hints: list[str] | None = None,
) -> datetime | None:
    text = (token or "").strip().lower()
    if not text:
        return None
    match = re.search(r"\b(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<meridiem>am|pm)?\b", text)
    if not match:
        return None

    try:
        hour = int(match.group("hour"))
        minute = int(match.group("minute") or "0")
    except Exception:
        return None
    if minute < 0 or minute > 59:
        return None

    meridiem = (match.group("meridiem") or "").lower()
    if meridiem:
        if hour < 1 or hour > 12:
            return None
        hour = hour % 12
        if meridiem == "pm":
            hour += 12
    elif hour > 23:
        return None

    local_anchor = anchor.astimezone(ZoneInfo(timezone))
    shift_days = None
    hints = day_hints or []
    if "day after tomorrow" in hints:
        shift_days = 2
    elif "tomorrow" in hints:
        shift_days = 1
    elif "today" in hints or "tonight" in hints:
        shift_days = 0

    base_date = local_anchor.date() if shift_days is None else (local_anchor + timedelta(days=shift_days)).date()
    candidate = local_anchor.replace(
        year=base_date.year,
        month=base_date.month,
        day=base_date.day,
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )
    if shift_days is None and candidate <= local_anchor:
        candidate = candidate + timedelta(days=1)
    return candidate


def _resolve_selected_start_iso(user_message: str, pending: dict, timezone: str) -> str | None:
    alternatives = pending.get("alternatives", []) if isinstance(pending, dict) else []
    if isinstance(alternatives, list) and alternatives:
        selected_idx = _selected_option_index(user_message)
        if selected_idx is not None and 1 <= selected_idx <= len(alternatives):
            selected = alternatives[selected_idx - 1]
            if isinstance(selected, dict):
                start_iso = selected.get("start_iso")
                if isinstance(start_iso, str) and start_iso.strip():
                    return start_iso.strip()

    text = (user_message or "").strip()
    if not text:
        return None

    payload = pending.get("payload", {}) if isinstance(pending, dict) else {}
    anchor = _parse_iso_local(payload.get("start_iso") if isinstance(payload, dict) else None, timezone)
    if anchor is None:
        anchor = datetime.now(ZoneInfo(timezone))

    candidates: list[str] = [text]
    lower_text = text.lower()
    day_hints: list[str] = []
    for hint in ("day after tomorrow", "tomorrow", "today", "tonight"):
        if hint in lower_text:
            day_hints.append(hint)

    time_tokens = [match.group(0).strip() for match in TIME_TOKEN_RE.finditer(text)]
    for token in time_tokens:
        if token and token not in candidates:
            candidates.append(token)
        for hint in day_hints:
            combined = f"{hint} {token}".strip()
            if combined and combined not in candidates:
                candidates.append(combined)

    for token in time_tokens:
        parsed_manual = _parse_time_token_with_anchor(
            token=token,
            anchor=anchor,
            timezone=timezone,
            day_hints=day_hints,
        )
        if parsed_manual is not None:
            return parsed_manual.isoformat()

    for candidate in candidates:
        try:
            parsed = parse_natural_time(text=candidate, timezone=timezone, now=anchor)
            return parsed.isoformat()
        except Exception:
            continue
    return None


def _chat_response_from_normalized(
    *,
    payload: ChatRequest,
    summary: str,
    normalized: dict,
    assistant_marker: str | None = None,
) -> ChatResponse:
    response_mode = normalized["response_mode"]
    latest_event_id = normalized["latest_event_id"]
    latest_start_iso = normalized.get("latest_start_iso")

    assistant_text = summary
    if assistant_marker:
        assistant_text = f"{assistant_text} {assistant_marker}".strip()
    elif latest_event_id and latest_start_iso:
        assistant_text = f"{summary} [event_id={latest_event_id} start_iso={latest_start_iso}]"
    elif latest_event_id:
        assistant_text = f"{summary} [event_id={latest_event_id}]"

    updated_history = [
        *payload.conversation_history,
        {"role": "user", "content": payload.message},
        {"role": "assistant", "content": assistant_text},
    ]

    public_hitl_action_id = normalized["hitl_action_id"]
    public_alternatives = normalized["alternatives"]
    if normalized["status"] == "needs_hitl":
        public_hitl_action_id = None
        public_alternatives = []

    return ChatResponse(
        status=normalized["status"],
        summary=summary,
        response_mode=response_mode,
        meet_link=normalized["meet_link"],
        invite_status=normalized["invite_status"],
        latest_event_id=latest_event_id,
        hitl_action_id=public_hitl_action_id,
        alternatives=public_alternatives,
        conversation_history=updated_history,
    )


def _handle_chat_hitl_followup(payload: ChatRequest, trace_id: str) -> ChatResponse | None:
    marker_action_id = _extract_latest_hitl_action_id(payload.conversation_history)
    if not marker_action_id:
        return None

    pending = pending_repo.get(marker_action_id)
    if not isinstance(pending, dict) or pending.get("user_id") != payload.user_id:
        return None

    selected_start_iso = _resolve_selected_start_iso(
        user_message=payload.message,
        pending=pending,
        timezone=payload.timezone,
    )
    if not selected_start_iso:
        summary = "Please share the exact time you'd like in IST (for example: 8:30 PM)."
        normalized = {
            "status": "needs_clarification",
            "summary": summary,
            "response_mode": "calendar_action",
            "meet_link": None,
            "invite_status": None,
            "latest_event_id": None,
            "latest_start_iso": None,
            "hitl_action_id": marker_action_id,
            "alternatives": pending.get("alternatives", []),
        }
        return _chat_response_from_normalized(
            payload=payload,
            summary=summary,
            normalized=normalized,
            assistant_marker=f"[hitl_action_id={marker_action_id}]",
        )

    resolved = resolve_hitl_action(
        pending=pending,
        decision="reschedule",
        selected_start_iso=selected_start_iso,
        action_id=marker_action_id,
        book_event_tool=book_event,
    )
    execution_result = resolved.get("execution_result", {}) if isinstance(resolved, dict) else {}

    if isinstance(execution_result, dict) and execution_result.get("status") == "conflict":
        hitl_state = hitl_node(
            {
                "trace_id": trace_id,
                "user_id": payload.user_id,
                "timezone": payload.timezone,
                "execution_result": execution_result,
            }
        )
        summary = str(hitl_state.get("summary") or "That time conflicts with another event.")
        next_action_id = hitl_state.get("hitl_action_id")
        normalized = {
            "status": "needs_hitl",
            "summary": summary,
            "response_mode": "calendar_action",
            "meet_link": None,
            "invite_status": None,
            "latest_event_id": None,
            "latest_start_iso": execution_result.get("start_iso"),
            "hitl_action_id": next_action_id,
            "alternatives": hitl_state.get("alternatives", []),
        }
        logger.info(
            "chat.hitl_followup_conflict trace_id=%s old_action_id=%s new_action_id=%s",
            trace_id,
            marker_action_id,
            next_action_id,
        )
        return _chat_response_from_normalized(
            payload=payload,
            summary=summary,
            normalized=normalized,
            assistant_marker=f"[hitl_action_id={next_action_id}]" if isinstance(next_action_id, str) and next_action_id else None,
        )

    finalized = finalizer_node(
        {
            "trace_id": trace_id,
            "user_id": resolved.get("user_id"),
            "timezone": resolved.get("timezone", payload.timezone),
            "response_mode": "calendar_action",
            "execution_result": execution_result,
            "hitl_action_id": None,
            "alternatives": [],
        }
    )
    normalized = _normalized_final_response(finalized, default_response_mode="calendar_action")
    summary = normalized["summary"]

    _refresh_cache_after_calendar_action(
        user_id=payload.user_id,
        timezone=payload.timezone,
        response_mode=normalized["response_mode"],
        status=normalized["status"],
    )
    logger.info(
        "chat.hitl_followup_done trace_id=%s action_id=%s status=%s event_id=%s",
        trace_id,
        marker_action_id,
        normalized["status"],
        normalized["latest_event_id"],
    )
    return _chat_response_from_normalized(payload=payload, summary=summary, normalized=normalized)


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


def _refresh_cache_after_calendar_action(user_id: str | None, timezone: str, response_mode: str, status: str) -> None:
    if not user_id:
        logger.info("cache.refresh_after_action.skip reason=missing_user_id response_mode=%s status=%s", response_mode, status)
        return
    if response_mode != "calendar_action":
        logger.info(
            "cache.refresh_after_action.skip reason=non_action_mode user_id=%s response_mode=%s status=%s",
            user_id,
            response_mode,
            status,
        )
        return
    if status not in {"created", "updated", "cancelled"}:
        logger.info(
            "cache.refresh_after_action.skip reason=status_not_mutating user_id=%s response_mode=%s status=%s",
            user_id,
            response_mode,
            status,
        )
        return
    try:
        cache_result = event_cache.prime_user_window(user_id=user_id, timezone=timezone)
        logger.info(
            "cache.refresh_after_action user_id=%s timezone=%s status=%s total=%s",
            user_id,
            timezone,
            status,
            cache_result.get("total_count"),
        )
    except Exception:
        logger.exception(
            "cache.refresh_after_action_failed user_id=%s timezone=%s status=%s",
            user_id,
            timezone,
            status,
        )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/calendar/cache/prime", response_model=CalendarCachePrimeResponse)
def prime_calendar_cache(payload: CalendarCachePrimeRequest) -> CalendarCachePrimeResponse:
    logger.info("cache.prime_api.start user_id=%s timezone=%s", payload.user_id, payload.timezone)
    result = event_cache.prime_user_window(user_id=payload.user_id, timezone=payload.timezone)
    logger.info(
        "cache.prime_api.done user_id=%s timezone=%s today_count=%s tomorrow_count=%s total=%s",
        payload.user_id,
        payload.timezone,
        result.get("today_count"),
        result.get("tomorrow_count"),
        result.get("total_count"),
    )
    return CalendarCachePrimeResponse(
        status=str(result.get("status", "ok")),
        today_count=int(result.get("today_count", 0)),
        tomorrow_count=int(result.get("tomorrow_count", 0)),
        total_count=int(result.get("total_count", 0)),
    )


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
    hitl_followup_response = _handle_chat_hitl_followup(payload=payload, trace_id=trace_id)
    if hitl_followup_response is not None:
        return hitl_followup_response

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
    logger.info(
        "chat.end trace_id=%s user_id=%s response_mode=%s status=%s iteration_count=%s summary=%r",
        trace_id,
        payload.user_id,
        response_mode,
        normalized["status"],
        result.get("iteration_count"),
        summary[:220],
    )
    _refresh_cache_after_calendar_action(
        user_id=payload.user_id,
        timezone=payload.timezone,
        response_mode=response_mode,
        status=normalized["status"],
    )
    assistant_marker = None
    if normalized["status"] == "needs_hitl" and normalized.get("hitl_action_id"):
        assistant_marker = f"[hitl_action_id={normalized['hitl_action_id']}]"
    return _chat_response_from_normalized(
        payload=payload,
        summary=summary,
        normalized=normalized,
        assistant_marker=assistant_marker,
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
    _refresh_cache_after_calendar_action(
        user_id=resolved.get("user_id"),
        timezone=resolved.get("timezone", "Asia/Kolkata"),
        response_mode=normalized["response_mode"],
        status=normalized["status"],
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
