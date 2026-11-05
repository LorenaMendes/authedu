"""End-to-end HTTP integration tests for registration and cookie sessions."""

import asyncio
import secrets
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from authedu_api import registration, session_routes
from authedu_api.database import create_database_engine
from authedu_api.main import app
from authedu_api.models import AuthSession, User
from authedu_api.registration import RegistrationRateLimiter

TRUSTED_ORIGIN = "https://localhost:5173"


@pytest.fixture

def session_app(test_database_url, monkeypatch):
    monkeypatch.setenv("AUTHEDU_PUBLIC_ORIGIN", TRUSTED_ORIGIN)
    monkeypatch.setenv("AUTHEDU_CSRF_SECRET", secrets.token_urlsafe(48))
    monkeypatch.delenv("AUTHEDU_CSRF_SECRET_FILE", raising=False)
    monkeypatch.setattr(
        registration, "_registration_rate_limiter", RegistrationRateLimiter()
    )
    monkeypatch.setattr(
        session_routes,
        "_login_rate_limiter",
        RegistrationRateLimiter(
            max_requests=100,
            window_seconds=60,
            error_message="Too many login attempts. Try again later.",
        ),
    )
    yield test_database_url


def test_registration_login_current_user_logout_flow(session_app) -> None:
    email = f"{uuid4().hex}@example.com"
    password = secrets.token_urlsafe(24)

    async def exercise_browser_flow() -> tuple[list[int], str]:
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url=TRUSTED_ORIGIN,
            ) as client:
                registration_response = await client.post(
                    "/register",
                    json={"email": email, "password": password},
                )
                login_response = await client.post(
                    "/login",
                    headers={"Origin": TRUSTED_ORIGIN},
                    json={"email": email, "password": password},
                )
                login_payload = login_response.json()
                cookie_name = session_routes.SESSION_COOKIE_NAME
                session_cookie = client.cookies.get(cookie_name)
                me_response = await client.get("/me")
                me_payload = me_response.json()
                csrf_token = me_payload["csrf_token"]
                logout_response = await client.post(
                    "/logout",
                    headers={
                        "Origin": TRUSTED_ORIGIN,
                        "X-CSRF-Token": csrf_token,
                    },
                )
                after_logout_response = await client.get("/me")

                if not session_cookie:
                    raise AssertionError("Successful login did not set a session cookie.")
                if session_cookie in login_response.text or session_cookie in me_response.text:
                    raise AssertionError("Session cookie was included in a response body.")
                if login_payload["user"] != me_payload["user"]:
                    raise AssertionError("Login and current-user identities did not match.")
                return (
                    [
                        registration_response.status_code,
                        login_response.status_code,
                        me_response.status_code,
                        logout_response.status_code,
                        after_logout_response.status_code,
                    ],
                    email,
                )

    statuses, registered_email = asyncio.run(exercise_browser_flow())

    assert statuses == [200, 200, 200, 204, 401]
    engine = create_database_engine(session_app)
    try:
        with Session(engine) as session:
            user = session.scalar(select(User).where(User.email == registered_email))
            assert user is not None
            if not user.password_hash or not user.password_hash.startswith("$argon2id$"):
                raise AssertionError("Registration did not persist an Argon2id password hash.")

            auth_session = session.scalar(select(AuthSession).where(AuthSession.user_id == user.id))
            assert auth_session is not None
            assert auth_session.revoked_at is not None
    finally:
        engine.dispose()
