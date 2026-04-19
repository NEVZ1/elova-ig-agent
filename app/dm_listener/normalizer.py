from __future__ import annotations

from app.instagram.types import NormalizedInboundMessage


def normalize_instagram_payload(payload: dict) -> list[NormalizedInboundMessage]:
    """
    Normalizes common Meta webhook shapes to a stable internal format.
    Supports: entry[].messaging[] with message.text.
    """
    out: list[NormalizedInboundMessage] = []
    for entry in payload.get("entry", []) or []:
        for messaging in entry.get("messaging", []) or []:
            sender_id = (messaging.get("sender") or {}).get("id")
            if not sender_id:
                continue
            message = messaging.get("message") or {}
            text = message.get("text")
            out.append(
                NormalizedInboundMessage(
                    instagram_user_id=str(sender_id),
                    instagram_username=None,
                    instagram_message_id=message.get("mid"),
                    text=text,
                    raw=messaging,
                )
            )
    return out

