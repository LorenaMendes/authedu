"""Shared Argon2id verifier and process-local dummy hash."""

import secrets

import pytest

from authedu_api.core import passwords


def test_verifier_uses_one_dummy_hash_for_missing_and_hashless_accounts() -> None:
    assert passwords.DUMMY_PASSWORD_HASH.startswith("$argon2id$")
    if passwords.DUMMY_PASSWORD_HASH == "dummy password":
        raise AssertionError("The dummy verifier is not a real Argon2id hash.")


@pytest.mark.parametrize("malformed_hash", ["", "not-an-argon2-hash"])
def test_malformed_stored_hash_is_a_failed_verification(malformed_hash: str) -> None:
    assert passwords.verify_password(secrets.token_urlsafe(24), malformed_hash) is False