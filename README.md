# AuthEdu

AuthEdu is an educational reference for learning how authentication and authorization work in web applications. It favors readable implementations, tests, and explicit security boundaries over framework magic. **This repository is a work in progress, not a production identity provider or production-ready authentication service.**

## What works today

- A React/Vite health screen makes a same-origin request to the FastAPI health endpoint.
- PostgreSQL stores the initial `users` and `notes` schema; Alembic migrations run when the Compose backend starts.
- `POST /register` validates an email/password request and stores an Argon2id password hash; duplicate registrations receive a generic response.
- The HTTPS API supports cookie-backed login, current-session lookup, and CSRF-protected logout; session identifiers are opaque and stored only as digests.
- A guarded CLI creates and selectively removes repeatable fictional demo users and their notes.
- Backend/frontend checks, dependency audits, workflow validation, and secret scanning run in GitHub Actions.

## What is not implemented yet

Email verification, password recovery, JWT authentication, authenticated notes APIs, role-based authorization, and an admin UI are not implemented yet. Session login depends on configured local HTTPS, `AUTHEDU_PUBLIC_ORIGIN`, and a private CSRF signing key; its in-memory rate limiter is an educational safeguard, not suitable for production, multiple workers, or distributed deployments. The fictional demo users have no password hashes and cannot sign in. The health endpoint only reports that the API process responds; it does not prove that the database or authentication is working. See the [project plan](.github/project-plan.md) for what is planned. Do not treat the current app as a security product or use real personal data or credentials in its demo database.

## Start from a fresh checkout

If you have not cloned the repository yet:

```sh
git clone https://github.com/LorenaMendes/authedu.git
cd authedu
```

### Prerequisites

- Docker Engine and Docker Compose v2.
- Python 3 for generating a private local database password; use the pinned CPython version below when running backend checks outside Docker.
- `mkcert` to create a local HTTPS certificate. Install it using the [official instructions](https://github.com/FiloSottile/mkcert#installation). On Linux, install `libnss3-tools` if Firefox needs its own certificate trust database.
- For running backend/frontend checks outside Docker: CPython **3.14.10**, `uv` **0.13.6**, Node.js **26.13.0**, and npm **12.2.1**. See the [runtime decision record](docs/technology-decisions.md) for compatibility references; the component guides link to official installers.

### Configure local-only files

From the repository root, copy the example and create a private database-password file. `.env.example` contains non-secret local settings only; both `.env` and `.secrets/` are ignored by Git.

```sh
cp .env.example .env
mkdir -p .secrets
python3 -c 'import secrets; print(secrets.token_urlsafe(32))' > .secrets/postgres_password
python3 -c 'import secrets; print(secrets.token_urlsafe(48))' > .secrets/csrf_signing_key
chmod 600 .secrets/postgres_password
chmod 600 .secrets/csrf_signing_key
```

Install/trust mkcert's local certificate authority once for this computer and browser, then create a certificate for the exact local hosts:

```sh
mkcert -install
mkdir -p .certs && chmod 700 .certs
(umask 077; mkcert -cert-file .certs/localhost.pem -key-file .certs/localhost-key.pem localhost 127.0.0.1 ::1) &&
chmod 600 .certs/localhost-key.pem
``` 

The local certificate authority changes your user trust stores; never install it on a shared or production machine. The private key remains on your computer and is mounted read-only into the local frontend container.

### Start and check the application

```sh
docker compose up --build -d
```

Compose waits for PostgreSQL and API health before starting the HTTPS frontend. Open <https://localhost:5173> and accept only a certificate issued by your locally installed mkcert CA. The browser's `/api/health` request is proxied to the API on the private Compose network. To manually test registration, login, current-user lookup, and logout with `curl`, use the safe sequence in the [local development guide](docs/local-development.md#manually-test-session-routes-with-curl). Verify the API directly if useful:

```sh
curl --fail http://127.0.0.1:8000/health
```

Expected JSON: `{"status":"ok"}`. This HTTP loopback URL is for diagnostics, not cookie-authenticated browser work. For other ports, change `POSTGRES_PORT`, `API_HOST_PORT`, or `FRONTEND_HOST_PORT` in your ignored `.env` before startup.

The API container applies the committed Alembic migrations before starting. To apply or inspect migrations manually in a standalone backend setup, follow [backend migration setup](backend/README.md#first-time-setup).

### Seed and reset fictional demo records

With the Compose stack running and `AUTHEDU_DEMO_MODE=1` in `.env` (the example already enables this local-only flag), seed the same fictional records used in tests:

```sh
docker compose exec backend python -m authedu_api.demo_data seed
```

The command is idempotent. It creates two users, each owning a sample note; they have no password hashes and cannot log in. To remove **only** these demo records, run the explicitly confirmed reset command:

```sh
docker compose exec backend python -m authedu_api.demo_data reset --confirm-demo-reset
```

Reset deletes the seeded demo rows, including edited demo content. It refuses to run without demo mode, the expected local database, and the confirmation flag. The safety checks are educational safeguards, not production isolation or a backup strategy. See the [backend guide](backend/README.md#fictional-demo-records) for details.

### Stop the stack

```sh
docker compose down
```

This stops containers and **preserves** the local database volume. `docker compose down --volumes` permanently deletes the local PostgreSQL data and cached frontend dependencies; use it only when you intentionally want a full local reset.

## Run checks

Backend integration tests need Docker and use disposable, isolated PostgreSQL databases; they do not use the persistent Compose database. From `backend/`:

```sh
uv sync --locked
uv run --locked ruff check .
uv run --locked pytest --tb=short
```

From `frontend/`:

```sh
npm install --global npm@12.2.1
npm ci
npm run lint
npm test
npm run build
npm audit --audit-level=low
```

See the [CI guide](docs/continuous-integration.md) for the locked Python dependency audit, workflow linting, and secret-scanning commands. Full test and local TLS details are in the [local development guide](docs/local-development.md).

## Project and learning guides

- [Project goals, planned modules, and security principles](.github/project-plan.md)
- [Architecture and database foundation](docs/database-foundation.md)
- [Local setup, HTTPS, seed/reset, and troubleshooting](docs/local-development.md)
- [Continuous integration and security checks](docs/continuous-integration.md)
- [Technology pins and compatibility evidence](docs/technology-decisions.md)
- [GitHub workflow](docs/github-workflow.md)
- [AI engineering guide](docs/ai-engineering-guide.md)
- [Backend API setup and implementation notes](backend/README.md)
- [Frontend setup and health-screen behavior](frontend/README.md)

Guided session-authentication, authorization, and JWT tutorials and diagrams are **planned**; they are not present implementations. Current implementation notes describe the persistence and connectivity foundation only.

## Limitations

The project demonstrates security concepts for learning and is not independently audited or certified. Its local Compose/TLS configuration is development-only, not production deployment guidance. Review the [security scope and non-production limits](.github/project-plan.md#first-release-scope) before adapting examples for another system.
