# AuthEdu backend

The API includes a PostgreSQL-backed persistence layer, versioned schema, registration, and mounted cookie-backed session login/current-user/logout endpoints. Route and app-level integration tests exercise the session flow. Authorization and note endpoints are not implemented yet. `GET /health` reports process liveness and does not require PostgreSQL.

## Requirements

- CPython 3.14.10 (pinned in `.python-version`)
- uv 0.13.6 (required by `pyproject.toml`)
- Docker Engine and Docker Compose for PostgreSQL and persistence integration tests

Install uv using the [official instructions](https://docs.astral.sh/uv/getting-started/installation/), then run backend commands from `backend/`.

## First-time setup

Sync the exact dependency versions recorded in `uv.lock`:

```sh
uv sync --locked
```

To run a local PostgreSQL 18.6 service, create an untracked root `.env` file with `POSTGRES_DB`, `POSTGRES_USER`, and optionally `POSTGRES_PORT`. Store its password separately in `.secrets/postgres_password`, which Compose mounts as a read-only secret file for PostgreSQL. Generate a local password file with:

```sh
mkdir -p .secrets
python3 -c 'import secrets; print(secrets.token_urlsafe(32))' > .secrets/postgres_password
chmod 600 .secrets/postgres_password
```

Both `.env` and `.secrets/` are ignored by Git. Never commit or paste their contents into logs, screenshots, or examples.

From the repository root, start the database:

```sh
docker compose up -d postgres
```

Load the non-secret settings and construct the API connection URL from the generated URL-safe password, then apply migrations from `backend/`:

```sh
set -a; . ../.env; set +a
export DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:$(cat ../.secrets/postgres_password)@127.0.0.1:${POSTGRES_PORT:-5432}/${POSTGRES_DB}"
uv run --locked alembic upgrade head
```

`DATABASE_URL` is read by both the API and Alembic. Alembic commands fail with a generic configuration message if it is missing or uses another driver; credentials are not stored in `alembic.ini` or logged by SQLAlchemy. The generated password uses URL-safe characters. If you choose a different password, URL-escape special characters when constructing the connection URL. To reverse the initial schema in this local database, run `uv run --locked alembic downgrade base`. This drops the `users` and `notes` tables: do not run it where their data matters.

Compose stores local development data in a named volume. `docker compose down` stops the service and preserves that volume; deleting the volume is destructive. Integration tests do not use this service or its data.

## Check the code

```sh
uv run --locked ruff check .
uv run --locked pytest
```

Persistence tests require Docker and launch PostgreSQL 18.6 in a disposable Testcontainers instance. The fixture generates a process-local random password, creates a uniquely named database per test, applies the migrations, and drops the test database and container in teardown. Tests never read the local `.env`, connect to the local Compose service, or use developer data.

Pull requests run these checks and a strict audit of locked dependencies. See the [CI guide](../docs/continuous-integration.md) for identical local audit commands, failure behavior, and remote verification.

## Registration foundation

`POST /register` accepts a syntactically valid email and a password between 15 and 128 characters. Email input is trimmed and lowercased before storage, matching the database's case-insensitive uniqueness rule. Passwords are hashed with `argon2-cffi`'s high-level Argon2id `PasswordHasher`; salts and encoded hash parameters are managed by the library. Existing users created by the demo seed still have `password_hash = NULL` and cannot log in.

Duplicate and new email submissions receive the same `200` response so the endpoint does not explicitly disclose account existence. The server hashes before its atomic database insert on either path, which reduces—but cannot eliminate—timing differences. Invalid requests receive a generic `422` response that does not echo the submitted password.

Registration is limited to five attempts per direct peer address per ten-minute window using an in-memory, per-process limiter. Invalid payloads count too; throttling runs before request validation and before password hashing. To bound memory, the limiter tracks at most 10,000 client keys and evicts the least-recently-used key when full, so high client churn can reset an evicted client's quota. In the Compose setup, browser requests arrive through the shared Vite proxy, so they may all count against that proxy's address. The limiter resets on process restart, is not shared across workers or replicas, and can be evaded by distributed clients. The endpoint trusts the direct peer address and does not use forwarded-IP headers. Login also has a process-local per-IP limiter. These are educational safeguards, not production-ready defenses; deployment needs correctly configured trusted proxy handling and shared, abuse-resistant rate-limit storage. Account verification email, password recovery, and authorization are not implemented.

## Fictional demo records

With the full Compose stack running and `AUTHEDU_DEMO_MODE=1` added to the local, ignored `.env`, add the same fictional records used by the learner tests:

```sh
docker compose exec backend python -m authedu_api.demo_data seed
```

The command is idempotent: running it again does not duplicate or overwrite the demo records. It creates two fictional users with distinct owned notes. They have no password hashes and cannot log in.

The container puts `/opt/venv/bin` first on `PATH`, so `python` uses the installed app and dependencies. Each seed/reset process builds its database URL from the mounted password file and Compose settings when `DATABASE_URL` is absent: environment changes made by the API entrypoint are not inherited by a later `docker compose exec`. If an older image reports `No module named 'authedu_api'`, rebuild and recreate it with `docker compose up --build -d backend` before retrying.

Remove only these demo records (not the whole database) with an explicit confirmation:

```sh
docker compose exec backend python -m authedu_api.demo_data reset --confirm-demo-reset
```

Reset requires the explicit local demo-mode setting, a local Compose/loopback PostgreSQL host, an exact configured demo database name, and the confirmation flag. It refuses to delete records if the deterministic demo IDs conflict with another identity/owner or a demo user owns an extra non-demo note. Reset removes the seeded demo rows even if a learner edited their contents. Seed/reset operations serialize with a transaction-scoped PostgreSQL advisory lock. These are safety guards for local education—not a substitute for backups or production-grade environment isolation. Reset never uses database `DROP` operations.

## Start the full stack

For the recommended API, UI, PostgreSQL, and local HTTPS workflow, follow the repository's [local development guide](../docs/local-development.md). It starts all services in Compose and waits for database and API readiness.

## Start the API separately

With `DATABASE_URL` loaded, run:

```sh
uv run --locked uvicorn authedu_api.main:app --host 127.0.0.1 --port 8000
```

The API binds only to this computer at `http://127.0.0.1:8000`. To check it, open another terminal and run:

```sh
curl --fail http://127.0.0.1:8000/health
```

Expected response: `{"status":"ok"}`. The app creates its database engine during application lifespan only when `DATABASE_URL` is configured, and disposes that engine at shutdown. Request-scoped SQLAlchemy sessions are closed automatically; callers must commit explicitly, while closing an uncommitted session rolls its transaction back. The health endpoint remains available without a database because it measures process liveness, not dependency readiness.

## Data model and security boundary

The reversible migrations create `users`, `notes`, and `auth_sessions`, and add a timezone-aware `notes.updated_at` column. PostgreSQL initializes it for new notes and for existing rows when upgrading. SQLAlchemy refreshes it when an ORM update changes a note; direct SQL updates do not automatically refresh it. User email identity is protected by a database-enforced unique index over `lower(email)`; note ownership is a non-null foreign key with cascading deletion. New registrations require an Argon2id password hash; nullable hashes remain only for fictional demo users that cannot authenticate. Session records store only a digest of a random opaque identifier. The `UserRead` API schema explicitly lists public fields and excludes persistence-only fields. Registration and session endpoints are implemented; note endpoints and ownership authorization remain future work.

See [the technology decision record](../docs/technology-decisions.md) for stack compatibility details. This educational reference is not a production identity provider.
