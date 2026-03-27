from enum import Enum
import logging
import re
from typing import Literal

from pydantic import BaseModel

from app.llm.client import build_llm

logger = logging.getLogger(__name__)


class ConversationMode(str, Enum):
    CALENDAR_ACTION = "calendar_action"
    CALENDAR_QUERY = "calendar_query"
    GENERAL_CHAT = "general_chat"


class ModeRoute(BaseModel):
    mode: ConversationMode
    confidence: Literal["high", "low"] = "high"
    reason: str | None = None


_ACTION_PHRASES = (
    "book",
    "set up",
    "create meeting",
)
_ACTION_WORDS = {"schedule", "reschedule", "move", "cancel", "invite"}
_QUERY_PHRASES = (
    "how does my day look",
    "what does my day look",
    "how's my day",
    "what is on my calendar",
    "what's on my calendar",
    "show my calendar",
    "show my events",
    "what are my events",
    "availability",
    "am i free",
    "when am i free",
    "free busy",
    "calendar tomorrow",
)
_GENERAL_WORDS = {
    "hello",
    "hi",
    "hey",
    "good morning",
    "good evening",
    "how are you",
    "thank you",
    "thanks",
    "who are you",
    "help me think",
    "advice",
}


def _heuristic_mode(user_message: str) -> ConversationMode | None:
    text = user_message.lower().strip()
    tokens = set(re.findall(r"[a-z']+", text))
    if not text:
        return ConversationMode.GENERAL_CHAT
    if any(hint in text for hint in _ACTION_PHRASES) or any(word in tokens for word in _ACTION_WORDS):
        return ConversationMode.CALENDAR_ACTION
    if any(hint in text for hint in _QUERY_PHRASES):
        return ConversationMode.CALENDAR_QUERY
    if any(word in text for word in ("good morning", "good evening", "how are you", "who are you")):
        return ConversationMode.GENERAL_CHAT
    if any(word in tokens for word in _GENERAL_WORDS):
        return ConversationMode.GENERAL_CHAT
    return None


def route_mode(
    user_message: str,
    conversation_history: list[dict] | None = None,
    timezone: str = "Asia/Kolkata",
) -> ModeRoute:
    history_preview = (conversation_history or [])[-6:]
    prompt = f"""
Classify the latest user message into one mode:
- calendar_action: user asks to create/update/cancel meetings or invites
- calendar_query: user asks to inspect availability/events/schedule
- general_chat: all other conversation

Timezone: {timezone}
Recent history: {history_preview}
User message: {user_message}
""".strip()
    try:
        llm = build_llm(bound_tools=[])
        router_llm = llm.with_structured_output(ModeRoute)
        result = router_llm.invoke(prompt)
        if isinstance(result, ModeRoute):
            logger.info(
                "router.llm mode=%s confidence=%s reason=%s",
                result.mode.value,
                result.confidence,
                result.reason,
            )
            return result
        parsed = ModeRoute.model_validate(result)
        logger.info(
            "router.llm mode=%s confidence=%s reason=%s",
            parsed.mode.value,
            parsed.confidence,
            parsed.reason,
        )
        return parsed
    except Exception:
        logger.exception("router.error_fallback message=%r", user_message[:160])
        heuristic = _heuristic_mode(user_message)
        if heuristic is not None:
            logger.info("router.heuristic_fallback mode=%s message=%r", heuristic.value, user_message[:160])
            return ModeRoute(
                mode=heuristic,
                confidence="low",
                reason="heuristic_fallback_on_router_error",
            )
        return ModeRoute(
            mode=ConversationMode.GENERAL_CHAT,
            confidence="low",
            reason="fallback_on_router_error",
        )
