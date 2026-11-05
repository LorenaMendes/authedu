"""Session-bound HMAC CSRF proofs and lazy signing-secret configuration."""

import hmac
import os
import re
import secrets
from hashlib import sha256
from pathlib import Path

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