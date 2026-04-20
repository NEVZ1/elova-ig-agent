from __future__ import annotations

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
@limiter.limit("60/minute")
async def instagram_webhook_verify(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token and token == settings.ig_verify_token:
        return challenge or ""
    raise HTTPException(status_code=403, detail="forbidden")


@router.post("/instagram")
@limiter.limit("120/minute")
async def instagram_webhook_receive(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
) -> dict:
    raw_body = await request.body()
    if settings.ig_app_secret:
        if not verify_x_hub_signature_256(settings.ig_app_secret, raw_body, x_hub_signature_256):
            raise HTTPException(status_code=401, detail="bad_signature")
    payload = await request.json()
    events = normalize_instagram_payload(payload)
    for e in events:
        logger.info("dm_received", instagram_user_id=e.instagram_user_id, instagram_message_id=e.instagram_message_id)
        try:
            process_incoming_dm.delay(e.model_dump())
        except Exception as exc:  # noqa: BLE001
            logger.error("queue_publish_failed", err=str(exc))
    return {"ok": True, "accepted": len(events)}
