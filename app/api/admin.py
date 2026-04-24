from __future__ import annotations

import hashlib
import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
import httpx
from redis import Redis
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import AdminAuth
from app.core.config import settings
from app.workers.celery_app import celery
from app.workers.tasks import ping
from celery.result import AsyncResult
from app.db.models import Lead, Message
from app.db.session import get_async_session

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[AdminAuth])


@router.get("/leads")
async def list_leads(
    limit: int = 50,
    session: AsyncSession = Depends(get_async_session),
) -> list[dict]:
    limit = max(1, min(200, limit))
    rows = (await session.execute(select(Lead).order_by(desc(Lead.updated_at)).limit(limit))).scalars().all()
    return [
        {
            "id": str(lead.id),
            "instagram_user_id": lead.instagram_user_id,
            "instagram_username": lead.instagram_username,
            "name": lead.name,
            "event_type": lead.event_type,
            "event_date": lead.event_date.isoformat() if lead.event_date else None,
            "budget_min": lead.budget_min,
            "budget_max": lead.budget_max,
            "status": lead.status,
            "stage": lead.stage,
            "followup_state": lead.followup_state,
            "last_message_at": lead.last_message_at.isoformat() if lead.last_message_at else None,
            "updated_at": lead.updated_at.isoformat(),
        }
        for lead in rows
    ]


@router.get("/leads/{lead_id}")
async def get_lead(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")
    return {
        "id": str(lead.id),
        "instagram_user_id": lead.instagram_user_id,
        "instagram_username": lead.instagram_username,
        "name": lead.name,
        "event_type": lead.event_type,
        "event_date": lead.event_date.isoformat() if lead.event_date else None,
        "event_date_text": lead.event_date_text,
        "guest_count": lead.guest_count,
        "budget_min": lead.budget_min,
        "budget_max": lead.budget_max,
        "budget_currency": lead.budget_currency,
        "source": lead.source,
        "stage": lead.stage,
        "status": lead.status,
        "followup_state": lead.followup_state,
        "opted_out": lead.opted_out,
        "last_message_at": lead.last_message_at.isoformat() if lead.last_message_at else None,
        "last_inbound_at": lead.last_inbound_at.isoformat() if lead.last_inbound_at else None,
        "last_outbound_at": lead.last_outbound_at.isoformat() if lead.last_outbound_at else None,
        "created_at": lead.created_at.isoformat(),
        "updated_at": lead.updated_at.isoformat(),
    }


@router.get("/leads/{lead_id}/messages")
async def get_lead_messages(
    lead_id: uuid.UUID,
    limit: int = 100,
    session: AsyncSession = Depends(get_async_session),
) -> list[dict]:
    limit = max(1, min(500, limit))
    lead = (await session.execute(select(Lead.id).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")
    rows = (
        (await session.execute(select(Message).where(Message.lead_id == lead_id).order_by(desc(Message.created_at)).limit(limit)))
        .scalars()
        .all()
    )
    return [
        {
            "id": str(m.id),
            "direction": m.direction,
            "channel": m.channel,
            "instagram_message_id": m.instagram_message_id,
            "text": m.text,
            "created_at": m.created_at.isoformat(),
        }
        for m in rows
    ]


@router.get("/debug/config")
async def debug_config() -> dict:
    """
    Debug endpoint (admin-protected) to verify which env vars the running service
    actually sees in production. Never returns raw secrets.
    """

    def _hash8(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]

    def _url_bits(value: str | None) -> dict:
        if not value:
            return {"present": False}
        p = urlparse(value)
        return {"present": True, "scheme": p.scheme, "host": p.hostname, "port": p.port}

    verify_token = (settings.ig_verify_token or "").strip()
    return {
        "env": settings.env,
        "llm": {
            "provider": (settings.llm_provider or "").strip(),
            "openai_api_key_present": bool((settings.openai_api_key or "").strip()),
            "openai_model": (settings.openai_model or "").strip(),
            "gemini_api_key_present": bool((settings.gemini_api_key or "").strip()),
            "gemini_model": (settings.gemini_model or "").strip(),
        },
        "ig": {
            "app_id_present": bool((settings.ig_app_id or "").strip()),
            "page_id_present": bool((settings.ig_page_id or "").strip()),
            "sender_id_present": bool((settings.ig_sender_id or "").strip()),
        },
        "ig_verify_token": {"present": bool(verify_token), "len": len(verify_token), "sha256_8": _hash8(verify_token) if verify_token else None},
        "ig_app_secret_present": bool((settings.ig_app_secret or "").strip()),
        "ig_require_signature": bool(settings.ig_require_signature),
        "ig_verify_bypass": bool(settings.ig_verify_bypass),
        "redis_url": _url_bits(settings.redis_url),
        "celery_broker_url": _url_bits(settings.celery_broker_url),
        "celery_result_backend": _url_bits(settings.celery_result_backend),
        "database_url_present": bool((settings.database_url or "").strip()),
        "database_url_sync_present": bool((settings.database_url_sync or "").strip()),
    }


@router.get("/debug/queue")
async def debug_queue() -> dict:
    """
    Debug endpoint (admin-protected) to confirm that:
    - web and worker point at the same Redis broker
    - messages are being enqueued to the default `celery` list
    """

    def _url_bits(value: str | None) -> dict:
        if not value:
            return {"present": False}
        p = urlparse(value)
        db = None
        if p.path and p.path != "/":
            try:
                db = int(p.path.lstrip("/"))
            except Exception:  # noqa: BLE001
                db = p.path
        return {"present": True, "scheme": p.scheme, "host": p.hostname, "port": p.port, "db": db}

    broker = settings.celery_broker_url or ""
    backend = settings.celery_result_backend or ""
    redis_url = settings.redis_url or ""

    r = Redis.from_url(redis_url)  # type: ignore[arg-type]

    # Redis transport may apply a key prefix. Probe a small set of likely keys.
    candidates = ["celery"]
    try:
        # Scan is safer than KEYS.
        for k in r.scan_iter(match="*celery*", count=200):
            ks = k.decode("utf-8", errors="ignore") if isinstance(k, (bytes, bytearray)) else str(k)
            if ks not in candidates:
                candidates.append(ks)
            if len(candidates) >= 15:
                break
    except Exception:  # noqa: BLE001
        pass

    key_stats: list[dict] = []
    for key in candidates:
        try:
            t = r.type(key)
            t_str = t.decode() if isinstance(t, (bytes, bytearray)) else str(t)
            if t_str == "list":
                size = int(r.llen(key))
            else:
                size = None
            key_stats.append({"key": key, "type": t_str, "llen": size})
        except Exception:  # noqa: BLE001
            continue

    return {
        "settings": {
            "redis_url": _url_bits(redis_url),
            "celery_broker_url": _url_bits(broker),
            "celery_result_backend": _url_bits(backend),
        },
        "celery_conf": {
            "broker_url": _url_bits(celery.conf.broker_url),
            "result_backend": _url_bits(celery.conf.result_backend),
        },
        "redis_probe": {"keys": key_stats},
    }


@router.post("/debug/enqueue-ping")
async def debug_enqueue_ping() -> dict:
    """
    Enqueue a tiny task to validate that the worker is consuming from the same broker.
    Expect worker logs to include: `worker_ping`.
    """

    res = ping.delay()
    return {"task_id": res.id}


@router.get("/debug/task/{task_id}")
async def debug_task(task_id: str) -> dict:
    """
    Inspect a Celery task state via the configured result backend.
    Useful to confirm whether `process_incoming_dm` ran and whether it failed.
    """

    ar = AsyncResult(task_id, app=celery)
    result = None
    tb = None
    try:
        if ar.ready():
            r = ar.result
            result = str(r)
            if result and len(result) > 800:
                result = result[:800] + "…"
            tb = ar.traceback
            if tb and len(tb) > 1200:
                tb = tb[:1200] + "…"
    except Exception as exc:  # noqa: BLE001
        result = f"<error reading result: {exc}>"

    return {
        "task_id": task_id,
        "state": ar.state,
        "ready": bool(ar.ready()),
        "successful": bool(ar.successful()) if ar.ready() else None,
        "result": result,
        "traceback": tb,
    }


@router.get("/debug/openai")
async def debug_openai() -> dict:
    """
    Sanity-check the configured OpenAI credentials from the running service.
    Returns only status and a truncated error body (never the API key).
    """

    key = (settings.openai_api_key or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY_missing")

    headers = {"Authorization": f"Bearer {key}"}
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get("https://api.openai.com/v1/models", headers=headers)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}

    body_preview = resp.text[:400] if resp.text else ""
    return {"ok": resp.status_code < 400, "status": resp.status_code, "body_preview": body_preview}


@router.get("/debug/openai-chat")
async def debug_openai_chat() -> dict:
    """
    End-to-end check that the configured OpenAI key AND model can run the exact
    endpoint used by the worker (/v1/chat/completions).
    """

    key = (settings.openai_api_key or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY_missing")

    model = (settings.openai_model or "").strip()
    if not model:
        raise HTTPException(status_code=400, detail="OPENAI_MODEL_missing")

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "Return JSON: {\"ok\": true}"},
            {"role": "user", "content": "ping"},
        ],
    }
    try:
        with httpx.Client(timeout=20) as client:
            resp = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}

    body_preview = resp.text[:500] if resp.text else ""
    return {"ok": resp.status_code < 400, "status": resp.status_code, "model": model, "body_preview": body_preview}


@router.get("/debug/instagram-identity")
async def debug_instagram_identity() -> dict:
    """
    Resolve the Instagram sender identity for messaging:
    - Page ID -> connected instagram_business_account / connected_instagram_account
    Uses IG_PAGE_ACCESS_TOKEN for auth.
    """

    token = (settings.ig_page_access_token or "").strip()
    page_id = (settings.ig_page_id or "").strip()
    if not token or not page_id:
        raise HTTPException(status_code=400, detail="IG_PAGE_ACCESS_TOKEN_or_IG_PAGE_ID_missing")

    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://graph.facebook.com/v19.0/{page_id}"
    params = {"fields": "id,name,instagram_business_account,connected_instagram_account"}
    with httpx.Client(timeout=15) as client:
        resp = client.get(url, headers=headers, params=params)
        body_preview = resp.text[:500] if resp.text else ""
        if resp.status_code >= 400:
            return {"ok": False, "status": resp.status_code, "body_preview": body_preview}
        return {"ok": True, "status": resp.status_code, "data": resp.json()}


@router.get("/debug/instagram-token")
async def debug_instagram_token() -> dict:
    """
    Validate IG_PAGE_ACCESS_TOKEN using Graph API /debug_token.
    This helps detect when a token is a *User token* (wrong) instead of a *Page token*,
    missing scopes, or expired.
    """

    app_id = (settings.ig_app_id or "").strip()
    app_secret = (settings.ig_app_secret or "").strip()
    input_token = (settings.ig_page_access_token or "").strip()

    if not app_id or not app_secret:
        raise HTTPException(status_code=400, detail="IG_APP_ID_or_IG_APP_SECRET_missing")
    if not input_token:
        raise HTTPException(status_code=400, detail="IG_PAGE_ACCESS_TOKEN_missing")

    app_access_token = f"{app_id}|{app_secret}"
    url = "https://graph.facebook.com/debug_token"
    params = {"input_token": input_token, "access_token": app_access_token}
    with httpx.Client(timeout=15) as client:
        resp = client.get(url, params=params)
        body_preview = resp.text[:800] if resp.text else ""
        if resp.status_code >= 400:
            return {"ok": False, "status": resp.status_code, "body_preview": body_preview}
        data = resp.json().get("data") or {}

    # Return a safe subset.
    return {
        "ok": True,
        "is_valid": bool(data.get("is_valid")),
        "type": data.get("type"),
        "app_id": data.get("app_id"),
        "user_id": data.get("user_id"),
        "expires_at": data.get("expires_at"),
        "scopes": data.get("scopes"),
        "granular_scopes": data.get("granular_scopes"),
    }
