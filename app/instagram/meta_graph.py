from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import logger
from app.instagram.types import OutboundMessage


class MetaGraphInstagramClient:
    def __init__(self) -> None:
        if not settings.ig_page_access_token:
            logger.warning("instagram_config_missing", ig_page_access_token=False)
        if not settings.ig_sender_id and not settings.ig_page_id:
            logger.warning(
                "instagram_config_missing",
                ig_sender_id=False,
                ig_page_id=bool(settings.ig_page_id),
            )
        self._page_access_token = (settings.ig_page_access_token or "").strip()
        # Prefer IG sender id (Instagram Business/Professional account id).
        self._sender_id = (settings.ig_sender_id or "").strip() or (settings.ig_page_id or "").strip()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4))
    async def send_text(self, msg: OutboundMessage) -> None:
        if not self._page_access_token or not self._sender_id:
            raise RuntimeError("Instagram credentials missing (IG_PAGE_ACCESS_TOKEN and IG_SENDER_ID/IG_PAGE_ID).")
        url = f"https://graph.facebook.com/v19.0/{self._sender_id}/messages"
        payload = {
            "recipient": {"id": msg.recipient_id},
            "message": {"text": msg.text},
            "messaging_type": "RESPONSE",
        }
        # Use Authorization header to avoid leaking tokens in logs and URLs.
        headers = {"Authorization": f"Bearer {self._page_access_token}"}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                logger.error("instagram_send_failed", status=resp.status_code, body=resp.text)
                resp.raise_for_status()

    def send_text_sync(self, msg: OutboundMessage) -> None:
        if not self._page_access_token or not self._sender_id:
            raise RuntimeError("Instagram credentials missing (IG_PAGE_ACCESS_TOKEN and IG_SENDER_ID/IG_PAGE_ID).")
        url = f"https://graph.facebook.com/v19.0/{self._sender_id}/messages"
        payload = {
            "recipient": {"id": msg.recipient_id},
            "message": {"text": msg.text},
            "messaging_type": "RESPONSE",
        }
        headers = {"Authorization": f"Bearer {self._page_access_token}"}
        with httpx.Client(timeout=15) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                logger.error("instagram_send_failed", status=resp.status_code, body=resp.text)
                resp.raise_for_status()
