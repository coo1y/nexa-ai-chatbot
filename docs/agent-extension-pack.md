# Agent extension pack

Everything an AI coding agent needs to work on Nexa safely and productively. It is wired for
Claude Code (`.claude/`, `.mcp.json`) but the pieces are plain files usable by other agents
(`AGENTS.md` is the cross-tool convention; the MCP server works with any MCP client).

| Component | Location | What it gives the agent |
|---|---|---|
| Project instructions | `AGENTS.md`, `CLAUDE.md` | Repo map, commands, non-negotiable rules, definition of done |
| Reusable workflows (skills) | `agent-capabilities/skills/*/SKILL.md` (symlinked into `.claude/skills/`) | Step-by-step playbooks: `contract-first-change`, `add-assistant-tool`, `release-check`, `incident-diagnosis` |
| Review checklist | `agent-capabilities/review-checklist.md` | Shared by humans, subagents and the PR-audit workflow |
| Specialist subagents | `custom-agent/*.md` (symlinked into `.claude/agents/`) | `contract-guardian` (API consistency), `security-reviewer` (safety/security), `ops-diagnostician` (production triage) — each with a restricted tool list |
| MCP server | `mcp-server/nexa_mcp.py`, registered in `.mcp.json` | Tools: `contract_operations`, `contract_schema`, `contract_drift`, `service_health`, `service_metrics`, `chat_probe`; resource `nexa://openapi.yaml` |
| Hooks / guardrails | `agent-hooks/`, wired in `.claude/settings.json` | `guard_secrets.py` (blocks secrets & env files), `protect_paths.py` (generated/immutable files, destructive shell commands), `post_edit_quality.sh` (lint feedback; auto-regenerates API types when `openapi.yaml` changes) |
| Permissions | `.claude/settings.json` → [permissions.md](permissions.md) | allow / ask / deny lists |
| Automated PR audit | `.github/workflows/pr-audit.yml` | Claude reviews each PR against the checklist when the `ANTHROPIC_API_KEY` secret is set (advisory; deterministic scans gate) |

## Typical flows

**Change the API** — the agent loads `contract-first-change` → reads the contract via MCP →
edits `openapi.yaml` (the hook regenerates TS types) → updates the backend → tests → asks
`contract-guardian` to verify → `contract_drift` on the running stack reports `in_sync`.

**Add a tool** — `add-assistant-tool` skill → implementation + safety rule + mock trigger +
tests → `chat_probe` shows the tool firing.

**Incident** — `ops-diagnostician` → `service_health` / `service_metrics` → `ops/diagnose.sh`
→ written diagnosis following `ops/runbook.md`.

## Verified behaviour

* `make test-hooks` — 6 tests: secrets blocked (Groq-style keys, private keys, `.env`),
  `.env.example` allowed, generated/applied-migration/lockfile edits denied, destructive shell
  commands denied, `docker compose down -v` and `alembic downgrade` require confirmation.
* `make test-mcp` — 6 tests: URL allow-list rejects metadata IPs / other hosts / file URLs,
  drift detection, stream summarising, read-only annotations.
* Live: the MCP tools were run against the docker compose stack (health ok, contract drift
  `in_sync: true`, `chat_probe` showed `unit_convert` routing, metrics returned).
* In the session that built this repo, Claude Code discovered the four project skills from
  `.claude/skills/`, applied the project permission denials, and the `protect_paths.py` hook
  blocked a shell command (see the false-positive note in
  [`security/agent-extension-security.md`](../security/agent-extension-security.md)).

## Installing in another agent

* **MCP** (any client): command `uv run --project mcp-server python mcp-server/nexa_mcp.py`,
  env `NEXA_BASE_URL`, `NEXA_ALLOWED_HOSTS`, optional `NEXA_OPS_TOKEN`.
* **Skills/instructions**: point the agent at `AGENTS.md`; skills are Markdown playbooks.
* **Hooks**: the scripts read Claude Code's hook JSON on stdin and use its exit-code/JSON
  decision protocol; adapt the matcher config for other agents' pre/post-tool hooks.
