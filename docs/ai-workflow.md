# AI-assisted development workflow

This project was built with **Claude Code** (CLI, model Claude Opus 5.5, effort "high") driven
by a human project owner. This page records how the AI was used, what context it was given,
how work was split, and — most importantly — how its output was reviewed and verified.

## 1. Inputs and context files

| Context | Purpose |
|---|---|
| `product-spec.md` | Functional scope, exclusions, acceptance criteria |
| `docs/assignment.md` | Grading criteria → deliverables checklist (repo layout, tests, CI/CD, extension pack, security, ops) |
| Human constraint | "Backend must be Python" |
| `AGENTS.md` / `CLAUDE.md` (written early, kept current) | Rules every later agent session inherits: contract-first, safety pipeline, no secrets, tests with every change |
| `openapi.yaml` | Shared contract that anchored both halves of the implementation |

### The kickoff prompt (verbatim)

> I want to create a new full stack app according to `docs_/product_spec.md` with a full score
> with following criteria in `docs_/assignment.md`. Backend must be Python.

(The input files have since moved: the spec is `product-spec.md` at the repo root, the brief is
`docs/assignment.md`.)

## 2. How the work was decomposed

One Claude Code session executed the plan below; each phase ended with a verification gate
before moving on. Decisions the AI made on its own (and that a reviewer should challenge) are
listed in [decisions.md](decisions.md).

| # | Phase | AI output | Gate before continuing |
|---|---|---|---|
| 1 | Requirements analysis | Mapped spec sections + 14 grading criteria to deliverables; chose stack (FastAPI, React/Vite, Postgres, Render) | — |
| 2 | Backend core | config, DB models/repositories, LLM provider abstraction + mock, tools, router, safety, context builder, orchestrator, API | 138 unit tests, ruff, mypy |
| 3 | Contract | `openapi.yaml` written from spec + UI needs; contract tests; JSON-Schema validation of every SSE event | 41 integration tests (SQLite, then PostgreSQL) |
| 4 | Frontend | typed API client generated from the contract, store, components, theming | 61 Vitest tests, tsc, eslint, build |
| 5 | Visual review | Playwright screenshots (desktop light/dark, mobile) inspected by the model | layout bugs found → fixed → re-screenshotted |
| 6 | End-to-end | 13 Playwright specs covering all 24 acceptance criteria | green locally, against docker compose, and against the production image |
| 7 | Containers & CI/CD | Dockerfiles, compose, nginx, workflows, Render blueprint | stack healthy; headers verified with curl |
| 8 | Agent extension pack | skills, subagents, MCP server, hooks, permissions | hook + MCP tests; MCP tools exercised against the live stack |
| 9 | Security | 8 deterministic scanners; manual security review | findings fixed and re-scanned clean (see `security/`) |
| 10 | Operations | diagnosis script, benchmark, incident drill (provider outage, DB outage) | drill found 2 resilience bugs → fixed → drill re-run |
| 11 | Documentation | README, docs/, security/, ops/ | links and commands re-checked |

### Delegation model

* **Human** — owns requirements, constraints and acceptance; reviews diffs; holds secrets and
  cloud accounts (deployment, API keys); approves anything outward-facing.
* **Claude Code (main session)** — planning, implementation, running tests/scanners,
  self-review against the checklist.
* **Reusable delegation for future work** (in the extension pack): skills
  (`contract-first-change`, `add-assistant-tool`, `release-check`, `incident-diagnosis`) and
  specialist subagents (`contract-guardian`, `security-reviewer`, `ops-diagnostician`) with
  restricted tool access, plus the automated PR-audit workflow.

## 3. Review and verification

Nothing generated was accepted on trust. Every phase was verified by executing it:

* **Static checks**: ruff (lint + format), mypy, ESLint, Prettier, `tsc --strict`.
* **Tests**: unit → integration (SQLite *and* PostgreSQL) → frontend → browser e2e
  (dev servers, docker compose, and the single production image).
* **Contract checks**: YAML ⇄ FastAPI ⇄ generated TypeScript, plus JSON-Schema validation of
  live responses and stream events.
* **Visual review**: screenshots read back and inspected.
* **Runtime probes**: curl of headers/health, streaming via the MCP `chat_probe`.
* **Security**: bandit, pip-audit, npm audit, semgrep, gitleaks, trivy (image + config).
* **Chaos drill**: injected provider failures and a database outage.

### Defects caught by verification (and fixed)

| Found by | Defect | Fix |
|---|---|---|
| unit test | `data_process` sorted empty values first in descending order | nulls always last |
| unit test | malformed tool-call JSON still executed the tool with `{}` | report the parse error to the model without executing |
| integration test | SQLite dropped timezone info (timestamps without `Z`) | `UTCDateTime` column type |
| integration test | mock provider mis-detected search results from the system prompt | stricter markers |
| screenshot | page-level scroll pushed the composer off-screen | single-row grid with internal scrolling |
| screenshot | Search toggle stayed on for every later message | explicit search applies to one message |
| screenshot | mobile sidebar covered the chat with no way to dismiss | off-canvas drawer + backdrop |
| curl | nginx dropped security headers in locations with their own `add_header` | shared include |
| log review | access logs had `request_id: "-"` | log inside the request context |
| local CI rehearsal | migrations step would fail after tests created tables | migrate before tests |
| manual security review | no body-size limit in the single-container deploy | Content-Length middleware (413) |
| manual security review | `X-Forwarded-For` appended by nginx → rate-limit key spoofable | overwrite with `$remote_addr` |
| manual security review | `/metrics` open in production without a token | disabled unless `OPS_TOKEN` |
| bandit | `assert` used as a runtime guard | explicit check |
| trivy | HIGH CVE in a Debian base package | `apt-get upgrade` in runtime stages |
| incident drill | DB outage → unhandled 500 + traceback floods | handled 503, one-line warnings |
| benchmark | rate limiter (correctly) throttled the benchmark → script crashed | robust benchmark + documented override |
| first cloud deploy (Render log) | migrations failed with `Name or service not known`: the Blueprint pinned the web service to Singapore but left the database on Render's default region, and the internal DB hostname only resolves within one region | `region: singapore` on the database in `render.yaml`; database recreated |
| deploy-job review | the CD job appended `?ref=…` to Render's hook URL, which already contains `?key=…`, corrupting the key | append the ref with `&` when the URL has a query string |
| live smoke test (Groq monitoring: HTTP 404) | every Fast/Vision chat failed: Groq had retired `llama-3.3-70b-versatile` and `llama-4-scout` for free-tier accounts | switch both capabilities to the multimodal `qwen/qwen3.8-27b` |

## 4. Human review checklist (project owner)

The AI cannot sign off its own work. Before submission / merge the owner should:

- [ ] Read the diff of `backend/app/services/` (safety rules, routing heuristics, prompts) and agree with the policy choices in `decisions.md`.
- [ ] Run `make check` and `make e2e` locally; run `docker compose up` and click through the app.
- [ ] Try the app with a real `LLM_API_KEY` (routing, vision, search citations).
- [ ] Review `security/findings.md` accepted risks.
- [ ] Configure Render + GitHub secrets and record proof of deployment in `deployment.md`.

## 5. Lessons

* A deterministic mock provider made every layer (unit → e2e → CI) testable without keys
  and is what allowed the AI to verify its own work end-to-end.
* Contract-first + generated types + schema-validated tests removed a whole class of
  frontend/backend mismatches.
* Executing things (screenshots, curl, drills) found bugs that tests alone did not.
