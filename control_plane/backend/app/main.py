"""HydraStream control plane API."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .config import ControlPlaneConfig
from .routes import tenants

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = ControlPlaneConfig()
    app.state.config = config
    logging.getLogger().setLevel(config.log_level.upper())
    logger.info("Control plane API started (OIDC issuer: %s)", config.oidc_issuer_url)
    yield
    logger.info("Control plane API stopped")


app = FastAPI(
    title="HydraStream Control Plane",
    description="Tenant management API for HydraStream",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(tenants.router)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(content={"status": "healthy"})


if __name__ == "__main__":
    import uvicorn

    cfg = ControlPlaneConfig()
    uvicorn.run(
        "app.main:app",
        host=cfg.listen_host,
        port=cfg.listen_port,
        log_level=cfg.log_level.lower(),
    )
