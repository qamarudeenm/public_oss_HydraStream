"""Traits inference for statements."""

import re
from typing import Any

from ..models.confluent import ColumnTypeDefinition, SchemaColumn, StatementSchema
from ..models.flink import FetchResultsResponse


def infer_sql_kind(sql: str) -> str:
    """Infer SQL kind from statement text.

    Args:
        sql: SQL statement text

    Returns:
        SQL kind (e.g., SELECT, CREATE_TABLE, DROP_TABLE, SHOW, etc.)
    """
    sql_upper = sql.strip().upper()

    # DDL statements
    if sql_upper.startswith("CREATE TABLE"):
        return "CREATE_TABLE"
    elif sql_upper.startswith("CREATE VIEW") or sql_upper.startswith("CREATE MATERIALIZED VIEW"):
        return "CREATE_VIEW"
    elif sql_upper.startswith("DROP TABLE"):
        return "DROP_TABLE"
    elif sql_upper.startswith("DROP VIEW"):
        return "DROP_VIEW"
    elif sql_upper.startswith("ALTER TABLE"):
        return "ALTER_TABLE"
    elif sql_upper.startswith("CREATE DATABASE") or sql_upper.startswith("CREATE CATALOG"):
        return "CREATE_DATABASE"
    elif sql_upper.startswith("DROP DATABASE") or sql_upper.startswith("DROP CATALOG"):
        return "DROP_DATABASE"
    # DML statements
    elif sql_upper.startswith("SELECT"):
        return "SELECT"
    elif sql_upper.startswith("INSERT"):
        return "INSERT"
    elif sql_upper.startswith("UPDATE"):
        return "UPDATE"
    elif sql_upper.startswith("DELETE"):
        return "DELETE"
    # Utility statements
    elif sql_upper.startswith("SHOW"):
        return "SHOW"
    elif sql_upper.startswith("DESCRIBE") or sql_upper.startswith("DESC"):
        return "DESCRIBE"
    elif sql_upper.startswith("EXPLAIN"):
        return "EXPLAIN"
    elif sql_upper.startswith("USE"):
        return "USE"
    elif sql_upper.startswith("SET"):
        return "SET"
    elif sql_upper.startswith("RESET"):
        return "RESET"
    else:
        return "OTHER"


def infer_is_bounded(properties: dict[str, str], sql_kind: str) -> bool:
    """Infer if statement is bounded (has finite result set).

    Args:
        properties: Statement properties
        sql_kind: SQL kind

    Returns:
        True if bounded, False otherwise
    """
    # Check if snapshot mode is explicitly set
    snapshot_mode = properties.get("sql.snapshot.mode")
    if snapshot_mode == "now":
        return True

    # DDL statements are typically bounded (they complete)
    if sql_kind in {
        "CREATE_TABLE",
        "CREATE_VIEW",
        "DROP_TABLE",
        "DROP_VIEW",
        "ALTER_TABLE",
        "CREATE_DATABASE",
        "DROP_DATABASE",
        "INSERT",
        "UPDATE",
        "DELETE",
        "USE",
        "SET",
        "RESET",
    }:
        return True

    # SHOW and DESCRIBE are bounded
    if sql_kind in {"SHOW", "DESCRIBE", "EXPLAIN"}:
        return True

    # SELECT is unbounded unless in snapshot mode
    return False


def infer_is_append_only(sql_kind: str, is_bounded: bool) -> bool:
    """Infer if statement results are append-only.

    Args:
        sql_kind: SQL kind
        is_bounded: Whether statement is bounded

    Returns:
        True if append-only, False otherwise
    """
    # Bounded queries are always append-only
    if is_bounded:
        return True

    # Streaming SELECTs without aggregations/joins could be append-only,
    # but we conservatively assume non-append-only for streaming queries
    # unless we have more information
    if sql_kind == "SELECT":
        # Check if query has GROUP BY, JOIN, or window functions (conservative check)
        # For now, assume streaming SELECTs are NOT append-only
        return False

    # DDL/DML are append-only
    return True


def flink_type_to_confluent(flink_type: dict[str, Any]) -> ColumnTypeDefinition:
    """Convert Flink logical type to Confluent column type definition.

    Args:
        flink_type: Flink logical type dictionary

    Returns:
        Confluent column type definition
    """
    type_name = flink_type.get("type", "").upper()

    # Map Flink types to Confluent types
    type_mapping = {
        "CHAR": "CHAR",
        "VARCHAR": "VARCHAR",
        "STRING": "STRING",
        "BOOLEAN": "BOOLEAN",
        "BINARY": "BINARY",
        "VARBINARY": "VARBINARY",
        "BYTES": "BYTES",
        "DECIMAL": "DECIMAL",
        "TINYINT": "TINYINT",
        "SMALLINT": "SMALLINT",
        "INTEGER": "INT",
        "INT": "INT",
        "BIGINT": "BIGINT",
        "FLOAT": "FLOAT",
        "DOUBLE": "DOUBLE",
        "DATE": "DATE",
        "TIME": "TIME",
        "TIMESTAMP": "TIMESTAMP",
        "TIMESTAMP_LTZ": "TIMESTAMP_LTZ",
        "INTERVAL": "INTERVAL",
        "ARRAY": "ARRAY",
        "MULTISET": "MULTISET",
        "MAP": "MAP",
        "ROW": "ROW",
        "RAW": "RAW",
    }

    confluent_type = type_mapping.get(type_name, type_name)

    column_type = ColumnTypeDefinition(
        type=confluent_type,
        nullable=flink_type.get("nullable", True),
        precision=flink_type.get("precision"),
        scale=flink_type.get("scale"),
    )

    # Handle complex types
    if confluent_type == "ARRAY" and "elementType" in flink_type:
        column_type.element_type = flink_type_to_confluent(flink_type["elementType"])
    elif confluent_type == "MAP":
        if "keyType" in flink_type:
            column_type.key_type = flink_type_to_confluent(flink_type["keyType"])
        if "valueType" in flink_type:
            column_type.value_type = flink_type_to_confluent(flink_type["valueType"])
    elif confluent_type == "ROW" and "fields" in flink_type:
        column_type.fields = [
            flink_type_to_confluent(field) for field in flink_type["fields"]
        ]

    return column_type


def extract_schema_from_results(
    result_response: FetchResultsResponse,
) -> StatementSchema | None:
    """Extract schema from Flink results response.

    Args:
        result_response: Flink fetch results response

    Returns:
        Statement schema or None if no schema available
    """
    results = result_response.results

    # Check if this is a query result with schema
    if not results.is_query_result:
        return None

    # Flink SQL Gateway returns schema in result metadata
    # For now, we'll infer from the first data row structure
    # In practice, Flink Gateway should provide schema metadata

    # TODO: Extract actual schema from Flink response metadata
    # For now, return None and we'll extract lazily when needed
    return None
