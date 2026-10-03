# Nexa review checklist (used by humans, the PR-audit workflow and the security-reviewer agent)

## Correctness
- [ ] Behaviour matches `product-spec.md` (and its exclusions: no accounts, no server-side history, no code execution, no cross-file reasoning).
- [ ] Errors reach users as friendly messages; no stack traces, hostnames or provider names.
- [ ] Streaming: every path ends with a `done` event; cancellation (stop) is handled.

## Contract
- [ ] `openapi.yaml`, `backend/app/schemas`, and `frontend/src/api` change together.
- [ ] `schema.gen.ts` regenerated, not hand-edited.
- [ ] New stream events listed in `x-stream-events`.

## Safety & security
- [ ] New user/tool inputs pass through `SafetyService` (request and tool checks).
- [ ] Untrusted text (documents, search results) stays fenced and is never treated as instructions.
- [ ] No outbound requests to user-controlled URLs (SSRF).
- [ ] No secrets in code, tests, logs or fixtures; no message content in logs or telemetry.
- [ ] Upload validation (type allowlist, size, decompression bombs) preserved.
- [ ] Rate limiting and body size limits still apply to new endpoints.

## Quality
- [ ] Unit tests for logic; integration test for each new/changed endpoint; e2e for new UI flows.
- [ ] Frontend talks to the backend only via `src/api/client.ts`.
- [ ] Docs updated (`docs/`, README if setup changed).
