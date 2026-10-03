---
name: release-check
description: Run the full pre-merge verification for Nexa (lint, types, unit, integration, contract, frontend tests, build, e2e) and summarise results. Use before opening or approving a PR.
---

# Release check

Run from the repository root and report each step as pass/fail with the failing output.
Stop at the first failing group, fix, and re-run that group.

```bash
make check          # backend lint+types+unit+integration, frontend lint+types+contract+tests+build
make e2e            # Playwright: real frontend + backend with the mock model
```

If Docker is available, also run the containerised path CI uses:

```bash
docker compose up --build -d --wait
E2E_BASE_URL=http://localhost:8080 npx --prefix e2e playwright test
```

Then use the `nexa` MCP tools: `service_health` (expect `status: ok`) and `contract_drift`
(expect `in_sync: true`).

Report format:

| Group | Result | Notes |
|---|---|---|
| Backend lint/types | ✅/❌ | |
| Backend unit | ✅/❌ | count |
| Backend integration | ✅/❌ | count |
| Frontend lint/types/contract | ✅/❌ | |
| Frontend tests | ✅/❌ | count |
| Build | ✅/❌ | |
| E2E | ✅/❌ | count |

Never claim a step passed without running it in this session.
