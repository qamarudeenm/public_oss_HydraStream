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

"""Flink Gateway Proxy FastAPI application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .config import ProxyConfig
from .gateway.client import FlinkGatewayClient
from .routes import statements
from .session.manager import SessionManager
from .state.store import StateStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Global instances
config: ProxyConfig
gateway_client: FlinkGatewayClient
session_manager: SessionManager
state_store: StateStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global config, gateway_client, session_manager, state_store

    # Load configuration
    config = ProxyConfig()

    # Set logging level
    logging.getLogger().setLevel(config.log_level.upper())

    logger.info(f"Starting Flink Gateway Proxy")
    logger.info(f"Flink Gateway URL: {config.flink_gateway_url}")
    logger.info(f"Listen: {config.listen_host}:{config.listen_port}")

    # Initialize gateway client
    gateway_client = FlinkGatewayClient(config.flink_gateway_url)

    # Initialize state store
    state_store = StateStore()

    # Initialize session manager
    session_manager = SessionManager(
        gateway_client,
        heartbeat_interval=config.session_heartbeat_interval,
        idle_timeout=config.session_idle_timeout,
    )

    # Start session manager background tasks
    await session_manager.start()

    # Inject dependencies into routes
    statements.set_dependencies(gateway_client, session_manager, state_store)

    logger.info("Flink Gateway Proxy started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Flink Gateway Proxy")

    # Stop session manager
    await session_manager.stop()

    # Close gateway client
    await gateway_client.close()

    logger.info("Flink Gateway Proxy stopped")


# Create FastAPI app
app = FastAPI(
    title="Flink Gateway Proxy",
    description="Confluent-to-OSS Flink SQL Gateway translation proxy",
    version="0.1.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(statements.router)


@app.get("/health")
async def health() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse(content={"status": "healthy"}, status_code=200)


@app.get("/ready")
async def ready() -> JSONResponse:
    """Readiness check endpoint."""
    # Check if gateway client can reach Flink SQL Gateway
    try:
        # Simple check: try to list sessions (or any lightweight operation)
        # For now, just return ready if initialized
        if gateway_client is None:
            return JSONResponse(content={"status": "not ready"}, status_code=503)
        return JSONResponse(content={"status": "ready"}, status_code=200)
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(content={"status": "not ready"}, status_code=503)


if __name__ == "__main__":
    import uvicorn

    # Load config to get listen settings
    config = ProxyConfig()

    uvicorn.run(
        "flink_gateway_proxy.main:app",
        host=config.listen_host,
        port=config.listen_port,
        log_level=config.log_level.lower(),
    )
