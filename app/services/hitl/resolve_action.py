def resolve_hitl_action(
    *,
    pending: dict | None,
    decision: str,
    selected_start_iso: str | None,
    action_id: str,
    book_event_tool,
) -> dict:
    if not pending:
        return {
            "user_id": None,
            "timezone": "Asia/Kolkata",
            "alternatives": [],
            "hitl_action_id": action_id,
            "execution_result": {
                "status": "error",
                "error": "Invalid action id",
            },
        }

    timezone = pending.get("timezone", "Asia/Kolkata")
    if decision != "reschedule" or not selected_start_iso:
        return {
            "user_id": pending.get("user_id"),
            "timezone": timezone,
            "alternatives": pending.get("alternatives", []),
            "hitl_action_id": action_id,
            "execution_result": {
                "status": "cancelled",
                "reason": "No rebooking action taken",
            },
        }

    booking_payload = {
        "user_id": pending["user_id"],
        "timezone": timezone,
        "title": pending["payload"]["title"],
        "start_iso": selected_start_iso,
        "duration_minutes": pending["payload"].get("duration_minutes", 30),
        "attendees": pending["payload"].get("attendees", []),
        "send_invites": pending["payload"].get("send_invites", False),
        "add_meet_link": pending["payload"].get("add_meet_link", False),
    }
    result = book_event_tool.invoke(booking_payload)
    if not isinstance(result, dict):
        result = {"status": "error", "error": "Unexpected booking tool response"}
    if "status" not in result:
        result["status"] = "ok"

    return {
        "user_id": pending.get("user_id"),
        "timezone": timezone,
        "alternatives": pending.get("alternatives", []),
        "hitl_action_id": action_id,
        "execution_result": result,
        "booking_payload": booking_payload,
    }
