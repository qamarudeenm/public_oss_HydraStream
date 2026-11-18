"""Test fixtures for the control plane API."""

from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.auth as auth_mod
from app.auth import get_current_user
from app.routes.tenants import router, _reset_store

TEST_USER = {"sub": "test-user-123", "email": "user@example.com", "scope": "admin"}

_OIDC_ISSUER = "https://oidc.example.com"
_OIDC_AUDIENCE = "control-plane-api"


@asynccontextmanager
async def _noop_lifespan(app: FastAPI):
    yield


def _make_app() -> FastAPI:
    """Standalone test app using only the tenants router — no database needed."""
    test_app = FastAPI(lifespan=_noop_lifespan)
    test_app.include_router(router)

    @test_app.get("/health")
    async def health():
        return {"status": "healthy"}

    return test_app


app = _make_app()


@pytest.fixture(autouse=True)
def reset_store():
    _reset_store()
    yield
    _reset_store()


@pytest.fixture(autouse=True)
def reset_jwks_cache():
    auth_mod._jwks_cache = {}
    yield
    auth_mod._jwks_cache = {}


@pytest.fixture
def client(monkeypatch):
    """Authenticated test client — bypasses actual JWT validation."""
    monkeypatch.setenv("CONTROL_PLANE_OIDC_ISSUER_URL", _OIDC_ISSUER)
    monkeypatch.setenv("CONTROL_PLANE_OIDC_AUDIENCE", _OIDC_AUDIENCE)
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def unauth_client(monkeypatch):
    """Unauthenticated test client — real auth dependency enforced."""
    monkeypatch.setenv("CONTROL_PLANE_OIDC_ISSUER_URL", _OIDC_ISSUER)
    monkeypatch.setenv("CONTROL_PLANE_OIDC_AUDIENCE", _OIDC_AUDIENCE)
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        yield c
