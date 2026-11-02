"""Seed and safely reset AuthEdu's fictional local demo records.

These accounts intentionally have no password hashes; registration/login are not
implemented here. Reset deletes only the deterministic demo fixture rows and
refuses to proceed unless both local demo configuration and explicit confirmation
are present.
"""

import argparse
import os
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from authedu_api.database import create_database_engine, database_url_from_environment
from authedu_api.models import Note, User

DEMO_USERS = (
    (UUID("00000000-0000-4000-8000-000000000101"), "ada@example.test"),
    (UUID("00000000-0000-4000-8000-000000000102"), "bia@example.test"),
)
DEMO_NOTES = (
    (
        UUID("00000000-0000-4000-8000-000000000201"),
        DEMO_USERS[0][0],
        "Ada's sample note",
        "Fictional note owned by Ada for AuthEdu demonstrations.",
    ),
    (
        UUID("00000000-0000-4000-8000-000000000202"),
        DEMO_USERS[1][0],
        "Bia's sample note",
        "Fictional note owned by Bia for AuthEdu demonstrations.",
    ),
)
LOCAL_DATABASE_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "postgres"})
DEMO_FIXTURE_LOCK_KEY = 73194268150427


class DemoSafetyError(RuntimeError):
    """Raised when demo operations target an unapproved or conflicting database."""


def _demo_database_url() -> URL:
    """Require an explicitly marked local database with the configured demo name."""
    if os.environ.get("AUTHEDU_DEMO_MODE") != "1":
        raise DemoSafetyError("Set AUTHEDU_DEMO_MODE=1 in the local demo environment.")

    database_url = database_url_from_environment()
    assert database_url is not None
    expected_database = os.environ.get("AUTHEDU_DEMO_DATABASE")
    if not expected_database or database_url.database != expected_database:
        raise DemoSafetyError("The connected database does not match AUTHEDU_DEMO_DATABASE.")
    if database_url.host not in LOCAL_DATABASE_HOSTS:
        raise DemoSafetyError("Demo data operations are restricted to a local PostgreSQL host.")
    return database_url


def _lock_demo_fixture(session: Session) -> None:
    """Serialize seed/reset operations so their shared fixture cannot race."""
    session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": DEMO_FIXTURE_LOCK_KEY},
    )


def seed_demo_data() -> None:
    """Create missing fictional demo users and notes without overwriting existing rows."""
    database_url = _demo_database_url()
    engine = create_database_engine(database_url)
    try:
        with Session(engine) as session, session.begin():
            _lock_demo_fixture(session)
            for user_id, email in DEMO_USERS:
                user = session.get(User, user_id)
                if user is not None:
                    if user.email != email:
                        raise DemoSafetyError("A demo user ID is already used by another identity.")
                    continue

                matching_email = session.scalar(
                    select(User).where(func.lower(User.email) == email.lower())
                )
                if matching_email is not None:
                    raise DemoSafetyError("A demo email is already used by another identity.")
                session.add(User(id=user_id, email=email))

            session.flush()
            for note_id, owner_id, title, body in DEMO_NOTES:
                note = session.get(Note, note_id)
                if note is not None:
                    if note.owner_id != owner_id:
                        raise DemoSafetyError("A demo note ID is already owned by another user.")
                    continue
                session.add(Note(id=note_id, owner_id=owner_id, title=title, body=body))
    finally:
        engine.dispose()


def reset_demo_data(*, confirm: bool) -> None:
    """Delete only demo fixture rows after validating the local target and extra notes."""
    if not confirm:
        raise DemoSafetyError("Reset requires the --confirm-demo-reset flag.")

    database_url = _demo_database_url()
    engine = create_database_engine(database_url)
    user_ids = {user_id for user_id, _ in DEMO_USERS}
    note_ids = {note_id for note_id, _, _, _ in DEMO_NOTES}
    expected_emails = dict(DEMO_USERS)
    expected_note_owners = {note_id: owner_id for note_id, owner_id, _, _ in DEMO_NOTES}
    try:
        with Session(engine) as session, session.begin():
            _lock_demo_fixture(session)
            locked_users = session.scalars(
                select(User).where(User.id.in_(user_ids)).with_for_update()
            ).all()
            for user in locked_users:
                if user.email != expected_emails[user.id]:
                    raise DemoSafetyError("A demo user ID is already used by another identity.")

            notes = session.scalars(
                select(Note).where(Note.owner_id.in_(user_ids)).with_for_update()
            ).all()
            if any(note.id not in note_ids for note in notes):
                raise DemoSafetyError(
                    "A demo user owns non-demo notes; refusing to remove that user's data."
                )

            for note_id, _, _, _ in DEMO_NOTES:
                note = session.get(Note, note_id)
                if note is not None and note.owner_id != expected_note_owners[note_id]:
                    raise DemoSafetyError("A demo note ID is already owned by another user.")
                if note is not None:
                    session.delete(note)

            for user_id, email in DEMO_USERS:
                user = session.get(User, user_id)
                if user is not None and user.email == expected_emails[user_id]:
                    session.delete(user)
    finally:
        engine.dispose()


def build_parser() -> argparse.ArgumentParser:
    """Build the seed/reset command-line interface."""
    parser = argparse.ArgumentParser(description="Manage fictional local AuthEdu demo records.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("seed", help="create missing deterministic demo records")
    reset_parser = commands.add_parser("reset", help="remove only the deterministic demo records")
    reset_parser.add_argument(
        "--confirm-demo-reset",
        action="store_true",
        help="confirm deletion of the fictional demo records from the configured local database",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the requested operation and report configuration conflicts safely."""
    arguments = build_parser().parse_args(argv)
    try:
        if arguments.command == "seed":
            seed_demo_data()
            print("Fictional demo users and notes are present.")
        else:
            reset_demo_data(confirm=arguments.confirm_demo_reset)
            print("Fictional demo records were removed.")
    except (DemoSafetyError, RuntimeError) as error:
        print(f"error: {error}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
