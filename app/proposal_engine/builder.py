from __future__ import annotations

from typing import Any

from app.db.models import Lead


def build_proposal_draft(lead: Lead) -> dict[str, Any]:
    event_label = _event_label(lead)
    date_label = _date_label(lead)
    city_label = lead.venue_city or "the venue area"
    guest_label = _guest_label(lead)
    budget_label = _budget_label(lead)
    urgency_label = (lead.urgency_level or "medium").strip().lower()
    channel_label = (lead.preferred_channel or "instagram").strip().lower()

    recommended_next_action = _recommended_next_action(lead)
    short_quote_draft = _short_quote_draft(event_label, city_label, date_label, guest_label, budget_label, lead)
    premium_proposal_intro = _premium_proposal_intro(event_label, city_label, date_label, urgency_label)
    next_step_copy = _next_step_copy(recommended_next_action, channel_label, city_label, date_label, guest_label)

    proposal_outline = [
        f"Event type: {event_label}",
        f"Date: {date_label}",
        f"Venue area: {city_label}",
        f"Guest count: {guest_label}",
        f"Budget signal: {budget_label}",
        f"Urgency: {urgency_label}",
        f"Preferred channel: {channel_label}",
    ]

    operator_notes = [
        "Keep the copy short and premium.",
        "Do not force a final price if scope is not fully confirmed.",
    ]
    if lead.handoff_required:
        operator_notes.append("Human handoff is already required; keep the tone warm and direct.")
    if lead.proposal_status in {"requested", "in_progress"}:
        operator_notes.append("Proposal work is active; keep the next step concrete and near-term.")
    if lead.lost_reason:
        operator_notes.append(f"Known loss reason: {lead.lost_reason}")

    return {
        "lead": {
            "id": str(lead.id),
            "instagram_user_id": lead.instagram_user_id,
            "instagram_username": lead.instagram_username,
            "name": lead.name,
            "event_type": lead.event_type,
            "event_date": lead.event_date.isoformat() if lead.event_date else None,
            "event_date_text": lead.event_date_text,
            "venue_city": lead.venue_city,
            "guest_count": lead.guest_count,
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
        },
        "proposal": {
            "headline": f"Tailored {event_label} direction for {city_label}",
            "short_quote_draft": short_quote_draft,
            "premium_proposal_intro": premium_proposal_intro,
            "next_step_copy": next_step_copy,
            "recommended_next_action": recommended_next_action,
            "proposal_outline": proposal_outline,
            "operator_notes": operator_notes,
        },
    }


def _recommended_next_action(lead: Lead) -> str:
    if lead.status == "won":
        return "won"
    if lead.status == "lost":
        return "lost"
    if lead.handoff_required:
        return "handoff"
    if lead.proposal_status in {"requested", "in_progress"}:
        return "prepare_proposal"
    if lead.status == "reply_failed":
        return "fix_delivery"
    return "continue_qualification"


def _short_quote_draft(
    event_label: str,
    city_label: str,
    date_label: str,
    guest_label: str,
    budget_label: str,
    lead: Lead,
) -> str:
    if lead.budget_min or lead.budget_max:
        return (
            f"For the {event_label} in {city_label}, a tailored starting range would be {budget_label}. "
            f"The final scope depends on the venue, styling direction, and guest count ({guest_label})."
        )
    return (
        f"For the {event_label} in {city_label}, pricing is scope-based and depends on the venue, styling direction, "
        f"and guest count ({guest_label}). If you share the date ({date_label}), we can narrow it down quickly."
    )


def _premium_proposal_intro(event_label: str, city_label: str, date_label: str, urgency_label: str) -> str:
    tone = "calm and considered" if urgency_label != "high" else "fast, clear, and direct"
    return (
        f"Thank you — this {event_label} feels like a beautiful fit for a boutique, {tone} approach. "
        f"We would shape the experience around the venue area, {city_label}, and the date {date_label}, "
        f"so the final direction feels polished, cohesive, and intentional."
    )


def _next_step_copy(
    recommended_next_action: str,
    channel_label: str,
    city_label: str,
    date_label: str,
    guest_label: str,
) -> str:
    if recommended_next_action == "handoff":
        return (
            f"If you'd like, we can continue on {channel_label} and keep the next step simple. "
            f"Just send the venue area, date, and guest count ({guest_label}) and we’ll guide it from there."
        )
    if recommended_next_action == "prepare_proposal":
        return (
            f"If you send the venue area ({city_label}), date ({date_label}), and guest count ({guest_label}), "
            f"I can prepare a concise proposal direction next."
        )
    if recommended_next_action == "fix_delivery":
        return "The reply path needs a quick check before we continue. Once that’s fixed, we can send the next step cleanly."
    if recommended_next_action == "won":
        return "Great — this lead is already won. Move to delivery, scheduling, and payment checkpoints."
    if recommended_next_action == "lost":
        return "This lead is marked lost. Capture the reason, then move on to recovery or future remarketing if relevant."
    return (
        f"To keep this moving, ask for the venue area, date, and guest count ({guest_label}). "
        f"That is enough to prepare the next step cleanly."
    )


def _event_label(lead: Lead) -> str:
    if lead.event_type:
        return lead.event_type.strip()
    return "event"


def _date_label(lead: Lead) -> str:
    if lead.event_date:
        return lead.event_date.isoformat()
    if lead.event_date_text:
        return lead.event_date_text.strip()
    return "your preferred date"


def _guest_label(lead: Lead) -> str:
    if lead.guest_count:
        return f"{lead.guest_count} guests"
    return "guest count to be confirmed"


def _budget_label(lead: Lead) -> str:
    if lead.budget_min and lead.budget_max:
        currency = f" {lead.budget_currency}" if lead.budget_currency else ""
        return f"{lead.budget_min}-{lead.budget_max}{currency}"
    if lead.budget_max:
        currency = f" {lead.budget_currency}" if lead.budget_currency else ""
        return f"up to {lead.budget_max}{currency}"
    if lead.budget_min:
        currency = f" {lead.budget_currency}" if lead.budget_currency else ""
        return f"from {lead.budget_min}{currency}"
    if lead.project_value_estimate:
        return f"around {lead.project_value_estimate}"
    return "not confirmed yet"
