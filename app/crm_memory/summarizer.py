from __future__ import annotations

from app.db.models import ConversationSummary, Lead
from app.llm.client import get_llm


SUMMARY_SYSTEM = """You are updating a private CRM memory summary for a luxury event design brand.
Return JSON with keys:
- summary_text: short, factual, no sales language
- key_facts: JSON object with any of: name, event_type, date, guest_count, budget
"""


class Summarizer:
    def __init__(self) -> None:
        self._llm = get_llm()

    def should_summarize(self, summary: ConversationSummary, recent_messages: list[dict]) -> bool:
        if not recent_messages:
            return False
        if not summary.summary_text:
            return len(recent_messages) >= 4
        return len(recent_messages) >= 10

    def summarize(self, existing_summary: str | None, recent_messages: list[dict], *, lead: Lead) -> dict:
        user = (
            f"Existing summary:\n{existing_summary or ''}\n\n"
            f"Lead fields: name={lead.name!r}, event_type={lead.event_type!r}, event_date={lead.event_date or lead.event_date_text!r}, "
            f"guest_count={lead.guest_count!r}, budget_min={lead.budget_min!r}, budget_max={lead.budget_max!r}, currency={lead.budget_currency!r}\n\n"
            "Recent messages (oldest → newest):\n"
            + "\n".join([f"{m['direction']}: {m.get('text') or ''}".strip() for m in recent_messages])
        )
        from pydantic import BaseModel  # local import

        class _Summary(BaseModel):
            summary_text: str | None = None
            key_facts: dict | None = None

        parsed = self._llm.chat_json(system=SUMMARY_SYSTEM, user=user, schema=_Summary, temperature=0.0)
        return {"summary_text": parsed.summary_text, "key_facts": parsed.key_facts or {}}
