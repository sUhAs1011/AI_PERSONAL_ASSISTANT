import json
import logging

from langchain_core.messages import ToolMessage

from app.llm.router import ConversationMode

logger = logging.getLogger(__name__)


def _parse_tool_content(content):
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        try:
            return json.loads(content)
        except Exception:
            return {"raw": content}
    return {"raw": str(content)}


def tool_result_node(state: dict) -> dict:
    trace_id = state.get("trace_id", "na")
    messages = state.get("messages", [])
    tool_messages = [msg for msg in messages if isinstance(msg, ToolMessage)]
    if not tool_messages:
        logger.info("tool_result.empty trace_id=%s", trace_id)
        return {}

    msg = tool_messages[-1]
    tool_name = getattr(msg, "name", "")
    content = _parse_tool_content(msg.content)
    logger.info("tool_result.start trace_id=%s tool=%s keys=%s", trace_id, tool_name, list(content.keys()))

    if tool_name == "find_events":
        events = content.get("events", [])
        logger.info("tool_result.find_events trace_id=%s events=%s", trace_id, len(events) if isinstance(events, list) else "na")
        return {
            "response_mode": ConversationMode.CALENDAR_QUERY.value,
            "execution_result": {"status": "ok", "events": events, "tool": tool_name},
        }

    if tool_name == "check_availability":
        logger.info("tool_result.check_availability trace_id=%s status=%s windows=%s", trace_id, content.get("status", "ok"), len(content.get("windows", [])))
        return {
            "response_mode": ConversationMode.CALENDAR_QUERY.value,
            "execution_result": {
                "status": content.get("status", "ok"),
                "summary": content.get("summary"),
                "windows": content.get("windows", []),
                "tool": tool_name,
            },
        }

    if tool_name == "get_event_duration":
        logger.info(
            "tool_result.get_event_duration trace_id=%s status=%s duration_minutes=%s",
            trace_id,
            content.get("status", "ok"),
            content.get("duration_minutes"),
        )
        return {
            "response_mode": ConversationMode.CALENDAR_QUERY.value,
            "execution_result": {
                "status": content.get("status", "ok"),
                "summary": content.get("summary"),
                "title": content.get("title") or content.get("title_hint"),
                "duration_minutes": content.get("duration_minutes"),
                "start_iso": content.get("start_iso"),
                "end_iso": content.get("end_iso"),
                "tool": tool_name,
            },
        }

    if tool_name == "schedule_mutual":
        alternatives = content.get("alternatives", [])
        if alternatives:
            logger.info("tool_result.schedule_mutual trace_id=%s alternatives=%s", trace_id, len(alternatives))
            return {
                "needs_hitl": True,
                "alternatives": alternatives,
                "response_mode": ConversationMode.CALENDAR_ACTION.value,
                "execution_result": {
                    "status": "conflict",
                    "alternatives": alternatives,
                    "tool": tool_name,
                },
            }
        return {
            "response_mode": ConversationMode.CALENDAR_ACTION.value,
            "execution_result": {"status": "ok", "alternatives": [], "tool": tool_name},
        }

    if tool_name in {"book_event", "reschedule_event", "update_event_duration", "cancel_event"}:
        status = content.get("status", "ok")
        logger.info("tool_result.action trace_id=%s tool=%s status=%s", trace_id, tool_name, status)
        return {
            "response_mode": ConversationMode.CALENDAR_ACTION.value,
            "execution_result": {"status": status, **content, "tool": tool_name},
        }

    logger.info("tool_result.other trace_id=%s tool=%s", trace_id, tool_name)
    return {"execution_result": {"status": "ok", "tool": tool_name, **content}}
