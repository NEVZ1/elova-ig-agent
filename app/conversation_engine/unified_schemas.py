from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class UnifiedOutput(BaseModel):
    # Reply
    reply_text: str = Field(min_length=1, max_length=1200)
    stage: str
    intent: str
    action: str

    # Lead updates (only if present in conversation; do not guess)
    name: str | None = Field(default=None, max_length=256)
    event_type: str | None = Field(default=None, max_length=128)
    event_date: date | None = None
    event_date_text: str | None = Field(default=None, max_length=128)
    guest_count: int | None = Field(default=None, ge=0)
    budget_min: int | None = Field(default=None, ge=0)
    budget_max: int | None = Field(default=None, ge=0)
    budget_currency: str | None = Field(default=None, max_length=8)

    # Memory summary
    summary_text: str | None = Field(default=None, max_length=2000)
    key_facts: dict | None = None

