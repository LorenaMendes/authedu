"""Session-bound CSRF proofs and lazy signing-secret configuration."""

import secrets

import pytest

from authedu_api.core import csrf


def test_csrf_token_round_trip_for_its_session(monkeypatch) -> None:
    monkeypatch.delenv("AUTHEDU_CSRF_SECRET_FILE", raising=False)
    monkeypatch.setenv("AUTHEDU_CSRF_SECRET", secrets.token_urlsafe(48))
    session_token = secrets.token_urlsafe(32)

    csrf_token = csrf.issue_csrf_token(session_token=session_token)

    assert csrf_token.startswith("v1.")
    assert csrf.validate_csrf_token(
        session_token=session_token, submitted_token=csrf_token
    ) is None


def test_csrf_token_is_bound_to_the_session(monkeypatch) -> None:
    monkeypatch.delenv("AUTHEDU_CSRF_SECRET_FILE", raising=False)
    monkeypatch.setenv("AUTHEDU_CSRF_SECRET", secrets.token_urlsafe(48))
    csrf_token = csrf.issue_csrf_token(
        session_token=secrets.token_urlsafe(32)
    )

    with pytest.raises(ValueError, match="Invalid CSRF token"):
        csrf.validate_csrf_token(
            session_token=secrets.token_urlsafe(32), submitted_token=csrf_token
        )


@pytest.mark.parametrize("submitted_token", [None, "", "v1.bad.bad"])
def test_csrf_validation_rejects_missing_or_malformed_token(
    monkeypatch, submitted_token: str | None
) -> None:
    monkeypatch.delenv("AUTHEDU_CSRF_SECRET_FILE", raising=False)
    monkeypatch.setenv("AUTHEDU_CSRF_SECRET", secrets.token_urlsafe(48))

    with pytest.raises(ValueError, match="Invalid CSRF token"):
        csrf.validate_csrf_token(
            session_token=secrets.token_urlsafe(32), submitted_token=submitted_token
        )


def test_csrf_validation_rejects_tampered_signature(monkeypatch) -> None:
    monkeypatch.delenv("AUTHEDU_CSRF_SECRET_FILE", raising=False)
    monkeypatch.setenv("AUTHEDU_CSRF_SECRET", secrets.token_urlsafe(48))
    session_token = secrets.token_urlsafe(32)
    csrf_token = csrf.issue_csrf_token(session_token=session_token)
    version, nonce, signature = csrf_token.split(".")
    tampered_token = f"{version}.{nonce}.{signature[:-1]}{'0' if signature[-1] != '0' else '1'}"

    with pytest.raises(ValueError, match="Invalid CSRF token"):
        csrf.validate_csrf_token(
            session_token=session_token, submitted_token=tampered_token
        )


def test_csrf_helpers_require_an_authenticated_session() -> None:
    with pytest.raises(ValueError, match="authenticated session"):
        csrf.issue_csrf_token(session_token=None)

    with pytest.raises(ValueError, match="Invalid CSRF token"):
        csrf.validate_csrf_token(session_token=None, submitted_token="v1.token.tag")


def test_csrf_helpers_require_configured_signing_secret(monkeypatch) -> None:
    monkeypatch.delenv("AUTHEDU_CSRF_SECRET_FILE", raising=False)
    monkeypatch.delenv("AUTHEDU_CSRF_SECRET", raising=False)
    session_token = secrets.token_urlsafe(32)

    with pytest.raises(RuntimeError, match="CSRF signing secret"):
        csrf.issue_csrf_token(session_token=session_token)

    monkeypatch.setenv("AUTHEDU_CSRF_SECRET", "too-short")
    with pytest.raises(RuntimeError, match="at least 32 bytes"):
        csrf.issue_csrf_token(session_token=session_token)


def test_csrf_helpers_accept_a_32_byte_signing_secret(monkeypatch) -> None:
    monkeypatch.delenv("AUTHEDU_CSRF_SECRET_FILE", raising=False)
    secret = secrets.token_urlsafe(24)
    assert len(secret.encode("utf-8")) == 32
    monkeypatch.setenv("AUTHEDU_CSRF_SECRET", secret)
    session_token = secrets.token_urlsafe(32)

    csrf_token = csrf.issue_csrf_token(session_token=session_token)

    assert csrf.validate_csrf_token(
        session_token=session_token, submitted_token=csrf_token
    ) is None


def test_csrf_helpers_read_signing_secret_from_file(monkeypatch, tmp_path) -> None:
    secret_file = tmp_path / "csrf-signing-key"
    secret_file.write_bytes(secrets.token_urlsafe(48).encode("ascii") + b"\n")
    monkeypatch.delenv("AUTHEDU_CSRF_SECRET", raising=False)
    monkeypatch.setenv("AUTHEDU_CSRF_SECRET_FILE", str(secret_file))
    session_token = secrets.token_urlsafe(32)

    csrf_token = csrf.issue_csrf_token(session_token=session_token)

    assert csrf.validate_csrf_token(
        session_token=session_token, submitted_token=csrf_token
    ) is None