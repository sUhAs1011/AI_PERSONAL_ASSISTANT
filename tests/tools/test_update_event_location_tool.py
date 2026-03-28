from app.tools import calendar_proxy


def test_update_event_location_updates_existing_event():
    captured = {}

    class FakeClient:
        def call_tool(self, tool_name: str, arguments: dict) -> dict:
            captured["tool_name"] = tool_name
            captured["arguments"] = arguments
            return {"id": "evt_42"}

    calendar_proxy._client = lambda: FakeClient()
    out = calendar_proxy.update_event_location.invoke(
        {
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "event_id": "evt_42",
            "current_start_iso": "2026-03-28T20:00:00+05:30",
            "location": "Pizza Bakery indiranagar",
        }
    )

    assert out["status"] == "updated"
    assert out["event_id"] == "evt_42"
    assert out["location"] == "Pizza Bakery indiranagar"
    assert captured["tool_name"] == "mcp_google_calendar_update_event"
    assert captured["arguments"]["event_id"] == "evt_42"
    assert captured["arguments"]["location"] == "Pizza Bakery indiranagar"


def test_update_event_location_retries_with_resolved_event_id():
    class FakeClient:
        def __init__(self):
            self.calls = []

        def call_tool(self, tool_name: str, arguments: dict) -> dict:
            self.calls.append((tool_name, arguments))
            if tool_name == "mcp_google_calendar_update_event":
                if arguments["event_id"] == "dinner_date":
                    raise RuntimeError("event not found")
                return {"id": arguments["event_id"]}
            if tool_name == "mcp_google_calendar_find_events":
                return {
                    "events": [
                        {
                            "id": "evt_real_1",
                            "summary": "Dinner Date",
                            "start": {"dateTime": "2026-03-28T20:00:00+05:30"},
                            "end": {"dateTime": "2026-03-28T21:00:00+05:30"},
                        }
                    ]
                }
            raise AssertionError(f"unexpected tool call: {tool_name}")

    fake = FakeClient()
    calendar_proxy._client = lambda: fake
    out = calendar_proxy.update_event_location.invoke(
        {
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "event_id": "dinner_date",
            "current_start_iso": "2026-03-28T20:00:00+05:30",
            "location": "Pizza Bakery indiranagar",
        }
    )

    assert out["status"] == "updated"
    assert out["event_id"] == "evt_real_1"
    update_calls = [args for name, args in fake.calls if name == "mcp_google_calendar_update_event"]
    assert update_calls[0]["event_id"] == "dinner_date"
    assert update_calls[1]["event_id"] == "evt_real_1"


def test_update_event_location_returns_invalid_location_error():
    class FakeClient:
        def call_tool(self, tool_name: str, arguments: dict) -> dict:
            raise AssertionError("Should not call MCP client on invalid location")

    calendar_proxy._client = lambda: FakeClient()
    out = calendar_proxy.update_event_location.invoke(
        {
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "event_id": "evt_42",
            "current_start_iso": "2026-03-28T20:00:00+05:30",
            "location": "   ",
        }
    )

    assert out["status"] == "error"
    assert out["error_code"] == "invalid_location"
