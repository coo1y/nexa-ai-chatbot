# Service level objectives & latency targets

The product spec leaves latency targets to "technical design and benchmarking". They were
set from the platform benchmark (`benchmarks/`) plus a budget for the model provider.

## Latency budget (first token)

| Stage | Budget | Measured |
|---|---|---|
| Edge + routing + safety + context assembly + streaming (platform) | ≤ 100 ms p95 | **≈ 21 ms p95** sequential, 74 ms p95 at concurrency 8 (mock model, nginx + Postgres, local Docker) |
| Web search pre-fetch (when triggered) | ≤ 1.5 s p95 | provider-dependent (mock search adds ≈ 0.2 ms p50) |
| Model time-to-first-token (Fast, Groq) | ≤ 1.0 s p95 | provider-dependent — measure with `make bench` and a real key |

## SLOs (30-day window)

| SLO | Target | Measured by |
|---|---|---|
| Availability (`/health` = 200) | 99.5 % | uptime check |
| Chat error rate (`status=error` / all) | < 2 % | `/metrics` `error_rate` |
| TTFT p95, Fast capability, no search | < 2 s | `/metrics` `ttft_ms.p95` |
| TTFT p95 with web search | < 3.5 s | benchmark scenario `search` |

`ops/analyze.py` flags breaches of the error-rate and TTFT SLOs automatically in diagnosis reports.

## Benchmark results

| File | Setup |
|---|---|
| [`benchmarks/2026-10-03-mock-sequential.md`](benchmarks/2026-10-03-mock-sequential.md) | 4 scenarios × 30 requests, sequential |
| [`benchmarks/2026-10-03-mock-concurrency8.md`](benchmarks/2026-10-03-mock-concurrency8.md) | 4 scenarios × 40 requests, 8 concurrent |

Total times in mock runs are dominated by the mock's deliberate 10 ms per-token delay;
TTFT is the meaningful platform metric.
