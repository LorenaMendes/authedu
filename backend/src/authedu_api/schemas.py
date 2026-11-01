"""Explicit API representations; persistence-only fields stay private."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    """Public user representation, deliberately excluding password_hash."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    created_at: datetime
