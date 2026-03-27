from typing import Literal

from pydantic import BaseModel, Field


class BookingIntent(BaseModel):
    title: str = Field(default="meeting")
    start_iso: str | None = None
    duration_minutes: int = 30
    attendees: list[str] = Field(default_factory=list)
    send_invites: bool = False
    add_meet_link: bool = False
    event_id_to_cancel: str | None = None
    confidence: Literal["high", "low"] = "low"

