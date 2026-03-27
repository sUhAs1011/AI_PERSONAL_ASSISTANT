from fastapi.testclient import TestClient

import app.main as app_main


def test_hitl_respond_rebooks_selected_slot_and_uses_finalizer(monkeypatch):
    calls = []

    class StubBookTool:
        @staticmethod
        def invoke(payload):
            calls.append(payload)
            return {
                "status": "created",
                "event": {"id": "evt_2", "meet_link": None, "invite_status": "not_requested"},
            }

    app_main.book_event = StubBookTool

    def fake_finalizer_node(state):
        assert state["execution_result"]["status"] == "created"
        return {
            "summary": "Unified finalizer summary",
            "final_response": {
                "status": "created",
                "summary": "Unified finalizer summary",
                "response_mode": "calendar_action",
                "latest_event_id": "evt_2",
                "hitl_action_id": state.get("hitl_action_id"),
                "alternatives": [],
                "meet_link": None,
                "invite_status": "not_requested",
            },
        }

    monkeypatch.setattr(app_main, "finalizer_node", fake_finalizer_node)
    client = TestClient(app_main.app)
    action_id = app_main.pending_repo.save(
        "u1", {"title": "Design Review", "attendees": ["alex@example.com"], "duration_minutes": 30}
    )
    resp = client.post(
        "/hitl/respond",
        json={
            "action_id": action_id,
            "decision": "reschedule",
            "selected_start_iso": "2026-03-27T16:00:00+05:30",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert calls[0]["start_iso"] == "2026-03-27T16:00:00+05:30"
    assert body["summary"] == "Unified finalizer summary"
    assert body["latest_event_id"] == "evt_2"


def test_hitl_respond_invalid_action_uses_finalizer(monkeypatch):
    def fake_finalizer_node(state):
        assert state["execution_result"]["status"] == "error"
        return {
            "summary": "I hit an issue while processing that calendar request.",
            "final_response": {
                "status": "error",
                "summary": "I hit an issue while processing that calendar request.",
                "response_mode": "calendar_action",
                "latest_event_id": None,
                "hitl_action_id": state.get("hitl_action_id"),
                "alternatives": [],
                "meet_link": None,
                "invite_status": None,
            },
        }

    monkeypatch.setattr(app_main, "finalizer_node", fake_finalizer_node)
    client = TestClient(app_main.app)
    resp = client.post(
        "/hitl/respond",
        json={
            "action_id": "non-existent-action",
            "decision": "reschedule",
            "selected_start_iso": "2026-03-27T16:00:00+05:30",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "error"
    assert "issue" in body["summary"].lower()
