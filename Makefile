# Developer entry points. Tools: docker compose, uv, npm (Node 24), terraform.
SHELL := /bin/bash
.DEFAULT_GOAL := help

UI_PORT ?= 3000
TEST_DATABASE_URL ?= postgresql+psycopg://taskboard:taskboard-test@127.0.0.1:55432/taskboard_test
TEST_REDIS_URL ?= redis://127.0.0.1:56379/15
export TEST_DATABASE_URL TEST_REDIS_URL

.PHONY: help up down logs admin fmt lint typecheck test test-api test-ui test-services test-services-down tf-check smoke install

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-20s %s\n", $$1, $$2}'

install: ## Install API and UI dependencies from the lockfiles
	cd api && uv sync --frozen
	cd ui && npm ci

up: ## Build and start the stack in the background (needs .env)
	docker compose up --build -d

down: ## Stop the stack
	docker compose down

logs: ## Follow the stack's logs
	docker compose logs -f

admin: ## Create or promote the first admin from ADMIN_EMAIL / ADMIN_PASSWORD in .env
	docker compose run --rm api taskboard-api create-admin

fmt: ## Format all code
	cd api && uv run ruff format src tests && uv run ruff check --fix src tests
	cd ui && npx prettier --write .
	terraform -chdir=infra fmt -recursive

lint: ## Lint and check formatting
	cd api && uv run ruff check src tests && uv run ruff format --check src tests
	cd ui && npx eslint . && npx prettier --check .

typecheck: ## mypy --strict and tsc --noEmit
	cd api && uv run mypy
	cd ui && npx tsc --noEmit

test: test-api test-ui ## Run both test suites with coverage thresholds

test-api: ## API unit and integration tests (needs TEST_DATABASE_URL / TEST_REDIS_URL, see test-services)
	cd api && uv run pytest --cov --cov-report=term-missing

test-ui: ## UI tests with coverage
	cd ui && npm test

test-services: ## Start throwaway PostgreSQL and Redis for test-api
	docker compose -f docker-compose.test.yml up -d --wait

test-services-down: ## Stop the test services
	docker compose -f docker-compose.test.yml down

tf-check: ## terraform fmt check and validate (no AWS credentials needed)
	terraform -chdir=infra fmt -check -recursive
	terraform -chdir=infra/envs/dev init -backend=false -input=false
	terraform -chdir=infra/envs/dev validate

smoke: ## End-to-end smoke test through the UI of the running stack
	SMOKE_BASE_URL=http://localhost:$(UI_PORT) scripts/smoke.sh
