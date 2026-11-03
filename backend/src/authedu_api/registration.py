"""Registration policy and password hashing for the session-auth feature."""

from collections import OrderedDict, deque
from threading import Lock
from time import monotonic

from argon2 import PasswordHasher
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from authedu_api.models import User

EMAIL_UNIQUE_INDEX = "uq_users_email_lower"
PASSWORD_HASHER = PasswordHasher()


class RegistrationRateLimiter:
    """Best-effort in-memory registration throttling for this single-process demo."""

    def __init__(
        self, *, max_requests: int = 5, window_seconds: int = 600, max_clients: int = 10_000
    ) -> None:
        if max_requests < 1 or window_seconds < 1 or max_clients < 1:
            raise ValueError("Rate-limiter limits must be positive.")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.max_clients = max_clients
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
                    detail="Too many registration attempts. Try again later.",
                    headers={"Retry-After": str(retry_after)},
                )

            attempts.append(now)
            self._attempts[client_key] = attempts
            while len(self._attempts) > self.max_clients:
                self._attempts.popitem(last=False)


_registration_rate_limiter = RegistrationRateLimiter()

def normalize_email(email: str) -> str:
    """Trim and lowercase an address to match the database's case-insensitive key."""
    return email.strip().lower()

def hash_password(password: str) -> str:
    """Hash with argon2-cffi's high-level Argon2id implementation and random salt."""
    return PASSWORD_HASHER.hash(password)

def enforce_registration_rate_limit(client_key: str) -> None:
    """Apply the process-local limiter; do not trust unconfigured proxy headers."""
    _registration_rate_limiter.check(client_key)

def register_user(
    session: Session,
    *,
    email: str,
    password: str,
) -> bool:
    """Create a user, returning False only for a duplicate normalized email.

    Hashing happens before the atomic insert on both duplicate and new-email paths,
    reducing (but not eliminating) response-time differences that could reveal
    whether an address is already registered.
    """
    normalized_email = normalize_email(email)
    hashed_password = hash_password(password)
    new_user = User(email=normalized_email, password_hash=hashed_password)
    session.add(new_user)
    try:
        session.commit()
        return True
    except IntegrityError as error:
        session.rollback()
        diagnostic = getattr(error.orig, "diag", None)
        if getattr(diagnostic, "constraint_name", None) == EMAIL_UNIQUE_INDEX:
            return False
        raise