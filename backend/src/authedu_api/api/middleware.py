"""HTTP middleware applied before endpoint parsing and validation."""

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from authedu_api.core.rate_limit import InMemoryRateLimiter

_registration_rate_limiter = InMemoryRateLimiter()


def enforce_registration_rate_limit(client_key: str) -> None:
    """Apply the process-local limiter; do not trust unconfigured proxy headers."""
    _registration_rate_limiter.check(client_key)


async def limit_registration_requests(request: Request, call_next):
    """Count registration attempts before FastAPI parses and validates the body."""
    if request.method == "POST" and request.url.path == "/register":
        client_key = request.client.host if request.client is not None else "unknown"
        try:
            enforce_registration_rate_limit(client_key)
        except HTTPException as error:
            return JSONResponse(
                status_code=error.status_code,
                content={"detail": error.detail},
                headers=error.headers,
            )
    return await call_next(request)