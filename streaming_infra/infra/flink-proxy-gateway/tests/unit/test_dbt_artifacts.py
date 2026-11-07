"""Unit tests for dbt artifact parsing."""

import json

from flink_gateway_proxy.dbt_artifacts import parse_artifact_summary


def test_parse_artifact_summary_extracts_inventory_and_lineage(tmp_path):
    """Parser should extract model inventory and lineage edges."""
    manifest = {
        "metadata": {"dbt_version": "1.11.7", "generated_at": "2026-05-01T00:00:00Z"},
        "nodes": {
            "model.demo.source_model": {
                "resource_type": "model",
                "name": "source_model",
                "package_name": "demo",
                "database": "default_catalog",
                "schema": "default_database",
                "alias": "source_model",
                "relation_name": "`default_catalog`.`default_database`.`source_model`",
                "config": {"materialized": "table"},
                "depends_on": {"nodes": []},
            },
            "model.demo.sink_model": {
                "resource_type": "model",
                "name": "sink_model",
                "package_name": "demo",
                "database": "default_catalog",
                "schema": "default_database",
                "alias": "sink_model",
                "relation_name": "`default_catalog`.`default_database`.`sink_model`",
                "config": {"materialized": "streaming_table"},
                "depends_on": {"nodes": ["model.demo.source_model"]},
            },
        },
    }

    run_results = {
        "metadata": {"generated_at": "2026-05-01T00:05:00Z", "dbt_version": "1.11.7"},
        "results": [
            {
                "unique_id": "model.demo.source_model",
                "status": "success",
                "message": "ok",
                "execution_time": 0.2,
            },
            {
                "unique_id": "model.demo.sink_model",
                "status": "success",
                "message": "ok",
                "execution_time": 0.3,
            },
        ],
    }

    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "run_results.json").write_text(json.dumps(run_results), encoding="utf-8")

    summary = parse_artifact_summary(tmp_path)

    assert summary.metadata["inventory_count"] == 2
    assert summary.metadata["lineage_edge_count"] == 1
    assert len(summary.inventory) == 2
    assert len(summary.lineage) == 1
    assert summary.lineage[0]["upstream"] == "model.demo.source_model"
    assert summary.lineage[0]["downstream"] == "model.demo.sink_model"
