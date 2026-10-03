# Agent hooks (guardrails)

Wired in `../.claude/settings.json`. Stdlib-only Python / bash.

| Hook | Event | Behaviour |
|---|---|---|
| `guard_secrets.py` | PreToolUse (Write/Edit/MultiEdit) | Blocks writing `.env`/key files and content that looks like API keys, private keys or hard-coded credentials (exit 2 → reason shown to the agent) |
| `protect_paths.py` | PreToolUse (Write/Edit/MultiEdit/Bash) | Denies edits to generated `schema.gen.ts`, applied migrations, lockfiles; denies destructive shell commands; asks before `docker compose down -v` / `alembic downgrade` |
| `post_edit_quality.sh` | PostToolUse (Write/Edit/MultiEdit) | Lints the edited file (ruff / eslint) and feeds problems back; regenerates frontend API types when `openapi.yaml` changes |

Tests: `make test-hooks`. Security notes: `../security/agent-extension-security.md`.
