---
name: add-assistant-tool
description: Add a new tool the Nexa assistant can call (e.g. currency conversion, dictionary). Covers the tool implementation, registry, safety rules, routing hints, tests, UI icon and docs.
---

# Add an assistant tool

Tools live in `backend/app/services/tools/` and are exposed to models via OpenAI-style
function calling. Every tool is untrusted-input-in, text-out, time-boxed and read-only.

## Steps

1. **Implement** `backend/app/services/tools/<name>.py`:
   - a pure function with the logic (easy to unit test);
   - an async handler `(args, ToolContext) -> ToolResult` with a model-facing `content` and a
     one-line user-facing `summary`;
   - raise `ToolInputError` for bad arguments (the model sees the message and can retry);
   - a `Tool(...)` with a precise `description` and JSON-Schema `parameters`, and a tight
     `timeout_seconds`.
   - No network calls to user-controlled URLs (SSRF). If the tool needs an external API, put
     the base URL in `Settings` and add the key to `.env.example`.
2. **Register** it in `build_registry()` in `registry.py`.
3. **Safety** – if the tool can be misused, add a rule to `_TOOL_BLOCKS` in
   `backend/app/services/safety.py` with tests in `tests/unit/test_safety.py`.
4. **Mock provider** – teach `app/services/llm/mock.py::_plan_tool_call` a trigger phrase so
   integration and e2e tests can exercise the tool deterministically.
5. **Tests** – unit tests for the logic and handler; an integration case in
   `tests/integration/test_chat_flow.py::test_utility_tools`; the capabilities test lists
   tool names.
6. **UI** – add an icon in `frontend/src/components/ToolActivityList.tsx` (`ICONS`) and an input
   description in `describeInput`.
7. **Docs** – add the tool to the table in `docs/architecture.md`.
8. **Verify** – `make check`, then `chat_probe` (MCP) with the trigger phrase on a running stack.
