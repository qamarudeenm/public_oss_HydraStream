"""Unit tests for dbt runtime callback endpoints."""

import hashlib
import hmac
import json

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from flink_gateway_proxy.routes import dbt_runtime


class FakeFlinkGatewayClient:
    """Stub Flink client for runtime callback tests."""

    def __init__(self, base_url: str):
        self.base_url = base_url

    async def open_session(self, session_name=None, properties=None):
        return "session-123"

    async def execute_statement(self, session_handle, sql, execution_config=None):
        return f"op-{abs(hash(sql)) % 10000}"

    async def close_session(self, session_handle):
        return None

    async def close(self):
        return None


class FlakyFlinkGatewayClient(FakeFlinkGatewayClient):
    """Fails once with transient error, then succeeds."""

    def __init__(self, base_url: str):
        super().__init__(base_url)
        self.calls = 0

    async def execute_statement(self, session_handle, sql, execution_config=None):
        self.calls += 1
        if self.calls == 1:
            raise httpx.ConnectError("connection reset", request=httpx.Request("POST", "http://x"))
        return await super().execute_statement(session_handle, sql, execution_config)


class TerminalFlinkGatewayClient(FakeFlinkGatewayClient):
    """Always fails with non-retryable HTTP status."""

    async def execute_statement(self, session_handle, sql, execution_config=None):
        request = httpx.Request("POST", "http://x")
        response = httpx.Response(400, request=request)
        raise httpx.HTTPStatusError("bad request", request=request, response=response)


def _sign(secret: str, raw: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(dbt_runtime.router)
    return app


def _valid_payload() -> dict:
    return {
        "event_id": "evt-1",
        "tenant_id": "tenant-a",
        "job": {
            "id": 10,
            "run_id": 101,
            "account_id": 22,
            "environment_id": 33,
            "name": "daily-run",
        },
        "execution": {
            "catalog": "default_catalog",
            "database": "default_database",
            "properties": {"pipeline.mode": "streaming"},
        },
        "statements": [
            {"name": "create_source", "sql": "CREATE TABLE src (id STRING)"},
            {"name": "create_sink", "sql": "CREATE TABLE sink (id STRING)"},
        ],
    }


def test_callback_requires_signature(monkeypatch):
    """Callback should reject missing signature header."""
    monkeypatch.setattr(dbt_runtime, "FlinkGatewayClient", FakeFlinkGatewayClient)
    dbt_runtime.set_runtime_config(
        shared_secret="test-secret",
        tenant_gateway_map={"tenant-a": "http://tenant-a-gateway:8083"},
    )

    client = TestClient(_build_app())
    response = client.post("/runtime/v1/dbt/run-callback", json=_valid_payload())

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing X-Dbt-Signature header"


def test_callback_rejects_unknown_tenant(monkeypatch):
    """Callback should reject tenant IDs without runtime mapping."""
    monkeypatch.setattr(dbt_runtime, "FlinkGatewayClient", FakeFlinkGatewayClient)
    dbt_runtime.set_runtime_config(shared_secret="test-secret", tenant_gateway_map={})

    raw = json.dumps(_valid_payload(), separators=(",", ":")).encode("utf-8")
    signature = _sign("test-secret", raw)

    client = TestClient(_build_app())
    response = client.post(
        "/runtime/v1/dbt/run-callback",
        content=raw,
        headers={"Content-Type": "application/json", "X-Dbt-Signature": signature},
    )

    assert response.status_code == 404
    assert "No Flink gateway mapping configured" in response.json()["detail"]


def test_callback_dispatches_statements(monkeypatch):
    """Callback should dispatch all statements to mapped tenant gateway."""
    monkeypatch.setattr(dbt_runtime, "FlinkGatewayClient", FakeFlinkGatewayClient)
    dbt_runtime.set_runtime_config(
        shared_secret="test-secret",
        tenant_gateway_map={"tenant-a": "http://tenant-a-gateway:8083"},
    )

    raw = json.dumps(_valid_payload(), separators=(",", ":")).encode("utf-8")
    signature = _sign("test-secret", raw)

    client = TestClient(_build_app())
    response = client.post(
        "/runtime/v1/dbt/run-callback",
        content=raw,
        headers={"Content-Type": "application/json", "X-Dbt-Signature": signature},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "accepted"
    assert body["tenant_id"] == "tenant-a"
    assert body["flink_gateway_url"] == "http://tenant-a-gateway:8083"
    assert body["dispatched_count"] == 2
    assert len(body["statements"]) == 2


def test_callback_retries_transient_statement_failure(monkeypatch):
    """Callback should retry transient dispatch errors."""
    monkeypatch.setattr(dbt_runtime, "FlinkGatewayClient", FlakyFlinkGatewayClient)
    dbt_runtime.set_runtime_config(
        shared_secret="test-secret",
        tenant_gateway_map={"tenant-a": "http://tenant-a-gateway:8083"},
        max_dispatch_attempts=2,
    )

    raw = json.dumps(_valid_payload(), separators=(",", ":")).encode("utf-8")
    signature = _sign("test-secret", raw)
    client = TestClient(_build_app())
    response = client.post(
        "/runtime/v1/dbt/run-callback",
        content=raw,
        headers={"Content-Type": "application/json", "X-Dbt-Signature": signature},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"


def test_callback_returns_actionable_terminal_error(monkeypatch):
    """Callback should surface terminal errors with action metadata."""
    monkeypatch.setattr(dbt_runtime, "FlinkGatewayClient", TerminalFlinkGatewayClient)
    dbt_runtime.set_runtime_config(
        shared_secret="test-secret",
        tenant_gateway_map={"tenant-a": "http://tenant-a-gateway:8083"},
        max_dispatch_attempts=2,
    )

    raw = json.dumps(_valid_payload(), separators=(",", ":")).encode("utf-8")
    signature = _sign("test-secret", raw)
    client = TestClient(_build_app())
    response = client.post(
        "/runtime/v1/dbt/run-callback",
        content=raw,
        headers={"Content-Type": "application/json", "X-Dbt-Signature": signature},
    )

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["error_code"] == "gateway_http_terminal"
    assert detail["retryable"] is False
    assert detail["retries_attempted"] == 0
