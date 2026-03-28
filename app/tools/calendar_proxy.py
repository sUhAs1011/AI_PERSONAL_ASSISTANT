import os
import logging
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from langchain_core.tools import tool

from app.services.calendar.mcp_client import MCPClient
from app.services.time_utils import parse_natural_time, resolve_date_range

logger = logging.getLogger(__name__)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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


def _format_clock(dt: datetime) -> str:
    return dt.strftime("%I:%M %p").lstrip("0")


def _parse_iso_datetime(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _parse_event_datetime(value: str | None, timezone: str) -> datetime | None:
    if not value:
        return None
    if len(value) == 10 and value.count("-") == 2:
        try:
            return datetime.fromisoformat(value).replace(tzinfo=ZoneInfo(timezone))
        except ValueError:
            return None
    parsed = _parse_iso_datetime(value)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(timezone))
    return parsed.astimezone(ZoneInfo(timezone))


def _normalize_start_iso(value: str, timezone: str) -> str:
    parsed_iso = _parse_iso_datetime(value)
    if parsed_iso is not None:
        if parsed_iso.tzinfo is None:
            parsed_iso = parsed_iso.replace(tzinfo=ZoneInfo(timezone))
        return parsed_iso.astimezone(ZoneInfo(timezone)).isoformat()
    now = datetime.now(ZoneInfo(timezone))
    parsed_natural = parse_natural_time(value, timezone, now=now)
    if parsed_natural.tzinfo is None:
        parsed_natural = parsed_natural.replace(tzinfo=ZoneInfo(timezone))
    return parsed_natural.astimezone(ZoneInfo(timezone)).isoformat()


def _partition_attendees(attendees: list[str]) -> tuple[list[str], list[str], list[str]]:
    valid_emails: list[str] = []
    invalid_email_like: list[str] = []
    non_email_tokens: list[str] = []
    for raw in attendees:
        token = raw.strip()
        if not token:
            continue
        if "@" in token:
            if EMAIL_RE.match(token):
                valid_emails.append(token)
            else:
                invalid_email_like.append(token)
        else:
            non_email_tokens.append(token)
    return valid_emails, invalid_email_like, non_email_tokens


def _resolve_duration_range(date_range: str, timezone: str) -> tuple[str, str]:
    now = datetime.now(ZoneInfo(timezone))
    normalized = (date_range or "today").strip().lower()
    if normalized == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return start.isoformat(), end.isoformat()
    if normalized == "tomorrow":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        end = start + timedelta(days=1)
        return start.isoformat(), end.isoformat()
    return resolve_date_range(date_range, timezone)


def _normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _pick_best_event(events: list[dict], title_hint: str) -> dict | None:
    if not events:
        return None
    hint = _normalize_text(title_hint)
    if not hint:
        return events[0]
    hint_tokens = set(hint.split())
    best: tuple[int, dict] | None = None
    for event in events:
        title = str(event.get("summary") or event.get("title") or "")
        title_norm = _normalize_text(title)
        title_tokens = set(title_norm.split())
        score = 0
        if title_norm and hint in title_norm:
            score += 5
        overlap = len(hint_tokens & title_tokens)
        score += overlap
        if best is None or score > best[0]:
            best = (score, event)
    if best is None or best[0] <= 0:
        return None
    return best[1]


def _event_start_end(event: dict, timezone: str) -> tuple[datetime | None, datetime | None]:
    start_obj = event.get("start", {}) if isinstance(event.get("start"), dict) else {}
    end_obj = event.get("end", {}) if isinstance(event.get("end"), dict) else {}
    start = _parse_event_datetime(
        start_obj.get("dateTime") or start_obj.get("date") or event.get("start_iso"),
        timezone,
    )
    end = _parse_event_datetime(
        end_obj.get("dateTime") or end_obj.get("date") or event.get("end_iso"),
        timezone,
    )
    return start, end


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
def get_event_duration(
    user_id: str,
    timezone: str,
    title_hint: str,
    date_range: str = "today",
) -> dict:
    """Get duration details for a named event by searching events in a date range and computing minutes from start/end."""
    logger.info(
        "tool.get_event_duration.start user_id=%s title_hint=%r date_range=%r timezone=%s",
        user_id,
        title_hint,
        date_range,
        timezone,
    )
    start_iso, end_iso = _resolve_duration_range(date_range=date_range, timezone=timezone)
    raw = _client().call_tool(
        "mcp_google_calendar_find_events",
        {"user_id": user_id, "start_iso": start_iso, "end_iso": end_iso},
    )
    events = raw.get("events", []) if isinstance(raw, dict) else []
    match = _pick_best_event(events=events, title_hint=title_hint)
    if match is None:
        logger.info("tool.get_event_duration.not_found user_id=%s title_hint=%r", user_id, title_hint)
        return {
            "status": "not_found",
            "title_hint": title_hint,
            "summary": f"I couldn't find an event matching '{title_hint}' in that time range.",
        }
    start, end = _event_start_end(match, timezone=timezone)
    title = str(match.get("summary") or match.get("title") or "that event")
    if start is None or end is None or end <= start:
        logger.warning("tool.get_event_duration.unreadable_event user_id=%s title=%r", user_id, title)
        return {
            "status": "error",
            "error_code": "duration_unavailable",
            "title": title,
            "summary": f"I found {title}, but couldn't read its start and end time to calculate duration.",
        }
    duration_minutes = int((end - start).total_seconds() // 60)
    day_label = "today" if start.date() == datetime.now(ZoneInfo(timezone)).date() else start.strftime("%A")
    summary = (
        f"Your {title} is {duration_minutes} minutes long, from {_format_clock(start)} to {_format_clock(end)} {day_label}."
    )
    logger.info(
        "tool.get_event_duration.ok user_id=%s title=%r duration_minutes=%s",
        user_id,
        title,
        duration_minutes,
    )
    return {
        "status": "ok",
        "title": title,
        "duration_minutes": duration_minutes,
        "start_iso": start.isoformat(),
        "end_iso": end.isoformat(),
        "summary": summary,
    }


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
    location: str | None = None,
) -> dict:
    """Book an event. Coerce non-ISO times, enforce stable output, never crash."""
    normalized_attendees = [
        attendee.strip()
        for attendee in (attendees or [])
        if isinstance(attendee, str) and attendee.strip()
    ]
    valid_attendees, invalid_attendees, non_email_tokens = _partition_attendees(normalized_attendees)
    if invalid_attendees:
        logger.warning(
            "tool.book_event.invalid_attendees user_id=%s count=%s",
            user_id,
            len(invalid_attendees),
        )
        return {
            "status": "error",
            "error_code": "invalid_attendees",
            "error": "One or more attendee emails are invalid.",
            "title": title,
            "start_iso": start_iso,
            "invalid_attendees": invalid_attendees,
        }

    inferred_location = (location or "").strip() or None
    if inferred_location is None and non_email_tokens:
        inferred_location = ", ".join(non_email_tokens)
        logger.info(
            "tool.book_event.inferred_location user_id=%s location=%r non_email_tokens=%s",
            user_id,
            inferred_location,
            len(non_email_tokens),
        )

    try:
        start_iso = _normalize_start_iso(start_iso, timezone)
    except Exception:
        logger.exception("tool.book_event.invalid_datetime user_id=%s start_iso=%r", user_id, start_iso)
        return {
            "status": "error",
            "error_code": "invalid_datetime",
            "error": "Could not parse the requested event time.",
            "title": title,
            "start_iso": start_iso,
            "attendee_count": len(normalized_attendees),
        }

    try:
        logger.info("tool.book_event.start user_id=%s title=%r start_iso=%s", user_id, title, start_iso)
        payload = {
            "user_id": user_id,
            "title": title,
            "start_iso": start_iso,
            "duration_minutes": duration_minutes,
            "attendees": valid_attendees,
            "send_invites": send_invites,
            "add_google_meet": add_meet_link,
        }
        if inferred_location:
            payload["location"] = inferred_location
        created = _client().call_tool("mcp_google_calendar_create_event", payload)
        event_id = created.get("id")
        meet_link = (
            created.get("meet_link")
            or created.get("google_meet_link")
            or created.get("hangoutLink")
        )
        return {
            "status": "created",
            "start_iso": start_iso,
            "event": {
                "id": event_id,
                "meet_link": meet_link,
                "invite_status": "sent" if send_invites and valid_attendees else "not_requested",
            },
        }
    except Exception as exc:
        logger.exception("tool.book_event.error user_id=%s", user_id)
        response = getattr(exc, "response", None)
        http_status = getattr(response, "status_code", None)
        return {
            "status": "error",
            "error_code": "calendar_api_error" if http_status else "internal_error",
            "error": str(exc),
            "http_status": http_status,
            "title": title,
            "start_iso": start_iso,
            "attendee_count": len(valid_attendees),
        }


@tool
def update_event_duration(
    user_id: str,
    timezone: str,
    event_id: str,
    current_start_iso: str,
    duration_minutes: int,
) -> dict:
    """Update only event duration while keeping start time unchanged. Requires event_id and the existing start time."""
    try:
        start_iso = _normalize_start_iso(current_start_iso, timezone)
    except Exception:
        logger.exception(
            "tool.update_event_duration.invalid_datetime user_id=%s event_id=%s current_start_iso=%r",
            user_id,
            event_id,
            current_start_iso,
        )
        return {
            "status": "error",
            "error_code": "invalid_datetime",
            "error": "Could not parse current_start_iso for duration update.",
            "event_id": event_id,
            "start_iso": current_start_iso,
        }

    try:
        logger.info(
            "tool.update_event_duration.start user_id=%s event_id=%s start_iso=%s duration_minutes=%s",
            user_id,
            event_id,
            start_iso,
            duration_minutes,
        )
        raw = _client().call_tool(
            "mcp_google_calendar_update_event",
            {
                "user_id": user_id,
                "event_id": event_id,
                "start_iso": start_iso,
                "duration_minutes": duration_minutes,
            },
        )
        out_event_id = raw.get("id") if isinstance(raw, dict) else None
        return {
            "status": "updated",
            "event": {"id": out_event_id or event_id},
            "event_id": out_event_id or event_id,
            "start_iso": start_iso,
            "duration_minutes": duration_minutes,
            "raw": raw,
        }
    except Exception as exc:
        logger.exception("tool.update_event_duration.error user_id=%s event_id=%s", user_id, event_id)
        return {
            "status": "error",
            "error_code": "calendar_api_error",
            "error": str(exc),
            "event_id": event_id,
            "start_iso": start_iso,
            "duration_minutes": duration_minutes,
        }


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
