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
from app.proposal_engine.builder import build_proposal_draft
from app.workers.celery_app import celery
from app.workers.tasks import ping
from celery.result import AsyncResult
from app.db.models import Lead, Message
from app.db.session import get_async_session
from sqlalchemy import or_
from datetime import datetime, timezone

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[AdminAuth])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
            "venue_city": lead.venue_city,
            "budget_min": lead.budget_min,
            "budget_max": lead.budget_max,
            "project_value_estimate": lead.project_value_estimate,
            "owner": lead.owner,
            "preferred_channel": lead.preferred_channel,
            "urgency_level": lead.urgency_level,
            "status": lead.status,
            "stage": lead.stage,
            "proposal_status": lead.proposal_status,
            "handoff_required": lead.handoff_required,
            "followup_state": lead.followup_state,
            "review_status": lead.review_status,
            "testimonial_status": lead.testimonial_status,
            "referral_status": lead.referral_status,
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
        "venue_city": lead.venue_city,
        "budget_min": lead.budget_min,
        "budget_max": lead.budget_max,
        "budget_currency": lead.budget_currency,
        "project_value_estimate": lead.project_value_estimate,
        "preferred_channel": lead.preferred_channel,
        "urgency_level": lead.urgency_level,
        "owner": lead.owner,
        "proposal_status": lead.proposal_status,
        "proposal_sent_at": lead.proposal_sent_at.isoformat() if lead.proposal_sent_at else None,
        "handoff_required": lead.handoff_required,
        "handoff_reason": lead.handoff_reason,
        "lost_reason": lead.lost_reason,
        "internal_notes": lead.internal_notes,
        "review_status": lead.review_status,
        "testimonial_status": lead.testimonial_status,
        "referral_status": lead.referral_status,
        "next_followup_at": lead.next_followup_at.isoformat() if lead.next_followup_at else None,
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


@router.get("/review-queue")
async def review_queue(
    limit: int = 50,
    session: AsyncSession = Depends(get_async_session),
) -> list[dict]:
    limit = max(1, min(200, limit))
    rows = (
        (
            await session.execute(
                select(Lead)
                .where(
                    or_(
                        Lead.handoff_required.is_(True),
                        Lead.proposal_status == "requested",
                        Lead.proposal_status == "in_progress",
                        Lead.status == "reply_failed",
                        Lead.status == "pending_handoff",
                        Lead.status == "proposal_requested",
                    )
                )
                .order_by(desc(Lead.updated_at))
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": str(lead.id),
            "instagram_user_id": lead.instagram_user_id,
            "instagram_username": lead.instagram_username,
            "name": lead.name,
            "event_type": lead.event_type,
            "venue_city": lead.venue_city,
            "guest_count": lead.guest_count,
            "budget_min": lead.budget_min,
            "budget_max": lead.budget_max,
            "preferred_channel": lead.preferred_channel,
            "urgency_level": lead.urgency_level,
            "owner": lead.owner,
            "status": lead.status,
            "stage": lead.stage,
            "proposal_status": lead.proposal_status,
            "handoff_required": lead.handoff_required,
            "handoff_reason": lead.handoff_reason,
            "next_followup_at": lead.next_followup_at.isoformat() if lead.next_followup_at else None,
            "followup_state": lead.followup_state,
            "last_message_at": lead.last_message_at.isoformat() if lead.last_message_at else None,
            "updated_at": lead.updated_at.isoformat(),
        }
        for lead in rows
    ]


@router.get("/control-tower")
async def control_tower(
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    rows = (await session.execute(select(Lead).order_by(desc(Lead.updated_at)).limit(500))).scalars().all()

    def _lead_row(lead: Lead) -> dict:
        return {
            "id": str(lead.id),
            "instagram_username": lead.instagram_username,
            "name": lead.name,
            "event_type": lead.event_type,
            "venue_city": lead.venue_city,
            "status": lead.status,
            "proposal_status": lead.proposal_status,
            "handoff_required": lead.handoff_required,
            "urgency_level": lead.urgency_level,
            "owner": lead.owner,
            "updated_at": lead.updated_at.isoformat(),
        }

    review = [
        _lead_row(lead)
        for lead in rows
        if lead.handoff_required
        or lead.proposal_status in {"requested", "in_progress"}
        or lead.status in {"reply_failed", "pending_handoff", "proposal_requested"}
    ]
    recovery = [
        _lead_row(lead)
        for lead in rows
        if lead.status in {"reply_failed", "lost"} or lead.next_followup_at is not None
    ]
    priority = [
        _lead_row(lead)
        for lead in rows
        if lead.owner == "priority_queue" or lead.urgency_level == "high"
    ]

    return {
        "summary": {
            "total_leads": len(rows),
            "review_queue": len(review),
            "recovery_queue": len(recovery),
            "priority_queue": len(priority),
            "proposal_requested": sum(1 for lead in rows if lead.proposal_status == "requested"),
            "proposal_in_progress": sum(1 for lead in rows if lead.proposal_status == "in_progress"),
            "pending_handoff": sum(1 for lead in rows if lead.status == "pending_handoff"),
            "reply_failed": sum(1 for lead in rows if lead.status == "reply_failed"),
        },
        "priority_leads": priority[:10],
        "review_leads": review[:10],
        "recovery_leads": recovery[:10],
    }


@router.get("/action-list")
async def action_list(
    limit: int = 25,
    session: AsyncSession = Depends(get_async_session),
) -> list[dict]:
    limit = max(1, min(100, limit))
    rows = (await session.execute(select(Lead).order_by(desc(Lead.updated_at)).limit(500))).scalars().all()

    items = []
    for lead in rows:
        score = _lead_score(lead)
        next_action = _next_action_for_lead(lead)
        if next_action == "monitor":
            continue
        items.append(
            {
                "lead_id": str(lead.id),
                "instagram_username": lead.instagram_username,
                "name": lead.name,
                "event_type": lead.event_type,
                "venue_city": lead.venue_city,
                "status": lead.status,
                "proposal_status": lead.proposal_status,
                "owner": lead.owner,
                "urgency_level": lead.urgency_level,
                "score": score,
                "next_action": next_action,
                "suggested_followup_at": _suggested_followup_at(lead),
                "updated_at": lead.updated_at.isoformat(),
            }
        )

    items.sort(key=lambda item: (-item["score"], item["updated_at"]), reverse=False)
    return items[:limit]


@router.post("/leads/{lead_id}/mark-handoff-handled")
async def mark_handoff_handled(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")

    lead.handoff_required = False
    lead.handoff_reason = None
    if not lead.next_followup_at:
        lead.next_followup_at = _utcnow()
    if lead.status == "pending_handoff":
        lead.status = "active"
    await session.commit()
    return {
        "ok": True,
        "lead_id": str(lead.id),
        "status": lead.status,
        "next_followup_at": lead.next_followup_at.isoformat() if lead.next_followup_at else None,
    }


@router.post("/leads/{lead_id}/mark-proposal-sent")
async def mark_proposal_sent(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")

    lead.proposal_status = "sent"
    lead.proposal_sent_at = _utcnow()
    if not lead.next_followup_at:
        lead.next_followup_at = _utcnow()
    if lead.status == "proposal_requested":
        lead.status = "awaiting_user"
    await session.commit()
    return {
        "ok": True,
        "lead_id": str(lead.id),
        "proposal_status": lead.proposal_status,
        "proposal_sent_at": lead.proposal_sent_at.isoformat() if lead.proposal_sent_at else None,
        "next_followup_at": lead.next_followup_at.isoformat() if lead.next_followup_at else None,
    }


@router.post("/leads/{lead_id}/mark-proposal-in-progress")
async def mark_proposal_in_progress(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")

    lead.proposal_status = "in_progress"
    if lead.status == "proposal_requested":
        lead.status = "active"
    await session.commit()
    return {
        "ok": True,
        "lead_id": str(lead.id),
        "proposal_status": lead.proposal_status,
        "status": lead.status,
    }


@router.get("/leads/{lead_id}/sales-brief")
async def get_sales_brief(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")

    recent_messages = (
        (
            await session.execute(
                select(Message).where(Message.lead_id == lead_id).order_by(desc(Message.created_at)).limit(12)
            )
        )
        .scalars()
        .all()
    )
    recent_messages = list(reversed(recent_messages))

    summary = {
        "lead_id": str(lead.id),
        "name": lead.name,
        "instagram_username": lead.instagram_username,
        "event_type": lead.event_type,
        "event_date": lead.event_date.isoformat() if lead.event_date else None,
        "event_date_text": lead.event_date_text,
        "guest_count": lead.guest_count,
        "venue_city": lead.venue_city,
        "budget_min": lead.budget_min,
        "budget_max": lead.budget_max,
        "budget_currency": lead.budget_currency,
        "project_value_estimate": lead.project_value_estimate,
        "preferred_channel": lead.preferred_channel,
        "urgency_level": lead.urgency_level,
        "proposal_status": lead.proposal_status,
        "handoff_required": lead.handoff_required,
        "handoff_reason": lead.handoff_reason,
        "owner": lead.owner,
        "status": lead.status,
        "stage": lead.stage,
    }

    missing = []
    for field, value in [
        ("event_type", lead.event_type),
        ("date", lead.event_date or lead.event_date_text),
        ("guest_count", lead.guest_count),
        ("venue_city", lead.venue_city),
        ("budget", lead.budget_min or lead.budget_max),
        ("name", lead.name),
    ]:
        if not value:
            missing.append(field)

    recommendation = "Continue qualification in DM."
    if lead.handoff_required:
        recommendation = "Human handoff recommended. Continue on WhatsApp or phone."
    elif lead.proposal_status == "requested":
        recommendation = "Prepare a tailored quote or proposal summary next."
    elif lead.status == "reply_failed":
        recommendation = "Reply delivery failed. Review channel setup before next outreach."

    return {
        "lead": summary,
        "missing_fields": missing,
        "recommended_next_step": recommendation,
        "internal_notes": lead.internal_notes,
        "recent_messages": [
            {
                "direction": m.direction,
                "text": m.text,
                "created_at": m.created_at.isoformat(),
            }
            for m in recent_messages
        ],
    }


@router.get("/leads/{lead_id}/operator-suggestions")
async def get_operator_suggestions(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")

    event_label = lead.event_type or "event"
    date_label = lead.event_date.isoformat() if lead.event_date else (lead.event_date_text or "your preferred date")
    city_label = lead.venue_city or "the venue area"
    guest_label = str(lead.guest_count) if lead.guest_count else "your guest count"
    budget_label = _budget_label(lead)

    handoff_message = (
        f"Of course. I’d be happy to continue personally. "
        f"If you send {city_label}, {date_label}, and {guest_label}, we can guide the next step quickly without overcomplicating it."
    )
    quote_message = (
        f"Thank you. Based on the {event_label}, we can prepare a tailored starting direction. "
        f"To shape it properly, we would confirm the city, guest count, and budget range first, then narrow the right scope for you."
    )
    proposal_outline = [
        f"Event type: {event_label}",
        f"Date: {date_label}",
        f"City / venue area: {city_label}",
        f"Guest count: {guest_label}",
        f"Budget signal: {budget_label}",
        f"Urgency: {lead.urgency_level or 'medium'}",
        f"Preferred channel: {lead.preferred_channel or 'instagram'}",
    ]

    next_action = "continue_dm"
    if lead.handoff_required:
        next_action = "handoff"
    elif lead.proposal_status in {"requested", "in_progress"}:
        next_action = "prepare_proposal"

    return {
        "next_action": next_action,
        "handoff_message": handoff_message,
        "quote_message": quote_message,
        "proposal_outline": proposal_outline,
    }


@router.get("/leads/{lead_id}/proposal-draft")
async def get_proposal_draft(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")
    return build_proposal_draft(lead)


@router.get("/leads/{lead_id}/execution-packet")
async def get_execution_packet(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")

    recent_messages = (
        (
            await session.execute(
                select(Message).where(Message.lead_id == lead_id).order_by(desc(Message.created_at)).limit(12)
            )
        )
        .scalars()
        .all()
    )
    recent_messages = list(reversed(recent_messages))

    event_label = lead.event_type or "event"
    date_label = lead.event_date.isoformat() if lead.event_date else (lead.event_date_text or "your preferred date")
    city_label = lead.venue_city or "the venue area"
    guest_label = str(lead.guest_count) if lead.guest_count else "your guest count"
    budget_label = _budget_label(lead)

    missing = []
    for field, value in [
        ("event_type", lead.event_type),
        ("date", lead.event_date or lead.event_date_text),
        ("guest_count", lead.guest_count),
        ("venue_city", lead.venue_city),
        ("budget", lead.budget_min or lead.budget_max),
        ("name", lead.name),
    ]:
        if not value:
            missing.append(field)

    next_action = "continue_dm"
    if lead.handoff_required:
        next_action = "handoff"
    elif lead.proposal_status in {"requested", "in_progress"}:
        next_action = "prepare_proposal"
    elif lead.status == "reply_failed":
        next_action = "fix_delivery_then_retry"
    elif lead.status == "lost":
        next_action = "soft_reactivation"

    proposal = build_proposal_draft(lead)
    score = _lead_score(lead)

    return {
        "lead": {
            "id": str(lead.id),
            "instagram_username": lead.instagram_username,
            "name": lead.name,
            "event_type": event_label,
            "date": date_label,
            "venue_city": city_label,
            "guest_count": guest_label,
            "budget_signal": budget_label,
            "preferred_channel": lead.preferred_channel or "instagram",
            "urgency_level": lead.urgency_level or "medium",
            "owner": lead.owner,
            "status": lead.status,
            "proposal_status": lead.proposal_status,
            "handoff_required": lead.handoff_required,
            "score": score,
        },
        "missing_fields": missing,
        "next_action": next_action,
        "suggested_followup_at": _suggested_followup_at(lead),
        "operator_messages": {
            "handoff_message": (
                f"Of course. I’d be happy to continue personally. "
                f"If you send {city_label}, {date_label}, and {guest_label}, we can guide the next step quickly."
            ),
            "quote_message": (
                f"Thank you. Based on the {event_label}, we can prepare a tailored starting direction. "
                f"To shape it properly, we would confirm the city, guest count, and budget range first."
            ),
            "recovery_message": (
                "Just checking in gently in case the timing has shifted. "
                "If the plans are still open, I’d be happy to guide the next step."
            ),
        },
        "proposal": proposal.get("proposal"),
        "recent_messages": [
            {
                "direction": m.direction,
                "text": m.text,
                "created_at": m.created_at.isoformat(),
            }
            for m in recent_messages
        ],
    }


@router.get("/leads/{lead_id}/scorecard")
async def get_scorecard(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")

    breakdown = _lead_score_breakdown(lead)
    return {
        "lead_id": str(lead.id),
        "score": sum(item["points"] for item in breakdown),
        "breakdown": breakdown,
        "next_action": _next_action_for_lead(lead),
        "suggested_followup_at": _suggested_followup_at(lead),
    }


@router.post("/leads/{lead_id}/set-owner")
async def set_owner(
    lead_id: uuid.UUID,
    owner: str,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")
    lead.owner = owner.strip() or None
    await session.commit()
    return {"ok": True, "lead_id": str(lead.id), "owner": lead.owner}


@router.post("/leads/{lead_id}/set-notes")
async def set_notes(
    lead_id: uuid.UUID,
    notes: str,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")
    lead.internal_notes = notes.strip() or None
    await session.commit()
    return {"ok": True, "lead_id": str(lead.id), "internal_notes": lead.internal_notes}


@router.post("/leads/{lead_id}/mark-won")
async def mark_won(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")
    lead.status = "won"
    lead.lost_reason = None
    lead.next_followup_at = None
    await session.commit()
    return {"ok": True, "lead_id": str(lead.id), "status": lead.status}


@router.post("/leads/{lead_id}/mark-lost")
async def mark_lost(
    lead_id: uuid.UUID,
    reason: str,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")
    lead.status = "lost"
    lead.lost_reason = reason.strip() or "not_specified"
    if not lead.next_followup_at:
        lead.next_followup_at = _utcnow()
    await session.commit()
    return {
        "ok": True,
        "lead_id": str(lead.id),
        "status": lead.status,
        "lost_reason": lead.lost_reason,
        "next_followup_at": lead.next_followup_at.isoformat() if lead.next_followup_at else None,
    }


@router.post("/leads/{lead_id}/set-next-followup")
async def set_next_followup(
    lead_id: uuid.UUID,
    iso_datetime: str,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")
    try:
        lead.next_followup_at = datetime.fromisoformat(iso_datetime.replace("Z", "+00:00"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"invalid_datetime:{exc}") from exc
    await session.commit()
    return {
        "ok": True,
        "lead_id": str(lead.id),
        "next_followup_at": lead.next_followup_at.isoformat() if lead.next_followup_at else None,
    }


def _budget_label(lead: Lead) -> str:
    if lead.budget_min and lead.budget_max:
        return f"{lead.budget_min}-{lead.budget_max} {lead.budget_currency or ''}".strip()
    if lead.budget_max:
        return f"up to {lead.budget_max} {lead.budget_currency or ''}".strip()
    if lead.budget_min:
        return f"from {lead.budget_min} {lead.budget_currency or ''}".strip()
    if lead.project_value_estimate:
        return f"estimated around {lead.project_value_estimate}"
    return "not confirmed yet"


def _lead_score(lead: Lead) -> int:
    return sum(item["points"] for item in _lead_score_breakdown(lead))


def _lead_score_breakdown(lead: Lead) -> list[dict]:
    items: list[dict] = []
    if lead.handoff_required:
        items.append({"reason": "human handoff requested", "points": 35})
    if lead.proposal_status == "requested":
        items.append({"reason": "proposal requested", "points": 30})
    if lead.proposal_status == "in_progress":
        items.append({"reason": "proposal in progress", "points": 20})
    if lead.urgency_level == "high":
        items.append({"reason": "high urgency", "points": 20})
    if lead.preferred_channel == "whatsapp":
        items.append({"reason": "prefers WhatsApp", "points": 10})
    if (lead.budget_max or 0) >= 150000:
        items.append({"reason": "high budget signal", "points": 20})
    elif (lead.budget_max or 0) >= 75000 or (lead.budget_min or 0) >= 75000:
        items.append({"reason": "mid-high budget signal", "points": 12})
    if (lead.guest_count or 0) >= 120:
        items.append({"reason": "large guest count", "points": 12})
    elif (lead.guest_count or 0) >= 50:
        items.append({"reason": "qualified guest count", "points": 8})
    if lead.status == "reply_failed":
        items.append({"reason": "reply delivery issue", "points": 18})
    if lead.next_followup_at is not None:
        items.append({"reason": "scheduled follow-up exists", "points": 8})
    if not items:
        items.append({"reason": "general monitoring", "points": 5})
    return items


def _next_action_for_lead(lead: Lead) -> str:
    if lead.status == "won":
        return "handover_to_delivery"
    if lead.status == "lost":
        return "soft_reactivation"
    if lead.status == "reply_failed":
        return "fix_delivery_then_retry"
    if lead.handoff_required:
        return "human_handoff"
    if lead.proposal_status == "requested":
        return "prepare_proposal"
    if lead.proposal_status == "in_progress":
        return "send_proposal"
    if lead.next_followup_at is not None:
        return "follow_up"
    if lead.owner == "priority_queue" or lead.urgency_level == "high":
        return "priority_outreach"
    if lead.status == "awaiting_user":
        return "wait_or_follow_up"
    return "monitor"


def _suggested_followup_at(lead: Lead) -> str | None:
    if lead.next_followup_at:
        return lead.next_followup_at.isoformat()
    if lead.status in {"proposal_requested", "pending_handoff"}:
        return "within_2_hours"
    if lead.proposal_status == "in_progress":
        return "today"
    if lead.status == "reply_failed":
        return "immediately_after_fix"
    if lead.urgency_level == "high":
        return "within_1_hour"
    if lead.status == "awaiting_user":
        return "within_24_hours_if_silent"
    return None


@router.get("/recovery-queue")
async def recovery_queue(
    limit: int = 50,
    session: AsyncSession = Depends(get_async_session),
) -> list[dict]:
    limit = max(1, min(200, limit))
    rows = (
        (
            await session.execute(
                select(Lead)
                .where(
                    or_(
                        Lead.status == "reply_failed",
                        Lead.status == "lost",
                        Lead.next_followup_at.is_not(None),
                    )
                )
                .order_by(desc(Lead.updated_at))
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": str(lead.id),
            "instagram_username": lead.instagram_username,
            "name": lead.name,
            "event_type": lead.event_type,
            "venue_city": lead.venue_city,
            "status": lead.status,
            "lost_reason": lead.lost_reason,
            "next_followup_at": lead.next_followup_at.isoformat() if lead.next_followup_at else None,
            "preferred_channel": lead.preferred_channel,
            "proposal_status": lead.proposal_status,
            "updated_at": lead.updated_at.isoformat(),
        }
        for lead in rows
    ]


@router.get("/leads/{lead_id}/recovery-suggestions")
async def get_recovery_suggestions(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")

    if lead.status == "reply_failed":
        next_action = "fix_delivery_then_retry"
        message = "We had a delivery issue on our side. If you'd still like, I can continue with the next step here and keep it simple."
    elif lead.status == "lost":
        next_action = "soft_reactivation"
        message = (
            "Just checking in gently in case the timing has shifted. "
            "If the plans are still open, I’d be happy to guide the next step in a simple, tailored way."
        )
    elif lead.next_followup_at:
        next_action = "scheduled_followup"
        message = (
            "Just following up in case you'd still like me to prepare the next step. "
            "If you share the venue area and guest count, I can narrow the direction quickly and make the next step more concrete."
        )
    else:
        next_action = "monitor"
        message = "No immediate recovery action is needed."

    return {
        "next_action": next_action,
        "recommended_message": message,
        "lost_reason": lead.lost_reason,
        "next_followup_at": lead.next_followup_at.isoformat() if lead.next_followup_at else None,
    }


@router.get("/leads/{lead_id}/trust-pack")
async def get_trust_pack(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")

    event_label = lead.event_type or "event"
    testimonial_ask = (
        f"Thank you again for trusting Elova with your {event_label}. "
        f"If you’re comfortable, I’d love to ask for a short testimonial about the overall experience and atmosphere."
    )
    review_ask = (
        "If the experience felt meaningful and smooth, a short Google review would genuinely help future clients feel more confident reaching out."
    )
    referral_ask = (
        "And if someone in your circle is planning a celebration with a similar feel, I’d be very happy to help them as well."
    )
    return {
        "testimonial_ask": testimonial_ask,
        "review_ask": review_ask,
        "referral_ask": referral_ask,
        "statuses": {
            "review_status": lead.review_status,
            "testimonial_status": lead.testimonial_status,
            "referral_status": lead.referral_status,
        },
    }


@router.get("/trust-queue")
async def trust_queue(
    limit: int = 50,
    session: AsyncSession = Depends(get_async_session),
) -> list[dict]:
    limit = max(1, min(200, limit))
    rows = (
        (
            await session.execute(
                select(Lead)
                .where(Lead.status == "won")
                .order_by(desc(Lead.updated_at))
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": str(lead.id),
            "instagram_username": lead.instagram_username,
            "name": lead.name,
            "event_type": lead.event_type,
            "review_status": lead.review_status,
            "testimonial_status": lead.testimonial_status,
            "referral_status": lead.referral_status,
            "updated_at": lead.updated_at.isoformat(),
        }
        for lead in rows
        if not (
            lead.review_status == "collected"
            and lead.testimonial_status == "collected"
            and lead.referral_status == "collected"
        )
    ]


@router.post("/leads/{lead_id}/mark-review-requested")
async def mark_review_requested(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")
    lead.review_status = "requested"
    await session.commit()
    return {"ok": True, "lead_id": str(lead.id), "review_status": lead.review_status}


@router.post("/leads/{lead_id}/mark-testimonial-requested")
async def mark_testimonial_requested(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")
    lead.testimonial_status = "requested"
    await session.commit()
    return {"ok": True, "lead_id": str(lead.id), "testimonial_status": lead.testimonial_status}


@router.post("/leads/{lead_id}/mark-referral-requested")
async def mark_referral_requested(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")
    lead.referral_status = "requested"
    await session.commit()
    return {"ok": True, "lead_id": str(lead.id), "referral_status": lead.referral_status}


@router.post("/leads/{lead_id}/mark-review-collected")
async def mark_review_collected(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")
    lead.review_status = "collected"
    await session.commit()
    return {"ok": True, "lead_id": str(lead.id), "review_status": lead.review_status}


@router.post("/leads/{lead_id}/mark-testimonial-collected")
async def mark_testimonial_collected(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")
    lead.testimonial_status = "collected"
    await session.commit()
    return {"ok": True, "lead_id": str(lead.id), "testimonial_status": lead.testimonial_status}


@router.post("/leads/{lead_id}/mark-referral-collected")
async def mark_referral_collected(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")
    lead.referral_status = "collected"
    await session.commit()
    return {"ok": True, "lead_id": str(lead.id), "referral_status": lead.referral_status}


@router.get("/leads/{lead_id}/close-plan")
async def get_close_plan(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")

    event_label = lead.event_type or "event"

    if lead.status == "won":
        next_action = "collect_review_and_referral"
        primary_message = (
            f"Thank you again for trusting Elova with your {event_label}. "
            f"The next best step is to collect a short testimonial and, if appropriate, a Google review."
        )
    elif lead.proposal_status == "sent":
        next_action = "follow_up_on_proposal"
        primary_message = (
            "Just checking in on the proposal in case it would help to refine the scope or walk through the direction together."
        )
    elif lead.proposal_status in {"requested", "in_progress"}:
        next_action = "move_to_sent_proposal"
        primary_message = (
            "This lead is already in proposal motion. The highest-value next step is to send the clearest possible version quickly."
        )
    elif lead.handoff_required:
        next_action = "complete_handoff"
        primary_message = (
            "This lead asked for a person. The highest-value move is a clean, personal handoff with very little friction."
        )
    elif lead.status == "lost":
        next_action = "reactivate_later"
        primary_message = (
            "This lead is marked lost. Keep the tone light and leave the door open for timing, budget, or scope changes later."
        )
    else:
        next_action = "continue_qualification"
        primary_message = "The next step is to clarify the missing basics and move toward a proposal or handoff."

    return {
        "lead_id": str(lead.id),
        "status": lead.status,
        "proposal_status": lead.proposal_status,
        "next_action": next_action,
        "primary_message": primary_message,
        "suggested_followup_at": _suggested_followup_at(lead),
        "trust_pack_available": lead.status == "won",
    }


@router.get("/leads/{lead_id}/close-plan")
async def get_close_plan(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    lead = (await session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="not_found")

    event_label = lead.event_type or "event"

    if lead.status == "won":
        next_action = "collect_review_and_referral"
        primary_message = (
            f"Thank you again for trusting Elova with your {event_label}. "
            f"The next best step is to collect a short testimonial and, if appropriate, a Google review."
        )
    elif lead.proposal_status == "sent":
        next_action = "follow_up_on_proposal"
        primary_message = (
            "Just checking in on the proposal in case it would help to refine the scope or walk through the direction together."
        )
    elif lead.proposal_status in {"requested", "in_progress"}:
        next_action = "move_to_sent_proposal"
        primary_message = (
            "This lead is already in proposal motion. The highest-value next step is to send the clearest possible version quickly."
        )
    elif lead.handoff_required:
        next_action = "complete_handoff"
        primary_message = (
            "This lead asked for a person. The highest-value move is a clean, personal handoff with very little friction."
        )
    elif lead.status == "lost":
        next_action = "reactivate_later"
        primary_message = (
            "This lead is marked lost. Keep the tone light and leave the door open for timing, budget, or scope changes later."
        )
    else:
        next_action = "continue_qualification"
        primary_message = "The next step is to clarify the missing basics and move toward a proposal or handoff."

    return {
        "lead_id": str(lead.id),
        "status": lead.status,
        "proposal_status": lead.proposal_status,
        "next_action": next_action,
        "primary_message": primary_message,
        "suggested_followup_at": _suggested_followup_at(lead),
        "trust_pack_available": lead.status == "won",
    }


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
