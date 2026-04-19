from __future__ import annotations

import json
from typing import TypeVar

import httpx
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import logger

T = TypeVar("T", bound=BaseModel)


class GeminiLLM:
    """
    Uses Google AI Studio / Generative Language API with API key.
    Model IDs like: gemini-2.0-flash-lite
    """

    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        self._api_key = settings.gemini_api_key
        self._model = settings.gemini_model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.6, min=0.6, max=5))
    def chat_json(self, *, system: str, user: str, schema: type[T], temperature: float = 0.3) -> T:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent"
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": temperature,
                "response_mime_type": "application/json",
            },
        }
        params = {"key": self._api_key}
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, params=params, json=payload)
            if resp.status_code >= 400:
                logger.error("llm_call_failed", provider="gemini", status=resp.status_code, body=resp.text[:500])
                resp.raise_for_status()
            data = resp.json()
        text = (
            (((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [{}])[0].get("text") or ""
        ).strip()
        try:
            parsed = json.loads(text)
        except Exception:  # noqa: BLE001
            logger.error("llm_invalid_json", content=text[:500], provider="gemini")
            raise
        return schema.model_validate(parsed)

