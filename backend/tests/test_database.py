"""Persistence constraints, explicit transaction behavior, and safe serialization."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from authedu_api.database import create_database_engine, create_session_factory
from authedu_api.models import Note, User
from authedu_api.schemas import UserRead


def test_initial_schema_and_user_identity_uniqueness(test_database_url) -> None:
    engine = create_database_engine(test_database_url)
    try:
        inspector = inspect(engine)
        assert {"users", "notes", "alembic_version"}.issubset(inspector.get_table_names())
        assert any(
            index["name"] == "uq_users_email_lower" for index in inspector.get_indexes("users")
        )

        session_factory = create_session_factory(engine)
        with session_factory() as session:
            session.add(User(email="learner@example.test"))
            session.commit()
            session.add(User(email="LEARNER@example.test"))
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        engine.dispose()


def test_note_owner_foreign_key_is_enforced(test_database_url) -> None:
    engine = create_database_engine(test_database_url)
    try:
        session_factory = create_session_factory(engine)
        with session_factory() as session:
            session.add(Note(owner_id=uuid4(), title="Orphan", body="No owner"))
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        engine.dispose()


def test_note_updated_at_is_set_on_insert_and_orm_update(test_database_url) -> None:
    engine = create_database_engine(test_database_url)
    session_factory = create_session_factory(engine)
    try:
        with session_factory() as session:
            user = User(email="timestamp-owner@example.test")
            note = Note(owner=user, title="First title", body="Body")
            session.add(note)
            session.commit()
            session.refresh(note)
            created_updated_at = note.updated_at
            assert created_updated_at is not None

            note.title = "Changed title"
            session.commit()
            session.refresh(note)
            assert note.updated_at > created_updated_at
    finally:
        engine.dispose()


def test_committed_work_persists_and_uncommitted_work_rolls_back(test_database_url) -> None:
    engine = create_database_engine(test_database_url)
    session_factory = create_session_factory(engine)
    user_id = uuid4()
    try:
        with session_factory() as session:
            session.add(User(id=user_id, email="committed@example.test"))
            session.commit()

        with session_factory() as session:
            session.add(User(email="rolled-back@example.test"))
            session.flush()

        with session_factory() as session:
            assert session.scalar(select(User).where(User.id == user_id)) is not None
            assert session.scalar(
                select(User).where(User.email == "rolled-back@example.test")
            ) is None
    finally:
        engine.dispose()


def test_public_user_schema_omits_model_only_password_hash() -> None:
    user = User(id=uuid4(), email="safe@example.test")
    representation = UserRead.model_validate(
        {"id": user.id, "email": user.email, "created_at": "2026-11-02T00:00:00Z"}
    ).model_dump()

    assert set(representation) == {"id", "email", "created_at"}
    assert "password_hash" not in UserRead.model_fields
    assert "password_hash" not in representation


def test_application_lifespan_disposes_database_engine(test_database_url) -> None:
    from authedu_api.main import app

    async def exercise_lifespan() -> None:
        async with app.router.lifespan_context(app):
            engine = app.state.session_factory.kw["bind"]
            original_pool = engine.pool
            assert engine.pool.checkedout() == 0

        assert engine.pool is not original_pool
        assert not hasattr(app.state, "session_factory")

    asyncio.run(exercise_lifespan())
