from app.graph.builder import route_after_agent, route_after_tool_result


def test_route_after_tool_result_routes_to_finalizer_when_ok():
    state = {"execution_result": {"status": "ok"}}
    assert route_after_tool_result(state) == "finalizer"


def test_route_after_tool_result_routes_to_hitl_on_conflict():
    state = {"execution_result": {"status": "conflict"}}
    assert route_after_tool_result(state) == "hitl"


def test_route_after_tool_result_routes_to_hitl_when_flag_present():
    state = {"needs_hitl": True, "execution_result": {"status": "ok"}}
    assert route_after_tool_result(state) == "hitl"


def test_route_after_agent_still_routes_to_tool_node_when_tool_calls_present():
    class Msg:
        tool_calls = [{"name": "find_events"}]

    state = {"iteration_count": 0, "messages": [Msg()]}
    assert route_after_agent(state) == "tool_node"
