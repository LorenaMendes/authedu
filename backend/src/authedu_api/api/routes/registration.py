"""Registration HTTP adapter with enumeration-resistant responses."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from authedu_api.database import get_database_session
from authedu_api.schemas import RegistrationRequest, RegistrationResponse
from authedu_api.services.registration import register_user

router = APIRouter(tags=["users"])


@router.post(
    "/register",
    response_model=RegistrationResponse,
)
def register(
    payload: RegistrationRequest,
    request: Request,
    session: Session = Depends(get_database_session),
) -> RegistrationResponse:
    """Accept registration without revealing whether the email already exists."""
    register_user(
        session,
        email=str(payload.email),
        password=payload.password.get_secret_value(),
    )
    return RegistrationResponse(message="Registration request accepted.")