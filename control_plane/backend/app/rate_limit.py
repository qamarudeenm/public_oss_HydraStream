"""Per-tenant sliding-window rate limit middleware."""

import asyncio
import base64
import json
import logging
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

security_logger = logging.getLogger("security")

_EXEMPT_PATHS = frozenset({"/health"})


def _extract_tenant_key(request: Request) -> str:
    """Rate limit key: JWT sub claim (per-tenant) or client IP as fallback.

    Decodes the JWT payload without signature verification — actual validation
    is handled by the OIDC auth dependency. Safe because this key is only used
    for bucketing, not authorization.
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        try:
            parts = token.split(".")
            if len(parts) == 3:
                padded = parts[1] + "=" * (-len(parts[1]) % 4)
                payload = json.loads(base64.b64decode(padded))
                sub = payload.get("sub")
                if sub:
                    return str(sub)
        except Exception:
            pass

    if request.client:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host
    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-tenant sliding-window rate limiter.

    Applies separate limits for read (GET/HEAD/OPTIONS) and write operations.
    Paths in _EXEMPT_PATHS bypass the limiter.
    """

    def __init__(
        self,
        app,
        reads_per_minute: int = 120,
        writes_per_minute: int = 30,
    ) -> None:
        super().__init__(app)
        self._reads_limit = reads_per_minute
        self._writes_limit = writes_per_minute
        self._windows: dict[str, deque] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        is_write = request.method not in ("GET", "HEAD", "OPTIONS")
        limit = self._writes_limit if is_write else self._reads_limit
        tenant_key = _extract_tenant_key(request)
        bucket = f"{tenant_key}:{'w' if is_write else 'r'}"

        now = time.monotonic()
        window_start = now - 60.0

        async with self._lock:
            dq = self._windows[bucket]
            while dq and dq[0] < window_start:
                dq.popleft()

            if len(dq) >= limit:
                security_logger.warning(
                    "rate_limit_exceeded",
                    extra={
                        "event": "rate_limit_exceeded",
                        "path": request.url.path,
                        "method": request.method,
                        "tenant_key": tenant_key,
                        "count": len(dq),
                        "limit": limit,
                    },
                )
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Try again later."},
                    headers={"Retry-After": "60"},
                )

            dq.append(now)

        return await call_next(request)
