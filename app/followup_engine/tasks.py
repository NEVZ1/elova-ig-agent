from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.workers.celery_app import celery
from sqlalchemy import and_, select

from app.core.logging import logger
from app.db.models import Lead, Message
from app.db.session import SyncSessionLocal
from app.followup_engine.templates import final_followup, soft_nudge
from app.instagram.factory import get_instagram_client
from app.instagram.types import OutboundMessage


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@celery.task(name="app.followup_engine.tasks.send_due_followups")
def send_due_followups() -> dict:
    """
    Follow-up automation:
    - 2 hours after last outbound (if no inbound since): soft nudge
    - 24 hours after last outbound (if still no inbound): final follow-up
    """
    now = _utcnow()
    nudge_cutoff = now - timedelta(hours=2)
    final_cutoff = now - timedelta(hours=24)

    sent = 0
    client = get_instagram_client()

    with SyncSessionLocal() as session:
        leads = (
            session.execute(
                select(Lead).where(
                    and_(
                        Lead.opted_out.is_(False),
                        Lead.status == "awaiting_user",
                        Lead.followup_anchor_at.is_not(None),
                        Lead.last_inbound_at.is_not(None),
                        Lead.last_inbound_at <= Lead.last_outbound_at,
                        Lead.followup_state.in_(["none", "nudge_sent"]),
                    )
                )
            )
            .scalars()
            .all()
        )

        for lead in leads:
            if lead.followup_state == "none" and lead.followup_anchor_at and lead.followup_anchor_at <= nudge_cutoff:
                text = soft_nudge()
                _send_followup_sync(client, lead.instagram_user_id, text)
                lead.followup_state = "nudge_sent"
                lead.stage = "followup"
                lead.last_outbound_at = now
                lead.last_message_at = now
                session.add(Message(lead_id=lead.id, direction="outbound", channel="instagram", text=text, raw_payload={"type": "followup", "kind": "nudge"}))
                sent += 1
                continue

            if lead.followup_state == "nudge_sent" and lead.followup_anchor_at and lead.followup_anchor_at <= final_cutoff:
                text = final_followup()
                _send_followup_sync(client, lead.instagram_user_id, text)
                lead.followup_state = "final_sent"
                lead.stage = "followup"
                lead.last_outbound_at = now
                lead.last_message_at = now
                lead.followup_anchor_at = None
                session.add(Message(lead_id=lead.id, direction="outbound", channel="instagram", text=text, raw_payload={"type": "followup", "kind": "final"}))
                sent += 1

        session.commit()

    logger.info("followups_processed", sent=sent)
    return {"sent": sent}


def _send_followup_sync(client, recipient_id: str, text: str) -> None:  # noqa: ANN001
    try:
        client.send_text_sync(OutboundMessage(recipient_id=recipient_id, text=text))
    except Exception as exc:  # noqa: BLE001
        logger.error("followup_send_failed", recipient_id=recipient_id, err=str(exc))
