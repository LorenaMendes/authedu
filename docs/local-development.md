# Local development environment

The supported full-stack development path uses Docker Compose for PostgreSQL, the FastAPI service, and the Vite development server. Open the frontend over local HTTPS; its `/api` proxy forwards requests to the backend over the private Compose network, so browser requests remain same-origin. This provides a realistic secure-cookie origin for later modules without adding authentication now.

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
   chmod 600 .secrets/postgres_password
   ```

   `.env` contains only the database name/user and optional host ports (`POSTGRES_PORT`, `API_HOST_PORT`, `FRONTEND_HOST_PORT`). The password file is ignored by Git and mounted read-only into the database and backend containers. Do not put credentials in the tracked Compose file or `VITE_` frontend variables; Vite embeds those variables in browser-delivered assets.
2. Install and trust the local certificate authority for your operating system and supported browsers:

   ```sh
   mkcert -install
   ```

   This modifies the current user's local trust stores. Restart browsers after installation. On Linux, install the platform's `certutil` package first (for Debian/Ubuntu, `libnss3-tools`) if Firefox should trust the certificate; some browsers use a separate NSS trust database. Follow mkcert's [supported trust-store guidance](https://github.com/FiloSottile/mkcert#supported-root-stores) if a browser still reports the certificate as untrusted. Never install a development CA on a shared or production machine.
3. Generate a certificate for the exact local names used to access Vite:

   ```sh
   mkdir -p .certs
   mkcert -cert-file .certs/localhost.pem -key-file .certs/localhost-key.pem localhost 127.0.0.1 ::1
   chmod 600 .certs/localhost-key.pem
   ```

   Both certificate files and the `.certs/` directory are ignored by Git. The private key stays on the host and is mounted read-only only into the local frontend container. Do not copy it into an image or share it.

## Start and verify

From the repository root:

```sh
docker compose up --build -d
```

Compose waits for PostgreSQL's `pg_isready` health check before starting the API. The API entrypoint constructs its SQLAlchemy URL from the mounted password file, applies `alembic upgrade head`, then starts Uvicorn. Compose waits for the API `/health` endpoint before starting Vite with HTTPS enabled. If a database, secret, or certificate is missing, the dependent service fails rather than silently switching to an insecure or unauthenticated configuration.

Open <https://localhost:5173> (or the configured `FRONTEND_HOST_PORT`). Accept only a certificate issued by the locally installed mkcert CA. The browser requests `/api/health`; Vite proxies it to the API's `/health` endpoint, with no cross-origin browser request. For local diagnostics, the API is also bound to loopback at <http://127.0.0.1:8000> (or the configured `API_HOST_PORT`); do not use that HTTP origin for cookie-authenticated browser work.

Useful status and logs:

```sh
docker compose ps
docker compose logs --tail=100 postgres backend frontend
```

Stop services but retain database data:

```sh
docker compose down
```

To reset the local database, stop services and remove the named data volume. This permanently deletes the local PostgreSQL data and the cached frontend dependency volume:

```sh
docker compose down --volumes
```

Start again with `docker compose up --build -d`; the backend reapplies migrations on startup. The database, local certificate authority, and certificates are development-only and are not production deployment guidance.

## Standalone frontend limitation

`npm run dev` from `frontend/` remains available for UI work and uses HTTP when `AUTHEDU_DEV_HTTPS` is unset or `0`. Set it to `1` only with valid certificate paths; missing files or invalid setting values fail at startup rather than silently selecting HTTP. That HTTP-only mode is for the health screen and non-cookie development. It is not a fallback for session/cookie modules. The full-stack Compose command above requires HTTPS certificates and fails clearly when TLS is not configured.
