"""Credential-verification tests for server-side session authentication."""

import secrets
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from authedu_api import registration, session_service
from authedu_api.database import create_database_engine
from authedu_api.models import AuthSession, User


def _add_user(database_url, password_hash: str | None) -> tuple[UUID, str]:
    engine = create_database_engine(database_url)
    try:
        with Session(engine) as session, session.begin():
            user = User(email=f"{uuid4().hex}@example.com", password_hash=password_hash)
            session.add(user)
            session.flush()
            return user.id, user.email
    finally:
        engine.dispose()


def test_valid_credentials_return_the_matching_user(test_database_url) -> None:
    password = secrets.token_urlsafe(24)
    user_id, email = _add_user(test_database_url, registration.hash_password(password))
    engine = create_database_engine(test_database_url)
    try:
        with Session(engine) as session:
            result = session_service.verify_credentials(
                session, email=email.upper(), password=password
            )
        assert result is not None
        assert result.id == user_id
    finally:
        engine.dispose()


def test_create_session_returns_raw_token_but_persists_only_digest(
    test_database_url,
) -> None:
    user_id, email = _add_user(test_database_url, password_hash="not-used-by-session-creation")
    now = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
    expected_idle_expiry = now + timedelta(minutes=30)
    expected_absolute_expiry = now + timedelta(hours=8)

    engine = create_database_engine(test_database_url)
    try:
        with Session(engine) as session:
            user = session.get(User, user_id)
            assert user is not None
            raw_token, absolute_expiry = session_service.create_session(
                session, user=user, now=now
            )

        assert isinstance(raw_token, str)
        assert len(raw_token) >= 32
        assert absolute_expiry == expected_absolute_expiry

        # Use a fresh session to prove create_session committed the record.
        with Session(engine) as session:
            record = session.query(AuthSession).one()
            assert record.user_id == user_id
            if record.token_hash != sha256(raw_token.encode("utf-8")).hexdigest():
                raise AssertionError("Session token was not stored as its digest.")
            if record.token_hash == raw_token:
                raise AssertionError("Raw session token was stored in the database.")
            assert record.created_at == now
            assert record.last_seen_at == now
            assert record.idle_expires_at == expected_idle_expiry
            assert record.expires_at == expected_absolute_expiry
            assert record.revoked_at is None
    finally:
        engine.dispose()


def test_create_and_resolve_session_use_database_clock_by_default(test_database_url) -> None:
    user_id, _ = _add_user(test_database_url, password_hash="not-used-by-session-creation")
    engine = create_database_engine(test_database_url)
    try:
        with Session(engine) as session:
            user = session.get(User, user_id)
            assert user is not None
            raw_token, absolute_expiry = session_service.create_session(session, user=user)

        assert absolute_expiry.tzinfo is not None

        with Session(engine) as session:
            resolved_user = session_service.resolve_session_user(
                session, session_token=raw_token
            )
            assert resolved_user is not None
            resolved_user_id = resolved_user.id
        assert resolved_user_id == user_id

        with Session(engine) as session:
            record = session.query(AuthSession).one()
            assert record.expires_at == absolute_expiry
            assert record.created_at.tzinfo is not None
            assert record.idle_expires_at.tzinfo is not None
    finally:
        engine.dispose()


def test_resolve_session_user_returns_none_for_missing_token(test_database_url) -> None:
    engine = create_database_engine(test_database_url)
    try:
        with Session(engine) as session:
            result = session_service.resolve_session_user(session, session_token=None)
        assert result is None
    finally:
        engine.dispose()

def test_resolve_session_user_returns_none_for_unknown_token(test_database_url) -> None:
    engine = create_database_engine(test_database_url)
    try:
        with Session(engine) as session:
            result = session_service.resolve_session_user(
                session, session_token=secrets.token_urlsafe(32)
            )
        assert result is None
    finally:
        engine.dispose()

def test_resolve_session_user_returns_none_for_revoked_token(test_database_url) -> None:
    user_id, email = _add_user(test_database_url, password_hash="not-used-by-session-creation")
    now = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
    engine = create_database_engine(test_database_url)
    try:
        with Session(engine) as session:
            user = session.get(User, user_id)
            assert user is not None
            raw_token, _ = session_service.create_session(session, user=user, now=now)
            record = session.query(AuthSession).one()
            record.revoked_at = now + timedelta(minutes=1)
            session.commit()

        with Session(engine) as session:
            result = session_service.resolve_session_user(
                session, session_token=raw_token, now=now + timedelta(minutes=2)
            )
        assert result is None
    finally:
        engine.dispose()

def test_resolve_session_user_returns_none_for_idle_expired_token(test_database_url) -> None:
    user_id, email = _add_user(test_database_url, password_hash="not-used-by-session-creation")
    now = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
    check_time = now + timedelta(minutes=31)
    engine = create_database_engine(test_database_url)
    try:
        with Session(engine) as session:
            user = session.get(User, user_id)
            assert user is not None
            raw_token, _ = session_service.create_session(session, user=user, now=now)
            record = session.query(AuthSession).one()
            record.idle_expires_at = check_time - timedelta(seconds=1)
            session.commit()

        with Session(engine) as session:
            result = session_service.resolve_session_user(
                session, session_token=raw_token, now=check_time
            )
        assert result is None
    finally:
        engine.dispose()

def test_resolve_session_user_returns_none_for_absolute_expired_token(test_database_url) -> None:
    user_id, email = _add_user(test_database_url, password_hash="not-used-by-session-creation")
    now = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
    check_time = now + timedelta(hours=8, seconds=1)
    engine = create_database_engine(test_database_url)
    try:
        with Session(engine) as session:
            user = session.get(User, user_id)
            assert user is not None
            raw_token, _ = session_service.create_session(session, user=user, now=now)
            record = session.query(AuthSession).one()
            record.expires_at = check_time - timedelta(seconds=1)
            session.commit()

        with Session(engine) as session:
            result = session_service.resolve_session_user(
                session, session_token=raw_token, now=check_time
            )
        assert result is None
    finally:
        engine.dispose()

def test_resolve_session_user_returns_user_for_valid_token(test_database_url) -> None:
    user_id, email = _add_user(test_database_url, password_hash="not-used-by-session-creation")
    now = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
    engine = create_database_engine(test_database_url)
    try:
        with Session(engine) as session:
            user = session.get(User, user_id)
            assert user is not None
            raw_token, _ = session_service.create_session(session, user=user, now=now)
            session.commit()

        with Session(engine) as session:
            result = session_service.resolve_session_user(
                session, session_token=raw_token, now=now + timedelta(minutes=1)
            )
            result_id = result.id if result is not None else None
        assert result is not None
        assert result_id == user_id
    finally:
        engine.dispose()


def test_resolve_session_user_refreshes_idle_expiry_but_caps_at_absolute_expiry(
    test_database_url,
) -> None:
    user_id, _ = _add_user(test_database_url, password_hash="not-used-by-session-creation")
    created_at = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
    last_activity = created_at + timedelta(hours=7, minutes=50)
    absolute_expiry = created_at + timedelta(hours=8)

    engine = create_database_engine(test_database_url)
    try:
        with Session(engine) as session:
            user = session.get(User, user_id)
            assert user is not None
            raw_token, _ = session_service.create_session(session, user=user, now=created_at)

        with Session(engine) as session:
            activity_times = [
                created_at + timedelta(minutes=minutes)
                for minutes in range(20, 461, 20)
            ] + [last_activity]
            for activity_time in activity_times:
                resolved_user = session_service.resolve_session_user(
                    session, session_token=raw_token, now=activity_time
                )
                assert resolved_user is not None
                assert resolved_user.id == user_id

            record = session.query(AuthSession).one()
            assert record.last_seen_at == last_activity
            assert record.idle_expires_at == absolute_expiry
            assert record.expires_at == absolute_expiry
    finally:
        engine.dispose()


def test_out_of_order_activity_does_not_move_idle_expiry_backwards(test_database_url) -> None:
    user_id, _ = _add_user(test_database_url, password_hash="not-used-by-session-creation")
    created_at = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
    earlier_activity = created_at + timedelta(minutes=20)
    later_activity = created_at + timedelta(minutes=25)
    engine = create_database_engine(test_database_url)
    try:
        with Session(engine) as session:
            user = session.get(User, user_id)
            assert user is not None
            raw_token, _ = session_service.create_session(session, user=user, now=created_at)

        # A newer request may finish first, then an older request may be processed.
        with Session(engine) as session:
            assert session_service.resolve_session_user(
                session, session_token=raw_token, now=later_activity
            ) is not None
        with Session(engine) as session:
            assert session_service.resolve_session_user(
                session, session_token=raw_token, now=earlier_activity
            ) is not None

        with Session(engine) as session:
            record = session.query(AuthSession).one()
            assert record.last_seen_at == later_activity
            assert record.idle_expires_at == later_activity + timedelta(minutes=30)
    finally:
        engine.dispose()


def test_reused_session_does_not_authenticate_stale_row_after_external_revocation(
    test_database_url,
) -> None:
    user_id, _ = _add_user(test_database_url, password_hash="not-used-by-session-creation")
    now = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
    engine = create_database_engine(test_database_url)
    try:
        resolver_session = Session(engine, expire_on_commit=False)
        try:
            user = resolver_session.get(User, user_id)
            assert user is not None
            raw_token, _ = session_service.create_session(
                resolver_session, user=user, now=now
            )
            assert session_service.resolve_session_user(
                resolver_session, session_token=raw_token, now=now + timedelta(minutes=1)
            ) is not None

            with Session(engine) as revoker_session:
                record = revoker_session.query(AuthSession).one()
                record.revoked_at = now + timedelta(minutes=2)
                revoker_session.commit()

            result = session_service.resolve_session_user(
                resolver_session, session_token=raw_token, now=now + timedelta(minutes=3)
            )
            assert result is None
            assert not resolver_session.in_transaction()
        finally:
            resolver_session.close()
    finally:
        engine.dispose()


def test_revoke_session_without_token_is_noop(test_database_url) -> None:
    engine = create_database_engine(test_database_url)
    try:
        with Session(engine) as session:
            assert session_service.revoke_session(session, session_token=None) is None
            assert not session.in_transaction()
    finally:
        engine.dispose()


def test_revoke_session_for_unknown_token_is_idempotent(test_database_url) -> None:
    engine = create_database_engine(test_database_url)
    try:
        with Session(engine) as session:
            assert session_service.revoke_session(
                session, session_token=secrets.token_urlsafe(32)
            ) is None
            assert not session.in_transaction()
    finally:
        engine.dispose()


def test_revoke_session_invalidates_token_and_is_idempotent(test_database_url) -> None:
    user_id, _ = _add_user(test_database_url, password_hash="not-used-by-session-creation")
    now = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
    engine = create_database_engine(test_database_url)
    try:
        with Session(engine) as session:
            user = session.get(User, user_id)
            assert user is not None
            raw_token, _ = session_service.create_session(session, user=user, now=now)

        with Session(engine) as session:
            session_service.revoke_session(
                session, session_token=raw_token, now=now + timedelta(minutes=5)
            )

        with Session(engine) as session:
            record = session.query(AuthSession).one()
            if record.token_hash != sha256(raw_token.encode("utf-8")).hexdigest():
                raise AssertionError("Session token was not stored as its digest.")
            assert record.revoked_at == now + timedelta(minutes=5)
            assert session_service.resolve_session_user(
                session, session_token=raw_token, now=now + timedelta(minutes=6)
            ) is None

        # Revoking an already-revoked token is deliberately harmless.
        with Session(engine) as session:
            assert session_service.revoke_session(
                session, session_token=raw_token, now=now + timedelta(minutes=7)
            ) is None
            assert not session.in_transaction()

        with Session(engine) as session:
            record = session.query(AuthSession).one()
            assert record.revoked_at == now + timedelta(minutes=5)
    finally:
        engine.dispose()


def test_csrf_token_round_trip_for_its_session(monkeypatch) -> None:
    monkeypatch.delenv("AUTHEDU_CSRF_SECRET_FILE", raising=False)
    monkeypatch.setenv("AUTHEDU_CSRF_SECRET", secrets.token_urlsafe(48))
    session_token = secrets.token_urlsafe(32)

    csrf_token = session_service.issue_csrf_token(session_token=session_token)

    assert csrf_token.startswith("v1.")
    assert session_service.validate_csrf_token(
        session_token=session_token, submitted_token=csrf_token
    ) is None


def test_csrf_token_is_bound_to_the_session(monkeypatch) -> None:
    monkeypatch.delenv("AUTHEDU_CSRF_SECRET_FILE", raising=False)
    monkeypatch.setenv("AUTHEDU_CSRF_SECRET", secrets.token_urlsafe(48))
    csrf_token = session_service.issue_csrf_token(
        session_token=secrets.token_urlsafe(32)
    )

    with pytest.raises(ValueError, match="Invalid CSRF token"):
        session_service.validate_csrf_token(
            session_token=secrets.token_urlsafe(32), submitted_token=csrf_token
        )


@pytest.mark.parametrize("submitted_token", [None, "", "v1.bad.bad"])
def test_csrf_validation_rejects_missing_or_malformed_token(
    monkeypatch, submitted_token: str | None
) -> None:
    monkeypatch.delenv("AUTHEDU_CSRF_SECRET_FILE", raising=False)
    monkeypatch.setenv("AUTHEDU_CSRF_SECRET", secrets.token_urlsafe(48))

    with pytest.raises(ValueError, match="Invalid CSRF token"):
        session_service.validate_csrf_token(
            session_token=secrets.token_urlsafe(32), submitted_token=submitted_token
        )


def test_csrf_validation_rejects_tampered_signature(monkeypatch) -> None:
    monkeypatch.delenv("AUTHEDU_CSRF_SECRET_FILE", raising=False)
    monkeypatch.setenv("AUTHEDU_CSRF_SECRET", secrets.token_urlsafe(48))
    csrf_token = session_service.issue_csrf_token(
        session_token=secrets.token_urlsafe(32)
    )
    version, nonce, signature = csrf_token.split(".")
    tampered_token = f"{version}.{nonce}.{signature[:-1]}{'0' if signature[-1] != '0' else '1'}"

    with pytest.raises(ValueError, match="Invalid CSRF token"):
        session_service.validate_csrf_token(
            session_token=secrets.token_urlsafe(32), submitted_token=tampered_token
        )


def test_csrf_helpers_require_an_authenticated_session() -> None:
    with pytest.raises(ValueError, match="authenticated session"):
        session_service.issue_csrf_token(session_token=None)

    with pytest.raises(ValueError, match="Invalid CSRF token"):
        session_service.validate_csrf_token(session_token=None, submitted_token="v1.token.tag")


def test_csrf_helpers_require_configured_signing_secret(monkeypatch) -> None:
    monkeypatch.delenv("AUTHEDU_CSRF_SECRET_FILE", raising=False)
    monkeypatch.delenv("AUTHEDU_CSRF_SECRET", raising=False)
    session_token = secrets.token_urlsafe(32)

    with pytest.raises(RuntimeError, match="CSRF signing secret"):
        session_service.issue_csrf_token(session_token=session_token)

    monkeypatch.setenv("AUTHEDU_CSRF_SECRET", "too-short")
    with pytest.raises(RuntimeError, match="at least 32 bytes"):
        session_service.issue_csrf_token(session_token=session_token)


def test_csrf_helpers_accept_a_32_byte_signing_secret(monkeypatch) -> None:
    monkeypatch.delenv("AUTHEDU_CSRF_SECRET_FILE", raising=False)
    secret = secrets.token_urlsafe(24)
    assert len(secret.encode("utf-8")) == 32
    monkeypatch.setenv("AUTHEDU_CSRF_SECRET", secret)
    session_token = secrets.token_urlsafe(32)

    csrf_token = session_service.issue_csrf_token(session_token=session_token)

    assert session_service.validate_csrf_token(
        session_token=session_token, submitted_token=csrf_token
    ) is None


def test_csrf_helpers_read_signing_secret_from_file(monkeypatch, tmp_path) -> None:
    secret_file = tmp_path / "csrf-signing-key"
    secret_file.write_bytes(secrets.token_urlsafe(48).encode("ascii") + b"\n")
    monkeypatch.delenv("AUTHEDU_CSRF_SECRET", raising=False)
    monkeypatch.setenv("AUTHEDU_CSRF_SECRET_FILE", str(secret_file))
    session_token = secrets.token_urlsafe(32)

    csrf_token = session_service.issue_csrf_token(session_token=session_token)

    assert session_service.validate_csrf_token(
        session_token=session_token, submitted_token=csrf_token
    ) is None


def test_wrong_password_returns_none(test_database_url) -> None:
    _, email = _add_user(test_database_url, registration.hash_password(secrets.token_urlsafe(24)))
    engine = create_database_engine(test_database_url)
    try:
        with Session(engine) as session:
            result = session_service.verify_credentials(
                session, email=email, password=secrets.token_urlsafe(24)
            )
        assert result is None
    finally:
        engine.dispose()


def test_unknown_user_still_verifies_against_dummy_hash(test_database_url, monkeypatch) -> None:
    password = secrets.token_urlsafe(24)
    verified_hashes: list[str] = []
    real_verify = session_service.verify_password

    def record_verify(submitted_password: str, stored_hash: str) -> bool:
        verified_hashes.append(stored_hash)
        return real_verify(submitted_password, stored_hash)

    monkeypatch.setattr(session_service, "verify_password", record_verify)
    engine = create_database_engine(test_database_url)
    try:
        with Session(engine) as session:
            result = session_service.verify_credentials(
                session, email="missing@example.com", password=password
            )
        assert result is None
        if verified_hashes != [session_service.DUMMY_PASSWORD_HASH]:
            raise AssertionError("Unknown account did not use the dummy password hash.")
    finally:
        engine.dispose()


def test_hashless_demo_user_is_not_authenticated_even_if_dummy_verifies(
    test_database_url, monkeypatch
) -> None:
    _, email = _add_user(test_database_url, password_hash=None)
    verified_hashes: list[str] = []

    def dummy_verifies(submitted_password: str, stored_hash: str) -> bool:
        verified_hashes.append(stored_hash)
        return True

    monkeypatch.setattr(session_service, "verify_password", dummy_verifies)
    engine = create_database_engine(test_database_url)
    try:
        with Session(engine) as session:
            result = session_service.verify_credentials(
                session, email=email, password=secrets.token_urlsafe(24)
            )
        assert result is None
        if verified_hashes != [session_service.DUMMY_PASSWORD_HASH]:
            raise AssertionError("Hashless account did not use the dummy password hash.")
    finally:
        engine.dispose()


def test_verifier_uses_one_dummy_hash_for_missing_and_hashless_accounts() -> None:
    assert registration.DUMMY_PASSWORD_HASH.startswith("$argon2id$")
    if registration.DUMMY_PASSWORD_HASH == "dummy password":
        raise AssertionError("The dummy verifier is not a real Argon2id hash.")


@pytest.mark.parametrize("malformed_hash", ["", "not-an-argon2-hash"])
def test_malformed_stored_hash_is_a_failed_verification(malformed_hash: str) -> None:
    assert registration.verify_password(secrets.token_urlsafe(24), malformed_hash) is False


def test_corrupt_hash_for_existing_user_still_uses_dummy_argon2_verification(
    test_database_url, monkeypatch
) -> None:
    _, email = _add_user(test_database_url, password_hash="corrupt-hash")
    original_verify = registration.PASSWORD_HASHER.verify
    verified_hashes: list[str] = []

    class RecordingHasher:
        def verify(self, hash_value: str, password: str) -> bool:
            verified_hashes.append(hash_value)
            return original_verify(hash_value, password)

    monkeypatch.setattr(registration, "PASSWORD_HASHER", RecordingHasher())
    engine = create_database_engine(test_database_url)
    try:
        with Session(engine) as session:
            result = session_service.verify_credentials(
                session, email=email, password=secrets.token_urlsafe(24)
            )
        assert result is None
        if verified_hashes != ["corrupt-hash", registration.DUMMY_PASSWORD_HASH]:
            raise AssertionError("Corrupt password hash did not trigger dummy Argon2 verification.")
    finally:
        engine.dispose()
