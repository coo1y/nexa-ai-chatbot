# Nexa — common developer commands. Run `make help`.
.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help install dev-backend dev-frontend lint typecheck test-unit test-integration test-backend \
        test-frontend test-hooks test-mcp test e2e e2e-docker check gen-api up down logs scan diagnose bench

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install backend, frontend, e2e and MCP dependencies
	cd backend && uv sync
	cd frontend && npm ci
	cd e2e && npm ci && npx playwright install chromium
	cd mcp-server && uv sync

dev-backend: ## Run the API on :8000 (SQLite; mock model unless .env configures one)
	cd backend && uv run uvicorn app.asgi:app --reload --port 8000

dev-frontend: ## Run the web app on :5173 (proxies /api to :8000)
	cd frontend && npm run dev

lint: ## Lint and format-check everything
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint && npm run format:check
	cd mcp-server && uv run ruff check --line-length 120 .

typecheck: ## Static type checks
	cd backend && uv run mypy app
	cd frontend && npm run typecheck

test-unit: ## Backend unit tests
	cd backend && uv run pytest tests/unit -q

test-integration: ## Backend integration tests (HTTP + DB; set TEST_DATABASE_URL for Postgres)
	cd backend && uv run pytest tests/integration -m integration -q

test-backend: test-unit test-integration ## All backend tests

test-frontend: ## Frontend unit/component tests
	cd frontend && npm test

test-hooks: ## Agent hook tests
	uv run --no-project --python 3.12 --quiet --with pytest pytest agent-hooks/tests -q -p no:cacheprovider

test-mcp: ## MCP server tests
	cd mcp-server && uv run pytest -q

test: test-backend test-frontend test-hooks test-mcp ## All unit + integration tests

e2e: ## Browser end-to-end tests (starts backend + frontend with the mock model)
	cd e2e && npx playwright test

e2e-docker: up ## End-to-end tests against the docker compose stack
	cd e2e && E2E_BASE_URL=http://localhost:8080 npx playwright test

gen-api: ## Regenerate frontend types from openapi.yaml
	cd frontend && npm run gen:api

check: lint typecheck test ## Everything CI runs except e2e and docker
	cd frontend && npm run check:api && npm run build

up: ## Start the full stack with Docker Compose (http://localhost:8080)
	docker compose up --build --detach --wait

down: ## Stop the stack (keeps the database volume)
	docker compose down

logs: ## Follow stack logs
	docker compose logs -f

scan: ## Deterministic security scans → security/scan-results/
	./security/run-scans.sh

diagnose: ## Operational diagnosis report for a running stack (URL=http://localhost:8080)
	./ops/diagnose.sh $${URL:-http://localhost:8080}

bench: ## Latency benchmark (URL=..., N=...)
	cd backend && uv run python ../ops/bench_latency.py --url $${URL:-http://localhost:8080} -n $${N:-30}
