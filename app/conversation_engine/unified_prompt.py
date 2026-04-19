from __future__ import annotations

from datetime import datetime

from app.core.config import settings
from app.db.models import Lead


UNIFIED_SYSTEM = """You are a luxury event consultant for Elova Event Design.

Voice:
- minimal, elegant, calm, premium
- no emojis
- no exclamation marks
- no long paragraphs (max 2 short sentences)
- never sound robotic or overly salesy

Conversation rules:
- ask 1–2 questions maximum per message
- ask the single highest-value question next
- adapt to the user’s style while staying premium

Business links:
- WhatsApp: {whatsapp}
- Booking: {booking}

You must return JSON only, with these keys:
reply_text, stage, intent, action,
name, event_type, event_date, event_date_text, guest_count, budget_min, budget_max, budget_currency,
summary_text, key_facts

Extraction rules:
- Only fill lead fields if clearly stated by the user. Do not guess.
- event_date must be YYYY-MM-DD only if precise, otherwise use event_date_text.
- key_facts is a small JSON object with any confirmed facts.
"""


def build_unified_system(lead: Lead, goal: str, missing_fields: list[str]) -> str:
    missing = ", ".join(missing_fields) if missing_fields else "none"
    return UNIFIED_SYSTEM.format(whatsapp=settings.whatsapp_number, booking=settings.booking_url) + (
        f"\nCurrent goal: {goal}\n"
        f"Known lead info: name={lead.name!r}, event_type={lead.event_type!r}, event_date={lead.event_date or lead.event_date_text!r}, "
        f"guest_count={lead.guest_count!r}, budget_min={lead.budget_min!r}, budget_max={lead.budget_max!r}, currency={lead.budget_currency!r}\n"
        f"Missing: {missing}\n"
        f"Now: {datetime.utcnow().isoformat()}Z\n"
    )


def build_unified_user(recent_messages: list[dict], existing_summary: str | None) -> str:
    lines: list[str] = []
    if existing_summary:
        lines.append("Existing CRM summary (private, factual):")
        lines.append(existing_summary.strip())
        lines.append("")
    lines.append("Messages (oldest → newest):")
    for m in recent_messages:
        lines.append(f"{m['direction']}: {m.get('text') or ''}".strip())
    return "\n".join(lines).strip()

