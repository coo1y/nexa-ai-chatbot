# Nexa backend (FastAPI)

```bash
uv sync
uv run uvicorn app.asgi:app --reload --port 8000   # API docs: http://localhost:8000/api/v1/docs
uv run pytest tests/unit -q                         # unit
uv run pytest tests/integration -m integration -q   # integration (HTTP + DB + contract + migrations)
uv run ruff check . && uv run ruff format --check . && uv run mypy app
uv run alembic upgrade head                         # migrations (DATABASE_URL)
```

| Module | Responsibility |
|---|---|
| `app/main.py` | App factory, middleware (request ids, security headers, body limits), error handlers, SPA serving |
| `app/container.py` | Composition root (dependency wiring; tests inject fakes here) |
| `app/core/` | Settings, logging, errors, rate limiter |
| `app/api/routes/` | Thin HTTP layer: chat (SSE), files, feedback, health/capabilities/metrics |
| `app/schemas/` | Pydantic models mirroring `../openapi.yaml` |
| `app/services/chat.py` | Orchestrator: routing → safety → search → context → model/tool loop → events → telemetry |
| `app/services/router.py` · `safety.py` · `context.py` · `files.py` | Model routing, safety controls, context window, upload processing |
| `app/services/llm/` | Provider protocol, OpenAI-compatible adapter, deterministic mock |
| `app/services/tools/` | calculator, unit conversion, date/time, data processing, web search, registry |
| `app/db/` | Models, async sessions, repositories; `migrations/` Alembic |

Configuration: `../docs/configuration.md`.
