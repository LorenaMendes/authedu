"""Build the database URL from a mounted secret, migrate, then start the API."""

import os
import subprocess
import sys

from authedu_api.database import database_url_from_secret_file


def main() -> None:
    """Use the mounted password file without placing credentials in Compose config."""
    try:
        database_url = database_url_from_secret_file()
    except RuntimeError as error:
        raise SystemExit(str(error)) from None

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
