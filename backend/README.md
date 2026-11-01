# AuthEdu backend

This is the minimal Python API foundation. It intentionally implements no authentication, database access, or readiness checks yet.

## Requirements

- CPython 3.14.10 (pinned in `.python-version`)
- uv 0.13.6 (required by `pyproject.toml`)

Install uv using the [official instructions](https://docs.astral.sh/uv/getting-started/installation/), then run commands from `backend/`.

## First-time setup

Sync the exact dependency versions recorded in `uv.lock`:

```sh
uv sync --locked
```

You normally need this explicitly the first time, or after dependencies change. `uv run --locked` also checks and syncs the environment when needed, so it is not necessary to repeat `uv sync` before every launch.

## Check the code

These commands are for development and review; you do not need to run them just to start the API:

```sh
uv run --locked ruff check .
uv run --locked pytest
```

Ruff checks code style and common errors. Pytest runs the endpoint contract test.

## Start the API

Run this whenever you want the local API available:

```sh
uv run --locked uvicorn authedu_api.main:app --host 127.0.0.1 --port 8000
```

Keep that terminal open while using the API. The server listens only on your computer at `http://127.0.0.1:8000`. To check it, open another terminal and run:

```sh
curl --fail http://127.0.0.1:8000/health
```

Expected response: `{"status":"ok"}`.

`GET /health` is deliberately independent of PostgreSQL: it answers whether this API process can handle a request, not whether a database or other dependency is ready. It returns no configuration or credential details. See [the technology decision record](../docs/technology-decisions.md) for the dated stack compatibility notes. This educational reference is not a production identity provider.
