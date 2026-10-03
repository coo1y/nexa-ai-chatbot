# Operations

| Artefact | Purpose |
|---|---|
| [runbook.md](runbook.md) | Signals and playbooks per failure mode |
| [slo.md](slo.md) | Latency budget, SLOs, how they were derived |
| [diagnose.sh](diagnose.sh) + [analyze.py](analyze.py) | One-command diagnosis report (health, metrics → automatic findings, containers, warnings, DB view) |
| [bench_latency.py](bench_latency.py) | TTFT / total latency benchmark over the real streaming API |
| [benchmarks/](benchmarks/) | Benchmark outputs |
| [diagnosis-output/](diagnosis-output/) | **Operational diagnosis outputs from an incident drill** |

## Incident drill — 2026-10-03 (docker compose: nginx + FastAPI + Postgres, mock providers)

| Step | What was done | Report | Diagnosis |
|---|---|---|---|
| 1 | Baseline after ~330 requests (benchmarks + e2e) | [01-baseline.md](diagnosis-output/01-baseline.md) | 🟢 healthy, error rate 0.3 %, TTFT p95 14 ms |
| 2 | Simulated model-provider outage: 6 of 10 requests hit a failing upstream | [02-model-provider-outage.md](diagnosis-output/02-model-provider-outage.md) | 🔴 error rate 60 %, `upstream_unavailable` × 6 with remediation hint, 🟡 18 retries / 10 requests |
| 3 | `docker compose stop db` | [03-database-outage.md](diagnosis-output/03-database-outage.md) | 🔴 database unavailable (health 503), metrics 503 `service_unavailable`; logs show one-line warnings with request ids; a chat request during the outage still completed |
| 4 | `docker compose start db` | [04-recovered.md](diagnosis-output/04-recovered.md) | 🟢 recovered automatically, no backend restart |

The first run of step 3 exposed two defects — an unhandled 500 on `/metrics` and multi-hundred-line
tracebacks per request flooding the logs. Both were fixed (handled 503, one-line warnings,
regression test `test_database_outage_degrades_gracefully`) and the drill was re-run; the
reports above are from the re-run.
