from app.tools import calendar_proxy


def test_reschedule_event_updates_with_concrete_event_id():
    captured = {}

    class FakeClient:
        def call_tool(self, tool_name: str, arguments: dict) -> dict:
            captured["tool_name"] = tool_name
            captured["arguments"] = arguments
            return {"id": "evt_42"}

    class FakeCache:
        def get_event_by_reference(self, **_kwargs):
            return None

        def resolve_event_id(self, **_kwargs):
            return None

    calendar_proxy._client = lambda: FakeClient()
    calendar_proxy.event_cache = FakeCache()

    out = calendar_proxy.reschedule_event.invoke(
        {
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "event_id": "evt_42",
            "new_start_iso": "2026-03-30T11:00:00+05:30",
            "duration_minutes": 90,
        }
    )

    assert out["status"] == "updated"
    assert out["event_id"] == "evt_42"
    assert captured["tool_name"] == "mcp_google_calendar_update_event"
    assert captured["arguments"]["event_id"] == "evt_42"
    assert captured["arguments"]["start_iso"] == "2026-03-30T11:00:00+05:30"
    assert captured["arguments"]["duration_minutes"] == 90


def test_reschedule_event_retries_with_resolved_event_id_on_hint_failure():
    class FakeClient:
        def __init__(self):
            self.calls = []

        def call_tool(self, tool_name: str, arguments: dict) -> dict:
            self.calls.append((tool_name, arguments))
            if tool_name == "mcp_google_calendar_update_event":
                if arguments["event_id"] == "movie_plan":
                    raise RuntimeError("500 Server Error")
                return {"id": arguments["event_id"]}
            if tool_name == "mcp_google_calendar_find_events":
                return {
                    "events": [
                        {
                            "id": "evt_movie_1",
                            "summary": "Movie Plan",
                            "start": {"dateTime": "2026-03-29T11:00:00+05:30"},
                            "end": {"dateTime": "2026-03-29T13:00:00+05:30"},
                        }
                    ]
                }
            raise AssertionError(f"unexpected tool call: {tool_name}")

    class FakeCache:
        def get_event_by_reference(self, **_kwargs):
            return None

        def resolve_event_id(self, **_kwargs):
            return None

    fake = FakeClient()
    calendar_proxy._client = lambda: fake
    calendar_proxy.event_cache = FakeCache()

    out = calendar_proxy.reschedule_event.invoke(
        {
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "event_id": "movie_plan",
            "new_start_iso": "2026-03-30T11:00:00+05:30",
            "duration_minutes": 120,
        }
    )

    assert out["status"] == "updated"
    assert out["event_id"] == "evt_movie_1"
    assert out["start_iso"] == "2026-03-30T11:00:00+05:30"
    update_calls = [args for name, args in fake.calls if name == "mcp_google_calendar_update_event"]
    assert update_calls[0]["event_id"] == "movie_plan"
    assert update_calls[1]["event_id"] == "evt_movie_1"


def test_reschedule_event_returns_event_not_found_when_hint_resolution_fails():
    class FakeClient:
        def call_tool(self, tool_name: str, arguments: dict) -> dict:
            if tool_name == "mcp_google_calendar_update_event":
                raise RuntimeError("500 Server Error")
            if tool_name == "mcp_google_calendar_find_events":
                return {"events": []}
            raise AssertionError(f"unexpected tool call: {tool_name}")

    class FakeCache:
        def get_event_by_reference(self, **_kwargs):
            return None

        def resolve_event_id(self, **_kwargs):
            return None

    calendar_proxy._client = lambda: FakeClient()
    calendar_proxy.event_cache = FakeCache()

    out = calendar_proxy.reschedule_event.invoke(
        {
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "event_id": "movie_plan",
            "new_start_iso": "2026-03-30T11:00:00+05:30",
            "duration_minutes": 120,
        }
    )

    assert out["status"] == "error"
    assert out["error_code"] == "event_not_found"
    assert out["event_id"] == "movie_plan"
    assert out["start_iso"] == "2026-03-30T11:00:00+05:30"
