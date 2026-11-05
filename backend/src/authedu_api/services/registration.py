"""User registration with database-enforced case-insensitive email uniqueness."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from authedu_api.core.identity import normalize_email
from authedu_api.core.passwords import hash_password
from authedu_api.models import User

EMAIL_UNIQUE_INDEX = "uq_users_email_lower"


def register_user(
    session: Session,
    *,
    email: str,
    password: str,
) -> bool:
    """Create a user, returning False only for a duplicate normalized email.

    Hashing happens before the atomic insert on both duplicate and new-email paths,
    reducing (but not eliminating) response-time differences that could reveal
    whether an address is already registered.
    """
    normalized_email = normalize_email(email)
    hashed_password = hash_password(password)
    new_user = User(email=normalized_email, password_hash=hashed_password)
    session.add(new_user)
    try:
        session.commit()
        return True
    except IntegrityError as error:
        session.rollback()
        diagnostic = getattr(error.orig, "diag", None)
        if getattr(diagnostic, "constraint_name", None) == EMAIL_UNIQUE_INDEX:
            return False
        raise