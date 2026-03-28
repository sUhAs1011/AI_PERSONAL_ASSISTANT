from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: str
    timezone: str
    message: str
    conversation_history: list[dict] = Field(default_factory=list)


class CalendarCachePrimeRequest(BaseModel):
    user_id: str
    timezone: str


class CalendarCachePrimeResponse(BaseModel):
    status: str
    today_count: int
    tomorrow_count: int
    total_count: int


class ChatResponse(BaseModel):
    status: str
    summary: str
    response_mode: str = "general_chat"
    meet_link: str | None = None
    invite_status: str | None = None
    latest_event_id: str | None = None
    hitl_action_id: str | None = None
    alternatives: list[dict] = Field(default_factory=list)
    conversation_history: list[dict] = Field(default_factory=list)


class HitlResponse(BaseModel):
    action_id: str
    decision: str
    selected_start_iso: str | None = None


class PreferencesUpsertRequest(BaseModel):
    no_meetings_before_hour: int
