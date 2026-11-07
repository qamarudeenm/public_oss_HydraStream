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

    state_backend: str = "redis"
    """State backend: redis | memory"""

    state_redis_url: str = "redis://localhost:6379/0"
    """Redis URL for persistent statement state"""

    state_redis_key_prefix: str = "flink-gateway-proxy:statements"
    """Redis key prefix for statement records"""

    dbt_cloud_shared_secret: str = ""
    """Shared secret for validating dbt callback signatures"""

    dbt_tenant_gateway_map: dict[str, str] = {}
    """Tenant to Flink SQL Gateway URL mapping for runtime dispatch"""

    dbt_dispatch_max_attempts: int = 3
    """Maximum retry attempts for statement dispatch on retryable failures"""

    dbt_artifact_dir: str = ""
    """Default artifact directory containing manifest.json and run_results.json"""

    dbt_tenant_artifact_map: dict[str, str] = {}
    """Tenant to artifact directory mapping for inventory and lineage extraction"""

    log_level: str = "info"
    """Logging level"""
