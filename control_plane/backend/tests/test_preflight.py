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

"""Unit tests for the preflight module.

All network calls are patched so the test suite runs offline.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from app.models import KafkaConfig, SinkConfig, Tenant
from app.preflight import (
    _check_kafka_reachability,
    _check_reachability,
    _check_runtime_reachability,
    _check_schema_contract,
    _check_sink_readiness,
    _extract_host_port,
    _load_manifest_model_columns,
    run_preflight,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_tenant(**overrides) -> Tenant:
    kwargs = dict(id="test-tenant", name="Test Tenant")
    kwargs.update(overrides)
    return Tenant(**kwargs)


# ---------------------------------------------------------------------------
# _extract_host_port
# ---------------------------------------------------------------------------

def test_extract_host_port_standard():
    host, port = _extract_host_port("jdbc:mysql://db.example.com:3306/mydb")
    assert host == "db.example.com"
    assert port == 3306


def test_extract_host_port_empty():
    host, port = _extract_host_port("")
    assert host is None
    assert port is None


def test_extract_host_port_missing_port():
    host, port = _extract_host_port("jdbc:mysql://db.example.com/mydb")
    assert host == "db.example.com"
    assert port is None


# ---------------------------------------------------------------------------
# _check_sink_readiness
# ---------------------------------------------------------------------------

def test_sink_readiness_all_present():
    tenant = make_tenant()
    result = _check_sink_readiness(tenant)
    assert result["ok"] is True
    assert all(result["details"].values())


def test_sink_readiness_missing_jdbc():
    tenant = make_tenant(sink=SinkConfig(jdbc_url="", user="u", summary_table="t1", metrics_table="t2"))
    result = _check_sink_readiness(tenant)
    assert result["ok"] is False
    assert result["details"]["jdbc_url"] is False


def test_sink_readiness_missing_tables():
    tenant = make_tenant(
        sink=SinkConfig(
            jdbc_url="jdbc:mysql://db:3306/db",
            user="u",
            summary_table="",
            metrics_table="metrics",
        )
    )
    result = _check_sink_readiness(tenant)
    assert result["ok"] is False
    assert result["details"]["summary_table"] is False


# ---------------------------------------------------------------------------
# _load_manifest_model_columns
# ---------------------------------------------------------------------------

def test_load_manifest_model_columns_success(tmp_path):
    manifest = {
        "nodes": {
            "model.pkg.my_model": {
                "resource_type": "model",
                "name": "my_model",
                "columns": {
                    "col_a": {"data_type": "STRING"},
                    "col_b": {"data_type": "BIGINT"},
                },
            }
        }
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    result = _load_manifest_model_columns(str(tmp_path))
    assert result == {"my_model": {"col_a", "col_b"}}


def test_load_manifest_model_columns_missing_file(tmp_path):
    result = _load_manifest_model_columns(str(tmp_path))
    assert result == {}


def test_load_manifest_model_columns_invalid_json(tmp_path):
    (tmp_path / "manifest.json").write_text("not json {{{")
    result = _load_manifest_model_columns(str(tmp_path))
    assert result == {}


# ---------------------------------------------------------------------------
# _check_schema_contract
# ---------------------------------------------------------------------------

FULL_METRICS_MANIFEST = {
    "nodes": {
        "model.clickstream.transformed_clickstream_metrics": {
            "resource_type": "model",
            "name": "transformed_clickstream_metrics",
            "columns": {c: {} for c in [
                "user_id", "session_id", "event_type",
                "event_count", "window_start", "window_end",
            ]},
        },
        "model.clickstream.clickstream_summary": {
            "resource_type": "model",
            "name": "clickstream_summary",
            "columns": {},
        },
    }
}


def test_schema_contract_passes_with_valid_manifest(tmp_path, monkeypatch):
    (tmp_path / "manifest.json").write_text(json.dumps(FULL_METRICS_MANIFEST))
    monkeypatch.setenv("HYDRA_DBT_ARTIFACT_DIR", str(tmp_path))
    tenant = make_tenant()
    result = _check_schema_contract(tenant)
    assert result["ok"] is True
    assert result["modelMismatches"] == []
    assert result["manifestAvailable"] is True


def test_schema_contract_fails_missing_columns(tmp_path, monkeypatch):
    # Manifest has metrics model but is missing required columns
    manifest = {
        "nodes": {
            "model.clickstream.transformed_clickstream_metrics": {
                "resource_type": "model",
                "name": "transformed_clickstream_metrics",
                "columns": {"user_id": {}, "event_type": {}},  # missing session_id, etc.
            },
            "model.clickstream.clickstream_summary": {
                "resource_type": "model",
                "name": "clickstream_summary",
                "columns": {},
            },
        }
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setenv("HYDRA_DBT_ARTIFACT_DIR", str(tmp_path))
    tenant = make_tenant()
    result = _check_schema_contract(tenant)
    assert result["ok"] is False
    assert len(result["modelMismatches"]) == 1
    mismatch = result["modelMismatches"][0]
    assert mismatch["issue"] == "MISSING_REQUIRED_COLUMNS"
    assert "session_id" in mismatch["missingColumns"]


def test_schema_contract_warns_table_not_in_manifest(tmp_path, monkeypatch):
    # Only metrics model in manifest — summary table is absent
    manifest = {
        "nodes": {
            "model.clickstream.transformed_clickstream_metrics": {
                "resource_type": "model",
                "name": "transformed_clickstream_metrics",
                "columns": {c: {} for c in [
                    "user_id", "session_id", "event_type",
                    "event_count", "window_start", "window_end",
                ]},
            }
        }
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setenv("HYDRA_DBT_ARTIFACT_DIR", str(tmp_path))
    tenant = make_tenant()
    result = _check_schema_contract(tenant)
    # ok is still True — missing from manifest is a warning, not a failure
    assert result["ok"] is True
    assert any(w["issue"] == "NOT_IN_MANIFEST" for w in result["manifestWarnings"])


def test_schema_contract_fails_missing_table_names():
    tenant = make_tenant(
        sink=SinkConfig(
            jdbc_url="jdbc:mysql://db:3306/db",
            user="u",
            summary_table="",
            metrics_table="metrics",
        )
    )
    result = _check_schema_contract(tenant)
    assert result["ok"] is False
    assert "" in result["missingTables"]


def test_schema_contract_no_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv("HYDRA_DBT_ARTIFACT_DIR", str(tmp_path))
    tenant = make_tenant()
    result = _check_schema_contract(tenant)
    # Passes gracefully when manifest is absent
    assert result["ok"] is True
    assert result["manifestAvailable"] is False


# ---------------------------------------------------------------------------
# _check_reachability (sink TCP)
# ---------------------------------------------------------------------------

@patch("app.preflight.socket.create_connection")
def test_check_reachability_success(mock_conn):
    mock_conn.return_value.__enter__ = MagicMock(return_value=None)
    mock_conn.return_value.__exit__ = MagicMock(return_value=False)
    tenant = make_tenant()
    result = _check_reachability(tenant)
    assert result["ok"] is True
    assert result["host"] == "host.docker.internal"
    assert result["port"] == 9004


@patch("app.preflight.socket.create_connection", side_effect=OSError("refused"))
def test_check_reachability_failure(mock_conn):
    tenant = make_tenant()
    result = _check_reachability(tenant)
    assert result["ok"] is False
    assert "OSError" in result["error"]


def test_check_reachability_bad_jdbc():
    tenant = make_tenant(sink=SinkConfig(jdbc_url="", user="u", summary_table="t", metrics_table="m"))
    result = _check_reachability(tenant)
    assert result["ok"] is False
    assert result["error"] == "JDBC_URL_PARSE_FAILED"


# ---------------------------------------------------------------------------
# _check_kafka_reachability
# ---------------------------------------------------------------------------

@patch("app.preflight.socket.create_connection")
def test_kafka_reachability_success(mock_conn):
    mock_conn.return_value.__enter__ = MagicMock(return_value=None)
    mock_conn.return_value.__exit__ = MagicMock(return_value=False)
    tenant = make_tenant()
    result = _check_kafka_reachability(tenant)
    assert result["ok"] is True
    assert result["host"] == "kafka"
    assert result["port"] == 29092


@patch("app.preflight.socket.create_connection", side_effect=OSError("connection refused"))
def test_kafka_reachability_failure(mock_conn):
    tenant = make_tenant()
    result = _check_kafka_reachability(tenant)
    assert result["ok"] is False


def test_kafka_reachability_bad_bootstrap():
    tenant = make_tenant(kafka=KafkaConfig(bootstrap_servers="kafka-no-port"))
    result = _check_kafka_reachability(tenant)
    assert result["ok"] is False
    assert result["error"] == "KAFKA_BOOTSTRAP_PARSE_FAILED"


def test_kafka_reachability_multiple_brokers():
    """Only the first broker in the list is probed."""
    with patch("app.preflight.socket.create_connection") as mock_conn:
        mock_conn.return_value.__enter__ = MagicMock(return_value=None)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        tenant = make_tenant(
            kafka=KafkaConfig(bootstrap_servers="broker1:9092,broker2:9092,broker3:9092")
        )
        result = _check_kafka_reachability(tenant)
        assert result["ok"] is True
        called_host = mock_conn.call_args[0][0][0]
        assert called_host == "broker1"


# ---------------------------------------------------------------------------
# _check_runtime_reachability
# ---------------------------------------------------------------------------

@patch("app.preflight.socket.create_connection")
def test_runtime_reachability_all_up(mock_conn, monkeypatch):
    mock_conn.return_value.__enter__ = MagicMock(return_value=None)
    mock_conn.return_value.__exit__ = MagicMock(return_value=False)
    monkeypatch.setenv("HYDRA_RUNTIME_HOST_TEMPLATE", "runtime-host")
    monkeypatch.setenv("HYDRA_FLINK_GATEWAY_HOST_TEMPLATE", "flink-host")
    monkeypatch.setenv("DBT_CLOUD_HOST", "cloud.getdbt.com")
    tenant = make_tenant()
    result = _check_runtime_reachability(tenant)
    assert result["ok"] is True
    assert result["checks"]["controlPlaneToTenantRuntime"]["ok"] is True
    assert result["checks"]["controlPlaneToFlinkGateway"]["ok"] is True
    assert result["checks"]["controlPlaneToDbtCloud"]["ok"] is True


@patch("app.preflight.socket.create_connection", side_effect=OSError("unreachable"))
def test_runtime_reachability_all_down(mock_conn):
    tenant = make_tenant()
    result = _check_runtime_reachability(tenant)
    assert result["ok"] is False
    checks = result["checks"]
    assert checks["controlPlaneToTenantRuntime"]["ok"] is False
    assert checks["controlPlaneToFlinkGateway"]["ok"] is False
    assert checks["controlPlaneToDbtCloud"]["ok"] is False


# ---------------------------------------------------------------------------
# run_preflight (integration)
# ---------------------------------------------------------------------------

@patch("app.preflight.socket.create_connection")
def test_run_preflight_all_ok(mock_conn, tmp_path, monkeypatch):
    mock_conn.return_value.__enter__ = MagicMock(return_value=None)
    mock_conn.return_value.__exit__ = MagicMock(return_value=False)
    (tmp_path / "manifest.json").write_text(json.dumps(FULL_METRICS_MANIFEST))
    monkeypatch.setenv("HYDRA_DBT_ARTIFACT_DIR", str(tmp_path))
    tenant = make_tenant()
    result = run_preflight(tenant)
    assert result["ok"] is True
    assert result["failures"] == []
    assert "sinkReadiness" in result["checks"]
    assert "schemaContract" in result["checks"]
    assert "sinkReachability" in result["checks"]
    assert "kafkaReachability" in result["checks"]
    assert "runtimeReachability" in result["checks"]


@patch("app.preflight.socket.create_connection", side_effect=OSError("refused"))
def test_run_preflight_network_failures(mock_conn, tmp_path, monkeypatch):
    (tmp_path / "manifest.json").write_text(json.dumps(FULL_METRICS_MANIFEST))
    monkeypatch.setenv("HYDRA_DBT_ARTIFACT_DIR", str(tmp_path))
    tenant = make_tenant()
    result = run_preflight(tenant)
    assert result["ok"] is False
    assert "SINK_UNREACHABLE" in result["failures"]
    assert "KAFKA_UNREACHABLE" in result["failures"]
    assert "RUNTIME_LINK_UNREACHABLE" in result["failures"]


@patch("app.preflight.socket.create_connection")
def test_run_preflight_schema_failure_in_failures(mock_conn, tmp_path, monkeypatch):
    mock_conn.return_value.__enter__ = MagicMock(return_value=None)
    mock_conn.return_value.__exit__ = MagicMock(return_value=False)
    # Manifest missing required columns
    manifest = {
        "nodes": {
            "model.clickstream.transformed_clickstream_metrics": {
                "resource_type": "model",
                "name": "transformed_clickstream_metrics",
                "columns": {"user_id": {}},
            },
            "model.clickstream.clickstream_summary": {
                "resource_type": "model",
                "name": "clickstream_summary",
                "columns": {},
            },
        }
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setenv("HYDRA_DBT_ARTIFACT_DIR", str(tmp_path))
    tenant = make_tenant()
    result = run_preflight(tenant)
    assert result["ok"] is False
    assert "SCHEMA_CONTRACT_INVALID" in result["failures"]
