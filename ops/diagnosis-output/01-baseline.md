# Nexa diagnosis report

- Generated: 2026-10-03T12:33:25Z
- Target: `http://localhost:8080` · window: last 60 min

## Health (HTTP 200)
```json
{"status":"ok","version":"1.0.0","environment":"production","database":"ok","llm_provider":"mock","search_provider":"mock"}
```

## Metrics (HTTP 200)
```json
{
    "window_minutes": 60,
    "since": "2026-10-03T11:33:24.974351Z",
    "total_requests": 328,
    "by_status": {
        "completed": 326,
        "stopped": 1,
        "error": 1
    },
    "by_capability": {
        "fast": 326,
        "reasoning": 1,
        "vision": 1
    },
    "errors_by_code": {
        "upstream_unavailable": 1
    },
    "tool_usage": {
        "calculator": 71,
        "unit_convert": 2,
        "web_search": 72
    },
    "error_rate": 0.003,
    "total_retries": 3,
    "ttft_ms": {
        "p50": 10.0,
        "p95": 14.0,
        "max": 56.0
    },
    "duration_ms": {
        "p50": 139.5,
        "p95": 277.6,
        "max": 3990.0
    },
    "feedback": {
        "up": 1,
        "down": 0
    }
}
```

## Automatic findings
- 🟢 Service healthy (version 1.0.0, llm=mock, search=mock).
- 🟢 Error rate 0.3% within SLO (328 requests).
  - `upstream_unavailable` × 1: Model provider unreachable or 5xx → check provider status page; retries are already applied (LLM_MAX_RETRIES). Consider a fallback LLM_BASE_URL.
- 🟢 TTFT p95 14 ms (SLO 2000 ms).

## Containers
```
SERVICE    STATE     STATUS
backend    running   Up 20 seconds (healthy)
db         running   Up 18 minutes (healthy)
frontend   running   Up About a minute (healthy)
```

## Backend warnings/errors (last 60m, newest 25)
```
```

## Database (last hour, content-free telemetry)
```
  status   | capability | requests | avg_ttft_ms | retries 
-----------+------------+----------+-------------+---------
 completed | fast       |      324 |           7 |       0
 completed | vision     |        1 |          13 |       0
 stopped   | fast       |        1 |             |       0
 completed | reasoning  |        1 |          13 |       0
 error     | fast       |        1 |             |       3
(5 rows)

 uploads retained: 4, expired awaiting purge: 0

```
