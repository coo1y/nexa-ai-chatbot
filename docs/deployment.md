# Deployment

## Target: Render (Docker web service + managed PostgreSQL)

The root `Dockerfile` builds one production image: FastAPI serves the API **and** the built
React app from the same origin (no CORS, no proxy needed). `render.yaml` is a Render
Blueprint that creates the web service and the database.

### One-time setup

1. Push this repository to GitHub.
2. Render → **New → Blueprint** → select the repo. Render reads `render.yaml` and creates
   `nexa` (web) and `nexa-db` (Postgres). `OPS_TOKEN` is generated automatically.
3. In the `nexa` service → **Environment**, set `LLM_API_KEY` (e.g. a Groq key from
   console.groq.com; any OpenAI-compatible host works — also set `LLM_BASE_URL` and the
   `MODEL_*` ids if you use another one).
4. Service → **Settings → Deploy Hook**: copy the URL.
5. GitHub repo → **Settings → Secrets and variables → Actions**:
   * secret `RENDER_DEPLOY_HOOK_URL` = the deploy hook URL
   * variable `APP_URL` = `https://<your-service>.onrender.com`
   * (optional) secret `ANTHROPIC_API_KEY` to enable the AI PR-audit workflow.
6. Create a `production` environment in GitHub (optionally with required reviewers).

### Continuous deployment

`autoDeploy` is off in Render. `.github/workflows/ci.yml` deploys only when **every** job
(backend lint/types/unit/integration on Postgres, frontend, docker-compose e2e, production
image build) succeeds on `main`:

```
push to main → CI jobs ─┬─ all green → deploy job → POST deploy hook → poll /api/v1/health
                        └─ any red  → no deploy                     → smoke: /capabilities, SPA
```

The container entrypoint runs `alembic upgrade head` before starting uvicorn, so schema
changes ship with the code.

### Proof of deployment

- **Live URL: <https://nexa-c8g1.onrender.com>** (Render free plan, region Singapore: web
  service `nexa` + PostgreSQL 18 `nexa-db`)
- Health check, 2026-10-03:

  ```console
  $ curl https://nexa-c8g1.onrender.com/api/v1/health
  {"status":"ok","version":"1.0.0","environment":"production","database":"ok","llm_provider":"openai_compatible","search_provider":"duckduckgo"}
  ```

  `database: ok` shows the migrations ran against the managed Postgres; `openai_compatible`
  shows the real open-source models (Groq) are in use, not the mock.
- CD run: the `Deploy to Render` job of the
  [CI/CD workflow](https://github.com/coo1y/nexa-ai-chatbot/actions/workflows/ci.yml) on `main`.

The free plan sleeps when idle: the first request after a pause can take 30–60 s.

### Notes

* The web service and the database must be in the **same region** (`render.yaml` pins both to
  `singapore`). The `DATABASE_URL` Render injects uses the internal hostname, which does not
  resolve across regions: the container then exits during `alembic upgrade head` with
  `socket.gaierror: Name or service not known`. A Render database cannot change region, so
  if it was created elsewhere, delete it and re-sync the Blueprint.
* Render's free plan sleeps idle services (first request after idle is slow) and free
  Postgres instances expire after 30 days — use a paid plan for anything long-lived.
* Metrics: `curl -H "Authorization: Bearer $OPS_TOKEN" $APP_URL/api/v1/metrics`.
* Rollback: Render dashboard → Deploys → redeploy a previous image, or revert the commit.

## Alternatives

The same image runs anywhere that runs containers:

```bash
docker build -t nexa .
docker run -p 8000:8000 -e DATABASE_URL=postgresql://… -e LLM_PROVIDER=openai_compatible \
  -e LLM_API_KEY=… -e OPS_TOKEN=… nexa
```

* **Fly.io**: `fly launch --dockerfile Dockerfile`, `fly postgres create`, `fly secrets set …`.
* **Google Cloud Run**: `gcloud run deploy nexa --source . --port 8000` + Cloud SQL.

## Local production-like stack

```bash
cp .env.example .env    # optional: real model key
docker compose up --build -d --wait
open http://localhost:8080
```
