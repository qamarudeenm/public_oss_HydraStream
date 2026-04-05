"""Session lifecycle manager for Flink SQL Gateway sessions."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import NamedTuple

from ..gateway.client import FlinkGatewayClient

logger = logging.getLogger(__name__)


class SessionKey(NamedTuple):
    """Key for identifying a unique session."""

    org_id: str
    env_id: str
    catalog: str
    database: str


@dataclass
class Session:
    """Session state."""

    handle: str
    key: SessionKey
    last_used: float = field(default_factory=lambda: asyncio.get_event_loop().time())


class SessionManager:
    """Manages Flink SQL Gateway sessions with automatic heartbeats."""

    def __init__(
        self,
        gateway_client: FlinkGatewayClient,
        heartbeat_interval: int = 30,
        idle_timeout: int = 600,
    ):
        """Initialize the session manager.

        Args:
            gateway_client: Flink Gateway client
            heartbeat_interval: Seconds between heartbeats
            idle_timeout: Seconds before idle sessions are cleaned up
        """
        self.gateway_client = gateway_client
        self.heartbeat_interval = heartbeat_interval
        self.idle_timeout = idle_timeout

        self._sessions: dict[SessionKey, Session] = {}
        self._lock = asyncio.Lock()
        self._heartbeat_task: asyncio.Task | None = None
        self._cleanup_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start background tasks."""
        if self._running:
            return

        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Session manager started")

    async def stop(self) -> None:
        """Stop background tasks and close all sessions."""
        if not self._running:
            return

        self._running = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Close all sessions
        async with self._lock:
            for session in list(self._sessions.values()):
                try:
                    await self.gateway_client.close_session(session.handle)
                except Exception as e:
                    logger.error(f"Error closing session {session.handle}: {e}")
            self._sessions.clear()

        logger.info("Session manager stopped")

    async def get_or_create_session(
        self, org_id: str, env_id: str, catalog: str, database: str
    ) -> str:
        """Get or create a session for the given key.

        Args:
            org_id: Organization ID
            env_id: Environment ID (maps to catalog)
            catalog: Flink catalog
            database: Flink database

        Returns:
            Session handle
        """
        key = SessionKey(org_id, env_id, catalog, database)

        async with self._lock:
            session = self._sessions.get(key)

            if session is not None:
                # Update last used time
                session.last_used = asyncio.get_event_loop().time()
                logger.debug(f"Reusing session: {session.handle}")
                return session.handle

            # Create new session
            properties = {
                "sql.current-catalog": catalog,
                "sql.current-database": database,
            }

            session_handle = await self.gateway_client.open_session(
                session_name=f"{org_id}-{env_id}", properties=properties
            )

            session = Session(handle=session_handle, key=key)
            self._sessions[key] = session

            logger.info(f"Created new session: {session_handle} for {key}")
            return session_handle

    async def _heartbeat_loop(self) -> None:
        """Background task to send heartbeats to all sessions."""
        while self._running:
            try:
                await asyncio.sleep(self.heartbeat_interval)

                async with self._lock:
                    for session in list(self._sessions.values()):
                        try:
                            await self.gateway_client.heartbeat(session.handle)
                        except Exception as e:
                            logger.warning(
                                f"Heartbeat failed for session {session.handle}: {e}"
                            )
                            # Session may be dead, remove it
                            self._sessions.pop(session.key, None)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")

    async def _cleanup_loop(self) -> None:
        """Background task to clean up idle sessions."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute

                now = asyncio.get_event_loop().time()

                async with self._lock:
                    for key, session in list(self._sessions.items()):
                        if now - session.last_used > self.idle_timeout:
                            try:
                                await self.gateway_client.close_session(session.handle)
                                self._sessions.pop(key, None)
                                logger.info(
                                    f"Closed idle session: {session.handle} for {key}"
                                )
                            except Exception as e:
                                logger.error(
                                    f"Error closing idle session {session.handle}: {e}"
                                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
