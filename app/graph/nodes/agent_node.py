import logging
import re
from datetime import datetime

from groq import BadRequestError
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.llm.client import build_llm
from app.llm.prompts import render_agent_system_prompt, render_general_chat_prompt
from app.llm.router import ConversationMode, route_mode
from app.services.calendar.event_cache import event_cache
from app.tools.calendar_proxy import (
    book_event,
    cancel_event,
    check_availability,
    find_events,
    get_event_duration,
    get_event_location,
    update_event_location,
    update_event_duration,
    reschedule_event,
    schedule_mutual,
)

calendar_query_tools = [
    check_availability,
    find_events,
    get_event_duration,
    get_event_location,
]

calendar_action_tools = [
    book_event,
    check_availability,
    find_events,
    schedule_mutual,
    cancel_event,
    update_event_location,
    update_event_duration,
    reschedule_event,
]

proxy_tools = [
    *calendar_query_tools,
    *[tool for tool in calendar_action_tools if tool not in calendar_query_tools],
]
logger = logging.getLogger(__name__)
EVENT_MARKER_RE = re.compile(
    r"\[event_id=(?P<event_id>[^\s\]]+)(?:\s+start_iso=(?P<start_iso>[^\]]+))?\]"
)


def _is_tool_use_failed(exc: Exception) -> bool:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error_obj = body.get("error")
        if isinstance(error_obj, dict) and error_obj.get("code") == "tool_use_failed":
            return True
    return "tool_use_failed" in str(exc)


def _invoke_with_retry(llm, messages: list):
    try:
        return llm.invoke(messages)
    except BadRequestError as exc:
        if not _is_tool_use_failed(exc):
            raise
        repair_hint = SystemMessage(
            content=(
                "Use only valid tool-calling output. "
                "Do not emit pseudo tags like <function=...>. "
                "Select a provided tool and pass strict JSON arguments."
            )
        )
        return llm.invoke([messages[0], repair_hint, *messages[1:]])


def _clarification_for_mode(mode: ConversationMode) -> str:
    if mode == ConversationMode.CALENDAR_QUERY:
        return "I couldn't fetch that detail yet. Please mention the event name and day, for example: 'duration of dinner date today'."
    if mode == ConversationMode.CALENDAR_ACTION:
        return "Please rephrase your request with explicit date, time, and attendees."
    return "Please rephrase your request."


def _extract_latest_event_marker(state_messages: list) -> tuple[str | None, str | None]:
    for message in reversed(state_messages):
        content = getattr(message, "content", None)
        if not isinstance(content, str):
            continue
        matches = list(EVENT_MARKER_RE.finditer(content))
        if not matches:
            continue
        latest = matches[-1]
        return latest.group("event_id"), latest.group("start_iso")
    return None, None


def _is_suspicious_event_id(value: str | None) -> bool:
    if not isinstance(value, str):
        return True
    text = value.strip()
    if not text:
        return True
    if " " in text:
        return True
    if text.startswith("evt_"):
        return False
    if any(ch.isdigit() for ch in text):
        return False
    if "-" in text or "@" in text or "." in text:
        return False
    return True


def _is_location_update_followup(user_message: str) -> bool:
    text = (user_message or "").strip().lower()
    if not text:
        return False
    has_location_word = any(token in text for token in ("location", "venue", "address", "place"))
    if not has_location_word:
        return False
    has_update_word = any(token in text for token in ("add", "update", "change", "set", "also"))
    if not has_update_word:
        return False
    if any(token in text for token in ("book ", "schedule ", "create ", "new event", "another event")):
        return False
    return True


def _sanitize_tool_calls(
    tool_calls: list[dict],
    state_user_id: str | None,
    timezone: str,
    marker_event_id: str | None,
    marker_start_iso: str | None,
    latest_user_message: str,
) -> tuple[list[dict], str | None]:
    sanitized: list[dict] = []
    for call in tool_calls:
        if not isinstance(call, dict):
            sanitized.append(call)
            continue
        name = str(call.get("name") or "")
        args_obj = call.get("args") or {}
        args = dict(args_obj) if isinstance(args_obj, dict) else {}

        if name in {
            "book_event",
            "find_events",
            "check_availability",
            "schedule_mutual",
            "cancel_event",
            "update_event_location",
            "reschedule_event",
            "get_event_duration",
            "get_event_location",
            "update_event_duration",
        } and state_user_id:
            args["user_id"] = state_user_id

        if name in {
            "book_event",
            "check_availability",
            "schedule_mutual",
            "cancel_event",
            "update_event_location",
            "reschedule_event",
            "get_event_duration",
            "get_event_location",
            "update_event_duration",
        }:
            args["timezone"] = timezone

        if (
            name == "book_event"
            and marker_event_id
            and _is_location_update_followup(latest_user_message)
        ):
            location = args.get("location")
            if not isinstance(location, str) or not location.strip():
                return (
                    sanitized,
                    "I can update the event location, but I need the venue text to continue.",
                )
            if not isinstance(marker_start_iso, str) or not marker_start_iso.strip():
                return (
                    sanitized,
                    "I found the event but need its current start time context. Please mention the day/time once.",
                )
            rewritten = dict(call)
            rewritten["name"] = "update_event_location"
            rewritten["args"] = {
                "user_id": state_user_id,
                "timezone": timezone,
                "event_id": marker_event_id,
                "current_start_iso": marker_start_iso,
                "location": location.strip(),
            }
            sanitized.append(rewritten)
            continue

        if name in {"cancel_event", "reschedule_event"} and marker_event_id:
            args["event_id"] = marker_event_id

        if name == "update_event_location":
            if marker_event_id:
                args["event_id"] = marker_event_id
            if marker_start_iso:
                args["current_start_iso"] = marker_start_iso

            current_start_iso = args.get("current_start_iso")
            location = args.get("location")
            if not isinstance(current_start_iso, str) or not current_start_iso.strip():
                return (
                    sanitized,
                    "I found the event but need its current start time context. Please mention the day/time once.",
                )
            if not isinstance(location, str) or not location.strip():
                return (
                    sanitized,
                    "Please share the location text you want me to set for this event.",
                )

        if name == "update_event_duration":
            if marker_event_id:
                args["event_id"] = marker_event_id
            if marker_start_iso:
                args["current_start_iso"] = marker_start_iso

            event_id = args.get("event_id")
            current_start_iso = args.get("current_start_iso")
            if _is_suspicious_event_id(event_id):
                return (
                    sanitized,
                    "I couldn't find the exact event reference to update duration. Please confirm the event.",
                )
            if not isinstance(current_start_iso, str) or not current_start_iso.strip():
                return (
                    sanitized,
                    "I found the event but need its current start time context. Please mention the day/time once.",
                )

        sanitized_call = dict(call)
        sanitized_call["args"] = args
        sanitized.append(sanitized_call)
    return sanitized, None


def agent_node(state: dict) -> dict:
    trace_id = state.get("trace_id", "na")
    timezone = state.get("timezone", "Asia/Kolkata")
    no_meetings_before_hour = state.get("preferences", {}).get("no_meetings_before_hour")
    state_messages = state.get("messages", [])
    latest_user_message = ""
    for message in reversed(state_messages):
        if isinstance(message, HumanMessage):
            latest_user_message = message.content
            break

    route = route_mode(
        user_message=latest_user_message,
        conversation_history=[
            {"type": getattr(msg, "type", "unknown"), "content": getattr(msg, "content", "")}
            for msg in state_messages[-10:]
        ],
        timezone=timezone,
    )
    logger.info(
        "agent.route trace_id=%s mode=%s reason=%s confidence=%s iteration=%s message=%r",
        trace_id,
        route.mode.value,
        route.reason,
        route.confidence,
        state.get("iteration_count", 0),
        latest_user_message[:180],
    )

    if route.mode == ConversationMode.GENERAL_CHAT:
        llm = build_llm(bound_tools=[])
        system_prompt = render_general_chat_prompt(
            now_iso=datetime.now().astimezone().isoformat(), timezone=timezone
        )
        reply = llm.invoke([SystemMessage(content=system_prompt), *state_messages])
        summary = getattr(reply, "content", str(reply))
        logger.info(
            "agent.general_chat trace_id=%s summary=%r",
            trace_id,
            summary[:220],
        )
        return {
            "messages": [AIMessage(content=summary)],
            "iteration_count": state.get("iteration_count", 0) + 1,
            "response_mode": ConversationMode.GENERAL_CHAT.value,
            "summary": summary,
            "execution_result": {"status": "ok", "kind": "general_chat"},
        }

    if route.mode == ConversationMode.CALENDAR_QUERY and state.get("user_id"):
        marker_event_id, _marker_start_iso = _extract_latest_event_marker(state_messages)
        cached_query_result = event_cache.query_today_tomorrow(
            user_id=state.get("user_id"),
            timezone=timezone,
            user_message=latest_user_message,
            event_id_hint=marker_event_id,
        )
        if isinstance(cached_query_result, dict):
            logger.info(
                "agent.query_cache_hit trace_id=%s user_id=%s status=%s",
                trace_id,
                state.get("user_id"),
                cached_query_result.get("status"),
            )
            return {
                "iteration_count": state.get("iteration_count", 0) + 1,
                "response_mode": ConversationMode.CALENDAR_QUERY.value,
                "execution_result": {
                    "tool": "event_cache",
                    **cached_query_result,
                },
            }

    mode_tools = (
        calendar_query_tools
        if route.mode == ConversationMode.CALENDAR_QUERY
        else calendar_action_tools
    )
    llm = build_llm(bound_tools=mode_tools)
    system_prompt = render_agent_system_prompt(
        now_iso=datetime.now().astimezone().isoformat(),
        timezone=timezone,
        no_meetings_before_hour=no_meetings_before_hour,
        user_id=state.get("user_id"),
    )
    messages = [SystemMessage(content=system_prompt), *state_messages]
    try:
        response = _invoke_with_retry(llm, messages)
    except BadRequestError as exc:
        if _is_tool_use_failed(exc):
            body = getattr(exc, "body", None)
            failed_generation = None
            if isinstance(body, dict):
                err = body.get("error")
                if isinstance(err, dict):
                    failed_generation = err.get("failed_generation")
            logger.warning(
                "agent.tool_use_failed trace_id=%s mode=%s failed_generation=%r",
                trace_id,
                route.mode.value,
                failed_generation,
            )
            clarification = _clarification_for_mode(route.mode)
            return {
                "iteration_count": state.get("iteration_count", 0) + 1,
                "pending_clarification": clarification,
                "summary": clarification,
                "response_mode": route.mode.value,
                "execution_result": {
                    "status": "error",
                    "error_code": "tool_use_failed",
                    "error": "LLM emitted an invalid tool call format.",
                    "failed_generation": failed_generation,
                },
            }
        raise

    tool_calls = getattr(response, "tool_calls", None) or []
    logger.info(
        "agent.response trace_id=%s tool_calls=%s names=%s",
        trace_id,
        len(tool_calls),
        [call.get("name") for call in tool_calls if isinstance(call, dict)],
    )
    if tool_calls:
        marker_event_id, marker_start_iso = _extract_latest_event_marker(state_messages)
        sanitized_calls, clarification = _sanitize_tool_calls(
            tool_calls=tool_calls,
            state_user_id=state.get("user_id"),
            timezone=timezone,
            marker_event_id=marker_event_id,
            marker_start_iso=marker_start_iso,
            latest_user_message=latest_user_message,
        )
        if clarification:
            return {
                "iteration_count": state.get("iteration_count", 0) + 1,
                "pending_clarification": clarification,
                "summary": clarification,
                "response_mode": route.mode.value,
                "execution_result": {
                    "status": "error",
                    "error_code": "missing_event_context",
                    "error": clarification,
                },
            }
        if sanitized_calls != tool_calls:
            logger.info(
                "agent.sanitize_tool_calls trace_id=%s marker_event_id=%s marker_start_iso=%s",
                trace_id,
                marker_event_id,
                marker_start_iso,
            )
            if hasattr(response, "model_copy"):
                response = response.model_copy(update={"tool_calls": sanitized_calls})
            else:
                response.tool_calls = sanitized_calls

    update: dict = {
        "messages": [response],
        "iteration_count": state.get("iteration_count", 0) + 1,
        "response_mode": route.mode.value,
    }

    return update
