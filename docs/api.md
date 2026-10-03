# API

The contract lives in [`../openapi.yaml`](../openapi.yaml) (OpenAPI 3.1). Interactive docs are
served by the backend at `/api/v1/docs`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Liveness/readiness (503 + `degraded` when the DB is down) |
| GET | `/api/v1/capabilities` | Capabilities, tools, upload limits for the UI |
| POST | `/api/v1/chat/stream` | Generate a response (Server-Sent Events) |
| POST | `/api/v1/files` | Upload a document or image (multipart) |
| GET / DELETE | `/api/v1/files/{id}` | File metadata / delete (owner only) |
| POST | `/api/v1/feedback` | 👍/👎 on a response (re-submit to change) |
| GET | `/api/v1/metrics` | Content-free ops metrics (Bearer `OPS_TOKEN`) |

Stateful calls carry `X-Client-Id` (anonymous browser id). Errors share one envelope:
`{"error": {"code", "message", "request_id"}}` — messages are safe to show to users.

## Streaming protocol

```
event: start        {"request_id","message_id","routing":{"mode","capability","model","reason"}}
event: tool_call    {"id","name","label","input"}
event: tool_result  {"id","name","status","summary","duration_ms"}
event: sources      {"sources":[{"id":1,"title","url","domain","snippet"}]}
event: safety       {"action":"allow_with_guidance|block","category","message"}
event: delta        {"text":"..."}
event: error        {"code","message","retryable"}
event: done         {"finish_reason":"stop|length|blocked|error","usage",...,"ttft_ms","duration_ms"}
```

**Regenerate** = resend the conversation without the last assistant message.
**Edit latest message** = resend with the last user message changed (later messages dropped).
**Stop** = abort the request.

## How the contract is enforced

1. `openapi.yaml` was written first, from the product spec and the UI's needs.
2. Frontend types are generated from it (`npm run gen:api` → `src/api/schema.gen.ts`);
   `npm run check:api` fails CI if they are stale.
3. Backend contract tests (`backend/tests/integration/test_contract.py`) assert the FastAPI
   app exposes exactly the same operations, status codes, schema properties and request
   `required` fields.
4. Integration tests validate real responses **and every streamed event** against the YAML
   schemas with JSON Schema (`contract` fixture).
5. The `nexa` MCP server's `contract_drift` tool compares the YAML with a running backend.
