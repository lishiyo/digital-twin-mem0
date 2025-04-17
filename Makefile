.PHONY: help setup dev test lint format clean migrate db-up db-down

help:  ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n\nTargets:\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup:  ## Install dependencies
	pip install -e ".[dev]"
	pre-commit install

dev:  ## Run development server with reload
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:  ## Run tests
	pytest

lint:  ## Run code linters
	ruff check .
	mypy .

format:  ## Format code
	ruff format .

clean:  ## Clean up build files
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name "*.pyc" -delete
	find . -type d -name .pytest_cache -exec rm -rf {} +

migrate:  ## Run database migrations
	alembic upgrade head

migrate-create:  ## Create a new database migration
	alembic revision --autogenerate -m "$(message)"

db-up:  ## Start database in development
	docker-compose up -d db

db-down:  ## Stop database in development
	docker-compose stop db

run-worker:  ## Run Celery worker
	celery -A app.worker worker --loglevel=info

run-scheduler:  ## Run DAO manager scheduler
	celery -A app.worker beat --loglevel=info
