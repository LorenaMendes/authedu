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
