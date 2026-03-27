import app.graph.nodes.hitl_node as hitl_module


def test_hitl_node_returns_action_id(monkeypatch):
    monkeypatch.setattr(hitl_module.pending_repo, "save", lambda **_: "act_123")
    out = hitl_module.hitl_node(
        {
            "user_id": "u1",
            "execution_result": {"alternatives": [{"start_iso": "2026-03-27T16:00:00+05:30"}]},
        }
    )
    assert out["needs_hitl"] is True
    assert out["hitl_action_id"] == "act_123"

