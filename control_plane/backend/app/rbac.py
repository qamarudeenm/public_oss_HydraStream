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

"""Role-based access control for the control plane API.

JWT claims:
  hydra_role       -- one of: platform_admin | tenant_admin | tenant_viewer
  hydra_tenant_id  -- tenant UUID (required for tenant_admin / tenant_viewer)

Tokens without a hydra_role claim default to platform_admin for backward
compatibility with pre-RBAC authenticated clients.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from fastapi import Depends, HTTPException, Request, status

from .auth import get_current_user


class UserRole(str, Enum):
    platform_admin = "platform_admin"
    tenant_admin = "tenant_admin"
    tenant_viewer = "tenant_viewer"


class CurrentUser:
    __slots__ = ("sub", "role", "tenant_id")

    def __init__(self, payload: dict[str, Any]) -> None:
        self.sub: str = payload.get("sub", "")
        role_raw = payload.get("hydra_role", "platform_admin")
        try:
            self.role = UserRole(role_raw)
        except ValueError:
            self.role = UserRole.platform_admin
        self.tenant_id: str | None = payload.get("hydra_tenant_id")

    def can_access_tenant(self, tenant_id: str) -> bool:
        if self.role == UserRole.platform_admin:
            return True
        return self.tenant_id == tenant_id

    def can_write_tenant(self, tenant_id: str) -> bool:
        if self.role == UserRole.platform_admin:
            return True
        return self.role == UserRole.tenant_admin and self.tenant_id == tenant_id


async def get_rbac_user(
    request: Request,
    payload: dict[str, Any] = Depends(get_current_user),
) -> CurrentUser:
    user = CurrentUser(payload)
    request.state.current_user = user
    return user


async def require_platform_admin(
    request: Request,
    user: CurrentUser = Depends(get_rbac_user),
) -> CurrentUser:
    if user.role != UserRole.platform_admin:
        request.state.rbac_denial = {
            "actor": user.sub,
            "actor_role": user.role.value,
            "reason": "Platform admin role required",
        }
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin role required",
        )
    return user


async def require_tenant_write(
    request: Request,
    user: CurrentUser = Depends(get_rbac_user),
) -> CurrentUser:
    if user.role == UserRole.tenant_viewer:
        request.state.rbac_denial = {
            "actor": user.sub,
            "actor_role": user.role.value,
            "reason": "Tenant admin or platform admin role required",
        }
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant admin or platform admin role required",
        )
    return user
