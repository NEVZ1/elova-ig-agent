from __future__ import annotations

from pydantic import BaseModel, Field


class OutboundMessage(BaseModel):
    recipient_id: str
    text: str = Field(min_length=1, max_length=2000)


class NormalizedInboundMessage(BaseModel):
    platform: str = "instagram"
    instagram_user_id: str
    instagram_username: str | None = None
    instagram_message_id: str | None = None
    text: str | None = None
    raw: dict

