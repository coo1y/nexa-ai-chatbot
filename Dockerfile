# syntax=docker/dockerfile:1.7
# Single-container production image for cloud platforms (Render, Fly.io, Cloud Run...):
# FastAPI serves both the API (/api/v1) and the built frontend (same origin, no proxy needed).
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim AS runtime
# Pick up Debian security fixes released after the base image was built (trivy gate).
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH" \
    PORT=8000 STATIC_DIR=/app/static APP_ENV=production LOG_JSON=true
WORKDIR /app
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app
COPY --from=builder /app/.venv /app/.venv
COPY backend/alembic.ini backend/docker-entrypoint.sh ./
COPY backend/migrations ./migrations
COPY backend/app ./app
COPY --from=frontend /frontend/dist ./static
RUN mkdir -p /app/data && chown -R app:app /app/data
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/v1/health', timeout=2)"
ENTRYPOINT ["sh", "./docker-entrypoint.sh"]
