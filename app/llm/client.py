from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from app.core.config import settings
from app.llm.providers.gemini import GeminiLLM
from app.llm.providers.openai import OpenAILLM


@dataclass(frozen=True)
class LLM:
    provider: str

    def _impl(self):
        provider = (self.provider or "").strip().lower()
        openai_key_present = bool((settings.openai_api_key or "").strip())
        gemini_key_present = bool((settings.gemini_api_key or "").strip())

        # Render env groups can drift (e.g. LLM_PROVIDER=gemini without GEMINI_API_KEY).
        # Prefer the explicitly selected provider when configured; otherwise fall back
        # to the other provider if it is configured to avoid dropping DMs in prod.
        if provider == "gemini":
            if gemini_key_present:
                return GeminiLLM()
            if openai_key_present:
                return OpenAILLM()
            raise RuntimeError("LLM_PROVIDER=gemini but GEMINI_API_KEY is missing (and OPENAI_API_KEY is not set).")

        if provider == "openai":
            if openai_key_present:
                return OpenAILLM()
            if gemini_key_present:
                return GeminiLLM()
            raise RuntimeError("LLM_PROVIDER=openai but OPENAI_API_KEY is missing (and GEMINI_API_KEY is not set).")

        raise ValueError(f"Unknown LLM_PROVIDER: {provider}")

    def chat_json(self, *, system: str, user: str, schema: type[BaseModel], temperature: float = 0.3) -> BaseModel:
        return self._impl().chat_json(system=system, user=user, schema=schema, temperature=temperature)


def get_llm() -> LLM:
    return LLM(provider=settings.llm_provider)
