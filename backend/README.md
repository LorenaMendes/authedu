# AuthEdu backend

This is the minimal Python API foundation. It intentionally implements no authentication, database access, or readiness checks yet.

## Requirements

- CPython 3.14.10 (pinned in `.python-version`)
- uv 0.13.6 (required by `pyproject.toml`)

Install uv using the [official instructions](https://docs.astral.sh/uv/getting-started/installation/), then run these commands from `backend/`:

```sh
uv sync --locked
uv run --locked ruff check .
uv run --locked pytest
uv run --locked uvicorn authedu_api.main:app --host 127.0.0.1 --port 8000
```

The development server listens on `http://127.0.0.1:8000`. Check process liveness with:

```sh
curl --fail http://127.0.0.1:8000/health
```

Expected response: `{"status":"ok"}`.

`GET /health` is deliberately independent of PostgreSQL: it answers whether this API process can handle a request, not whether a database or other dependency is ready. It returns no configuration or credential details. See [the technology decision record](../docs/technology-decisions.md) for the dated stack compatibility notes. This educational reference is not a production identity provider.
