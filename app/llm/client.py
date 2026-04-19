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
        if self.provider == "gemini":
            return GeminiLLM()
        if self.provider == "openai":
            return OpenAILLM()
        raise ValueError(f"Unknown LLM_PROVIDER: {self.provider}")

    def chat_json(self, *, system: str, user: str, schema: type[BaseModel], temperature: float = 0.3) -> BaseModel:
        return self._impl().chat_json(system=system, user=user, schema=schema, temperature=temperature)


def get_llm() -> LLM:
    return LLM(provider=settings.llm_provider)

