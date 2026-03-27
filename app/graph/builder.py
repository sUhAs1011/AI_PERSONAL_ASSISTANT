import logging

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.graph.nodes.agent_node import agent_node, proxy_tools
from app.graph.nodes.finalizer_node import finalizer_node
from app.graph.nodes.hitl_node import hitl_node
from app.graph.nodes.tool_result_node import tool_result_node
from app.graph.state import AgentState

logger = logging.getLogger(__name__)


def route_after_agent(state: dict) -> str:
    trace_id = state.get("trace_id", "na")
    iteration_count = state.get("iteration_count", 0)
    if state.get("iteration_count", 0) >= 3:
        logger.info("graph.route trace_id=%s route=finalizer reason=iteration_guard iteration=%s", trace_id, iteration_count)
        return "finalizer"
    if state.get("needs_hitl"):
        logger.info("graph.route trace_id=%s route=hitl reason=needs_hitl", trace_id)
        return "hitl"
    if state.get("pending_clarification"):
        logger.info("graph.route trace_id=%s route=finalizer reason=pending_clarification", trace_id)
        return "finalizer"
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None
    if last_message is not None and getattr(last_message, "tool_calls", None):
        logger.info("graph.route trace_id=%s route=tool_node reason=tool_calls_present", trace_id)
        return "tool_node"
    logger.info("graph.route trace_id=%s route=finalizer reason=no_tool_calls", trace_id)
    return "finalizer"


def route_after_tool_result(state: dict) -> str:
    trace_id = state.get("trace_id", "na")
    if state.get("needs_hitl") or state.get("execution_result", {}).get("status") == "conflict":
        logger.info("graph.route_after_tool trace_id=%s route=hitl", trace_id)
        return "hitl"
    logger.info("graph.route_after_tool trace_id=%s route=finalizer", trace_id)
    return "finalizer"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tool_node", ToolNode(proxy_tools))
    graph.add_node("tool_result", tool_result_node)
    graph.add_node("hitl", hitl_node)
    graph.add_node("finalizer", finalizer_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tool_node": "tool_node", "hitl": "hitl", "finalizer": "finalizer"},
    )
    graph.add_edge("tool_node", "tool_result")
    graph.add_conditional_edges(
        "tool_result",
        route_after_tool_result,
        {"hitl": "hitl", "finalizer": "finalizer"},
    )
    graph.add_edge("hitl", END)
    graph.add_edge("finalizer", END)
    return graph.compile()
