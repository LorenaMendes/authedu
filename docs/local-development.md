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

   `.env` contains only the database name/user, optional host ports (`POSTGRES_PORT`, `API_HOST_PORT`, `FRONTEND_HOST_PORT`), and the local-only `AUTHEDU_DEMO_MODE=1` switch for guarded sample-data commands. The password file is ignored by Git and mounted read-only into the database and backend containers. Do not put credentials in the tracked Compose file or `VITE_` frontend variables; Vite embeds those variables in browser-delivered assets.
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
