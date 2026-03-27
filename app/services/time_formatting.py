from datetime import date, datetime
from zoneinfo import ZoneInfo


def _parse_dt_like(value: str, timezone: str) -> datetime | None:
    if not value:
        return None
    try:
        text = value.strip()
        if len(text) == 10 and text.count("-") == 2:
            year, month, day = [int(part) for part in text.split("-")]
            return datetime(year, month, day, tzinfo=ZoneInfo(timezone))
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=ZoneInfo(timezone))
        return parsed.astimezone(ZoneInfo(timezone))
    except Exception:
        return None


def parse_event_start(event: dict, timezone: str) -> datetime | None:
    start = event.get("start")
    if isinstance(start, dict):
        date_time = start.get("dateTime")
        if date_time:
            return _parse_dt_like(date_time, timezone)
        all_day = start.get("date")
        if all_day:
            return _parse_dt_like(all_day, timezone)
    start_iso = event.get("start_iso")
    if isinstance(start_iso, str):
        return _parse_dt_like(start_iso, timezone)
    return None


def format_time_only(dt: datetime) -> str:
    return dt.strftime("%I:%M %p").lstrip("0")


def relative_day_label(target: date, now_local: datetime) -> str:
    today = now_local.date()
    if target == today:
        return "today"
    if target == today.fromordinal(today.toordinal() + 1):
        return "tomorrow"
    return target.strftime("%A")
