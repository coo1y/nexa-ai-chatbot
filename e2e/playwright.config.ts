import { defineConfig, devices } from '@playwright/test';

/**
 * By default Playwright starts the backend (mock LLM + mock search, throwaway SQLite DB)
 * and the Vite dev server. Set E2E_BASE_URL to test an already running stack instead,
 * e.g. `docker compose up` (http://localhost:8080) or a deployed URL.
 */
const externalBaseUrl = process.env.E2E_BASE_URL;
const backendPort = 8001;
const frontendPort = 5174;

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  timeout: 30_000,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: externalBaseUrl ?? `http://localhost:${frontendPort}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: externalBaseUrl
    ? undefined
    : [
        {
          command: `uv run --project ../backend uvicorn app.asgi:app --app-dir ../backend --port ${backendPort}`,
          url: `http://localhost:${backendPort}/api/v1/health`,
          reuseExistingServer: !process.env.CI,
          env: {
            APP_ENV: 'development',
            DATABASE_URL: 'sqlite+aiosqlite:///./.e2e-data/e2e.db',
            LLM_PROVIDER: 'mock',
            SEARCH_PROVIDER: 'mock',
            LOG_LEVEL: 'WARNING',
          },
        },
        {
          command: `npm --prefix ../frontend run dev -- --port ${frontendPort} --strictPort`,
          url: `http://localhost:${frontendPort}`,
          reuseExistingServer: !process.env.CI,
          env: { VITE_API_PROXY_TARGET: `http://localhost:${backendPort}` },
        },
      ],
});
