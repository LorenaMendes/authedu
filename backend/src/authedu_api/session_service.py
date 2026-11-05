"""Session-authentication service functions for issue #23.

Raw session tokens must not be persisted, returned in response bodies, logged, or
included in exceptions. The session router is mounted only after its complete
route flow and tests have been reviewed.
"""

import hmac
import os
import re
import secrets
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from authedu_api.models import AuthSession, User
from authedu_api.registration import DUMMY_PASSWORD_HASH, normalize_email, verify_password

SESSION_IDLE_TIMEOUT = timedelta(minutes=30)
SESSION_ABSOLUTE_TIMEOUT = timedelta(hours=8)
CSRF_TOKEN_VERSION = "v1"
CSRF_NONCE_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}\Z")
CSRF_SIGNATURE_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


def _csrf_signing_secret() -> bytes:
    """Load the configured HMAC key without exposing it in errors or logs."""
    secret_file = os.environ.get("AUTHEDU_CSRF_SECRET_FILE")
    if secret_file:
        try:
            secret = Path(secret_file).read_bytes().strip()
        except OSError:
            raise RuntimeError(
                "CSRF signing secret file is unavailable; check the deployment configuration."
            ) from None
    else:
        secret = os.environ.get("AUTHEDU_CSRF_SECRET", "").encode("utf-8")
    if len(secret) < 32:
        raise RuntimeError("The CSRF signing secret must contain at least 32 bytes.")
    return secret


def validate_csrf_configuration() -> None:
    """Fail before session creation if the signing key is not configured."""
    _csrf_signing_secret()


def _csrf_signature(*, secret: bytes, session_token: str, nonce: str) -> str:
    message = f"authedu-csrf:{CSRF_TOKEN_VERSION}\0{session_token}\0{nonce}"
    return hmac.new(secret, message.encode("utf-8"), sha256).hexdigest()


def verify_credentials(session: Session, *, email: str, password: str) -> User | None:
    """Return the user only for valid credentials; use the same public failure either way."""
    normalized_email = normalize_email(email)
    user = session.scalar(select(User).where(func.lower(User.email) == normalized_email))
    stored_hash = user.password_hash if user is not None else None
    password_hash = stored_hash or DUMMY_PASSWORD_HASH
    password_is_valid = verify_password(password, password_hash)
    if user is None or stored_hash is None or not password_is_valid:
        return None
    return user


def create_session(
    session: Session,
    *,
    user: User,
    now: datetime | None = None,
    commit: bool = True,
) -> tuple[str, datetime]:
    """Persist a session and return its raw token and absolute expiry to the caller.

    The raw token is returned only so the route can place it in an HttpOnly cookie;
    only its SHA-256 digest is stored. The caller must not log or return the token
    in a response body. By default, this service commits the session record, so
    pass a clean SQLAlchemy session with no unrelated pending changes. Set
    ``commit=False`` only inside a caller-owned transaction; the caller must
    commit or roll back.
    """
    if now is None:
        # Use the database clock, matching the authority that stores expiry data.
        current_time = session.scalar(select(func.statement_timestamp()))
        if current_time is None:
            raise RuntimeError("Could not read the database clock for session creation.")
    else:
        current_time = now
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("Session timestamps must be timezone-aware.")
    raw_token = secrets.token_urlsafe(32)
    token_digest = sha256(raw_token.encode("utf-8")).hexdigest()
    absolute_expiry = current_time + SESSION_ABSOLUTE_TIMEOUT
    idle_expiry = min(current_time + SESSION_IDLE_TIMEOUT, absolute_expiry)
    auth_session = AuthSession(
        user_id=user.id,
        token_hash=token_digest,
        created_at=current_time,
        last_seen_at=current_time,
        expires_at=absolute_expiry,
        idle_expires_at=idle_expiry,
    )
    session.add(auth_session)
    try:
        if commit:
            session.commit()
        else:
            session.flush()
    except Exception:
        if commit:
            session.rollback()
        raise

    return raw_token, absolute_expiry


def resolve_session_user(
    session: Session,
    *,
    session_token: str | None,
    now: datetime | None = None,
) -> User | None:
    """Resolve a session and commit a monotonic idle-expiry refresh.

    The provided session must be clean: this service commits the activity update,
    and SQLAlchemy commits all pending work in that session. Callers must not use
    it to stage unrelated changes before invoking this method.
    """
    if not session_token:
        return None

    if now is not None and (now.tzinfo is None or now.utcoffset() is None):
        raise ValueError("Session timestamps must be timezone-aware.")

    token_digest = sha256(session_token.encode("utf-8")).hexdigest()
    try:
        # Refresh identity-map state while locking. A reused Session must not
        # authenticate from a stale row after another transaction revoked it.
        auth_session = session.scalar(
            select(AuthSession)
            .where(AuthSession.token_hash == token_digest)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if auth_session is None:
            session.rollback()
            return None

        # Lock first, then read the database clock so a request delayed on this row
        # cannot validate a session using a timestamp from before it acquired the lock.
        current_time = (
            now if now is not None else session.scalar(select(func.statement_timestamp()))
        )
        if current_time is None:
            raise RuntimeError("Could not read the database clock for session validation.")

        if (
            auth_session.revoked_at is not None
            or auth_session.idle_expires_at <= current_time
            or auth_session.expires_at <= current_time
        ):
            session.rollback()
            return None

        user = session.scalar(select(User).where(User.id == auth_session.user_id))
        if user is None:
            session.rollback()
            return None

        # The row lock serializes refreshes. max/min keep the idle deadline
        # monotonic while capping it at the absolute deadline.
        auth_session.last_seen_at = max(auth_session.last_seen_at, current_time)
        auth_session.idle_expires_at = min(
            auth_session.expires_at,
            max(auth_session.idle_expires_at, current_time + SESSION_IDLE_TIMEOUT),
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    return user


def revoke_session(
    session: Session,
    *,
    session_token: str | None,
    now: datetime | None = None,
    commit: bool = True,
) -> None:
    """Idempotently revoke a session, optionally in a caller-owned transaction.

    By default, the provided session must be clean and dedicated to this
    operation: a successful revocation commits, while a missing or already
    revoked record rolls back. Set ``commit=False`` only inside a caller-owned
    transaction. Routes should clear the browser cookie regardless of whether a
    matching session row was found.
    """
    if not session_token:
        return
    if now is not None and (now.tzinfo is None or now.utcoffset() is None):
        raise ValueError("Session timestamps must be timezone-aware.")

    token_digest = sha256(session_token.encode("utf-8")).hexdigest()
    try:
        auth_session = session.scalar(
            select(AuthSession)
            .where(AuthSession.token_hash == token_digest)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if auth_session is None or auth_session.revoked_at is not None:
            if commit:
                session.rollback()
            return

        revocation_time = now if now is not None else session.scalar(
            select(func.statement_timestamp())
        )
        if revocation_time is None:
            raise RuntimeError("Could not read the database clock for session revocation.")

        auth_session.revoked_at = revocation_time
        if commit:
            session.commit()
    except Exception:
        if commit:
            session.rollback()
        raise


def issue_csrf_token(*, session_token: str | None) -> str:
    """Issue a stateless HMAC proof bound to an authenticated session.

    Login has no authenticated session to bind to; its route must apply the
    documented Origin defense instead of calling this helper without a token.
    """
    if not session_token:
        raise ValueError("An authenticated session is required for a CSRF token.")

    nonce = secrets.token_urlsafe(32)
    signature = _csrf_signature(
        secret=_csrf_signing_secret(), session_token=session_token, nonce=nonce
    )
    return f"{CSRF_TOKEN_VERSION}.{nonce}.{signature}"


def validate_csrf_token(
    *,
    session_token: str | None,
    submitted_token: str | None,
) -> None:
    """Raise ValueError unless the proof is valid for the presented session.

    Routes should translate this rejection into a generic HTTP 403 response. This
    proof is not authentication: resolve the session separately before performing
    an authenticated operation.
    """
    if not session_token or not submitted_token or len(submitted_token) > 128:
        raise ValueError("Invalid CSRF token.")

    parts = submitted_token.split(".")
    if (
        len(parts) != 3
        or parts[0] != CSRF_TOKEN_VERSION
        or CSRF_NONCE_PATTERN.fullmatch(parts[1]) is None
        or CSRF_SIGNATURE_PATTERN.fullmatch(parts[2]) is None
    ):
        raise ValueError("Invalid CSRF token.")

    _, nonce, submitted_signature = parts
    expected_signature = _csrf_signature(
        secret=_csrf_signing_secret(), session_token=session_token, nonce=nonce
    )
    if not hmac.compare_digest(expected_signature, submitted_signature):
        raise ValueError("Invalid CSRF token.")
