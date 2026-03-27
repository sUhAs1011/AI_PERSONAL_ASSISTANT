from app.graph.builder import route_after_agent


def test_iteration_guard_routes_to_finalizer():
    state = {"iteration_count": 3}
    assert route_after_agent(state) == "finalizer"

