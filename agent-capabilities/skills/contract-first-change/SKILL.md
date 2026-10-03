---
name: contract-first-change
description: Change or add a Nexa API endpoint, field or stream event the contract-first way (openapi.yaml → generated frontend types → backend schemas → contract tests → UI). Use for any change that crosses the frontend/backend boundary.
---

# Contract-first API change

The API contract in `openapi.yaml` is the source of truth. Never change a request/response
shape in only one place.

## Steps

1. **Read the current contract** – use the `nexa` MCP tools `contract_operations` and
   `contract_schema` (or open `openapi.yaml`). Decide the smallest backwards-compatible change
   (add optional fields; don't rename or remove without a migration plan).
2. **Edit `openapi.yaml`.** The PostToolUse hook regenerates
   `frontend/src/api/schema.gen.ts` automatically (`npm --prefix frontend run gen:api`).
   Never edit `schema.gen.ts` by hand — a PreToolUse hook blocks it.
3. **Mirror the change in backend Pydantic models** (`backend/app/schemas/*.py`); keep names
   identical to the component names in the contract.
4. **Implement** in the route (`backend/app/api/routes/`) or service layer
   (`backend/app/services/`). Routes stay thin; logic lives in services.
5. **Tests**
   - Unit test for new service logic in `backend/tests/unit/`.
   - Integration test in `backend/tests/integration/` that calls the endpoint over HTTP and
     validates the payload with the `contract` fixture (JSON-Schema validation against
     `openapi.yaml`). New stream events must be added to `x-stream-events` — the contract
     test enforces it.
6. **Frontend** – types flow from `src/api/types.ts`; call the backend only through
   `src/api/client.ts` (ESLint forbids `fetch` elsewhere). Add/extend Vitest tests.
7. **Verify** – `make check` (or the release-check skill). With a running stack,
   `contract_drift` from the MCP server must report `in_sync: true`.
8. **Document** user-visible changes in `docs/api.md`.

## Done when

- `uv run pytest tests/integration/test_contract.py` passes.
- `npm --prefix frontend run check:api` passes.
- No hand edits to generated files.
