from langgraph.graph import MessagesState


class AgentState(MessagesState, total=False):
    trace_id: str
    user_id: str
    timezone: str
    preferences: dict
    iteration_count: int
    response_mode: str
    summary: str
    final_response: dict
    pending_clarification: str | None
    execution_result: dict
    alternatives: list[dict]
    needs_hitl: bool
    hitl_action_id: str
