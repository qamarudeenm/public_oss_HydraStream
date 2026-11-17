"""dbt artifact parsing helpers for inventory and lineage extraction."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ArtifactSummary:
    """Parsed dbt artifact summary."""

    metadata: dict[str, Any]
    inventory: list[dict[str, Any]]
    lineage: list[dict[str, str]]


class ArtifactParseError(ValueError):
    """Raised when dbt artifacts cannot be loaded or parsed."""


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ArtifactParseError(f"Missing artifact file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ArtifactParseError(f"Invalid JSON in artifact file: {path}") from exc


def parse_artifact_summary(artifact_dir: str | Path) -> ArtifactSummary:
    """Parse dbt manifest + run results into inventory/lineage summary."""
    base_dir = Path(artifact_dir)
    manifest = _load_json(base_dir / "manifest.json")
    run_results = _load_json(base_dir / "run_results.json")

    results_by_unique_id: dict[str, dict[str, Any]] = {}
    for result in run_results.get("results", []):
        unique_id = result.get("unique_id")
        if isinstance(unique_id, str):
            results_by_unique_id[unique_id] = result

    inventory: list[dict[str, Any]] = []
    lineage: list[dict[str, str]] = []

    nodes = manifest.get("nodes", {})
    for unique_id, node in nodes.items():
        if not isinstance(node, dict):
            continue
        if node.get("resource_type") != "model":
            continue

        run_info = results_by_unique_id.get(unique_id, {})
        depends_on_nodes = node.get("depends_on", {}).get("nodes", [])
        model_deps = [
            dep
            for dep in depends_on_nodes
            if isinstance(dep, str) and dep.startswith("model.")
        ]

        inventory.append(
            {
                "unique_id": unique_id,
                "name": node.get("name"),
                "package_name": node.get("package_name"),
                "database": node.get("database"),
                "schema": node.get("schema"),
                "alias": node.get("alias"),
                "materialized": node.get("config", {}).get("materialized"),
                "relation_name": node.get("relation_name"),
                "depends_on": model_deps,
                "status": run_info.get("status"),
                "message": run_info.get("message"),
                "execution_time": run_info.get("execution_time"),
            }
        )

        for dep in model_deps:
            lineage.append({"upstream": dep, "downstream": unique_id})

    metadata = {
        "manifest_generated_at": manifest.get("metadata", {}).get("generated_at"),
        "run_results_generated_at": run_results.get("metadata", {}).get("generated_at"),
        "dbt_version": manifest.get("metadata", {}).get("dbt_version")
        or run_results.get("metadata", {}).get("dbt_version"),
        "inventory_count": len(inventory),
        "lineage_edge_count": len(lineage),
    }

    return ArtifactSummary(metadata=metadata, inventory=inventory, lineage=lineage)
