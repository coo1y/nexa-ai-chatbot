#!/usr/bin/env python3
"""PreToolUse guardrail for project invariants and destructive shell commands.

File edits:
  * frontend/src/api/schema.gen.ts is generated → edit openapi.yaml and run `npm run gen:api`.
  * Applied Alembic migrations are immutable → create a new revision instead.
  * Lockfiles change only through the package manager.
Shell commands:
  * deny clearly destructive commands (rm -rf of root/home, force-push, hard reset, prune);
  * ask a human before deleting the database volume (`docker compose down -v`).
"""

import json
import re
import sys

PROTECTED_FILES = [
    (re.compile(r"frontend/src/api/schema\.gen\.ts$"), "is generated from openapi.yaml — edit the contract and run `npm --prefix frontend run gen:api`."),
    (re.compile(r"backend/migrations/versions/0001_[^/]*\.py$"), "is an applied migration — create a new revision with `uv run alembic revision --autogenerate -m ...`."),
    (re.compile(r"(^|/)(uv\.lock|package-lock\.json)$"), "is a lockfile — change dependencies with `uv add` / `npm install` instead."),
]

DENY_COMMANDS = [
    (re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f?[a-zA-Z]*\s+(/|~|\$HOME)(\s|$)"), "recursive delete of / or home"),
    (re.compile(r"\bgit\s+push\b.*(--force\b|-f\b)"), "force-push"),
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "hard reset discards work"),
    (re.compile(r"\bgit\s+clean\s+-[a-zA-Z]*f"), "git clean deletes untracked files"),
    (re.compile(r"\bdocker\s+(system|volume)\s+prune\b"), "prunes Docker data"),
    (re.compile(r"\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba|z)?sh\b"), "piping a download into a shell"),
    (re.compile(r"\bcat\s+[^|;]*\.env(\s|$)"), "printing secrets from .env"),
]
ASK_COMMANDS = [
    (re.compile(r"\bdocker\s+compose\b.*\bdown\b.*\s-v\b|\bdocker\s+compose\b.*\bdown\b.*--volumes"), "deletes the Postgres data volume"),
    (re.compile(r"\balembic\s+downgrade\b"), "rolls back the database schema"),
]


def decision(kind: str, reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": kind,
            "permissionDecisionReason": reason,
        }
    }


def check(event: dict) -> dict | None:
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    if tool in {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
        path = str(tool_input.get("file_path", "")).replace("\\", "/")
        for pattern, why in PROTECTED_FILES:
            if pattern.search(path):
                return decision("deny", f"{path} {why}")
    if tool == "Bash":
        command = str(tool_input.get("command", ""))
        for pattern, why in DENY_COMMANDS:
            if pattern.search(command):
                return decision("deny", f"Blocked by project guardrail: {why}.")
        for pattern, why in ASK_COMMANDS:
            if pattern.search(command):
                return decision("ask", f"This command {why}. Confirm it is intended.")
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    result = check(event)
    if result:
        print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
