"""Tests for rate limiting, security headers, and body size enforcement."""

from __future__ import annotations

import base64
import json
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware import BodySizeLimitMiddleware, SecurityHeadersMiddleware
from app.rate_limit import RateLimitMiddleware


# ---------------------------------------------------------------------------
# Minimal test app shared across all tests
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _noop_lifespan(app: FastAPI):
    yield


def _make_secured_app(
    reads_per_minute: int = 5,
    writes_per_minute: int = 2,
    max_body_bytes: int = 100,
) -> FastAPI:
    test_app = FastAPI(lifespan=_noop_lifespan)
    test_app.add_middleware(SecurityHeadersMiddleware)
    test_app.add_middleware(BodySizeLimitMiddleware, max_bytes=max_body_bytes)
    test_app.add_middleware(
        RateLimitMiddleware,
        reads_per_minute=reads_per_minute,
        writes_per_minute=writes_per_minute,
    )

    @test_app.get("/items")
    async def list_items():
        return []

    @test_app.post("/items")
    async def create_item(body: dict):
        return body

    @test_app.get("/health")
    async def health():
        return {"status": "healthy"}

    return test_app


@pytest.fixture
def client():
    with TestClient(_make_secured_app()) as c:
        yield c


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------


class TestSecurityHeaders:
    def test_x_content_type_options(self, client: TestClient):
        resp = client.get("/health")
        assert resp.headers.get("x-content-type-options") == "nosniff"

    def test_x_frame_options(self, client: TestClient):
        resp = client.get("/health")
        assert resp.headers.get("x-frame-options") == "DENY"

    def test_hsts(self, client: TestClient):
        resp = client.get("/health")
        hsts = resp.headers.get("strict-transport-security", "")
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts

    def test_content_security_policy(self, client: TestClient):
        resp = client.get("/health")
        csp = resp.headers.get("content-security-policy", "")
        assert "default-src 'none'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_headers_on_404(self, client: TestClient):
        resp = client.get("/does-not-exist")
        assert resp.headers.get("x-frame-options") == "DENY"


# ---------------------------------------------------------------------------
# Body size limits
# ---------------------------------------------------------------------------


class TestBodySizeLimit:
    def test_small_body_passes(self, client: TestClient):
        # max_body_bytes=100; this payload is well under that
        resp = client.post("/items", json={"x": 1}, headers={"Content-Length": "10"})
        assert resp.status_code != 413

    def test_oversized_body_returns_413(self, client: TestClient):
        resp = client.post(
            "/items",
            content=b"x" * 200,
            headers={"Content-Type": "application/json", "Content-Length": "200"},
        )
        assert resp.status_code == 413
        assert "too large" in resp.json()["detail"].lower()

    def test_invalid_content_length_returns_400(self, client: TestClient):
        resp = client.post(
            "/items",
            content=b"{}",
            headers={"Content-Type": "application/json", "Content-Length": "not-a-number"},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


def _make_jwt_header(sub: str) -> dict:
    """Build a fake Bearer token with the given sub claim (unsigned)."""
    payload = base64.urlsafe_b64encode(json.dumps({"sub": sub}).encode()).rstrip(b"=").decode()
    return {"Authorization": f"Bearer header.{payload}.sig"}


class TestRateLimiting:
    def test_read_limit_enforced(self):
        """After reads_per_minute requests, the next one returns 429."""
        app = _make_secured_app(reads_per_minute=3, writes_per_minute=10)
        with TestClient(app) as c:
            headers = _make_jwt_header("tenant-a")
            for _ in range(3):
                resp = c.get("/items", headers=headers)
                assert resp.status_code == 200
            # 4th request should be rate limited
            resp = c.get("/items", headers=headers)
            assert resp.status_code == 429
            assert resp.headers.get("retry-after") == "60"

    def test_write_limit_enforced(self):
        """After writes_per_minute requests, the next one returns 429."""
        app = _make_secured_app(reads_per_minute=10, writes_per_minute=2)
        with TestClient(app) as c:
            headers = _make_jwt_header("tenant-b")
            for _ in range(2):
                c.post("/items", json={"x": 1}, headers=headers)
            resp = c.post("/items", json={"x": 1}, headers=headers)
            assert resp.status_code == 429

    def test_per_tenant_isolation(self):
        """Rate limit buckets are isolated per tenant."""
        app = _make_secured_app(reads_per_minute=2, writes_per_minute=10)
        with TestClient(app) as c:
            # Exhaust tenant-c's quota
            for _ in range(2):
                c.get("/items", headers=_make_jwt_header("tenant-c"))
            # tenant-d is unaffected
            resp = c.get("/items", headers=_make_jwt_header("tenant-d"))
            assert resp.status_code == 200

    def test_health_endpoint_exempt_from_rate_limit(self):
        """The /health path always bypasses rate limiting."""
        app = _make_secured_app(reads_per_minute=1)
        with TestClient(app) as c:
            for _ in range(5):
                resp = c.get("/health")
                assert resp.status_code == 200
