#!/usr/bin/env bash
# Deterministic security scans. Writes raw outputs to security/scan-results/ and prints a
# summary. Scanners that need Docker (gitleaks, trivy) are skipped when Docker is absent.
set -uo pipefail
cd "$(dirname "$0")/.."
OUT=security/scan-results
mkdir -p "$OUT"
STAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "Scan run: $STAMP" > "$OUT/_run.txt"

run() { # name, command...
  local name=$1; shift
  echo "▶ $name"
  if "$@" > "$OUT/$name.txt" 2>&1; then echo "  ✔ clean"; echo "$name: clean" >> "$OUT/_run.txt";
  else echo "  ✖ findings (see $OUT/$name.txt)"; echo "$name: findings" >> "$OUT/_run.txt"; fi
}

# SAST — Python (all severities recorded; CI gates on medium+)
run bandit uvx bandit -r backend/app mcp-server/nexa_mcp.py agent-hooks -x agent-hooks/tests -f txt
# Dependency CVEs — Python
(cd backend && uv export --frozen --no-hashes --format requirements-txt > /tmp/nexa-req.txt)
run pip-audit uvx pip-audit -r /tmp/nexa-req.txt --strict
# Dependency CVEs — Node
run npm-audit-frontend bash -c "cd frontend && npm audit --audit-level=low"
run npm-audit-e2e bash -c "cd e2e && npm audit --audit-level=low"
# SAST — multi-language rules (Python, TypeScript/React, Dockerfiles, secrets)
run semgrep uvx --from semgrep semgrep scan --metrics=off --config p/python --config p/typescript --config p/react \
  --config p/dockerfile --config p/secrets --error \
  --exclude node_modules --exclude .venv --exclude dist --exclude frontend/src/api/schema.gen.ts .

if docker info >/dev/null 2>&1; then
  run gitleaks docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:latest dir /repo --no-banner --redact \
    --config /repo/.gitleaks.toml --verbose
  docker build -q -t nexa:scan . > /dev/null
  run trivy-image docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest image \
    --quiet --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 nexa:scan
  run trivy-config docker run --rm -v "$PWD:/repo" aquasec/trivy:latest config --quiet --severity HIGH,CRITICAL \
    --exit-code 1 /repo
else
  echo "Docker unavailable: skipped gitleaks and trivy" | tee -a "$OUT/_run.txt"
fi
echo; cat "$OUT/_run.txt"
