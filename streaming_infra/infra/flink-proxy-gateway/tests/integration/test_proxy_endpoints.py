"""Integration tests for proxy endpoints."""

import os
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from flink_gateway_proxy.routes import statements


@pytest.fixture
def mock_gateway_client():
    """Mock Flink Gateway client."""
    client = AsyncMock()
    client.open_session = AsyncMock(return_value="session-123")
    client.execute_statement = AsyncMock(return_value="op-456")
    client.get_operation_status = AsyncMock(
        return_value=MagicMock(status="RUNNING")
    )
    client.fetch_results = AsyncMock(
        return_value=MagicMock(
            results=MagicMock(
                data=[],
                result_type="EOS",
                is_query_result=True,
            ),
            next_result_uri=None,
        )
    )
    client.close = AsyncMock()
    return client


@pytest.fixture
def test_app():
    """Create test FastAPI app with minimal lifespan."""

    @asynccontextmanager
    async def test_lifespan(app: FastAPI):
        # Minimal startup/shutdown for testing
        yield

    app = FastAPI(lifespan=test_lifespan)
    app.include_router(statements.router)

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/ready")
    async def ready():
        return {"status": "ready"}

    return app


@pytest.fixture
def test_client(test_app):
    """Create test client."""
    with TestClient(test_app) as client:
        yield client


def test_health_endpoint(test_client):
    """Test health endpoint."""
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_ready_endpoint(test_client):
    """Test readiness endpoint."""
    response = test_client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
