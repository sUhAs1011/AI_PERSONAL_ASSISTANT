from app.graph.nodes.finalizer_node import finalizer_node


def test_finalizer_contains_time_and_title(monkeypatch):
    class MockMsg:
        def __init__(self, content: str):
            self.content = content

    class MockLLM:
        def invoke(self, _messages):
            return MockMsg("✅ Design Review booked at 15:00 with alex@example.com.")

    monkeypatch.setattr("app.graph.nodes.finalizer_node.build_llm", lambda **_: MockLLM())
    out = finalizer_node(
        {
            "execution_result": {
                "status": "created",
                "event": {"title": "Design Review", "start_iso": "2026-03-27T15:00:00+05:30"},
            }
        }
    )
    assert "Design Review" in out["summary"]
    assert "15:00" in out["summary"]

