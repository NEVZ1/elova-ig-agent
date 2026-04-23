from __future__ import annotations

import os
import sys
from urllib.parse import urlparse

from app.core.config import settings
from app.workers.celery_app import celery


def _describe_url(url: str | None) -> str:
    if not url:
        return "<missing>"
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.hostname}:{parsed.port or ''}"


def main() -> None:
    # Celery's CLI can read CELERY_BROKER_URL / CELERY_RESULT_BACKEND directly
    # and override app settings. Render may keep env vars with blank values.
    # Force the already-normalized settings into the environment before worker
    # startup so Kombu never receives an empty broker transport.
    broker_url = settings.celery_broker_url or settings.redis_url
    backend_url = settings.celery_result_backend or settings.redis_url
    os.environ["CELERY_BROKER_URL"] = broker_url
    os.environ["CELERY_RESULT_BACKEND"] = backend_url

    print(
        "starting_celery_worker",
        f"broker={_describe_url(broker_url)}",
        f"backend={_describe_url(backend_url)}",
        flush=True,
    )

    # Render small instances (512MB) can OOM with prefork (default). Use solo pool.
    # Also avoid running embedded Beat (-B) in the same process on tiny instances.
    args = sys.argv[1:] or [
        "worker",
        "-l",
        "info",
        "--pool=solo",
        "--concurrency=1",
        "--without-gossip",
        "--without-mingle",
        "--without-heartbeat",
    ]
    celery.worker_main(args)


if __name__ == "__main__":
    main()
