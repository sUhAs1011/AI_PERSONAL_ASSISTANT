from app.tools import calendar_proxy


def test_get_event_location_returns_location_for_matching_event():
    class FakeClient:
        def call_tool(self, tool_name: str, arguments: dict) -> dict:
            assert tool_name == "mcp_google_calendar_find_events"
            return {
                "events": [
                    {
                        "id": "evt_1",
                        "summary": "Dinner Date",
                        "location": "Plan B",
                        "start": {"dateTime": "2026-03-28T20:00:00+05:30"},
                        "end": {"dateTime": "2026-03-28T21:00:00+05:30"},
                    }
                ]
            }

    class FakeCache:
        def query_today_tomorrow(self, **_kwargs):
            return None

    calendar_proxy._client = lambda: FakeClient()
    calendar_proxy.event_cache = FakeCache()

    out = calendar_proxy.get_event_location.invoke(
        {
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "title_hint": "dinner date",
            "date_range": "today",
        }
    )

    assert out["status"] == "ok"
    assert out["title"] == "Dinner Date"
    assert out["location"] == "Plan B"


def test_get_event_location_uses_cache_when_available():
    class FakeCache:
        def query_today_tomorrow(self, **_kwargs):
            return {
                "status": "ok",
                "title": "Dinner Date",
                "location": "Plan B",
                "start_iso": "2026-03-28T20:00:00+05:30",
            }

    class FakeClient:
        def call_tool(self, _tool_name: str, _arguments: dict) -> dict:
            raise AssertionError("Should not call MCP when cache can answer")

    calendar_proxy._client = lambda: FakeClient()
    calendar_proxy.event_cache = FakeCache()

    out = calendar_proxy.get_event_location.invoke(
        {
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "title_hint": "dinner date",
            "date_range": "today",
        }
    )

    assert out["status"] == "ok"
    assert out["location"] == "Plan B"


def test_get_event_location_returns_not_found_when_missing_event():
    class FakeClient:
        def call_tool(self, tool_name: str, arguments: dict) -> dict:
            assert tool_name == "mcp_google_calendar_find_events"
            return {"events": []}

    class FakeCache:
        def query_today_tomorrow(self, **_kwargs):
            return None

    calendar_proxy._client = lambda: FakeClient()
    calendar_proxy.event_cache = FakeCache()

    out = calendar_proxy.get_event_location.invoke(
        {
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "title_hint": "dinner date",
            "date_range": "today",
        }
    )

    assert out["status"] == "not_found"
