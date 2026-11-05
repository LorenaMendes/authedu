"""HTTP exception handling that keeps submitted credentials out of responses."""

from fastapi import Request, status
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response


async def handle_request_validation_error(
    request: Request, error: RequestValidationError
) -> Response:
    """Avoid reflecting passwords in FastAPI's default validation-error payload."""
    if request.url.path in {"/register", "/login"}:
        detail = (
            "Invalid registration request."
            if request.url.path == "/register"
            else "Invalid login request."
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": detail},
        )
    return await request_validation_exception_handler(request, error)