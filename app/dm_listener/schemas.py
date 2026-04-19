from __future__ import annotations

from pydantic import BaseModel


class WebhookVerifyQuery(BaseModel):
    hub_mode: str | None = None
    hub_verify_token: str | None = None
    hub_challenge: str | None = None

