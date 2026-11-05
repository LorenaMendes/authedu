"""Secret-file configuration for independently executed Compose commands."""

import secrets

import pytest

from authedu_api.database import database_url_from_secret_file
from authedu_api.demo_data import DemoSafetyError, _demo_database_url


@pytest.fixture
def compose_settings(monkeypatch, tmp_path):
    password = secrets.token_urlsafe(32)
    secret_file = tmp_path / "database_password"
    secret_file.write_text(password + "\n", encoding="utf-8")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_PASSWORD_FILE", str(secret_file))
    monkeypatch.setenv("POSTGRES_USER", "authedu")
    monkeypatch.setenv("POSTGRES_DB", "authedu")
    monkeypatch.setenv("POSTGRES_HOST", "postgres")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("AUTHEDU_DEMO_MODE", "1")
    monkeypatch.setenv("AUTHEDU_DEMO_DATABASE", "authedu")
    return secret_file, password


def test_demo_command_reads_compose_secret_without_database_url(compose_settings):
    _, password = compose_settings
    url = _demo_database_url()
    assert url.drivername == "postgresql+psycopg"
    assert (url.username, url.host, url.port, url.database) == (
        "authedu", "postgres", 5432, "authedu"
    )
    if url.password != password:
        raise AssertionError("Compose database password was not read from the secret file.")


@pytest.mark.parametrize("contents", [None, "", "\n"])
def test_missing_or_empty_secret_fails_safely(compose_settings, contents):
    secret_file, password = compose_settings
    if contents is None:
        secret_file.unlink()
    else:
        secret_file.write_text(contents, encoding="utf-8")
    with pytest.raises(RuntimeError, match="Database password secret file") as error:
        database_url_from_secret_file()
    if password in str(error.value):
        raise AssertionError("Database configuration error exposed the secret password.")
    assert str(secret_file) not in str(error.value)


def test_invalid_port_fails_without_exposing_secret(compose_settings, monkeypatch):
    _, password = compose_settings
    monkeypatch.setenv("POSTGRES_PORT", password)
    with pytest.raises(RuntimeError, match="incomplete or invalid") as error:
        database_url_from_secret_file()
    if password in str(error.value):
        raise AssertionError("Database configuration error exposed the secret password.")


def test_explicit_invalid_url_does_not_fall_back_to_compose(compose_settings, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    with pytest.raises(RuntimeError, match="postgresql\\+psycopg"):
        _demo_database_url()


def test_empty_explicit_url_does_not_fall_back_to_compose(compose_settings, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    with pytest.raises(RuntimeError, match="not a valid SQLAlchemy URL"):
        _demo_database_url()


def test_valid_explicit_url_wins_over_compose_secret(compose_settings, monkeypatch):
    secret_file, _ = compose_settings
    secret_file.unlink()
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://localhost/authedu")
    assert _demo_database_url().host == "localhost"


@pytest.mark.parametrize(
    ("setting", "value", "message"),
    [
        ("AUTHEDU_DEMO_MODE", "0", "AUTHEDU_DEMO_MODE=1"),
        ("AUTHEDU_DEMO_DATABASE", "another_database", "does not match"),
        ("POSTGRES_HOST", "example.invalid", "local PostgreSQL host"),
    ],
)
def test_compose_fallback_preserves_demo_guards(
    compose_settings, monkeypatch, setting, value, message
):
    monkeypatch.setenv(setting, value)
    with pytest.raises(DemoSafetyError, match=message):
        _demo_database_url()