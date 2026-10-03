# Testing

Every layer has its own suite. Unit and integration tests are **separate directories with a
separate pytest marker** and separate CI steps. None of them needs network access or API keys:
the deterministic mock LLM and mock search providers stand in for external services.

| Suite | Location | Count | What it covers | Run |
|---|---|---|---|---|
| Backend unit | `backend/tests/unit/` | 138 | tools (calculator, units, date/time, data processing), router, safety rules & guard model, context assembly & document excerpting, file extraction (PDF/DOCX/XLSX/HTML/images, rejection cases), chat orchestrator (retries, tool loop bounds, blocked requests, search degradation), OpenAI adapter (stream assembly, error mapping), config, rate limiter | `make test-unit` |
| Backend integration | `backend/tests/integration/` (`-m integration`) | 41 | Full HTTP → service → database flows: streamed chat, coding, manual capabilities, utility tools, manual & automatic web search with citations, regenerate, edit, long context, retry/error, safety block, validation, rate limiting, uploads (documents, images, multiple files, ownership, expiry, rejections), feedback, metrics, body limits, DB outage, **contract tests**, **migrations** | `make test-integration` (SQLite) / `TEST_DATABASE_URL=postgresql+asyncpg://… make test-integration` |
| Frontend | `frontend/src/**/*.test.ts(x)` | 66 | SSE parser (chunk boundaries, CRLF, UTF-8), API client (headers, errors, aborts), conversation logic (regenerate/edit/stream reducer), citations, storage (quota, corruption, recovery), chat store (send/stop/retry/regenerate/edit/feedback/conversation management), settings, and UI tests of the whole App (streaming render, sources panel, stop, edit, retry, uploads, capability/search toggles, rename/delete, theme), full-size image viewer | `make test-frontend` |
| End-to-end | `e2e/tests/` | 14 | Real browser against the real frontend + backend: all MVP acceptance flows, plus opening an image full size | `make e2e` or `make e2e-docker` |
| MCP server | `mcp-server/tests/` | 6 | URL allow-list, drift detection, stream summarising, tool registration | `make test-mcp` |
| Agent hooks | `agent-hooks/tests/` | 6 | secret guard, protected paths, shell guardrails | `make test-hooks` |

Coverage (last run): backend **90 %** lines, frontend **81 %** statements
(`uv run pytest --cov`, `npm run test:coverage`).

## Contract tests

* `test_contract.py` — the FastAPI app and `openapi.yaml` declare the same operations,
  success codes, schema properties and request `required` fields; every stream event is
  documented under `x-stream-events`.
* The `contract` fixture validates responses and **each SSE event** against the YAML schemas.
* `npm run check:api` — generated TypeScript types match the YAML.

## Mock provider triggers (for deterministic tests)

| Message contains | Behaviour |
|---|---|
| `calculate …`, `what is 2 * 3` | calculator tool call |
| `convert 10 km to miles` | unit_convert tool call |
| `what time` / `today's date` | datetime tool call |
| `statistics` + numbers | data_process tool call |
| `[[mock:fail]]` | upstream failure on every attempt (retry exhaustion) |
| `[[mock:slow]]` | slow token stream (for stop-generation tests) |

## Acceptance criteria → tests

| # | Spec criterion | Automated by |
|---|---|---|
| 1–4 | open without login, start chat, send, streamed reply | e2e `chat.spec.ts` · App.test |
| 5 | coding questions | e2e code block · integration `test_coding_question` |
| 6 | image upload & analysis | e2e `files.spec.ts` · `test_image_upload_routes_to_vision` |
| 7–8 | summarise document, document Q&A | e2e · `test_upload_and_summarise_document`, `test_document_question_answering_across_turns` |
| 9 | multiple files independently | e2e · `test_multiple_files_analysed_independently` |
| 10–12 | manual search, automatic search, citations & sources | e2e · `test_manual_web_search_with_citations`, `test_automatic_web_search` · App.test sources panel |
| 13 | calculator / conversion / date-time / data processing | e2e · `test_utility_tools` |
| 14 | stop generation | e2e · chatStore & App tests |
| 15–16 | regenerate, edit latest message | e2e · integration · store tests |
| 17–19 | local conversations, rename, delete | e2e `conversations.spec.ts` (persists across reload) · App.test |
| 20 | Fast / Reasoning / Vision | e2e · `test_manual_capability_selection` |
| 21 | light/dark themes | e2e · App.test |
| 22 | 👍/👎 feedback | e2e · `test_feedback_create_and_update` |
| 23 | friendly error + Retry | e2e · `test_failure_shows_friendly_retryable_error` · App.test |
| 24 | long context without cross-conversation memory | `test_long_context_conversation` · context unit tests |
