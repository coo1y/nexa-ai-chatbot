# Security, audit & hardening

| Artefact | What it contains |
|---|---|
| [pr-audit.md](pr-audit.md) | PR audit of the initial implementation: 13 findings with evidence, fix and verification; checklist results |
| [findings.md](findings.md) | Deterministic scan results (bandit, pip-audit, npm audit, semgrep, gitleaks, trivy image + config), triage, accepted risks |
| [scan-results/](scan-results/) | Raw scanner output — `initial-run/` (before fixes) and current |
| [threat-model.md](threat-model.md) | Assets, trust boundaries, threats and mitigations with test evidence |
| [agent-extension-security.md](agent-extension-security.md) | Security notes for hooks, MCP server, subagents, permissions and the CI AI reviewer |
| [ai-tool-data-policy.md](ai-tool-data-policy.md) | What data Nexa processes and keeps, provider requirements, and rules for using AI tools in development/operations |
| [run-scans.sh](run-scans.sh) | Reproduce all scans: `make scan` |

Operational diagnosis outputs live in [`../ops/`](../ops/).

CI: `.github/workflows/security.yml` runs bandit, pip-audit, npm audit, semgrep (SARIF upload),
gitleaks and trivy on every PR, on `main`, and weekly. `.github/workflows/pr-audit.yml` adds an
advisory AI review on each PR when the `ANTHROPIC_API_KEY` secret is configured (it skips itself
otherwise).
