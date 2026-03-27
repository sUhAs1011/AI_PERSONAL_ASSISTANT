import app.llm.router as router


def test_router_returns_calendar_query_for_day_overview():
    result = router.route_mode("How does my day look tomorrow?", [])
    assert result.mode == router.ConversationMode.CALENDAR_QUERY
    assert result.confidence == "high"


def test_router_returns_general_chat_for_small_talk():
    result = router.route_mode("Hey, good morning!", [])
    assert result.mode == router.ConversationMode.GENERAL_CHAT
    assert result.confidence == "high"


def test_router_uses_llm_when_heuristic_uncertain(monkeypatch):
    class FakeStructured:
        def invoke(self, _prompt):
            return {
                "mode": "calendar_action",
                "confidence": "high",
                "reason": "llm_router",
            }

    class FakeLLM:
        def with_structured_output(self, _schema):
            return FakeStructured()

    monkeypatch.setattr(router, "build_llm", lambda bound_tools=None: FakeLLM())
    result = router.route_mode("Please take care of this for tomorrow.", [])
    assert result.mode == router.ConversationMode.CALENDAR_ACTION
