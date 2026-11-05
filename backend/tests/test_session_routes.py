"""HTTP-level tests for session route behavior in an isolated test app."""

import asyncio
import secrets
from hashlib import sha256
from http.cookies import SimpleCookie
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from authedu_api.api.exception_handlers import handle_request_validation_error
from authedu_api.api.routes import sessions as session_routes
from authedu_api.core import csrf, passwords
from authedu_api.core.rate_limit import InMemoryRateLimiter
from authedu_api.database import create_database_engine, get_database_session
from authedu_api.models import AuthSession, User
from authedu_api.schemas import LoginResponse
from authedu_api.services import sessions as session_service

TRUSTED_ORIGIN = "https://localhost:5173"


@pytest.fixture

def login_client(test_database_url, monkeypatch):
    monkeypatch.setenv("AUTHEDU_PUBLIC_ORIGIN", TRUSTED_ORIGIN)
    monkeypatch.setenv("AUTHEDU_CSRF_SECRET", "test-only-key-" + "x" * 40)
    monkeypatch.delenv("AUTHEDU_CSRF_SECRET_FILE", raising=False)
    monkeypatch.setattr(
        session_routes,
        "_login_rate_limiter",
        InMemoryRateLimiter(
            max_requests=100,
            window_seconds=60,
            error_message="Too many login attempts. Try again later.",
        ),
    )

    engine = create_database_engine(test_database_url)
    app = FastAPI()
    app.add_api_route(
        "/login", session_routes.login, methods=["POST"], response_model=LoginResponse
    )
    app.add_api_route("/me", session_routes.current_user, methods=["GET"])
    app.add_api_route("/logout", session_routes.logout, methods=["POST"])
    app.add_exception_handler(RequestValidationError, handle_request_validation_error)

    def override_database_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_database_session] = override_database_session
    try:
        yield app, engine
    finally:
        engine.dispose()


def _add_user(engine, *, email: str, password_hash: str | None) -> None:
    with Session(engine) as session:
        session.add(User(email=email, password_hash=password_hash))
        session.commit()


def _check_cookie_header(
    header: str,
    *,
    required: tuple[str, ...],
    forbidden: tuple[str, ...] = (),
) -> None:
    normalized_header = header.lower()
    if not all(attribute in normalized_header for attribute in required):
        raise AssertionError("Session cookie is missing a required security attribute.")
    if any(attribute in normalized_header for attribute in forbidden):
        raise AssertionError("Session cookie contains an unexpected security attribute.")


def _login(
    app: FastAPI,
    *,
    email: str,
    password: str,
    origin: str | None = TRUSTED_ORIGIN,
    cookies: dict[str, str] | None = None,
) -> Response:
    headers = {"Origin": origin} if origin is not None else {}
    if cookies:
        headers["Cookie"] = "; ".join(f"{name}={value}" for name, value in cookies.items())

    async def post_login() -> Response:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url=TRUSTED_ORIGIN
        ) as client:
            return await client.post(
                "/login",
                headers=headers,
                json={"email": email, "password": password},
            )

    return asyncio.run(post_login())


def _request(
    app: FastAPI,
    method: str,
    path: str,
    *,
    cookies: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> Response:
    request_headers = dict(headers or {})
    if cookies:
        request_headers["Cookie"] = "; ".join(
            f"{name}={value}" for name, value in cookies.items()
        )

    async def send_request() -> Response:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url=TRUSTED_ORIGIN
        ) as client:
            return await client.request(method, path, headers=request_headers)

    return asyncio.run(send_request())


def test_successful_login_sets_secure_cookie_and_returns_csrf_proof(login_client) -> None:
    client, engine = login_client
    email = f"{uuid4().hex}@example.com"
    password = secrets.token_urlsafe(24)
    user = User(email=email, password_hash=passwords.hash_password(password))
    with Session(engine) as session:
        session.add(user)
        session.commit()
        user_id = user.id

    response = _login(client, email=email, password=password)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    payload = response.json()
    if payload["user"] != {"id": str(user_id), "email": email}:
        raise AssertionError("Login returned an unexpected user representation.")
    csrf_token = payload["csrf_token"]
    if not csrf_token.startswith("v1."):
        raise AssertionError("Login did not return a versioned CSRF proof.")

    set_cookie = response.headers["set-cookie"]
    cookie = SimpleCookie(set_cookie)[session_routes.SESSION_COOKIE_NAME].value
    if cookie in response.text:
        raise AssertionError("Session cookie was included in the login response body.")
    _check_cookie_header(
        set_cookie,
        required=("secure", "httponly", "samesite=lax", "path=/", "max-age=28800"),
        forbidden=("domain=",),
    )

    csrf.validate_csrf_token(session_token=cookie, submitted_token=csrf_token)
    with Session(engine) as session:
        auth_session = session.scalar(select(AuthSession))
        assert auth_session is not None
        assert auth_session.user_id == user_id
        if auth_session.token_hash != sha256(cookie.encode("utf-8")).hexdigest():
            raise AssertionError("Session token was not stored as its digest.")
        if auth_session.token_hash == cookie:
            raise AssertionError("Raw session token was stored in the database.")


@pytest.mark.parametrize("origin", [None, "https://attacker.example"])
def test_login_rejects_missing_or_untrusted_origin_before_verifying_credentials(
    login_client, monkeypatch, origin
) -> None:
    client, _ = login_client

    def unexpected_verification(*args, **kwargs):
        raise AssertionError("Credentials must not be checked for a rejected Origin.")

    monkeypatch.setattr(session_routes, "verify_credentials", unexpected_verification)
    response = _login(
        client,
        email=f"{uuid4().hex}@example.com",
        password=secrets.token_urlsafe(24),
        origin=origin,
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid request origin."}
    if "set-cookie" in response.headers:
        raise AssertionError("Rejected login unexpectedly changed the session cookie.")


def test_login_uses_same_generic_failure_for_unknown_wrong_and_hashless_accounts(
    login_client,
) -> None:
    client, engine = login_client
    password = secrets.token_urlsafe(24)
    email = f"{uuid4().hex}@example.com"
    _add_user(
        engine,
        email=email,
        password_hash=passwords.hash_password(secrets.token_urlsafe(24)),
    )
    hashless_email = f"{uuid4().hex}@example.com"
    _add_user(engine, email=hashless_email, password_hash=None)

    unknown = _login(client, email=f"{uuid4().hex}@example.com", password=password)
    wrong_password = _login(client, email=email, password=password)
    hashless = _login(client, email=hashless_email, password=password)

    assert (unknown.status_code, unknown.json()) == (401, {"detail": "Invalid email or password."})
    assert (wrong_password.status_code, wrong_password.json()) == (
        unknown.status_code,
        unknown.json(),
    )
    assert (hashless.status_code, hashless.json()) == (unknown.status_code, unknown.json())
    if password in unknown.text + wrong_password.text + hashless.text:
        raise AssertionError("A login response included the submitted password.")
    if not all(
        "set-cookie" not in response.headers
        for response in (unknown, wrong_password, hashless)
    ):
        raise AssertionError("Failed credential check unexpectedly changed the session cookie.")


def test_successful_login_revokes_the_presented_session(login_client) -> None:
    client, engine = login_client
    email = f"{uuid4().hex}@example.com"
    password = secrets.token_urlsafe(24)
    with Session(engine) as session:
        user = User(email=email, password_hash=passwords.hash_password(password))
        session.add(user)
        session.commit()
        session.refresh(user)
        old_token, _ = session_service.create_session(session, user=user)

    response = _login(
        client,
        email=email,
        password=password,
        cookies={session_routes.SESSION_COOKIE_NAME: old_token},
    )

    assert response.status_code == 200
    new_token = SimpleCookie(response.headers["set-cookie"])[
        session_routes.SESSION_COOKIE_NAME
    ].value
    if new_token == old_token:
        raise AssertionError("Successful login reused the previous session credential.")
    with Session(engine) as session:
        old_session = session.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == sha256(old_token.encode("utf-8")).hexdigest()
            )
        )
        assert old_session is not None
        assert old_session.revoked_at is not None


def test_failed_login_rotation_keeps_the_existing_session_valid(
    login_client, monkeypatch
) -> None:
    client, engine = login_client
    email = f"{uuid4().hex}@example.com"
    password = secrets.token_urlsafe(24)
    with Session(engine) as session:
        user = User(email=email, password_hash=passwords.hash_password(password))
        session.add(user)
        session.commit()
        session.refresh(user)
        old_token, _ = session_service.create_session(session, user=user)

    def fail_csrf_issuance(*, session_token: str) -> str:
        raise RuntimeError("simulated CSRF configuration failure")

    monkeypatch.setattr(session_routes, "issue_csrf_token", fail_csrf_issuance)
    response = _login(
        client,
        email=email,
        password=password,
        cookies={session_routes.SESSION_COOKIE_NAME: old_token},
    )

    assert response.status_code == 503
    with Session(engine) as session:
        sessions = session.scalars(select(AuthSession).order_by(AuthSession.created_at)).all()
        assert len(sessions) == 1
        if sessions[0].token_hash != sha256(old_token.encode("utf-8")).hexdigest():
            raise AssertionError("Existing session credential changed during failed rotation.")
        assert sessions[0].revoked_at is None


def test_failure_after_staging_old_session_revocation_rolls_back_rotation(
    login_client, monkeypatch
) -> None:
    client, engine = login_client
    email = f"{uuid4().hex}@example.com"
    password = secrets.token_urlsafe(24)
    with Session(engine) as session:
        user = User(email=email, password_hash=passwords.hash_password(password))
        session.add(user)
        session.commit()
        session.refresh(user)
        old_token, _ = session_service.create_session(session, user=user)

    original_revoke = session_routes.revoke_session

    def revoke_then_fail(session, **kwargs) -> None:
        original_revoke(session, **kwargs)
        raise HTTPException(status_code=503, detail="Simulated transaction failure.")

    monkeypatch.setattr(session_routes, "revoke_session", revoke_then_fail)
    response = _login(
        client,
        email=email,
        password=password,
        cookies={session_routes.SESSION_COOKIE_NAME: old_token},
    )

    assert response.status_code == 503
    with Session(engine) as session:
        sessions = session.scalars(select(AuthSession)).all()
        assert len(sessions) == 1
        if sessions[0].token_hash != sha256(old_token.encode("utf-8")).hexdigest():
            raise AssertionError("Existing session credential changed during failed rotation.")
        assert sessions[0].revoked_at is None


def test_login_rate_limit_returns_retry_after(login_client, monkeypatch) -> None:
    client, _ = login_client
    monkeypatch.setattr(
        session_routes,
        "_login_rate_limiter",
        InMemoryRateLimiter(
            max_requests=1,
            window_seconds=60,
            error_message="Too many login attempts. Try again later.",
        ),
    )

    password = secrets.token_urlsafe(24)
    email = f"{uuid4().hex}@example.com"
    first = _login(client, email=email, password=password)
    second = _login(client, email=email, password=password)

    assert first.status_code == 401
    assert second.status_code == 429
    assert second.json() == {"detail": "Too many login attempts. Try again later."}
    assert int(second.headers["retry-after"]) > 0


def test_login_validation_error_does_not_reflect_password(login_client) -> None:
    client, _ = login_client
    password = "p" * 129

    response = _login(client, email="learner@example.com", password=password)

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid login request."}
    if password in response.text:
        raise AssertionError("Validation response included the submitted password.")


def test_login_fails_closed_when_csrf_signing_key_is_not_configured(
    login_client, monkeypatch
) -> None:
    client, engine = login_client
    email = f"{uuid4().hex}@example.com"
    password = secrets.token_urlsafe(24)
    _add_user(engine, email=email, password_hash=passwords.hash_password(password))
    monkeypatch.delenv("AUTHEDU_CSRF_SECRET", raising=False)

    response = _login(client, email=email, password=password)

    assert response.status_code == 503
    assert response.json() == {"detail": "Login is temporarily unavailable."}
    with Session(engine) as session:
        assert session.scalar(select(AuthSession)) is None


def test_login_fails_closed_when_public_origin_is_not_configured(
    login_client, monkeypatch
) -> None:
    client, _ = login_client
    monkeypatch.delenv("AUTHEDU_PUBLIC_ORIGIN", raising=False)

    response = _login(
        client, email=f"{uuid4().hex}@example.com", password=secrets.token_urlsafe(24)
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Session service is temporarily unavailable."}


def test_current_user_rejects_missing_session(login_client) -> None:
    app, _ = login_client

    response = _request(app, "GET", "/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "No valid session."}


def test_current_user_resolves_session_and_issues_fresh_csrf_proof(login_client) -> None:
    app, engine = login_client
    email = f"{uuid4().hex}@example.com"
    with Session(engine) as session:
        user = User(email=email, password_hash=None)
        session.add(user)
        session.commit()
        session.refresh(user)
        user_id = user.id
        session_token, _ = session_service.create_session(session, user=user)

    response = _request(
        app,
        "GET",
        "/me",
        cookies={session_routes.SESSION_COOKIE_NAME: session_token},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    payload = response.json()
    assert payload["user"] == {"id": str(user_id), "email": email}
    csrf.validate_csrf_token(
        session_token=session_token, submitted_token=payload["csrf_token"]
    )


def test_current_user_rejects_revoked_session(login_client) -> None:
    app, engine = login_client
    email = f"{uuid4().hex}@example.com"
    with Session(engine) as session:
        user = User(email=email, password_hash=None)
        session.add(user)
        session.commit()
        session.refresh(user)
        session_token, _ = session_service.create_session(session, user=user)
        session_service.revoke_session(session, session_token=session_token)

    response = _request(
        app,
        "GET",
        "/me",
        cookies={session_routes.SESSION_COOKIE_NAME: session_token},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "No valid session."}


@pytest.mark.parametrize("submitted_token", [None, "invalid"])
def test_logout_rejects_missing_or_invalid_csrf_and_preserves_session(
    login_client, submitted_token: str | None
) -> None:
    app, engine = login_client
    email = f"{uuid4().hex}@example.com"
    with Session(engine) as session:
        user = User(email=email, password_hash=None)
        session.add(user)
        session.commit()
        session.refresh(user)
        session_token, _ = session_service.create_session(session, user=user)

    headers = {"Origin": TRUSTED_ORIGIN}
    if submitted_token is not None:
        headers["X-CSRF-Token"] = submitted_token
    response = _request(
        app,
        "POST",
        "/logout",
        cookies={session_routes.SESSION_COOKIE_NAME: session_token},
        headers=headers,
    )

    assert response.status_code == 403
    with Session(engine) as session:
        record = session.scalar(select(AuthSession))
        assert record is not None
        assert record.revoked_at is None
    if "set-cookie" in response.headers:
        raise AssertionError("Rejected logout unexpectedly cleared the session cookie.")


def test_logout_revokes_session_and_clears_cookie(login_client) -> None:
    app, engine = login_client
    email = f"{uuid4().hex}@example.com"
    with Session(engine) as session:
        user = User(email=email, password_hash=None)
        session.add(user)
        session.commit()
        session.refresh(user)
        session_token, _ = session_service.create_session(session, user=user)
    csrf_token = csrf.issue_csrf_token(session_token=session_token)

    response = _request(
        app,
        "POST",
        "/logout",
        cookies={session_routes.SESSION_COOKIE_NAME: session_token},
        headers={"Origin": TRUSTED_ORIGIN, "X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["cache-control"] == "no-store"
    set_cookie = response.headers["set-cookie"].lower()
    _check_cookie_header(
        set_cookie,
        required=("max-age=0", "secure", "httponly", "samesite=lax", "path=/"),
    )
    with Session(engine) as session:
        record = session.scalar(select(AuthSession))
        assert record is not None
        assert record.revoked_at is not None


def test_logout_without_session_is_idempotent_and_clears_cookie(login_client) -> None:
    app, _ = login_client

    response = _request(
        app,
        "POST",
        "/logout",
        headers={"Origin": TRUSTED_ORIGIN},
    )

    assert response.status_code == 204
    assert response.content == b""
    set_cookie = response.headers["set-cookie"].lower()
    _check_cookie_header(
        set_cookie,
        required=("max-age=0", "secure", "httponly", "samesite=lax", "path=/"),
    )


def test_logout_returns_unavailable_when_csrf_signing_key_is_missing(
    login_client, monkeypatch
) -> None:
    app, engine = login_client
    email = f"{uuid4().hex}@example.com"
    with Session(engine) as session:
        user = User(email=email, password_hash=None)
        session.add(user)
        session.commit()
        session.refresh(user)
        session_token, _ = session_service.create_session(session, user=user)
    csrf_token = csrf.issue_csrf_token(session_token=session_token)
    monkeypatch.delenv("AUTHEDU_CSRF_SECRET", raising=False)

    response = _request(
        app,
        "POST",
        "/logout",
        cookies={session_routes.SESSION_COOKIE_NAME: session_token},
        headers={"Origin": TRUSTED_ORIGIN, "X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 503
    if "set-cookie" in response.headers:
        raise AssertionError(
            "Logout configuration failure unexpectedly cleared the session cookie."
        )
    with Session(engine) as session:
        record = session.scalar(select(AuthSession))
        assert record is not None
        assert record.revoked_at is None


def test_logout_rejects_untrusted_origin(login_client) -> None:
    app, _ = login_client

    response = _request(
        app,
        "POST",
        "/logout",
        headers={"Origin": "https://attacker.example"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid request origin."}
