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

"""State store for statement records with pluggable backends."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Protocol


class RedisClient(Protocol):
    """Protocol for async Redis client used by this module."""

    async def set(self, key: str, value: str) -> Any:
        ...

    async def get(self, key: str) -> str | bytes | None:
        ...

    async def delete(self, key: str) -> Any:
        ...

    def scan_iter(self, match: str):
        ...

    async def ping(self) -> Any:
        ...

    async def aclose(self) -> Any:
        ...


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

    def to_payload(self) -> dict[str, Any]:
        """Serialize to a JSON-safe payload."""
        payload = asdict(self)
        payload["created_at"] = self.created_at.isoformat()
        return payload

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> StatementRecord:
        """Deserialize from a payload."""
        data = dict(payload)
        created_raw = data.get("created_at")
        if isinstance(created_raw, str):
            data["created_at"] = datetime.fromisoformat(created_raw)
        return cls(**data)


@dataclass
class StateStore:
    """Thread-safe state store with memory and Redis backends."""

    backend: str = "memory"
    redis_url: str | None = None
    redis_key_prefix: str = "flink-gateway-proxy:statements"
    _records: dict[str, StatementRecord] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _redis: RedisClient | None = None
    _owns_redis_client: bool = False

    @classmethod
    async def create(
        cls,
        backend: str,
        redis_url: str | None = None,
        redis_key_prefix: str = "flink-gateway-proxy:statements",
    ) -> StateStore:
        """Create and initialize a state store."""
        store = cls(
            backend=backend,
            redis_url=redis_url,
            redis_key_prefix=redis_key_prefix,
        )
        await store.start()
        return store

    async def start(self) -> None:
        """Initialize backend resources."""
        if self.backend == "memory":
            return

        if self.backend != "redis":
            raise ValueError(f"Unsupported state backend: {self.backend}")

        if self._redis is None:
            if not self.redis_url:
                raise ValueError("redis_url is required when backend=redis")

            try:
                from redis.asyncio import Redis
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "redis package is required for Redis state backend"
                ) from exc

            self._redis = Redis.from_url(self.redis_url, decode_responses=True)
            self._owns_redis_client = True

        await self._redis.ping()

    async def close(self) -> None:
        """Close backend resources."""
        if self._owns_redis_client and self._redis is not None:
            await self._redis.aclose()

    def _record_key(self, name: str) -> str:
        return f"{self.redis_key_prefix}:{name}"

    async def add(self, record: StatementRecord) -> None:
        """Add a statement record."""
        async with self._lock:
            if self.backend == "memory":
                self._records[record.name] = record
                return

            await self._set_redis_record(record)

    async def get(self, name: str) -> StatementRecord | None:
        """Get a statement record by name."""
        async with self._lock:
            if self.backend == "memory":
                return self._records.get(name)

            return await self._get_redis_record(name)

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
            record: StatementRecord | None
            if self.backend == "memory":
                record = self._records.get(name)
            else:
                record = await self._get_redis_record(name)

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

            if self.backend == "memory":
                self._records[name] = record
            else:
                await self._set_redis_record(record)

    async def delete(self, name: str) -> None:
        """Delete a statement record."""
        async with self._lock:
            if self.backend == "memory":
                self._records.pop(name, None)
                return

            redis = self._require_redis()
            await redis.delete(self._record_key(name))

    async def list_by_labels(self, label_filter: dict[str, str]) -> list[StatementRecord]:
        """List statement records matching label filters."""
        records = await self.list_all()
        return [
            record
            for record in records
            if all(record.labels.get(k) == v for k, v in label_filter.items())
        ]

    async def list_all(self) -> list[StatementRecord]:
        """List all statement records."""
        async with self._lock:
            if self.backend == "memory":
                return list(self._records.values())

            return await self._list_redis_records()

    def _require_redis(self) -> RedisClient:
        if self._redis is None:
            raise RuntimeError("Redis backend is not initialized")
        return self._redis

    async def _set_redis_record(self, record: StatementRecord) -> None:
        redis = self._require_redis()
        payload = json.dumps(record.to_payload(), separators=(",", ":"))
        await redis.set(self._record_key(record.name), payload)

    async def _get_redis_record(self, name: str) -> StatementRecord | None:
        redis = self._require_redis()
        raw = await redis.get(self._record_key(name))
        if raw is None:
            return None

        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")

        payload = json.loads(raw)
        return StatementRecord.from_payload(payload)

    async def _list_redis_records(self) -> list[StatementRecord]:
        redis = self._require_redis()
        results: list[StatementRecord] = []
        async for key in redis.scan_iter(match=f"{self.redis_key_prefix}:*"):
            if isinstance(key, bytes):
                key = key.decode("utf-8")

            raw = await redis.get(key)
            if raw is None:
                continue
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")

            payload = json.loads(raw)
            results.append(StatementRecord.from_payload(payload))

        return results
