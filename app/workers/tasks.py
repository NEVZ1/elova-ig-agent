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


@celery.task(name="app.workers.tasks.ping")
def ping() -> dict:
    logger.info("worker_ping")
    return {"ok": True}


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
    action_taken = "no_action"
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
            try:
                unified = convo.generate_unified(
                    lead=lead,
                    recent_messages=recent_messages,
                    summary_text=summary_text,
                    goal=decision.goal,
                    missing_fields=decision.missing_fields,
                )
                _apply_lead_update_from_unified(lead, unified)
                lead.stage = unified.stage or lead.stage
                _apply_operational_signals(lead, inbound_text, decision.goal, unified.action)
                action_taken = unified.action
                _upsert_summary_from_unified(session, lead, summary, unified)
                reply = unified.reply_text
            except Exception as exc:  # noqa: BLE001
                # If LLM is misconfigured or out of quota, we still want the bot to respond
                # and keep the lead moving. Fall back to deterministic prompts.
                logger.error("llm_generate_failed", provider=settings.llm_provider, err=str(exc))
                reply = _fallback_reply(decision.missing_fields, decision.goal)
        elif convo:
            plan = convo.generate_reply(
                lead=lead,
                recent_messages=recent_messages,
                summary_text=summary_text,
                goal=decision.goal,
                missing_fields=decision.missing_fields,
            )
            memory.upsert_summary(session, lead, recent_messages)
            lead.stage = plan.stage or lead.stage
            _apply_operational_signals(lead, inbound_text, decision.goal, plan.action)
            action_taken = plan.action
            reply = plan.reply_text
        else:
            reply = _fallback_reply(decision.missing_fields, decision.goal)

        try:
            client.send_text_sync(OutboundMessage(recipient_id=instagram_user_id, text=reply))
            lead.status = _next_status_after_reply(lead, action_taken)
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
            lead.status = "reply_failed"
            lead.last_message_at = now
            session.add(
                Message(
                    lead_id=lead.id,
                    direction="system",
                    channel="instagram",
                    instagram_message_id=None,
                    text="Outbound Instagram reply failed.",
                    raw_payload={"type": "send_error", "error": str(exc)},
                )
            )
            session.commit()
            logger.error("dm_reply_failed", instagram_user_id=instagram_user_id, lead_id=str(lead.id), err=str(exc))
            return {"ok": False, "lead_id": str(lead.id), "error": "send_failed"}


def _fallback_reply(missing: list[str], goal: str) -> str:
    if goal == "handoff":
        return "Of course. WhatsApp works best for quick details, and I can have our team continue there."
    if goal == "quote":
        return "I can prepare a tailored starting direction. May I ask the city and guest count first?"
    if goal == "price_inquiry":
        return "Pricing is tailored to venue and scope. May I ask the date first?"
    if goal == "convert":
        return "Of course. What date are you considering?"
    if "date" in missing:
        return "That sounds like a beautiful event. What date are you considering?"
    if "guest_count" in missing:
        return "Lovely. About how many guests?"
    if "venue_city" in missing:
        return "Lovely. Which city or area is the event in?"
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
            "venue_city": lead.venue_city,
            "budget_min": lead.budget_min,
            "budget_max": lead.budget_max,
            "budget_currency": lead.budget_currency,
            "project_value_estimate": lead.project_value_estimate,
            "preferred_channel": lead.preferred_channel,
            "urgency_level": lead.urgency_level,
            "handoff_required": lead.handoff_required,
            "handoff_reason": lead.handoff_reason,
            "proposal_status": lead.proposal_status,
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
        if update.venue_city:
            lead.venue_city = lead.venue_city or update.venue_city
        if update.budget_min is not None:
            lead.budget_min = lead.budget_min or update.budget_min
        if update.budget_max is not None:
            lead.budget_max = lead.budget_max or update.budget_max
        if update.budget_currency:
            lead.budget_currency = lead.budget_currency or update.budget_currency
        if update.project_value_estimate is not None:
            lead.project_value_estimate = lead.project_value_estimate or update.project_value_estimate
        if update.preferred_channel:
            lead.preferred_channel = lead.preferred_channel or update.preferred_channel
        if update.urgency_level:
            lead.urgency_level = lead.urgency_level or update.urgency_level
        if update.handoff_required is not None:
            lead.handoff_required = lead.handoff_required or update.handoff_required
        if update.handoff_reason:
            lead.handoff_reason = lead.handoff_reason or update.handoff_reason
        if update.proposal_status:
            lead.proposal_status = update.proposal_status if lead.proposal_status == "none" else lead.proposal_status
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
    if unified.venue_city:
        lead.venue_city = lead.venue_city or unified.venue_city
    if unified.budget_min is not None:
        lead.budget_min = lead.budget_min or unified.budget_min
    if unified.budget_max is not None:
        lead.budget_max = lead.budget_max or unified.budget_max
    if unified.budget_currency:
        lead.budget_currency = lead.budget_currency or unified.budget_currency
    if unified.project_value_estimate is not None:
        lead.project_value_estimate = lead.project_value_estimate or unified.project_value_estimate
    if unified.preferred_channel:
        lead.preferred_channel = lead.preferred_channel or unified.preferred_channel
    if unified.urgency_level:
        lead.urgency_level = lead.urgency_level or unified.urgency_level
    if unified.handoff_required is not None:
        lead.handoff_required = lead.handoff_required or unified.handoff_required
    if unified.handoff_reason:
        lead.handoff_reason = lead.handoff_reason or unified.handoff_reason
    if unified.proposal_status:
        lead.proposal_status = unified.proposal_status if lead.proposal_status == "none" else lead.proposal_status


def _apply_operational_signals(lead: Lead, inbound_text: str, goal: str, action: str) -> None:
    text = (inbound_text or "").lower()
    if any(k in text for k in ["whatsapp", "phone", "call me", "ara", "numara"]):
        lead.preferred_channel = lead.preferred_channel or "whatsapp"
    elif any(k in text for k in ["book", "booking", "consultation", "consult"]):
        lead.preferred_channel = lead.preferred_channel or "booking"

    if any(k in text for k in ["urgent", "asap", "today", "tomorrow", "acil", "hemen"]):
        lead.urgency_level = lead.urgency_level or "high"
    elif not lead.urgency_level:
        lead.urgency_level = "medium"

    if goal in {"handoff", "quote"} or action in {"human_handoff", "request_quote"}:
        if lead.proposal_status == "none" and goal == "quote":
            lead.proposal_status = "requested"
        if goal == "handoff" or action == "human_handoff":
            lead.handoff_required = True
            lead.handoff_reason = lead.handoff_reason or "Explicit request for human support."
            lead.owner = lead.owner or "sales_queue"

    if not lead.owner and _is_priority_lead(lead):
        lead.owner = "priority_queue"

    if lead.project_value_estimate is None:
        lead.project_value_estimate = _estimate_project_value(lead)


def _next_status_after_reply(lead: Lead, action: str) -> str:
    if lead.handoff_required or action == "human_handoff":
        return "pending_handoff"
    if lead.proposal_status == "requested" or action == "request_quote":
        return "proposal_requested"
    return "awaiting_user"


def _is_priority_lead(lead: Lead) -> bool:
    if lead.urgency_level == "high":
        return True
    if (lead.budget_max or 0) >= 150000:
        return True
    if (lead.guest_count or 0) >= 120:
        return True
    return False


def _estimate_project_value(lead: Lead) -> int | None:
    if lead.budget_max:
        return lead.budget_max
    if lead.budget_min:
        return lead.budget_min
    if lead.guest_count:
        if lead.guest_count >= 150:
            return 200000
        if lead.guest_count >= 80:
            return 120000
        if lead.guest_count >= 40:
            return 70000
        return 40000
    return None


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
