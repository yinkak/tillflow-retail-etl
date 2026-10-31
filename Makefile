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
