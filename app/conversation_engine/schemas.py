from __future__ import annotations

from pydantic import BaseModel, Field


class ReplyPlan(BaseModel):
    reply_text: str = Field(min_length=1, max_length=1200)
    stage: str = Field(description="greeting | qualification | positioning | conversion | followup")
    intent: str = Field(description="price_inquiry | booking_intent | general_inquiry | other")
    action: str = Field(description="ask_question | provide_offer | push_whatsapp | suggest_booking | no_action")

