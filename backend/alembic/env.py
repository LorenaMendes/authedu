"""Alembic configuration using DATABASE_URL and application model metadata."""

from sqlalchemy import pool

from alembic import context
from authedu_api.database import create_database_engine, database_url_from_environment
from authedu_api.models import Base

config = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Render migration SQL without exposing a configured password."""
    database_url = database_url_from_environment()
    assert database_url is not None
    context.configure(
        url=database_url.render_as_string(hide_password=True),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using a short-lived, non-pooled connection."""
    database_url = database_url_from_environment()
    assert database_url is not None
    connectable = create_database_engine(database_url, poolclass=pool.NullPool)
    try:
        with connectable.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
