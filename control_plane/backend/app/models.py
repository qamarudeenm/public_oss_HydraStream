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

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class KafkaConfig(BaseModel):
    bootstrap_servers: str = "kafka:29092"
    topic: str = "clickstream"
    group_id: str = "clickstream-consumer-group"

class SinkConfig(BaseModel):
    jdbc_url: str = "jdbc:mysql://host.docker.internal:9004/clickstream"
    user: str = "flink_user"
    password: str = "12345"
    summary_table: str = "clickstream_summary"
    metrics_table: str = "transformed_clickstream_metrics"

class EnvironmentMapping(BaseModel):
    hydra_runtime_id: str
    dbt_environment_id: str
    dbt_project_id: str
    dbt_service_token: str
    dbt_service_token_hash: Optional[str] = None

class TenantEnvironments(BaseModel):
    dev: EnvironmentMapping
    staging: EnvironmentMapping
    prod: EnvironmentMapping

def default_environment_mapping(tenant_id: str, env_name: str) -> EnvironmentMapping:
    return EnvironmentMapping(
        hydra_runtime_id=f"{tenant_id}-{env_name}",
        dbt_environment_id=f"dbt-{env_name}-{tenant_id}",
        dbt_project_id=f"project-{tenant_id}",
        dbt_service_token="",
    )

class Tenant(BaseModel):
    id: str
    name: str
    description: str = ""
    kafka: KafkaConfig = Field(default_factory=KafkaConfig)
    sink: SinkConfig = Field(default_factory=SinkConfig)
    flink_version: str = "1.19.1"
    dbt_version: str = "1.7.0"
    environments: Optional[TenantEnvironments] = None
    status: str = "inactive" # inactive, active, provisioning

    def model_post_init(self, __context):
        if self.environments is None:
            self.environments = TenantEnvironments(
                dev=default_environment_mapping(self.id, "dev"),
                staging=default_environment_mapping(self.id, "staging"),
                prod=default_environment_mapping(self.id, "prod"),
            )


class TenantCreate(BaseModel):
    name: str
    description: str = ""


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class WebhookEventType(str, Enum):
    pipeline_error = "pipeline_error"
    pipeline_recovered = "pipeline_recovered"
    threshold_exceeded = "threshold_exceeded"
    billing_event = "billing_event"
    maintenance_notice = "maintenance_notice"


class WebhookEndpoint(BaseModel):
    id: str
    tenant_id: str
    url: str
    event_types: List[WebhookEventType]
    signing_secret: str
    enabled: bool = True
    created_at: datetime


class WebhookEndpointCreate(BaseModel):
    url: str
    event_types: List[WebhookEventType]


class WebhookEndpointUpdate(BaseModel):
    url: Optional[str] = None
    event_types: Optional[List[WebhookEventType]] = None
    enabled: Optional[bool] = None


class WebhookDeliveryStatus(str, Enum):
    success = "success"
    failed = "failed"


class WebhookDeliveryLog(BaseModel):
    id: str
    webhook_id: str
    tenant_id: str
    event_type: WebhookEventType
    payload: dict
    status: WebhookDeliveryStatus
    attempt: int
    response_code: Optional[int] = None
    latency_ms: Optional[int] = None
    error: Optional[str] = None
    delivered_at: datetime


class WebhookDeadLetterEntry(BaseModel):
    id: str
    webhook_id: str
    tenant_id: str
    event_type: WebhookEventType
    payload: dict
    attempts: int
    last_error: Optional[str] = None
    created_at: datetime
