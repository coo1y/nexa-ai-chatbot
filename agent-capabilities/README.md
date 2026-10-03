# Agent capabilities

Reusable workflows (Claude Code skills; plain Markdown playbooks for any agent). Symlinked into
`.claude/skills/`.

| Skill | Use when |
|---|---|
| [contract-first-change](skills/contract-first-change/SKILL.md) | Any change crossing the frontend/backend boundary |
| [add-assistant-tool](skills/add-assistant-tool/SKILL.md) | Adding a tool the assistant can call |
| [release-check](skills/release-check/SKILL.md) | Before opening/approving a PR |
| [incident-diagnosis](skills/incident-diagnosis/SKILL.md) | A deployment is erroring or slow |

[review-checklist.md](review-checklist.md) is shared by humans, subagents and the PR-audit workflow.
