# Project structure

AuthEdu separates HTTP transport, authentication/session operations, and shared
security helpers. The layout is intentionally small: it introduces no repository
framework, generic CRUD layer, or empty packages for unimplemented features.

## Repository areas

- [backend](../backend/README.md): FastAPI application, persistence, migrations, and Python tests.
- [frontend](../frontend/README.md): React/Vite health screen and its component/configuration tests.
- [docs](local-development.md): setup, design decisions, and learner walkthroughs.
- [scripts/test-session-curl.sh](../scripts/test-session-curl.sh): optional local HTTPS API smoke test.
- [.github/workflows/ci.yml](../.github/workflows/ci.yml): automated checks.

## Backend responsibilities

| Area | Responsibility | Examples |
| --- | --- | --- |
| Application composition | App creation, lifespan, and middleware/handler/router registration | [main.py](../backend/src/authedu_api/main.py) |
| HTTP adapters | Request/response handling, cookies, Origin checks, HTTP error mapping | [api/routes/sessions.py](../backend/src/authedu_api/api/routes/sessions.py), [api/routes/registration.py](../backend/src/authedu_api/api/routes/registration.py), [api/routes/health.py](../backend/src/authedu_api/api/routes/health.py) |
| HTTP cross-cutting policy | Pre-validation registration throttling and password-safe validation errors | [api/middleware.py](../backend/src/authedu_api/api/middleware.py), [api/exception_handlers.py](../backend/src/authedu_api/api/exception_handlers.py) |
| Services | Registration persistence, credential verification, session issuance/resolution/revocation | [services/registration.py](../backend/src/authedu_api/services/registration.py), [services/sessions.py](../backend/src/authedu_api/services/sessions.py) |
| Shared helpers | Password hashing, CSRF proofs, normalized identity policy, bounded in-memory limiter | [core/passwords.py](../backend/src/authedu_api/core/passwords.py), [core/csrf.py](../backend/src/authedu_api/core/csrf.py), [core/identity.py](../backend/src/authedu_api/core/identity.py), [core/rate_limit.py](../backend/src/authedu_api/core/rate_limit.py) |
| Persistence | Database configuration, engine/session lifecycle, ORM definitions | [database.py](../backend/src/authedu_api/database.py), [models.py](../backend/src/authedu_api/models.py) |
| Public representations | Explicit request/response fields that exclude persistence-only credentials | [schemas.py](../backend/src/authedu_api/schemas.py) |
| Local data tooling | Guarded demo seed/reset CLI | [demo_data.py](../backend/src/authedu_api/demo_data.py) |

The dependency direction is **HTTP adapters → services/shared helpers → persistence**.
Shared helpers do not import routes or application composition. The existing
in-memory limiter still raises an HTTP rejection and remains a demo-only safeguard;
this restructuring is not a redesign of rate-limit policy.

Origin checking stays in the HTTP adapter because it inspects browser request
metadata. CSRF signing belongs in shared security code because its inputs are a
session token and a proof, independent of FastAPI's request object. Registration
and login use the same password hasher and dummy hash rather than maintaining
separate cryptographic instances.

## Stable interfaces and security boundaries

This restructuring does not change endpoints, response schemas, database tables,
dependencies, cookie attributes, CSRF formats, or transaction ownership. Registration
throttling still runs before body validation. Session rotation remains atomic,
and expiry checks still use the database clock with row locking.

The Uvicorn target remains `authedu_api.main:app`, and the CLI remains
`python -m authedu_api.demo_data`. Docker, Alembic imports, and CI discovery keep
their existing entrypoints. Internal Python imports use the new module locations;
the old flat registration and session modules are removed rather than re-exported.

## Tests and frontend growth

Python tests remain in the flat [backend/tests](../backend/tests/conftest.py) area
so migration fixture root paths and normal pytest discovery are unchanged. Service,
HTTP, and app-level integration tests retain their existing files. Pure helper
coverage is separated into [test_passwords.py](../backend/tests/test_passwords.py),
[test_csrf.py](../backend/tests/test_csrf.py), and
[test_rate_limit.py](../backend/tests/test_rate_limit.py).

The frontend currently has one small view in [App.jsx](../frontend/src/App.jsx).
It remains flat until the browser authentication task introduces meaningful feature
components. Add directories for real responsibilities, not speculative future code.

**Learning note:** folders make a request easier to trace, but do not enforce
security. Authorization checks, credential validation, and transaction rules must
still be enforced by the code and tested at their boundaries.