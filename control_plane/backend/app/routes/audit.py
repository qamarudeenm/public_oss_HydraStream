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

"""Audit log query endpoint."""

from fastapi import APIRouter, Depends, HTTPException, Query

from ..audit import AuditEvent, AuditStore, get_store
from ..rbac import CurrentUser, UserRole, get_rbac_user

router = APIRouter(tags=["audit"])


def _get_audit_store() -> AuditStore:
    return get_store()


@router.get("/tenants/{tenant_id}/audit-logs", response_model=list[AuditEvent])
async def get_tenant_audit_logs(
    tenant_id: str,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(get_rbac_user),
    store: AuditStore = Depends(_get_audit_store),
) -> list[AuditEvent]:
    if user.role == UserRole.platform_admin:
        return await store.query(tenant_id=tenant_id, limit=limit, offset=offset)
    if user.tenant_id != tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Access to this tenant's audit logs is forbidden",
        )
    return await store.query(tenant_id=tenant_id, limit=limit, offset=offset)
