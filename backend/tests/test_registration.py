"""Registration validation, credential hashing, and enumeration resistance."""

import asyncio
import secrets
from collections import Counter

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from authedu_api.api import middleware
from authedu_api.core.passwords import verify_password
from authedu_api.core.rate_limit import InMemoryRateLimiter
from authedu_api.database import create_database_engine
from authedu_api.main import app
from authedu_api.models import User
from authedu_api.services import registration


async def _post_registrations(payloads: list[dict[str, str]]) -> list[Response]:
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return [await client.post("/register", json=payload) for payload in payloads]


async def _post_registrations_concurrently(payloads: list[dict[str, str]]) -> list[Response]:
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await asyncio.gather(
                *(client.post("/register", json=payload) for payload in payloads)
            )


def test_registration_normalizes_email_and_persists_only_argon2_hash(
    test_database_url, monkeypatch
) -> None:
    monkeypatch.setattr(
        middleware, "_registration_rate_limiter", InMemoryRateLimiter()
    )
    password = secrets.token_urlsafe(24)

    (response,) = asyncio.run(
        _post_registrations(
            [{"email": "  Learner@Example.COM  ", "password": password}]
        )
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Registration request accepted."}
    if password in response.text:
        raise AssertionError("Registration response included the submitted password.")

    engine = create_database_engine(test_database_url)
    try:
        with Session(engine) as session:
            user = session.scalar(select(User).where(User.email == "learner@example.com"))
            assert user is not None
            if not user.password_hash or not user.password_hash.startswith("$argon2id$"):
                raise AssertionError("Registration did not persist an Argon2id password hash.")
            if user.password_hash == password:
                raise AssertionError("Registration persisted the plaintext password.")
            if not verify_password(password, user.password_hash):
                raise AssertionError("Stored password hash did not verify the submitted password.")
    finally:
        engine.dispose()


def test_duplicate_and_new_addresses_have_identical_responses_and_both_hash(
    test_database_url, monkeypatch
) -> None:
    monkeypatch.setattr(
        middleware, "_registration_rate_limiter", InMemoryRateLimiter()
    )
    real_hash_password = registration.hash_password
    hash_calls: Counter[str] = Counter()

    def count_hash_calls(password: str) -> str:
        hash_calls[password] += 1
        return real_hash_password(password)

    monkeypatch.setattr(registration, "hash_password", count_hash_calls)

    first, new_address, duplicate = asyncio.run(
        _post_registrations(
            [
                {"email": "taken@example.com", "password": "correct horse battery staple"},
                {"email": "available@example.com", "password": "another long passphrase"},
                {"email": "TAKEN@example.com", "password": "correct horse battery staple"},
            ]
        )
    )

    assert first.status_code == 200
    assert (duplicate.status_code, duplicate.json()) == (
        new_address.status_code,
        new_address.json(),
    )
    assert hash_calls == Counter(
        {"correct horse battery staple": 2, "another long passphrase": 1}
    )

    engine = create_database_engine(test_database_url)
    try:
        with Session(engine) as session:
            count = session.scalar(
                select(func.count()).select_from(User).where(
                    func.lower(User.email) == "taken@example.com"
                )
            )
        assert count == 1
    finally:
        engine.dispose()


def test_concurrent_duplicate_registrations_create_only_one_user(
    test_database_url, monkeypatch
) -> None:
    monkeypatch.setattr(
        middleware,
        "_registration_rate_limiter",
        InMemoryRateLimiter(),
    )
    responses = asyncio.run(
        _post_registrations_concurrently(
            [
                {"email": "racing@example.com", "password": "first long passphrase"},
                {"email": "RACING@example.com", "password": "second long passphrase"},
            ]
        )
    )

    assert [(response.status_code, response.json()) for response in responses] == [
        (200, {"message": "Registration request accepted."}),
        (200, {"message": "Registration request accepted."}),
    ]
    engine = create_database_engine(test_database_url)
    try:
        with Session(engine) as session:
            count = session.scalar(
                select(func.count()).select_from(User).where(
                    func.lower(User.email) == "racing@example.com"
                )
            )
        assert count == 1
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("not-an-email", "correct horse battery staple"),
        ("valid@example.com", "short"),
        ("valid@example.com", "x" * 129),
    ],
)
def test_invalid_email_and_password_lengths_are_rejected(
    test_database_url, email, password, monkeypatch
) -> None:
    hash_calls = 0

    def unexpected_hash(_: str) -> str:
        nonlocal hash_calls
        hash_calls += 1
        raise AssertionError("Invalid registration data must be rejected before hashing.")

    monkeypatch.setattr(registration, "hash_password", unexpected_hash)
    (response,) = asyncio.run(
        _post_registrations([{"email": email, "password": password}])
    )

    assert response.status_code == 422
    if password in response.text:
        raise AssertionError("Validation response included the submitted password.")
    assert hash_calls == 0


def test_invalid_requests_consume_registration_limit_before_validation(
    test_database_url, monkeypatch
) -> None:
    monkeypatch.setattr(
        middleware,
        "_registration_rate_limiter",
        InMemoryRateLimiter(max_requests=1),
    )
    invalid_payload = {"email": "not-an-email", "password": "correct horse battery staple"}

    first, second = asyncio.run(_post_registrations([invalid_payload, invalid_payload]))

    assert first.status_code == 422
    assert second.status_code == 429
    assert "correct horse battery staple" not in first.text
    assert "correct horse battery staple" not in second.text