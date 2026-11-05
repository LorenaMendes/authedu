"""FastAPI application composition for AuthEdu API routes."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from authedu_api.database import (
    create_database_engine,
    create_session_factory,
    database_url_from_environment,
    get_database_session,
)
from authedu_api.registration import enforce_registration_rate_limit, register_user
from authedu_api.schemas import RegistrationRequest, RegistrationResponse
from authedu_api.session_routes import router as session_router


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Manage an optional database engine without making liveness depend on PostgreSQL."""
    database_url = database_url_from_environment(required=False)
    engine: Engine | None = None
    if database_url is not None:
        engine = create_database_engine(database_url)
        application.state.session_factory = create_session_factory(engine)
    try:
        yield
    finally:
        if engine is not None:
            engine.dispose()
            del application.state.session_factory

app = FastAPI(
    title="AuthEdu API",
    description="Educational authentication and authorization reference API.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(session_router)


@app.middleware("http")
async def limit_registration_requests(request: Request, call_next):
    """Count registration attempts before FastAPI parses and validates the body."""
    if request.method == "POST" and request.url.path == "/register":
        client_key = request.client.host if request.client is not None else "unknown"
        try:
            enforce_registration_rate_limit(client_key)
        except HTTPException as error:
            return JSONResponse(
                status_code=error.status_code,
                content={"detail": error.detail},
                headers=error.headers,
            )
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(
    request: Request, error: RequestValidationError
) -> Response:
    """Avoid reflecting passwords in FastAPI's default validation-error payload."""
    if request.url.path in {"/register", "/login"}:
        detail = (
            "Invalid registration request."
            if request.url.path == "/register"
            else "Invalid login request."
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": detail},
        )
    return await request_validation_exception_handler(request, error)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Report that the API process is responsive; this does not check dependencies."""
    return {"status": "ok"}


@app.post(
    "/register",
    tags=["users"],
    response_model=RegistrationResponse,
)
def register(
    payload: RegistrationRequest,
    request: Request,
    session: Session = Depends(get_database_session),
) -> RegistrationResponse:
    """Accept registration without revealing whether the email already exists."""
    register_user(
        session,
        email=str(payload.email),
        password=payload.password.get_secret_value(),
    )
    return RegistrationResponse(message="Registration request accepted.")