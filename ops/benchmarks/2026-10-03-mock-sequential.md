# Latency benchmark

- Target: `http://localhost:8080` · llm=mock · search=mock
- 30 requests per scenario, concurrency 1

| Scenario | OK | TTFT p50 (ms) | TTFT p95 (ms) | Total p50 (ms) | Total p95 (ms) |
|---|---|---|---|---|---|
| plain | 30/30 | 18.9 | 20.9 | 144.4 | 151.1 |
| tool | 30/30 | 18.9 | 20.8 | 133.2 | 138.7 |
| search | 30/30 | 19.1 | 20.4 | 228.9 | 235.8 |
| code | 30/30 | 18.6 | 20.7 | 290.5 | 298.1 |
