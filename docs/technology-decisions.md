# Foundation technology decisions

**Status:** Backend health slice merged; frontend health slice implemented on a feature branch and awaiting PR review.
**Reviewed:** 2026-11-01.
**Owner-approved targets:** FastAPI; PostgreSQL 18 with SQLAlchemy and Alembic; React/Vite; CPython 3.14.10; Node.js 26.13; `uv`; `npm`.

This decision record captures the approved targets and a dated compatibility check. The backend health-check slice has pinned dependencies in `backend/uv.lock`; its endpoint tests and local smoke test passed before merge. The frontend health slice now has pinned dependencies in `frontend/package-lock.json`, available/unavailable UI tests, and a Vite proxy to the backend health route. The database application layer is not yet scaffolded. Re-check the latest stable versions before each subsequent scaffold and commit corresponding lockfiles.

## Selected runtime and package-manager pins

| Component | Pin for implementation | Compatibility/status evidence |
| --- | --- | --- |
| CPython | **3.14.10** | Latest stable 3.14 patch on the review date, released 2026-10-25; 3.14 is in the supported bug-fix cycle through 2030-10. `uv` lists CPython 3.14 as Tier 1. FastAPI's current CI matrix tests 3.14. See [Python 3.14.10 release](https://www.python.org/downloads/release/python-31410/), [Python version status](https://devguide.python.org/versions/), [FastAPI CI matrix](https://github.com/fastapi/fastapi/blob/master/.github/workflows/test.yml), and [uv Python support](https://docs.astral.sh/uv/reference/policies/python/). |
| Node.js | **26.13.0 (Lithium LTS)** | Exact release is available in the official archive. It bundles npm 11.20.0. See [Node.js 26.13.0 archive](https://nodejs.org/en/download/archive/v26.13.0) and [Node.js release status](https://nodejs.org/en/about/previous-releases). |
| npm | **12.2.1** | Current stable npm CLI at review time; registry metadata declares Node `>=26.0.0`, so it is compatible with Node 26.13.0. Install/pin this CLI rather than relying on Node's bundled npm 11.20.0. See [npm release metadata](https://registry.npmjs.org/npm/latest) and [npm CLI docs](https://docs.npmjs.com/cli/). |
| uv | **0.13.6** | Current stable release at review time; uv lists CPython 3.14 and 3.15 as Tier 1 and provides a project lockfile. Commit `uv.lock`. See [uv documentation](https://docs.astral.sh/uv/) and [uv Python support](https://docs.astral.sh/uv/reference/policies/python/). |
| PostgreSQL image | **`postgres:18.6-bookworm`** | PostgreSQL 18.6 is the current supported 18.x minor at review time; the official Docker image publishes the exact Bookworm tag. PostgreSQL 18 is supported through 2030-11-14. See [PostgreSQL supported versions](https://www.postgresql.org/support/versioning/) and [official image tag](https://hub.docker.com/layers/library/postgres/18.6-bookworm/images/sha256-98f065bcb89e5506cd0277dd685fcb6693ec70dec7892d48b0586b460e0453d4). |

## Current stable library candidates

These are the newest non-prerelease versions found in the official package registries on the review date. They are candidate pins for the scaffold issue, not a fully resolved or tested lockfile.

| Area | Candidate versions | Compatibility note |
| --- | --- | --- |
| API | FastAPI **0.162.0**, Starlette **1.10.0**, Pydantic **2.14.2**, pydantic-core **2.50.2**, Uvicorn **0.54.0** | FastAPI's current package metadata supports Python `>=3.10` and classifies through 3.14; its upstream CI matrix tests Python 3.14/3.14 free-threaded. Uvicorn is used directly as the ASGI server to keep the runtime dependency footprint small instead of installing FastAPI's broad optional CLI bundle. These versions resolved and passed the health endpoint test on CPython 3.14.10. See [FastAPI PyPI metadata](https://pypi.org/project/fastapi/0.162.0/), [FastAPI CI matrix](https://github.com/fastapi/fastapi/blob/master/.github/workflows/test.yml), and [Uvicorn](https://pypi.org/project/uvicorn/0.54.0/). |
| Persistence/migrations | SQLAlchemy **2.1.6**, Alembic **1.20.1**, Psycopg **3.3.6** | Current registry metadata lists Python 3.14 support for these releases. SQLAlchemy documents PostgreSQL 18-specific support and a PostgreSQL dialect; Psycopg documents official support for Python 3.10–3.15 and PostgreSQL 10–18; Alembic documents PostgreSQL transactional DDL. See [SQLAlchemy PostgreSQL dialect](https://docs.sqlalchemy.org/en/21/dialects/postgresql.html), [Psycopg supported systems](https://www.psycopg.org/psycopg3/docs/basic/install.html#supported-systems), [Alembic](https://alembic.sqlalchemy.org/en/latest/), [SQLAlchemy](https://pypi.org/project/SQLAlchemy/2.1.6/), and [Psycopg binary distribution](https://pypi.org/project/psycopg-binary/3.3.6/). |
| Backend baseline checks/build | pytest **9.2.0**, HTTPX **0.28.1**, Ruff **0.17.3**, uv-build **0.13.6** | pytest and Ruff list Python 3.14 in registry classifiers. The health contract uses HTTPX `ASGITransport` directly (rather than deprecated Starlette `TestClient` integration). These pinned tools resolved and passed in the backend environment. See [pytest](https://pypi.org/project/pytest/), [HTTPX](https://pypi.org/project/httpx/), [Ruff](https://pypi.org/project/ruff/), and [uv-build](https://pypi.org/project/uv-build/0.13.6/). |
| Frontend | React **19.3.1**, React DOM **19.3.1**, Vite **8.3.5**, `@vitejs/plugin-react` **6.1.2**, Vitest **5.0.5** | Vite, its React plugin, and Vitest support Node 26.13.0. See [React](https://www.npmjs.com/package/react), [React DOM](https://www.npmjs.com/package/react-dom), [Vite](https://vite.dev/guide/), [Vite React plugin](https://www.npmjs.com/package/@vitejs/plugin-react), and [Vitest](https://vitest.dev/). |

Versions in this table are a snapshot, not an instruction to upgrade automatically. Before each new dependency manifest or lockfile is generated, check official release metadata again and resolve a compatible set. For the backend health slice, exact dependency pins are in `backend/pyproject.toml` and the complete transitive resolution is in `backend/uv.lock`. Frontend direct dependency pins are in `frontend/package.json`, with the complete transitive resolution in `frontend/package-lock.json`.

## Baseline command interface

The scaffold defines and documents these repeatable backend checks:

- Backend: `uv run ruff check .` and `uv run pytest`.
- Frontend: `npm run lint`, `npm test`, and `npm run build` (scripts to be defined by the frontend scaffold).

Backend checks were run on CPython 3.14.10 in issue #2: `uv sync --locked`, `uv run --locked ruff check .`, and `uv run --locked pytest` all passed; a local `GET /health` smoke test returned HTTP 200 with `{"status":"ok"}`. Frontend checks are `npm run lint`, `npm test`, and `npm run build`; all passed on Node 26.13.0/npm 12.2.1, with zero npm audit advisories after pinning a patched transitive minimatch release. The Vite proxy was smoke-tested against the backend health route.

## Compatibility decision

The project owner explicitly replaced the earlier CPython 3.15.2 preference with **CPython 3.14.10**. FastAPI's current supported-Python classifier and official test matrix include Python 3.14, so this resolves the previously identified support-evidence blocker. Python 3.14 and the other runtime/package-manager targets are supported as of this dated review. During issue #2, recheck latest patch/package versions, resolve dependencies, commit the lockfiles, and run tests on the exact environment; this decision record is not a substitute for that integration verification.

## Baseline rationale

This stack matches the product plan's intended educational architecture: FastAPI for a readable Python API; PostgreSQL with SQLAlchemy and Alembic for persistent, migration-backed state; React/Vite for a small browser demo; `uv` and `npm` for reproducible language-specific dependency workflows. Exact pins make the initial foundation repeatable, while explicit support evidence prevents “latest” from becoming an untested compatibility assumption.
