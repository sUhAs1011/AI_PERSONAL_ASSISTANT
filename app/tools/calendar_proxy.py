import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_core.tools import tool

from app.services.calendar.mcp_client import MCPClient
from app.services.time_utils import parse_natural_time, resolve_date_range

logger = logging.getLogger(__name__)


def _client() -> MCPClient:
    return MCPClient(base_url=os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8080"))


def _format_window(window: dict) -> str:
    start = window.get("start_iso") or window.get("start")
    end = window.get("end_iso") or window.get("end")
    if not start or not end:
        return "a free slot in that range"
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    start_s = start_dt.strftime("%I:%M %p").lstrip("0")
    end_s = end_dt.strftime("%I:%M %p").lstrip("0")
    return f"{start_s}-{end_s} on {start_dt.strftime('%A')}"


@tool
def check_availability(
    user_id: str, date_range: str, timezone: str, attendees: list[str] | None = None
) -> dict:
    """Check free time in a natural-language date range and return a human-readable summary with normalized free windows."""
    logger.info("tool.check_availability.start user_id=%s date_range=%r timezone=%s attendees=%s", user_id, date_range, timezone, len(attendees or []))
    start_iso, end_iso = resolve_date_range(date_range, timezone)
    raw = _client().call_tool(
        "mcp_google_calendar_query_free_busy",
        {
            "user_id": user_id,
            "start_iso": start_iso,
            "end_iso": end_iso,
            "attendees": attendees or [],
        },
    )
    windows = raw.get("free_windows", []) if isinstance(raw, dict) else []
    if windows:
        summary = f"You're free {_format_window(windows[0])}."
        logger.info("tool.check_availability.free user_id=%s windows=%s", user_id, len(windows))
        return {"status": "free", "summary": summary, "windows": windows, "raw": raw}
    logger.info("tool.check_availability.busy user_id=%s", user_id)
    return {
        "status": "busy",
        "summary": "No free windows found in that range.",
        "windows": [],
        "raw": raw,
    }


@tool
def find_events(user_id: str, start_iso: str, end_iso: str) -> dict:
    """Find events in a range and always return {'events': list[dict]} for downstream stability."""
    logger.info("tool.find_events.start user_id=%s start_iso=%s end_iso=%s", user_id, start_iso, end_iso)
    raw = _client().call_tool(
        "mcp_google_calendar_find_events",
        {"user_id": user_id, "start_iso": start_iso, "end_iso": end_iso},
    )
    events = raw.get("events") if isinstance(raw, dict) else []
    logger.info("tool.find_events.end user_id=%s events=%s", user_id, len(events or []))
    return {"events": events or []}


@tool
def schedule_mutual(
    user_id: str,
    attendees: list[str],
    date_range: str,
    timezone: str,
    duration_minutes: int = 30,
) -> dict:
    """Find mutual free-time alternatives for attendees in a date range and return normalized options for HITL selection."""
    logger.info(
        "tool.schedule_mutual.start user_id=%s attendees=%s date_range=%r duration=%s",
        user_id,
        len(attendees),
        date_range,
        duration_minutes,
    )
    start_iso, end_iso = resolve_date_range(date_range, timezone)
    raw = _client().call_tool(
        "mcp_google_calendar_schedule_mutual",
        {
            "user_id": user_id,
            "attendees": attendees,
            "start_iso": start_iso,
            "end_iso": end_iso,
            "duration_minutes": duration_minutes,
        },
    )
    alternatives = raw.get("alternatives", []) if isinstance(raw, dict) else []
    logger.info("tool.schedule_mutual.end user_id=%s alternatives=%s", user_id, len(alternatives))
    return {"status": "ok", "alternatives": alternatives, "raw": raw}


@tool
def book_event(
    user_id: str,
    timezone: str,
    title: str,
    start_iso: str,
    duration_minutes: int,
    attendees: list[str],
    send_invites: bool,
    add_meet_link: bool,
) -> dict:
    """Book an event. Coerce non-ISO times, enforce stable output, never crash."""
    try:
        logger.info("tool.book_event.start user_id=%s title=%r start_iso=%s", user_id, title, start_iso)
        if "T" not in start_iso:
            now = datetime.now(ZoneInfo(timezone))
            coerced = parse_natural_time(start_iso, timezone, now=now)
            start_iso = coerced.isoformat()
            logger.info("tool.book_event.coerced_start user_id=%s start_iso=%s", user_id, start_iso)
        payload = {
            "user_id": user_id,
            "title": title,
            "start_iso": start_iso,
            "duration_minutes": duration_minutes,
            "attendees": attendees,
            "send_invites": send_invites,
            "add_google_meet": add_meet_link,
        }
        created = _client().call_tool("mcp_google_calendar_create_event", payload)
        event_id = created.get("id")
        if send_invites and event_id and attendees:
            _client().call_tool(
                "mcp_google_calendar_add_attendee",
                {
                    "user_id": user_id,
                    "event_id": event_id,
                    "attendees": attendees,
                    "send_updates": True,
                },
            )
        meet_link = (
            created.get("meet_link")
            or created.get("google_meet_link")
            or created.get("hangoutLink")
        )
        return {
            "status": "created",
            "event": {
                "id": event_id,
                "meet_link": meet_link,
                "invite_status": "sent" if send_invites else "not_requested",
            },
        }
    except Exception as exc:
        logger.exception("tool.book_event.error user_id=%s", user_id)
        return {"status": "error", "error": str(exc)}


@tool
def cancel_event(user_id: str, event_id: str) -> dict:
    """Cancel an existing event by id and return a stable status payload."""
    try:
        logger.info("tool.cancel_event.start user_id=%s event_id=%s", user_id, event_id)
        raw = _client().call_tool(
            "mcp_google_calendar_delete_event",
            {"user_id": user_id, "event_id": event_id},
        )
        return {"status": "cancelled", "event_id": event_id, "raw": raw}
    except Exception as exc:
        logger.exception("tool.cancel_event.error user_id=%s event_id=%s", user_id, event_id)
        return {"status": "error", "error": str(exc)}


@tool
def reschedule_event(
    user_id: str,
    timezone: str,
    event_id: str,
    new_start_iso: str,
    duration_minutes: int,
) -> dict:
    """Reschedule an event to a new time. Coerce natural language time to ISO and return normalized event payload."""
    try:
        logger.info("tool.reschedule_event.start user_id=%s event_id=%s new_start_iso=%s", user_id, event_id, new_start_iso)
        if "T" not in new_start_iso:
            now = datetime.now(ZoneInfo(timezone))
            coerced = parse_natural_time(new_start_iso, timezone, now=now)
            new_start_iso = coerced.isoformat()
            logger.info("tool.reschedule_event.coerced_start user_id=%s event_id=%s start_iso=%s", user_id, event_id, new_start_iso)
        raw = _client().call_tool(
            "mcp_google_calendar_update_event",
            {
                "user_id": user_id,
                "event_id": event_id,
                "start_iso": new_start_iso,
                "duration_minutes": duration_minutes,
            },
        )
        return {"status": "updated", "event": raw, "start_iso": new_start_iso}
    except Exception as exc:
        logger.exception("tool.reschedule_event.error user_id=%s event_id=%s", user_id, event_id)
        return {"status": "error", "error": str(exc)}
