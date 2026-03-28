from fastapi.testclient import TestClient

import app.main as app_main


def test_calendar_cache_prime_endpoint_returns_counts(monkeypatch):
    captured: dict = {}

    class FakeCache:
        def prime_user_window(self, user_id: str, timezone: str) -> dict:
            captured["user_id"] = user_id
            captured["timezone"] = timezone
            return {
                "status": "ok",
                "today_count": 1,
                "tomorrow_count": 2,
                "total_count": 3,
            }

    monkeypatch.setattr(app_main, "event_cache", FakeCache())
    client = TestClient(app_main.app)

    resp = client.post(
        "/calendar/cache/prime",
        json={"user_id": "u1", "timezone": "Asia/Kolkata"},
    )

    body = resp.json()
    assert resp.status_code == 200
    assert captured["user_id"] == "u1"
    assert captured["timezone"] == "Asia/Kolkata"
    assert body["status"] == "ok"
    assert body["today_count"] == 1
    assert body["tomorrow_count"] == 2


def test_chat_refreshes_calendar_cache_after_action(monkeypatch):
    refreshed: list[tuple[str, str]] = []

    class StubGraph:
        def invoke(self, _state):
            return {
                "response_mode": "calendar_action",
                "summary": "Booked Design Review at 3 PM.",
                "execution_result": {
                    "status": "created",
                    "start_iso": "2026-03-28T15:00:00+05:30",
                    "event": {"id": "evt_1"},
                },
            }

    class FakeCache:
        def prime_user_window(self, user_id: str, timezone: str) -> dict:
            refreshed.append((user_id, timezone))
            return {"status": "ok", "today_count": 1, "tomorrow_count": 0, "total_count": 1}

    app_main.booking_graph = StubGraph()
    app_main.preferences_repo.get_preferences = lambda _uid: {"no_meetings_before_hour": 10}
    monkeypatch.setattr(app_main, "event_cache", FakeCache())

    client = TestClient(app_main.app)
    resp = client.post(
        "/chat",
        json={
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "message": "book design review tomorrow at 3 pm",
            "conversation_history": [],
        },
    )

    assert resp.status_code == 200
    assert refreshed == [("u1", "Asia/Kolkata")]
