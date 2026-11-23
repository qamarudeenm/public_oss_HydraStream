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

import asyncio
import hashlib
import hmac
import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

import httpx

from .models import (
    WebhookDeadLetterEntry,
    WebhookDeliveryLog,
    WebhookDeliveryStatus,
    WebhookEndpoint,
    WebhookEventType,
)


def sign_payload(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class RateLimiter:
    """Sliding-window per-tenant rate limiter."""

    def __init__(self, max_per_minute: int = 60):
        self._max = max_per_minute
        self._windows: dict[str, list[float]] = defaultdict(list)

    def allow(self, tenant_id: str) -> bool:
        now = time.monotonic()
        cutoff = now - 60.0
        window = [t for t in self._windows[tenant_id] if t > cutoff]
        self._windows[tenant_id] = window
        if len(window) >= self._max:
            return False
        self._windows[tenant_id].append(now)
        return True


class WebhookDeliveryEngine:
    MAX_ATTEMPTS = 5

    def __init__(
        self,
        rate_limiter: Optional[RateLimiter] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        base_delay: float = 1.0,
    ):
        self._rate_limiter = rate_limiter or RateLimiter()
        self._transport = transport
        self._base_delay = base_delay
        self._delivery_logs: list[WebhookDeliveryLog] = []
        self._dead_letter: list[WebhookDeadLetterEntry] = []
        self._log_counter = 0
        self._dlq_counter = 0

    def _next_log_id(self) -> str:
        self._log_counter += 1
        return f"log-{self._log_counter}"

    def _next_dlq_id(self) -> str:
        self._dlq_counter += 1
        return f"dlq-{self._dlq_counter}"

    async def deliver(
        self,
        webhook: WebhookEndpoint,
        event_type: WebhookEventType,
        payload: dict,
    ) -> WebhookDeliveryLog:
        if not self._rate_limiter.allow(webhook.tenant_id):
            log = WebhookDeliveryLog(
                id=self._next_log_id(),
                webhook_id=webhook.id,
                tenant_id=webhook.tenant_id,
                event_type=event_type,
                payload=payload,
                status=WebhookDeliveryStatus.failed,
                attempt=0,
                error="Rate limit exceeded",
                delivered_at=datetime.now(timezone.utc),
            )
            self._delivery_logs.append(log)
            return log

        body = json.dumps(payload).encode()
        signature = sign_payload(webhook.signing_secret, body)
        headers = {
            "Content-Type": "application/json",
            "X-Hydra-Signature": f"sha256={signature}",
            "X-Hydra-Event": event_type.value,
        }

        last_log: Optional[WebhookDeliveryLog] = None
        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            start = time.monotonic()
            status = WebhookDeliveryStatus.failed
            response_code: Optional[int] = None
            error: Optional[str] = None

            try:
                client_kwargs: dict = {"timeout": 10.0}
                if self._transport is not None:
                    client_kwargs["transport"] = self._transport
                async with httpx.AsyncClient(**client_kwargs) as client:
                    resp = await client.post(webhook.url, content=body, headers=headers)
                    response_code = resp.status_code
                    if 200 <= resp.status_code < 300:
                        status = WebhookDeliveryStatus.success
            except Exception as exc:
                error = str(exc)

            latency_ms = int((time.monotonic() - start) * 1000)
            log = WebhookDeliveryLog(
                id=self._next_log_id(),
                webhook_id=webhook.id,
                tenant_id=webhook.tenant_id,
                event_type=event_type,
                payload=payload,
                status=status,
                attempt=attempt,
                response_code=response_code,
                latency_ms=latency_ms,
                error=error,
                delivered_at=datetime.now(timezone.utc),
            )
            self._delivery_logs.append(log)
            last_log = log

            if status == WebhookDeliveryStatus.success:
                return log

            if attempt < self.MAX_ATTEMPTS:
                await asyncio.sleep(self._base_delay * (2 ** (attempt - 1)))

        # All attempts exhausted → dead-letter queue
        dlq_entry = WebhookDeadLetterEntry(
            id=self._next_dlq_id(),
            webhook_id=webhook.id,
            tenant_id=webhook.tenant_id,
            event_type=event_type,
            payload=payload,
            attempts=self.MAX_ATTEMPTS,
            last_error=last_log.error if last_log else None,
            created_at=datetime.now(timezone.utc),
        )
        self._dead_letter.append(dlq_entry)
        return last_log  # type: ignore[return-value]

    def get_delivery_logs(self, webhook_id: str) -> list[WebhookDeliveryLog]:
        return [log for log in self._delivery_logs if log.webhook_id == webhook_id]

    def get_dead_letter(self, webhook_id: str) -> list[WebhookDeadLetterEntry]:
        return [e for e in self._dead_letter if e.webhook_id == webhook_id]

    async def retry_dead_letter(
        self,
        dlq_id: str,
        webhook_store: dict[str, WebhookEndpoint],
    ) -> Optional[WebhookDeliveryLog]:
        entry = next((e for e in self._dead_letter if e.id == dlq_id), None)
        if entry is None:
            return None
        webhook = webhook_store.get(entry.webhook_id)
        if webhook is None:
            return None
        self._dead_letter = [e for e in self._dead_letter if e.id != dlq_id]
        return await self.deliver(webhook, entry.event_type, entry.payload)


_engine = WebhookDeliveryEngine()


def get_engine() -> WebhookDeliveryEngine:
    return _engine
