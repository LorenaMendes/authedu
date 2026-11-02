FROM python:3.14.10-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN pip install --no-cache-dir uv==0.13.6

COPY pyproject.toml uv.lock .python-version README.md ./
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic
COPY entrypoint.py ./entrypoint.py

RUN uv sync --locked --no-dev

EXPOSE 8000
CMD ["/opt/venv/bin/python", "entrypoint.py"]
