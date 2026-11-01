"""Build the database URL from a mounted secret, migrate, then start the API."""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy.engine import URL


def main() -> None:
    """Use the mounted password file without placing credentials in Compose config."""
    password_file = Path(os.environ.get("DATABASE_PASSWORD_FILE", ""))
    if not password_file.is_file():
        raise SystemExit("Database password secret file is unavailable; check Compose secrets.")

    password = password_file.read_text(encoding="utf-8").rstrip("\r\n")
    if not password:
        raise SystemExit("Database password secret file is empty.")

    try:
        database_url = URL.create(
            "postgresql+psycopg",
            username=os.environ["POSTGRES_USER"],
            password=password,
            host=os.environ.get("POSTGRES_HOST", "postgres"),
            port=int(os.environ.get("POSTGRES_PORT", "5432")),
            database=os.environ["POSTGRES_DB"],
        )
    except (KeyError, ValueError):
        raise SystemExit("Database connection settings are incomplete or invalid.") from None

    os.environ["DATABASE_URL"] = database_url.render_as_string(hide_password=False)
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    os.execv(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "authedu_api.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ],
    )


if __name__ == "__main__":
    main()
