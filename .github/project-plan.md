# AuthEdu — Runnable Authentication and Authorization Reference

## Project Goal

Build an educational GitHub repository demonstrating how authentication and authorization are implemented in real applications, using a Python backend and React frontend.

Each example should run locally, expose readable implementation code, and include a guided explanation of its request flow, credential lifecycle, security controls, and tradeoffs.

The goal is to help learners understand, compare, and implement these mechanisms—not to provide intentionally vulnerable labs or a production identity service.

## Intended Audience and Learning Outcomes

The primary audience is developers who understand basic HTTP and application development but want to learn how security mechanisms work beyond framework configuration.

Learners should be able to:

- Trace registration, login, authenticated requests, expiration, refresh, and logout from browser to backend and database.
- Distinguish authentication, credential management, delegated authorization, and application authorization.
- Understand where credentials are stored, how they are validated, and which state remains server-side.
- Compare session and JWT approaches using the same application and protected resources.
- Implement and test role permissions and resource ownership on the backend.
- Explain each implementation's guarantees, limitations, and deployment requirements.

## Product Shape

Working implementations are the product. Documentation, diagrams, and a small shared demo UI explain them.

This is a runnable reference repository, not a full interactive learning platform. Prioritize understandable code and complete examples over visual tooling or abstraction frameworks.

The examples should be security-conscious and secure by default within their documented assumptions. They are not independently audited or certified production identity infrastructure.

## Security Concepts and Their Relationships

These mechanisms solve different problems and are not interchangeable login methods.

| Category | Examples | Question answered |
| --- | --- | --- |
| Authentication | Passwords, passkeys | How is identity established? |
| Session and credential management | Server-side sessions, JWT access tokens | How are subsequent requests authenticated? |
| Delegated authorization | OAuth | How can an application access another service on someone's behalf? |
| Federated authentication | OpenID Connect (OIDC) | How can an application trust another provider's identity assertion? |
| Additional verification | TOTP MFA | What additional evidence is required? |
| Application authorization | Ownership, RBAC, ABAC | What may this identity do? |

JWT is a token format, not a standalone authentication protocol. OAuth does not by itself define user authentication; OIDC adds an identity layer. Neither replaces application-level resource authorization.

## First Release Scope

### Included

- Password registration and login.
- Server-side session authentication.
- JWT access tokens with refresh-token rotation.
- Role-based access control (RBAC) and resource ownership.
- A small React demonstration interface.
- Guided tutorials, sequence diagrams, comparisons, and automated tests.
- Reproducible local setup and GitHub CI.

### Explicitly Out of Scope

- Intentionally vulnerable implementations, attack toggles, and exploit labs.
- Quizzes, challenge modes, sandbox environments, and elaborate inspectors.
- Building an OAuth authorization server or OIDC provider.
- MFA, passkeys, and other later modules in the first release.
- A general-purpose authentication framework or plugin architecture.
- Production deployment support or claims of production readiness.

Common mistakes may be explained in documentation and addressed through rejection tests. Shipping insecure variants is not part of the current project goal; no lab scaffolding is needed.

## Recommended Implementation Stack

Python backend and React frontend are project requirements. The following choices are recommendations for keeping the implementation approachable:

| Responsibility | Recommendation |
| --- | --- |
| Backend | FastAPI |
| Persistence | PostgreSQL, SQLAlchemy, migrations |
| Frontend | React with Vite |
| Local environment | Docker Compose and a documented local HTTPS setup |
| Documentation | Repository Markdown and Mermaid diagrams |
| Backend tests | pytest and httpx |
| Browser tests | Playwright |
| Automation | GitHub Actions |

Use PostgreSQL for session and refresh-token records; Redis is not required for the first release. Select one maintained library per security responsibility and verify its maintenance status when implementation begins. Do not implement cryptographic primitives manually.

## Shared Demonstration Application

Build a small notes application:

- Users can create, read, update, and delete their own notes.
- An admin-only endpoint lists users.
- Session and JWT examples protect the same resources.
- Role permissions and note ownership are separate checks.
- Admin status does not silently bypass note ownership.

This provides concrete demonstrations of both role-based and object-level access control without introducing a large business domain.

### Architecture Principles

- Both authentication approaches produce a trusted principal consumed by shared authorization checks.
- Derive identity from validated credentials, never client-submitted user IDs or roles.
- Share users, notes, password hashing, persistence, and policy checks.
- Keep session and JWT credential flows explicit and separately readable.
- Enforce authorization on the backend for every protected operation; frontend visibility is not an access-control boundary.
- Use one active demonstration method at a time. Switching methods clears frontend authentication state and requires a fresh login; do not silently fall back between cookies and bearer tokens.
- Prefer a same-origin browser/API arrangement through a local proxy. Document local TLS configuration and any development exceptions instead of silently disabling secure cookies.

## Definition of Done for Every Module

A module is complete only when it includes:

1. **Runnable implementation:** reproducible setup, prerequisites, and seed/reset instructions.
2. **Concept explanation:** the problem solved, actors, trust boundaries, suitable use cases, and relationship to other modules.
3. **Sequence diagram and code walkthrough:** documentation linked to the actual implementation.
4. **Credential lifecycle:** issuance, storage, transport, validation, expiration, renewal, logout/revocation, and recovery where applicable.
5. **Security guarantees and limitations:** controls, assumptions, common mistakes, and deployment caveats.
6. **Automated tests:** successful flows and rejected invalid or unauthorized requests.
7. **Comparison entry and learner exercise:** meaningful tradeoffs and a guided task to inspect or modify secure behavior.

Mark operations as not applicable when necessary rather than forcing every mechanism into identical login/logout semantics. Write educational material alongside code, not after all features are implemented.

## Development Roadmap

### Phase A — Runnable Foundation

**Deliverables**

- Python backend, React frontend, and PostgreSQL setup.
- Database migrations and repeatable sample-data reset.
- Environment configuration examples without committed secrets.
- Users, password hashing with Argon2id, registration validation, and database-enforced uniqueness.
- Notes and shared principal/authorization interfaces.
- A small frontend for registration, login, notes, and an admin view.
- Basic credential-endpoint throttling and generic login errors.
- Developer documentation and initial CI checks.

**Completion gate:** A fresh checkout starts deterministically, applies migrations, seeds data, and passes initial tests without requiring live third-party credentials.

### Phase B — Sessions and Authorization

Depends on Phase A. Build the first complete educational vertical slice.

**Session implementation**

- Cryptographically random opaque session identifiers.
- Hashed server-side session records.
- Server-enforced idle and absolute expiration.
- Session identifier rotation at login and relevant privilege transitions.
- Secure, HttpOnly cookies with an appropriate SameSite policy.
- CSRF protection for state-changing cookie-authenticated requests, including appropriate login defenses.
- Server-side logout invalidation.

**Authorization implementation**

- Deny-by-default role-to-permission checks.
- Ownership checks on every note read, update, and delete operation.
- No client-controlled privilege assignment.
- Documented behavior for missing credentials, insufficient permissions, and inaccessible resources, including chosen 401/403/404 responses.

**Educational deliverables**

- Session and authorization walkthroughs.
- Browser-to-backend-to-database sequence diagrams.
- Guided exercises and happy-path/rejection tests.

**Completion gate:** Users can register, log in, manage only their notes, and log out. Expired sessions, invalid CSRF requests, cross-user access, and unauthorized admin requests are rejected.

### Phase C — JWT Comparison and First Release

Depends on Phase B. Reuse the same application and authorization policies.

**JWT implementation**

- Short-lived signed access tokens validated with a maintained library.
- Explicit allowed algorithms and validation of signature, issuer, audience, expiration, and required claims.
- Access tokens held in React memory and sent as Authorization bearer credentials, not persisted in localStorage or sessionStorage.
- A refresh flow to obtain a new access token after browser reload.
- Opaque refresh tokens in a path-restricted Secure, HttpOnly cookie.
- Hashed server-side refresh records, expiration, transactional single-use rotation, and token-family reuse detection and revocation.
- CSRF protection for refresh and logout endpoints.

**Logout semantics**

Logout clears frontend credentials and revokes the refresh-token family. Previously issued access tokens remain valid until expiration. Immediate access-token revocation is outside the first-release scope.

Document this limitation explicitly. The overall system is not completely stateless because refresh-token lifecycle management retains server-side state.

**Educational deliverables**

- JWT issuance, validation, refresh, and logout walkthroughs.
- Sequence diagrams and a session-versus-JWT comparison.
- Minimal non-sensitive credential status displays.
- Backend and browser tests, complete first-release documentation, and CI.

Documentation and backend tests can develop alongside implementation; final browser tests depend on the completed flows.

**Completion gate:** Both approaches enforce the same resource policies. Tampered or expired tokens, wrong issuer/audience, refresh-token reuse, and unauthorized access are rejected. A fresh-clone tutorial walkthrough succeeds.

### Phase D — Subsequent Modules

Add one independently complete module at a time. These are expansion directions, not first-release commitments.

#### OAuth Delegation and OIDC Login

- Act as an OAuth client and OIDC relying party using an established provider; do not build a provider.
- Prefer a maintained local provider for reproducible learning, with optional hosted-provider instructions later.
- Demonstrate delegated API access separately from federated identity.
- Cover authorization code flow, PKCE, state validation, redirect handling, and nonce where applicable.
- Consume discovery/JWKS and verify ID tokens rather than merely decoding them.
- Explain local application logout versus provider logout.
- Define account mapping and linking safely; do not automatically link identities based only on unverified email addresses.

#### TOTP Multi-Factor Authentication

- Enrollment confirmation and a pending first-factor state.
- Second-factor verification before authenticated access is granted.
- Verification throttling, encrypted TOTP secret storage, and hashed single-use recovery codes.
- Explicit rules for disabling MFA and account recovery.
- Explain that TOTP is not phishing-resistant.

#### WebAuthn and Passkeys

- Use a maintained verification library.
- Cover RP ID/origin checks, expiring single-use challenges, registration, and authentication.
- Support credential lifecycle explanations, multiple credentials, removal, and recovery.
- Document browser and local HTTPS requirements.
- Explain that passkeys may be synced or device-bound.

#### Optional Later Additions

- Magic links with single-use expiration and a local mail service.
- API keys and service credentials.
- ABAC using subject, resource, action, and environment attributes.

Each addition must satisfy the module definition of done before another is started.

## Educational Visibility and Safety

Prefer sequence diagrams, browser developer tools, redacted examples, and non-sensitive status displays.

- Do not expose session identifiers, refresh tokens, password hashes, secrets, or bearer credentials through educational endpoints or logs.
- HttpOnly cookies are deliberately unreadable to React; teach this property rather than work around it.
- A JWT decoder illustrates claims, but decoding alone does not establish validity. Only a verified token should be described as trusted.
- Keep credentials out of screenshots, test artifacts, and CI output.

## Verification Strategy

### Backend Tests

Use pytest/httpx and disposable PostgreSQL integration environments to verify:

- Password verification and registration rules.
- Session expiration, rotation, and invalidation.
- CSRF enforcement.
- JWT signature, issuer, audience, and expiration validation.
- Refresh-token rotation and reuse handling, including transactional behavior.
- Role permissions and note ownership.
- Rejection of forged identities and privilege assignments.

These tests validate protections; they do not require intentionally vulnerable implementations.

### Browser Tests

Use Playwright to cover:

- Registration and session login/logout.
- JWT login, refresh after reload, and logout.
- Note ownership and admin restrictions.
- Explicit authentication-method switching.
- Cookie attributes and the absence of tokens in persistent browser storage.

### CI Checks

- Backend/frontend linting and appropriate type checks.
- Unit, integration, and browser tests.
- Dependency vulnerability auditing and secret scanning.
- Credential redaction in output and artifacts.

### Educational Acceptance Test

From a fresh checkout:

1. Follow documented startup and seed/reset instructions.
2. Complete each first-release tutorial.
3. Compare a sequence diagram against actual requests.
4. Identify where authentication and authorization occur in the code.
5. Explain credential storage, expiration, and logout behavior for both approaches.

## First Release Acceptance Criteria

- Session, JWT, and authorization examples meet the module definition of done.
- The same protected resources demonstrate both authentication approaches.
- Core protections are documented and tested.
- Local setup is reproducible without hosted services.
- No vulnerable modes, attack toggles, or secret-exposing inspectors are included.
- Limitations and deployment caveats are explicit.

**Success means a learner can run an example, trace its implementation, explain its guarantees, and understand when to choose it.**
