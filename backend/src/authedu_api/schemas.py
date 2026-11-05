"""Explicit API representations; persistence-only fields stay private."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator


class UserRead(BaseModel):
    """Public user representation, deliberately excluding password_hash."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    created_at: datetime


class RegistrationRequest(BaseModel):
    """Validated public input; never serialize this model into logs or responses."""

    email: EmailStr
    password: SecretStr = Field(min_length=15, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        """Apply the persisted case-insensitive identity policy before validation."""
        if isinstance(value, str):
            return value.strip().lower()
        return value


class RegistrationResponse(BaseModel):
    """Generic response which does not reveal whether the address was already used."""

    message: str


class LoginRequest(BaseModel):
    """Login input; keep password secret from representations and logs."""

    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        """Apply the persisted case-insensitive identity policy before validation."""
        if isinstance(value, str):
            return value.strip().lower()
        return value


class AuthenticatedUser(BaseModel):
    """Minimal public identity returned by the future session-status endpoint."""

    id: UUID
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        """Apply the persisted case-insensitive identity policy before validation."""
        if isinstance(value, str):
            return value.strip().lower()
        return value


class LoginResponse(BaseModel):
    """Authenticated identity and a CSRF proof, never the session credential."""

    user: AuthenticatedUser
    csrf_token: str


class CurrentSessionResponse(BaseModel):
    """Current identity and fresh CSRF proof for the browser session."""

    user: AuthenticatedUser
    csrf_token: str
