"""Shared in-memory request throttling."""

import pytest
from fastapi import HTTPException

from authedu_api.core.rate_limit import InMemoryRateLimiter


def test_registration_rate_limiter_returns_retry_after() -> None:
    limiter = InMemoryRateLimiter(max_requests=2, window_seconds=60)
    limiter.check("client-a")
    limiter.check("client-a")

    with pytest.raises(HTTPException) as error:
        limiter.check("client-a")

    assert error.value.status_code == 429
    assert int(error.value.headers["Retry-After"]) > 0
    limiter.check("client-b")