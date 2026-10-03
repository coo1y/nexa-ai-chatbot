# Nexa diagnosis report

- Generated: 2026-10-03T12:38:32Z
- Target: `http://localhost:8080` · window: last 10 min

## Health (HTTP 200)
```json
{"status":"ok","version":"1.0.0","environment":"production","database":"ok","llm_provider":"mock","search_provider":"mock"}
```

## Metrics (HTTP 200)
```json
{
    "window_minutes": 10,
    "since": "2026-10-03T12:28:32.385806Z",
    "total_requests": 320,
    "by_status": {
        "completed": 314,
        "error": 6
    },
    "by_capability": {
        "fast": 320
    },
    "errors_by_code": {
        "upstream_unavailable": 6
    },
    "tool_usage": {
        "calculator": 70,
        "web_search": 70
    },
    "error_rate": 0.0187,
    "total_retries": 18,
    "ttft_ms": {
        "p50": 10.0,
        "p95": 14.0,
        "max": 56.0
    },
    "duration_ms": {
        "p50": 140.0,
        "p95": 279.1,
        "max": 4083.0
    },
    "feedback": {
        "up": 0,
        "down": 0
    }
}
```

## Automatic findings
- 🟢 Service healthy (version 1.0.0, llm=mock, search=mock).
- 🟢 Error rate 1.9% within SLO (320 requests).
  - `upstream_unavailable` × 6: Model provider unreachable or 5xx → check provider status page; retries are already applied (LLM_MAX_RETRIES). Consider a fallback LLM_BASE_URL.
- 🟢 TTFT p95 14 ms (SLO 2000 ms).

## Containers
```
SERVICE    STATE     STATUS
backend    running   Up About a minute (healthy)
db         running   Up 35 seconds (healthy)
frontend   running   Up 7 minutes (healthy)
```

## Backend warnings/errors (last 10m, newest 25)
```
backend-1  | {"ts": "2026-10-03T12:37:00.783554+00:00", "level": "WARNING", "logger": "app.services.chat", "msg": "chat telemetry not persisted (gaierror: [Errno -2] Name or service not known)", "request_id": "93420709193ff467568e7d536c80ed89"}
backend-1  | {"ts": "2026-10-03T12:37:00.927675+00:00", "level": "WARNING", "logger": "app", "msg": "dependency unavailable: gaierror: [Errno -2] Name or service not known", "request_id": "9e13ae123bb7ab6a18abe6ec2fe328f3"}
```

## Database (last hour, content-free telemetry)
```
  status   | capability | requests | avg_ttft_ms | retries 
-----------+------------+----------+-------------+---------
 completed | fast       |      328 |           7 |       0
 error     | fast       |        7 |             |      21
 completed | vision     |        1 |          13 |       0
 stopped   | fast       |        1 |             |       0
 completed | reasoning  |        1 |          13 |       0
(5 rows)

 uploads retained: 4, expired awaiting purge: 0

```
