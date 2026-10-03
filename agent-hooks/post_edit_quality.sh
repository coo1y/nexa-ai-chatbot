#!/usr/bin/env bash
# PostToolUse hook: lint the file the agent just changed and feed problems back to it.
# Exit code 2 surfaces stderr to the agent so it fixes issues in the same turn.
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
FILE=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))' 2>/dev/null)
[ -z "$FILE" ] && exit 0
REL="${FILE#"$ROOT"/}"

case "$REL" in
  openapi.yaml)
    # Keep the generated frontend types in lock-step with the contract.
    if ! out=$(cd "$ROOT/frontend" && npm run --silent gen:api 2>&1); then
      echo "openapi.yaml changed but type generation failed:" >&2; echo "$out" >&2; exit 2
    fi
    echo "Regenerated frontend/src/api/schema.gen.ts from openapi.yaml. Run backend contract tests next." >&2
    exit 0 ;;
  backend/*.py|mcp-server/*.py|agent-hooks/*.py)
    out=$(cd "$ROOT/backend" && uv run --quiet ruff check "$FILE" 2>&1) || { echo "ruff found problems in $REL:" >&2; echo "$out" >&2; exit 2; } ;;
  frontend/src/*.ts|frontend/src/*.tsx)
    out=$(cd "$ROOT/frontend" && npx --no-install eslint "$FILE" 2>&1) || { echo "eslint found problems in $REL:" >&2; echo "$out" >&2; exit 2; } ;;
esac
exit 0
