from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import AdminAuth
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

