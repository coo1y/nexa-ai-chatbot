# Nexa MCP server

Read-only project tools for coding agents (registered for Claude Code in `../.mcp.json`).

| Tool | Description |
|---|---|
| `contract_operations` | List operations in `openapi.yaml` |
| `contract_schema(name)` | One component schema |
| `contract_drift(base_url?)` | Compare `openapi.yaml` with a running backend's OpenAPI |
| `service_health(base_url?)` | `/api/v1/health` |
| `service_metrics(window_minutes, base_url?)` | `/api/v1/metrics` (uses `NEXA_OPS_TOKEN`) |
| `chat_probe(message, capability, web_search, base_url?)` | One chat turn summarised: routing, tools, sources, text |

Resource: `nexa://openapi.yaml`.

```bash
uv sync
uv run python nexa_mcp.py          # stdio transport
uv run pytest -q
```

Environment: `NEXA_BASE_URL` (default `http://localhost:8000`), `NEXA_ALLOWED_HOSTS`
(default `localhost,127.0.0.1` — requests to other hosts are refused), `NEXA_OPS_TOKEN`.
