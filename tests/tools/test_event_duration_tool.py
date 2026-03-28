from app.tools import calendar_proxy


def test_get_event_duration_returns_minutes_for_matching_event():
    class FakeClient:
        def call_tool(self, tool_name: str, arguments: dict) -> dict:
            assert tool_name == "mcp_google_calendar_find_events"
            return {
                "events": [
                    {
                        "summary": "Dinner Date",
                        "start": {"dateTime": "2026-03-28T20:00:00+05:30"},
                        "end": {"dateTime": "2026-03-28T21:30:00+05:30"},
                    }
                ]
            }

    calendar_proxy._client = lambda: FakeClient()
    out = calendar_proxy.get_event_duration.invoke(
        {
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "title_hint": "dinner date",
            "date_range": "today",
        }
    )

    assert out["status"] == "ok"
    assert out["duration_minutes"] == 90
    assert "90 minutes" in out["summary"]


def test_get_event_duration_returns_not_found_for_missing_title():
    class FakeClient:
        def call_tool(self, tool_name: str, arguments: dict) -> dict:
            assert tool_name == "mcp_google_calendar_find_events"
            return {
                "events": [
                    {
                        "summary": "Team Sync",
                        "start": {"dateTime": "2026-03-28T10:00:00+05:30"},
                        "end": {"dateTime": "2026-03-28T10:30:00+05:30"},
                    }
                ]
            }

    calendar_proxy._client = lambda: FakeClient()
    out = calendar_proxy.get_event_duration.invoke(
        {
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "title_hint": "dinner date",
            "date_range": "today",
        }
    )

    assert out["status"] == "not_found"
    assert "couldn't find" in out["summary"].lower()
