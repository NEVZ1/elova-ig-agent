from __future__ import annotations

from datetime import date

from app.core.logging import logger
from app.lead_engine.schemas import LeadUpdate
from app.llm.client import get_llm


LEAD_EXTRACT_SYSTEM = """You extract structured lead info from a short Instagram DM conversation.

Return JSON with keys:
- name (string or null)
- event_type (string or null)
- event_date (YYYY-MM-DD or null)
- event_date_text (string or null, when date not precise)
- guest_count (int or null)
- budget_min (int or null)
- budget_max (int or null)
- budget_currency (string or null, like USD/EUR/TRY)
- source (string or null)

Rules:
- If you are not sure, return null.
- Do not guess budgets or dates.
"""


class LeadExtractor:
    def __init__(self) -> None:
        self._llm = get_llm()

    def extract(self, *, recent_messages: list[dict], known: dict) -> LeadUpdate:
        user = (
            "Known lead fields:\n"
            f"{known}\n\n"
            "Messages (oldest → newest):\n"
            + "\n".join([f"{m['direction']}: {m.get('text') or ''}".strip() for m in recent_messages])
        )
        update = self._llm.chat_json(system=LEAD_EXTRACT_SYSTEM, user=user, schema=LeadUpdate, temperature=0.0)
        if update.event_date and update.event_date < date(2000, 1, 1):
            update.event_date = None
        logger.info("lead_extracted", has_name=bool(update.name), has_event_type=bool(update.event_type), has_budget=bool(update.budget_min or update.budget_max))
        return update
