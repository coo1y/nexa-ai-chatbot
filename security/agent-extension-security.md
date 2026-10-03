# Agent & extension security notes

Security review of the agent extension pack (`AGENTS.md`, `.claude/`, `agent-capabilities/`,
`custom-agent/`, `agent-hooks/`, `mcp-server/`, `.mcp.json`, `pr-audit.yml`).

## Risks and controls

| Risk | Control | Residual risk |
|---|---|---|
| **Prompt injection of the coding agent** through repository content, issue text, documents or tool output | Network tools denied (`curl`, `wget`, `ssh`, WebFetch); secrets unreadable (`.env`, `*.pem` denied); destructive commands blocked by hook; outward-facing actions (`git push`, `docker compose down`) require confirmation | An injected agent could still make bad *local* edits — caught by human review + CI |
| **Secret leakage via agent writes** | `guard_secrets.py` blocks key-shaped strings and env/key files on every Write/Edit; gitleaks in CI | Pattern-based: novel key formats may slip → gitleaks default rules as a second net |
| **Tampering with generated / immutable artefacts** | `protect_paths.py` denies edits to `schema.gen.ts`, applied migrations, lockfiles | — |
| **MCP server as an SSRF pivot** | Host allow-list (`NEXA_ALLOWED_HOSTS`, default localhost), scheme check; tested against metadata IP, external host, `file://` | Operators who add production hosts expose read-only production metrics to the agent — intended, token-gated |
| **MCP token exposure** | Ops token read from env, sent only as a header, never returned | Visible to anyone with access to the MCP process environment |
| **Over-privileged subagents** | Each subagent lists its tools explicitly; reviewers are read-only by instruction and tool list (no Write/Edit) | `Bash` is granted to reviewers for running tests; project deny rules and hooks still apply |
| **CI AI reviewer abuse** (malicious PR prompt-injects the reviewer) | Reviewer has read-only repo access, can only update its own comment; workflow skips without the secret; advisory only | A crafted PR could produce a misleading review comment → humans + deterministic gates decide |
| **Hook bypass** | Hooks are configured in the committed project settings; tests (`make test-hooks`) keep them working | A user can disable hooks locally; CI remains authoritative |
| **Supply chain of the MCP server** | Pinned via `uv.lock`; minimal deps (`mcp`, `httpx`, `pyyaml`) | Dependency updates require review (`uv add` is an "ask" permission) |

## Observed behaviour (from the build session)

* The project permissions took effect mid-session: once `.claude/settings.json` existed, the
  denied `WebFetch` tool was removed from the agent's toolset.
* **False positive**: `protect_paths.py` blocked a shell command whose heredoc *contained
  documentation text* mentioning a force-push. The hook matches the full command string
  because reliably parsing shell (heredocs, quoting, `eval`) is not possible in a guard.
  This fail-closed behaviour is intentional; the workaround is to write files with the
  editor tool (which is checked by `guard_secrets.py` instead). Documented here so the
  behaviour is not mistaken for a bug.

## Recommendations

1. Keep reviewer subagents without Write/Edit tools.
2. When adding MCP tools that change state, mark them `read_only_hint=False`, add them to the
   `ask` list, and require explicit arguments (no defaults that target production).
3. Re-run `make test-hooks` and `make test-mcp` in CI when touching `agent-hooks/` or `mcp-server/`.
4. Review `.claude/settings.json` changes like code — they change what agents may do.
