from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.crm_memory.summarizer import Summarizer
from app.db.models import ConversationSummary, Lead, Message


class MemoryService:
    def __init__(self) -> None:
        self._summarizer = Summarizer()

    def get_recent_messages(self, session: Session, lead_id, limit: int = 12) -> list[dict]:  # noqa: ANN001
        rows = (
            session.execute(select(Message).where(Message.lead_id == lead_id).order_by(desc(Message.created_at)).limit(limit))
            .scalars()
            .all()
        )
        rows.reverse()
        return [{"direction": r.direction, "text": r.text, "created_at": r.created_at.isoformat()} for r in rows]

    def get_summary(self, session: Session, lead_id):  # noqa: ANN001
        return session.execute(select(ConversationSummary).where(ConversationSummary.lead_id == lead_id)).scalar_one_or_none()

    def upsert_summary(self, session: Session, lead: Lead, recent_messages: list[dict]) -> ConversationSummary:
        summary = self.get_summary(session, lead.id)
        if not summary:
            summary = ConversationSummary(lead_id=lead.id, summary_text=None, key_facts=None, last_message_id=None)
            session.add(summary)
            session.flush()

        if not self._summarizer.should_summarize(summary, recent_messages):
            return summary

        updated = self._summarizer.summarize(summary.summary_text, recent_messages, lead=lead)
        summary.summary_text = updated["summary_text"]
        summary.key_facts = updated.get("key_facts") or {}
        logger.info("summary_updated", lead_id=str(lead.id))
        return summary

