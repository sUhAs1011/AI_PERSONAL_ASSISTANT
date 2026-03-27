import app.llm.router as router


def test_router_prefers_llm_routing_over_heuristic(monkeypatch):
    class FakeStructured:
        def invoke(self, _prompt):
            return {
                "mode": "general_chat",
                "confidence": "high",
                "reason": "llm_router",
            }

    class FakeLLM:
        def with_structured_output(self, _schema):
            return FakeStructured()

    monkeypatch.setattr(router, "build_llm", lambda bound_tools=None: FakeLLM())
    result = router.route_mode("How does my day look tomorrow?", [])
    assert result.mode == router.ConversationMode.GENERAL_CHAT
    assert result.reason == "llm_router"


def test_router_uses_llm_for_day_overview_when_available(monkeypatch):
    class FakeStructured:
        def invoke(self, _prompt):
            return {
                "mode": "calendar_query",
                "confidence": "high",
                "reason": "llm_router",
            }

    class FakeLLM:
        def with_structured_output(self, _schema):
            return FakeStructured()

    monkeypatch.setattr(router, "build_llm", lambda bound_tools=None: FakeLLM())
    result = router.route_mode("How does my day look tomorrow?", [])
    assert result.mode == router.ConversationMode.CALENDAR_QUERY
    assert result.confidence == "high"


def test_router_returns_general_chat_for_small_talk(monkeypatch):
    class FakeStructured:
        def invoke(self, _prompt):
            return {
                "mode": "general_chat",
                "confidence": "high",
                "reason": "llm_router",
            }

    class FakeLLM:
        def with_structured_output(self, _schema):
            return FakeStructured()

    monkeypatch.setattr(router, "build_llm", lambda bound_tools=None: FakeLLM())
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


def test_router_falls_back_to_heuristic_when_llm_errors(monkeypatch):
    class BrokenLLM:
        def with_structured_output(self, _schema):
            raise RuntimeError("router unavailable")

    monkeypatch.setattr(router, "build_llm", lambda bound_tools=None: BrokenLLM())
    result = router.route_mode("How does my day look tomorrow?", [])
    assert result.mode == router.ConversationMode.CALENDAR_QUERY
    assert result.reason == "heuristic_fallback_on_router_error"
