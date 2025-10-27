.PHONY: help install install-dev venv build shell test test-container docker-smoke docker-test docker-down lint format clean

help:
	@echo ""
	@echo "Available targets:"
	@echo "  make install         Install prod dependencies"
	@echo "  make install-dev     Install dev + prod dependencies + pre-commit hooks"
	@echo "  make venv            Create and initialize a clean virtualenv"
	@echo "  make build           Build Docker image"
	@echo "  make shell           Run interactive container with mounted code"
	@echo "  make test            Run all tests with pytest"
	@echo "  make test-container  Run tests inside Docker container"
	@echo "  make docker-smoke    Quick smoke test - verify container starts and responds"
	@echo "  make docker-test     Full container test - build, run, health checks, log validation"
	@echo "  make docker-down     Stop and remove Docker containers"
	@echo "  make lint            Run linter (ruff)"
	@echo "  make format          Format code (black + ruff)"
	@echo "  make clean           Remove __pycache__ and .pyc files"
	@echo "  make run-api         Start FastAPI server on port 8000 (dev mode)"
	@echo ""

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt -r dev-requirements.txt
	pre-commit install
	@echo ""
	@echo "✅ Pre-commit hooks installed successfully!"
	@echo "   Hooks will now run automatically on git commit"
	@echo ""

venv:
	python3 -m venv venv && source venv/bin/activate && make install-dev

build:
	docker build -t sync-hostaway .

shell:
	docker run -it --rm \
		--env-file=.env \
		-v $(PWD):/app \
		-w /app \
		sync-hostaway \
		/bin/bash

test-container:
	docker run --rm \
		--env-file=.env \
		-v $(PWD):/app \
		-w /app \
		sync-hostaway \
		make test

test:
	PYTHONPATH=. pytest -v --tb=short --cov=sync_hostaway --cov-report=html --cov-report=term

lint:
	pre-commit run --all-files

format:
	ruff check . --fix
	black .

clean:
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -exec rm -r {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache venv

run-api:
	uvicorn sync_hostaway.main:app --host 0.0.0.0 --port 8000 --reload

docker-smoke:
	@echo "🔨 Building Docker image..."
	docker compose build
	@echo "🚀 Starting container..."
	docker compose up -d
	@echo "⏳ Waiting for container to be healthy (60s timeout)..."
	@timeout=60; \
	while [ $$timeout -gt 0 ]; do \
		if curl -sf http://localhost:8000/health > /dev/null 2>&1; then \
			echo "✅ Container is healthy!"; \
			docker compose down -v; \
			exit 0; \
		fi; \
		sleep 2; \
		timeout=$$((timeout - 2)); \
	done; \
	echo "❌ Container failed to become healthy"; \
	docker compose logs app; \
	docker compose down -v; \
	exit 1

docker-test:
	@echo "🔨 Building Docker image..."
	docker compose build
	@echo "🚀 Starting containers..."
	docker compose up -d
	@echo "⏳ Waiting for application to be ready..."
	@timeout=60; \
	while [ $$timeout -gt 0 ]; do \
		if curl -sf http://localhost:8000/health > /dev/null 2>&1; then \
			echo "✅ Health check passed"; \
			break; \
		fi; \
		sleep 2; \
		timeout=$$((timeout - 2)); \
		if [ $$timeout -le 0 ]; then \
			echo "❌ Health check failed - timeout"; \
			docker compose logs app; \
			docker compose down -v; \
			exit 1; \
		fi; \
	done
	@echo "🔍 Checking readiness endpoint..."
	@if curl -sf http://localhost:8000/ready | grep -q '"status":"ready"'; then \
		echo "✅ Readiness check passed"; \
	else \
		echo "❌ Readiness check failed"; \
		docker compose logs app; \
		docker compose down -v; \
		exit 1; \
	fi
	@echo "🔍 Scanning logs for errors..."
	@if docker compose logs app | grep -iE "(error|exception|traceback)" | grep -v "uvicorn.error"; then \
		echo "❌ Found errors in logs"; \
		docker compose down -v; \
		exit 1; \
	else \
		echo "✅ No errors found in logs"; \
	fi
	@echo "🎉 All container tests passed!"
	@docker compose down -v

docker-down:
	docker compose down -v
