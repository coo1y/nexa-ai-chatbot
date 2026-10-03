# syntax=docker/dockerfile:1.7
# Backend API image (used by docker-compose). Multi-stage: dependencies are resolved with uv
# from the lockfile, the runtime image contains only the virtualenv and app code.
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim AS runtime
# Pick up Debian security fixes released after the base image was built (trivy gate).
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH" PORT=8000
WORKDIR /app
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app
COPY --from=builder /app/.venv /app/.venv
COPY alembic.ini docker-entrypoint.sh ./
COPY migrations ./migrations
COPY app ./app
RUN mkdir -p /app/data && chown -R app:app /app/data
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/v1/health', timeout=2)"
ENTRYPOINT ["sh", "./docker-entrypoint.sh"]
