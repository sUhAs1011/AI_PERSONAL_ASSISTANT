import logging

from app.services.hitl.pending_repo import pending_repo

logger = logging.getLogger(__name__)


def hitl_node(state: dict) -> dict:
    trace_id = state.get("trace_id", "na")
    result = state.get("execution_result", {})
    alternatives = result.get("alternatives", []) or state.get("alternatives", [])
    action_id = pending_repo.save(
        user_id=state["user_id"],
        payload={
            "title": "meeting",
            "attendees": [],
            "duration_minutes": 30,
            "send_invites": False,
            "add_meet_link": False,
        },
        alternatives=alternatives,
        timezone=state.get("timezone", "Asia/Kolkata"),
    )
    logger.info("hitl.node trace_id=%s action_id=%s alternatives=%s", trace_id, action_id, len(alternatives))
    return {
        "needs_hitl": True,
        "hitl_action_id": action_id,
        "alternatives": alternatives,
        "execution_result": {"status": "needs_hitl", "alternatives": alternatives},
    }
