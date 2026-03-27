from app.graph.nodes.finalizer_node import finalizer_node


def test_finalizer_returns_normalized_final_response_for_created_action(monkeypatch):
    class MockMsg:
        def __init__(self, content: str):
            self.content = content

    class MockLLM:
        def invoke(self, _messages):
            return MockMsg("Done.")

    monkeypatch.setattr("app.graph.nodes.finalizer_node.build_llm", lambda **_: MockLLM())
    out = finalizer_node(
        {
            "response_mode": "calendar_action",
            "execution_result": {
                "status": "created",
                "event": {
                    "id": "evt_99",
                    "meet_link": "https://meet.google.com/abc-defg",
                    "invite_status": "sent",
                },
            },
            "hitl_action_id": "act_123",
            "alternatives": [],
        }
    )
    final = out["final_response"]
    assert final["status"] == "created"
    assert final["summary"] == out["summary"]
    assert final["response_mode"] == "calendar_action"
    assert final["latest_event_id"] == "evt_99"
    assert final["hitl_action_id"] == "act_123"
    assert final["meet_link"] == "https://meet.google.com/abc-defg"
    assert final["invite_status"] == "sent"


def test_finalizer_returns_error_contract_without_llm(monkeypatch):
    monkeypatch.setattr(
        "app.graph.nodes.finalizer_node.build_llm",
        lambda **_: (_ for _ in ()).throw(RuntimeError("llm unavailable")),
    )
    out = finalizer_node(
        {
            "response_mode": "calendar_action",
            "execution_result": {"status": "error", "error": "Invalid action id"},
            "hitl_action_id": "act_404",
        }
    )
    final = out["final_response"]
    assert final["status"] == "error"
    assert final["summary"]
    assert final["response_mode"] == "calendar_action"
    assert final["hitl_action_id"] == "act_404"
