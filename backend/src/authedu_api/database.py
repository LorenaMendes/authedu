"""Database URL configuration and SQLAlchemy session lifecycle."""

import os
from collections.abc import Generator

from fastapi import HTTPException, Request
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import Pool


def database_url_from_environment(*, required: bool = True) -> URL | None:
    """Read and validate the PostgreSQL URL without echoing its contents."""
    raw_url = os.environ.get("DATABASE_URL")
    if raw_url is None:
        if required:
            raise RuntimeError("DATABASE_URL must be set to use database functionality.")
        return None

    try:
        database_url = make_url(raw_url)
    except ArgumentError:
        raise RuntimeError("DATABASE_URL is not a valid SQLAlchemy URL.") from None

    if database_url.drivername != "postgresql+psycopg":
        raise RuntimeError("DATABASE_URL must use the postgresql+psycopg driver.")
    return database_url


def create_database_engine(
    database_url: URL | str, *, poolclass: type[Pool] | None = None
) -> Engine:
    """Create one lazy, pooled engine; SQL parameters are hidden from logs/errors."""
    try:
        parsed_url = make_url(database_url)
    except ArgumentError:
        raise RuntimeError("The database URL is not valid.") from None
    if parsed_url.drivername != "postgresql+psycopg":
        raise RuntimeError("The database URL must use the postgresql+psycopg driver.")

    engine_options: dict[str, type[Pool] | bool] = {
        "hide_parameters": True,
        "pool_pre_ping": True,
    }
    if poolclass is not None:
        engine_options["poolclass"] = poolclass
    return create_engine(parsed_url, **engine_options)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Build sessions that callers close explicitly and commit only intentionally."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_database_session(request: Request) -> Generator[Session, None, None]:
    """Yield a request-scoped session; closing it rolls back any uncommitted work."""
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")

    with session_factory() as session:
        yield session
