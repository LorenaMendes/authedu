"""Minimal FastAPI application for the AuthEdu foundation."""

from fastapi import FastAPI

app = FastAPI(
    title="AuthEdu API",
    description="Educational authentication and authorization reference API.",
    version="0.1.0",
)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Report that the API process is responsive; this does not check dependencies."""
    return {"status": "ok"}
