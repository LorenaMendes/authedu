# AuthEdu frontend

The first frontend slice is a small health screen. It demonstrates browser-to-API connectivity only; there are no login forms, users, credentials, or authentication behavior yet.

## Requirements

- Node.js 26.13.0 (pinned in `.nvmrc`)
- npm 12.2.1 (pinned in `package.json`)

Use a Node version manager such as [nvm](https://github.com/nvm-sh/nvm) to select the pinned runtime. From the repository root:

```sh
cd frontend
nvm install
nvm use
npm install --global npm@12.2.1
npm ci
```

`npm ci` installs the exact dependency tree from `package-lock.json`. Repeat it after a clean clone or when dependencies change; you do not need to reinstall before each launch.

## Check the frontend

```sh
npm run lint
npm test
npm run build
```

## Run the full local health view

Start the backend first in another terminal by following [backend setup](../backend/README.md). Then, from `frontend/`:

```sh
npm run dev
```

Open the local URL printed by Vite (normally `http://localhost:5173`). The Vite development proxy forwards browser requests at `/api/*` to `http://127.0.0.1:8000/*`, so the health screen's `/api/health` request reaches the backend's `GET /health`. If the backend is stopped, the UI shows an unavailable state and offers a retry.

The proxy is for local development. A production deployment will need an equivalent same-origin reverse-proxy rule; deployment configuration is outside this issue's scope.
