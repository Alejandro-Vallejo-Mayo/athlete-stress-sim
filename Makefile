# =============================================================================
# Athlete Stress Sim — single entry point for development commands.
# Usage: `make help` to list every target.
# =============================================================================

UV ?= uv
COMPOSE ?= docker compose -f docker/docker-compose.yml

.DEFAULT_GOAL := help

.PHONY: help install lint format typecheck test test-cov run-backend run-frontend docker-up docker-logs docker-down clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Create the environment, install dependencies and activate git hooks
	$(UV) sync --all-groups
	$(UV) run pre-commit install

lint: ## Run ruff (linter) and check formatting
	$(UV) run ruff check .
	$(UV) run ruff format --check .

format: ## Auto-fix and format the code with ruff
	$(UV) run ruff check --fix .
	$(UV) run ruff format .

typecheck: ## Check static types with mypy
	$(UV) run mypy

test: ## Run the test suite
	$(UV) run pytest

test-cov: ## Run tests with coverage (80% threshold on core)
	$(UV) run pytest --cov

run-backend: ## Start the FastAPI backend in development mode
	$(UV) run athlete-stress-sim

run-frontend: ## Start the Dash dashboard in development mode
	$(UV) run python -m athlete_stress_sim.frontend.app

docker-up: ## Build and start all services (background)
	@printf "\n\033[1mBuilding and starting services in the background...\033[0m\n"
	@printf "(the first build can take ~1 minute; the progress bar may look frozen)\n\n"
	$(COMPOSE) up --build -d
	@printf "\n\033[1mServices available at:\033[0m\n"
	@printf "  Frontend (Dash) : \033[36mhttp://localhost:8050\033[0m\n"
	@printf "  Backend  (API)  : \033[36mhttp://localhost:8000\033[0m\n"
	@printf "  API docs (docs) : \033[36mhttp://localhost:8000/docs\033[0m\n"
	@printf "\nFollow logs with 'make docker-logs' and stop with 'make docker-down'.\n"

docker-logs: ## Follow the logs of all Docker Compose services
	$(COMPOSE) logs -f

docker-down: ## Stop and remove the Docker Compose services
	$(COMPOSE) down

clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov dist build
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
