from app.tools import calendar_proxy


def test_cancel_event_includes_cached_metadata_when_available():
    class FakeClient:
        def call_tool(self, tool_name: str, arguments: dict) -> dict:
            assert tool_name == "mcp_google_calendar_delete_event"
            assert arguments["event_id"] == "evt_1"
            return {"ok": True}

    class FakeCache:
        def get_event_by_reference(self, **_kwargs):
            return {
                "id": "evt_1",
                "summary": "Dinner Date",
                "location": "Pizza Bakery",
                "start_iso": "2026-03-28T20:00:00+05:30",
            }

    calendar_proxy._client = lambda: FakeClient()
    calendar_proxy.event_cache = FakeCache()

    out = calendar_proxy.cancel_event.invoke(
        {
            "user_id": "u1",
            "event_id": "evt_1",
            "timezone": "Asia/Kolkata",
        }
    )

    assert out["status"] == "cancelled"
    assert out["title"] == "Dinner Date"
    assert out["location"] == "Pizza Bakery"
    assert out["start_iso"] == "2026-03-28T20:00:00+05:30"


def test_cancel_event_succeeds_without_cache_metadata():
    class FakeClient:
        def call_tool(self, tool_name: str, arguments: dict) -> dict:
            assert tool_name == "mcp_google_calendar_delete_event"
            return {"ok": True}

    class FakeCache:
        def get_event_by_reference(self, **_kwargs):
            return None

    calendar_proxy._client = lambda: FakeClient()
    calendar_proxy.event_cache = FakeCache()

    out = calendar_proxy.cancel_event.invoke(
        {
            "user_id": "u1",
            "event_id": "evt_2",
            "timezone": "Asia/Kolkata",
        }
    )

    assert out["status"] == "cancelled"
    assert out["event_id"] == "evt_2"
    assert "title" not in out
