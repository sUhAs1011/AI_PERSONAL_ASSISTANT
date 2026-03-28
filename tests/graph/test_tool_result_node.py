import json

from langchain_core.messages import ToolMessage

from app.graph.nodes.tool_result_node import tool_result_node


def test_find_events_tool_message_populates_execution_result():
    state = {
        "messages": [
            ToolMessage(
                content=json.dumps({"events": [{"id": "evt_1"}]}),
                tool_call_id="call_1",
                name="find_events",
            )
        ]
    }
    result = tool_result_node(state)
    assert result["response_mode"] == "calendar_query"
    assert result["execution_result"]["status"] == "ok"
    assert result["execution_result"]["events"][0]["id"] == "evt_1"


def test_free_busy_tool_message_populates_execution_result():
    state = {
        "messages": [
            ToolMessage(
                content=json.dumps(
                    {
                        "status": "free",
                        "summary": "You're free 2-4pm on Thursday.",
                        "windows": [
                            {
                                "start_iso": "2026-03-27T14:00:00+05:30",
                                "end_iso": "2026-03-27T16:00:00+05:30",
                            }
                        ],
                    }
                ),
                tool_call_id="call_2",
                name="check_availability",
            )
        ]
    }
    result = tool_result_node(state)
    assert result["response_mode"] == "calendar_query"
    assert result["execution_result"]["status"] == "free"
    assert "summary" in result["execution_result"]


def test_get_event_duration_tool_message_populates_execution_result():
    state = {
        "messages": [
            ToolMessage(
                content=json.dumps(
                    {
                        "status": "ok",
                        "summary": "Your Dinner Date is 90 minutes long.",
                        "title": "Dinner Date",
                        "duration_minutes": 90,
                        "start_iso": "2026-03-28T20:00:00+05:30",
                        "end_iso": "2026-03-28T21:30:00+05:30",
                    }
                ),
                tool_call_id="call_3",
                name="get_event_duration",
            )
        ]
    }
    result = tool_result_node(state)
    assert result["response_mode"] == "calendar_query"
    assert result["execution_result"]["status"] == "ok"
    assert result["execution_result"]["duration_minutes"] == 90
    assert "Dinner Date" in result["execution_result"]["summary"]


def test_update_event_duration_tool_message_populates_action_execution_result():
    state = {
        "messages": [
            ToolMessage(
                content=json.dumps(
                    {
                        "status": "updated",
                        "event": {"id": "evt_42"},
                        "event_id": "evt_42",
                        "start_iso": "2026-03-28T20:00:00+05:30",
                        "duration_minutes": 45,
                    }
                ),
                tool_call_id="call_4",
                name="update_event_duration",
            )
        ]
    }
    result = tool_result_node(state)
    assert result["response_mode"] == "calendar_action"
    assert result["execution_result"]["status"] == "updated"
    assert result["execution_result"]["event"]["id"] == "evt_42"
    assert result["execution_result"]["duration_minutes"] == 45
