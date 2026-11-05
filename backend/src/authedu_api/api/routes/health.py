"""Process liveness endpoint, independent of external dependencies."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Report that the API process is responsive; this does not check dependencies."""
    return {"status": "ok"}