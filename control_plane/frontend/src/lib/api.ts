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

import { Tenant, TenantCreate, TenantRunHistory, TenantUpdate } from './types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

let _authToken: string | null = null;

export function setAuthToken(token: string | null): void {
  _authToken = token;
}

function authHeaders(): Record<string, string> {
  return _authToken ? { Authorization: `Bearer ${_authToken}` } : {};
}

function handleUnauthorized(res: Response): void {
  if (res.status === 401 && typeof window !== 'undefined') {
    window.dispatchEvent(new Event('auth:unauthorized'));
  }
}

export const fetcher = (url: string) =>
  fetch(`${API_BASE_URL}${url}`, { headers: authHeaders() }).then((res) => {
    if (!res.ok) {
      handleUnauthorized(res);
      throw new Error('An error occurred while fetching the data.');
    }
    return res.json();
  });

export const getTenants = async (): Promise<Tenant[]> => {
  const res = await fetch(`${API_BASE_URL}/tenants`, { headers: authHeaders() });
  handleUnauthorized(res);
  return res.json();
};

export const getTenant = async (id: string): Promise<Tenant> => {
  const res = await fetch(`${API_BASE_URL}/tenants/${id}`, { headers: authHeaders() });
  handleUnauthorized(res);
  return res.json();
};

export const createTenant = async (tenant: TenantCreate): Promise<Tenant> => {
  const res = await fetch(`${API_BASE_URL}/tenants`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify(tenant),
  });
  handleUnauthorized(res);
  return res.json();
};

export const updateTenant = async (id: string, tenant: TenantUpdate): Promise<Tenant> => {
  const res = await fetch(`${API_BASE_URL}/tenants/${id}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify(tenant),
  });
  handleUnauthorized(res);
  return res.json();
};

export const deleteTenant = async (id: string): Promise<{ status: string; message: string }> => {
  const res = await fetch(`${API_BASE_URL}/tenants/${id}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  handleUnauthorized(res);
  return res.json();
};

export const getTenantRunHistory = async (id: string): Promise<TenantRunHistory> => {
  const res = await fetch(`${API_BASE_URL}/tenants/${id}/runs`, { headers: authHeaders() });
  if (!res.ok) {
    handleUnauthorized(res);
    throw new Error('Failed to load tenant run history.');
  }
  const payload = await res.json();
  return normalizeTenantRunHistory(id, payload);
};

const normalizeTenantRunHistory = (tenantId: string, payload: unknown): TenantRunHistory => {
  const raw = (payload ?? {}) as Record<string, unknown>;
  const rawRuns = Array.isArray(raw.runs) ? raw.runs : [];

  const runs = rawRuns.map((item, index) => {
    const run = (item ?? {}) as Record<string, unknown>;
    const error = (run.error ?? run.errorEnvelope ?? run.failure) as Record<string, unknown> | undefined;
    const finalSummary = (run.finalSummary ?? run.terminalSummary) as Record<string, unknown> | undefined;
    const modelFailuresRaw = Array.isArray(run.modelFailures) ? run.modelFailures : [];

    return {
      runId: String(run.runId ?? run.id ?? `run-${index}`),
      attempt: Number(run.attempt ?? run.retryAttempt ?? 1),
      maxAttempts: Number(run.maxAttempts ?? run.retryBudget ?? 1),
      status: String(run.status ?? 'unknown'),
      startedAt: String(run.startedAt ?? run.started_at ?? new Date().toISOString()),
      finishedAt: run.finishedAt ? String(run.finishedAt) : run.finished_at ? String(run.finished_at) : undefined,
      durationSeconds: run.durationSeconds ? Number(run.durationSeconds) : undefined,
      correlationId: String(run.correlationId ?? run.correlation_id ?? 'unknown'),
      runtimeLogUrl: run.runtimeLogUrl ? String(run.runtimeLogUrl) : run.runtime_log_url ? String(run.runtime_log_url) : undefined,
      error: error
        ? {
            category: String(error.category ?? error.type ?? 'UNKNOWN'),
            reasonCode: String(error.reasonCode ?? error.reason_code ?? 'UNKNOWN'),
            isRetryable: Boolean(error.isRetryable ?? error.retryable),
            suggestedAction: String(error.suggestedAction ?? error.remediation ?? 'Inspect runtime logs and retry if safe.'),
            retryAfterSeconds: error.retryAfterSeconds ? Number(error.retryAfterSeconds) : undefined,
            correlationId: String(
              error.correlationId ?? error.correlation_id ?? run.correlationId ?? run.correlation_id ?? 'unknown'
            ),
          }
        : undefined,
      finalSummary: finalSummary
        ? {
            rootCause: String(finalSummary.rootCause ?? finalSummary.root_cause ?? 'Unknown root cause'),
            remediation: String(finalSummary.remediation ?? finalSummary.suggestedAction ?? 'Review logs and retry.'),
          }
        : undefined,
      modelFailures: modelFailuresRaw.map((failure) => {
        const rawFailure = (failure ?? {}) as Record<string, unknown>;
        return {
          model: String(rawFailure.model ?? rawFailure.modelName ?? 'unknown-model'),
          message: String(rawFailure.message ?? rawFailure.error ?? 'Unknown model failure'),
        };
      }),
    };
  });

  return {
    tenantId: String(raw.tenantId ?? raw.tenant_id ?? tenantId),
    health: String(raw.health ?? raw.status ?? 'unknown'),
    lastUpdatedAt: String(raw.lastUpdatedAt ?? raw.updatedAt ?? new Date().toISOString()),
    runs,
  };
};
