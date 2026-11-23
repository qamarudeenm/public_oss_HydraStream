"""Tests for webhook registration, delivery engine, and management endpoints."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.auth as auth_mod
from app.auth import get_current_user
from app.models import WebhookDeliveryStatus, WebhookEventType
from app.notification_manager import RateLimiter, WebhookDeliveryEngine, sign_payload
from app.routes.webhooks import _reset_store, router
from app.notification_manager import get_engine


ADMIN_TOKEN = {
    "sub": "admin-user",
    "email": "admin@example.com",
    "hydra_role": "platform_admin",
}
TENANT_ID = "tenant-abc"
TENANT_ADMIN_TOKEN = {
    "sub": "tenant-user",
    "email": "tenant@example.com",
    "hydra_role": "tenant_admin",
    "hydra_tenant_id": TENANT_ID,
}
VIEWER_TOKEN = {
    "sub": "viewer-user",
    "email": "viewer@example.com",
    "hydra_role": "tenant_viewer",
    "hydra_tenant_id": TENANT_ID,
}


class SuccessTransport(httpx.AsyncBaseTransport):
    def __init__(self, status_code: int = 200):
        self.status_code = status_code
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status_code)


@asynccontextmanager
async def _noop_lifespan(app: FastAPI):
    yield


def _make_test_app(engine: WebhookDeliveryEngine) -> FastAPI:
    test_app = FastAPI(lifespan=_noop_lifespan)
    test_app.include_router(router)
    test_app.dependency_overrides[get_engine] = lambda: engine
    return test_app


@pytest.fixture(autouse=True)
def reset_webhook_store():
    _reset_store()
    yield
    _reset_store()


@pytest.fixture(autouse=True)
def reset_jwks():
    auth_mod._jwks_cache = {}
    yield
    auth_mod._jwks_cache = {}


@pytest.fixture
def transport():
    return SuccessTransport(200)


@pytest.fixture
def engine(transport):
    return WebhookDeliveryEngine(transport=transport, base_delay=0.0)


@pytest.fixture
def admin_client(engine):
    app = _make_test_app(engine)
    app.dependency_overrides[get_current_user] = lambda: ADMIN_TOKEN
    with TestClient(app) as c:
        yield c


@pytest.fixture
def tenant_client(engine):
    app = _make_test_app(engine)
    app.dependency_overrides[get_current_user] = lambda: TENANT_ADMIN_TOKEN
    with TestClient(app) as c:
        yield c


@pytest.fixture
def viewer_client(engine):
    app = _make_test_app(engine)
    app.dependency_overrides[get_current_user] = lambda: VIEWER_TOKEN
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Payload signing
# ---------------------------------------------------------------------------

class TestSignPayload:
    def test_deterministic(self):
        sig1 = sign_payload("secret", b"body")
        sig2 = sign_payload("secret", b"body")
        assert sig1 == sig2

    def test_different_secrets(self):
        assert sign_payload("s1", b"body") != sign_payload("s2", b"body")

    def test_different_bodies(self):
        assert sign_payload("s", b"body1") != sign_payload("s", b"body2")

    def test_hex_string(self):
        sig = sign_payload("secret", b"payload")
        assert len(sig) == 64
        assert all(c in "0123456789abcdef" for c in sig)


# ---------------------------------------------------------------------------
# CRUD — register, list, get, update, delete
# ---------------------------------------------------------------------------

class TestWebhookCRUD:
    def test_register_webhook(self, admin_client):
        resp = admin_client.post(
            f"/tenants/{TENANT_ID}/webhooks",
            json={"url": "https://example.com/hook", "event_types": ["pipeline_error"]},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["url"] == "https://example.com/hook"
        assert data["event_types"] == ["pipeline_error"]
        assert data["enabled"] is True
        assert len(data["signing_secret"]) == 64
        assert data["tenant_id"] == TENANT_ID

    def test_register_multiple_event_types(self, admin_client):
        resp = admin_client.post(
            f"/tenants/{TENANT_ID}/webhooks",
            json={
                "url": "https://example.com/hook",
                "event_types": ["pipeline_error", "billing_event"],
            },
        )
        assert resp.status_code == 201
        assert set(resp.json()["event_types"]) == {"pipeline_error", "billing_event"}

    def test_list_webhooks_empty(self, admin_client):
        resp = admin_client.get(f"/tenants/{TENANT_ID}/webhooks")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_webhooks_after_register(self, admin_client):
        admin_client.post(
            f"/tenants/{TENANT_ID}/webhooks",
            json={"url": "https://a.com/h", "event_types": ["billing_event"]},
        )
        admin_client.post(
            f"/tenants/{TENANT_ID}/webhooks",
            json={"url": "https://b.com/h", "event_types": ["pipeline_error"]},
        )
        resp = admin_client.get(f"/tenants/{TENANT_ID}/webhooks")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_webhook(self, admin_client):
        created = admin_client.post(
            f"/tenants/{TENANT_ID}/webhooks",
            json={"url": "https://example.com/hook", "event_types": ["pipeline_error"]},
        ).json()
        resp = admin_client.get(f"/tenants/{TENANT_ID}/webhooks/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_get_webhook_not_found(self, admin_client):
        resp = admin_client.get(f"/tenants/{TENANT_ID}/webhooks/nonexistent")
        assert resp.status_code == 404

    def test_update_webhook_url(self, admin_client):
        created = admin_client.post(
            f"/tenants/{TENANT_ID}/webhooks",
            json={"url": "https://old.com/hook", "event_types": ["pipeline_error"]},
        ).json()
        resp = admin_client.patch(
            f"/tenants/{TENANT_ID}/webhooks/{created['id']}",
            json={"url": "https://new.com/hook"},
        )
        assert resp.status_code == 200
        assert resp.json()["url"] == "https://new.com/hook"
        assert resp.json()["event_types"] == ["pipeline_error"]  # unchanged

    def test_update_webhook_disable(self, admin_client):
        created = admin_client.post(
            f"/tenants/{TENANT_ID}/webhooks",
            json={"url": "https://example.com/hook", "event_types": ["pipeline_error"]},
        ).json()
        resp = admin_client.patch(
            f"/tenants/{TENANT_ID}/webhooks/{created['id']}",
            json={"enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_update_webhook_not_found(self, admin_client):
        resp = admin_client.patch(
            f"/tenants/{TENANT_ID}/webhooks/nonexistent",
            json={"url": "https://new.com/hook"},
        )
        assert resp.status_code == 404

    def test_delete_webhook(self, admin_client):
        created = admin_client.post(
            f"/tenants/{TENANT_ID}/webhooks",
            json={"url": "https://example.com/hook", "event_types": ["pipeline_error"]},
        ).json()
        resp = admin_client.delete(f"/tenants/{TENANT_ID}/webhooks/{created['id']}")
        assert resp.status_code == 204
        assert admin_client.get(f"/tenants/{TENANT_ID}/webhooks/{created['id']}").status_code == 404

    def test_delete_webhook_not_found(self, admin_client):
        resp = admin_client.delete(f"/tenants/{TENANT_ID}/webhooks/nonexistent")
        assert resp.status_code == 404

    def test_viewer_cannot_register(self, viewer_client):
        resp = viewer_client.post(
            f"/tenants/{TENANT_ID}/webhooks",
            json={"url": "https://example.com/hook", "event_types": ["pipeline_error"]},
        )
        assert resp.status_code == 403

    def test_tenant_admin_can_register_own_tenant(self, tenant_client):
        resp = tenant_client.post(
            f"/tenants/{TENANT_ID}/webhooks",
            json={"url": "https://example.com/hook", "event_types": ["pipeline_error"]},
        )
        assert resp.status_code == 201

    def test_tenant_admin_cannot_access_other_tenant(self, tenant_client):
        resp = tenant_client.get("/tenants/other-tenant/webhooks")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Delivery engine unit tests
# ---------------------------------------------------------------------------

class TestDeliveryEngine:
    @pytest.mark.asyncio
    async def test_successful_delivery(self):
        transport = SuccessTransport(200)
        engine = WebhookDeliveryEngine(transport=transport, base_delay=0.0)
        from app.models import WebhookEndpoint, WebhookEventType
        from datetime import datetime, timezone
        webhook = WebhookEndpoint(
            id="wh-1",
            tenant_id="t1",
            url="https://example.com/hook",
            event_types=[WebhookEventType.pipeline_error],
            signing_secret="secret",
            enabled=True,
            created_at=datetime.now(timezone.utc),
        )
        log = await engine.deliver(webhook, WebhookEventType.pipeline_error, {"key": "val"})
        assert log.status == WebhookDeliveryStatus.success
        assert log.attempt == 1
        assert log.response_code == 200
        assert len(transport.requests) == 1

    @pytest.mark.asyncio
    async def test_signature_header_sent(self):
        transport = SuccessTransport(200)
        engine = WebhookDeliveryEngine(transport=transport, base_delay=0.0)
        from app.models import WebhookEndpoint, WebhookEventType
        from datetime import datetime, timezone
        webhook = WebhookEndpoint(
            id="wh-1",
            tenant_id="t1",
            url="https://example.com/hook",
            event_types=[WebhookEventType.pipeline_error],
            signing_secret="mysecret",
            enabled=True,
            created_at=datetime.now(timezone.utc),
        )
        await engine.deliver(webhook, WebhookEventType.pipeline_error, {"x": 1})
        req = transport.requests[0]
        assert "X-Hydra-Signature" in req.headers
        assert req.headers["X-Hydra-Signature"].startswith("sha256=")
        assert req.headers["X-Hydra-Event"] == "pipeline_error"

    @pytest.mark.asyncio
    async def test_retry_on_failure_and_dead_letter(self):
        transport = SuccessTransport(500)
        engine = WebhookDeliveryEngine(transport=transport, base_delay=0.0)
        from app.models import WebhookEndpoint, WebhookEventType
        from datetime import datetime, timezone
        webhook = WebhookEndpoint(
            id="wh-1",
            tenant_id="t1",
            url="https://example.com/hook",
            event_types=[WebhookEventType.pipeline_error],
            signing_secret="secret",
            enabled=True,
            created_at=datetime.now(timezone.utc),
        )
        log = await engine.deliver(webhook, WebhookEventType.pipeline_error, {})
        assert log.status == WebhookDeliveryStatus.failed
        assert log.attempt == WebhookDeliveryEngine.MAX_ATTEMPTS
        assert len(transport.requests) == WebhookDeliveryEngine.MAX_ATTEMPTS

        dlq = engine.get_dead_letter("wh-1")
        assert len(dlq) == 1
        assert dlq[0].attempts == WebhookDeliveryEngine.MAX_ATTEMPTS

    @pytest.mark.asyncio
    async def test_delivery_logs_recorded(self):
        transport = SuccessTransport(200)
        engine = WebhookDeliveryEngine(transport=transport, base_delay=0.0)
        from app.models import WebhookEndpoint, WebhookEventType
        from datetime import datetime, timezone
        webhook = WebhookEndpoint(
            id="wh-1",
            tenant_id="t1",
            url="https://example.com/hook",
            event_types=[WebhookEventType.pipeline_error],
            signing_secret="secret",
            enabled=True,
            created_at=datetime.now(timezone.utc),
        )
        await engine.deliver(webhook, WebhookEventType.pipeline_error, {})
        logs = engine.get_delivery_logs("wh-1")
        assert len(logs) == 1
        assert logs[0].webhook_id == "wh-1"

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_delivery(self):
        limiter = RateLimiter(max_per_minute=0)
        engine = WebhookDeliveryEngine(rate_limiter=limiter, base_delay=0.0)
        from app.models import WebhookEndpoint, WebhookEventType
        from datetime import datetime, timezone
        webhook = WebhookEndpoint(
            id="wh-1",
            tenant_id="t1",
            url="https://example.com/hook",
            event_types=[WebhookEventType.pipeline_error],
            signing_secret="secret",
            enabled=True,
            created_at=datetime.now(timezone.utc),
        )
        log = await engine.deliver(webhook, WebhookEventType.pipeline_error, {})
        assert log.status == WebhookDeliveryStatus.failed
        assert log.error == "Rate limit exceeded"

    @pytest.mark.asyncio
    async def test_retry_dead_letter_success(self):
        transport = SuccessTransport(200)
        engine = WebhookDeliveryEngine(transport=SuccessTransport(500), base_delay=0.0)
        from app.models import WebhookEndpoint, WebhookEventType
        from datetime import datetime, timezone
        webhook = WebhookEndpoint(
            id="wh-1",
            tenant_id="t1",
            url="https://example.com/hook",
            event_types=[WebhookEventType.pipeline_error],
            signing_secret="secret",
            enabled=True,
            created_at=datetime.now(timezone.utc),
        )
        await engine.deliver(webhook, WebhookEventType.pipeline_error, {"retry": True})
        dlq = engine.get_dead_letter("wh-1")
        assert len(dlq) == 1
        dlq_id = dlq[0].id

        # Swap transport to success for retry
        engine._transport = transport
        result = await engine.retry_dead_letter(dlq_id, {"wh-1": webhook})
        assert result is not None
        assert result.status == WebhookDeliveryStatus.success
        assert engine.get_dead_letter("wh-1") == []


# ---------------------------------------------------------------------------
# Delivery endpoints (via HTTP routes)
# ---------------------------------------------------------------------------

class TestDeliveryRoutes:
    def test_list_deliveries(self, admin_client, engine, transport):
        created = admin_client.post(
            f"/tenants/{TENANT_ID}/webhooks",
            json={"url": "https://example.com/hook", "event_types": ["pipeline_error"]},
        ).json()
        # trigger test delivery
        admin_client.post(f"/tenants/{TENANT_ID}/webhooks/{created['id']}/test")
        resp = admin_client.get(f"/tenants/{TENANT_ID}/webhooks/{created['id']}/deliveries")
        assert resp.status_code == 200
        logs = resp.json()
        assert len(logs) >= 1
        assert logs[0]["webhook_id"] == created["id"]

    def test_test_webhook_delivers(self, admin_client, engine, transport):
        created = admin_client.post(
            f"/tenants/{TENANT_ID}/webhooks",
            json={"url": "https://example.com/hook", "event_types": ["pipeline_error"]},
        ).json()
        resp = admin_client.post(f"/tenants/{TENANT_ID}/webhooks/{created['id']}/test")
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_test_webhook_not_found(self, admin_client):
        resp = admin_client.post(f"/tenants/{TENANT_ID}/webhooks/nonexistent/test")
        assert resp.status_code == 404

    def test_dead_letter_list_empty(self, admin_client):
        created = admin_client.post(
            f"/tenants/{TENANT_ID}/webhooks",
            json={"url": "https://example.com/hook", "event_types": ["pipeline_error"]},
        ).json()
        resp = admin_client.get(f"/tenants/{TENANT_ID}/webhooks/{created['id']}/dead-letters")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_retry_dead_letter_not_found(self, admin_client):
        created = admin_client.post(
            f"/tenants/{TENANT_ID}/webhooks",
            json={"url": "https://example.com/hook", "event_types": ["pipeline_error"]},
        ).json()
        resp = admin_client.post(
            f"/tenants/{TENANT_ID}/webhooks/{created['id']}/dead-letters/nonexistent/retry"
        )
        assert resp.status_code == 404

    def test_dead_letter_populated_on_all_failures(self, engine):
        """Engine test verifying DLQ is populated after MAX_ATTEMPTS failures."""
        transport = SuccessTransport(503)
        engine._transport = transport

        @pytest.mark.asyncio
        async def _run():
            from app.models import WebhookEndpoint
            from datetime import datetime, timezone
            webhook = WebhookEndpoint(
                id="wh-fail",
                tenant_id=TENANT_ID,
                url="https://example.com/hook",
                event_types=[WebhookEventType.pipeline_error],
                signing_secret="secret",
                enabled=True,
                created_at=datetime.now(timezone.utc),
            )
            await engine.deliver(webhook, WebhookEventType.pipeline_error, {})
            dlq = engine.get_dead_letter("wh-fail")
            assert len(dlq) == 1
