from __future__ import annotations

from pydantic import BaseModel


class Decision(BaseModel):
    stage: str
    status: str
    goal: str
    missing_fields: list[str]

