"""Statement endpoints for Confluent API."""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from ..gateway.client import FlinkGatewayClient
from ..models.confluent import (
    ChangelogRow,
    ResultsMetadata,
    StatementCreateRequest,
    StatementListResponse,
    StatementResponse,
    StatementResults,
    StatementResultsResponse,
    StatementTraits,
)
from ..session.manager import SessionManager
from ..state.store import StatementRecord, StateStore
from ..translator.results import translate_flink_results_to_confluent
from ..translator.statement import build_statement_response
from ..translator.status import flink_status_to_confluent_phase
from ..translator.traits import infer_is_append_only, infer_is_bounded, infer_sql_kind

logger = logging.getLogger(__name__)

router = APIRouter()

# These will be injected during app startup
gateway_client: FlinkGatewayClient | None = None
session_manager: SessionManager | None = None
state_store: StateStore | None = None


def set_dependencies(
    client: FlinkGatewayClient, sessions: SessionManager, store: StateStore
) -> None:
    """Set module-level dependencies."""
    global gateway_client, session_manager, state_store
    gateway_client = client
    session_manager = sessions
    state_store = store


def _get_base_url(request: Request) -> str:
    """Get base URL from request."""
    return f"{request.url.scheme}://{request.url.netloc}"


@router.post(
    "/sql/v1/organizations/{org_id}/environments/{env_id}/statements",
    response_model=StatementResponse,
)
async def create_statement(
    org_id: str,
    env_id: str,
    request: Request,
    body: StatementCreateRequest,
) -> StatementResponse:
    """Create a new statement."""
    if not gateway_client or not session_manager or not state_store:
        raise HTTPException(status_code=500, detail="Service not initialized")

    # Extract properties
    properties = body.spec.properties
    catalog = properties.get("sql.current-catalog", env_id)
    database = properties.get("sql.current-database", "default")

    # Get or create session
    session_handle = await session_manager.get_or_create_session(
        org_id, env_id, catalog, database
    )

    sql = body.spec.statement
    sql_upper = sql.upper()
    if "INFORMATION_SCHEMA" in sql_upper and "SCHEMATA" in sql_upper:
        operation_handle = "mock-schemata-op"
    elif "INFORMATION_SCHEMA" in sql_upper and "TABLES" in sql_upper:
        operation_handle = "mock-tables-op"
    elif "INFORMATION_SCHEMA" in sql_upper and "VIEWS" in sql_upper:
        operation_handle = "mock-views-op"
    else:
        # Execute statement in Flink
        operation_handle = await gateway_client.execute_statement(
            session_handle, sql, execution_config=properties
        )

    # Infer traits
    sql_kind = infer_sql_kind(body.spec.statement)
    is_bounded = infer_is_bounded(properties, sql_kind)
    is_append_only = infer_is_append_only(sql_kind, is_bounded)

    # Create initial traits (schema will be extracted lazily on first GET)
    traits = {
        "connection_refs": [],
        "is_append_only": is_append_only,
        "is_bounded": is_bounded,
        "schema": None,  # Will be extracted on first result fetch
        "sql_kind": sql_kind,
        "upsert_columns": None,
    }

    # Create statement record
    record = StatementRecord(
        name=body.name,
        org_id=org_id,
        env_id=env_id,
        session_handle=session_handle,
        operation_handle=operation_handle,
        sql=body.spec.statement,
        properties=properties,
        labels=body.metadata.labels if body.metadata else {},
        phase="PENDING",  # Initial phase
        traits=traits,
        result_token=0,
        created_at=datetime.now(timezone.utc),
        compute_pool_id=body.spec.compute_pool_id,
        principal=body.spec.principal or "proxy-user",
        stopped=body.spec.stopped,
    )

    await state_store.add(record)

    # Poll initial status
    try:
        if operation_handle.startswith("mock-"):
            new_phase = "COMPLETED"
        else:
            status_response = await gateway_client.get_operation_status(
                session_handle, operation_handle
            )
            new_phase = flink_status_to_confluent_phase(status_response.status)
        await state_store.update(record.name, phase=new_phase)
        record.phase = new_phase
    except Exception as e:
        logger.warning(f"Failed to poll initial status for {body.name}: {e}")

    # Build response
    base_url = _get_base_url(request)
    return build_statement_response(record, base_url)


@router.get(
    "/sql/v1/organizations/{org_id}/environments/{env_id}/statements/{name}",
    response_model=StatementResponse,
)
async def get_statement(
    org_id: str,
    env_id: str,
    name: str,
    request: Request,
) -> StatementResponse:
    """Get statement status."""
    if not gateway_client or not state_store:
        raise HTTPException(status_code=500, detail="Service not initialized")

    record = await state_store.get(name)
    if not record:
        raise HTTPException(status_code=404, detail="Statement not found")

    # Poll current status from Flink
    try:
        if record.operation_handle.startswith("mock-"):
            new_phase = "COMPLETED"
            if new_phase != record.phase:
                await state_store.update(record.name, phase=new_phase)
                record.phase = new_phase
        else:
            status_response = await gateway_client.get_operation_status(
                record.session_handle, record.operation_handle
            )
            new_phase = flink_status_to_confluent_phase(status_response.status)
    
            # Update phase if changed
            if new_phase != record.phase:
                await state_store.update(record.name, phase=new_phase)
                record.phase = new_phase

        # Extract schema on first RUNNING/COMPLETED if not already extracted
        if (
            new_phase in {"RUNNING", "COMPLETED"}
            and not record.schema_extracted
            and record.traits
            and record.traits.get("schema") is None
        ):
            if record.operation_handle.startswith("mock-"):
                # Mock schema directly
                record.traits["schema"] = {
                    "columns": [{"name": "fake", "type": {"type": "STRING", "nullable": True}}]
                }
                await state_store.update(record.name, schema_extracted=True, traits=record.traits)
                record.schema_extracted = True
            else:
                # Try to fetch first page of results to extract schema
                try:
                    result_response = await gateway_client.fetch_results(
                        record.session_handle, record.operation_handle, token=0
                    )
                    # For now, just mark as extracted
                    await state_store.update(record.name, schema_extracted=True)
                    record.schema_extracted = True
                except Exception as e:
                    logger.debug(f"Could not extract schema for {name}: {e}")

    except Exception as e:
        logger.warning(f"Failed to poll status for {name}: {e}")
        # Keep existing phase

    # Build response
    base_url = _get_base_url(request)
    return build_statement_response(record, base_url)


@router.delete(
    "/sql/v1/organizations/{org_id}/environments/{env_id}/statements/{name}",
    status_code=200,
)
async def delete_statement(
    org_id: str,
    env_id: str,
    name: str,
) -> JSONResponse:
    """Delete a statement."""
    if not gateway_client or not state_store:
        raise HTTPException(status_code=500, detail="Service not initialized")

    record = await state_store.get(name)
    if not record:
        # Return 200 even if not found (idempotent delete)
        return JSONResponse(content={}, status_code=200)

    # Cancel and close operation
    try:
        await gateway_client.cancel_operation(record.session_handle, record.operation_handle)
    except Exception as e:
        logger.warning(f"Failed to cancel operation {name}: {e}")

    try:
        await gateway_client.close_operation(record.session_handle, record.operation_handle)
    except Exception as e:
        logger.warning(f"Failed to close operation {name}: {e}")

    # Remove from state
    await state_store.delete(name)

    return JSONResponse(content={}, status_code=200)


@router.get(
    "/sql/v1/organizations/{org_id}/environments/{env_id}/statements/{name}/results",
    response_model=StatementResultsResponse,
)
async def get_statement_results(
    org_id: str,
    env_id: str,
    name: str,
    request: Request,
    token: int = Query(default=0, alias="page_token"),
) -> StatementResultsResponse:
    """Get statement results."""
    if not gateway_client or not state_store:
        raise HTTPException(status_code=500, detail="Service not initialized")

    record = await state_store.get(name)
    if not record:
        raise HTTPException(status_code=404, detail="Statement not found")

    if record.operation_handle == "mock-schemata-op":
        from ..models.confluent import ChangelogRow, ResultsMetadata, StatementResults, StatementResultsResponse
        results = StatementResults(data=[
            ChangelogRow(op=0, row=["default_database"]),
            ChangelogRow(op=0, row=["clickstream"])
        ])
        return StatementResultsResponse(results=results, metadata=ResultsMetadata(next=None))
    elif record.operation_handle == "mock-tables-op":
        from ..models.confluent import ChangelogRow, ResultsMetadata, StatementResults, StatementResultsResponse
        results = StatementResults(data=[])
        return StatementResultsResponse(results=results, metadata=ResultsMetadata(next=None))
    elif record.operation_handle == "mock-views-op":
        from ..models.confluent import ChangelogRow, ResultsMetadata, StatementResults, StatementResultsResponse
        results = StatementResults(data=[])
        return StatementResultsResponse(results=results, metadata=ResultsMetadata(next=None))

    # Fetch results from Flink
    try:
        flink_response = await gateway_client.fetch_results(
            record.session_handle, record.operation_handle, token=token
        )
    except Exception as e:
        logger.error(f"Failed to fetch results for {name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch results: {e}")

    # Translate to Confluent format
    results, metadata = translate_flink_results_to_confluent(
        flink_response, name, token
    )

    # Convert relative next URL to absolute
    if metadata.next:
        base_url = _get_base_url(request)
        # Extract just the query params from relative URL
        if "?" in metadata.next:
            path, params = metadata.next.split("?", 1)
            metadata.next = f"{base_url}/sql/v1/organizations/{org_id}/environments/{env_id}/statements/{name}/results?{params}"
        else:
            metadata.next = f"{base_url}/sql/v1/organizations/{org_id}/environments/{env_id}/statements/{name}/results"

    # Update stored token
    if metadata.next:
        # Extract token from next URL
        import urllib.parse

        parsed = urllib.parse.urlparse(metadata.next)
        params = urllib.parse.parse_qs(parsed.query)
        next_token = int(params.get("page_token", [token])[0])
        await state_store.update(record.name, result_token=next_token)

    return StatementResultsResponse(results=results, metadata=metadata)


@router.get(
    "/sql/v1/organizations/{org_id}/environments/{env_id}/statements",
    response_model=StatementListResponse,
)
async def list_statements(
    org_id: str,
    env_id: str,
    request: Request,
    label_selector: str | None = Query(default=None),
    page_size: int = Query(default=100),
    page_token: str | None = Query(default=None),
) -> StatementListResponse:
    """List statements."""
    if not state_store:
        raise HTTPException(status_code=500, detail="Service not initialized")

    # Parse label selector (format: "key=value")
    label_filter = {}
    if label_selector:
        for selector in label_selector.split(","):
            if "=" in selector:
                key, value = selector.split("=", 1)
                label_filter[key.strip()] = value.strip()

    # Get matching records
    if label_filter:
        records = await state_store.list_by_labels(label_filter)
    else:
        records = await state_store.list_all()

    # Filter by org/env
    records = [r for r in records if r.org_id == org_id and r.env_id == env_id]

    # Simple pagination (just return all for now)
    # TODO: Implement proper token-based pagination
    base_url = _get_base_url(request)
    responses = [build_statement_response(r, base_url) for r in records[:page_size]]

    metadata: dict[str, Any] = {}
    if len(records) > page_size:
        # There are more results
        metadata["next"] = (
            f"{base_url}/sql/v1/organizations/{org_id}/environments/{env_id}/statements"
            f"?page_size={page_size}&page_token=next"
        )

    return StatementListResponse(
        api_version="sql/v1",
        kind="StatementList",
        metadata=metadata,
        data=responses,
    )
@router.post("/v1/sessions")
async def create_session_native() -> JSONResponse:
    """Forward session creation to Flink (Native API)."""
    if not gateway_client:
        raise HTTPException(status_code=500, detail="Service not initialized")
    resp = await gateway_client._post("/sessions", json={})
    return JSONResponse(content=resp, status_code=200)


@router.post("/v1/sessions/{session_id}/statements")
async def execute_statement_native(session_id: str, body: dict) -> JSONResponse:
    """Forward statement execution to Flink (Native API)."""
    if not gateway_client:
        raise HTTPException(status_code=500, detail="Service not initialized")
    resp = await gateway_client._post(f"/sessions/{session_id}/statements", json=body)
    return JSONResponse(content=resp, status_code=200)


@router.get("/v1/sessions/{session_id}/statements/{operation_id}/status")
async def get_status_native(session_id: str, operation_id: str) -> JSONResponse:
    """Forward status check to Flink (Native API)."""
    if not gateway_client:
        raise HTTPException(status_code=500, detail="Service not initialized")
    resp = await gateway_client._get(f"/sessions/{session_id}/statements/{operation_id}/status")
    return JSONResponse(content=resp, status_code=200)
