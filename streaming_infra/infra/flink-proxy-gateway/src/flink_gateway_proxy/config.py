"""Configuration for Flink Gateway Proxy."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ProxyConfig(BaseSettings):
    """Proxy configuration settings."""

    model_config = SettingsConfigDict(env_prefix="PROXY_", env_file=".env", extra="ignore")

    flink_gateway_url: str
    """URL of the Flink SQL Gateway (required)"""

    listen_host: str = "0.0.0.0"
    """Host to bind the proxy server"""

    listen_port: int = 8080
    """Port to bind the proxy server"""

    session_heartbeat_interval: int = 30
    """Seconds between session heartbeats"""

    session_idle_timeout: int = 600
    """Seconds before idle sessions are cleaned up"""

    auth_mode: str = "passthrough"
    """Authentication mode: passthrough | static"""

    auth_user: str = ""
    """Username for static auth (if auth_mode=static)"""

    auth_pass: str = ""
    """Password for static auth (if auth_mode=static)"""

    default_principal: str = "proxy-user"
    """Default principal name for statement tracking"""

    log_level: str = "info"
    """Logging level"""
