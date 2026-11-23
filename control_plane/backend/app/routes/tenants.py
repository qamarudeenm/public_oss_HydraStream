"""Tenant CRUD endpoints — all routes require a valid JWT with RBAC enforcement."""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException

from ..models import Tenant, TenantCreate, TenantUpdate
from ..rbac import CurrentUser, UserRole, get_rbac_user, require_platform_admin, require_tenant_write

router = APIRouter(prefix="/tenants", tags=["tenants"])

_store: dict[str, Tenant] = {}


def _reset_store() -> None:
    _store.clear()


@router.get("/", response_model=list[Tenant])
async def list_tenants(
    user: CurrentUser = Depends(get_rbac_user),
) -> list[Tenant]:
    if user.role == UserRole.platform_admin:
        return list(_store.values())
    if user.tenant_id is None:
        return []
    return [t for t in _store.values() if t.id == user.tenant_id]


@router.post("/", response_model=Tenant, status_code=201)
async def create_tenant(
    body: TenantCreate,
    _user: CurrentUser = Depends(require_platform_admin),
) -> Tenant:
    tenant = Tenant(id=str(uuid4()), **body.model_dump())
    _store[tenant.id] = tenant
    return tenant


@router.get("/{tenant_id}", response_model=Tenant)
async def get_tenant(
    tenant_id: UUID,
    user: CurrentUser = Depends(get_rbac_user),
) -> Tenant:
    key = str(tenant_id)
    if not user.can_access_tenant(key):
        raise HTTPException(status_code=403, detail="Access to this tenant is forbidden")
    tenant = _store.get(key)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.patch("/{tenant_id}", response_model=Tenant)
async def update_tenant(
    tenant_id: UUID,
    body: TenantUpdate,
    user: CurrentUser = Depends(require_tenant_write),
) -> Tenant:
    key = str(tenant_id)
    if not user.can_write_tenant(key):
        raise HTTPException(status_code=403, detail="Access to this tenant is forbidden")
    tenant = _store.get(key)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    updated = tenant.model_copy(update=body.model_dump(exclude_unset=True))
    _store[key] = updated
    return updated


@router.delete("/{tenant_id}", status_code=204)
async def delete_tenant(
    tenant_id: UUID,
    _user: CurrentUser = Depends(require_platform_admin),
) -> None:
    key = str(tenant_id)
    if key not in _store:
        raise HTTPException(status_code=404, detail="Tenant not found")
    del _store[key]
