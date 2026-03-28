import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_core.messages import HumanMessage

from app.llm.client import build_llm
from app.llm.prompts import render_finalizer_system_prompt
from app.services.time_formatting import format_time_only, parse_event_start, relative_day_label

logger = logging.getLogger(__name__)


def finalizer_node(state: dict) -> dict:
    trace_id = state.get("trace_id", "na")
    response_mode = state.get("response_mode", "calendar_action")
    result = state.get("execution_result", {})

    if state.get("iteration_count", 0) >= 3:
        logger.warning(
            "finalizer.iteration_guard trace_id=%s iteration=%s",
            trace_id,
            state.get("iteration_count", 0),
        )
        return _finalize(
            state=state,
            summary="I need one more detail to complete this booking safely.",
        )

    existing_summary = state.get("summary")
    if existing_summary and existing_summary.strip().lower() != "done.":
        logger.info(
            "finalizer.use_existing_summary trace_id=%s summary=%r",
            trace_id,
            existing_summary[:220],
        )
        return _finalize(state=state, summary=existing_summary)

    if response_mode == "calendar_query":
        query_summary = _calendar_query_summary(state=state, result=result)
        if query_summary:
            logger.info(
                "finalizer.calendar_query trace_id=%s summary=%r",
                trace_id,
                query_summary[:220],
            )
            return _finalize(state=state, summary=query_summary)

    if response_mode == "general_chat":
        logger.info("finalizer.general_chat_default trace_id=%s", trace_id)
        return _finalize(state=state, summary="I'm here and ready to help with your day.")

    summary = _action_summary_with_fallback(response_mode=response_mode, result=result, trace_id=trace_id, timezone=state.get("timezone", "Asia/Kolkata"))
    return _finalize(state=state, summary=summary)


def _finalize(state: dict, summary: str) -> dict:
    response_mode = state.get("response_mode", "calendar_action")
    result = state.get("execution_result", {})
    final_response = _build_final_response(
        summary=summary,
        response_mode=response_mode,
        result=result,
        hitl_action_id=state.get("hitl_action_id"),
        alternatives=state.get("alternatives"),
    )
    return {
        "summary": summary,
        "response_mode": response_mode,
        "final_response": final_response,
    }


def _build_final_response(
    summary: str,
    response_mode: str,
    result: dict,
    hitl_action_id: str | None,
    alternatives: list[dict] | None,
) -> dict:
    event = result.get("event", {}) if isinstance(result, dict) else {}
    status = result.get("status", "ok") if isinstance(result, dict) else "ok"
    latest_event_id = event.get("id") if isinstance(event, dict) else None
    out = {
        "status": status,
        "summary": summary,
        "response_mode": response_mode,
        "meet_link": event.get("meet_link") if isinstance(event, dict) else None,
        "invite_status": event.get("invite_status") if isinstance(event, dict) else None,
        "latest_event_id": latest_event_id,
        "hitl_action_id": hitl_action_id,
        "alternatives": alternatives if isinstance(alternatives, list) else result.get("alternatives", []),
    }
    return out


def _action_summary_with_fallback(response_mode: str, result: dict, trace_id: str, timezone: str) -> str:
    try:
        llm = build_llm(bound_tools=[])
        msg = llm.invoke(
            [
                {"role": "system", "content": render_finalizer_system_prompt(response_mode)},
                {"role": "user", "content": f"User Timezone: {timezone}\n\nExecution result: {result}\n\nImportant: Use the User Timezone provided above when mentioning event times."},
            ]
        )
        summary = getattr(msg, "content", str(msg)).strip()
        if summary and summary.lower() != "done.":
            logger.info("finalizer.llm_summary trace_id=%s summary=%r", trace_id, summary[:220])
            return summary
    except Exception:
        logger.exception("finalizer.action_llm_error trace_id=%s", trace_id)
    fallback = _action_fallback(result)
    logger.info("finalizer.action_fallback trace_id=%s summary=%r", trace_id, fallback[:220])
    return fallback


def _calendar_query_summary(state: dict, result: dict) -> str:
    llm_summary = _calendar_query_llm_summary(state=state, result=result)
    if llm_summary:
        return llm_summary
    return _calendar_query_fallback(
        result=result,
        timezone=state.get("timezone", "Asia/Kolkata"),
        user_message=_latest_user_message(state),
    )


def _latest_user_message(state: dict) -> str:
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return getattr(msg, "content", "") or ""
    return ""


def _calendar_query_llm_summary(state: dict, result: dict) -> str | None:
    timezone = state.get("timezone", "Asia/Kolkata")
    user_message = _latest_user_message(state)
    context = _calendar_query_context_for_llm(result=result, timezone=timezone, user_message=user_message)
    if not context:
        return None
    try:
        llm = build_llm(bound_tools=[])
        msg = llm.invoke(
            [
                {"role": "system", "content": render_finalizer_system_prompt("calendar_query")},
                {
                    "role": "user",
                    "content": (
                        f"Timezone: {timezone}\n"
                        f"User asked: {user_message}\n"
                        f"Structured calendar context:\n{context}"
                    ),
                },
            ]
        )
        summary = getattr(msg, "content", str(msg)).strip()
        if summary and summary.lower() != "done." and not _looks_like_iso_text(summary):
            return summary
    except Exception:
        logger.exception("finalizer.calendar_query_llm_error")
    return None


def _calendar_query_context_for_llm(result: dict, timezone: str, user_message: str) -> str:
    lines: list[str] = []
    events = result.get("events")
    if isinstance(events, list):
        lines.append(f"event_count: {len(events)}")
        for idx, event in enumerate(events[:3], start=1):
            if not isinstance(event, dict):
                continue
            title = event.get("summary") or event.get("title") or "Untitled event"
            start_dt = parse_event_start(event, timezone)
            when = "time unavailable"
            if start_dt:
                day_label = relative_day_label(start_dt.date(), datetime.now(ZoneInfo(timezone)))
                when = f"{day_label} at {format_time_only(start_dt)}"
            lines.append(f"event_{idx}: title={title}; when={when}")

    summary = result.get("summary")
    if isinstance(summary, str) and summary.strip():
        lines.append(f"availability_summary: {summary.strip()}")

    windows = result.get("windows")
    if isinstance(windows, list) and windows:
        first = windows[0] if isinstance(windows[0], dict) else {}
        start = _parse_dt(first.get("start_iso") or first.get("start"), timezone)
        end = _parse_dt(first.get("end_iso") or first.get("end"), timezone)
        if start and end:
            lines.append(
                f"first_free_window: {relative_day_label(start.date(), datetime.now(ZoneInfo(timezone)))} "
                f"{format_time_only(start)} to {format_time_only(end)}"
            )
    if user_message:
        lines.append(f"user_message_hint: {user_message}")
    return "\n".join(lines).strip()


def _parse_dt(value: str | None, timezone: str) -> datetime | None:
    if not value:
        return None
    try:
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=ZoneInfo(timezone))
        return parsed.astimezone(ZoneInfo(timezone))
    except Exception:
        return None


def _looks_like_iso_text(text: str) -> bool:
    return bool(
        re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", text)
        or re.search(r"[+-]\d{2}:\d{2}", text)
    )


def _calendar_query_fallback(result: dict, timezone: str, user_message: str) -> str:
    now_local = datetime.now(ZoneInfo(timezone))
    asked_tomorrow = "tomorrow" in user_message.lower()
    asked_today = "today" in user_message.lower()
    events = result.get("events")
    if isinstance(events, list):
        if not events:
            if asked_tomorrow:
                return "Tomorrow looks clear with no events on your calendar."
            if asked_today:
                return "Your calendar is clear today."
            return "You have no events in that time window."
        first = events[0] if isinstance(events[0], dict) else {}
        title = first.get("summary") or first.get("title") or "an event"
        start_dt = parse_event_start(first, timezone)
        count = len(events)
        count_text = "1 event" if count == 1 else f"{count} events"
        if start_dt:
            day_label = relative_day_label(start_dt.date(), now_local)
            if asked_tomorrow and day_label == "tomorrow":
                return (
                    f"Tomorrow looks good. You have {count_text}, "
                    f"starting with {title} at {format_time_only(start_dt)}."
                )
            if asked_today and day_label == "today":
                return (
                    f"Today you have {count_text}, "
                    f"starting with {title} at {format_time_only(start_dt)}."
                )
            if day_label in {"today", "tomorrow"}:
                when = f"{day_label} at {format_time_only(start_dt)}"
            else:
                when = f"on {day_label} at {format_time_only(start_dt)}"
            return f"You have {count_text}, and the first is {title} {when}."
        return f"You have {count_text}, and the first is {title}."

    summary = result.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    windows = result.get("windows")
    if isinstance(windows, list) and windows:
        first = windows[0]
        start = _parse_dt(first.get("start_iso") or first.get("start"), timezone)
        end = _parse_dt(first.get("end_iso") or first.get("end"), timezone)
        if start and end:
            day_label = relative_day_label(start.date(), now_local)
            return f"You're free {day_label} from {format_time_only(start)} to {format_time_only(end)}."
    return "I checked your schedule but need one more detail to summarize it."


def _action_fallback(result: dict) -> str:
    status = (result or {}).get("status", "ok")
    if status == "created":
        return "Your event has been booked."
    if status == "updated":
        return "Your event has been updated."
    if status == "cancelled":
        return "Your event has been cancelled."
    if status == "needs_hitl":
        return "I found a conflict and need your preferred slot."
    if status == "error":
        return "I hit an issue while processing that calendar request."
    return "I need one more detail to complete that request."
