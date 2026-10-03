# AI tool & data policy

This policy covers (A) the AI features inside Nexa and (B) the AI tools used to build and operate it.

## A. Nexa (the product)

### Data we process

| Data | Where | Retention | Shared with |
|---|---|---|---|
| Conversation history | The user's browser (localStorage) only | Until the user deletes it | — |
| Message content for the current turn | Backend memory while generating | Not persisted | Model provider (inference only) |
| Uploaded documents (extracted text) and images (re-encoded, metadata stripped) | Database | 24 h (`UPLOAD_RETENTION_HOURS`), hourly purge; deleted immediately when the conversation is deleted | Model provider, only when attached to a turn |
| Search queries | Backend memory | Not persisted | Search provider (DuckDuckGo/Tavily) |
| Feedback (👍/👎, optional comment) | Database | Until operators delete it | — |
| Request telemetry (capability, model, tools, status, latency, token counts) | Database | 30 days recommended (`DELETE FROM chat_requests WHERE created_at < now() - interval '30 days'`) | — |
| Anonymous client id | Browser + DB rows above | As above | — |

**Never stored or logged**: message text, model output, document text in logs, IP addresses
in the database, API keys.

### Provider requirements

* Use only providers whose API terms state that **API inputs are not used for training** and
  that offer a short or zero retention option; record the provider and plan in the deployment
  notes. The default (Groq API) meets this at the time of writing — re-check on provider change.
* Models must be open-source (product strategy) and configured per capability via environment.
* A provider change requires: updating `.env`/Render settings, running the e2e suite, and a
  note in `docs/decisions.md`.

### Safety commitments

* Safety checks run on every request and every tool call (see `docs/architecture.md`).
* Self-harm conversations receive supportive guidance; methods are never provided.
* The assistant does not identify real people from facial features.
* No code execution, no image generation, no autonomous actions outside the conversation.
* The UI states that answers can be wrong; web answers carry citations.

### User rights

Users control their history (rename/delete per conversation). Deleting a conversation also
deletes its uploads from the server. No account is required, and no data is linked to an
identity.

## B. AI tools used in development and operations

| Allowed | Conditions |
|---|---|
| Coding agents (Claude Code and others via `AGENTS.md`) on this repository | Must operate under `.claude/settings.json` permissions and the `agent-hooks` guardrails; outputs are reviewed by a human and must pass CI |
| AI PR review (`pr-audit.yml`) | Advisory only; deterministic scanners and human review decide merges |
| MCP server (`mcp-server/`) | Read-only tools, localhost by default; production metrics only with an explicitly provided ops token |

**Prohibited**

* Pasting secrets (API keys, `.env`, tokens) or production user data (uploaded documents,
  feedback comments) into any AI tool prompt.
* Giving agents production credentials or write access to production systems.
* Merging AI-generated code without tests and human review.
* Using customer data to evaluate or fine-tune models without explicit consent.

**Data in prompts**: use synthetic fixtures (`backend/tests/fixtures.py`) or the mock provider
for reproductions. Diagnosis reports produced by agents must contain metrics and request ids
only, never user content.
