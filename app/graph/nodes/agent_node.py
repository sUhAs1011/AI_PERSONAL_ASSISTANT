import logging
from datetime import datetime

from groq import BadRequestError
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.llm.client import build_llm
from app.llm.prompts import render_agent_system_prompt, render_general_chat_prompt
from app.llm.router import ConversationMode, route_mode
from app.tools.calendar_proxy import (
    book_event,
    cancel_event,
    check_availability,
    find_events,
    get_event_duration,
    update_event_duration,
    reschedule_event,
    schedule_mutual,
)

calendar_query_tools = [
    check_availability,
    find_events,
    get_event_duration,
]

calendar_action_tools = [
    book_event,
    check_availability,
    find_events,
    schedule_mutual,
    cancel_event,
    update_event_duration,
    reschedule_event,
]

proxy_tools = [
    *calendar_query_tools,
    *[tool for tool in calendar_action_tools if tool not in calendar_query_tools],
]
logger = logging.getLogger(__name__)


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
    update: dict = {
        "messages": [response],
        "iteration_count": state.get("iteration_count", 0) + 1,
        "response_mode": route.mode.value,
    }

    return update
