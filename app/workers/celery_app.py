from __future__ import annotations

from celery import Celery

from app.core.config import settings


celery = Celery(
    "elova_dm",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.tasks",
        "app.followup_engine.tasks",
    ],
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)

celery.conf.beat_schedule = {
    "send-due-followups-every-5-min": {
        "task": "app.followup_engine.tasks.send_due_followups",
        "schedule": 300.0,
    }
}

