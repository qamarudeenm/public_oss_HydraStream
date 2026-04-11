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

"""Apache Flink SQL Gateway REST API models."""

from typing import Any

from pydantic import BaseModel, Field


class OpenSessionRequest(BaseModel):
    """Request to open a new session."""

    session_name: str | None = Field(default=None, alias="sessionName")
    properties: dict[str, str] = Field(default_factory=dict)


class OpenSessionResponse(BaseModel):
    """Response from opening a session."""

    session_handle: str = Field(alias="sessionHandle")


class ExecuteStatementRequest(BaseModel):
    """Request to execute a statement."""

    statement: str
    execution_timeout: int | None = Field(default=None, alias="executionTimeout")
    execution_config: dict[str, str] | None = Field(default=None, alias="executionConfig")


class ExecuteStatementResponse(BaseModel):
    """Response from executing a statement."""

    operation_handle: str = Field(alias="operationHandle")


class OperationStatus(BaseModel):
    """Status of an operation."""

    status: str  # INITIALIZED, PENDING, RUNNING, FINISHED, CANCELED, CLOSED, ERROR


class FetchResultsRequest(BaseModel):
    """Request to fetch results."""

    token: int = 0
    max_rows: int | None = Field(default=None, alias="maxRows")


class ColumnInfo(BaseModel):
    """Column information."""

    name: str
    logical_type: dict[str, Any] = Field(alias="logicalType")
    comment: str | None = None


class ResultSchema(BaseModel):
    """Result schema."""

    columns: list[ColumnInfo] = Field(default_factory=list)


class RowData(BaseModel):
    """Row data with optional changelog operation."""

    kind: str  # INSERT, UPDATE_BEFORE, UPDATE_AFTER, DELETE
    fields: list[Any]


class ResultSet(BaseModel):
    """Result set data."""

    result_type: str = Field(alias="resultType")  # PAYLOAD, EOS (end of stream)
    data: list[RowData] | None = None
    row_format: str | None = Field(default=None, alias="rowFormat")
    next_result_uri: str | None = Field(default=None, alias="nextResultUri")
    is_query_result: bool | None = Field(default=None, alias="isQueryResult")
    result_kind: str | None = Field(default=None, alias="resultKind")


class FetchResultsResponse(BaseModel):
    """Response from fetching results."""

    results: ResultSet
    result_type: str = Field(alias="resultType")
    next_result_uri: str | None = Field(default=None, alias="nextResultUri")


class GetOperationStatusResponse(BaseModel):
    """Response from getting operation status."""

    status: str  # INITIALIZED, PENDING, RUNNING, FINISHED, CANCELED, CLOSED, ERROR
