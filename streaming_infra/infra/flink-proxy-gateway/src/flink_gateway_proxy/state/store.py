"""In-memory state store for statement records."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class StatementRecord:
    """Record of a statement execution."""

    name: str
    org_id: str
    env_id: str
    session_handle: str
    operation_handle: str
    sql: str
    properties: dict[str, str]
    labels: dict[str, str]
    phase: str
    traits: dict | None
    result_token: int
    created_at: datetime
    compute_pool_id: str
    principal: str
    stopped: bool = False
    detail: str = ""
    schema_extracted: bool = False


@dataclass
class StateStore:
    """Thread-safe in-memory store for statement records."""

    _records: dict[str, StatementRecord] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def add(self, record: StatementRecord) -> None:
        """Add a statement record."""
        async with self._lock:
            self._records[record.name] = record

    async def get(self, name: str) -> StatementRecord | None:
        """Get a statement record by name."""
        async with self._lock:
            return self._records.get(name)

    async def update(
        self,
        name: str,
        phase: str | None = None,
        traits: dict | None = None,
        result_token: int | None = None,
        stopped: bool | None = None,
        detail: str | None = None,
        schema_extracted: bool | None = None,
    ) -> None:
        """Update a statement record."""
        async with self._lock:
            record = self._records.get(name)
            if record is None:
                return

            if phase is not None:
                record.phase = phase
            if traits is not None:
                record.traits = traits
            if result_token is not None:
                record.result_token = result_token
            if stopped is not None:
                record.stopped = stopped
            if detail is not None:
                record.detail = detail
            if schema_extracted is not None:
                record.schema_extracted = schema_extracted

    async def delete(self, name: str) -> None:
        """Delete a statement record."""
        async with self._lock:
            self._records.pop(name, None)

    async def list_by_labels(self, label_filter: dict[str, str]) -> list[StatementRecord]:
        """List statement records matching label filters."""
        async with self._lock:
            results = []
            for record in self._records.values():
                if all(record.labels.get(k) == v for k, v in label_filter.items()):
                    results.append(record)
            return results

    async def list_all(self) -> list[StatementRecord]:
        """List all statement records."""
        async with self._lock:
            return list(self._records.values())
