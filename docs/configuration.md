# Configuration

All settings are environment variables (or `backend/.env`), defined in
`backend/app/core/config.py`. Defaults run fully offline.

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | `development` \| `test` \| `production` |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/nexa.db` | SQLAlchemy async URL; `postgres://` URLs are normalised |
| `LLM_PROVIDER` | `mock` | `openai_compatible` or `mock` |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` | Any OpenAI-compatible endpoint (Groq, OpenRouter, Together, vLLM, Ollama) |
| `LLM_API_KEY` | — | Provider key (required for `openai_compatible`) |
| `MODEL_FAST` / `MODEL_REASONING` / `MODEL_VISION` | `qwen/qwen3.8-27b` / `openai/gpt-oss-120b` / `qwen/qwen3.8-27b` | Model per capability. Groq retires models regularly: a 404 `model_not_found` from the provider means an id must be updated ([deprecations](https://console.groq.com/docs/deprecations)) |
| `LLM_MAX_RETRIES` | `3` | Retries after the first attempt |
| `LLM_RETRY_BASE_DELAY_SECONDS` | `0.5` | Exponential backoff base |
| `LLM_TIMEOUT_SECONDS` | `60` | Per request |
| `MAX_OUTPUT_TOKENS` | `2048` | Response cap |
| `MAX_TOOL_ITERATIONS` | `4` | Model ↔ tool round trips per message |
| `CONTEXT_MAX_TOKENS` | `24000` | Prompt budget for long conversations/documents |
| `SAFETY_MODEL` | — | Optional guard model (e.g. `meta-llama/llama-guard-4-12b`) |
| `SEARCH_PROVIDER` | `duckduckgo` | `duckduckgo` \| `tavily` \| `mock` |
| `TAVILY_API_KEY` | — | Required for Tavily |
| `UPLOAD_MAX_BYTES` | `10485760` | Per file |
| `UPLOAD_RETENTION_HOURS` | `24` | Server-side retention of uploads |
| `MAX_REQUEST_BYTES` | `4194304` | JSON body limit |
| `RATE_LIMIT_CHAT_PER_MINUTE` / `RATE_LIMIT_UPLOAD_PER_MINUTE` | `30` / `20` | Per client (×3 per IP) |
| `OPS_TOKEN` | — | Bearer token for `/metrics` (metrics disabled in production without it) |
| `CORS_ORIGINS` | `http://localhost:5173,…` | Comma-separated |
| `STATIC_DIR` | — | Serve the built SPA from the backend (single-container deploy) |
| `LOG_LEVEL` / `LOG_JSON` | `INFO` / `false` | JSON logs in containers |

Frontend: `VITE_API_BASE_URL` (default `/api/v1`), `VITE_API_PROXY_TARGET` (dev proxy target).
