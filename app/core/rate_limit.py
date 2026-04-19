from __future__ import annotations

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse


limiter = Limiter(key_func=get_remote_address)


def rate_limit_exceeded_handler(request, exc: RateLimitExceeded) -> JSONResponse:  # noqa: ANN001
    return JSONResponse(status_code=429, content={"detail": "rate_limited"})

