# Specialist subagents

Claude Code subagent definitions (symlinked into `.claude/agents/`), each with a restricted tool list.

| Agent | Purpose | Tools |
|---|---|---|
| [contract-guardian](contract-guardian.md) | Verify `openapi.yaml`, backend schemas and frontend types agree | Read/Grep/Glob, Bash (tests), MCP contract tools |
| [security-reviewer](security-reviewer.md) | Review changes for safety-pipeline bypasses, injection, SSRF, uploads, secrets | Read/Grep/Glob, Bash (scanners) — no write tools |
| [ops-diagnostician](ops-diagnostician.md) | Diagnose a running stack following the runbook | Read/Grep/Glob, Bash, MCP health/metrics/probe |
