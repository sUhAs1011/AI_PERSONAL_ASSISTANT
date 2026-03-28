from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from langchain_core.messages import HumanMessage

from app.graph.nodes.finalizer_node import finalizer_node


def test_finalizer_calendar_query_includes_event_count_and_time(monkeypatch):
    class MockMsg:
        def __init__(self, content: str):
            self.content = content

    class MockLLM:
        def invoke(self, _messages):
            return MockMsg("")

    monkeypatch.setattr("app.graph.nodes.finalizer_node.build_llm", lambda **_: MockLLM())
    out = finalizer_node(
        {
            "response_mode": "calendar_query",
            "execution_result": {
                "status": "ok",
                "events": [
                    {
                        "summary": "Design Review",
                        "start": {"dateTime": "2026-03-28T15:00:00+05:30"},
                    }
                ],
            },
        }
    )
    assert "1 event" in out["summary"]
    assert "Design Review" in out["summary"]
    assert "3:00 PM" in out["summary"]
    assert "T15:00:00" not in out["summary"]
    assert "+05:30" not in out["summary"]


def test_finalizer_calendar_query_tomorrow_reply_is_natural(monkeypatch):
    class MockMsg:
        def __init__(self, content: str):
            self.content = content

    class MockLLM:
        def invoke(self, _messages):
            return MockMsg("Done.")

    monkeypatch.setattr("app.graph.nodes.finalizer_node.build_llm", lambda **_: MockLLM())
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    tomorrow_3pm = (now + timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0)

    out = finalizer_node(
        {
            "timezone": "Asia/Kolkata",
            "response_mode": "calendar_query",
            "messages": [HumanMessage(content="what does my day look like tomorrow?")],
            "execution_result": {
                "status": "ok",
                "events": [
                    {
                        "summary": "Meditation",
                        "start": {"dateTime": tomorrow_3pm.isoformat()},
                    }
                ],
            },
        }
    )
    assert "tomorrow" in out["summary"].lower()
    assert "3:00 PM" in out["summary"]
    assert "T15:00:00" not in out["summary"]
    assert "+05:30" not in out["summary"]


def test_finalizer_general_chat_reads_like_assistant_reply():
    out = finalizer_node(
        {
            "response_mode": "general_chat",
            "summary": "Good morning! You have a calm day ahead.",
            "execution_result": {"status": "ok"},
        }
    )
    assert "Good morning" in out["summary"]


def test_finalizer_never_returns_done_literal(monkeypatch):
    class MockMsg:
        def __init__(self, content: str):
            self.content = content

    class MockLLM:
        def invoke(self, _messages):
            return MockMsg("Done.")

    monkeypatch.setattr("app.graph.nodes.finalizer_node.build_llm", lambda **_: MockLLM())
    out = finalizer_node({"response_mode": "calendar_query", "execution_result": {"status": "ok"}})
    assert out["summary"].strip().lower() != "done."


def test_finalizer_error_summary_is_grounded_and_not_successful(monkeypatch):
    class MockMsg:
        def __init__(self, content: str):
            self.content = content

    class MockLLM:
        def invoke(self, _messages):
            return MockMsg("✅ Booked successfully at 10:00 AM.")

    monkeypatch.setattr("app.graph.nodes.finalizer_node.build_llm", lambda **_: MockLLM())
    out = finalizer_node(
        {
            "timezone": "Asia/Kolkata",
            "response_mode": "calendar_action",
            "execution_result": {
                "status": "error",
                "error_code": "invalid_datetime",
                "title": "Design Review",
                "start_iso": "not-a-time",
                "error": "Could not parse",
            },
        }
    )
    summary = out["summary"].lower()
    assert "sorry" in summary
    assert "couldn't" in summary
    assert "booked successfully" not in summary
