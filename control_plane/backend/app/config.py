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

from pydantic_settings import BaseSettings, SettingsConfigDict


class ControlPlaneConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONTROL_PLANE_", env_file=".env", extra="ignore")

    oidc_issuer_url: str = ""
    # Production (Google Identity Platform): set to the GCP OAuth2 client ID
    # e.g. CONTROL_PLANE_OIDC_AUDIENCE=<numbers>-<hash>.apps.googleusercontent.com
    oidc_audience: str = "hydrastream-control-plane"
    auth_disabled: bool = False

    listen_host: str = "0.0.0.0"
    listen_port: int = 8000
    log_level: str = "info"

    # CORS — comma-separated list of allowed origins.
    # Default: production domain only. Override in dev with localhost origins.
    cors_origins: str = "https://hydrastream.imarasystems.com"

    # Rate limiting — requests per minute per tenant (JWT sub) or IP.
    rate_limit_per_minute: int = 120
    # Stricter limit for mutation endpoints (POST/PATCH/DELETE).
    rate_limit_writes_per_minute: int = 30

    # Maximum request body size in bytes (default: 1 MiB).
    max_body_size_bytes: int = 1_048_576

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = ControlPlaneConfig()
