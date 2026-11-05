"""Reusable best-effort throttling for this single-process demo."""

from collections import OrderedDict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, status


class InMemoryRateLimiter:
    """Best-effort in-memory request throttling for this single-process demo."""

    def __init__(
        self,
        *,
        max_requests: int = 5,
        window_seconds: int = 600,
        max_clients: int = 10_000,
        error_message: str = "Too many registration attempts. Try again later.",
    ) -> None:
        if max_requests < 1 or window_seconds < 1 or max_clients < 1:
            raise ValueError("Rate-limiter limits must be positive.")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        self.error_message = error_message
        self._attempts: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = Lock()

    def check(self, client_key: str) -> None:
        """Count a request and reject clients over the fixed-window limit."""
        now = monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            attempts = self._attempts.pop(client_key, deque())
            while attempts and attempts[0] <= cutoff:
                attempts.popleft()

            if len(attempts) >= self.max_requests:
                self._attempts[client_key] = attempts
                self._attempts.move_to_end(client_key)
                retry_after = max(1, int(attempts[0] + self.window_seconds - now))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=self.error_message,
                    headers={"Retry-After": str(retry_after)},
                )

            attempts.append(now)
            self._attempts[client_key] = attempts
            while len(self._attempts) > self.max_clients:
                self._attempts.popitem(last=False)