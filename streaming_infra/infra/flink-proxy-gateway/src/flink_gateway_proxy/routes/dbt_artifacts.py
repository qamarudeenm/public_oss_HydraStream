"""dbt artifact summary endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..dbt_artifacts import ArtifactParseError, parse_artifact_summary

router = APIRouter()

_default_artifact_dir: str = ""
_tenant_artifact_map: dict[str, str] = {}


class DbtArtifactSummaryResponse(BaseModel):
    """Summary response for model inventory and lineage."""

    tenant_id: str
    artifact_dir: str
    metadata: dict
    inventory: list[dict]
    lineage: list[dict]


def set_artifact_config(default_artifact_dir: str, tenant_artifact_map: dict[str, str]) -> None:
    """Inject artifact location settings."""
    global _default_artifact_dir, _tenant_artifact_map
    _default_artifact_dir = default_artifact_dir
    _tenant_artifact_map = tenant_artifact_map


def _resolve_artifact_dir(tenant_id: str) -> str:
    if tenant_id in _tenant_artifact_map:
        return _tenant_artifact_map[tenant_id]
    if _default_artifact_dir:
        return _default_artifact_dir
    raise HTTPException(
        status_code=404,
        detail=(
            f"No dbt artifact directory configured for tenant '{tenant_id}'. "
            "Set PROXY_DBT_TENANT_ARTIFACT_MAP or PROXY_DBT_ARTIFACT_DIR."
        ),
    )


@router.get(
    "/runtime/v1/tenants/{tenant_id}/dbt/artifacts/summary",
    response_model=DbtArtifactSummaryResponse,
)
async def get_dbt_artifact_summary(tenant_id: str) -> DbtArtifactSummaryResponse:
    """Return model inventory and lineage extracted from dbt artifacts."""
    artifact_dir = _resolve_artifact_dir(tenant_id)
    try:
        summary = parse_artifact_summary(artifact_dir)
    except ArtifactParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return DbtArtifactSummaryResponse(
        tenant_id=tenant_id,
        artifact_dir=artifact_dir,
        metadata=summary.metadata,
        inventory=summary.inventory,
        lineage=summary.lineage,
    )
