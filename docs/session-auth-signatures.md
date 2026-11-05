# Session-authentication implementation notes (issue #23)

The session service, ORM model, migration, login/current-user/logout handlers, and route/app integration tests are implemented. The session router in [api/routes/sessions.py](../backend/src/authedu_api/api/routes/sessions.py) is mounted by [main.py](../backend/src/authedu_api/main.py). See [the directory guide](project-structure.md) for the separation between HTTP adapters, services, and security helpers.

## Suggested implementation order

1. Keep route and browser-flow tests current as frontend integration is added.

## Login handler

- `POST /login` and `POST /logout` require an exact match between the request `Origin` and configured `AUTHEDU_PUBLIC_ORIGIN`; absent or mismatched origins are rejected.
- Login attempts are limited to 10 per minute per direct client address using a bounded, process-local limiter. This is a learning/demo safeguard, not distributed production throttling; deployments behind proxies must configure trusted client-address handling before relying on IP limits.
- Credentials are verified with the dummy Argon2id path for missing/hashless users. All credential failures have the same 401 response.
- On success, any presented session is revoked, a fresh opaque session is created, and its raw value is set only in a Secure, HttpOnly, SameSite=Lax `__Host-` cookie. The response body contains the public user and CSRF proof, never the session cookie value.
- `LoginResponse` exposes the CSRF proof so the same-origin frontend can hold it in memory and send it in a custom header on state-changing authenticated requests.
- Authentication responses use `Cache-Control: no-store`; `GET /me` resolves the cookie through the session service and returns the authenticated user plus a fresh CSRF proof, allowing a page reload to recover in-memory CSRF state.
- `POST /logout` validates Origin and the session-bound `X-CSRF-Token` before revocation. A missing cookie is idempotent and still clears it; when a cookie exists, absent or invalid CSRF proof is rejected.

## Selected CSRF contract

- Authenticated state-changing requests use a stateless, session-bound HMAC proof. `issue_csrf_token()` returns `v1.<nonce>.<signature>` where the random nonce is signed with HMAC-SHA-256 over a versioned, domain-separated message containing the raw session cookie value and nonce.
- `validate_csrf_token()` checks the token version and format, recomputes the signature using the presented session cookie, and compares it with `hmac.compare_digest()`. The route must separately resolve the session and reject expired or revoked sessions; a CSRF proof is not authentication.
- Configure `AUTHEDU_CSRF_SECRET_FILE` to a mounted secret file (the Compose default), or inject `AUTHEDU_CSRF_SECRET` directly in a deployment that manages environment secrets. The key must contain at least 32 bytes of cryptographically random material. Never commit or log it. Changing this secret invalidates previously issued CSRF proofs.
- The frontend sends the proof in a custom request header; it never reads or sends the HttpOnly session cookie itself. The token is not stored in the database, so no migration is needed for this protocol.
- These helpers reject a missing session token. Login occurs before an authenticated session exists, so the login route uses the strict configured Origin check described above instead of these session-bound helpers.
- CSRF protection does not prevent XSS or session-token theft.

## Existing extension points

- `User.password_hash` and `AuthSession` are defined in [models.py](../backend/src/authedu_api/models.py); their database schema is managed by [Alembic migrations](../backend/alembic/versions/0003_auth_session.py).
- The shared Argon2id hasher and dummy verification hash live in [core/passwords.py](../backend/src/authedu_api/core/passwords.py), while HMAC CSRF helpers live in [core/csrf.py](../backend/src/authedu_api/core/csrf.py).
- Credential verification and session lifecycle logic live in [services/sessions.py](../backend/src/authedu_api/services/sessions.py), separate from [registration persistence](../backend/src/authedu_api/services/registration.py).
- Request-scoped SQLAlchemy sessions are supplied by `get_database_session()` in [database.py](../backend/src/authedu_api/database.py).
- Public request and response schemas are in [schemas.py](../backend/src/authedu_api/schemas.py).
- Origin checks, cookie handling, and HTTP error mapping stay in [api/routes/sessions.py](../backend/src/authedu_api/api/routes/sessions.py); [main.py](../backend/src/authedu_api/main.py) mounts the router.

## Review questions while implementing

- Does a missing user take a distinguishably cheaper password-verification path? How will you avoid revealing account existence without storing or logging a dummy plaintext credential?
- Is the presented cookie token ever stored raw, returned in JSON, or included in an exception/log?
- Are both idle and absolute expiration checked on every authenticated request using timezone-aware timestamps?
- Does logout validate the CSRF proof, invalidate the server-side row, and clear a cookie using the same path/security attributes as issuance?
- Does each state-changing route validate the CSRF proof and resolve the session before changing data?
- Are `AUTHEDU_PUBLIC_ORIGIN` and the CSRF signing secret configured before enabling session routes?
- Are privilege transitions in scope now? There is no role schema yet; document what is not applicable now and leave a clear rotation/invalidation hook for later.

## Existing test coverage

- [Session service tests](../backend/tests/test_session_service.py): credential verification, digest-only storage, expiry, activity refresh, revocation, and stale ORM-state rejection.
- [Session route tests](../backend/tests/test_session_routes.py): Origin checks, credential failures, cookies, CSRF, HTTP errors, and atomic rotation rollback.
- [Application integration test](../backend/tests/test_session_integration.py): registration → login → current-user lookup → logout using the real app and request-scoped database dependency.
- [CSRF tests](../backend/tests/test_csrf.py), [password tests](../backend/tests/test_passwords.py), and [rate-limit test](../backend/tests/test_rate_limit.py): shared security helper contracts.

HTTPX integration tests are not browser tests; browser cookie enforcement and frontend flows still need separate coverage.
