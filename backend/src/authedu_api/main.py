"""Minimal FastAPI application for the AuthEdu foundation."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from sqlalchemy.engine import Engine

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


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Report that the API process is responsive; this does not check dependencies."""
    return {"status": "ok"}
