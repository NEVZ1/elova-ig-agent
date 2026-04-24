from __future__ import annotations

import logging
import sys

import structlog
from pythonjsonlogger import jsonlogger

from app.core.config import settings


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    root.handlers.clear()

    # Avoid leaking secrets in third-party HTTP client logs (URLs can include tokens).
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(settings.log_level.upper())
    handler.setFormatter(jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(root.level),
        cache_logger_on_first_use=True,
    )


logger = structlog.get_logger("elova_dm")
