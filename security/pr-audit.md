# PR audit — "Initial implementation of Nexa MVP"

| | |
|---|---|
| Change set | Entire initial implementation (backend, frontend, contract, containers, CI/CD, extension pack) |
| Auditor | Claude Code (Claude Opus 5.5), audit pass against `agent-capabilities/review-checklist.md`, plus the deterministic scans in [findings.md](findings.md) |
| Date | 2026-10-03 |
| Method | Read the diff by area; for each checklist item, either cite the test that proves it or execute a probe (curl, Playwright, chaos drill); every finding fixed got a regression test or a recorded probe |
| Status | **All findings resolved** · 5 accepted risks (see findings.md) · human sign-off pending (see `docs/ai-workflow.md` §4) |

Future PRs are audited automatically by `.github/workflows/pr-audit.yml` (same checklist), with
the deterministic scanners in `security.yml` as the merge gate.

## Findings

| # | Sev. | Area | Finding | Evidence | Fix | Verified by |
|---|---|---|---|---|---|---|
| 1 | High | Backend / DoS | No request-body limit when the backend is exposed directly (single-container cloud deploy): a multi-GB upload or a 40 MB chat payload is fully buffered before validation rejects it. nginx (compose) masked this locally. | Code read of `routes/files.py` (`await file.read()` after multipart parsing) | `limit_body_size` middleware rejects by `Content-Length` (uploads: `UPLOAD_MAX_BYTES` + 64 KB; JSON: `MAX_REQUEST_BYTES`) and refuses chunked bodies → 413 | `test_oversized_bodies_are_rejected_before_parsing` |
| 2 | High | Proxy / abuse | nginx used `$proxy_add_x_forwarded_for` (appends) while uvicorn trusts forwarded headers → a client could send a fake `X-Forwarded-For` and rotate the IP-level rate-limit key at will | `frontend/nginx.conf` + uvicorn `--forwarded-allow-ips` | nginx now overwrites `X-Forwarded-For` with `$remote_addr` | config review; e2e on compose still green |
| 3 | Medium | Ops data exposure | `/metrics` was public whenever `OPS_TOKEN` was unset — including production | `routes/meta.py` | Production refuses metrics without a configured token; Render blueprint generates one | `test_metrics_disabled_in_production_without_token`, `test_metrics_token` |
| 4 | Medium | Headers | nginx dropped all server-level security headers (CSP, X-Frame-Options…) on `/` and `/assets/` because those locations declare their own `add_header` (nginx does not inherit in that case) | `curl -I localhost:8080/` showed no CSP | Shared `security-headers.conf` included per location; duplicated backend headers hidden on `/api/` | `curl -I` on `/`, `/assets/*`, `/api/*` |
| 5 | Medium | Tool safety | A tool call with malformed JSON arguments was still executed with `{}` | unit test `test_invalid_tool_arguments_are_reported_to_model` failed | Parse errors are reported to the model; the tool is not executed | same test |
| 6 | Medium | Resilience | Database outage → `/metrics` returned an unhandled 500 and every request logged a ~200-line traceback (log flooding hides real errors, burns log quota) | chaos drill `ops/diagnosis-output/03-database-outage.md` (first attempt) | DB/OS connection errors → handled 503 `service_unavailable`; telemetry failures log one line; chat keeps streaming | `test_database_outage_degrades_gracefully`; drill re-run |
| 7 | Low | Correctness | `data_process` sort put empty values first when descending | unit test | nulls always last; mixed types compared as text | `test_sort_filter_aggregate` |
| 8 | Low | Data | SQLite returned naive datetimes; API timestamps lost their timezone | integration test diff (`…703268` vs `…703268Z`) | `UTCDateTime` type decorator | file metadata round-trip test |
| 9 | Low | Observability | Access logs carried `request_id: "-"` (logged after the context var was reset) | production container logs | Log inside the request context | log inspection |
| 10 | Low | UX / cost | The Search toggle stayed on for all later messages, silently adding a web search (latency, provider load) to every turn | screenshot review | Explicit search applies to a single message | `chatStore.test.ts` |
| 11 | Low | UX | Composer pushed off-screen by page scroll; mobile sidebar had no dismiss | screenshots | Grid row constraint; off-canvas drawer + backdrop | screenshots, e2e |
| 12 | Low | CI | Migration check ran after integration tests on the same DB → would always fail | local rehearsal against Postgres | Migrate → check → downgrade → upgrade before tests | rehearsal on fresh Postgres |
| 13 | Info | Code | `assert` used as a runtime guard (bandit B101) | bandit | explicit check | bandit clean |

## Checklist results

| Checklist item | Result | Proof |
|---|---|---|
| Behaviour matches spec incl. exclusions | ✅ | 24 acceptance criteria mapped to tests (`docs/testing.md`) |
| Friendly errors, no internals leaked | ✅ | `test_failure_shows_friendly_retryable_error`, `test_database_outage_degrades_gracefully` (asserts hostnames absent), client maps 5xx to a generic message |
| Every stream ends with `done`; stop handled | ✅ | orchestrator tests; `status=stopped` rows observed in telemetry |
| Contract consistency | ✅ | `test_contract.py`, schema-validated SSE events, `check:api`, MCP `contract_drift` → `in_sync: true` |
| Safety on every model and tool path | ✅ | single entry point `ChatService.stream`; `test_blocked_request` (model never called), `test_blocked_tool_call` |
| Untrusted content fenced | ✅ | `context.py` / `web_search.py`; system prompt rule; tools read-only |
| No SSRF | ✅ | no user-supplied URLs fetched; MCP allow-list tested |
| No secrets / no content in logs | ✅ | gitleaks clean; secret-guard hook; telemetry schema has no content columns |
| Upload hardening | ✅ | extension allowlist, magic-byte checks, zip-bomb + decompression-bomb guards, EXIF stripped, owner checks, 24 h purge — `test_files_service.py`, `test_files_flow.py` |
| Rate & size limits on new endpoints | ✅ | middleware applies to all POSTs; `test_rate_limiting` |
| Tests for each change; frontend uses central client | ✅ | 265 automated tests; ESLint `no-restricted-globals: fetch` |
