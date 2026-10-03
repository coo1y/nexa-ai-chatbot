# End-to-end tests (Playwright)

```bash
npm ci && npx playwright install chromium
npx playwright test                                   # starts backend (mock model, SQLite) + Vite automatically
E2E_BASE_URL=http://localhost:8080 npx playwright test   # against docker compose / any deployment
```

Specs cover the spec's acceptance criteria: chat streaming, regenerate, edit, feedback, coding,
tools, manual and automatic web search with sources, stop, friendly error + retry, capability
selection, document upload/summary/Q&A, multiple files, image analysis, local conversation
management across reloads, themes.
