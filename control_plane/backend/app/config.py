"""Control plane configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ControlPlaneConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CONTROL_PLANE_", env_file=".env", extra="ignore"
    )

    oidc_issuer_url: str = ""
    """OIDC provider issuer URL (e.g. https://accounts.example.com). Required in production."""

    oidc_audience: str = ""
    """Expected JWT audience claim. Required in production."""

    listen_host: str = "0.0.0.0"
    listen_port: int = 8000
    log_level: str = "info"
