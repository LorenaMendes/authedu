# Initial GitHub Backlog

This is the planning seed for **AuthEdu Development**. The first three starter tasks are live as [#1 — foundation technology decisions](https://github.com/LorenaMendes/authedu/issues/1), [#2 — Python API health service](https://github.com/LorenaMendes/authedu/issues/2), and [#3 — frontend health screen](https://github.com/LorenaMendes/authedu/issues/3). Issue #1 is complete using CPython 3.14.10, which is covered by FastAPI's official test matrix; issue #2 is merged, and issue #3 is in implementation/review. See [the technology decision record](technology-decisions.md). The epics and remaining foundation tasks below are not yet live issues. Map or refine them against the starter issues before publishing so work is not duplicated.

**Milestone for all items below:** v0.1 — Sessions, JWT, and Authorization.

Identifiers such as F1 and E1 are local planning references, not GitHub issue numbers. Replace them with real issue links after publication. Assign issues when someone starts owning them; do not assume an account name.

## Summary

| ID | Title | Parent | Initial status | Priority | Size |
| --- | --- | --- | --- | --- | --- |
| E1 | Runnable foundation | — | Backlog | P0 | — |
| E2 | Session authentication | — | Backlog | P0 | — |
| E3 | Application authorization | — | Backlog | P0 | — |
| E4 | JWT authentication and comparison | — | Backlog | P0 | — |
| F1 | Scaffold Python backend and React frontend | E1 | Ready | P0 | M |
| F2 | Configure PostgreSQL and migrations | E1 | Backlog | P0 | M |
| F3 | Add reproducible local startup and HTTPS | E1 | Backlog | P0 | M |
| F4 | Add deterministic sample-data seed and reset | E1 | Backlog | P0 | M |
| F5 | Configure initial backend and frontend CI | E1 | Backlog | P0 | M |
| F6 | Document and verify fresh-checkout onboarding | E1 | Backlog | P0 | S |

Sizes are provisional. Split a task if implementation reveals multiple independently reviewable outcomes.

## Epics

### E1 — Runnable foundation

**Labels:** `type:epic`, `area:infra`.

**Outcome:** A contributor can start a Python/React application with persistent storage and follow reproducible development instructions.

**Scope:** Backend/frontend skeleton, PostgreSQL migrations, local startup/HTTPS, initial demo models and sample data, developer commands, and initial CI. Authentication and authorization behavior belongs to E2/E3.

**Completion gate:**

- [ ] A fresh checkout starts without hosted-service credentials.
- [ ] Database migrations and seed/reset instructions work reproducibly.
- [ ] The frontend reaches the backend through the documented local arrangement.
- [ ] Initial checks pass locally and in GitHub Actions.
- [ ] Configuration examples contain no live secrets.
- [ ] No security-sensitive placeholder endpoints are mistaken for working authentication.

**Sub-issues:** F1–F6. No prerequisite epic.

### E2 — Session authentication

**Labels:** `type:epic`, `module:sessions`, `area:backend`, `area:frontend`, `area:docs`.

**Outcome:** A learner can trace password registration, session login, authenticated requests, expiration, and logout in working code.

**Scope:** Argon2id password hashing, registration validation, generic login failures, credential throttling, opaque session issuance, hashed session storage, idle/absolute expiration, rotation, cookie security, CSRF protection, UI flows, tests, and a walkthrough/diagram.

**Exclusions:** Vulnerable variants, MFA, federated login, and elaborate credential inspectors.

**Completion gate:**

- [ ] Registration and login work with documented validation and uniqueness rules.
- [ ] Session lifetime, rotation, validation, and logout invalidation are enforced server-side.
- [ ] Secure/HttpOnly/SameSite cookie choices and local HTTPS requirements are explained.
- [ ] Missing/invalid CSRF, invalid credentials, and expired/revoked sessions are rejected by tests.
- [ ] Browser flows, tutorial, and sequence diagram match the implementation.
- [ ] Credentials do not appear in logs or educational endpoints.

**Dependencies:** E1. Refine implementation sub-issues once the foundation is established.

### E3 — Application authorization

**Labels:** `type:epic`, `module:authorization`, `area:backend`, `area:frontend`, `area:docs`.

**Outcome:** A learner can distinguish validated identity from backend access decisions and observe role and ownership enforcement.

**Scope:** Trusted principal, role-to-permission checks, notes CRUD with ownership enforcement, admin-only user listing, documented 401/403/404 behavior, demo UI, tests, and a tutorial.

**Exclusions:** ABAC, implicit administrator bypass of note ownership, and client-controlled role assignment.

**Completion gate:**

- [ ] Every note operation enforces ownership on the backend.
- [ ] Admin-only user listing checks trusted role permissions.
- [ ] Authorization is deny-by-default and does not trust submitted identity or privilege fields.
- [ ] Cross-user reads, updates, deletes, and unauthorized admin access are rejected.
- [ ] The tutorial traces credential validation into a principal and then into a policy decision.
- [ ] A session-authenticated end-to-end learner flow passes.

**Dependencies:** E1; the complete learner flow requires E2. Policy design/tests may proceed alongside E2 once shared interfaces exist.

### E4 — JWT authentication and comparison

**Labels:** `type:epic`, `module:jwt`, `area:backend`, `area:frontend`, `area:docs`.

**Outcome:** A learner can run token-based request authentication against the same protected resources and explain its differences from sessions.

**Scope:** Short-lived signed access tokens, strict validation, memory-only browser access-token storage, opaque refresh cookies, hashed refresh records, transactional rotation/reuse detection, CSRF defenses, logout, browser reload handling, tests, and comparisons.

**Exclusions:** Immediate access-token revocation, a claim of fully stateless lifecycle management, custom cryptography, and insecure modes.

**Completion gate:**

- [ ] Algorithm, signature, issuer, audience, expiration, and required claims are validated.
- [ ] Refresh-token rotation is single-use and transactional; detected reuse revokes its token family.
- [ ] Browser reload obtains a new access token through the protected refresh flow.
- [ ] Tokens are not persisted in localStorage/sessionStorage or exposed through inspection endpoints.
- [ ] Logout clears frontend credentials and revokes refresh credentials; remaining access-token lifetime is documented.
- [ ] Session and JWT methods enforce identical note/admin policies.
- [ ] Rejection tests, browser flows, walkthrough, diagram, and comparison are complete.

**Dependencies:** E2 and E3 as the comparison baseline. Refine detailed tasks when that baseline is usable.

## Foundation Implementation Tasks

### F1 — Scaffold Python backend and React frontend

**Parent:** E1. **Labels:** `type:chore`, `area:backend`, `area:frontend`.

**Goal:** Establish a minimal runnable codebase without pretending authentication is already implemented.

**Scope:** Confirm FastAPI and React/Vite recommendations; create backend/frontend dependency configuration, a health endpoint, a frontend health view, and baseline test/lint commands. Pin runtime requirements and provide a non-secret configuration example.

**Acceptance criteria:**

- [ ] Backend and frontend dependencies install using documented commands and reproducible dependency records.
- [ ] A backend health endpoint returns a predictable result with no credential data.
- [ ] The frontend renders backend availability and handles an unavailable backend.
- [ ] Baseline tests and lint checks run for both components.
- [ ] No fake login, insecure mode, or hard-coded credentials are introduced.

**Dependencies:** None.

**Verification:** Install from a clean environment, start each component, exercise the health view, and run baseline checks.

### F2 — Configure PostgreSQL and migrations

**Parent:** E1. **Labels:** `type:chore`, `area:backend`, `area:infra`.

**Goal:** Establish persistent storage and a versioned schema for later authentication and authorization work.

**Scope:** Database configuration, SQLAlchemy session handling, migration tooling, and initial User/Note tables with ownership relationship. Reserve password storage for hashes, never plaintext; authentication behavior is implemented in E2. Prevent accidental exposure of sensitive model fields in API serialization.

**Acceptance criteria:**

- [ ] A new PostgreSQL database migrates to the current schema.
- [ ] The schema enforces user identity uniqueness and valid note ownership relationships.
- [ ] Database sessions have documented transaction and cleanup behavior.
- [ ] Integration tests use disposable PostgreSQL, not a developer's data.
- [ ] Database credentials are supplied through configuration, not committed literals.

**Dependencies:** F1.

**Verification:** Apply migrations to a fresh database and test persistence, uniqueness, and relationships.

### F3 — Add reproducible local startup and HTTPS

**Parent:** E1. **Labels:** `type:chore`, `area:infra`.

**Goal:** Run the demo locally with a browser/API arrangement compatible with secure cookies.

**Scope:** Docker Compose, service health checks, same-origin proxying, documented local TLS certificate generation/trust, environment examples, and start/stop commands.

**Acceptance criteria:**

- [ ] Documented commands start backend, frontend, PostgreSQL, and the required proxy arrangement.
- [ ] The browser reaches the API under the documented same-origin HTTPS setup.
- [ ] Local TLS prerequisites and manual trust steps are explicit; certificate private keys are ignored by version control.
- [ ] Startup waits appropriately for database readiness or fails with an actionable error.
- [ ] No hosted identity provider or live secret is required.
- [ ] Any development exception is explicit rather than silently disabling secure-cookie behavior.

**Dependencies:** F1 and F2.

**Verification:** Follow the setup on a fresh environment, verify the browser-to-backend request, then stop and restart without losing persisted data.

### F4 — Add deterministic sample-data seed and reset

**Parent:** E1. **Labels:** `type:chore`, `area:backend`.

**Goal:** Give every learner the same reproducible data without endangering non-demo databases.

**Scope:** Seed at least two distinct users and owned notes; add an admin persona once its role schema is available. Provide development-only seed/reset operations. If local demo passwords are needed, generate hashes using the same Argon2id helper used by E2; never insert plaintext password values into database records.

**Acceptance criteria:**

- [ ] Repeated seeding does not create duplicate records.
- [ ] Notes belong to distinct users for later cross-user rejection tests.
- [ ] Reset is explicitly destructive and restricted to the configured local demo environment.
- [ ] Fixtures contain no real personal data or credentials.
- [ ] Sample account behavior and any temporary inability to log in before E2 are documented.

**Dependencies:** F2 and F3. Coordinate hash helper and role fixtures with E2/E3 rather than duplicating security code.

**Verification:** Seed twice, compare resulting records, reset the disposable demo database, and recreate the same fixtures.

### F5 — Configure initial backend and frontend CI

**Parent:** E1. **Labels:** `type:chore`, `area:infra`.

**Goal:** Automatically catch baseline regressions on pull requests and default-branch changes.

**Scope:** GitHub Actions for backend/frontend installation, linting, applicable type checks, tests, frontend build, and disposable PostgreSQL integration tests. Configure dependency auditing and secret detection with maintained tooling as appropriate.

**Acceptance criteria:**

- [ ] Checks run on pull requests and pushes to the default branch.
- [ ] The pipeline executes the same documented baseline checks used locally.
- [ ] Integration tests use an isolated database.
- [ ] Broken checks fail the pipeline rather than being silently ignored.
- [ ] Workflow permissions are minimal; credentials are not emitted in logs/artifacts.
- [ ] Browser security-flow checks have a documented extension point for E2–E4, not a claim of existing coverage.

**Dependencies:** F1 and F2; remote verification requires a published repository.

**Verification:** Observe a passing remote run and confirm a deliberately failing ordinary test fails its check, then remove the test change.

### F6 — Document and verify fresh-checkout onboarding

**Parent:** E1. **Labels:** `type:docs`, `area:docs`.

**Goal:** Enable a learner to start and reset the foundation without undocumented knowledge.

**Scope:** Repository landing page, prerequisites, architecture overview, install/start/stop/test commands, TLS setup, sample-data behavior, troubleshooting, and links to the project plan and contribution workflow.

**Acceptance criteria:**

- [ ] A fresh-checkout walkthrough works using only published instructions.
- [ ] Instructions cover migrations, startup, seed/reset, and checks.
- [ ] Missing configuration and local certificate issues have actionable guidance.
- [ ] Authentication features not implemented yet are clearly distinguished from current functionality.
- [ ] The project's educational scope and non-production limitations are explicit.

**Dependencies:** F3, F4, and F5.

**Verification:** Perform the entire documented walkthrough in a clean directory/environment and record its result in the issue.

## Publication Checklist

- [x] Restore GitHub access without sharing secrets in chat.
- [ ] Publish the local planning files to the existing repository.
- [ ] Create the milestone and labels.
- [ ] Create and configure the Project using the [workflow guide](github-workflow.md).
- [ ] Create E1–E4 and the remaining foundation tasks as issues, avoiding duplication of starter issues #1–#3; assign the milestone and add them to the Project.
- [ ] Attach F1–F6 as sub-issues of E1 and replace planning identifiers with actual links.
- [ ] Set initial status, priority, and size using the summary table.
- [ ] Start F1; refine only the next actionable tasks as implementation progresses.