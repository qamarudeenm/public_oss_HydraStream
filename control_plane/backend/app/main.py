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

import hashlib
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from . import orchestrator
from .database import AsyncSessionLocal, engine, get_db
from .db_models import TenantRecord
from .dbt_artifacts import ArtifactLoadError, load_dbt_artifacts
from .models import Tenant
from .preflight import run_preflight

TOKEN_MASK = "********"


def _hash_secret(secret: str) -> str:
    salt = os.getenv("HYDRA_TOKEN_HASH_SALT", "hydrastream-local-salt")
    return hashlib.sha256(f"{salt}:{secret}".encode("utf-8")).hexdigest()


def _secure_environment_tokens(tenant: Tenant) -> Tenant:
    for env_name in ("dev", "staging", "prod"):
        mapping = getattr(tenant.environments, env_name)
        if mapping.dbt_service_token:
            mapping.dbt_service_token_hash = _hash_secret(mapping.dbt_service_token)
            mapping.dbt_service_token = TOKEN_MASK
    return tenant


def _record_to_tenant(record: TenantRecord) -> Tenant:
    cfg = record.config or {}
    return Tenant(
        id=record.id,
        name=record.name,
        status=record.status,
        flink_version=record.flink_version,
        dbt_version=record.dbt_version,
        kafka=cfg.get("kafka"),
        sink=cfg.get("sink"),
        environments=cfg.get("environments"),
    )


def _tenant_to_record(tenant: Tenant) -> TenantRecord:
    data = tenant.dict()
    return TenantRecord(
        id=data["id"],
        name=data["name"],
        status=data.get("status", "inactive"),
        flink_version=data.get("flink_version", "1.19.1"),
        dbt_version=data.get("dbt_version", "1.7.0"),
        config={
            "kafka": data.get("kafka"),
            "sink": data.get("sink"),
            "environments": data.get("environments"),
        },
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they don't exist (Alembic handles schema migrations in prod).
    from .db_models import TenantRecord  # noqa: F401 — registers the model with Base

    from .database import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="HydraStream Control Plane", lifespan=lifespan)

_cors_origins_raw = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
_allowed_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/tenants", response_model=List[Tenant])
async def list_tenants(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TenantRecord))
    return [_record_to_tenant(r) for r in result.scalars().all()]


@app.get("/tenants/{tenant_id}", response_model=Tenant)
async def get_tenant(tenant_id: str, db: AsyncSession = Depends(get_db)):
    record = await db.get(TenantRecord, tenant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return _record_to_tenant(record)


@app.post("/tenants", response_model=Tenant)
async def create_tenant(tenant: Tenant, db: AsyncSession = Depends(get_db)):
    existing = await db.get(TenantRecord, tenant.id)
    if existing is not None:
        raise HTTPException(status_code=400, detail="Tenant ID already exists")
    tenant = _secure_environment_tokens(tenant)
    record = _tenant_to_record(tenant)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return _record_to_tenant(record)


@app.patch("/tenants/{tenant_id}", response_model=Tenant)
async def update_tenant(
    tenant_id: str,
    tenant_update: dict = Body(...),
    db: AsyncSession = Depends(get_db),
):
    record = await db.get(TenantRecord, tenant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    current = _record_to_tenant(record)
    updated_tenant = current.copy(update=tenant_update)
    updated_tenant = _secure_environment_tokens(updated_tenant)
    updated_data = updated_tenant.dict()
    record.name = updated_data["name"]
    record.status = updated_data.get("status", record.status)
    record.flink_version = updated_data.get("flink_version", record.flink_version)
    record.dbt_version = updated_data.get("dbt_version", record.dbt_version)
    record.config = {
        "kafka": updated_data.get("kafka"),
        "sink": updated_data.get("sink"),
        "environments": updated_data.get("environments"),
    }
    record.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(record)
    return _record_to_tenant(record)


@app.delete("/tenants/{tenant_id}")
async def delete_tenant(tenant_id: str, db: AsyncSession = Depends(get_db)):
    record = await db.get(TenantRecord, tenant_id)
    if record is not None:
        await db.delete(record)
        await db.commit()
    return {"status": "ok", "message": f"Tenant {tenant_id} deleted"}


@app.post("/tenants/preview")
async def preview_tenant_profiles(tenant: Tenant):
    tenant = _secure_environment_tokens(tenant)
    return {
        "profiles.yml": orchestrator.generate_tenant_profiles_yml(tenant),
        "dbt_project.yml": orchestrator.generate_tenant_dbt_project_yml(tenant),
        "vars.json": orchestrator.generate_tenant_vars(tenant),
        "docker-compose.yml": orchestrator.generate_tenant_docker_compose(tenant),
        "verification": orchestrator.verify_tenant_connection_mapping(tenant),
        "preflight": run_preflight(tenant),
    }


@app.get("/tenants/{tenant_id}/profiles.yml")
async def get_tenant_profiles(tenant_id: str, db: AsyncSession = Depends(get_db)):
    record = await db.get(TenantRecord, tenant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return orchestrator.generate_tenant_profiles_yml(_record_to_tenant(record))


@app.get("/tenants/{tenant_id}/vars.json")
async def get_tenant_vars(tenant_id: str, db: AsyncSession = Depends(get_db)):
    record = await db.get(TenantRecord, tenant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return orchestrator.generate_tenant_vars(_record_to_tenant(record))


@app.get("/tenants/{tenant_id}/dbt_project.yml")
async def get_tenant_dbt_project(tenant_id: str, db: AsyncSession = Depends(get_db)):
    record = await db.get(TenantRecord, tenant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return orchestrator.generate_tenant_dbt_project_yml(_record_to_tenant(record))


@app.get("/tenants/{tenant_id}/verification")
async def get_tenant_mapping_verification(tenant_id: str, db: AsyncSession = Depends(get_db)):
    record = await db.get(TenantRecord, tenant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return orchestrator.verify_tenant_connection_mapping(_record_to_tenant(record))


@app.get("/tenants/{tenant_id}/preflight")
async def get_tenant_preflight(tenant_id: str, db: AsyncSession = Depends(get_db)):
    record = await db.get(TenantRecord, tenant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {
        "tenantId": tenant_id,
        **run_preflight(_record_to_tenant(record)),
    }


@app.get("/tenants/{tenant_id}/runs")
async def get_tenant_run_history(tenant_id: str, db: AsyncSession = Depends(get_db)):
    record = await db.get(TenantRecord, tenant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    now = datetime.now(timezone.utc)

    runs = [
        {
            "runId": f"{tenant_id}-run-20260501-03",
            "attempt": 3,
            "maxAttempts": 3,
            "status": "failed",
            "startedAt": (now - timedelta(minutes=17)).isoformat(),
            "finishedAt": (now - timedelta(minutes=11)).isoformat(),
            "durationSeconds": 360,
            "correlationId": f"corr-{tenant_id}-a03",
            "runtimeLogUrl": f"/tenants/{tenant_id}/verification",
            "error": {
                "category": "SCHEMA_MISMATCH",
                "reasonCode": "DBT_MODEL_COLUMNS_MISSING",
                "isRetryable": False,
                "suggestedAction": "Align source schema with dbt model expectations and rerun.",
                "correlationId": f"corr-{tenant_id}-a03",
            },
            "finalSummary": {
                "rootCause": "Expected columns were missing in upstream clickstream source.",
                "remediation": "Backfill missing columns or update model SQL before next run.",
            },
            "modelFailures": [
                {"model": "transformed_clickstream_metrics", "message": "column user_agent missing"},
                {"model": "clickstream_summary", "message": "column session_id missing"},
            ],
        },
        {
            "runId": f"{tenant_id}-run-20260501-02",
            "attempt": 2,
            "maxAttempts": 3,
            "status": "retrying",
            "startedAt": (now - timedelta(minutes=30)).isoformat(),
            "finishedAt": (now - timedelta(minutes=27)).isoformat(),
            "durationSeconds": 180,
            "correlationId": f"corr-{tenant_id}-a02",
            "runtimeLogUrl": f"/tenants/{tenant_id}/verification",
            "error": {
                "category": "RATE_LIMIT",
                "reasonCode": "DBT_API_429",
                "isRetryable": True,
                "suggestedAction": "Retry after backoff window or reduce poll frequency.",
                "retryAfterSeconds": 45,
                "correlationId": f"corr-{tenant_id}-a02",
            },
            "modelFailures": [],
        },
        {
            "runId": f"{tenant_id}-run-20260501-01",
            "attempt": 1,
            "maxAttempts": 3,
            "status": "success",
            "startedAt": (now - timedelta(hours=1, minutes=12)).isoformat(),
            "finishedAt": (now - timedelta(hours=1, minutes=7)).isoformat(),
            "durationSeconds": 300,
            "correlationId": f"corr-{tenant_id}-a01",
            "runtimeLogUrl": f"/tenants/{tenant_id}/verification",
            "modelFailures": [],
        },
    ]

    latest_status = runs[0]["status"] if runs else "unknown"
    health = "degraded" if latest_status in {"failed", "retrying"} else "healthy"

    return {
        "tenantId": tenant_id,
        "health": health,
        "lastUpdatedAt": now.isoformat(),
        "runs": runs,
    }


@app.get("/tenants/{tenant_id}/dbt/artifacts/summary")
async def get_tenant_dbt_artifact_summary(tenant_id: str, db: AsyncSession = Depends(get_db)):
    record = await db.get(TenantRecord, tenant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    artifact_dir = os.getenv("HYDRA_DBT_ARTIFACT_DIR", "../../streaming_infra/dbt/target")
    artifact_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), artifact_dir))

    try:
        summary = load_dbt_artifacts(artifact_dir)
    except ArtifactLoadError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "tenantId": tenant_id,
        "artifactDir": artifact_dir,
        **summary,
    }


@app.get("/tenants/{tenant_id}/docker-compose.yml")
async def get_tenant_docker_compose(tenant_id: str, db: AsyncSession = Depends(get_db)):
    record = await db.get(TenantRecord, tenant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return orchestrator.generate_tenant_docker_compose(_record_to_tenant(record))


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as exc:
        db_status = f"unhealthy: {exc}"
    return {"status": "healthy", "database": db_status}
