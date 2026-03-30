.PHONY: help install test lint format run docker-build docker-run clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	uv sync --all-extras

test:  ## Run tests
	uv run pytest tests/ -v

test-unit:  ## Run unit tests only
	uv run pytest tests/unit/ -v

test-integration:  ## Run integration tests only
	uv run pytest tests/integration/ -v

lint:  ## Run linters
	uv run ruff check .
	uv run mypy src/

format:  ## Format code
	uv run ruff format .

run:  ## Run the proxy locally
	uv run python -m uvicorn flink_gateway_proxy.main:app --reload --host 0.0.0.0 --port 8080

docker-build:  ## Build Docker image
	docker build -t flink-gateway-proxy:latest .

docker-run:  ## Run Docker container
	docker run -p 8080:8080 \
		-e PROXY_FLINK_GATEWAY_URL=http://host.docker.internal:8083 \
		flink-gateway-proxy:latest

clean:  ## Clean build artifacts
	rm -rf build/ dist/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

.DEFAULT_GOAL := help
