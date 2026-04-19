from __future__ import annotations

import json
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import logger

T = TypeVar("T", bound=BaseModel)


class OpenAILLM:
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.6, min=0.6, max=5))
    def chat_json(self, *, system: str, user: str, schema: type[T], temperature: float = 0.3) -> T:
        resp = self._client.chat.completions.create(
            model=self._model,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = (resp.choices[0].message.content or "").strip()
        try:
            data = json.loads(content)
        except Exception:  # noqa: BLE001
            logger.error("llm_invalid_json", content=content[:500], provider="openai")
            raise
        return schema.model_validate(data)

