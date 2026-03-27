from fastapi.testclient import TestClient

import app.main as app_main


def test_hitl_respond_rebooks_selected_slot(monkeypatch):
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
    assert calls[0]["start_iso"] == "2026-03-27T16:00:00+05:30"

