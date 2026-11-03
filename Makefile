.PHONY: help up down stop ps psql test lint format

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-8s %s\n", $$1, $$2}'

up: ## Start Postgres and Azurite, wait until healthy
	docker compose up -d --wait

stop: ## Pause containers (data kept)
	docker compose stop

down: ## Remove containers (data kept in volumes)
	docker compose down

ps: ## Show running services
	docker compose ps

psql: ## Open a SQL shell in the database
	docker compose exec postgres psql -U tillflow -d retail

test: ## Run the test suite
	uv run pytest

lint: ## Check code style without changing files
	uv run ruff check .
	uv run ruff format --check .

format: ## Auto-fix code style
	uv run ruff check --fix .
	uv run ruff format .

extract: ## Extract landing files and report row counts (no loading yet)
	uv run python -m tillflow_retail_etl.extract

seed: ## Upload the 100-row sample to the local Azurite emulator
	uv run python scripts/seed_azurite.py

test-unit: ## Run fast tests that need no Docker services
	uv run pytest -m "not integration"

db: ## Create schemas and tables (safe to rerun)
	@for f in sql/ddl/*.sql; do \
		echo "Applying $$f"; \
		docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U tillflow -d retail < $$f; \
	done

etl: ## Run the pipeline: extract, validate, load into Postgres
	uv run python -m tillflow_retail_etl.pipeline
