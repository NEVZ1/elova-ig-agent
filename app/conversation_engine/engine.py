from __future__ import annotations

from app.conversation_engine.prompt_builder import build_system_prompt, build_user_context
from app.conversation_engine.schemas import ReplyPlan
from app.conversation_engine.unified_prompt import build_unified_system, build_unified_user
from app.conversation_engine.unified_schemas import UnifiedOutput
from app.core.config import settings
from app.core.logging import logger
from app.db.models import Lead
from app.llm.client import get_llm


class ConversationEngine:
    def __init__(self) -> None:
        self._llm = get_llm()

    def generate_reply(
        self,
        *,
        lead: Lead,
        recent_messages: list[dict],
        summary_text: str | None,
        goal: str,
        missing_fields: list[str],
    ) -> ReplyPlan:
        system = build_system_prompt(lead, goal, missing_fields)
        user = build_user_context(recent_messages, summary_text)
        plan = self._llm.chat_json(system=system, user=user, schema=ReplyPlan, temperature=0.35)

        plan.reply_text = _enforce_luxury_constraints(plan.reply_text, action=plan.action)
        logger.info("reply_planned", action=plan.action, stage=plan.stage, intent=plan.intent)
        return plan

    def generate_unified(
        self,
        *,
        lead: Lead,
        recent_messages: list[dict],
        summary_text: str | None,
        goal: str,
        missing_fields: list[str],
    ) -> UnifiedOutput:
        system = build_unified_system(lead, goal, missing_fields)
        user = build_unified_user(recent_messages, summary_text)
        out = self._llm.chat_json(system=system, user=user, schema=UnifiedOutput, temperature=0.3)
        out.reply_text = _enforce_luxury_constraints(out.reply_text, action=out.action)
        return out


def _enforce_luxury_constraints(text: str, *, action: str) -> str:
    cleaned = " ".join(text.replace("\n", " ").split()).strip()
    cleaned = cleaned.replace("!", "")
    if cleaned.count("?") > 2:
        parts = cleaned.split("?")
        cleaned = "?".join(parts[:2]).strip() + "?"
    if action == "push_whatsapp" and settings.whatsapp_number and settings.whatsapp_number not in cleaned:
        cleaned = f"{cleaned} WhatsApp works best for quick details: {settings.whatsapp_number}"
    if action == "suggest_booking" and settings.booking_url and settings.booking_url not in cleaned:
        cleaned = f"{cleaned} If you’d like, you can book a short consult here: {settings.booking_url}"
    return cleaned[:1200]
