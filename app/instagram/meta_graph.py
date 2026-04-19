from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import logger
from app.instagram.types import OutboundMessage


class MetaGraphInstagramClient:
    def __init__(self) -> None:
        if not settings.ig_page_access_token or not settings.ig_page_id:
            logger.warning("instagram_config_missing", ig_page_id=bool(settings.ig_page_id))
        self._page_access_token = settings.ig_page_access_token
        self._page_id = settings.ig_page_id

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4))
    async def send_text(self, msg: OutboundMessage) -> None:
        if not self._page_access_token or not self._page_id:
            raise RuntimeError("Instagram credentials missing (IG_PAGE_ACCESS_TOKEN / IG_PAGE_ID).")
        url = f"https://graph.facebook.com/v19.0/{self._page_id}/messages"
        payload = {
            "recipient": {"id": msg.recipient_id},
            "message": {"text": msg.text},
            "messaging_type": "RESPONSE",
        }
        params = {"access_token": self._page_access_token}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, params=params, json=payload)
            if resp.status_code >= 400:
                logger.error("instagram_send_failed", status=resp.status_code, body=resp.text)
                resp.raise_for_status()

    def send_text_sync(self, msg: OutboundMessage) -> None:
        if not self._page_access_token or not self._page_id:
            raise RuntimeError("Instagram credentials missing (IG_PAGE_ACCESS_TOKEN / IG_PAGE_ID).")
        url = f"https://graph.facebook.com/v19.0/{self._page_id}/messages"
        payload = {
            "recipient": {"id": msg.recipient_id},
            "message": {"text": msg.text},
            "messaging_type": "RESPONSE",
        }
        params = {"access_token": self._page_access_token}
        with httpx.Client(timeout=15) as client:
            resp = client.post(url, params=params, json=payload)
            if resp.status_code >= 400:
                logger.error("instagram_send_failed", status=resp.status_code, body=resp.text)
                resp.raise_for_status()
