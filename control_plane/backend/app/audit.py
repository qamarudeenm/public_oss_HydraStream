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

"""Audit logging: event model and in-memory store (swappable with DB store in production)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

_logger = logging.getLogger("audit")


class AuditEvent(BaseModel):
    actor: str
    actor_role: str
    action: str
    resource: str
    tenant_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    outcome: str  # "success" | "denied" | "error"
    ip_address: Optional[str] = None
    status_code: int
    denial_reason: Optional[str] = None


class AuditStore:
    """Thread-safe in-memory store; production can swap in a DB-backed implementation."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    async def append(self, event: AuditEvent) -> None:
        self._events.append(event)
        _logger.info(
            "audit_event",
            extra={
                "actor": event.actor,
                "actor_role": event.actor_role,
                "action": event.action,
                "resource": event.resource,
                "tenant_id": event.tenant_id,
                "outcome": event.outcome,
                "status_code": event.status_code,
                "denial_reason": event.denial_reason,
            },
        )

    async def query(
        self,
        tenant_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEvent]:
        events = self._events if tenant_id is None else [
            e for e in self._events if e.tenant_id == tenant_id
        ]
        return events[offset : offset + limit]

    def reset(self) -> None:
        self._events.clear()


_store = AuditStore()


def get_store() -> AuditStore:
    return _store


def reset_store() -> None:
    _store.reset()
