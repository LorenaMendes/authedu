"""Shared Argon2id hashing and verification, including one process-local dummy hash."""

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

PASSWORD_HASHER = PasswordHasher()
# Used only to perform dummy verification when an account/hash is missing or corrupt.
DUMMY_PASSWORD_HASH = PASSWORD_HASHER.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    """Hash with argon2-cffi's high-level Argon2id implementation and random salt."""
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify with argon2-cffi's high-level Argon2id implementation."""
    try:
        return PASSWORD_HASHER.verify(password_hash, password)
    except InvalidHashError:
        try:
            PASSWORD_HASHER.verify(DUMMY_PASSWORD_HASH, password)
        except VerificationError:
            pass
        return False
    except VerificationError:
        return False