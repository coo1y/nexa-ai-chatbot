# Database

Conversations are deliberately **not** stored on the server (product requirement: local
history). The database holds only what the server needs.

| Table | Contents | Retention |
|---|---|---|
| `uploaded_files` | owner `client_id`, filename, type, extracted document text or normalised image bytes, page count, dimensions | `UPLOAD_RETENTION_HOURS` (24 h); purged hourly; deleted when the user deletes the conversation |
| `feedback` | rating (up/down), optional comment, message/conversation ids, capability/model | until deleted by operators |
| `chat_requests` | routing mode/capability/model, tools used, safety action, status, error code, retries, token counts, TTFT, duration — **no message content** | operational window (purge policy in `security/ai-tool-data-policy.md`) |

Schema: `backend/app/db/models.py`. Data access only through repositories
(`backend/app/db/repositories.py`). Timestamps are timezone-aware UTC on every backend
(`UTCDateTime` type), and constraint names follow a fixed naming convention so migrations are
portable.

## Environments

| Environment | `DATABASE_URL` | Schema management |
|---|---|---|
| Local dev (`make dev-backend`) | `sqlite+aiosqlite:///./data/nexa.db` (default) | auto `create_all` on startup (dev only) |
| Unit/integration tests | temp SQLite per test, or `TEST_DATABASE_URL` (Postgres in CI) | `create_all` + tables cleaned per test |
| Docker Compose | `postgresql+asyncpg://nexa:…@db:5432/nexa` | `alembic upgrade head` in the container entrypoint |
| CI | Postgres 16 service container | migrations upgrade → `alembic check` → downgrade → upgrade, then integration tests |
| Production (Render) | managed Postgres (`postgres://…` is normalised to `postgresql+asyncpg://`) | entrypoint migrations |

## Migrations

```bash
cd backend
uv run alembic upgrade head                              # apply
uv run alembic revision --autogenerate -m "add x"        # new revision (never edit merged ones)
uv run alembic check                                     # models == migrations?
```

`tests/integration/test_migrations.py` verifies that upgrading produces exactly the ORM schema
and that downgrade works.

## Resilience

If the database is unavailable, `/health` returns 503 `degraded`, DB-backed endpoints return
a handled 503 `service_unavailable`, and chat keeps streaming (attachments can't be loaded and
telemetry is skipped with a one-line warning). Recovery is automatic (`pool_pre_ping`). See
`ops/diagnosis-output/03-database-outage.md`.
