# Agent permissions

Principle: **read freely, verify freely, change deliberately, never exfiltrate.** Configured in
`.claude/settings.json`; enforced additionally by hooks (which apply even when a user grants
broad permissions) and by the MCP server's own guardrails.

## Allowed without asking

| Capability | Why it is safe |
|---|---|
| Read/search the repository | Source is not secret (`.env` and key files are denied) |
| `uv run pytest/ruff/mypy`, `npm run test/lint/typecheck/build/gen:api/check:api`, `npx vitest`, `npx playwright test`, `make check` | Local and deterministic; tests use mock providers (no network, no keys) |
| `git status/diff/log`, `docker compose ps/logs` | Read-only |
| MCP: `contract_operations`, `contract_schema`, `contract_drift`, `service_health`, `service_metrics` | Read-only (`read_only_hint`), allow-listed hosts only |

## Require human confirmation (`ask`)

| Capability | Risk |
|---|---|
| MCP `chat_probe` | Sends a real message; costs tokens with a real provider; writes a telemetry row |
| `docker compose up/down` | Starts/stops services; `down -v` deletes the database (the hook also asks) |
| `git commit`, `git push` | Outward-facing / shared history |
| `uv add`, `npm install` | Supply-chain changes (lockfiles may only change this way) |
| `alembic downgrade` (hook) | Schema rollback |

## Denied

| Capability | Reason |
|---|---|
| Read `.env`, `.env.*`, `*.pem` | Secrets |
| `curl`, `wget`, `ssh`, `scp`, WebFetch | Exfiltration / untrusted downloads; use the MCP tools for local HTTP |
| Writing secrets anywhere (hook `guard_secrets.py`) | Credential leakage |
| Editing `schema.gen.ts`, applied migrations, lockfiles (hook `protect_paths.py`) | Generated/immutable artefacts |
| Recursive delete of `/` or `~`, force-push, hard reset, `git clean -f`, Docker prune, piping downloads into a shell, printing `.env` (hook `protect_paths.py`) | Destructive or unsafe |

## MCP server guardrails

* Requests only to hosts in `NEXA_ALLOWED_HOSTS` (default `localhost,127.0.0.1`) — prevents
  SSRF if an agent is prompt-injected into probing internal addresses (tested).
* The ops token comes from the environment and is never returned in tool output.
* Probe messages are capped at 4,000 characters; capability values are validated.

## CI agents

The PR-audit workflow runs Claude with `--allowedTools` limited to reading the repo,
`git diff/log`, and updating its own PR comment; job permissions are `contents: read,
pull-requests: write`. It cannot push code, and the only secret it receives is its API key.
