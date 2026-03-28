from app.tools import calendar_proxy


def test_update_event_duration_keeps_start_and_changes_duration():
    captured = {}

    class FakeClient:
        def call_tool(self, tool_name: str, arguments: dict) -> dict:
            captured["tool_name"] = tool_name
            captured["arguments"] = arguments
            return {"id": "evt_42"}

    calendar_proxy._client = lambda: FakeClient()
    out = calendar_proxy.update_event_duration.invoke(
        {
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "event_id": "evt_42",
            "current_start_iso": "2026-03-28T20:00:00+05:30",
            "duration_minutes": 45,
        }
    )

    assert out["status"] == "updated"
    assert out["event_id"] == "evt_42"
    assert out["duration_minutes"] == 45
    assert captured["tool_name"] == "mcp_google_calendar_update_event"
    assert captured["arguments"]["event_id"] == "evt_42"
    assert captured["arguments"]["duration_minutes"] == 45
    assert captured["arguments"]["start_iso"] == "2026-03-28T20:00:00+05:30"


def test_update_event_duration_invalid_start_returns_structured_error(monkeypatch):
    class FakeClient:
        def call_tool(self, tool_name: str, arguments: dict) -> dict:
            raise AssertionError("Should not call MCP client on invalid start")

    calendar_proxy._client = lambda: FakeClient()
    monkeypatch.setattr(
        calendar_proxy,
        "_normalize_start_iso",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad start")),
    )
    out = calendar_proxy.update_event_duration.invoke(
        {
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "event_id": "evt_42",
            "current_start_iso": "not-a-date",
            "duration_minutes": 45,
        }
    )

    assert out["status"] == "error"
    assert out["error_code"] == "invalid_datetime"
    assert out["event_id"] == "evt_42"
