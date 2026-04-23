from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from app.core.config import settings


def require_admin(x_api_key: str | None = Header(default=None)) -> None:
    expected = (settings.admin_api_key or "").strip()
    provided = (x_api_key or "").strip()
    if not expected:
        raise HTTPException(status_code=500, detail="ADMIN_API_KEY is not configured")
    if not provided or provided != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


AdminAuth = Depends(require_admin)
