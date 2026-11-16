"""OIDC JWT authentication dependency for the control plane API."""

from typing import Any, Optional

import httpx
from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

# auto_error=False so we can return 401 instead of FastAPI's default 403
_bearer = HTTPBearer(auto_error=False)

# Module-level JWKS cache; lazily populated on first authenticated request.
# Tests can inject a fake value directly: `import app.auth as auth_mod; auth_mod._jwks_cache = ...`
_jwks_cache: Optional[dict] = None


async def _fetch_jwks(issuer_url: str) -> dict:
    """Fetch JWKS from the OIDC discovery document."""
    async with httpx.AsyncClient() as client:
        discovery_url = f"{issuer_url.rstrip('/')}/.well-known/openid-configuration"
        disc_resp = await client.get(discovery_url)
        disc_resp.raise_for_status()
        jwks_resp = await client.get(disc_resp.json()["jwks_uri"])
        jwks_resp.raise_for_status()
        return jwks_resp.json()


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer),
) -> dict[str, Any]:
    """FastAPI dependency that validates the Bearer JWT and returns the token claims.

    Raises HTTP 401 for missing or invalid tokens.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    global _jwks_cache
    config = request.app.state.config
    if _jwks_cache is None:
        try:
            _jwks_cache = await _fetch_jwks(config.oidc_issuer_url)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"OIDC provider unreachable: {exc}")

    try:
        return jwt.decode(
            credentials.credentials,
            _jwks_cache,
            algorithms=["RS256"],
            audience=config.oidc_audience,
            issuer=config.oidc_issuer_url,
        )
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")
