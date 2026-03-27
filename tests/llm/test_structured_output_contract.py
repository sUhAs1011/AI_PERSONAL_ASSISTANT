from app.llm.schemas import BookingIntent


def test_booking_intent_contract_parses_mocked_groq_output():
    mocked_groq_tool_args = {
        "title": "Design review",
        "start_iso": "2026-03-27T15:00:00+05:30",
        "duration_minutes": 45,
        "attendees": ["alex@example.com"],
        "send_invites": True,
        "add_meet_link": True,
        "event_id_to_cancel": None,
        "confidence": "high",
    }
    obj = BookingIntent.model_validate(mocked_groq_tool_args)
    assert obj.duration_minutes == 45

