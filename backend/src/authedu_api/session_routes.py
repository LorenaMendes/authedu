"""Mounted session endpoints for issue #23: login, current-user, and logout."""

import os
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from authedu_api.database import get_database_session
from authedu_api.models import User
from authedu_api.registration import RegistrationRateLimiter
from authedu_api.schemas import (
    AuthenticatedUser,
    CurrentSessionResponse,
    LoginRequest,
    LoginResponse,
)
from authedu_api.session_service import (
    SESSION_ABSOLUTE_TIMEOUT,
    create_session,
    issue_csrf_token,
    resolve_session_user,
    revoke_session,
    validate_csrf_configuration,
    validate_csrf_token,
    verify_credentials,
)

router = APIRouter(tags=["sessions"])
SESSION_COOKIE_NAME = "__Host-authedu_session"
_login_rate_limiter = RegistrationRateLimiter(
    max_requests=10,
    window_seconds=60,
    error_message="Too many login attempts. Try again later.",
)


def _validate_browser_origin(request: Request) -> None:
    """Require the browser's exact configured origin before authenticating."""
    expected_origin = os.environ.get("AUTHEDU_PUBLIC_ORIGIN")
    if not expected_origin:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session service is temporarily unavailable.",
        )
    if request.headers.get("origin") != expected_origin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid request origin.",
        )


def _limit_login_attempts(request: Request) -> None:
    """Throttle by the direct peer address; do not trust forwarded headers."""
    client_key = request.client.host if request.client is not None else "unknown"
    _login_rate_limiter.check(client_key)


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_database_session),
) -> LoginResponse:
    """Authenticate, rotate the browser's session, and return a CSRF proof."""
    _limit_login_attempts(request)
    _validate_browser_origin(request)
    try:
        validate_csrf_configuration()
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Login is temporarily unavailable.",
        ) from None

    user = verify_credentials(
        session,
        email=str(payload.email),
        password=payload.password.get_secret_value(),
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    user_id = user.id
    user_email = user.email
    previous_session_token = request.cookies.get(SESSION_COOKIE_NAME)
    # End the credential lookup transaction before beginning an atomic rotation.
    session.rollback()
    try:
        with session.begin():
            authenticated_user = session.get(User, user_id)
            if authenticated_user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password.",
                )

            # Create and revoke inside one transaction: failures leave the old session valid.
            session_token, absolute_expiry = create_session(
                session, user=authenticated_user, commit=False
            )
            try:
                csrf_token = issue_csrf_token(session_token=session_token)
            except RuntimeError:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Login is temporarily unavailable.",
                ) from None
            if previous_session_token:
                revoke_session(
                    session,
                    session_token=previous_session_token,
                    commit=False,
                )
    except HTTPException:
        raise

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        max_age=int(SESSION_ABSOLUTE_TIMEOUT.total_seconds()),
        expires=absolute_expiry.astimezone(timezone.utc),
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
    return LoginResponse(
        user=AuthenticatedUser(id=user_id, email=user_email),
        csrf_token=csrf_token,
    )


@router.get("/me", response_model=CurrentSessionResponse)
def current_user(
    request: Request,
    response: Response,
    session: Session = Depends(get_database_session),
) -> CurrentSessionResponse:
    """Return the authenticated identity and a CSRF proof, or 401 if invalid."""
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No valid session.",
        )
    try:
        validate_csrf_configuration()
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session service is temporarily unavailable.",
        ) from None
    user = resolve_session_user(session, session_token=session_token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No valid session.",
        )
    try:
        csrf_token = issue_csrf_token(session_token=session_token)
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session service is temporarily unavailable.",
        ) from None
    response.headers["Cache-Control"] = "no-store"
    return CurrentSessionResponse(
        user=AuthenticatedUser(id=user.id, email=user.email),
        csrf_token=csrf_token,
    )


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    session: Session = Depends(get_database_session),
) -> Response:
    """Validate same-origin CSRF proof, revoke the session, and clear its cookie."""
    _validate_browser_origin(request)
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if session_token:
        try:
            validate_csrf_token(
                session_token=session_token,
                submitted_token=request.headers.get("X-CSRF-Token"),
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid CSRF token.",
            ) from None
        except RuntimeError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Session service is temporarily unavailable.",
            ) from None
        try:
            revoke_session(session, session_token=session_token, commit=True)
        except Exception:
            session.rollback()
            raise
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
