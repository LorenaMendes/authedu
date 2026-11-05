"""Fresh-database migration upgrade and downgrade contract."""

from pathlib import Path
from uuid import uuid4

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import NullPool

from alembic import command

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_updated_at_migration_backfills_and_reverses(test_database_url) -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.check(config)
    command.downgrade(config, "base")
    command.upgrade(config, "0001_initial")

    engine = create_engine(test_database_url, poolclass=NullPool)
    user_id = uuid4()
    note_id = uuid4()
    try:
        inspector = inspect(engine)
        assert {"users", "notes"}.issubset(inspector.get_table_names())
        assert "updated_at" not in {
            column["name"] for column in inspector.get_columns("notes")
        }
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO users (id, email) VALUES (:id, :email)"),
                {"id": user_id, "email": "migration@example.test"},
            )
            connection.execute(
                text(
                    "INSERT INTO notes (id, owner_id, title, body) "
                    "VALUES (:id, :owner_id, :title, :body)"
                ),
                {
                    "id": note_id,
                    "owner_id": user_id,
                    "title": "Existing note",
                    "body": "This row predates updated_at.",
                },
            )
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(test_database_url, poolclass=NullPool)
    try:
        inspector = inspect(engine)
        assert "auth_sessions" in inspector.get_table_names()
        session_columns = {column["name"] for column in inspector.get_columns("auth_sessions")}
        assert session_columns == {
            "id",
            "user_id",
            "token_hash",
            "created_at",
            "last_seen_at",
            "expires_at",
            "idle_expires_at",
            "revoked_at",
        }
        assert any(
            constraint["name"] == "uq_auth_sessions_token_hash"
            and constraint["column_names"] == ["token_hash"]
            for constraint in inspector.get_unique_constraints("auth_sessions")
        )
        assert any(
            foreign_key["constrained_columns"] == ["user_id"]
            and foreign_key["referred_table"] == "users"
            and foreign_key["options"].get("ondelete") == "CASCADE"
            for foreign_key in inspector.get_foreign_keys("auth_sessions")
        )
        note_columns = inspect(engine).get_columns("notes")
        columns = {column["name"] for column in note_columns}
        assert "updated_at" in columns
        updated_at_column = next(
            column for column in note_columns if column["name"] == "updated_at"
        )
        assert updated_at_column["type"].timezone is True
        with engine.connect() as connection:
            assert connection.scalar(
                text("SELECT updated_at FROM notes WHERE id = :note_id"),
                {"note_id": note_id},
            ) is not None
    finally:
        engine.dispose()

    command.downgrade(config, "0001_initial")
    engine = create_engine(test_database_url, poolclass=NullPool)
    try:
        assert "auth_sessions" not in inspect(engine).get_table_names()
        columns = {column["name"] for column in inspect(engine).get_columns("notes")}
        assert "updated_at" not in columns
        with engine.connect() as connection:
            assert connection.scalar(
                text("SELECT id FROM notes WHERE id = :note_id"), {"note_id": note_id}
            ) == note_id
    finally:
        engine.dispose()

    command.upgrade(config, "head")
