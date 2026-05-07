from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from redis import Redis

from app.core.config import settings

router = APIRouter(tags=["review"])


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_review_markers() -> dict:
    r = Redis.from_url(settings.redis_url)
    out = {}
    for k in ["review:last_dm_at", "review:last_dm_user_id", "review:last_dm_message_id"]:
        try:
            v = r.get(k)
            out[k] = v.decode("utf-8", errors="ignore") if isinstance(v, (bytes, bytearray)) else v
        except Exception:  # noqa: BLE001
            out[k] = None
    return out


@router.get("/review/status", response_class=HTMLResponse)
async def review_status() -> HTMLResponse:
    """
    Public, non-sensitive status page intended for Meta App Review.
    Shows last inbound DM markers (received via webhook) and basic app config presence.
    """

    markers = _get_review_markers()
    last_at = markers.get("review:last_dm_at")
    last_at_human = None
    try:
        if last_at:
            last_at_human = datetime.fromtimestamp(int(last_at), tz=timezone.utc).isoformat()
    except Exception:  # noqa: BLE001
        last_at_human = None

    html = f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <title>Elova IG Agent — Review Status</title>
        <style>
          body {{ font-family: ui-sans-serif, system-ui, -apple-system; margin: 40px; }}
          .card {{ border: 1px solid #eee; border-radius: 12px; padding: 16px; max-width: 900px; }}
          code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 6px; }}
          .muted {{ color: #6b7280; }}
          table {{ border-collapse: collapse; width: 100%; }}
          td {{ padding: 8px; border-bottom: 1px solid #f0f0f0; }}
        </style>
      </head>
      <body>
        <h2>Elova IG Agent — Review Status</h2>
        <div class="card">
          <p class="muted">This page is intended for Meta App Review. It does not expose secrets.</p>
          <table>
            <tr><td><b>Server time (UTC)</b></td><td><code>{_utc_now_iso()}</code></td></tr>
            <tr><td><b>ENV</b></td><td><code>{settings.env}</code></td></tr>
            <tr><td><b>Last DM received at (UTC)</b></td><td><code>{last_at_human or "—"}</code></td></tr>
            <tr><td><b>Last DM sender IG user id</b></td><td><code>{markers.get("review:last_dm_user_id") or "—"}</code></td></tr>
            <tr><td><b>Last DM message id</b></td><td><code>{(markers.get("review:last_dm_message_id") or "—")}</code></td></tr>
            <tr><td><b>Webhook endpoint</b></td><td><code>{settings.base_url.rstrip("/")}/webhooks/instagram</code></td></tr>
          </table>
        </div>
      </body>
    </html>
    """
    return HTMLResponse(html, status_code=200)

