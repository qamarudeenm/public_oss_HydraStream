"""Test fixtures for the control plane API."""

import pytest
from fastapi.testclient import TestClient

import app.auth as auth_mod
from app.auth import get_current_user
from app.main import app
from app.routes.tenants import _reset_store

TEST_USER = {"sub": "test-user-123", "email": "user@example.com", "scope": "admin"}

_OIDC_ISSUER = "https://oidc.example.com"
_OIDC_AUDIENCE = "control-plane-api"


@pytest.fixture(autouse=True)
def reset_store():
    _reset_store()
    yield
    _reset_store()


@pytest.fixture(autouse=True)
def reset_jwks_cache():
    auth_mod._jwks_cache = None
    yield
    auth_mod._jwks_cache = None


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
