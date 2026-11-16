# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests verifying OIDC JWT authentication on control plane API routes.

Builds a minimal FastAPI app with the same auth wiring but no database
dependency so tests run offline without a PostgreSQL instance.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import List

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.models import Tenant


TENANT_ROUTES = [
    ("GET", "/tenants"),
    ("GET", "/tenants/t1"),
    ("POST", "/tenants"),
    ("PATCH", "/tenants/t1"),
    ("DELETE", "/tenants/t1"),
]


@asynccontextmanager
async def _noop_lifespan(app: FastAPI):
    yield


def _make_test_app() -> FastAPI:
    """Minimal app that mirrors the auth wiring without a real database."""
    test_app = FastAPI(lifespan=_noop_lifespan)

    @test_app.get("/tenants", response_model=List[Tenant])
    async def list_tenants(_user: dict = Depends(get_current_user)):
        return []

    @test_app.get("/tenants/{tenant_id}", response_model=Tenant)
    async def get_tenant(tenant_id: str, _user: dict = Depends(get_current_user)):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="not found")

    @test_app.post("/tenants", response_model=Tenant)
    async def create_tenant(tenant: Tenant, _user: dict = Depends(get_current_user)):
        return tenant

    @test_app.patch("/tenants/{tenant_id}", response_model=Tenant)
    async def update_tenant(tenant_id: str, _user: dict = Depends(get_current_user)):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="not found")

    @test_app.delete("/tenants/{tenant_id}")
    async def delete_tenant(tenant_id: str, _user: dict = Depends(get_current_user)):
        return {"status": "ok"}

    @test_app.get("/health")
    async def health():
        return {"status": "healthy"}

    return test_app


@pytest.fixture
def client():
    with TestClient(_make_test_app(), raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# Unauthenticated access to tenant routes must return 401
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method,path", TENANT_ROUTES)
def test_unauthenticated_returns_401(client, method, path):
    import app.auth as auth_module
    auth_module.settings.auth_disabled = False
    auth_module.settings.oidc_issuer_url = "https://issuer.example.com"
    # Clear JWKS cache so OIDC check is reached
    auth_module._jwks_cache.clear()

    kwargs = {}
    if method in ("POST", "PATCH"):
        kwargs["json"] = {}

    response = getattr(client, method.lower())(path, **kwargs)
    assert response.status_code == 401, f"{method} {path} should require auth"
    assert "token" in response.text.lower() or "bearer" in response.text.lower()


# ---------------------------------------------------------------------------
# Health endpoint must remain open (no auth required)
# ---------------------------------------------------------------------------

def test_health_endpoint_open(client):
    import app.auth as auth_module
    auth_module.settings.oidc_issuer_url = "https://issuer.example.com"
    auth_module.settings.auth_disabled = False
    response = client.get("/health")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# CONTROL_PLANE_AUTH_DISABLED=true bypasses auth (for local dev)
# ---------------------------------------------------------------------------

def test_auth_disabled_bypasses_check(client):
    import app.auth as auth_module
    auth_module.settings.auth_disabled = True
    auth_module.settings.oidc_issuer_url = ""

    response = client.get("/tenants")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# When OIDC issuer is not configured and bearer token is provided, return 401
# ---------------------------------------------------------------------------

def test_no_issuer_with_token_returns_401(client):
    import app.auth as auth_module
    auth_module.settings.oidc_issuer_url = ""
    auth_module.settings.auth_disabled = False

    response = client.get("/tenants", headers={"Authorization": "Bearer fake.token.here"})
    assert response.status_code == 401
