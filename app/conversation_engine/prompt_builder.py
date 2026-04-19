from __future__ import annotations

from datetime import datetime

from app.core.config import settings
from app.db.models import Lead


SYSTEM_BASE = """You are a luxury event consultant for Elova Event Design.

Voice:
- minimal, elegant, calm, premium
- no emojis
- no exclamation marks
- no long paragraphs (max 2 short sentences)
- never sound robotic or overly salesy

Conversation rules:
- ask 1–2 questions maximum per message
- if pricing is asked: give a thoughtful range + ask one qualifying question
- if booking intent: offer a booking link or WhatsApp handoff, gently
- if key details are missing: ask the single highest-value question next

Business links:
- WhatsApp: {whatsapp}
- Booking: {booking}

Your output must be JSON with keys: reply_text, stage, intent, action.
"""


def build_system_prompt(lead: Lead, goal: str, missing_fields: list[str]) -> str:
    missing = ", ".join(missing_fields) if missing_fields else "none"
    return SYSTEM_BASE.format(whatsapp=settings.whatsapp_number, booking=settings.booking_url) + (
        f"\nCurrent goal: {goal}\n"
        f"Known lead info: name={lead.name!r}, event_type={lead.event_type!r}, event_date={lead.event_date or lead.event_date_text!r}, "
        f"guest_count={lead.guest_count!r}, budget_min={lead.budget_min!r}, budget_max={lead.budget_max!r}, currency={lead.budget_currency!r}\n"
        f"Missing: {missing}\n"
        f"Now: {datetime.utcnow().isoformat()}Z\n"
    )


def build_user_context(recent_messages: list[dict], summary_text: str | None) -> str:
    lines: list[str] = []
    if summary_text:
        lines.append("Context summary:")
        lines.append(summary_text.strip())
        lines.append("")
    lines.append("Recent messages (oldest → newest):")
    for m in recent_messages:
        lines.append(f"{m['direction']}: {m.get('text') or ''}".strip())
    return "\n".join(lines).strip()

