import httpx
from fastapi.testclient import TestClient
from groq import BadRequestError

import app.main as app_main


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


def test_chat_returns_safe_response_when_tool_use_fails():
    class StubGraph:
        def invoke(self, state):
            raise _tool_use_failed_error()

    app_main.booking_graph = StubGraph()
    app_main.preferences_repo.get_preferences = lambda _uid: {"no_meetings_before_hour": 10}

    client = TestClient(app_main.app)
    resp = client.post(
        "/chat",
        json={
            "user_id": "u1",
            "timezone": "Asia/Kolkata",
            "message": "Show my events for tomorrow",
            "conversation_history": [],
        },
    )

    body = resp.json()
    assert resp.status_code == 200
    assert body["status"] == "needs_clarification"
    assert "Please rephrase" in body["summary"]
