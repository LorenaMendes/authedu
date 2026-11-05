"""FastAPI application composition for AuthEdu API routes."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy.engine import Engine

from authedu_api.api.exception_handlers import handle_request_validation_error
from authedu_api.api.middleware import limit_registration_requests
from authedu_api.api.routes.health import router as health_router
from authedu_api.api.routes.registration import router as registration_router
from authedu_api.api.routes.sessions import router as session_router
from authedu_api.database import (
    create_database_engine,
    create_session_factory,
    database_url_from_environment,
)


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
app.middleware("http")(limit_registration_requests)
app.add_exception_handler(RequestValidationError, handle_request_validation_error)
app.include_router(health_router)
app.include_router(registration_router)