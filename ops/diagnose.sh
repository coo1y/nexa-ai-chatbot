#!/usr/bin/env bash
# Operational diagnosis for a running Nexa stack. Prints a Markdown report:
#   health · metrics with automatic findings · container status · recent warnings/errors ·
#   database view of the last hour.
# Usage: ops/diagnose.sh [BASE_URL] [WINDOW_MINUTES]      (OPS_TOKEN env for /metrics)
# Read-only: it never restarts or changes anything.
set -uo pipefail
URL="${1:-http://localhost:8080}"
WINDOW="${2:-60}"
TOKEN="${OPS_TOKEN:-local-dev-ops-token}"
cd "$(dirname "$0")/.."
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

HEALTH_CODE=$(curl -s -o "$TMP/health.json" -w '%{http_code}' --max-time 5 "$URL/api/v1/health" || echo 000)
METRICS_CODE=$(curl -s -o "$TMP/metrics.json" -w '%{http_code}' --max-time 10 \
  -H "Authorization: Bearer $TOKEN" "$URL/api/v1/metrics?window_minutes=$WINDOW" || echo 000)

echo "# Nexa diagnosis report"
echo
echo "- Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "- Target: \`$URL\` · window: last $WINDOW min"
echo
echo "## Health (HTTP $HEALTH_CODE)"
echo '```json'; cat "$TMP/health.json" 2>/dev/null || echo "(no response)"; echo; echo '```'
echo
echo "## Metrics (HTTP $METRICS_CODE)"
echo '```json'; python3 -m json.tool "$TMP/metrics.json" 2>/dev/null || cat "$TMP/metrics.json" 2>/dev/null; echo '```'
echo
echo "## Automatic findings"
python3 ops/analyze.py "$HEALTH_CODE" "$TMP/health.json" "$METRICS_CODE" "$TMP/metrics.json"
echo

if command -v docker >/dev/null && docker compose ps >/dev/null 2>&1; then
  echo "## Containers"
  echo '```'; docker compose ps --format 'table {{.Service}}\t{{.State}}\t{{.Status}}'; echo '```'
  echo
  echo "## Backend warnings/errors (last ${WINDOW}m, newest 25)"
  echo '```'
  docker compose logs backend --since "${WINDOW}m" --no-color 2>/dev/null \
    | grep -E '"level": "(WARNING|ERROR|CRITICAL)"|Traceback|ERROR' | cut -c1-320 | tail -25 || true
  echo '```'
  echo
  echo "## Database (last hour, content-free telemetry)"
  echo '```'
  docker compose exec -T db psql -U nexa -d nexa -P pager=off -c \
    "SELECT status, capability, count(*) AS requests, round(avg(ttft_ms)) AS avg_ttft_ms, sum(retries) AS retries
       FROM chat_requests WHERE created_at > now() - interval '1 hour' GROUP BY 1,2 ORDER BY 3 DESC;" 2>&1 | head -20
  docker compose exec -T db psql -U nexa -d nexa -P pager=off -t -c \
    "SELECT 'uploads retained: ' || count(*) || ', expired awaiting purge: ' || count(*) FILTER (WHERE expires_at < now()) FROM uploaded_files;" 2>&1
  echo '```'
fi
