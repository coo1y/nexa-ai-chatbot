# Deterministic security scan findings

Scanners are reproducible with `make scan` (`security/run-scans.sh`) and run in CI on every PR,
on `main`, and weekly (`.github/workflows/security.yml`). Raw outputs:

* `scan-results/initial-run/` — first run against the finished feature set (2026-10-03 12:23 UTC)
* `scan-results/*.txt` — run after remediation (2026-10-03 12:27 UTC, semgrep re-run 12:29)

| Scanner | Scope | Initial run | After remediation |
|---|---|---|---|
| bandit | Python SAST: `backend/app`, MCP server, hooks | 27 Low (25 in test files) | ✅ clean |
| pip-audit | Python dependency CVEs (locked versions) | ✅ clean | ✅ clean |
| npm audit | `frontend/`, `e2e/` | ✅ clean* | ✅ clean |
| semgrep | p/python, p/typescript, p/react, p/dockerfile, p/secrets (269 rules, 232 files) | 1 blocking | ✅ 0 findings |
| gitleaks | secrets in the working tree | ⚠️ did not run (invalid flag in our script) | ✅ no leaks |
| trivy image | production image OS + Python packages (HIGH/CRITICAL, fixed) | 1 HIGH | ✅ clean |
| trivy config | Dockerfiles / IaC misconfiguration (HIGH/CRITICAL) | 1 HIGH | ✅ clean |

\* An earlier `npm install` reported 3 moderate advisories in `vitest@3` (`@vitest/mocker`
path traversal, dev-only). Resolved before the scan by upgrading to `vitest@4.1.11`.

## Triage

| ID | Tool / rule | Location | Severity | Verdict | Resolution |
|---|---|---|---|---|---|
| S-1 | trivy `CVE-2026-103111` (libpcre2-8-0 out-of-bounds write) | Debian base of `python:3.12-slim` | HIGH | True positive (inherited) | Runtime stages run `apt-get upgrade`; image re-scanned clean. Weekly scheduled scan catches future base-image CVEs. |
| S-2 | trivy `DS-0002` no `USER` | `frontend/Dockerfile` | HIGH | Effectively false positive — `nginx-unprivileged` already runs as uid 101 — but not verifiable by scanners | Added explicit `USER 101`. |
| S-3 | bandit `B101` assert used | `backend/app/services/safety.py` (guard model) | Low | **True positive**: asserts are stripped under `python -O`, turning a guard into an `AttributeError` | Replaced with an explicit check. |
| S-4 | bandit `B311` random | `backend/app/services/chat.py` retry jitter | Low | False positive (not cryptographic) | Annotated `# nosec B311` with reason. |
| S-5 | bandit `B101/B404/B603` | `agent-hooks/tests/` | Low | Expected in tests | Tests excluded from the bandit scope. |
| S-6 | semgrep `python.flask…directly-returned-format-string` | `backend/app/services/llm/mock.py` | Blocking | False positive — not Flask, not an HTTP response; output is Markdown rendered without raw HTML | Initially an inline `# nosemgrep`, but GitHub code scanning still opened alert #1 from the uploaded SARIF. Root cause: the helper's `CompletionRequest` parameter was named `request`, matching the rule's Flask `request.$FUNC[...]` taint source. `_compose_answer` now takes the message list, so the rule no longer matches and the suppression is gone. |
| S-7 | gitleaks scan did not execute | `security/run-scans.sh` | Process gap | **True positive (tooling)** — a green CI badge would have hidden that secret scanning never ran | Fixed invocation; added `.gitleaks.toml` (default rules, dependency dirs allow-listed); verified "no leaks found". |

## Findings from manual review (not detectable by the scanners)

See [pr-audit.md](pr-audit.md): request body limits, `X-Forwarded-For` spoofing of the rate-limit
key, unauthenticated metrics in production, nginx header inheritance, DB-outage handling.
All fixed with tests.

## Accepted risks

| Risk | Rationale / mitigation |
|---|---|
| Rate limiter is in-memory, per instance | Single instance on the MVP plan; Redis-backed implementation is a drop-in (`RateLimiter` interface). |
| Heuristic safety rules can miss paraphrased harmful requests | Defence in depth: provider-side model safety, optional `SAFETY_MODEL` guard, tools are read-only. |
| DuckDuckGo search relies on an unofficial client | Failures degrade gracefully (tool error → model answers without search); Tavily is a configuration switch. |
| `X-Client-Id` is a bearer-like identifier in localStorage | ~124-bit random; only grants access to that browser's uploads (24 h) and feedback. Replaced by real auth when accounts ship. |
| `FORWARDED_ALLOW_IPS="*"` on Render | Render's edge proxy sets the client address; the per-client limit still applies. Restrict to the platform's proxy range when it is published. |
