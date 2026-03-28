from fastapi.testclient import TestClient

import app.main as app_main


def test_chat_appends_history_and_returns_response(monkeypatch):
    class StubGraph:
        def invoke(self, state):
            return {
                "summary": "Design Review booked at 3:00 PM.",
                "execution_result": {
                    "status": "created",
                    "start_iso": "2026-03-28T15:00:00+05:30",
                    "event": {"id": "evt_1", "meet_link": "https://meet.google.com/abc"},
                },
            }

    app_main.booking_graph = StubGraph()
    app_main.preferences_repo.get_preferences = lambda _uid: {"no_meetings_before_hour": 10}
    client = TestClient(app_main.app)
    resp = client.post(
        "/chat",
        json={
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "message": "Book design review tomorrow at 3",
            "conversation_history": [],
        },
    )
    body = resp.json()
    assert resp.status_code == 200
    assert len(body["conversation_history"]) == 2
    assert body["latest_event_id"] == "evt_1"
    assert "event_id=evt_1" in body["conversation_history"][-1]["content"]
    assert "start_iso=2026-03-28T15:00:00+05:30" in body["conversation_history"][-1]["content"]
