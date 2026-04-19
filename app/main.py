from __future__ import annotations

from fastapi import FastAPI
from slowapi.middleware import SlowAPIMiddleware

from app.api import admin, health
from app.core.logging import configure_logging
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.dm_listener.router import router as dm_router


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Elova Event Design — IG DM Agent", version="1.0.0")

    app.state.limiter = limiter
    app.add_exception_handler(429, rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.include_router(health.router)
    app.include_router(dm_router)
    app.include_router(admin.router)
    return app


app = create_app()

