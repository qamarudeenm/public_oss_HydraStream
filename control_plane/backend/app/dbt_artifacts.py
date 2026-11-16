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

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ArtifactLoadError(Exception):
    """Raised when dbt artifact files cannot be loaded."""


def _safe_parse_relation_name(relation_name: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if not relation_name:
        return None, None, None

    cleaned = relation_name.replace("`", "").replace('"', "")
    parts = [part for part in cleaned.split(".") if part]
    if len(parts) >= 3:
        return parts[-3], parts[-2], parts[-1]
    if len(parts) == 2:
        return None, parts[0], parts[1]
    if len(parts) == 1:
        return None, None, parts[0]
    return None, None, None


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ArtifactLoadError(f"Artifact file not found: {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ArtifactLoadError(f"Invalid JSON in artifact file {path}: {exc}") from exc


def extract_inventory_and_lineage(manifest: Dict[str, Any], run_results: Dict[str, Any]) -> Dict[str, Any]:
    nodes = manifest.get("nodes", {})
    run_results_by_id = {
        result.get("unique_id"): result
        for result in run_results.get("results", [])
        if result.get("unique_id")
    }

    models: List[Dict[str, Any]] = []
    edges: List[Dict[str, str]] = []
    model_ids = {uid for uid, node in nodes.items() if node.get("resource_type") == "model"}

    for unique_id, node in nodes.items():
        if node.get("resource_type") != "model":
            continue

        run_result = run_results_by_id.get(unique_id, {})
        relation_name = node.get("relation_name")
        db_name, schema_name, relation = _safe_parse_relation_name(relation_name)
        depends_on = node.get("depends_on", {}).get("nodes", [])

        models.append(
            {
                "unique_id": unique_id,
                "name": node.get("name"),
                "package_name": node.get("package_name"),
                "database": node.get("database") or db_name,
                "schema": node.get("schema") or schema_name,
                "relation": node.get("alias") or relation,
                "relation_name": relation_name,
                "materialized": node.get("config", {}).get("materialized"),
                "path": node.get("path"),
                "depends_on": depends_on,
                "status": run_result.get("status"),
                "execution_time": run_result.get("execution_time"),
                "message": run_result.get("message"),
            }
        )

        for upstream_id in depends_on:
            if upstream_id in model_ids:
                edges.append({"from": upstream_id, "to": unique_id})

    return {
        "inventory": {
            "model_count": len(models),
            "models": models,
        },
        "lineage": {
            "edge_count": len(edges),
            "edges": edges,
        },
        "metadata": {
            "manifest_generated_at": manifest.get("metadata", {}).get("generated_at"),
            "dbt_version": manifest.get("metadata", {}).get("dbt_version"),
            "run_generated_at": run_results.get("metadata", {}).get("generated_at"),
        },
    }


def load_dbt_artifacts(artifact_dir: str) -> Dict[str, Any]:
    base = Path(artifact_dir)
    manifest = _load_json(base / "manifest.json")
    run_results = _load_json(base / "run_results.json")
    return extract_inventory_and_lineage(manifest, run_results)
