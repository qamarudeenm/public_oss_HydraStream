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

import yaml
import os
from .models import Tenant

def generate_tenant_profiles_yml(tenant: Tenant) -> str:
    dev_mapping = tenant.environments.dev
    profile = {
        "hydrastream": {
            "outputs": {
                "dev": {
                    "type": "confluent",
                    "host": f"proxy-{tenant.id}",
                    "port": 8080,
                    "cloud_provider": "kubernetes",
                    "cloud_region": "local",
                    "compute_pool_id": dev_mapping.hydra_runtime_id,
                    "organization_id": f"org-{tenant.id}",
                    "environment_id": dev_mapping.dbt_environment_id,
                    "flink_api_key": "runtime",
                    "flink_api_secret": f"${{DBT_SERVICE_TOKEN_{tenant.id.upper()}_DEV}}",
                    "dbname": "default_database",
                    "threads": 1
                }
            },
            "target": "dev"
        }
    }
    return yaml.dump(profile)

def generate_tenant_dbt_project_yml(tenant: Tenant) -> str:
    dbt_project = {
        "name": f"tenant_{tenant.id}",
        "version": "1.0.0",
        "config-version": 2,
        "profile": "hydrastream",
        "model-paths": ["models"],
        "models": {
            f"tenant_{tenant.id}": {
                "+materialized": "table",
                "+vars": generate_tenant_vars(tenant),
            }
        },
        "vars": {
            "hydra_runtime_dev": tenant.environments.dev.hydra_runtime_id,
            "hydra_runtime_staging": tenant.environments.staging.hydra_runtime_id,
            "hydra_runtime_prod": tenant.environments.prod.hydra_runtime_id,
        },
    }
    return yaml.dump(dbt_project)

def generate_tenant_vars(tenant: Tenant) -> dict:
    return {
        "kafka_topic": tenant.kafka.topic,
        "kafka_bootstrap_servers": tenant.kafka.bootstrap_servers,
        "kafka_group_id": tenant.kafka.group_id,
        "clickhouse_jdbc_url": tenant.sink.jdbc_url,
        "clickhouse_user": tenant.sink.user,
        "clickhouse_password": tenant.sink.password,
        "clickhouse_summary_table": tenant.sink.summary_table,
        "clickhouse_metrics_table": tenant.sink.metrics_table,
    }

def generate_tenant_docker_compose(tenant: Tenant) -> dict:
    # This is a simplified version of the main docker-compose
    # Each tenant gets their own flink cluster and proxy
    # In a real SaaS, this would be Kubernetes
    return {
        "version": "3.8",
        "name": f"hydrastream-{tenant.id}",
        "services": {
            f"flink-jobmanager-{tenant.id}": {
                "image": f"blue2berry/hydrastream:engine-flink{tenant.flink_version}",
                "command": "jobmanager",
                "environment": [
                    "FLINK_PROPERTIES=jobmanager.rpc.address: flink-jobmanager-" + tenant.id
                ]
            },
            f"flink-taskmanager-{tenant.id}": {
                "image": f"blue2berry/hydrastream:engine-flink{tenant.flink_version}",
                "command": "taskmanager",
                "depends_on": [f"flink-jobmanager-{tenant.id}"],
                "environment": [
                    f"FLINK_PROPERTIES=jobmanager.rpc.address: flink-jobmanager-{tenant.id}"
                ]
            },
            f"flink-sql-gateway-{tenant.id}": {
                "image": f"blue2berry/hydrastream:engine-flink{tenant.flink_version}",
                "command": "/opt/flink/bin/sql-gateway.sh start-foreground",
                "depends_on": [f"flink-jobmanager-{tenant.id}"],
                "environment": [
                    f"FLINK_PROPERTIES=jobmanager.rpc.address: flink-jobmanager-{tenant.id}\nsql-gateway.endpoint.rest.address: 0.0.0.0"
                ]
            },
            f"proxy-{tenant.id}": {
                "image": "blue2berry/hydrastream:proxy-latest",
                "environment": {
                    "PROXY_FLINK_GATEWAY_URL": f"http://flink-sql-gateway-{tenant.id}:8083",
                    "PROXY_LISTEN_HOST": "0.0.0.0",
                    "PROXY_LISTEN_PORT": "8080"
                },
                "depends_on": [f"flink-sql-gateway-{tenant.id}"]
            }
        }
    }

def verify_tenant_connection_mapping(tenant: Tenant) -> dict:
    required_runtime_fields = (
        tenant.environments.dev.hydra_runtime_id,
        tenant.environments.staging.hydra_runtime_id,
        tenant.environments.prod.hydra_runtime_id,
        tenant.environments.dev.dbt_environment_id,
        tenant.environments.staging.dbt_environment_id,
        tenant.environments.prod.dbt_environment_id,
    )
    return {
        "tenant_id": tenant.id,
        "kafka_configured": bool(tenant.kafka.bootstrap_servers and tenant.kafka.topic and tenant.kafka.group_id),
        "sink_configured": bool(tenant.sink.jdbc_url and tenant.sink.user and tenant.sink.summary_table and tenant.sink.metrics_table),
        "runtime_mappings_complete": all(required_runtime_fields),
        "dbt_tokens_hashed": all(
            bool(getattr(tenant.environments, env).dbt_service_token_hash)
            for env in ("dev", "staging", "prod")
        ),
    }
