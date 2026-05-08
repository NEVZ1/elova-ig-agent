from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class LeadUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=256)
    event_type: str | None = Field(default=None, max_length=128)
    budget_min: int | None = Field(default=None, ge=0)
    budget_max: int | None = Field(default=None, ge=0)
    budget_currency: str | None = Field(default=None, max_length=8)
    event_date: date | None = None
    event_date_text: str | None = Field(default=None, max_length=128)
    guest_count: int | None = Field(default=None, ge=0)
    venue_city: str | None = Field(default=None, max_length=128)
    project_value_estimate: int | None = Field(default=None, ge=0)
    preferred_channel: str | None = Field(default=None, max_length=32)
    urgency_level: str | None = Field(default=None, max_length=32)
    handoff_required: bool | None = None
    handoff_reason: str | None = Field(default=None, max_length=512)
    proposal_status: str | None = Field(default=None, max_length=32)
    source: str | None = Field(default=None, max_length=64)
