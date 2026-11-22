"""Security middleware: HTTP security headers and request body size enforcement."""

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

security_logger = logging.getLogger("security")


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
