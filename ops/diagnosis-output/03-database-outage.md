# Nexa diagnosis report

- Generated: 2026-10-03T12:37:00Z
- Target: `http://localhost:8080` · window: last 5 min

## Health (HTTP 503)
```json
{"status":"degraded","version":"1.0.0","environment":"production","database":"unavailable","llm_provider":"mock","search_provider":"mock"}
```

## Metrics (HTTP 503)
```json
{
    "error": {
        "code": "service_unavailable",
        "message": "The service is temporarily unavailable. Please try again shortly.",
        "request_id": "9e13ae123bb7ab6a18abe6ec2fe328f3"
    }
}
```

## Automatic findings
- 🔴 **Database unavailable** — health is degraded (HTTP 503). See runbook 'Database unavailable'.
- 🔴 Metrics unavailable (HTTP 503, `service_unavailable`) — telemetry lives in the database.

## Containers
```
SERVICE    STATE     STATUS
backend    running   Up 17 seconds (healthy)
frontend   running   Up 5 minutes (healthy)
```

## Backend warnings/errors (last 5m, newest 25)
```
backend-1  | {"ts": "2026-10-03T12:37:00.783554+00:00", "level": "WARNING", "logger": "app.services.chat", "msg": "chat telemetry not persisted (gaierror: [Errno -2] Name or service not known)", "request_id": "93420709193ff467568e7d536c80ed89"}
backend-1  | {"ts": "2026-10-03T12:37:00.927675+00:00", "level": "WARNING", "logger": "app", "msg": "dependency unavailable: gaierror: [Errno -2] Name or service not known", "request_id": "9e13ae123bb7ab6a18abe6ec2fe328f3"}
```

## Database (last hour, content-free telemetry)
```
service "db" is not running
service "db" is not running
```
