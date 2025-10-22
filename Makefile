.PHONY: help install install-dev venv build shell test test-container lint format clean

help:
	@echo ""
	@echo "Available targets:"
	@echo "  make install         Install prod dependencies"
	@echo "  make install-dev     Install dev + prod dependencies"
	@echo "  make venv            Create and initialize a clean virtualenv"
	@echo "  make build           Build Docker image"
	@echo "  make shell           Run interactive container with mounted code"
	@echo "  make test            Run all tests with pytest"
	@echo "  make test-container  Run tests inside Docker container"
	@echo "  make lint            Run linter (ruff)"
	@echo "  make format          Format code (black + ruff)"
	@echo "  make clean           Remove __pycache__ and .pyc files"
	@echo "  make run-api         Start FastAPI server on port 8000 (dev mode)"
	@echo ""

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt -r dev-requirements.txt

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
