"""dbt Cloud runtime callback endpoints."""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from ..gateway.client import FlinkGatewayClient

logger = logging.getLogger(__name__)

router = APIRouter()


class DbtExecutionConfig(BaseModel):
    """Execution context used for session and statement dispatch."""

    catalog: str | None = None
    database: str | None = None
    properties: dict[str, str] = Field(default_factory=dict)


class DbtStatementSpec(BaseModel):
    """Single statement payload from dbt callback."""

    sql: str = Field(min_length=1)
    name: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class DbtJobRef(BaseModel):
    """dbt Cloud job metadata."""

    id: int
    run_id: int
    account_id: int
    environment_id: int
    name: str | None = None


class DbtRunCallbackRequest(BaseModel):
    """Schema for dbt Cloud execution callback requests."""

    event_id: str = Field(min_length=1)
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    trigger_source: str = "dbt_cloud"
    tenant_id: str = Field(min_length=1)
    job: DbtJobRef
    execution: DbtExecutionConfig = Field(default_factory=DbtExecutionConfig)
    statements: list[DbtStatementSpec] = Field(min_length=1)


class DbtStatementDispatchResult(BaseModel):
    """Execution result for a single dispatched statement."""

    name: str
    operation_handle: str


class DbtRunCallbackResponse(BaseModel):
    """Response schema for accepted callbacks."""

    status: str
    tenant_id: str
    flink_gateway_url: str
    session_handle: str
    dispatched_count: int
    statements: list[DbtStatementDispatchResult]


_runtime_secret: str = ""
_tenant_gateway_map: dict[str, str] = {}
_max_dispatch_attempts: int = 3


def set_runtime_config(
    shared_secret: str,
    tenant_gateway_map: dict[str, str],
    max_dispatch_attempts: int = 3,
) -> None:
    """Inject runtime auth and tenant routing config."""
    global _runtime_secret, _tenant_gateway_map, _max_dispatch_attempts
    _runtime_secret = shared_secret
    _tenant_gateway_map = tenant_gateway_map
    _max_dispatch_attempts = max(1, max_dispatch_attempts)


def _classify_dispatch_error(exc: Exception) -> tuple[str, bool, str]:
    """Classify errors for retry policy and actionable propagation."""
    if isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout)):
        return (
            "gateway_unreachable",
            True,
            "Transient network failure. Verify gateway availability and retry.",
        )
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in {429, 500, 502, 503, 504}:
            return (
                "gateway_http_transient",
                True,
                "Gateway returned transient error. Retry with backoff.",
            )
        return (
            "gateway_http_terminal",
            False,
            "Gateway rejected request. Validate SQL, auth, and tenant configuration.",
        )
    return (
        "dispatch_unknown",
        False,
        "Unhandled execution failure. Inspect proxy logs and request payload.",
    )


def _validate_signature(raw_body: bytes, provided_signature: str) -> None:
    if not _runtime_secret:
        raise HTTPException(status_code=503, detail="dbt callback auth is not configured")

    if not provided_signature:
        raise HTTPException(status_code=401, detail="Missing X-Dbt-Signature header")

    expected = hmac.new(
        _runtime_secret.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    expected_header = f"sha256={expected}"
    if not hmac.compare_digest(expected_header, provided_signature):
        raise HTTPException(status_code=401, detail="Invalid callback signature")


def _resolve_tenant_gateway(tenant_id: str) -> str:
    gateway = _tenant_gateway_map.get(tenant_id)
    if not gateway:
        raise HTTPException(
            status_code=404,
            detail=f"No Flink gateway mapping configured for tenant '{tenant_id}'",
        )
    return gateway


@router.post(
    "/runtime/v1/dbt/run-callback",
    response_model=DbtRunCallbackResponse,
    status_code=202,
)
async def handle_dbt_run_callback(
    request: Request,
    payload: DbtRunCallbackRequest,
    x_dbt_signature: str = Header(default="", alias="X-Dbt-Signature"),
) -> DbtRunCallbackResponse:
    """Authenticate and dispatch dbt callback statements to tenant Flink runtime."""
    raw_body = await request.body()
    _validate_signature(raw_body, x_dbt_signature)

    gateway_url = _resolve_tenant_gateway(payload.tenant_id)

    session_properties = dict(payload.execution.properties)
    if payload.execution.catalog:
        session_properties["sql.current-catalog"] = payload.execution.catalog
    if payload.execution.database:
        session_properties["sql.current-database"] = payload.execution.database

    client = FlinkGatewayClient(gateway_url)
    session_handle: str | None = None
    dispatched: list[DbtStatementDispatchResult] = []

    attempt = 0
    try:
        session_handle = await client.open_session(
            session_name=f"dbt-cloud-{payload.job.run_id}",
            properties=session_properties,
        )

        for idx, statement in enumerate(payload.statements):
            statement_name = statement.name or f"statement-{idx + 1}"
            for attempt in range(1, _max_dispatch_attempts + 1):
                try:
                    operation_handle = await client.execute_statement(
                        session_handle,
                        statement.sql,
                        execution_config=session_properties,
                    )
                    dispatched.append(
                        DbtStatementDispatchResult(
                            name=statement_name,
                            operation_handle=operation_handle,
                        )
                    )
                    break
                except Exception as exc:
                    error_code, retryable, action = _classify_dispatch_error(exc)
                    if retryable and attempt < _max_dispatch_attempts:
                        logger.warning(
                            (
                                "Retrying statement dispatch tenant=%s "
                                "event=%s statement=%s attempt=%d"
                            ),
                            payload.tenant_id,
                            payload.event_id,
                            statement_name,
                            attempt + 1,
                        )
                        continue
                    raise HTTPException(
                        status_code=502,
                        detail={
                            "error_code": error_code,
                            "retryable": retryable,
                            "action": action,
                            "retries_attempted": attempt - 1,
                            "statement_name": statement_name,
                            "message": str(exc),
                        },
                    ) from exc

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Failed dispatch for tenant %s event %s", payload.tenant_id, payload.event_id
        )
        raise HTTPException(status_code=502, detail=f"Dispatch failed: {exc}") from exc
    finally:
        if session_handle:
            try:
                await client.close_session(session_handle)
            except Exception:
                logger.warning("Failed to close session %s", session_handle)
        await client.close()

    return DbtRunCallbackResponse(
        status="accepted",
        tenant_id=payload.tenant_id,
        flink_gateway_url=gateway_url,
        session_handle=session_handle or "",
        dispatched_count=len(dispatched),
        statements=dispatched,
    )
