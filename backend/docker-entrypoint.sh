#!/bin/sh
# Apply database migrations, then start the API server.
set -eu
alembic upgrade head
exec uvicorn app.asgi:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --proxy-headers \
  --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-*}" \
  --timeout-graceful-shutdown 20
