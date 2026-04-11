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

"""Confluent Cloud Flink SQL API models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StatementCreateRequest(BaseModel):
    """Request to create a new statement."""

    name: str
    organization_id: str
    environment_id: str
    spec: "StatementSpec"
    metadata: "StatementMetadata | None" = None


class StatementSpec(BaseModel):
    """Statement specification."""

    statement: str
    properties: dict[str, str] = Field(default_factory=dict)
    compute_pool_id: str
    stopped: bool = False
    principal: str | None = None
    execution_mode: str | None = None


class StatementMetadata(BaseModel):
    """Statement metadata."""

    uid: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    self: str | None = Field(default=None, alias="self")
    resource_version: str | None = None


class ColumnTypeDefinition(BaseModel):
    """Column type definition."""

    type: str
    nullable: bool = True
    precision: int | None = None
    scale: int | None = None
    # NOTE: default_factory=list is a critical fix for dbt-confluent compatibility.
    # The adapter's client code (confluent_sql) expects an iterable 'fields' list; 
    # returning null/None causes a 'NoneType' object is not iterable error.
    fields: list["ColumnTypeDefinition"] = Field(default_factory=list)
    element_type: "ColumnTypeDefinition | None" = None
    key_type: "ColumnTypeDefinition | None" = None
    value_type: "ColumnTypeDefinition | None" = None


class SchemaColumn(BaseModel):
    """Schema column definition."""

    name: str
    type: ColumnTypeDefinition
    description: str | None = None


class StatementSchema(BaseModel):
    """Statement result schema."""

    columns: list[SchemaColumn] = Field(default_factory=list)


class StatementTraits(BaseModel):
    """Statement traits."""

    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    connection_refs: list[str] | None = None
    is_append_only: bool = True
    is_bounded: bool = True
    result_schema: StatementSchema | None = Field(default=None, alias="schema")
    sql_kind: str = "SELECT"
    upsert_columns: list[int] | None = None


class ScalingStatus(BaseModel):
    """Scaling status."""

    scaling_state: str = "OK"
    last_updated: datetime | None = None


class StatementStatus(BaseModel):
    """Statement status."""

    phase: str
    detail: str = ""
    traits: StatementTraits | None = None
    network_kind: str = "PUBLIC"
    scaling_status: ScalingStatus | None = None


class StatementResponse(BaseModel):
    """Full statement response."""

    api_version: str = "sql/v1"
    kind: str = "Statement"
    name: str
    organization_id: str
    environment_id: str
    metadata: StatementMetadata
    spec: StatementSpec
    status: StatementStatus


class StatementListResponse(BaseModel):
    """Response from listing statements."""

    api_version: str = "sql/v1"
    kind: str = "StatementList"
    metadata: dict[str, Any] = Field(default_factory=dict)
    data: list[StatementResponse] = Field(default_factory=list)


class ChangelogRow(BaseModel):
    """A single row with optional changelog operation."""

    op: int = 0  # 0=INSERT, 1=UPDATE_BEFORE, 2=UPDATE_AFTER, 3=DELETE
    row: list[Any]


class ResultsMetadata(BaseModel):
    """Metadata for results pagination."""

    next: str | None = None


class StatementResults(BaseModel):
    """Statement results data."""

    data: list[ChangelogRow] = Field(default_factory=list)


class StatementResultsResponse(BaseModel):
    """Response from fetching statement results."""

    results: StatementResults
    metadata: ResultsMetadata
