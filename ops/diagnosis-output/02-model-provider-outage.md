# Nexa diagnosis report

- Generated: 2026-10-03T12:34:31Z
- Target: `http://localhost:8080` · window: last 1 min

## Health (HTTP 200)
```json
{"status":"ok","version":"1.0.0","environment":"production","database":"ok","llm_provider":"mock","search_provider":"mock"}
```

## Metrics (HTTP 200)
```json
{
    "window_minutes": 1,
    "since": "2026-10-03T12:33:31.194814Z",
    "total_requests": 10,
    "by_status": {
        "completed": 4,
        "error": 6
    },
    "by_capability": {
        "fast": 10
    },
    "errors_by_code": {
        "upstream_unavailable": 6
    },
    "tool_usage": {},
    "error_rate": 0.6,
    "total_retries": 18,
    "ttft_ms": {
        "p50": 13.5,
        "p95": 15.0,
        "max": 15.0
    },
    "duration_ms": {
        "p50": 3136.0,
        "p95": 3985.3,
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
- 🔴 **Error rate 60.0%** exceeds the 2% SLO.
  - `upstream_unavailable` × 6: Model provider unreachable or 5xx → check provider status page; retries are already applied (LLM_MAX_RETRIES). Consider a fallback LLM_BASE_URL.
- 🟢 TTFT p95 15 ms (SLO 2000 ms).
- 🟡 18 model retries for 10 requests — upstream instability is adding latency.

## Containers
```
SERVICE    STATE     STATUS
backend    running   Up About a minute (healthy)
db         running   Up 19 minutes (healthy)
frontend   running   Up 3 minutes (healthy)
```

## Backend warnings/errors (last 1m, newest 25)
```
backend-1  | {"ts": "2026-10-03T12:34:30.111578+00:00", "level": "WARNING", "logger": "app.services.chat", "msg": "chat request failed after 3 retries: mock forced failure (upstream_unavailable)", "request_id": "016f7b7692cca19df5f6036059487157"}
backend-1  | {"ts": "2026-10-03T12:34:30.173817+00:00", "level": "WARNING", "logger": "app.services.chat", "msg": "chat request failed after 3 retries: mock forced failure (upstream_unavailable)", "request_id": "9d15f5c510c9c33cb23554b77c220201"}
backend-1  | {"ts": "2026-10-03T12:34:30.446188+00:00", "level": "WARNING", "logger": "app.services.chat", "msg": "chat request failed after 3 retries: mock forced failure (upstream_unavailable)", "request_id": "43d118204a116a1845edc90e96530822"}
backend-1  | {"ts": "2026-10-03T12:34:30.743339+00:00", "level": "WARNING", "logger": "app.services.chat", "msg": "chat request failed after 3 retries: mock forced failure (upstream_unavailable)", "request_id": "3ac284f4927c9a54fa57e02eb62d7edd"}
backend-1  | {"ts": "2026-10-03T12:34:30.873633+00:00", "level": "WARNING", "logger": "app.services.chat", "msg": "chat request failed after 3 retries: mock forced failure (upstream_unavailable)", "request_id": "4451be3b065e41d312a2d64e091fb339"}
backend-1  | {"ts": "2026-10-03T12:34:31.081269+00:00", "level": "WARNING", "logger": "app.services.chat", "msg": "chat request failed after 3 retries: mock forced failure (upstream_unavailable)", "request_id": "aefcc46015590230c26ecf1509f2c877"}
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
