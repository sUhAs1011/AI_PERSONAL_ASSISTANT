import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.hitl.pending_repo import pending_repo
from app.services.time_formatting import format_time_only, relative_day_label

logger = logging.getLogger(__name__)


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


def _format_slot(start_iso: str | None, timezone: str) -> str | None:
    start_dt = _parse_iso_local(start_iso, timezone)
    if not start_dt:
        return None
    now_local = datetime.now(ZoneInfo(timezone))
    day_label = relative_day_label(start_dt.date(), now_local)
    time_text = format_time_only(start_dt)
    if day_label in {"today", "tomorrow"}:
        return f"{day_label} at {time_text} IST"
    return f"{day_label} at {time_text} IST"


def _build_conflict_summary(result: dict, alternatives: list[dict], timezone: str) -> str:
    conflict = result.get("conflicting_event") if isinstance(result.get("conflicting_event"), dict) else {}
    conflict_title = str(conflict.get("title") or "another event").strip()
    conflict_when = _format_slot(conflict.get("start_iso"), timezone)

    if conflict_when:
        first_line = f"You already have {conflict_title} scheduled {conflict_when}."
    else:
        first_line = f"You already have {conflict_title} scheduled around that time."

    options: list[str] = []
    for idx, alt in enumerate(alternatives[:3], start=1):
        start_iso = alt.get("start_iso") if isinstance(alt, dict) else None
        label = _format_slot(start_iso, timezone)
        if label:
            options.append(f"{idx}) {label}")

    if not options:
        return (
            f"{first_line} I can try another time if you share one in IST "
            "(for example: 'try 8:30 PM')."
        )

    options_text = "\n".join(options)
    return (
        f"{first_line}\n"
        "Here are a few free options:\n"
        f"{options_text}\n"
        "Reply with a time you prefer (for example, '8:30 PM works') and I'll try it."
    )


def hitl_node(state: dict) -> dict:
    trace_id = state.get("trace_id", "na")
    result = state.get("execution_result", {})
    timezone = state.get("timezone", "Asia/Kolkata")
    alternatives = result.get("alternatives", []) or state.get("alternatives", [])
    payload = {
        "title": str(result.get("title") or "meeting"),
        "attendees": result.get("attendees", []) if isinstance(result.get("attendees"), list) else [],
        "duration_minutes": int(result.get("duration_minutes") or 30),
        "send_invites": bool(result.get("send_invites", False)),
        "add_meet_link": bool(result.get("add_meet_link", False)),
        "start_iso": result.get("start_iso"),
    }
    action_id = pending_repo.save(
        user_id=state["user_id"],
        payload=payload,
        alternatives=alternatives,
        timezone=timezone,
    )
    logger.info("hitl.node trace_id=%s action_id=%s alternatives=%s", trace_id, action_id, len(alternatives))
    summary = _build_conflict_summary(result=result, alternatives=alternatives, timezone=timezone)
    return {
        "needs_hitl": True,
        "summary": summary,
        "hitl_action_id": action_id,
        "alternatives": alternatives,
        "execution_result": {
            "status": "needs_hitl",
            "alternatives": alternatives,
            "title": payload.get("title"),
            "start_iso": result.get("start_iso"),
            "conflicting_event": result.get("conflicting_event"),
        },
    }
