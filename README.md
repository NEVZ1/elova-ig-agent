# Elova Event Design — Instagram DM Agent (Backend)

Production-ready AI DM agent system for Elova Event Design (luxury event design).

## What’s inside

- FastAPI webhook + API
- Redis + Celery queue (message processing + follow-ups)
- PostgreSQL persistence (leads, messages, memory)
- Modular engines:
  - `app/dm_listener/`
  - `app/conversation_engine/`
  - `app/lead_engine/`
  - `app/crm_memory/`
  - `app/conversion_engine/`
  - `app/followup_engine/`

## Quick start (local)

1) Create env file:

```bash
cp .env.example .env
```

2) Start Postgres + Redis:

```bash
docker compose up -d postgres redis
```

3) Install deps:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

4) Run migrations:

```bash
alembic upgrade head
```

5) Run API:

```bash
uvicorn app.main:app --reload --port 8000
```

6) Run Celery worker + beat:

```bash
celery -A app.workers.celery_app.celery worker -l info
celery -A app.workers.celery_app.celery beat -l info
```

## Key endpoints

- `GET /health`
- `GET /health/ready`
- `GET /webhooks/instagram` (Meta webhook verification)
- `POST /webhooks/instagram` (incoming Instagram DM events)
- `GET /admin/leads` (bearer token)
- `GET /admin/leads/{lead_id}` (bearer token)
- `GET /admin/leads/{lead_id}/messages` (bearer token)

## Notes

- Instagram Graph API setup is required (Page, App, permissions, webhook subscriptions).
- The API abstraction is in `app/instagram/client.py` so you can swap Meta Graph API vs. future browser automation.
- Admin auth uses `X-API-Key: $ADMIN_API_KEY`.
- Default LLM is Gemini (cheap). Configure `LLM_PROVIDER=gemini` + `GEMINI_API_KEY`.
- Cost-optimized mode is `LLM_UNIFIED_MODE=true` (single model call per inbound DM).
