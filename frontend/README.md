# Nexa frontend (React + TypeScript + Vite)

```bash
npm ci
npm run dev            # http://localhost:5173, proxies /api → http://localhost:8000
npm test               # Vitest (jsdom)
npm run test:coverage
npm run lint && npm run typecheck && npm run format:check
npm run gen:api        # regenerate src/api/schema.gen.ts from ../openapi.yaml
npm run check:api      # fail if generated types are stale (CI)
npm run build
```

| Path | Responsibility |
|---|---|
| `src/api/` | **Only** place that talks HTTP: `client.ts` (typed calls, error mapping, SSE streaming), `sse.ts` (parser), `types.ts` (from generated `schema.gen.ts`) |
| `src/state/chatStore.ts` | Conversations, streaming, stop/regenerate/edit/retry, feedback (API + storage injected → unit-testable) |
| `src/state/settingsStore.ts` | Interface customisation |
| `src/lib/` | Pure logic: stream reducer, regenerate/edit preparation, citations, file validation, formatting |
| `src/storage/` | `ConversationRepository` (localStorage today; cloud sync later) |
| `src/components/` | UI: Sidebar, MessageList/MessageItem, Markdown, ToolActivityList, Composer, SourcesPanel, SettingsDialog |
