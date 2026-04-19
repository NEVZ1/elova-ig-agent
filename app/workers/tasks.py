from __future__ import annotations

from datetime import datetime, timezone

from app.workers.celery_app import celery
from sqlalchemy import select

from app.conversation_engine.engine import ConversationEngine
from app.conversion_engine.policy import ConversionPolicy
from app.core.logging import logger
from app.crm_memory.memory import MemoryService
from app.db.models import Lead, Message
from app.db.session import SyncSessionLocal
from app.db.models import ConversationSummary
from app.instagram.factory import get_instagram_client
from app.instagram.types import OutboundMessage
from app.lead_engine.extractor import LeadExtractor
from app.core.config import settings


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@celery.task(name="app.workers.tasks.process_incoming_dm")
def process_incoming_dm(event: dict) -> dict:
    """
    Inbound DM processing pipeline (worker):
    - upsert lead
    - store inbound message
    - generate and send reply (placeholder; upgraded in conversation_engine)
    - store outbound message
    """
    now = _utcnow()
    instagram_user_id = str(event.get("instagram_user_id") or "")
    if not instagram_user_id:
        return {"ok": False, "error": "missing_instagram_user_id"}

    inbound_text = (event.get("text") or "").strip()
    client = get_instagram_client()
    policy = ConversionPolicy()
    memory = MemoryService()
    try:
        convo: ConversationEngine | None = ConversationEngine()
        extractor: LeadExtractor | None = None if settings.llm_unified_mode else LeadExtractor()
    except Exception as exc:  # noqa: BLE001
        logger.warning("llm_disabled", err=str(exc))
        extractor = None
        convo = None

    with SyncSessionLocal() as session:
        mid = event.get("instagram_message_id")
        if mid:
            existing = session.execute(select(Message.id).where(Message.instagram_message_id == mid)).scalar_one_or_none()
            if existing:
                return {"ok": True, "deduped": True}

        lead = session.execute(select(Lead).where(Lead.instagram_user_id == instagram_user_id)).scalar_one_or_none()
        if not lead:
            lead = Lead(instagram_user_id=instagram_user_id, instagram_username=event.get("instagram_username"))
            session.add(lead)
            session.flush()
        elif event.get("instagram_username") and not lead.instagram_username:
            lead.instagram_username = event.get("instagram_username")

        lead.status = "active"
        lead.last_message_at = now
        lead.last_inbound_at = now
        lead.followup_anchor_at = None
        lead.followup_state = "none"

        session.add(
            Message(
                lead_id=lead.id,
                direction="inbound",
                channel="instagram",
                instagram_message_id=event.get("instagram_message_id"),
                text=inbound_text,
                raw_payload=event.get("raw"),
            )
        )

        recent_messages = memory.get_recent_messages(session, lead.id, limit=14)

        # Lead extraction (best-effort; non-blocking for reply) when unified is off.
        if extractor:
            _apply_lead_update_from_extractor(lead, extractor, recent_messages)

        decision = policy.decide(lead, inbound_text)
        if decision.goal == "stop":
            lead.opted_out = True
            lead.status = "lost"
            lead.stage = "followup"
            session.commit()
            return {"ok": True, "lead_id": str(lead.id), "stopped": True}

        lead.stage = decision.stage
        lead.status = decision.status

        summary = memory.get_summary(session, lead.id)
        summary_text = summary.summary_text if summary else None

        if convo and settings.llm_unified_mode:
            unified = convo.generate_unified(
                lead=lead,
                recent_messages=recent_messages,
                summary_text=summary_text,
                goal=decision.goal,
                missing_fields=decision.missing_fields,
            )
            _apply_lead_update_from_unified(lead, unified)
            _upsert_summary_from_unified(session, lead, summary, unified)
            reply = unified.reply_text
        elif convo:
            plan = convo.generate_reply(
                lead=lead,
                recent_messages=recent_messages,
                summary_text=summary_text,
                goal=decision.goal,
                missing_fields=decision.missing_fields,
            )
            memory.upsert_summary(session, lead, recent_messages)
            reply = plan.reply_text
        else:
            reply = _fallback_reply(decision.missing_fields, decision.goal)

        try:
            client.send_text_sync(OutboundMessage(recipient_id=instagram_user_id, text=reply))
            lead.status = "awaiting_user"
            lead.last_outbound_at = now
            lead.last_message_at = now
            lead.followup_state = "none"
            lead.followup_anchor_at = now

            session.add(
                Message(
                    lead_id=lead.id,
                    direction="outbound",
                    channel="instagram",
                    instagram_message_id=None,
                    text=reply,
                    raw_payload=None,
                )
            )
            session.commit()
            logger.info("dm_replied", instagram_user_id=instagram_user_id, lead_id=str(lead.id))
            return {"ok": True, "lead_id": str(lead.id)}
        except Exception as exc:  # noqa: BLE001
            session.commit()
            logger.error("dm_reply_failed", instagram_user_id=instagram_user_id, err=str(exc))
            return {"ok": False, "lead_id": str(lead.id), "error": "send_failed"}


def _fallback_reply(missing: list[str], goal: str) -> str:
    if goal == "price_inquiry":
        return "Pricing is tailored to venue and scope. May I ask the date?"
    if goal == "convert":
        return "Of course. What date are you considering?"
    if "date" in missing:
        return "That sounds like a beautiful event. What date are you considering?"
    if "guest_count" in missing:
        return "Lovely. About how many guests?"
    if "event_type" in missing:
        return "Lovely. What type of event is it?"
    if "budget" in missing:
        return "To tailor this properly, what budget range are you working with?"
    return "Thank you. Would you like a quick call, or should we continue here?"


def _apply_lead_update_from_extractor(lead: Lead, extractor: LeadExtractor, recent_messages: list[dict]) -> None:
    try:
        known = {
            "name": lead.name,
            "event_type": lead.event_type,
            "event_date": lead.event_date.isoformat() if lead.event_date else None,
            "event_date_text": lead.event_date_text,
            "guest_count": lead.guest_count,
            "budget_min": lead.budget_min,
            "budget_max": lead.budget_max,
            "budget_currency": lead.budget_currency,
            "source": lead.source,
        }
        update = extractor.extract(recent_messages=recent_messages, known=known)
        if update.name:
            lead.name = lead.name or update.name
        if update.event_type:
            lead.event_type = lead.event_type or update.event_type
        if update.event_date:
            lead.event_date = lead.event_date or update.event_date
        if update.event_date_text:
            lead.event_date_text = lead.event_date_text or update.event_date_text
        if update.guest_count:
            lead.guest_count = lead.guest_count or update.guest_count
        if update.budget_min is not None:
            lead.budget_min = lead.budget_min or update.budget_min
        if update.budget_max is not None:
            lead.budget_max = lead.budget_max or update.budget_max
        if update.budget_currency:
            lead.budget_currency = lead.budget_currency or update.budget_currency
        if update.source:
            lead.source = update.source
    except Exception as exc:  # noqa: BLE001
        logger.warning("lead_extract_failed", err=str(exc))


def _apply_lead_update_from_unified(lead: Lead, unified) -> None:  # noqa: ANN001
    if unified.name:
        lead.name = lead.name or unified.name
    if unified.event_type:
        lead.event_type = lead.event_type or unified.event_type
    if unified.event_date:
        lead.event_date = lead.event_date or unified.event_date
    if unified.event_date_text:
        lead.event_date_text = lead.event_date_text or unified.event_date_text
    if unified.guest_count:
        lead.guest_count = lead.guest_count or unified.guest_count
    if unified.budget_min is not None:
        lead.budget_min = lead.budget_min or unified.budget_min
    if unified.budget_max is not None:
        lead.budget_max = lead.budget_max or unified.budget_max
    if unified.budget_currency:
        lead.budget_currency = lead.budget_currency or unified.budget_currency


def _upsert_summary_from_unified(session, lead: Lead, existing, unified) -> None:  # noqa: ANN001
    if not (unified.summary_text or unified.key_facts):
        return
    summary = existing
    if not summary:
        summary = ConversationSummary(
            lead_id=lead.id,
            summary_text=None,
            key_facts=None,
            last_message_id=None,
        )
        session.add(summary)
        session.flush()
    if unified.summary_text:
        summary.summary_text = unified.summary_text
    if unified.key_facts is not None:
        summary.key_facts = unified.key_facts
