import os
import logging

from langchain_groq import ChatGroq

logger = logging.getLogger(__name__)


def build_llm(bound_tools: list | None = None):
    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    model = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0"))
    max_tokens = int(os.getenv("LLM_MAX_TOKENS", "1024"))
    logger.info(
        "llm.build provider=%s model=%s temperature=%s max_tokens=%s bound_tools=%s",
        provider,
        model,
        temperature,
        max_tokens,
        len(bound_tools or []),
    )

    if provider == "groq":
        llm = ChatGroq(model=model, temperature=temperature, max_tokens=max_tokens)
    else:
        from langchain_community.chat_models import ChatOllama

        llm = ChatOllama(model=model, temperature=temperature)

    tools = bound_tools or []
    if tools:
        return llm.bind_tools(tools)
    return llm
