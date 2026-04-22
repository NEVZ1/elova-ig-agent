from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _to_async_db_url(url: str) -> str:
    # Supports:
    # - postgresql+psycopg://... -> postgresql+asyncpg://...
    # - postgresql://... or postgres://... -> postgresql+asyncpg://...
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql+psycopg://"):
        return "postgresql+asyncpg://" + url.split("://", 1)[1]
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql+asyncpg://" + url.split("://", 1)[1]
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.split("://", 1)[1]
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.split("://", 1)[1]
    return url


def _to_sync_db_url(url: str) -> str:
    # Supports:
    # - postgresql+asyncpg://... -> postgresql+psycopg://...
    # - postgresql://... or postgres://... -> postgresql+psycopg://...
    if url.startswith("postgresql+psycopg://"):
        return url
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg://" + url.split("://", 1)[1]
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql+psycopg://" + url.split("://", 1)[1]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.split("://", 1)[1]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.split("://", 1)[1]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "local"
    log_level: str = "INFO"
    base_url: str = "http://localhost:8000"

    database_url: str | None = None
    database_url_sync: str | None = None

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"

    llm_provider: str = "gemini"
    llm_unified_mode: bool = True

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash-lite"

    ig_verify_token: str = ""
    ig_provider: str = "meta_graph"
    ig_page_access_token: str = ""
    ig_page_id: str = ""
    ig_app_secret: str = ""
    ig_require_signature: bool = True

    whatsapp_number: str = ""
    booking_url: str = ""

    admin_api_key: str = ""

    @model_validator(mode="after")
    def _normalize_urls(self) -> "Settings":
        # DB: allow providing only one URL (Render typically provides DATABASE_URL).
        if not self.database_url and not self.database_url_sync:
            raise ValueError("DATABASE_URL (async) or DATABASE_URL_SYNC (sync) must be set.")

        if self.database_url and not self.database_url_sync:
            self.database_url_sync = _to_sync_db_url(self.database_url)
        if self.database_url_sync and not self.database_url:
            self.database_url = _to_async_db_url(self.database_url_sync)
        # Always normalize driver schemes to avoid psycopg2 defaulting.
        if self.database_url:
            self.database_url = _to_async_db_url(self.database_url)
        if self.database_url_sync:
            self.database_url_sync = _to_sync_db_url(self.database_url_sync)

        # Celery: allow using REDIS_URL if CELERY_* are not set.
        if not self.celery_broker_url:
            self.celery_broker_url = self.redis_url
        if not self.celery_result_backend:
            self.celery_result_backend = self.redis_url
        return self


settings = Settings()
