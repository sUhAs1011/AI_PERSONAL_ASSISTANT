from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

import app.main as app_main


def test_day_overview_query_returns_specific_schedule_summary():
    class StubGraph:
        def invoke(self, state):
            return {
                "response_mode": "calendar_query",
                "summary": "You have 2 events tomorrow, starting with Design Review at 15:00.",
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
    assert "2 events" in body["summary"]
    assert body["summary"].strip().lower() != "done."


def test_general_chat_input_returns_conversational_response():
    class StubGraph:
        def invoke(self, state):
            return {
                "response_mode": "general_chat",
                "summary": "Good morning! I can review your day or book a meeting when you're ready.",
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
            "message": "Hey, good morning",
            "conversation_history": [],
        },
    )
    body = resp.json()
    assert resp.status_code == 200
    assert body["response_mode"] == "general_chat"
    assert "Good morning" in body["summary"]


def test_follow_up_modification_uses_history_context():
    class StubGraph:
        def __init__(self):
            self.states = []

        def invoke(self, state):
            self.states.append(state)
            if len(self.states) == 1:
                return {
                    "response_mode": "calendar_action",
                    "summary": "Booked Design Review at 3 PM.",
                    "execution_result": {"status": "created", "event": {"id": "evt_1"}},
                }
            return {
                "response_mode": "calendar_action",
                "summary": "Updated Design Review to 45 minutes.",
                "execution_result": {"status": "updated", "event": {"id": "evt_1"}},
            }

    stub = StubGraph()
    app_main.booking_graph = stub
    app_main.preferences_repo.get_preferences = lambda _uid: {"no_meetings_before_hour": 10}
    client = TestClient(app_main.app)

    first = client.post(
        "/chat",
        json={
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "message": "Book a sync with alex tomorrow at 3 PM",
            "conversation_history": [],
        },
    )
    first_body = first.json()
    second = client.post(
        "/chat",
        json={
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "message": "Actually make it 45 minutes",
            "conversation_history": first_body["conversation_history"],
        },
    )
    assert second.status_code == 200
    second_state = stub.states[1]
    assert any(
        isinstance(msg, AIMessage) and "event_id=evt_1" in msg.content
        for msg in second_state.get("messages", [])
    )
