# DTCE AI Bot Development Makefile

.PHONY: help install install-dev test lint format clean run docker-build docker-run

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install production dependencies
	pip install -e .

install-dev: ## Install development dependencies
	pip install -e ".[dev]"
	pre-commit install

test: ## Run tests
	pytest tests/ -v

test-cov: ## Run tests with coverage
	pytest tests/ -v --cov=dtce_ai_bot --cov-report=html --cov-report=term

lint: ## Run linting
	flake8 dtce_ai_bot/ tests/
	mypy dtce_ai_bot/

format: ## Format code
	black dtce_ai_bot/ tests/
	isort dtce_ai_bot/ tests/

format-check: ## Check code formatting
	black --check dtce_ai_bot/ tests/
	isort --check-only dtce_ai_bot/ tests/

clean: ## Clean build artifacts
	rm -rf build/ dist/ *.egg-info/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

run: ## Run the application
	python app.py

run-dev: ## Run in development mode
	uvicorn dtce_ai_bot.core.app:create_app --reload --host 0.0.0.0 --port 8000

docker-build: ## Build Docker image
	docker build -t dtce-ai-bot .

docker-run: ## Run Docker container
	docker run -p 8000:8000 --env-file .env dtce-ai-bot

deploy-prep: ## Prepare for deployment
	python deployment/deploy.py
