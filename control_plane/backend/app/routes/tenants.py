"""Tenant CRUD endpoints — all routes require a valid JWT."""

from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_user
from ..models import Tenant, TenantCreate, TenantUpdate

router = APIRouter(prefix="/tenants", tags=["tenants"])

# In-memory store. Replace with a real database for production.
_store: dict[str, Tenant] = {}


def _reset_store() -> None:
    """Clear the in-memory store. Used by tests."""
    _store.clear()


@router.get("/", response_model=list[Tenant])
async def list_tenants(
    _user: dict[str, Any] = Depends(get_current_user),
) -> list[Tenant]:
    return list(_store.values())


@router.post("/", response_model=Tenant, status_code=201)
async def create_tenant(
    body: TenantCreate,
    _user: dict[str, Any] = Depends(get_current_user),
) -> Tenant:
    tenant = Tenant(id=str(uuid4()), **body.model_dump())
    _store[tenant.id] = tenant
    return tenant


@router.get("/{tenant_id}", response_model=Tenant)
async def get_tenant(
    tenant_id: UUID,
    _user: dict[str, Any] = Depends(get_current_user),
) -> Tenant:
    tenant = _store.get(str(tenant_id))
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.patch("/{tenant_id}", response_model=Tenant)
async def update_tenant(
    tenant_id: UUID,
    body: TenantUpdate,
    _user: dict[str, Any] = Depends(get_current_user),
) -> Tenant:
    key = str(tenant_id)
    tenant = _store.get(key)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    updated = tenant.model_copy(update=body.model_dump(exclude_unset=True))
    _store[key] = updated
    return updated


@router.delete("/{tenant_id}", status_code=204)
async def delete_tenant(
    tenant_id: UUID,
    _user: dict[str, Any] = Depends(get_current_user),
) -> None:
    key = str(tenant_id)
    if key not in _store:
        raise HTTPException(status_code=404, detail="Tenant not found")
    del _store[key]
