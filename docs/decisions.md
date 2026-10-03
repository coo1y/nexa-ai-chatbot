# Design decisions (ADR log)

| # | Decision | Alternatives | Why |
|---|---|---|---|
| 1 | **FastAPI + async SQLAlchemy** backend | Django, Flask | Native async streaming (SSE) and Pydantic models that mirror the OpenAPI contract. |
| 2 | **OpenAI-compatible provider abstraction** with configurable model ids; Groq default | Provider-specific SDKs, self-hosting | Spec: cloud-hosted open-source models, replaceable implementation, speed first (Groq LPU latency). |
| 3 | **Heuristic routing** (no LLM classifier) | Small classifier model | Zero added latency; transparent `reason` shown in the UI; users can override. |
| 4 | **Conversations in localStorage**, server DB for uploads/feedback/telemetry | Server-side history | Spec requires local history; DB still needed for document Q&A across turns, feedback and ops. Repository interface keeps cloud sync possible. |
| 5 | **Uploads stored in the DB** with 24 h retention | Object storage (S3) | One managed dependency for MVP; swap to object storage behind `FileRepository` when scaling. |
| 6 | **Search pre-fetch** when needed + model-callable `web_search` | Model-decided only | Saves a model round-trip on obviously time-sensitive questions; still supports follow-up searches. |
| 7 | **Relevant-excerpt selection** for long documents | Truncation, embeddings/RAG | Better answers than truncation without a vector store; no extra latency or infra. |
| 8 | **Heuristic safety + optional guard model** | Guard model on every request | Hard blocks are instant; the guard model is opt-in because it adds a round-trip. |
| 9 | **Single-container cloud image**, compose with nginx locally | Separate static hosting | Same-origin SSE without proxy buffering issues; one service to deploy. |
| 10 | **SSE over fetch** | WebSockets | One-directional streaming; works through proxies; abort = stop. |
