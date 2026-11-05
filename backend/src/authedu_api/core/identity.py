"""Shared case-insensitive email identity policy."""


def normalize_email(email: str) -> str:
    """Trim and lowercase an address to match the database's case-insensitive key."""
    return email.strip().lower()