"""Security middleware: HTTP security headers, request body size enforcement, and audit logging."""

import logging
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

security_logger = logging.getLogger("security")

_MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _extract_tenant_id(path: str) -> Optional[str]:
    """Parse /tenants/{tenant_id}/... and return the tenant_id segment."""
    parts = path.strip("/").split("/")
    for i, part in enumerate(parts):
        if part == "tenants" and i + 1 < len(parts):
            candidate = parts[i + 1]
            # Exclude pseudo-paths like /tenants/preview
            if candidate not in ("preview",):
                return candidate
    return None


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'"
        )
        return response


class AuditMiddleware(BaseHTTPMiddleware):
    """Log all mutating requests (POST/PUT/PATCH/DELETE) to the audit store."""

    def __init__(self, app, audit_store) -> None:
        super().__init__(app)
        self._audit_store = audit_store

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        if request.method not in _MUTATION_METHODS:
            return response

        rbac_denial = getattr(request.state, "rbac_denial", None)
        current_user = getattr(request.state, "current_user", None)

        if current_user is None and rbac_denial is None:
            return response

        from .audit import AuditEvent

        tenant_id = _extract_tenant_id(str(request.url.path))

        if rbac_denial:
            actor = rbac_denial["actor"]
            actor_role = rbac_denial["actor_role"]
            outcome = "denied"
            denial_reason = rbac_denial["reason"]
        else:
            actor = current_user.sub
            actor_role = current_user.role.value
            if response.status_code == 403:
                outcome = "denied"
                denial_reason = "Access forbidden"
            elif response.status_code >= 400:
                outcome = "error"
                denial_reason = None
            else:
                outcome = "success"
                denial_reason = None

        event = AuditEvent(
            actor=actor,
            actor_role=actor_role,
            action=request.method,
            resource=str(request.url.path),
            tenant_id=tenant_id,
            outcome=outcome,
            ip_address=request.client.host if request.client else None,
            status_code=response.status_code,
            denial_reason=denial_reason,
        )
        await self._audit_store.append(event)

        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Content-Length exceeds the configured maximum."""

    def __init__(self, app, max_bytes: int) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                length = int(content_length)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header"},
                )
            if length > self.max_bytes:
                security_logger.warning(
                    "request_body_too_large",
                    extra={
                        "event": "request_body_too_large",
                        "path": request.url.path,
                        "content_length": length,
                        "max_bytes": self.max_bytes,
                        "client": request.client.host if request.client else None,
                    },
                )
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request body too large"},
                )
        return await call_next(request)
