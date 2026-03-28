import re

from fastapi.testclient import TestClient

import app.main as app_main


def test_chat_conflict_hides_hitl_fields_and_keeps_marker_in_history():
    class StubGraph:
        def invoke(self, _state):
            return {
                "response_mode": "calendar_action",
                "summary": "You already have another event scheduled today at 6:00 PM IST.",
                "execution_result": {"status": "needs_hitl"},
                "hitl_action_id": "act_conflict_1",
                "alternatives": [
                    {"start_iso": "2026-04-02T19:00:00+05:30"},
                    {"start_iso": "2026-04-02T20:00:00+05:30"},
                ],
            }

    app_main.booking_graph = StubGraph()
    app_main.preferences_repo.get_preferences = lambda _uid: {"no_meetings_before_hour": 10}
    client = TestClient(app_main.app)

    resp = client.post(
        "/chat",
        json={
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "message": "book design review tomorrow at 6 pm",
            "conversation_history": [],
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "needs_hitl"
    assert body["hitl_action_id"] is None
    assert body["alternatives"] == []
    assert "another event scheduled" in body["summary"].lower()
    assert "[hitl_action_id=act_conflict_1]" in body["conversation_history"][-1]["content"]


def test_chat_followup_time_uses_pending_hitl_context_without_graph(monkeypatch):
    class StubGraph:
        def invoke(self, _state):
            raise AssertionError("graph should be bypassed for hitl time follow-up")

    class StubBookTool:
        calls = []

        @staticmethod
        def invoke(payload):
            StubBookTool.calls.append(payload)
            return {
                "status": "created",
                "event": {"id": "evt_2", "meet_link": None, "invite_status": "not_requested"},
                "start_iso": payload["start_iso"],
            }

    app_main.booking_graph = StubGraph()
    app_main.book_event = StubBookTool
    app_main.preferences_repo.get_preferences = lambda _uid: {"no_meetings_before_hour": 10}

    def fake_finalizer_node(state):
        assert state["execution_result"]["status"] == "created"
        return {
            "summary": "Done, moved it to 8:30 PM IST.",
            "final_response": {
                "status": "created",
                "summary": "Done, moved it to 8:30 PM IST.",
                "response_mode": "calendar_action",
                "latest_event_id": "evt_2",
                "latest_start_iso": state["execution_result"].get("start_iso"),
                "hitl_action_id": None,
                "alternatives": [],
                "meet_link": None,
                "invite_status": "not_requested",
            },
        }

    monkeypatch.setattr(app_main, "finalizer_node", fake_finalizer_node)

    action_id = app_main.pending_repo.save(
        "u1",
        {
            "title": "Design Review",
            "duration_minutes": 30,
            "attendees": [],
            "send_invites": False,
            "add_meet_link": False,
            "start_iso": "2026-04-02T18:00:00+05:30",
        },
        alternatives=[{"start_iso": "2026-04-02T19:00:00+05:30"}],
        timezone="Asia/Kolkata",
    )

    client = TestClient(app_main.app)
    resp = client.post(
        "/chat",
        json={
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "message": "8:30 pm works",
            "conversation_history": [
                {
                    "role": "assistant",
                    "content": f"That conflicts. [hitl_action_id={action_id}]",
                }
            ],
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "created"
    assert StubBookTool.calls[0]["start_iso"] == "2026-04-02T20:30:00+05:30"


def test_chat_followup_reconflict_returns_conversational_options(monkeypatch):
    class StubGraph:
        def invoke(self, _state):
            raise AssertionError("graph should be bypassed for hitl time follow-up")

    class StubBookTool:
        @staticmethod
        def invoke(payload):
            return {
                "status": "conflict",
                "error_code": "time_conflict",
                "title": "Design Review",
                "start_iso": payload["start_iso"],
                "duration_minutes": 30,
                "conflicting_event": {
                    "id": "evt_busy_1",
                    "title": "Doctor Appointment",
                    "start_iso": "2026-04-02T21:00:00+05:30",
                    "end_iso": "2026-04-02T21:30:00+05:30",
                },
                "alternatives": [
                    {"start_iso": "2026-04-02T21:30:00+05:30"},
                    {"start_iso": "2026-04-02T22:00:00+05:30"},
                    {"start_iso": "2026-04-02T22:30:00+05:30"},
                ],
            }

    app_main.booking_graph = StubGraph()
    app_main.book_event = StubBookTool
    app_main.preferences_repo.get_preferences = lambda _uid: {"no_meetings_before_hour": 10}
    monkeypatch.setattr(
        app_main,
        "finalizer_node",
        lambda _state: (_ for _ in ()).throw(AssertionError("finalizer should not be called for reconflict")),
    )

    action_id = app_main.pending_repo.save(
        "u1",
        {
            "title": "Design Review",
            "duration_minutes": 30,
            "attendees": [],
            "send_invites": False,
            "add_meet_link": False,
            "start_iso": "2026-04-02T18:00:00+05:30",
        },
        alternatives=[{"start_iso": "2026-04-02T19:00:00+05:30"}],
        timezone="Asia/Kolkata",
    )

    client = TestClient(app_main.app)
    resp = client.post(
        "/chat",
        json={
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "message": "try 9 PM instead",
            "conversation_history": [
                {
                    "role": "assistant",
                    "content": f"That conflicts. [hitl_action_id={action_id}]",
                }
            ],
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "needs_hitl"
    assert body["hitl_action_id"] is None
    assert body["alternatives"] == []
    assert "IST" in body["summary"]
    assert "1)" in body["summary"]
    assert re.search(r"\[hitl_action_id=[^\]]+\]", body["conversation_history"][-1]["content"])
