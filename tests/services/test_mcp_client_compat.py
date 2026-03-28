import requests

from app.services.calendar.mcp_client import MCPClient


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")

    def json(self) -> dict:
        return self._payload


def test_fallback_find_events_when_tools_call_returns_404(monkeypatch):
    calls: dict = {}

    def fake_post(url, json=None, timeout=30):
        calls["tools_call_url"] = url
        return _FakeResponse(status_code=404, text="not found")

    def fake_get(url, params=None, timeout=30):
        calls["events_url"] = url
        calls["events_params"] = params
        return _FakeResponse(status_code=200, payload={"items": [{"id": "evt_1"}]})

    monkeypatch.setattr("app.services.calendar.mcp_client.requests.post", fake_post)
    monkeypatch.setattr("app.services.calendar.mcp_client.requests.get", fake_get)

    client = MCPClient(base_url="http://127.0.0.1:8000")
    result = client.call_tool(
        "mcp_google_calendar_find_events",
        {
            "user_id": "u1",
            "start_iso": "2026-03-28T09:00:00+05:30",
            "end_iso": "2026-03-28T12:00:00+05:30",
        },
    )

    assert calls["tools_call_url"].endswith("/tools/call")
    assert calls["events_url"].endswith("/calendars/primary/events")
    assert calls["events_params"]["time_min"] == "2026-03-28T09:00:00+05:30"
    assert calls["events_params"]["time_max"] == "2026-03-28T12:00:00+05:30"
    assert result["events"][0]["id"] == "evt_1"


def test_fallback_query_free_busy_normalizes_free_windows(monkeypatch):
    def fake_post(url, json=None, timeout=30):
        if url.endswith("/tools/call"):
            return _FakeResponse(status_code=404, text="not found")
        if url.endswith("/freeBusy"):
            return _FakeResponse(
                status_code=200,
                payload={
                    "calendars": {
                        "primary": {
                            "busy": [
                                {
                                    "start": "2026-03-28T10:00:00+05:30",
                                    "end": "2026-03-28T11:00:00+05:30",
                                }
                            ]
                        }
                    }
                },
            )
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr("app.services.calendar.mcp_client.requests.post", fake_post)

    client = MCPClient(base_url="http://127.0.0.1:8000")
    result = client.call_tool(
        "mcp_google_calendar_query_free_busy",
        {
            "user_id": "u1",
            "start_iso": "2026-03-28T09:00:00+05:30",
            "end_iso": "2026-03-28T12:00:00+05:30",
            "attendees": [],
        },
    )

    assert len(result["free_windows"]) == 2
    assert result["free_windows"][0]["start_iso"] == "2026-03-28T09:00:00+05:30"
    assert result["free_windows"][0]["end_iso"] == "2026-03-28T10:00:00+05:30"
    assert result["free_windows"][1]["start_iso"] == "2026-03-28T11:00:00+05:30"
    assert result["free_windows"][1]["end_iso"] == "2026-03-28T12:00:00+05:30"


def test_fallback_create_event_includes_location_when_present(monkeypatch):
    calls: dict = {}

    def fake_post(url, json=None, params=None, timeout=30):
        if url.endswith("/tools/call"):
            return _FakeResponse(status_code=404, text="not found")
        calls["url"] = url
        calls["json"] = json
        calls["params"] = params
        return _FakeResponse(status_code=201, payload={"id": "evt_1"})

    monkeypatch.setattr("app.services.calendar.mcp_client.requests.post", fake_post)

    client = MCPClient(base_url="http://127.0.0.1:8000")
    out = client.call_tool(
        "mcp_google_calendar_create_event",
        {
            "user_id": "u1",
            "title": "Dinner Date",
            "start_iso": "2026-03-28T20:00:00+05:30",
            "duration_minutes": 60,
            "attendees": ["alex@example.com"],
            "location": "PlanB: Indiranagar",
            "send_invites": True,
        },
    )

    assert out["id"] == "evt_1"
    assert calls["url"].endswith("/calendars/primary/events")
    assert calls["json"]["location"] == "PlanB: Indiranagar"
    assert calls["json"]["attendees"] == ["alex@example.com"]


def test_fallback_update_event_supports_location_only_patch(monkeypatch):
    calls: dict = {}

    def fake_post(url, json=None, timeout=30):
        if url.endswith("/tools/call"):
            return _FakeResponse(status_code=404, text="not found")
        raise AssertionError(f"Unexpected POST URL: {url}")

    def fake_patch(url, json=None, timeout=30):
        calls["url"] = url
        calls["json"] = json
        return _FakeResponse(status_code=200, payload={"id": "evt_42", "location": "Pizza Bakery indiranagar"})

    monkeypatch.setattr("app.services.calendar.mcp_client.requests.post", fake_post)
    monkeypatch.setattr("app.services.calendar.mcp_client.requests.patch", fake_patch)

    client = MCPClient(base_url="http://127.0.0.1:8000")
    out = client.call_tool(
        "mcp_google_calendar_update_event",
        {
            "user_id": "u1",
            "event_id": "evt_42",
            "location": "Pizza Bakery indiranagar",
        },
    )

    assert out["id"] == "evt_42"
    assert calls["url"].endswith("/calendars/primary/events/evt_42")
    assert calls["json"] == {"location": "Pizza Bakery indiranagar"}
