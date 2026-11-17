"""Tests for tenant CRUD endpoints — authenticated and unauthenticated paths."""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Unauthenticated access — all tenant routes must return 401
# ---------------------------------------------------------------------------

class TestUnauthenticated:
    def test_list_tenants_requires_auth(self, unauth_client: TestClient):
        resp = unauth_client.get("/tenants/")
        assert resp.status_code == 401

    def test_create_tenant_requires_auth(self, unauth_client: TestClient):
        resp = unauth_client.post("/tenants/", json={"name": "ACME"})
        assert resp.status_code == 401

    def test_get_tenant_requires_auth(self, unauth_client: TestClient):
        resp = unauth_client.get("/tenants/00000000-0000-0000-0000-000000000001")
        assert resp.status_code == 401

    def test_update_tenant_requires_auth(self, unauth_client: TestClient):
        resp = unauth_client.patch(
            "/tenants/00000000-0000-0000-0000-000000000001", json={"name": "New"}
        )
        assert resp.status_code == 401

    def test_delete_tenant_requires_auth(self, unauth_client: TestClient):
        resp = unauth_client.delete("/tenants/00000000-0000-0000-0000-000000000001")
        assert resp.status_code == 401

    def test_invalid_bearer_token_returns_401(self, unauth_client: TestClient):
        """Malformed JWT triggers jose.JWTError → 401, not 500."""
        import app.auth as auth_mod

        # Inject a fake JWKS so the OIDC discovery fetch is skipped
        auth_mod._jwks_cache = {"keys": []}

        resp = unauth_client.get(
            "/tenants/", headers={"Authorization": "Bearer not.a.valid.jwt"}
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Authenticated CRUD
# ---------------------------------------------------------------------------

class TestTenantCRUD:
    def test_list_tenants_empty(self, client: TestClient):
        resp = client.get("/tenants/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_tenant(self, client: TestClient):
        resp = client.post("/tenants/", json={"name": "ACME Corp"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "ACME Corp"
        assert data["description"] == ""
        assert "id" in data

    def test_create_tenant_with_description(self, client: TestClient):
        resp = client.post(
            "/tenants/", json={"name": "Beta Inc", "description": "Beta tenant"}
        )
        assert resp.status_code == 201
        assert resp.json()["description"] == "Beta tenant"

    def test_list_tenants_after_create(self, client: TestClient):
        client.post("/tenants/", json={"name": "Alpha"})
        client.post("/tenants/", json={"name": "Beta"})
        resp = client.get("/tenants/")
        assert resp.status_code == 200
        names = {t["name"] for t in resp.json()}
        assert names == {"Alpha", "Beta"}

    def test_get_tenant(self, client: TestClient):
        created = client.post("/tenants/", json={"name": "Gamma LLC"}).json()
        resp = client.get(f"/tenants/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Gamma LLC"

    def test_get_tenant_not_found(self, client: TestClient):
        resp = client.get("/tenants/00000000-0000-0000-0000-000000000099")
        assert resp.status_code == 404

    def test_update_tenant_name(self, client: TestClient):
        created = client.post("/tenants/", json={"name": "OldName"}).json()
        resp = client.patch(f"/tenants/{created['id']}", json={"name": "NewName"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "NewName"
        assert resp.json()["description"] == ""  # unchanged

    def test_update_tenant_not_found(self, client: TestClient):
        resp = client.patch(
            "/tenants/00000000-0000-0000-0000-000000000099", json={"name": "X"}
        )
        assert resp.status_code == 404

    def test_delete_tenant(self, client: TestClient):
        created = client.post("/tenants/", json={"name": "ToDelete"}).json()
        resp = client.delete(f"/tenants/{created['id']}")
        assert resp.status_code == 204
        # Verify it's gone
        assert client.get(f"/tenants/{created['id']}").status_code == 404

    def test_delete_tenant_not_found(self, client: TestClient):
        resp = client.delete("/tenants/00000000-0000-0000-0000-000000000099")
        assert resp.status_code == 404

    def test_health_endpoint_no_auth(self, unauth_client: TestClient):
        resp = unauth_client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy"}
