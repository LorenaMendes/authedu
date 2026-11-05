# Local development environment

The supported full-stack development path uses Docker Compose for PostgreSQL, the FastAPI service, and the Vite development server. Open the frontend over local HTTPS; its `/api` proxy forwards requests to the backend over the private Compose network, so browser requests remain same-origin. Session login, current-user, and logout routes are available through this API proxy after the session migration and required secrets are configured.

## Prerequisites

- Docker Engine and Docker Compose v2.
- The approved local runtimes for standalone development: CPython 3.14.10, `uv` 0.13.6, Node.js 26.13.0, and npm 12.2.1.
- `mkcert` installed using its [official installation instructions](https://github.com/FiloSottile/mkcert#installation). It creates a local certificate authority and certificates for this computer; it is not a public certificate authority.

## One-time local setup

1. Copy the non-secret environment example and create a private password file for PostgreSQL, as described in [backend setup](../backend/README.md#first-time-setup):

   ```sh
   cp .env.example .env
   mkdir -p .secrets
   python3 -c 'import secrets; print(secrets.token_urlsafe(32))' > .secrets/postgres_password
   python3 -c 'import secrets; print(secrets.token_urlsafe(48))' > .secrets/csrf_signing_key
   chmod 600 .secrets/postgres_password
   chmod 600 .secrets/csrf_signing_key
   ```

   `.env` contains the database name/user, optional host ports (`POSTGRES_PORT`, `API_HOST_PORT`, `FRONTEND_HOST_PORT`), `AUTHEDU_PUBLIC_ORIGIN` (the exact browser origin, including scheme and port), and the local-only `AUTHEDU_DEMO_MODE=1` switch for guarded sample-data commands. If you change `FRONTEND_HOST_PORT`, update `AUTHEDU_PUBLIC_ORIGIN` to match. Both secret files are ignored by Git and mounted read-only into their required containers. The CSRF key is 48 random bytes encoded as URL-safe text; all backend replicas in a deployment must use the same key. Do not put credentials in the tracked Compose file or `VITE_` frontend variables; Vite embeds those variables in browser-delivered assets.
2. Install and trust the local certificate authority for your operating system and supported browsers:

   ```sh
   mkcert -install
   ```

   This modifies the current user's local trust stores. Restart browsers after installation. On Linux, install the platform's `certutil` package first (for Debian/Ubuntu, `libnss3-tools`) if Firefox should trust the certificate; some browsers use a separate NSS trust database. Follow mkcert's [supported trust-store guidance](https://github.com/FiloSottile/mkcert#supported-root-stores) if a browser still reports the certificate as untrusted. Never install a development CA on a shared or production machine.

   `mkcert` keeps its local CA under the directory printed by `mkcert -CAROOT`. Make sure the same `mkcert` executable and CA directory are used for both `mkcert -install` and certificate generation. Terminals launched by snap-installed applications such as VS Code can have a different `XDG_DATA_HOME`, and therefore a different CA directory, from a regular terminal. Compare `command -v mkcert` and `mkcert -CAROOT` in the terminal you use for setup. If you choose a fixed CA directory, set `CAROOT` before **both** commands, for example `export CAROOT="$HOME/.local/share/mkcert"`; run `mkcert -install`, then regenerate the localhost certificate in step 3 from that same terminal. Regenerating replaces the local leaf certificate/key, not the database. Do not copy, publish, or delete `rootCA-key.pem`; it can sign certificates trusted by your machine.
3. Generate a certificate for the exact local names used to access Vite:

   ```sh
   mkdir -p .certs &&
   chmod 700 .certs &&
   (umask 077; mkcert -cert-file .certs/localhost.pem -key-file .certs/localhost-key.pem localhost 127.0.0.1 ::1) &&
   chmod 600 .certs/localhost-key.pem
   ```

   `umask 077` makes newly created files private by default, and `&&` prevents the final `chmod` from running if `mkcert` fails. If `.certs/` already exists but you get a permission error, check its owner with `ls -ld .certs`. `mkdir -p` does not fix ownership on an existing directory. If it is root-owned and empty, recreate it as your user with `rmdir .certs && mkdir -m 700 .certs`; if it contains files, do not delete it—correct ownership of this project directory instead. Both certificate files and the `.certs/` directory are ignored by Git. The private key stays on the host and is mounted read-only only into the local frontend container. Do not copy it into an image or share it.

## Start and verify

From the repository root:

```sh
docker compose up --build -d
```

Compose waits for PostgreSQL's `pg_isready` health check before starting the API. The API entrypoint constructs its SQLAlchemy URL from the mounted password file, applies `alembic upgrade head`, then starts Uvicorn. Compose waits for the API `/health` endpoint before starting Vite with HTTPS enabled. If a database, secret, or certificate is missing, the dependent service fails rather than silently switching to an insecure or unauthenticated configuration.

Open <https://localhost:5173> (or the configured `FRONTEND_HOST_PORT`). Accept only a certificate issued by the locally installed mkcert CA. The browser requests `/api/health`; Vite proxies it to the API's `/health` endpoint, with no cross-origin browser request. For local diagnostics, the API is also bound to loopback at <http://127.0.0.1:8000> (or the configured `API_HOST_PORT`); do not use that HTTP origin for cookie-authenticated browser work.

### Manually test session routes with curl

Start the full Compose stack and use a **new email address**. The commands below prompt for credentials without echoing the password, keep the HttpOnly session cookie in a private temporary cookie jar, and keep CSRF proofs in shell memory. The block is wrapped in a subshell: a failed command stops the test sequence but does not close or alter your interactive terminal. The prompts work in Bash and zsh. Requests use the local HTTPS Vite proxy so `Origin` matches `AUTHEDU_PUBLIC_ORIGIN`; do not add `curl -k` or use the backend's loopback HTTP port.

```sh
(
set -eu
printf 'New test email: '
read -r AUTHEDU_TEST_EMAIL
printf 'Test password (15+ characters): '
read -r -s AUTHEDU_TEST_PASSWORD
printf '\n'
export AUTHEDU_TEST_EMAIL

ORIGIN='https://localhost:5173'
API="$ORIGIN/api"
umask 077
COOKIE_DIR=$(mktemp -d)
chmod 700 "$COOKIE_DIR"
COOKIE_JAR="$COOKIE_DIR/cookies.txt"
trap 'rm -rf "$COOKIE_DIR"; unset AUTHEDU_TEST_PASSWORD AUTHEDU_TEST_EMAIL' EXIT

# Register a new account. The password is streamed as JSON, not placed in curl arguments.
AUTHEDU_TEST_PASSWORD="$AUTHEDU_TEST_PASSWORD" \
   python3 -c 'import json, os; print(json.dumps({"email": os.environ["AUTHEDU_TEST_EMAIL"], "password": os.environ["AUTHEDU_TEST_PASSWORD"]}))' \
   | curl --silent --show-error --fail-with-body \
         -H 'Content-Type: application/json' --data-binary @- "$API/register"
printf '\n'

# Log in: curl saves the Secure, HttpOnly cookie to the private jar.
LOGIN_RESPONSE=$(AUTHEDU_TEST_PASSWORD="$AUTHEDU_TEST_PASSWORD" \
   python3 -c 'import json, os; print(json.dumps({"email": os.environ["AUTHEDU_TEST_EMAIL"], "password": os.environ["AUTHEDU_TEST_PASSWORD"]}))' \
   | curl --silent --show-error --fail-with-body \
         -H "Origin: $ORIGIN" -H 'Content-Type: application/json' \
         --cookie-jar "$COOKIE_JAR" --data-binary @- "$API/login")
chmod 600 "$COOKIE_JAR"
CSRF_TOKEN=$(printf '%s' "$LOGIN_RESPONSE" \
   | python3 -c 'import json, sys; print(json.load(sys.stdin)["csrf_token"])')
unset LOGIN_RESPONSE
printf 'Login succeeded; session cookie saved privately.\n'

# Confirm the authenticated principal and refresh the CSRF proof after a page reload.
ME_RESPONSE=$(curl --silent --show-error --fail-with-body \
   --cookie "$COOKIE_JAR" "$API/me")
CSRF_TOKEN=$(printf '%s' "$ME_RESPONSE" \
   | python3 -c 'import json, sys; print(json.load(sys.stdin)["csrf_token"])')
unset ME_RESPONSE
printf 'Current session is valid.\n'

# Logout requires both the same Origin and the session-bound CSRF proof.
printf 'header = "Origin: %s"\nheader = "X-CSRF-Token: %s"\n' \
   "$ORIGIN" "$CSRF_TOKEN" > "$COOKIE_DIR/logout-curl.conf"
chmod 600 "$COOKIE_DIR/logout-curl.conf"
curl --silent --show-error --fail-with-body --output /dev/null \
   --config "$COOKIE_DIR/logout-curl.conf" \
   --cookie "$COOKIE_JAR" --cookie-jar "$COOKIE_JAR" \
   -X POST "$API/logout"
rm -f "$COOKIE_DIR/logout-curl.conf"
unset CSRF_TOKEN
printf 'Logout succeeded and the cookie jar was cleared.\n'

# The old cookie must no longer authenticate; expected status is 401.
STATUS=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
   --cookie "$COOKIE_JAR" "$API/me")
test "$STATUS" = '401'
printf 'Post-logout /me returned the expected 401.\n'
)
```

The browser session cookie is a credential; do not print, copy, or commit the cookie jar. The CSRF proof is not an identity credential, but keep it out of logs and URLs; the logout header is passed through a mode-600 temporary curl config instead of a command-line argument. The password is not exported to curl and is streamed to it through stdin. The temporary directory and entered values are removed from the current shell when the script exits. This is a local smoke test, not production deployment guidance.

With the Compose stack running and `AUTHEDU_DEMO_MODE=1` added to the local `.env`, create the repeatable fictional sample users and their notes with `docker compose exec backend python -m authedu_api.demo_data seed`. Run it again safely to ensure any missing fixture rows are present. To remove only those seeded records, use `docker compose exec backend python -m authedu_api.demo_data reset --confirm-demo-reset`. Reset checks the demo-mode flag, configured database name, and local database host, and requires the explicit confirmation flag; it refuses when demo IDs conflict with other identities/owners or when a demo user owns extra notes. Reset intentionally deletes the seeded demo rows even if their contents were edited. These commands are serialized against each other; the safety checks are for local learning, not production isolation. The sample users have no passwords and cannot log in until authentication is implemented.

Useful status and logs:

```sh
docker compose ps
docker compose logs --tail=100 postgres backend frontend
```

### Stop services and preserve data

```sh
docker compose down
```

### Destructive local database reset

To reset the local database, stop services and remove the named data volume. This permanently deletes the local PostgreSQL data and the cached frontend dependency volume:

```sh
docker compose down --volumes
```

Start again with `docker compose up --build -d`; the backend reapplies migrations on startup. The database, local certificate authority, and certificates are development-only and are not production deployment guidance.

## Automated checks

See the [continuous integration guide](continuous-integration.md) for backend/frontend check commands, isolated database tests, dependency audits, secret scanning, and the future browser-security test extension point. CI does not use this guide's persistent Compose database or local secrets.

## Troubleshooting

### Compose says `Set POSTGRES_DB` or reports a missing `.env`

Run Compose from the repository root and create the ignored local settings file with `cp .env.example .env`. Keep the required database name and user entries. Compose reads `.env` from the project directory; exporting a variable in a different shell does not create that file.

### PostgreSQL/backend reports a missing or empty password secret

Confirm `.secrets/postgres_password` exists and is non-empty. Re-create it using the random-password instructions in [backend setup](../backend/README.md#first-time-setup), and restrict it with `chmod 600`. Do not display or paste its contents into logs, chat, or issue reports. If PostgreSQL was already initialized with a different password, changing the file alone will not change the credential stored in the database volume. Keep using the existing database credential to preserve data; discard the volume only if you intentionally accept permanent local data loss as described under [destructive local database reset](#destructive-local-database-reset).

### Backend reports a missing or invalid CSRF signing secret

Confirm `.secrets/csrf_signing_key` exists, contains at least 32 bytes, and is readable by Docker. Create it using the random-key command in [one-time local setup](#one-time-local-setup), then restrict it with `chmod 600`. Never display or commit the key. If the key changes, all previously issued CSRF proofs become invalid; restart the backend after correcting the key configuration.

### Login rejects the request origin

`AUTHEDU_PUBLIC_ORIGIN` must exactly match the browser origin, including `https://` and the frontend port—for the default local setup, `https://localhost:5173`. If you change `FRONTEND_HOST_PORT`, update the origin in `.env`; do not add a trailing slash or derive this trust value from an incoming `Host` header.

### A host port is already in use

Set an unused host port in the ignored `.env` (`POSTGRES_PORT`, `API_HOST_PORT`, or `FRONTEND_HOST_PORT`) and retry. The frontend host port controls the browser URL; the API host port is only needed for direct loopback diagnostics. `docker compose ps` shows published ports; do not stop unrelated processes without identifying them first.

### Frontend fails because a TLS certificate is missing or invalid

Check that `.certs/localhost.pem` and `.certs/localhost-key.pem` exist, are readable by Docker, and were generated for `localhost`, `127.0.0.1`, and `::1`. Re-run the certificate-generation command from the [setup section](#one-time-local-setup). Keep the key private; do not copy it into the image or commit it. Check ownership before changing permissions if an existing `.certs/` directory was created by another user.

### Browser reports that the local certificate is untrusted

Run `command -v mkcert` and `mkcert -CAROOT` both where you generated the certificate and where you ran `mkcert -install`. They must identify the same executable and CA directory. If `CAROOT` differs, choose one directory, export it before running `mkcert -install`, then regenerate the localhost certificate with that same `CAROOT`; installing a different local CA does not trust the certificate you already generated. For snap-launched terminals, an `XDG_DATA_HOME` difference can explain why the paths differ. Restart the browser after installation. Firefox may use a separate NSS database; on Linux install `libnss3-tools` and follow mkcert's [supported trust-store guidance](https://github.com/FiloSottile/mkcert#supported-root-stores). Trust only your own local development CA. Do not bypass certificate validation or use a browser exception as a production workaround.

### API health check or browser proxy is unavailable

Check `docker compose ps` and `docker compose logs --tail=100 postgres backend frontend`. PostgreSQL must become healthy before the backend migrates and starts; Vite starts after the API health check. Fix the first service that failed and rerun `docker compose up --build -d`. The health route checks API process liveness only; it does not prove database readiness or implement authentication.

### Python or Node commands use the wrong version

Run `python3 --version`, `uv --version`, `node --version`, and `npm --version` and match the pinned values in [the runtime prerequisites](../README.md#prerequisites). For Python, install/select CPython 3.14.10 and let uv install it with `uv python install`; for Node, use `.nvmrc` with `nvm install` and `nvm use`, then install npm 12.2.1 as the frontend guide describes. Do not update lockfiles with an unintended runtime/package manager version.

### CLI reports `No module named 'authedu_api'`

Rebuild and recreate the backend image with `docker compose up --build -d backend`; then retry the documented seed/reset command. The image configures its virtual-environment interpreter on `PATH`.

## Standalone frontend limitation

`npm run dev` from `frontend/` remains available for UI work and uses HTTP when `AUTHEDU_DEV_HTTPS` is unset or `0`. Set it to `1` only with valid certificate paths; missing files or invalid setting values fail at startup rather than silently selecting HTTP. That HTTP-only mode is for the health screen and non-cookie development. It is not a fallback for session/cookie modules. The full-stack Compose command above requires HTTPS certificates and fails clearly when TLS is not configured.
