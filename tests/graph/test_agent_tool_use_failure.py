import httpx
from groq import BadRequestError
from langchain_core.messages import AIMessage, HumanMessage

import app.graph.nodes.agent_node as agent_mod
from app.llm.router import ConversationMode, ModeRoute


def _tool_use_failed_error() -> BadRequestError:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(status_code=400, request=request)
    body = {
        "error": {
            "message": "Failed to call a function",
            "type": "invalid_request_error",
            "code": "tool_use_failed",
        }
    }
    return BadRequestError("tool failed", response=response, body=body)


def test_agent_node_handles_tool_use_failed_with_safe_fallback(monkeypatch):
    class FakeLLM:
        def __init__(self):
            self.calls = 0

        def invoke(self, _messages):
            self.calls += 1
            raise _tool_use_failed_error()

    fake = FakeLLM()
    monkeypatch.setattr(agent_mod, "build_llm", lambda bound_tools=None: fake)
    monkeypatch.setattr(
        agent_mod,
        "route_mode",
        lambda user_message, conversation_history, timezone: ModeRoute(
            mode=ConversationMode.CALENDAR_QUERY,
            confidence="high",
            reason="test",
        ),
    )

    state = {
        "timezone": "Asia/Kolkata",
        "preferences": {"no_meetings_before_hour": 10},
        "messages": [HumanMessage(content="Show tomorrow events")],
        "iteration_count": 0,
    }

    result = agent_mod.agent_node(state)

    assert fake.calls == 2
    assert result["iteration_count"] == 1
    assert "pending_clarification" in result
    assert result["execution_result"]["status"] == "error"
    assert result["response_mode"] == "calendar_query"
    assert "event name and day" in result["summary"]


def test_agent_node_uses_query_tool_subset(monkeypatch):
    captured: dict = {}

    class FakeLLM:
        def invoke(self, _messages):
            return AIMessage(content="ok", tool_calls=[])

    def fake_build_llm(bound_tools=None):
        captured["tool_names"] = [tool.name for tool in (bound_tools or [])]
        return FakeLLM()

    monkeypatch.setattr(agent_mod, "build_llm", fake_build_llm)
    monkeypatch.setattr(
        agent_mod,
        "route_mode",
        lambda user_message, conversation_history, timezone: ModeRoute(
            mode=ConversationMode.CALENDAR_QUERY,
            confidence="high",
            reason="test",
        ),
    )

    result = agent_mod.agent_node(
        {
            "timezone": "Asia/Kolkata",
            "preferences": {},
            "messages": [HumanMessage(content="what is the duration of my dinner date?")],
            "iteration_count": 0,
        }
    )

    assert result["response_mode"] == "calendar_query"
    assert "get_event_duration" in captured["tool_names"]
    assert "book_event" not in captured["tool_names"]


def test_agent_node_uses_action_tool_subset(monkeypatch):
    captured: dict = {}

    class FakeLLM:
        def invoke(self, _messages):
            return AIMessage(content="ok", tool_calls=[])

    def fake_build_llm(bound_tools=None):
        captured["tool_names"] = [tool.name for tool in (bound_tools or [])]
        return FakeLLM()

    monkeypatch.setattr(agent_mod, "build_llm", fake_build_llm)
    monkeypatch.setattr(
        agent_mod,
        "route_mode",
        lambda user_message, conversation_history, timezone: ModeRoute(
            mode=ConversationMode.CALENDAR_ACTION,
            confidence="high",
            reason="test",
        ),
    )

    result = agent_mod.agent_node(
        {
            "timezone": "Asia/Kolkata",
            "preferences": {},
            "messages": [HumanMessage(content="book dinner date tomorrow at 8pm")],
            "iteration_count": 0,
        }
    )

    assert result["response_mode"] == "calendar_action"
    assert "book_event" in captured["tool_names"]
    assert "update_event_location" in captured["tool_names"]
    assert "update_event_duration" in captured["tool_names"]


def test_agent_node_sanitizes_duration_update_tool_args_from_marker(monkeypatch):
    class FakeLLM:
        def invoke(self, _messages):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "update_event_duration",
                        "id": "call_1",
                        "type": "tool_call",
                        "args": {
                            "user_id": "user123",
                            "event_id": "dinner_date",
                            "current_start_iso": "2026-03-28T20:00:00+05:30",
                            "duration_minutes": 60,
                        },
                    }
                ],
            )

    monkeypatch.setattr(agent_mod, "build_llm", lambda bound_tools=None: FakeLLM())
    monkeypatch.setattr(
        agent_mod,
        "route_mode",
        lambda user_message, conversation_history, timezone: ModeRoute(
            mode=ConversationMode.CALENDAR_ACTION,
            confidence="high",
            reason="test",
        ),
    )

    result = agent_mod.agent_node(
        {
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "preferences": {},
            "messages": [
                AIMessage(content="Booked. [event_id=evt_77 start_iso=2026-03-28T20:00:00+05:30]"),
                HumanMessage(content="make it 1 hour"),
            ],
            "iteration_count": 0,
        }
    )

    tool_call = result["messages"][0].tool_calls[0]
    assert tool_call["name"] == "update_event_duration"
    assert tool_call["args"]["user_id"] == "u1"
    assert tool_call["args"]["event_id"] == "evt_77"
    assert tool_call["args"]["current_start_iso"] == "2026-03-28T20:00:00+05:30"


def test_agent_node_returns_clarification_when_duration_update_lacks_marker(monkeypatch):
    class FakeLLM:
        def invoke(self, _messages):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "update_event_duration",
                        "id": "call_2",
                        "type": "tool_call",
                        "args": {
                            "user_id": "user123",
                            "event_id": "dinner_date",
                            "duration_minutes": 60,
                        },
                    }
                ],
            )

    monkeypatch.setattr(agent_mod, "build_llm", lambda bound_tools=None: FakeLLM())
    monkeypatch.setattr(
        agent_mod,
        "route_mode",
        lambda user_message, conversation_history, timezone: ModeRoute(
            mode=ConversationMode.CALENDAR_ACTION,
            confidence="high",
            reason="test",
        ),
    )

    result = agent_mod.agent_node(
        {
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "preferences": {},
            "messages": [HumanMessage(content="make dinner date 1 hour")],
            "iteration_count": 0,
        }
    )

    assert "pending_clarification" in result
    assert result["execution_result"]["error_code"] == "missing_event_context"


def test_agent_node_rewrites_location_followup_book_event_to_update_location(monkeypatch):
    class FakeLLM:
        def invoke(self, _messages):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "book_event",
                        "id": "call_loc_1",
                        "type": "tool_call",
                        "args": {
                            "user_id": "user123",
                            "title": "dinner date",
                            "start_iso": "2026-03-28T20:00:00+05:30",
                            "duration_minutes": 60,
                            "attendees": [],
                            "send_invites": False,
                            "add_meet_link": False,
                            "location": "Pizza Bakery indiranagar",
                        },
                    }
                ],
            )

    monkeypatch.setattr(agent_mod, "build_llm", lambda bound_tools=None: FakeLLM())
    monkeypatch.setattr(
        agent_mod,
        "route_mode",
        lambda user_message, conversation_history, timezone: ModeRoute(
            mode=ConversationMode.CALENDAR_ACTION,
            confidence="high",
            reason="test",
        ),
    )

    result = agent_mod.agent_node(
        {
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "preferences": {},
            "messages": [
                AIMessage(content="Booked. [event_id=evt_77 start_iso=2026-03-28T20:00:00+05:30]"),
                HumanMessage(content="can you also add the location of the dinner date as Pizza Bakery indiranagar"),
            ],
            "iteration_count": 0,
        }
    )

    tool_call = result["messages"][0].tool_calls[0]
    assert tool_call["name"] == "update_event_location"
    assert tool_call["args"]["user_id"] == "u1"
    assert tool_call["args"]["event_id"] == "evt_77"
    assert tool_call["args"]["current_start_iso"] == "2026-03-28T20:00:00+05:30"
    assert tool_call["args"]["location"] == "Pizza Bakery indiranagar"
