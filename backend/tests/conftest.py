"""Disposable PostgreSQL 18 fixtures for persistence and migration tests."""

from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.pool import NullPool
from testcontainers.community.postgres import PostgresContainer

from alembic import command

POSTGRES_IMAGE = "postgres:18.6-bookworm"
BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def postgres_admin_url() -> Iterator[URL]:
    """Start one disposable PostgreSQL container with an in-memory random password."""
    with PostgresContainer(
        POSTGRES_IMAGE,
        username=f"authedu_{uuid4().hex}",
        password=uuid4().hex + uuid4().hex,
        dbname="authedu_test",
    ) as postgres:
        yield make_url(postgres.get_connection_url(driver="psycopg"))


@pytest.fixture

def test_database_url(monkeypatch: pytest.MonkeyPatch, postgres_admin_url: URL) -> Iterator[URL]:
    """Create and always drop a unique database; never connect to developer data."""
    database_name = f"authedu_test_{uuid4().hex}"
    admin_engine = create_engine(
        postgres_admin_url, poolclass=NullPool, hide_parameters=True
    )
    database_created = False
    try:
        with admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
        database_created = True
        database_url = postgres_admin_url.set(database=database_name)
        monkeypatch.setenv("DATABASE_URL", database_url.render_as_string(hide_password=False))
        monkeypatch.setenv("AUTHEDU_DEMO_MODE", "1")
        monkeypatch.setenv("AUTHEDU_DEMO_DATABASE", database_name)

        config = Config(str(BACKEND_ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
        command.upgrade(config, "head")
        yield database_url
    finally:
        try:
            if database_created:
                with (
                    admin_engine.connect().execution_options(isolation_level="AUTOCOMMIT")
                    as connection
                ):
                    connection.execute(
                        text(
                            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                            "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                        ),
                        {"database_name": database_name},
                    )
                    connection.exec_driver_sql(f'DROP DATABASE "{database_name}"')
        finally:
            admin_engine.dispose()
