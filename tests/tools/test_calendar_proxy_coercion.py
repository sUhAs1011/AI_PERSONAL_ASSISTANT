from app.tools import calendar_proxy


def test_book_event_coerces_natural_time_to_iso():
    captured_calls: list[tuple[str, dict]] = []

    class FakeClient:
        def call_tool(self, tool_name: str, arguments: dict) -> dict:
            captured_calls.append((tool_name, arguments))
            return {"id": "evt_1"}

    calendar_proxy._client = lambda: FakeClient()

    result = calendar_proxy.book_event.invoke(
        {
            "title": "Design Review",
            "start_iso": "tomorrow 3pm",
            "duration_minutes": 30,
            "attendees": ["alex@example.com"],
            "send_invites": True,
            "add_meet_link": True,
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
        }
    )
    assert result["status"] == "created"
    create_event_call = next(
        args for name, args in captured_calls if name == "mcp_google_calendar_create_event"
    )
    assert "T" in create_event_call["start_iso"]
