import httpx
from groq import BadRequestError
from langchain_core.messages import HumanMessage

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
