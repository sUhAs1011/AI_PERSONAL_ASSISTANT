import hashlib
import logging
import os
import re
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.services.calendar.mcp_client import MCPClient

logger = logging.getLogger(__name__)

_LOCATION_HINTS = ("where", "location", "venue", "address", "place")
_DURATION_HINTS = ("duration", "how long", "minutes")
_OUT_OF_WINDOW_HINTS = ("next week", "next month", "next year")


def _normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _parse_iso_datetime(value: str | None, timezone: str) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=ZoneInfo(timezone))
    return parsed.astimezone(ZoneInfo(timezone))


def _extract_start_end_iso(event: dict) -> tuple[str | None, str | None]:
    start_obj = event.get("start", {}) if isinstance(event.get("start"), dict) else {}
    end_obj = event.get("end", {}) if isinstance(event.get("end"), dict) else {}
    start_iso = start_obj.get("dateTime") or start_obj.get("date") or event.get("start_iso")
    end_iso = end_obj.get("dateTime") or end_obj.get("date") or event.get("end_iso")
    return start_iso, end_iso


def _extract_title_hint(user_message: str) -> str | None:
    text = (user_message or "").strip().lower()
    if not text:
        return None

    cleaned = re.sub(r"[?!.,]", "", text)
    patterns = [
        r"(?:where is|where's|location of|venue of|address of)\s+(?:my\s+)?(.+?)(?:\s+(?:today|tomorrow))?$",
        r"(?:duration of|how long is|how long's)\s+(?:my\s+)?(.+?)(?:\s+(?:today|tomorrow))?$",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned)
        if match:
            candidate = (match.group(1) or "").strip()
            if candidate:
                return candidate

    if "my " in cleaned:
        tail = cleaned.split("my ", 1)[1]
        tail = re.sub(r"\b(today|tomorrow)\b", "", tail).strip()
        if tail:
            return tail
    return None


def _contains_hint(text: str, hints: tuple[str, ...]) -> bool:
    lowered = (text or "").lower()
    return any(hint in lowered for hint in hints)


def _default_fetch_events(user_id: str, start_iso: str, end_iso: str) -> list[dict]:
    client = MCPClient(base_url=os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8080"))
    raw = client.call_tool(
        "mcp_google_calendar_find_events",
        {"user_id": user_id, "start_iso": start_iso, "end_iso": end_iso},
    )
    events = raw.get("events", []) if isinstance(raw, dict) else []
    return [event for event in events if isinstance(event, dict)]


class EventCacheService:
    def __init__(
        self,
        fetch_events=None,
        now_fn=None,
        ttl_seconds: int = 300,
    ) -> None:
        self._fetch_events = fetch_events or _default_fetch_events
        self._now_fn = now_fn or (lambda timezone: datetime.now(ZoneInfo(timezone)))
        self._ttl_seconds = max(30, int(ttl_seconds))
        self._lock = threading.RLock()
        self._store: dict[str, dict] = {}

    def canonical_event_id(
        self,
        user_id: str,
        provider_event_id: str | None,
        title: str,
        start_iso: str,
    ) -> str:
        base = f"{user_id}|{provider_event_id or ''}|{_normalize_text(title)}|{start_iso}"
        digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]
        return f"evtc_{digest}"

    def prime_user_window(self, user_id: str, timezone: str) -> dict:
        now_local = self._now_fn(timezone)
        today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_start = today_start + timedelta(days=1)
        day_after_tomorrow_start = today_start + timedelta(days=2)
        logger.info(
            "event_cache.prime.start user_id=%s timezone=%s window_start=%s window_end=%s",
            user_id,
            timezone,
            today_start.isoformat(),
            day_after_tomorrow_start.isoformat(),
        )

        events = self._fetch_events(
            user_id,
            today_start.isoformat(),
            day_after_tomorrow_start.isoformat(),
        )

        events_by_day: dict[str, list[dict]] = {
            today_start.date().isoformat(): [],
            tomorrow_start.date().isoformat(): [],
        }

        for event in events:
            normalized = self._normalize_event(user_id=user_id, event=event, timezone=timezone)
            if normalized is None:
                continue
            event_day = normalized["start_local_date"]
            if event_day in events_by_day:
                events_by_day[event_day].append(normalized)

        entry = {
            "timezone": timezone,
            "fetched_at": datetime.now(ZoneInfo("UTC")),
            "events_by_day": events_by_day,
        }
        with self._lock:
            self._store[user_id] = entry

        today_count = len(events_by_day[today_start.date().isoformat()])
        tomorrow_count = len(events_by_day[tomorrow_start.date().isoformat()])
        logger.info(
            "event_cache.prime.done user_id=%s timezone=%s fetched=%s today_count=%s tomorrow_count=%s total=%s",
            user_id,
            timezone,
            len(events),
            today_count,
            tomorrow_count,
            today_count + tomorrow_count,
        )
        return {
            "status": "ok",
            "today_count": today_count,
            "tomorrow_count": tomorrow_count,
            "total_count": today_count + tomorrow_count,
        }

    def refresh_user_window(self, user_id: str, timezone: str) -> dict:
        return self.prime_user_window(user_id=user_id, timezone=timezone)

    def get_events_for_day(self, user_id: str, timezone: str, day_label: str) -> list[dict]:
        now_local = self._now_fn(timezone)
        day_offset = 1 if day_label == "tomorrow" else 0
        target_date = (now_local.date() + timedelta(days=day_offset)).isoformat()
        self._ensure_user_window(user_id=user_id, timezone=timezone)
        with self._lock:
            entry = self._store.get(user_id, {})
            events_by_day = entry.get("events_by_day", {}) if isinstance(entry, dict) else {}
            events = events_by_day.get(target_date, []) if isinstance(events_by_day, dict) else []
            out = [self._public_event_copy(event) for event in events]
            logger.info(
                "event_cache.day_events user_id=%s timezone=%s day_label=%s date=%s count=%s",
                user_id,
                timezone,
                day_label,
                target_date,
                len(out),
            )
            return out

    def resolve_event_id(
        self,
        user_id: str,
        timezone: str,
        event_ref_or_hint: str,
        start_iso_hint: str | None = None,
    ) -> str | None:
        self._ensure_user_window(user_id=user_id, timezone=timezone)
        normalized_ref = _normalize_text(event_ref_or_hint)
        hinted_start = _parse_iso_datetime(start_iso_hint, timezone) if start_iso_hint else None
        logger.info(
            "event_cache.resolve_id.start user_id=%s timezone=%s has_start_hint=%s ref=%r",
            user_id,
            timezone,
            hinted_start is not None,
            event_ref_or_hint,
        )

        with self._lock:
            entry = self._store.get(user_id, {})
            events_by_day = entry.get("events_by_day", {}) if isinstance(entry, dict) else {}
            candidates: list[dict] = []
            for day_events in events_by_day.values():
                if isinstance(day_events, list):
                    candidates.extend(day_events)

        if hinted_start is not None:
            hinted_iso = hinted_start.isoformat()
            for event in candidates:
                if event.get("start_iso") == hinted_iso and normalized_ref in event.get("aliases", set()):
                    logger.info(
                        "event_cache.resolve_id.hit user_id=%s strategy=start+alias resolved_event_id=%s",
                        user_id,
                        event.get("id"),
                    )
                    return event.get("id")

        for event in candidates:
            if normalized_ref in event.get("aliases", set()):
                logger.info(
                    "event_cache.resolve_id.hit user_id=%s strategy=alias resolved_event_id=%s",
                    user_id,
                    event.get("id"),
                )
                return event.get("id")
        logger.info("event_cache.resolve_id.miss user_id=%s ref=%r", user_id, event_ref_or_hint)
        return None

    def get_event_by_reference(
        self,
        user_id: str,
        timezone: str,
        event_ref_or_hint: str,
        start_iso_hint: str | None = None,
    ) -> dict | None:
        if not isinstance(event_ref_or_hint, str) or not event_ref_or_hint.strip():
            logger.info("event_cache.lookup.skip user_id=%s reason=empty_reference", user_id)
            return None

        self._ensure_user_window(user_id=user_id, timezone=timezone)
        normalized_ref = _normalize_text(event_ref_or_hint)
        hinted_start = _parse_iso_datetime(start_iso_hint, timezone) if start_iso_hint else None
        logger.info(
            "event_cache.lookup.start user_id=%s timezone=%s has_start_hint=%s ref=%r",
            user_id,
            timezone,
            hinted_start is not None,
            event_ref_or_hint,
        )

        with self._lock:
            entry = self._store.get(user_id, {})
            events_by_day = entry.get("events_by_day", {}) if isinstance(entry, dict) else {}
            candidates: list[dict] = []
            for day_events in events_by_day.values():
                if isinstance(day_events, list):
                    candidates.extend(day_events)

        def _matches(event: dict) -> bool:
            aliases = event.get("aliases", set())
            return normalized_ref in aliases or normalized_ref == _normalize_text(event.get("id", ""))

        if hinted_start is not None:
            hinted_iso = hinted_start.isoformat()
            for event in candidates:
                if event.get("start_iso") == hinted_iso and _matches(event):
                    logger.info(
                        "event_cache.lookup.hit user_id=%s strategy=start+ref event_id=%s",
                        user_id,
                        event.get("id"),
                    )
                    return self._public_event_copy(event)

        for event in candidates:
            if _matches(event):
                logger.info(
                    "event_cache.lookup.hit user_id=%s strategy=ref event_id=%s",
                    user_id,
                    event.get("id"),
                )
                return self._public_event_copy(event)
        logger.info("event_cache.lookup.miss user_id=%s ref=%r", user_id, event_ref_or_hint)
        return None

    def query_today_tomorrow(
        self,
        user_id: str,
        timezone: str,
        user_message: str,
        event_id_hint: str | None,
    ) -> dict | None:
        lowered = (user_message or "").lower().strip()
        if not lowered:
            logger.info("event_cache.query.skip user_id=%s reason=empty_message", user_id)
            return None

        if _contains_hint(lowered, _OUT_OF_WINDOW_HINTS):
            logger.info("event_cache.query.skip user_id=%s reason=out_of_window_hint message=%r", user_id, user_message)
            return None

        day_label = "tomorrow" if "tomorrow" in lowered else "today"
        if day_label == "today" and "today" not in lowered:
            if "tomorrow" not in lowered and not (
                _contains_hint(lowered, _LOCATION_HINTS) or _contains_hint(lowered, _DURATION_HINTS)
            ):
                logger.info("event_cache.query.skip user_id=%s reason=no_day_or_supported_hint message=%r", user_id, user_message)
                return None

        asked_location = _contains_hint(lowered, _LOCATION_HINTS)
        asked_duration = _contains_hint(lowered, _DURATION_HINTS)
        intent = "location" if asked_location else ("duration" if asked_duration else "day_list")
        logger.info(
            "event_cache.query.start user_id=%s timezone=%s day_label=%s intent=%s has_event_hint=%s",
            user_id,
            timezone,
            day_label,
            intent,
            bool(event_id_hint),
        )

        events = self.get_events_for_day(user_id=user_id, timezone=timezone, day_label=day_label)
        if asked_location:
            matched = self._match_event(events=events, event_id_hint=event_id_hint, title_hint=_extract_title_hint(lowered))
            if matched is None:
                logger.info("event_cache.query.miss user_id=%s day_label=%s intent=location", user_id, day_label)
                return {
                    "status": "not_found",
                    "summary": "I couldn't find that event in your cached schedule.",
                    "day_label": day_label,
                }
            title = matched.get("summary") or matched.get("title") or "that event"
            location = (matched.get("location") or "").strip()
            if location:
                summary = f"Your {title} is at {location}."
            else:
                summary = f"I found {title}, but it doesn't have a location set yet."
            logger.info(
                "event_cache.query.hit user_id=%s day_label=%s intent=location event_title=%r location_set=%s",
                user_id,
                day_label,
                title,
                bool(location),
            )
            return {
                "status": "ok",
                "title": title,
                "location": location,
                "start_iso": matched.get("start_iso"),
                "event": matched,
                "summary": summary,
                "day_label": day_label,
            }

        if asked_duration:
            matched = self._match_event(events=events, event_id_hint=event_id_hint, title_hint=_extract_title_hint(lowered))
            if matched is None:
                logger.info("event_cache.query.miss user_id=%s day_label=%s intent=duration", user_id, day_label)
                return {
                    "status": "not_found",
                    "summary": "I couldn't find that event in your cached schedule.",
                    "day_label": day_label,
                }
            start_dt = _parse_iso_datetime(matched.get("start_iso"), timezone)
            end_dt = _parse_iso_datetime(matched.get("end_iso"), timezone)
            title = matched.get("summary") or matched.get("title") or "that event"
            if start_dt is None or end_dt is None or end_dt <= start_dt:
                return {
                    "status": "error",
                    "error_code": "duration_unavailable",
                    "title": title,
                    "summary": f"I found {title}, but couldn't read its duration from cache.",
                }
            duration_minutes = int((end_dt - start_dt).total_seconds() // 60)
            logger.info(
                "event_cache.query.hit user_id=%s day_label=%s intent=duration event_title=%r duration_minutes=%s",
                user_id,
                day_label,
                title,
                duration_minutes,
            )
            return {
                "status": "ok",
                "title": title,
                "duration_minutes": duration_minutes,
                "start_iso": start_dt.isoformat(),
                "end_iso": end_dt.isoformat(),
                "summary": f"Your {title} is {duration_minutes} minutes long.",
                "day_label": day_label,
            }

        logger.info(
            "event_cache.query.hit user_id=%s day_label=%s intent=day_list events=%s",
            user_id,
            day_label,
            len(events),
        )
        return {
            "status": "ok",
            "events": events,
            "day_label": day_label,
            "summary": "Fetched from event cache.",
        }

    def _ensure_user_window(self, user_id: str, timezone: str) -> None:
        with self._lock:
            entry = self._store.get(user_id)
        freshness_reason = self._entry_freshness_reason(entry=entry, timezone=timezone)
        if freshness_reason == "fresh":
            logger.info("event_cache.ensure.hit user_id=%s timezone=%s", user_id, timezone)
            return
        logger.info(
            "event_cache.ensure.miss user_id=%s timezone=%s reason=%s",
            user_id,
            timezone,
            freshness_reason,
        )
        try:
            result = self.prime_user_window(user_id=user_id, timezone=timezone)
            logger.info(
                "event_cache.ensure.reprimed user_id=%s timezone=%s total=%s",
                user_id,
                timezone,
                result.get("total_count"),
            )
        except Exception:
            logger.exception("event_cache.prime_failed user_id=%s timezone=%s", user_id, timezone)

    def _is_entry_fresh(self, entry: dict | None, timezone: str) -> bool:
        return self._entry_freshness_reason(entry=entry, timezone=timezone) == "fresh"

    def _entry_freshness_reason(self, entry: dict | None, timezone: str) -> str:
        if not isinstance(entry, dict):
            return "missing"
        if entry.get("timezone") != timezone:
            return "timezone_mismatch"
        fetched_at = entry.get("fetched_at")
        if not isinstance(fetched_at, datetime):
            return "missing_fetched_at"
        age_seconds = (datetime.now(ZoneInfo("UTC")) - fetched_at).total_seconds()
        if age_seconds > self._ttl_seconds:
            return "expired"

        now_local = self._now_fn(timezone)
        today_iso = now_local.date().isoformat()
        tomorrow_iso = (now_local.date() + timedelta(days=1)).isoformat()
        events_by_day = entry.get("events_by_day", {})
        if not isinstance(events_by_day, dict):
            return "invalid_events_by_day"
        if today_iso not in events_by_day or tomorrow_iso not in events_by_day:
            return "missing_day_bucket"
        return "fresh"

    def _normalize_event(self, user_id: str, event: dict, timezone: str) -> dict | None:
        start_iso_raw, end_iso_raw = _extract_start_end_iso(event)
        start_dt = _parse_iso_datetime(start_iso_raw, timezone)
        if start_dt is None:
            return None
        end_dt = _parse_iso_datetime(end_iso_raw, timezone)
        if end_dt is None:
            end_dt = start_dt + timedelta(minutes=30)

        title = str(event.get("summary") or event.get("title") or "Untitled event")
        provider_id = str(event.get("id") or "").strip() or None
        canonical_id = self.canonical_event_id(
            user_id=user_id,
            provider_event_id=provider_id,
            title=title,
            start_iso=start_dt.isoformat(),
        )
        normalized_title = _normalize_text(title)

        aliases = {
            canonical_id,
            normalized_title,
            _normalize_text(provider_id or ""),
            _normalize_text(f"{normalized_title} {start_dt.strftime('%H:%M')}") if normalized_title else "",
        }
        aliases = {alias for alias in aliases if alias}

        return {
            "id": provider_id or canonical_id,
            "canonical_id": canonical_id,
            "provider_event_id": provider_id,
            "summary": title,
            "title": title,
            "location": str(event.get("location") or "").strip(),
            "start_iso": start_dt.isoformat(),
            "end_iso": end_dt.isoformat(),
            "start": {"dateTime": start_dt.isoformat()},
            "end": {"dateTime": end_dt.isoformat()},
            "start_local_date": start_dt.date().isoformat(),
            "aliases": aliases,
        }

    def _match_event(self, events: list[dict], event_id_hint: str | None, title_hint: str | None) -> dict | None:
        if not events:
            return None

        if isinstance(event_id_hint, str) and event_id_hint.strip():
            normalized_id = _normalize_text(event_id_hint)
            for event in events:
                aliases = event.get("aliases", set())
                if normalized_id in aliases or normalized_id == _normalize_text(event.get("id", "")):
                    return event

        if isinstance(title_hint, str) and title_hint.strip():
            hint_norm = _normalize_text(title_hint)
            hint_tokens = set(hint_norm.split())
            best: tuple[int, dict] | None = None
            for event in events:
                title_norm = _normalize_text(event.get("summary") or event.get("title") or "")
                title_tokens = set(title_norm.split())
                score = 0
                if hint_norm and hint_norm in title_norm:
                    score += 5
                score += len(hint_tokens & title_tokens)
                if best is None or score > best[0]:
                    best = (score, event)
            if best is not None and best[0] > 0:
                return best[1]

        return events[0]

    def _public_event_copy(self, event: dict) -> dict:
        out = dict(event)
        out.pop("aliases", None)
        out.pop("start_local_date", None)
        return out


event_cache = EventCacheService()
