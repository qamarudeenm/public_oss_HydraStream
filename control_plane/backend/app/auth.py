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

"""OIDC JWT authentication dependency for the control plane API."""

from __future__ import annotations

import logging
import threading
from typing import Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from .config import settings

security_logger = logging.getLogger("security")

_bearer = HTTPBearer(auto_error=False)

_jwks_cache: dict[str, Any] = {}
_jwks_lock = threading.Lock()


def _get_jwks() -> dict:
    if not settings.oidc_issuer_url:
        return {}
    with _jwks_lock:
        if _jwks_cache:
            return _jwks_cache
        discovery_url = settings.oidc_issuer_url.rstrip("/") + "/.well-known/openid-configuration"
        try:
            resp = httpx.get(discovery_url, timeout=5.0)
            resp.raise_for_status()
            jwks_uri = resp.json()["jwks_uri"]
            jwks_resp = httpx.get(jwks_uri, timeout=5.0)
            jwks_resp.raise_for_status()
            _jwks_cache.update(jwks_resp.json())
        except Exception as exc:
            security_logger.error(
                "auth_oidc_unreachable",
                extra={"event": "auth_oidc_unreachable", "reason": str(exc)},
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Could not fetch JWKS from OIDC provider: {exc}",
            ) from exc
        return _jwks_cache


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """FastAPI dependency that validates a JWT Bearer token.

    - When CONTROL_PLANE_AUTH_DISABLED=true, authentication is bypassed (for local dev).
    - When CONTROL_PLANE_OIDC_ISSUER_URL is not set, all requests are rejected with 401.
    - Otherwise, validates the RS256 JWT against the OIDC JWKS endpoint.
    """
    if settings.auth_disabled:
        return {"sub": "local-dev", "auth": "disabled"}

    if not credentials:
        security_logger.warning(
            "auth_missing_token",
            extra={"event": "auth_missing_token"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not settings.oidc_issuer_url:
        security_logger.warning(
            "auth_oidc_not_configured",
            extra={"event": "auth_oidc_not_configured"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OIDC issuer not configured",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jwks = _get_jwks()
    try:
        payload = jwt.decode(
            credentials.credentials,
            jwks,
            algorithms=["RS256"],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer_url.rstrip("/"),
            options={"verify_at_hash": False},
        )
    except JWTError as exc:
        security_logger.warning(
            "auth_invalid_token",
            extra={
                "event": "auth_invalid_token",
                "reason": str(exc),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return payload
