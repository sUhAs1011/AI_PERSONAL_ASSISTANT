from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.calendar.event_cache import EventCacheService


def _fixed_now(timezone: str) -> datetime:
    return datetime(2026, 3, 28, 9, 0, tzinfo=ZoneInfo(timezone))


def test_event_cache_prime_buckets_today_and_tomorrow_events():
    captured: dict = {}

    def fake_fetch(user_id: str, start_iso: str, end_iso: str) -> list[dict]:
        captured["user_id"] = user_id
        captured["start_iso"] = start_iso
        captured["end_iso"] = end_iso
        return [
            {
                "id": "evt_today",
                "summary": "Dinner Date",
                "location": "Plan B",
                "start": {"dateTime": "2026-03-28T20:00:00+05:30"},
                "end": {"dateTime": "2026-03-28T21:00:00+05:30"},
            },
            {
                "id": "evt_tomorrow",
                "summary": "Design Review",
                "location": "Office",
                "start": {"dateTime": "2026-03-29T15:00:00+05:30"},
                "end": {"dateTime": "2026-03-29T16:00:00+05:30"},
            },
        ]

    cache = EventCacheService(fetch_events=fake_fetch, now_fn=_fixed_now, ttl_seconds=3600)
    result = cache.prime_user_window(user_id="u1", timezone="Asia/Kolkata")

    assert captured["user_id"] == "u1"
    assert result["today_count"] == 1
    assert result["tomorrow_count"] == 1
    assert result["total_count"] == 2

    today_events = cache.get_events_for_day(user_id="u1", timezone="Asia/Kolkata", day_label="today")
    assert len(today_events) == 1
    assert today_events[0]["id"] == "evt_today"


def test_event_cache_canonical_id_is_deterministic():
    cache = EventCacheService(fetch_events=lambda *_args, **_kwargs: [], now_fn=_fixed_now, ttl_seconds=3600)

    first = cache.canonical_event_id(
        user_id="u1",
        provider_event_id="evt_42",
        title="Dinner Date",
        start_iso="2026-03-28T20:00:00+05:30",
    )
    second = cache.canonical_event_id(
        user_id="u1",
        provider_event_id="evt_42",
        title="Dinner Date",
        start_iso="2026-03-28T20:00:00+05:30",
    )

    assert first == second
    assert first.startswith("evtc_")


def test_event_cache_location_query_uses_cached_event():
    def fake_fetch(_user_id: str, _start_iso: str, _end_iso: str) -> list[dict]:
        return [
            {
                "id": "evt_today",
                "summary": "Dinner Date",
                "location": "Plan B",
                "start": {"dateTime": "2026-03-28T20:00:00+05:30"},
                "end": {"dateTime": "2026-03-28T21:00:00+05:30"},
            }
        ]

    cache = EventCacheService(fetch_events=fake_fetch, now_fn=_fixed_now, ttl_seconds=3600)
    cache.prime_user_window(user_id="u1", timezone="Asia/Kolkata")

    result = cache.query_today_tomorrow(
        user_id="u1",
        timezone="Asia/Kolkata",
        user_message="where is my dinner date today?",
        event_id_hint=None,
    )

    assert result is not None
    assert result["status"] == "ok"
    assert result["title"] == "Dinner Date"
    assert result["location"] == "Plan B"


def test_event_cache_skips_out_of_window_query():
    cache = EventCacheService(fetch_events=lambda *_args, **_kwargs: [], now_fn=_fixed_now, ttl_seconds=3600)

    result = cache.query_today_tomorrow(
        user_id="u1",
        timezone="Asia/Kolkata",
        user_message="where is my dinner date next week?",
        event_id_hint=None,
    )

    assert result is None


def test_event_cache_get_event_by_reference_matches_provider_id():
    def fake_fetch(_user_id: str, _start_iso: str, _end_iso: str) -> list[dict]:
        return [
            {
                "id": "evt_today",
                "summary": "Dinner Date",
                "location": "Pizza Bakery",
                "start": {"dateTime": "2026-03-28T20:00:00+05:30"},
                "end": {"dateTime": "2026-03-28T21:00:00+05:30"},
            }
        ]

    cache = EventCacheService(fetch_events=fake_fetch, now_fn=_fixed_now, ttl_seconds=3600)
    cache.prime_user_window(user_id="u1", timezone="Asia/Kolkata")

    event = cache.get_event_by_reference(
        user_id="u1",
        timezone="Asia/Kolkata",
        event_ref_or_hint="evt_today",
    )

    assert isinstance(event, dict)
    assert event["id"] == "evt_today"
    assert event["summary"] == "Dinner Date"
    assert event["start_iso"] == "2026-03-28T20:00:00+05:30"
