from __future__ import annotations

from typing import Protocol

from app.instagram.types import OutboundMessage


class InstagramClient(Protocol):
    async def send_text(self, msg: OutboundMessage) -> None: ...

