/**
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

export interface KafkaConfig {
  bootstrap_servers: string;
  topic: string;
  group_id: string;
}

export interface SinkConfig {
  jdbc_url: string;
  user: string;
  password?: string;
  summary_table: string;
  metrics_table: string;
}

export interface EnvironmentMapping {
  hydra_runtime_id: string;
  dbt_environment_id: string;
  dbt_project_id: string;
  dbt_service_token: string;
}

export interface TenantEnvironments {
  dev: EnvironmentMapping;
  staging: EnvironmentMapping;
  prod: EnvironmentMapping;
}

export interface Tenant {
  id: string;
  name: string;
  kafka: KafkaConfig;
  sink: SinkConfig;
  flink_version: string;
  dbt_version: string;
  environments: TenantEnvironments;
  status: 'inactive' | 'active' | 'provisioning';
}

export type TenantCreate = Omit<Tenant, 'status'>;
export type TenantUpdate = Partial<Tenant>;

export type ErrorCategory =
  | 'NETWORK_TIMEOUT'
  | 'UPSTREAM_5XX'
  | 'RATE_LIMIT'
  | 'AUTH_INVALID'
  | 'CONFIG_INVALID'
  | 'PERMISSION_DENIED'
  | 'SCHEMA_MISMATCH'
  | string;

export interface RunErrorEnvelope {
  category: ErrorCategory;
  reasonCode: string;
  isRetryable: boolean;
  suggestedAction: string;
  retryAfterSeconds?: number;
  correlationId: string;
}

export interface RunModelFailure {
  model: string;
  message: string;
}

export interface RunFinalSummary {
  rootCause: string;
  remediation: string;
}

export interface RunHistoryItem {
  runId: string;
  attempt: number;
  maxAttempts: number;
  status: 'success' | 'failed' | 'retrying' | 'running' | 'queued' | string;
  startedAt: string;
  finishedAt?: string;
  durationSeconds?: number;
  correlationId: string;
  runtimeLogUrl?: string;
  error?: RunErrorEnvelope;
  finalSummary?: RunFinalSummary;
  modelFailures: RunModelFailure[];
}

export interface TenantRunHistory {
  tenantId: string;
  health: 'healthy' | 'degraded' | 'unknown' | string;
  lastUpdatedAt: string;
  runs: RunHistoryItem[];
}
