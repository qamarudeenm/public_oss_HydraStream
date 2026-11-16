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

from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path
from urllib.parse import urlparse

from .models import Tenant

# Required columns for the metrics model per the Flink/dbt contract.
_METRICS_REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {"user_id", "session_id", "event_type", "event_count", "window_start", "window_end"}
)


def _check_sink_readiness(tenant: Tenant) -> dict:
    sink = tenant.sink
    required = {
        "jdbc_url": bool(sink.jdbc_url),
        "user": bool(sink.user),
        "summary_table": bool(sink.summary_table),
        "metrics_table": bool(sink.metrics_table),
    }
    return {
        "ok": all(required.values()),
        "details": required,
    }


def _load_manifest_model_columns(artifact_dir: str) -> dict[str, set[str]]:
    """
    Returns ``{model_name: set_of_column_names}`` from the dbt manifest.
    Returns an empty dict when the manifest is absent or unreadable so that
    callers can treat a missing manifest as a non-fatal condition.
    """
    manifest_path = Path(artifact_dir) / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    result: dict[str, set[str]] = {}
    for node in manifest.get("nodes", {}).values():
        if node.get("resource_type") == "model":
            name = node.get("name") or node.get("alias")
            if name:
                result[name] = set(node.get("columns", {}).keys())
    return result


def _check_schema_contract(tenant: Tenant) -> dict:
    """
    Validates schema contract compatibility between the source Kafka topic
    and the destination sink tables.

    Checks performed:
    1. Table names are non-empty in the sink config.
    2. Sink tables are present as dbt models in the manifest (warning only).
    3. The metrics model has all required columns defined in the manifest.
    """
    sink = tenant.sink
    expected_tables = [sink.summary_table, sink.metrics_table]
    missing_tables = [t for t in expected_tables if not t]
    if missing_tables:
        return {
            "ok": False,
            "expectedTables": expected_tables,
            "missingTables": missing_tables,
            "manifestAvailable": False,
            "modelMismatches": [],
            "manifestWarnings": [],
        }

    artifact_dir = os.getenv("HYDRA_DBT_ARTIFACT_DIR", "../../streaming_infra/dbt/target")
    artifact_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), artifact_dir))
    manifest_models = _load_manifest_model_columns(artifact_dir)
    manifest_available = bool(manifest_models)

    model_mismatches: list[dict] = []
    manifest_warnings: list[dict] = []

    if manifest_available:
        # Tables absent from the manifest are a warning, not a failure — they
        # may be created by Flink directly rather than by a dbt model.
        for table in expected_tables:
            if table not in manifest_models:
                manifest_warnings.append(
                    {"table": table, "issue": "NOT_IN_MANIFEST"}
                )

        # Validate column completeness for the metrics model (strict).
        if sink.metrics_table in manifest_models:
            defined = manifest_models[sink.metrics_table]
            if defined:  # only validate when manifest carries column info
                missing_cols = sorted(_METRICS_REQUIRED_COLUMNS - defined)
                if missing_cols:
                    model_mismatches.append(
                        {
                            "table": sink.metrics_table,
                            "issue": "MISSING_REQUIRED_COLUMNS",
                            "missingColumns": missing_cols,
                            "definedColumns": sorted(defined),
                        }
                    )

    return {
        "ok": len(missing_tables) == 0 and len(model_mismatches) == 0,
        "expectedTables": expected_tables,
        "missingTables": missing_tables,
        "manifestAvailable": manifest_available,
        "modelMismatches": model_mismatches,
        "manifestWarnings": manifest_warnings,
    }


def _extract_host_port(jdbc_url: str) -> tuple[str | None, int | None]:
    if not jdbc_url:
        return (None, None)
    # JDBC URLs have the "jdbc:" prefix which urlparse does not understand directly.
    normalized = jdbc_url[5:] if jdbc_url.startswith("jdbc:") else jdbc_url
    parsed = urlparse(normalized)
    return (parsed.hostname, parsed.port)


def _check_reachability(tenant: Tenant, timeout_seconds: float = 1.5) -> dict:
    start = time.perf_counter()
    host, port = _extract_host_port(tenant.sink.jdbc_url)
    if not host or not port:
        return {
            "ok": False,
            "host": host,
            "port": port,
            "latencyMs": int((time.perf_counter() - start) * 1000),
            "error": "JDBC_URL_PARSE_FAILED",
        }

    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return {
                "ok": True,
                "host": host,
                "port": port,
                "latencyMs": int((time.perf_counter() - start) * 1000),
            }
    except OSError as exc:
        return {
            "ok": False,
            "host": host,
            "port": port,
            "latencyMs": int((time.perf_counter() - start) * 1000),
            "error": f"{type(exc).__name__}: {exc}",
        }


def _probe_tcp(host: str | None, port: int | None, timeout_seconds: float) -> dict:
    start = time.perf_counter()
    if not host or not port:
        return {
            "ok": False,
            "host": host,
            "port": port,
            "latencyMs": int((time.perf_counter() - start) * 1000),
            "error": "MISSING_HOST_OR_PORT",
        }
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return {
                "ok": True,
                "host": host,
                "port": port,
                "latencyMs": int((time.perf_counter() - start) * 1000),
            }
    except OSError as exc:
        return {
            "ok": False,
            "host": host,
            "port": port,
            "latencyMs": int((time.perf_counter() - start) * 1000),
            "error": f"{type(exc).__name__}: {exc}",
        }


def _check_kafka_reachability(tenant: Tenant, timeout_seconds: float = 1.5) -> dict:
    """TCP-probe the first Kafka bootstrap server to verify source reachability."""
    bootstrap = tenant.kafka.bootstrap_servers
    first = bootstrap.split(",")[0].strip()
    if ":" not in first:
        return {
            "ok": False,
            "host": first,
            "port": None,
            "latencyMs": 0,
            "error": "KAFKA_BOOTSTRAP_PARSE_FAILED",
        }
    host, _, raw_port = first.rpartition(":")
    try:
        port = int(raw_port)
    except ValueError:
        return {
            "ok": False,
            "host": host,
            "port": None,
            "latencyMs": 0,
            "error": "KAFKA_PORT_PARSE_FAILED",
        }
    return _probe_tcp(host, port, timeout_seconds)


def _check_runtime_reachability(tenant: Tenant, timeout_seconds: float = 1.5) -> dict:
    runtime_host = os.getenv("HYDRA_RUNTIME_HOST_TEMPLATE", "proxy-{tenant_id}").format(tenant_id=tenant.id)
    runtime_port = int(os.getenv("HYDRA_RUNTIME_PORT", "8080"))
    flink_host = os.getenv("HYDRA_FLINK_GATEWAY_HOST_TEMPLATE", f"flink-sql-gateway-{tenant.id}")
    flink_port = int(os.getenv("HYDRA_FLINK_GATEWAY_PORT", "8083"))
    dbt_cloud_host = os.getenv("DBT_CLOUD_HOST", "cloud.getdbt.com")
    dbt_cloud_port = int(os.getenv("DBT_CLOUD_PORT", "443"))

    runtime_probe = _probe_tcp(runtime_host, runtime_port, timeout_seconds)
    flink_probe = _probe_tcp(flink_host, flink_port, timeout_seconds)
    dbt_probe = _probe_tcp(dbt_cloud_host, dbt_cloud_port, timeout_seconds)

    return {
        "ok": runtime_probe["ok"] and flink_probe["ok"] and dbt_probe["ok"],
        "checks": {
            "controlPlaneToTenantRuntime": runtime_probe,
            "controlPlaneToFlinkGateway": flink_probe,
            "controlPlaneToDbtCloud": dbt_probe,
        },
    }


def run_preflight(tenant: Tenant) -> dict:
    sink = _check_sink_readiness(tenant)
    schema = _check_schema_contract(tenant)
    sink_reachability = _check_reachability(tenant)
    kafka_reachability = _check_kafka_reachability(tenant)
    runtime_reachability = _check_runtime_reachability(tenant)

    failures = []
    if not sink["ok"]:
        failures.append("SINK_NOT_READY")
    if not schema["ok"]:
        failures.append("SCHEMA_CONTRACT_INVALID")
    if not sink_reachability["ok"]:
        failures.append("SINK_UNREACHABLE")
    if not kafka_reachability["ok"]:
        failures.append("KAFKA_UNREACHABLE")
    if not runtime_reachability["ok"]:
        failures.append("RUNTIME_LINK_UNREACHABLE")

    warnings = []
    if sink_reachability["ok"] and sink_reachability["latencyMs"] > 1000:
        warnings.append("SINK_LATENCY_HIGH")
    if kafka_reachability["ok"] and kafka_reachability.get("latencyMs", 0) > 1000:
        warnings.append("KAFKA_LATENCY_HIGH")
    for w in schema.get("manifestWarnings", []):
        warnings.append(f"SCHEMA_{w['issue']}:{w['table']}")

    return {
        "ok": len(failures) == 0,
        "failures": failures,
        "warnings": warnings,
        "latencyMs": sink_reachability.get("latencyMs", 0),
        "checks": {
            "sinkReadiness": sink,
            "schemaContract": schema,
            "sinkReachability": sink_reachability,
            "kafkaReachability": kafka_reachability,
            "runtimeReachability": runtime_reachability,
        },
    }
