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


def test_book_event_invalid_datetime_returns_structured_error(monkeypatch):
    captured_calls: list[tuple[str, dict]] = []

    class FakeClient:
        def call_tool(self, tool_name: str, arguments: dict) -> dict:
            captured_calls.append((tool_name, arguments))
            return {"id": "evt_1"}

    calendar_proxy._client = lambda: FakeClient()
    monkeypatch.setattr(
        calendar_proxy,
        "parse_natural_time",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad time")),
    )

    result = calendar_proxy.book_event.invoke(
        {
            "title": "Design Review",
            "start_iso": "not-a-time",
            "duration_minutes": 30,
            "attendees": ["alex@example.com"],
            "send_invites": True,
            "add_meet_link": True,
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
        }
    )

    assert result["status"] == "error"
    assert result["error_code"] == "invalid_datetime"
    assert not captured_calls


def test_book_event_invalid_attendee_returns_structured_error():
    captured_calls: list[tuple[str, dict]] = []

    class FakeClient:
        def call_tool(self, tool_name: str, arguments: dict) -> dict:
            captured_calls.append((tool_name, arguments))
            return {"id": "evt_1"}

    calendar_proxy._client = lambda: FakeClient()

    result = calendar_proxy.book_event.invoke(
        {
            "title": "Design Review",
            "start_iso": "2026-03-30T15:00:00+05:30",
            "duration_minutes": 30,
            "attendees": ["alex@@example.com"],
            "send_invites": True,
            "add_meet_link": True,
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
        }
    )

    assert result["status"] == "error"
    assert result["error_code"] == "invalid_attendees"
    assert result["invalid_attendees"] == ["alex@@example.com"]
    assert not captured_calls


def test_book_event_does_not_call_add_attendee_sidecar():
    captured_calls: list[tuple[str, dict]] = []

    class FakeClient:
        def call_tool(self, tool_name: str, arguments: dict) -> dict:
            captured_calls.append((tool_name, arguments))
            return {"id": "evt_1"}

    calendar_proxy._client = lambda: FakeClient()

    result = calendar_proxy.book_event.invoke(
        {
            "title": "Design Review",
            "start_iso": "2026-03-30T15:00:00+05:30",
            "duration_minutes": 30,
            "attendees": ["alex@example.com"],
            "send_invites": True,
            "add_meet_link": True,
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
        }
    )

    assert result["status"] == "created"
    names = [name for name, _args in captured_calls]
    assert names.count("mcp_google_calendar_create_event") == 1
    assert "mcp_google_calendar_add_attendee" not in names


def test_book_event_non_email_attendee_tokens_do_not_fail_and_infer_location():
    captured_calls: list[tuple[str, dict]] = []

    class FakeClient:
        def call_tool(self, tool_name: str, arguments: dict) -> dict:
            captured_calls.append((tool_name, arguments))
            return {"id": "evt_1"}

    calendar_proxy._client = lambda: FakeClient()

    result = calendar_proxy.book_event.invoke(
        {
            "title": "Dinner Date",
            "start_iso": "2026-03-30T20:00:00+05:30",
            "duration_minutes": 60,
            "attendees": ["PlanB", "Indiranagar"],
            "send_invites": True,
            "add_meet_link": False,
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
        }
    )

    assert result["status"] == "created"
    create_event_call = next(
        args for name, args in captured_calls if name == "mcp_google_calendar_create_event"
    )
    assert create_event_call["attendees"] == []
    assert create_event_call["location"] == "PlanB, Indiranagar"


def test_book_event_explicit_location_is_sent_to_create_event():
    captured_calls: list[tuple[str, dict]] = []

    class FakeClient:
        def call_tool(self, tool_name: str, arguments: dict) -> dict:
            captured_calls.append((tool_name, arguments))
            return {"id": "evt_1"}

    calendar_proxy._client = lambda: FakeClient()

    result = calendar_proxy.book_event.invoke(
        {
            "title": "Dinner Date",
            "start_iso": "2026-03-30T20:00:00+05:30",
            "duration_minutes": 60,
            "attendees": ["alex@example.com"],
            "send_invites": True,
            "add_meet_link": False,
            "location": "PlanB: Indiranagar",
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
        }
    )

    assert result["status"] == "created"
    create_event_call = next(
        args for name, args in captured_calls if name == "mcp_google_calendar_create_event"
    )
    assert create_event_call["location"] == "PlanB: Indiranagar"


def test_book_event_returns_conflict_when_time_overlaps_existing_event():
    captured_calls: list[tuple[str, dict]] = []

    class FakeClient:
        def call_tool(self, tool_name: str, arguments: dict) -> dict:
            captured_calls.append((tool_name, arguments))
            if tool_name == "mcp_google_calendar_find_events":
                return {
                    "events": [
                        {
                            "id": "evt_busy",
                            "summary": "Meditation Session",
                            "start": {"dateTime": "2026-03-28T15:00:00+05:30"},
                            "end": {"dateTime": "2026-03-28T15:30:00+05:30"},
                        }
                    ]
                }
            if tool_name == "mcp_google_calendar_query_free_busy":
                return {
                    "free_windows": [
                        {
                            "start_iso": "2026-03-28T16:00:00+05:30",
                            "end_iso": "2026-03-28T18:00:00+05:30",
                        }
                    ]
                }
            if tool_name == "mcp_google_calendar_create_event":
                raise AssertionError("create_event must not be called when conflict is detected")
            raise AssertionError(f"Unexpected tool: {tool_name}")

    calendar_proxy._client = lambda: FakeClient()

    result = calendar_proxy.book_event.invoke(
        {
            "title": "Casual Call",
            "start_iso": "2026-03-28T15:00:00+05:30",
            "duration_minutes": 30,
            "attendees": [],
            "send_invites": False,
            "add_meet_link": False,
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
        }
    )

    assert result["status"] == "conflict"
    assert result["error_code"] == "time_conflict"
    assert result["conflicting_event"]["id"] == "evt_busy"
    assert result["alternatives"]
    assert result["alternatives"][0]["start_iso"] == "2026-03-28T16:00:00+05:30"
    called_tools = [name for name, _ in captured_calls]
    assert "mcp_google_calendar_find_events" in called_tools
    assert "mcp_google_calendar_query_free_busy" in called_tools
    assert "mcp_google_calendar_create_event" not in called_tools
