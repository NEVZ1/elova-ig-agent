from __future__ import annotations

from app.instagram.types import OutboundMessage


class BrowserAutomationInstagramClient:
    async def send_text(self, msg: OutboundMessage) -> None:  # noqa: ARG002
        raise NotImplementedError("Browser automation client is not implemented yet.")

    def send_text_sync(self, msg: OutboundMessage) -> None:  # noqa: ARG002
        raise NotImplementedError("Browser automation client is not implemented yet.")

