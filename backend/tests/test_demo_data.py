"""Deterministic, fictional demo data and guarded selective reset tests."""

import os
import subprocess
import sys
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from authedu_api.demo_data import (
    DEMO_NOTES,
    DEMO_USERS,
    DemoSafetyError,
    reset_demo_data,
    seed_demo_data,
)
from authedu_api.models import Note, User


def _demo_snapshot(
    database_url,
) -> tuple[tuple[tuple[UUID, str], ...], tuple[tuple[UUID, UUID, str, str], ...]]:
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            users = tuple(
                sorted(
                    (user.id, user.email)
                    for user in session.scalars(select(User)).all()
                    if user.id in {user_id for user_id, _ in DEMO_USERS}
                )
            )
            notes = tuple(
                sorted(
                    (note.id, note.owner_id, note.title, note.body)
                    for note in session.scalars(select(Note)).all()
                    if note.id in {note_id for note_id, _, _, _ in DEMO_NOTES}
                )
            )
            return users, notes
    finally:
        engine.dispose()


def test_seed_is_idempotent_and_assigns_notes_to_distinct_users(test_database_url) -> None:
    seed_demo_data()
    first_snapshot = _demo_snapshot(test_database_url)
    seed_demo_data()
    second_snapshot = _demo_snapshot(test_database_url)

    assert first_snapshot == second_snapshot
    users, notes = second_snapshot
    assert users == tuple(sorted(DEMO_USERS))
    assert len(notes) == 2
    assert {owner_id for _, owner_id, _, _ in notes} == {user_id for user_id, _ in DEMO_USERS}


def test_cli_seeds_twice_using_compose_secret_configuration(test_database_url, tmp_path) -> None:
    secret_file = tmp_path / "database_password"
    secret_file.write_text(test_database_url.password, encoding="utf-8")
    environment = dict(os.environ)
    environment.pop("DATABASE_URL", None)
    environment.update(
        DATABASE_PASSWORD_FILE=str(secret_file),
        POSTGRES_USER=test_database_url.username,
        POSTGRES_DB=test_database_url.database,
        POSTGRES_HOST=test_database_url.host,
        POSTGRES_PORT=str(test_database_url.port),
    )
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, "-m", "authedu_api.demo_data", "seed"],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "Fictional demo users and notes are present."
        assert result.stderr == ""
    assert _demo_snapshot(test_database_url) == (
        tuple(sorted(DEMO_USERS)), tuple(sorted(DEMO_NOTES))
    )


def test_demo_users_have_no_password_hashes(test_database_url) -> None:
    seed_demo_data()
    engine = create_engine(test_database_url)
    try:
        with Session(engine) as session:
            users = session.scalars(select(User)).all()
            assert {user.email for user in users} == {email for _, email in DEMO_USERS}
            assert all(user.password_hash is None for user in users)
    finally:
        engine.dispose()


def test_reset_requires_explicit_confirmation_and_preserves_rows(test_database_url) -> None:
    seed_demo_data()

    with pytest.raises(DemoSafetyError, match="--confirm-demo-reset"):
        reset_demo_data(confirm=False)

    assert _demo_snapshot(test_database_url) == (
        tuple(sorted(DEMO_USERS)),
        tuple(sorted(DEMO_NOTES)),
    )


def test_reset_removes_only_demo_rows_and_preserves_unrelated_data(test_database_url) -> None:
    seed_demo_data()
    unrelated_id = uuid4()
    engine = create_engine(test_database_url)
    try:
        with Session(engine) as session, session.begin():
            unrelated_user = User(id=unrelated_id, email="unrelated@example.test")
            session.add(unrelated_user)
            session.flush()
            session.add(
                Note(
                    id=uuid4(),
                    owner_id=unrelated_id,
                    title="Keep this note",
                    body="Reset should not delete unrelated records.",
                )
            )
    finally:
        engine.dispose()

    reset_demo_data(confirm=True)
    assert _demo_snapshot(test_database_url) == ((), ())

    engine = create_engine(test_database_url)
    try:
        with Session(engine) as session:
            user = session.get(User, unrelated_id)
            assert user is not None
            assert [note.title for note in user.notes] == ["Keep this note"]
    finally:
        engine.dispose()


def test_reset_then_seed_recreates_same_demo_records(test_database_url) -> None:
    seed_demo_data()
    initial_snapshot = _demo_snapshot(test_database_url)

    reset_demo_data(confirm=True)
    seed_demo_data()

    assert _demo_snapshot(test_database_url) == initial_snapshot


def test_reset_refuses_to_delete_a_demo_user_with_extra_notes(test_database_url) -> None:
    seed_demo_data()
    extra_note_id = uuid4()
    engine = create_engine(test_database_url)
    try:
        with Session(engine) as session, session.begin():
            session.add(
                Note(
                    id=extra_note_id,
                    owner_id=DEMO_USERS[0][0],
                    title="Not part of the fixture",
                    body="This must survive a refused reset.",
                )
            )
    finally:
        engine.dispose()

    with pytest.raises(DemoSafetyError, match="non-demo notes"):
        reset_demo_data(confirm=True)

    engine = create_engine(test_database_url)
    try:
        with Session(engine) as session:
            assert session.get(Note, extra_note_id) is not None
            assert session.get(User, DEMO_USERS[0][0]) is not None
    finally:
        engine.dispose()


def test_reset_refuses_a_demo_note_id_owned_by_the_wrong_demo_user(test_database_url) -> None:
    seed_demo_data()
    note_id = DEMO_NOTES[0][0]
    wrong_owner_id = DEMO_USERS[1][0]
    engine = create_engine(test_database_url)
    try:
        with Session(engine) as session, session.begin():
            note = session.get(Note, note_id)
            assert note is not None
            note.owner_id = wrong_owner_id
    finally:
        engine.dispose()

    with pytest.raises(DemoSafetyError, match="already owned"):
        reset_demo_data(confirm=True)

    engine = create_engine(test_database_url)
    try:
        with Session(engine) as session:
            note = session.get(Note, note_id)
            assert note is not None
            assert note.owner_id == wrong_owner_id
            assert session.get(User, DEMO_USERS[0][0]) is not None
    finally:
        engine.dispose()


def test_demo_operations_refuse_without_local_demo_mode(test_database_url, monkeypatch) -> None:
    seed_demo_data()
    monkeypatch.setenv("AUTHEDU_DEMO_MODE", "0")

    with pytest.raises(DemoSafetyError, match="AUTHEDU_DEMO_MODE=1"):
        reset_demo_data(confirm=True)

    assert len(_demo_snapshot(test_database_url)[0]) == 2


def test_demo_operations_refuse_database_name_mismatch(test_database_url, monkeypatch) -> None:
    monkeypatch.setenv("AUTHEDU_DEMO_DATABASE", "another_database")

    with pytest.raises(DemoSafetyError, match="does not match"):
        seed_demo_data()


def test_demo_operations_refuse_nonlocal_database_host(test_database_url, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@example.invalid/authedu")
    monkeypatch.setenv("AUTHEDU_DEMO_DATABASE", "authedu")

    with pytest.raises(DemoSafetyError, match="local PostgreSQL host"):
        reset_demo_data(confirm=True)
