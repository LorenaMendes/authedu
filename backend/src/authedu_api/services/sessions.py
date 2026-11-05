"""Session-authentication service functions for issue #23.

Raw session tokens must not be persisted, returned in response bodies, logged, or
included in exceptions. The session router is mounted only after its complete
route flow and tests have been reviewed.
"""

import secrets
from datetime import datetime, timedelta
from hashlib import sha256

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from authedu_api.core.identity import normalize_email
from authedu_api.core.passwords import DUMMY_PASSWORD_HASH, verify_password
from authedu_api.models import AuthSession, User

SESSION_IDLE_TIMEOUT = timedelta(minutes=30)
SESSION_ABSOLUTE_TIMEOUT = timedelta(hours=8)


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
