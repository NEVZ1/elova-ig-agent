# Sample prompts

## System prompt (generated)

The runtime system prompt is generated in `app/conversation_engine/prompt_builder.py`.

Core constraints:

- minimal, elegant, calm, premium
- no emojis, no exclamation marks
- max 2 short sentences
- ask 1–2 questions max
- output JSON: `reply_text`, `stage`, `intent`, `action`

## Unified (tek çağrı) prompt

Unified mod (maliyet optimizasyonu) tek LLM çağrısıyla şunları döndürür:
- reply + stage/intent/action
- lead field updates (sadece kullanıcı net söylediyse)
- CRM summary update

Kod: `app/conversation_engine/unified_prompt.py`, schema: `app/conversation_engine/unified_schemas.py`

## Lead extraction prompt

See `app/lead_engine/extractor.py` (`LEAD_EXTRACT_SYSTEM`).

## CRM memory summary prompt

See `app/crm_memory/summarizer.py` (`SUMMARY_SYSTEM`).
