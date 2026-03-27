from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import dateparser


def parse_natural_time(text: str, timezone: str, now: datetime) -> datetime:
    dt = dateparser.parse(
        text,
        settings={
            "TIMEZONE": timezone,
            "RETURN_AS_TIMEZONE_AWARE": True,
            "RELATIVE_BASE": now,
            "PREFER_DATES_FROM": "future",
        },
    )
    if dt is None:
        raise ValueError(f"Could not parse: {text}")
    return dt.astimezone(ZoneInfo(timezone))


def resolve_date_range(date_range: str, timezone: str) -> tuple[str, str]:
    now = datetime.now(ZoneInfo(timezone))
    start = parse_natural_time(date_range, timezone, now)
    end = start + timedelta(hours=8)
    return start.isoformat(), end.isoformat()

