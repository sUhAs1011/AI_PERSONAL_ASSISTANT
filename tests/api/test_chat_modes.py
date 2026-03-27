from fastapi.testclient import TestClient

import app.main as app_main


def test_chat_returns_response_mode_general_chat():
    class StubGraph:
        def invoke(self, state):
            return {
                "response_mode": "general_chat",
                "summary": "Hey! Good morning. Want me to check your calendar?",
                "execution_result": {"status": "ok"},
            }

    app_main.booking_graph = StubGraph()
    app_main.preferences_repo.get_preferences = lambda _uid: {"no_meetings_before_hour": 10}
    client = TestClient(app_main.app)
    resp = client.post(
        "/chat",
        json={
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "message": "Hey there",
            "conversation_history": [],
        },
    )
    body = resp.json()
    assert resp.status_code == 200
    assert body["response_mode"] == "general_chat"


def test_chat_returns_calendar_query_summary_for_overview():
    class StubGraph:
        def invoke(self, state):
            return {
                "response_mode": "calendar_query",
                "summary": "You have 2 events tomorrow.",
                "execution_result": {"status": "ok", "events": [{"id": "evt_1"}, {"id": "evt_2"}]},
            }

    app_main.booking_graph = StubGraph()
    app_main.preferences_repo.get_preferences = lambda _uid: {"no_meetings_before_hour": 10}
    client = TestClient(app_main.app)
    resp = client.post(
        "/chat",
        json={
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "message": "How does my day look tomorrow?",
            "conversation_history": [],
        },
    )
    body = resp.json()
    assert resp.status_code == 200
    assert body["response_mode"] == "calendar_query"
    assert "2 events" in body["summary"]


def test_chat_never_defaults_to_done_when_summary_missing():
    class StubGraph:
        def invoke(self, state):
            return {
                "response_mode": "calendar_query",
                "execution_result": {"status": "ok", "events": []},
            }

    app_main.booking_graph = StubGraph()
    app_main.preferences_repo.get_preferences = lambda _uid: {"no_meetings_before_hour": 10}
    client = TestClient(app_main.app)
    resp = client.post(
        "/chat",
        json={
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "message": "How does my day look tomorrow?",
            "conversation_history": [],
        },
    )
    body = resp.json()
    assert resp.status_code == 200
    assert body["summary"].strip().lower() != "done."
