# Latency benchmark

- Target: `http://localhost:8080` · llm=mock · search=mock
- 40 requests per scenario, concurrency 8

| Scenario | OK | TTFT p50 (ms) | TTFT p95 (ms) | Total p50 (ms) | Total p95 (ms) |
|---|---|---|---|---|---|
| plain | 40/40 | 17.9 | 74.0 | 181.9 | 277.8 |
| tool | 40/40 | 18.7 | 29.2 | 124.6 | 139.8 |
| search | 40/40 | 23.1 | 45.3 | 235.2 | 287.7 |
| code | 40/40 | 20.8 | 37.1 | 275.2 | 312.7 |
