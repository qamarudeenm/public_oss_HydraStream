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

"""Async HTTP client for Flink SQL Gateway REST API."""

import asyncio
import logging
from typing import Any

import httpx

from ..models.flink import (
    ExecuteStatementRequest,
    ExecuteStatementResponse,
    FetchResultsResponse,
    GetOperationStatusResponse,
    OpenSessionRequest,
    OpenSessionResponse,
)

logger = logging.getLogger(__name__)


class FlinkGatewayClient:
    """Async client for Flink SQL Gateway REST API."""

    def __init__(self, base_url: str):
        """Initialize the gateway client.

        Args:
            base_url: Base URL of the Flink SQL Gateway (e.g., http://localhost:8083)
        """
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0, connect=5.0),
            headers={"Content-Type": "application/json"},
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def open_session(
        self, session_name: str | None = None, properties: dict[str, str] | None = None
    ) -> str:
        """Open a new session.

        Args:
            session_name: Optional session name
            properties: Session properties (e.g., catalog, database)

        Returns:
            Session handle
        """
        request = OpenSessionRequest(
            session_name=session_name, properties=properties or {}
        )
        response = await self.client.post(
            "/v1/sessions", json=request.model_dump(by_alias=True, exclude_none=True)
        )
        response.raise_for_status()
        data = response.json()
        session_response = OpenSessionResponse.model_validate(data)
        logger.info(f"Opened session: {session_response.session_handle}")
        return session_response.session_handle

    async def close_session(self, session_handle: str) -> None:
        """Close a session.

        Args:
            session_handle: Session handle to close
        """
        response = await self.client.delete(f"/v1/sessions/{session_handle}")
        response.raise_for_status()
        logger.info(f"Closed session: {session_handle}")

    async def heartbeat(self, session_handle: str) -> None:
        """Send a heartbeat to keep session alive.

        Args:
            session_handle: Session handle
        """
        response = await self.client.post(f"/v1/sessions/{session_handle}/heartbeat")
        response.raise_for_status()
        logger.debug(f"Sent heartbeat for session: {session_handle}")

    async def execute_statement(
        self, session_handle: str, sql: str, execution_config: dict[str, str] | None = None
    ) -> str:
        """Execute a SQL statement.

        Args:
            session_handle: Session handle
            sql: SQL statement to execute
            execution_config: Execution configuration properties

        Returns:
            Operation handle
        """
        request = ExecuteStatementRequest(
            statement=sql, execution_config=execution_config
        )
        response = await self.client.post(
            f"/v1/sessions/{session_handle}/statements",
            json=request.model_dump(by_alias=True, exclude_none=True),
        )
        response.raise_for_status()
        data = response.json()
        exec_response = ExecuteStatementResponse.model_validate(data)
        logger.info(
            f"Executed statement in session {session_handle}: {exec_response.operation_handle}"
        )
        return exec_response.operation_handle

    async def wait_for_operation(
        self,
        session_handle: str,
        operation_handle: str,
        timeout: float = 60.0,
        interval: float = 0.5,
    ) -> str:
        """Wait for an operation to complete.

        Args:
            session_handle: Session handle
            operation_handle: Operation handle
            timeout: Maximum time to wait in seconds
            interval: Polling interval in seconds

        Returns:
            Final status (e.g., FINISHED, ERROR)
        """
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            status_resp = await self.get_operation_status(session_handle, operation_handle)
            status = status_resp.status
            if status in {"FINISHED", "ERROR", "CANCELED"}:
                return status
            await asyncio.sleep(interval)
        return "TIMEOUT"

    async def get_operation_status(
        self, session_handle: str, operation_handle: str
    ) -> GetOperationStatusResponse:
        """Get the status of an operation.

        Args:
            session_handle: Session handle
            operation_handle: Operation handle

        Returns:
            Operation status response
        """
        response = await self.client.get(
            f"/v1/sessions/{session_handle}/operations/{operation_handle}/status"
        )
        response.raise_for_status()
        data = response.json()
        return GetOperationStatusResponse.model_validate(data)

    async def fetch_results(
        self, session_handle: str, operation_handle: str, token: int = 0
    ) -> FetchResultsResponse:
        """Fetch results for an operation.

        Args:
            session_handle: Session handle
            operation_handle: Operation handle
            token: Pagination token (starts at 0)

        Returns:
            Fetch results response
        """
        response = await self.client.get(
            f"/v1/sessions/{session_handle}/operations/{operation_handle}/result/{token}"
        )
        response.raise_for_status()
        data = response.json()
        return FetchResultsResponse.model_validate(data)

    async def cancel_operation(self, session_handle: str, operation_handle: str) -> None:
        """Cancel an operation.

        Args:
            session_handle: Session handle
            operation_handle: Operation handle
        """
        response = await self.client.post(
            f"/v1/sessions/{session_handle}/operations/{operation_handle}/cancel"
        )
        response.raise_for_status()
        logger.info(f"Cancelled operation: {operation_handle}")

    async def close_operation(self, session_handle: str, operation_handle: str) -> None:
        """Close an operation.

        Args:
            session_handle: Session handle
            operation_handle: Operation handle
        """
        response = await self.client.delete(
            f"/v1/sessions/{session_handle}/operations/{operation_handle}/close"
        )
        response.raise_for_status()
        logger.info(f"Closed operation: {operation_handle}")

    async def _get(self, path: str, **kwargs) -> Any:
        """Generic GET wrapper."""
        response = await self.client.get(path, **kwargs)
        response.raise_for_status()
        return response.json()

    async def _post(self, path: str, **kwargs) -> Any:
        """Generic POST wrapper."""
        response = await self.client.post(path, **kwargs)
        response.raise_for_status()
        return response.json()

    async def _delete(self, path: str, **kwargs) -> Any:
        """Generic DELETE wrapper."""
        response = await self.client.delete(path, **kwargs)
        response.raise_for_status()
        return response.json()
