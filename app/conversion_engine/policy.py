from __future__ import annotations

from app.conversion_engine.schemas import Decision
from app.db.models import Lead


def missing_fields(lead: Lead) -> list[str]:
    missing: list[str] = []
    if not lead.event_type:
        missing.append("event_type")
    if not (lead.event_date or lead.event_date_text):
        missing.append("date")
    if not lead.guest_count:
        missing.append("guest_count")
    if not (lead.budget_min or lead.budget_max):
        missing.append("budget")
    if not lead.name:
        missing.append("name")
    return missing


class ConversionPolicy:
    def decide(self, lead: Lead, inbound_text: str) -> Decision:
        text = (inbound_text or "").lower()
        missing = missing_fields(lead)

        if any(k in text for k in ["stop", "unsubscribe", "do not message", "dont message", "no more"]):
            return Decision(stage="followup", status="lost", goal="stop", missing_fields=missing)

        if any(k in text for k in ["price", "pricing", "how much", "cost", "rates"]):
            stage = "qualification" if missing else "positioning"
            return Decision(stage=stage, status="active", goal="price_inquiry", missing_fields=missing)

        if any(k in text for k in ["book", "booking", "reserve", "call", "consultation"]):
            return Decision(stage="conversion", status="active", goal="convert", missing_fields=missing)

        if missing:
            return Decision(stage="qualification", status="active", goal="qualify", missing_fields=missing)
        return Decision(stage="positioning", status="active", goal="position", missing_fields=missing)

