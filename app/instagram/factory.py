from __future__ import annotations

from app.core.config import settings
from app.instagram.browser_stub import BrowserAutomationInstagramClient
from app.instagram.meta_graph import MetaGraphInstagramClient


def get_instagram_client():
    if settings.ig_provider == "meta_graph":
        return MetaGraphInstagramClient()
    if settings.ig_provider == "browser_automation":
        return BrowserAutomationInstagramClient()
    raise ValueError(f"Unknown IG_PROVIDER: {settings.ig_provider}")

