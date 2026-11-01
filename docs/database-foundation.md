# Database foundation learning notes

AuthEdu uses SQLAlchemy models as application mappings and Alembic revisions as the authoritative history of database changes. Model edits alone do not change a running database: a reviewed migration must describe both the forward change and, when practical, its reversal.

## Initial schema

- `users.email` has a unique expression index on `lower(email)`, so case variants cannot create separate identities. Future registration validation must still trim and normalize input consistently before storage.
- `users.password_hash` is nullable and reserved for encoded hashes only. This foundation does not add authentication or generate hash values.
- `notes.owner_id` is non-null and references `users.id`; PostgreSQL enforces ownership references even if application code has a bug. Cascading deletion is a data-retention choice, not an authorization decision.
- `notes.updated_at` is timezone-aware, initialized by a PostgreSQL default, and refreshed by SQLAlchemy when an ORM update changes a note. The migration's default also populates pre-existing notes on upgrade. Direct SQL writes bypass SQLAlchemy's `onupdate` behavior, so a later design can move timestamp enforcement into a PostgreSQL trigger if all database writers must be covered.
- API representations are explicit Pydantic schemas. ORM objects should not be serialized directly because they contain persistence-only fields.

## Transaction and resource lifecycle

One SQLAlchemy engine owns the connection pool for the application process. The FastAPI lifespan creates it only when `DATABASE_URL` exists and disposes it at shutdown. Request dependencies own short-lived sessions. A session is closed after the request; successful changes require an explicit commit, and uncommitted changes roll back on close. Authentication and authorization remain separate future layers—the foreign key establishes data integrity but does not decide which principal may read a note.

## Verify migrations

With Docker available, from `backend/` run `uv run --locked pytest`. A session-scoped PostgreSQL 18.6 container hosts a unique database for each test. Each database starts from the committed migration history and is dropped in teardown. The migration test runs `upgrade head`, `downgrade base`, and `upgrade head` again. The local Compose database uses a separate persistent volume and is never used by these tests.

Follow-up exercise: update a note through direct SQL and inspect `updated_at`. Why does SQLAlchemy's `onupdate` not run? Sketch how a PostgreSQL trigger could make direct SQL and ORM updates follow the same rule, and identify what the trigger migration's downgrade should remove.
