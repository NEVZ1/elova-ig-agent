from __future__ import annotations

import hashlib

from fastapi import APIRouter, Header, HTTPException, Request
from starlette.responses import PlainTextResponse

from app.core.config import settings
from app.core.logging import logger
from app.core.rate_limit import limiter
from app.dm_listener.normalizer import normalize_instagram_payload
from app.instagram.signature import verify_x_hub_signature_256
from app.workers.tasks import process_incoming_dm

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/instagram", response_class=PlainTextResponse)
# Verification endpoints can be hit multiple times during Meta setup.
@limiter.limit("600/minute")
async def instagram_webhook_verify(request: Request):
    # Meta sends hub.* keys. Some tooling / proxies may also include underscore variants.
    # Also handle duplicate query params by taking the first non-empty value.
    def _first_non_empty(*keys: str) -> str | None:
        for k in keys:
            try:
                values = request.query_params.getlist(k)  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                values = [request.query_params.get(k)]
            for v in values:
                if v is not None and str(v).strip():
                    return str(v).strip()
        return None

    mode = _first_non_empty("hub.mode", "hub_mode")
    token = _first_non_empty("hub.verify_token", "hub_verify_token")
    challenge = _first_non_empty("hub.challenge", "hub_challenge")

    if mode == "subscribe" and token:
        expected = (settings.ig_verify_token or "").strip()
        if settings.ig_verify_bypass and challenge:
            logger.warning("instagram_verify_bypass_enabled")
            return challenge

        match = bool(expected) and token.strip() == expected
        logger.info(
            "instagram_webhook_verify",
            mode=mode,
            token_len=len(token),
            expected_len=len(expected),
            token_sha8=hashlib.sha256(token.encode("utf-8")).hexdigest()[:8],
            expected_sha8=hashlib.sha256(expected.encode("utf-8")).hexdigest()[:8] if expected else None,
            match=match,
        )
        if match:
            return challenge or ""
    raise HTTPException(status_code=403, detail="forbidden")


@router.post("/instagram")
@limiter.limit("120/minute")
async def instagram_webhook_receive(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
) -> dict:
    raw_body = await request.body()
    if settings.ig_app_secret and settings.ig_require_signature:
        ok = verify_x_hub_signature_256(settings.ig_app_secret, raw_body, x_hub_signature_256)
        if not ok:
            logger.warning(
                "instagram_bad_signature",
                signature_present=bool(x_hub_signature_256),
            )
            raise HTTPException(status_code=401, detail="bad_signature")
    payload = await request.json()
    logger.info(
        "instagram_webhook_post",
        object=payload.get("object"),
        entry_count=len(payload.get("entry") or []),
        top_keys=list(payload.keys())[:20],
    )
    events = normalize_instagram_payload(payload)
    if not events:
        entry0 = (payload.get("entry") or [{}])[0] if isinstance(payload.get("entry"), list) else {}
        logger.warning(
            "instagram_webhook_no_events",
            object=payload.get("object"),
            entry0_keys=list(entry0.keys())[:30] if isinstance(entry0, dict) else None,
        )
    for e in events:
        logger.info("dm_received", instagram_user_id=e.instagram_user_id, instagram_message_id=e.instagram_message_id)
        try:
            process_incoming_dm.delay(e.model_dump())
        except Exception as exc:  # noqa: BLE001
            logger.error("queue_publish_failed", err=str(exc))
    return {"ok": True, "accepted": len(events)}
