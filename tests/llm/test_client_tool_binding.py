import app.llm.client as llm_client


def test_build_llm_binds_tools_without_forcing_tool_choice(monkeypatch):
    captured: dict = {}

    class FakeLLM:
        def bind_tools(self, tools, tool_choice=None, **kwargs):
            captured["tools"] = tools
            captured["tool_choice"] = tool_choice
            return "BOUND"

    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setattr(llm_client, "ChatGroq", lambda **_: FakeLLM())

    result = llm_client.build_llm(bound_tools=["tool_a"])

    assert result == "BOUND"
    assert captured["tools"] == ["tool_a"]
    assert captured["tool_choice"] is None


def test_build_llm_returns_raw_model_when_no_tools(monkeypatch):
    class FakeLLM:
        bind_tools_called = False

        def bind_tools(self, tools, tool_choice=None, **kwargs):
            self.bind_tools_called = True
            return self

    fake = FakeLLM()
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setattr(llm_client, "ChatGroq", lambda **_: fake)

    result = llm_client.build_llm(bound_tools=[])

    assert result is fake
    assert fake.bind_tools_called is False
