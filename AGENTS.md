# AGENTS.md — instructions for AI coding agents working on Nexa

Nexa is a fast, anonymous, multimodal AI assistant (web). Read `product-spec.md` for scope —
especially the **Excluded** list (no accounts, no server-side chat history, no code execution,
no cross-file reasoning, no image generation). Don't build excluded features; keep the
extension points instead.

## Repository map

| Path | What |
|---|---|
| `openapi.yaml` | **API contract — source of truth** for frontend and backend |
| `backend/` | Python 3.12 · FastAPI · SQLAlchemy (async) · Alembic · uv |
| `backend/app/services/` | chat orchestrator, router, safety, context, tools, LLM providers |
| `frontend/` | React 19 · TypeScript · Vite · Zustand · Vitest |
| `frontend/src/api/` | the only place that talks HTTP; `schema.gen.ts` is generated |
| `e2e/` | Playwright browser tests (real frontend + backend, mock model) |
| `mcp-server/` | MCP server with read-only project tools (contract, health, metrics, chat probe) |
| `agent-capabilities/`, `custom-agent/`, `agent-hooks/` | agent extension pack (skills, subagents, guardrails) |
| `docs/`, `security/`, `ops/` | documentation, security artefacts, operations tooling |

## Commands (run from repo root)

```bash
make install          # all dependencies
make dev-backend      # API on :8000 (mock model by default)
make dev-frontend     # UI on :5173
make check            # lint + types + all unit/integration tests + contract drift + build
make e2e              # Playwright end-to-end
make up               # docker compose stack on :8080
```

## Rules

1. **Contract first.** Change `openapi.yaml` → `npm --prefix frontend run gen:api` → backend
   schemas → tests. Never hand-edit `frontend/src/api/schema.gen.ts` (a hook blocks it).
   Skill: `contract-first-change`.
2. **Every model call goes through `ChatService.stream`** so routing, safety checks
   (request + every tool call), retries and telemetry apply. No side doors to the LLM.
3. **Untrusted text stays fenced.** Documents → `<document>`, search results →
   `<search_results>`; tools must remain read-only and never fetch user-supplied URLs.
4. **No secrets in the repo**, no user content in logs or `chat_requests` telemetry.
   Configuration comes from environment variables (`backend/app/core/config.py`, `.env.example`).
5. **Tests with every change**: unit tests for logic, integration tests (HTTP + DB, validated
   against the contract) for endpoints, Vitest for frontend logic/components, Playwright for
   new user flows. Use the deterministic mock provider (`LLM_PROVIDER=mock`) — tests must not
   need network access or API keys.
6. **Migrations are immutable once merged.** Add a new Alembic revision; don't edit old ones.
7. **User-facing errors are friendly** and never include stack traces, hostnames or provider names.
8. Frontend code calls the backend only through `src/api/client.ts` (ESLint enforces it).
9. Keep it fast: no extra model round-trips on the hot path (routing is heuristic on purpose).

## Style

- Python: ruff (lint + format, line length 120), mypy-clean, type hints everywhere, small
  services with injected dependencies (see `app/container.py`).
- TypeScript: strict mode, ESLint + Prettier, pure logic in `src/lib/` with tests next to it.
- Match the surrounding code's naming and comment density; comments explain *why*.

## Definition of done

`make check` passes, `make e2e` passes for UI changes, docs updated when behaviour or setup
changes, and the review checklist in `agent-capabilities/review-checklist.md` is satisfied.
