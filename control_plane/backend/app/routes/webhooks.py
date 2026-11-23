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

"""Webhook registration, delivery, and management endpoints."""

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from ..models import (
    WebhookDeadLetterEntry,
    WebhookDeliveryLog,
    WebhookEndpoint,
    WebhookEndpointCreate,
    WebhookEndpointUpdate,
    WebhookEventType,
)
from ..notification_manager import WebhookDeliveryEngine, get_engine
from ..rbac import CurrentUser, get_rbac_user, require_tenant_write

router = APIRouter(tags=["webhooks"])

# tenant_id -> webhook_id -> WebhookEndpoint
_store: dict[str, dict[str, WebhookEndpoint]] = {}


def _reset_store() -> None:
    _store.clear()


def _tenant_webhooks(tenant_id: str) -> dict[str, WebhookEndpoint]:
    return _store.setdefault(tenant_id, {})


def _flat_store() -> dict[str, WebhookEndpoint]:
    """Flat map of all webhooks across tenants (for DLQ retry lookups)."""
    result: dict[str, WebhookEndpoint] = {}
    for tenant_webhooks in _store.values():
        result.update(tenant_webhooks)
    return result


@router.post("/tenants/{tenant_id}/webhooks", response_model=WebhookEndpoint, status_code=201)
async def register_webhook(
    tenant_id: str,
    body: WebhookEndpointCreate,
    user: CurrentUser = Depends(require_tenant_write),
) -> WebhookEndpoint:
    if not user.can_write_tenant(tenant_id):
        raise HTTPException(status_code=403, detail="Access to this tenant is forbidden")
    webhook = WebhookEndpoint(
        id=secrets.token_hex(16),
        tenant_id=tenant_id,
        url=body.url,
        event_types=body.event_types,
        signing_secret=secrets.token_hex(32),
        enabled=True,
        created_at=datetime.now(timezone.utc),
    )
    _tenant_webhooks(tenant_id)[webhook.id] = webhook
    return webhook


@router.get("/tenants/{tenant_id}/webhooks", response_model=list[WebhookEndpoint])
async def list_webhooks(
    tenant_id: str,
    user: CurrentUser = Depends(get_rbac_user),
) -> list[WebhookEndpoint]:
    if not user.can_access_tenant(tenant_id):
        raise HTTPException(status_code=403, detail="Access to this tenant is forbidden")
    return list(_tenant_webhooks(tenant_id).values())


@router.get("/tenants/{tenant_id}/webhooks/{webhook_id}", response_model=WebhookEndpoint)
async def get_webhook(
    tenant_id: str,
    webhook_id: str,
    user: CurrentUser = Depends(get_rbac_user),
) -> WebhookEndpoint:
    if not user.can_access_tenant(tenant_id):
        raise HTTPException(status_code=403, detail="Access to this tenant is forbidden")
    webhook = _tenant_webhooks(tenant_id).get(webhook_id)
    if webhook is None:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return webhook


@router.patch("/tenants/{tenant_id}/webhooks/{webhook_id}", response_model=WebhookEndpoint)
async def update_webhook(
    tenant_id: str,
    webhook_id: str,
    body: WebhookEndpointUpdate,
    user: CurrentUser = Depends(require_tenant_write),
) -> WebhookEndpoint:
    if not user.can_write_tenant(tenant_id):
        raise HTTPException(status_code=403, detail="Access to this tenant is forbidden")
    webhook = _tenant_webhooks(tenant_id).get(webhook_id)
    if webhook is None:
        raise HTTPException(status_code=404, detail="Webhook not found")
    updated = webhook.model_copy(update=body.model_dump(exclude_unset=True))
    _tenant_webhooks(tenant_id)[webhook_id] = updated
    return updated


@router.delete("/tenants/{tenant_id}/webhooks/{webhook_id}", status_code=204)
async def delete_webhook(
    tenant_id: str,
    webhook_id: str,
    user: CurrentUser = Depends(require_tenant_write),
) -> None:
    if not user.can_write_tenant(tenant_id):
        raise HTTPException(status_code=403, detail="Access to this tenant is forbidden")
    webhooks = _tenant_webhooks(tenant_id)
    if webhook_id not in webhooks:
        raise HTTPException(status_code=404, detail="Webhook not found")
    del webhooks[webhook_id]


@router.get(
    "/tenants/{tenant_id}/webhooks/{webhook_id}/deliveries",
    response_model=list[WebhookDeliveryLog],
)
async def list_deliveries(
    tenant_id: str,
    webhook_id: str,
    user: CurrentUser = Depends(get_rbac_user),
    engine: WebhookDeliveryEngine = Depends(get_engine),
) -> list[WebhookDeliveryLog]:
    if not user.can_access_tenant(tenant_id):
        raise HTTPException(status_code=403, detail="Access to this tenant is forbidden")
    if webhook_id not in _tenant_webhooks(tenant_id):
        raise HTTPException(status_code=404, detail="Webhook not found")
    return engine.get_delivery_logs(webhook_id)


@router.get(
    "/tenants/{tenant_id}/webhooks/{webhook_id}/dead-letters",
    response_model=list[WebhookDeadLetterEntry],
)
async def list_dead_letters(
    tenant_id: str,
    webhook_id: str,
    user: CurrentUser = Depends(get_rbac_user),
    engine: WebhookDeliveryEngine = Depends(get_engine),
) -> list[WebhookDeadLetterEntry]:
    if not user.can_access_tenant(tenant_id):
        raise HTTPException(status_code=403, detail="Access to this tenant is forbidden")
    if webhook_id not in _tenant_webhooks(tenant_id):
        raise HTTPException(status_code=404, detail="Webhook not found")
    return engine.get_dead_letter(webhook_id)


@router.post(
    "/tenants/{tenant_id}/webhooks/{webhook_id}/dead-letters/{dlq_id}/retry",
    response_model=WebhookDeliveryLog,
)
async def retry_dead_letter(
    tenant_id: str,
    webhook_id: str,
    dlq_id: str,
    user: CurrentUser = Depends(require_tenant_write),
    engine: WebhookDeliveryEngine = Depends(get_engine),
) -> WebhookDeliveryLog:
    if not user.can_write_tenant(tenant_id):
        raise HTTPException(status_code=403, detail="Access to this tenant is forbidden")
    if webhook_id not in _tenant_webhooks(tenant_id):
        raise HTTPException(status_code=404, detail="Webhook not found")
    result = await engine.retry_dead_letter(dlq_id, _flat_store())
    if result is None:
        raise HTTPException(status_code=404, detail="Dead-letter entry not found")
    return result


@router.post(
    "/tenants/{tenant_id}/webhooks/{webhook_id}/test",
    response_model=WebhookDeliveryLog,
)
async def test_webhook(
    tenant_id: str,
    webhook_id: str,
    user: CurrentUser = Depends(require_tenant_write),
    engine: WebhookDeliveryEngine = Depends(get_engine),
) -> WebhookDeliveryLog:
    if not user.can_write_tenant(tenant_id):
        raise HTTPException(status_code=403, detail="Access to this tenant is forbidden")
    webhook = _tenant_webhooks(tenant_id).get(webhook_id)
    if webhook is None:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return await engine.deliver(
        webhook,
        WebhookEventType.pipeline_error,
        {"event": "test", "webhook_id": webhook_id, "tenant_id": tenant_id},
    )
