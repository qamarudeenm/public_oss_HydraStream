"""Unit tests for dbt artifact summary route."""

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from flink_gateway_proxy.routes import dbt_artifacts


def _write_artifacts(base_dir):
    manifest = {
        "metadata": {"dbt_version": "1.11.7", "generated_at": "2026-05-01T00:00:00Z"},
        "nodes": {
            "model.demo.a": {
                "resource_type": "model",
                "name": "a",
                "package_name": "demo",
                "database": "default_catalog",
                "schema": "default_database",
                "alias": "a",
                "config": {"materialized": "table"},
                "depends_on": {"nodes": []},
            },
            "model.demo.b": {
                "resource_type": "model",
                "name": "b",
                "package_name": "demo",
                "database": "default_catalog",
                "schema": "default_database",
                "alias": "b",
                "config": {"materialized": "streaming_table"},
                "depends_on": {"nodes": ["model.demo.a"]},
            },
        },
    }
    run_results = {
        "metadata": {"generated_at": "2026-05-01T00:05:00Z", "dbt_version": "1.11.7"},
        "results": [
            {
                "unique_id": "model.demo.a",
                "status": "success",
                "message": "ok",
                "execution_time": 0.1,
            },
            {
                "unique_id": "model.demo.b",
                "status": "success",
                "message": "ok",
                "execution_time": 0.2,
            },
        ],
    }
    (base_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (base_dir / "run_results.json").write_text(json.dumps(run_results), encoding="utf-8")


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(dbt_artifacts.router)
    return app


def test_summary_route_returns_inventory(tmp_path):
    _write_artifacts(tmp_path)
    dbt_artifacts.set_artifact_config(default_artifact_dir=str(tmp_path), tenant_artifact_map={})

    client = TestClient(_build_app())
    response = client.get("/runtime/v1/tenants/tenant-a/dbt/artifacts/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant-a"
    assert body["metadata"]["inventory_count"] == 2
    assert body["metadata"]["lineage_edge_count"] == 1


def test_summary_route_requires_config():
    dbt_artifacts.set_artifact_config(default_artifact_dir="", tenant_artifact_map={})

    client = TestClient(_build_app())
    response = client.get("/runtime/v1/tenants/tenant-a/dbt/artifacts/summary")

    assert response.status_code == 404
