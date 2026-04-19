from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from app.core.config import settings


def require_admin(x_api_key: str | None = Header(default=None)) -> None:
    if not settings.admin_api_key:
        raise HTTPException(status_code=500, detail="ADMIN_API_KEY is not configured")
    if not x_api_key or x_api_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")


AdminAuth = Depends(require_admin)

