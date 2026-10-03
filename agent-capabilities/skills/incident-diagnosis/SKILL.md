---
name: incident-diagnosis
description: Diagnose a degraded or failing Nexa deployment (errors, slow responses, failing uploads) using health, metrics, logs and the ops runbook. Read-only investigation that ends with a written diagnosis.
---

# Incident diagnosis

1. **Health** – MCP `service_health` (or `curl $URL/api/v1/health`). `database: unavailable`
   → follow "Database unavailable" in `ops/runbook.md`.
2. **Metrics** – MCP `service_metrics` with `window_minutes` covering the incident.
   Read `errors_by_code`:
   - `upstream_unavailable` / `upstream_rate_limited` → model provider outage or quota;
   - `upstream_misconfigured` → bad/expired `LLM_API_KEY`;
   - `upstream_bad_request` → oversized context or unsupported content for the model;
   - `internal_error` → application bug: find the request id in logs.
   Compare `ttft_ms.p95` with the SLO in `ops/slo.md`; check `total_retries`.
3. **Logs** – `ops/diagnose.sh` collects health, metrics, container status and recent error
   logs in one report (`ops/diagnose.sh http://localhost:8080 > report.md`).
4. **Reproduce** – MCP `chat_probe` with a minimal message; for search issues set
   `web_search: true`.
5. **Write up** – symptoms, evidence (metric values, log lines with request ids), root
   cause, remediation, follow-ups. Never paste user content or secrets into the report.
