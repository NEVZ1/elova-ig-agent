from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import settings

router = APIRouter(tags=["instagram_login"])


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign_state(payload: dict[str, Any]) -> str:
    if not (settings.ig_app_secret or "").strip():
        raise RuntimeError("IG_APP_SECRET missing")
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    msg = _b64url(raw)
    sig = hmac.new(settings.ig_app_secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).digest()
    return f"{msg}.{_b64url(sig)}"


def _verify_state(state: str, max_age_s: int = 15 * 60) -> dict[str, Any]:
    try:
        msg, sig = state.split(".", 1)
        expected = hmac.new(settings.ig_app_secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64url(expected), sig):
            raise ValueError("bad_signature")
        payload = json.loads(_b64url_decode(msg).decode("utf-8"))
        ts = int(payload.get("ts") or 0)
        if ts <= 0 or int(time.time()) - ts > max_age_s:
            raise ValueError("expired")
        return payload
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"invalid_state:{exc}") from exc


@router.get("/connect/instagram")
async def connect_instagram() -> RedirectResponse:
    """
    Minimal Instagram Business Login initiation page for Meta App Review.
    Redirects to the OAuth dialog. After authorization, the user is sent back to
    /auth/instagram/callback where we display basic IG professional profile info.
    """

    app_id = (settings.ig_app_id or "").strip()
    if not app_id:
        raise HTTPException(status_code=500, detail="IG_APP_ID is not configured")

    base = (settings.base_url or "").strip().rstrip("/")
    if not base.startswith("https://"):
        raise HTTPException(status_code=500, detail="BASE_URL must be set to an https:// URL in production")
    redirect_uri = f"{base}/auth/instagram/callback"

    # Keep the scope list focused on the IG DM automation use case.
    scope = ",".join(
        [
            "instagram_business_basic",
            "instagram_business_manage_messages",
            "pages_show_list",
            "pages_read_engagement",
            "business_management",
        ]
    )
    state = _sign_state({"ts": int(time.time())})

    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "state": state,
    }
    url = "https://www.facebook.com/v19.0/dialog/oauth?" + urlencode(params)
    return RedirectResponse(url=url, status_code=302)


@router.get("/auth/instagram/callback")
async def instagram_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None) -> HTMLResponse:
    if error:
        return HTMLResponse(f"<h2>Login error</h2><pre>{error}</pre>", status_code=400)
    if not code or not state:
        return HTMLResponse("<h2>Missing code/state</h2>", status_code=400)

    _verify_state(state)

    app_id = (settings.ig_app_id or "").strip()
    app_secret = (settings.ig_app_secret or "").strip()
    base = (settings.base_url or "").strip().rstrip("/")
    redirect_uri = f"{base}/auth/instagram/callback"

    # Exchange code -> user token.
    token_url = "https://graph.facebook.com/v19.0/oauth/access_token"
    token_params = {
        "client_id": app_id,
        "client_secret": app_secret,
        "redirect_uri": redirect_uri,
        "code": code,
    }

    async with httpx.AsyncClient(timeout=20) as client:
        token_resp = await client.get(token_url, params=token_params)
        if token_resp.status_code >= 400:
            return HTMLResponse(
                f"<h2>Token exchange failed</h2><pre>{token_resp.text}</pre>",
                status_code=400,
            )
        access_token = (token_resp.json() or {}).get("access_token") or ""
        if not access_token:
            return HTMLResponse("<h2>Token exchange failed</h2><pre>Missing access_token</pre>", status_code=400)

        # Fetch connected assets and IG profile basics for reviewer visibility.
        accounts_url = "https://graph.facebook.com/v19.0/me/accounts"
        accounts_params = {"fields": "id,name,instagram_business_account{id,username,profile_picture_url}"}
        accounts_resp = await client.get(accounts_url, headers={"Authorization": f"Bearer {access_token}"}, params=accounts_params)
        accounts_preview = accounts_resp.text

    # Render a simple, review-friendly page (no secrets shown).
    html = f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <title>Instagram Connected</title>
        <style>
          body {{ font-family: ui-sans-serif, system-ui, -apple-system; margin: 40px; }}
          .card {{ border: 1px solid #eee; border-radius: 12px; padding: 16px; max-width: 900px; }}
          pre {{ background: #0b1020; color: #e6e6e6; padding: 12px; border-radius: 10px; overflow: auto; }}
          code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 6px; }}
        </style>
      </head>
      <body>
        <h2>Instagram professional account connected</h2>
        <div class="card">
          <p>This page is used for Meta App Review. It shows basic metadata of the Instagram professional account connected to this app.</p>
          <p><b>Next:</b> send a DM to the connected Instagram account and verify the app can respond automatically.</p>
        </div>
        <h3>Connected assets (sanitized)</h3>
        <pre>{accounts_preview}</pre>
      </body>
    </html>
    """
    return HTMLResponse(html, status_code=200)

