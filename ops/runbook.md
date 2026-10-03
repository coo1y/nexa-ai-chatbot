# Runbook

Start every investigation with `make diagnose URL=<base-url>` (or `ops/diagnose.sh <url>`); it
collects health, metrics with automatic findings, container status, recent warnings and a
database view. In production export `OPS_TOKEN` first. The `ops-diagnostician` agent and the
`incident-diagnosis` skill follow this runbook.

## Signals

| Signal | Source | Normal |
|---|---|---|
| `GET /api/v1/health` | load balancer / uptime check | 200 `{"status":"ok","database":"ok"}` |
| Error rate, errors by code | `GET /api/v1/metrics` | < 2 % ([slo.md](slo.md)) |
| TTFT p95 | metrics (`ttft_ms`) | < 2 s with a real provider |
| Retries | metrics (`total_retries`) | ≪ 1 per request |
| Logs | JSON on stdout, one `request_id` per request | WARNING lines rare |

## Playbooks

### Model provider errors (`upstream_unavailable`, `upstream_rate_limited`)
1. Metrics: confirm the error code dominates and retries are high.
2. Check the provider's status page; `chat_probe` (MCP) or a single request to reproduce.
3. Mitigate: if rate-limited, lower `RATE_LIMIT_CHAT_PER_MINUTE` or upgrade the provider plan;
   if down, point `LLM_BASE_URL`/`MODEL_*` to an alternative OpenAI-compatible host and redeploy.
4. Users already see a friendly error with Retry — no data loss (history is client-side).
Drill: [`diagnosis-output/02-model-provider-outage.md`](diagnosis-output/02-model-provider-outage.md).

### Invalid model credentials (`upstream_misconfigured`)
Rotate `LLM_API_KEY` in the platform settings (never in the repo) and redeploy. Retries do not help.

### Model rejects requests (`upstream_bad_request`)
Usually context too large for the model or unsupported content (e.g. image to a text model).
Lower `CONTEXT_MAX_TOKENS`; confirm `MODEL_VISION` supports images.

### Database unavailable (health 503, `database: unavailable`)
1. Chat keeps working (degraded: no attachments, telemetry skipped); uploads/feedback/metrics return 503.
2. Compose: `docker compose ps db`, `docker compose logs db`; `docker compose start db`.
   Render: check the database status page; free instances expire after 30 days.
3. Recovery is automatic once the DB is back (connection pool pre-ping) — no backend restart.
Drill: [`03-database-outage.md`](diagnosis-output/03-database-outage.md) → [`04-recovered.md`](diagnosis-output/04-recovered.md).

### `internal_error`
A bug. Take the `request_id` from the user-facing error or metrics window, find it in logs,
reproduce with the mock provider, add a regression test.

### Slow responses (TTFT above SLO)
Compare with the platform baseline in `benchmarks/` (≈20 ms): if the platform is fast, the
provider is slow → check provider latency or switch the Fast model to a smaller one. If many
generations are `stopped`, answers are too slow or too long (consider `MAX_OUTPUT_TOKENS`).

### Uploads failing
413 → file above `UPLOAD_MAX_BYTES` (also nginx `client_max_body_size` in compose);
415 → type not in the allowlist; 422 → empty or scanned PDF without text. Check
`uploaded_files` growth: purge runs hourly (`expired awaiting purge` in the diagnosis report).

### Web search returns nothing
DuckDuckGo throttling → set `SEARCH_PROVIDER=tavily` + `TAVILY_API_KEY`. The assistant answers
without search when the tool fails (tool status `error` in the UI).

## Routine operations

| Task | Command |
|---|---|
| Deploy | merge to `main` (CI deploys after tests) |
| Rollback | Render → Deploys → redeploy previous; or revert the commit |
| Migrations | run automatically by the container entrypoint |
| Telemetry retention | `DELETE FROM chat_requests WHERE created_at < now() - interval '30 days';` (monthly) |
| Benchmark | `make bench URL=… N=30` (raise the rate limit for the run) |
