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

'use client';

import { useParams, useRouter } from 'next/navigation';
import useSWR from 'swr';
import { fetcher, deleteTenant, getTenantRunHistory } from '@/lib/api';
import { Tenant, TenantRunHistory } from '@/lib/types';
import { Loader2, ArrowLeft, Trash2, ExternalLink, Code, Settings as SettingsIcon } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

export default function TenantDetails() {
  const { id } = useParams();
  const router = useRouter();
  const { data: tenant, error, isLoading } = useSWR<Tenant>(`/tenants/${id}`, fetcher);
  const { data: profiles } = useSWR(tenant ? `/tenants/${id}/profiles.yml` : null, (url) => fetch(`http://localhost:8000${url}`).then(res => res.text()));
  const { data: dbtProject } = useSWR(tenant ? `/tenants/${id}/dbt_project.yml` : null, (url) => fetch(`http://localhost:8000${url}`).then(res => res.text()));
  const { data: vars } = useSWR(tenant ? `/tenants/${id}/vars.json` : null, fetcher);
  const { data: verification } = useSWR(tenant ? `/tenants/${id}/verification` : null, fetcher);
  const { data: runHistory, error: runHistoryError } = useSWR<TenantRunHistory>(
    tenant ? `tenant-run-history-${id}` : null,
    () => getTenantRunHistory(String(id)),
    { refreshInterval: 30000 }
  );
  
  const [isDeleting, setIsDeleting] = useState(false);

  if (error) return <div className="card">Failed to load tenant details</div>;
  if (isLoading || !tenant) return <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}><Loader2 className="animate-spin" /></div>;

  const handleDelete = async () => {
    if (confirm(`Are you sure you want to delete tenant ${tenant.name}?`)) {
      setIsDeleting(true);
      try {
        await deleteTenant(tenant.id);
        router.push('/');
      } catch {
        alert('Failed to delete tenant');
        setIsDeleting(false);
      }
    }
  };

  return (
    <div>
      <div style={{ marginBottom: '2rem' }}>
        <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--gray-300)', marginBottom: '1rem' }}>
          <ArrowLeft size={16} />
          Back to Dashboard
        </Link>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1 className="title">{tenant.name}</h1>
            <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
              <span className={`status-badge status-${tenant.status}`}>{tenant.status}</span>
              <span style={{ color: 'var(--gray-300)', fontSize: '0.875rem' }}>ID: {tenant.id}</span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '1rem' }}>
            <button className="btn" style={{ backgroundColor: 'var(--gray-100)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <SettingsIcon size={18} />
              Edit Config
            </button>
            <button 
              onClick={handleDelete} 
              disabled={isDeleting}
              className="btn" 
              style={{ backgroundColor: '#fee2e2', color: '#991b1b', display: 'flex', alignItems: 'center', gap: '0.5rem' }}
            >
              <Trash2 size={18} />
              Delete
            </button>
          </div>
        </div>
      </div>

      <div className="grid">
        <div className="card">
          <h3 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Code size={18} color="var(--primary)" />
            Infrastructure
          </h3>
          <div style={{ fontSize: '0.875rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <span style={{ color: 'var(--gray-300)' }}>Flink Version:</span>
              <span>{tenant.flink_version}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <span style={{ color: 'var(--gray-300)' }}>dbt Version:</span>
              <span>{tenant.dbt_version}</span>
            </div>
          </div>
        </div>

        <div className="card">
          <h3 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <ExternalLink size={18} color="var(--primary)" />
            Connectivity
          </h3>
          <div style={{ fontSize: '0.875rem' }}>
            <div style={{ marginBottom: '0.5rem' }}>
              <span style={{ color: 'var(--gray-300)', display: 'block' }}>Kafka Topic:</span>
              <span>{tenant.kafka.topic}</span>
            </div>
            <div>
              <span style={{ color: 'var(--gray-300)', display: 'block' }}>JDBC URL:</span>
              <span style={{ wordBreak: 'break-all' }}>{tenant.sink.jdbc_url}</span>
            </div>
          </div>
        </div>

        <div className="card">
          <h3 style={{ marginBottom: '1rem' }}>Environment Mappings</h3>
          <div style={{ display: 'grid', gap: '0.75rem' }}>
            {Object.entries(tenant.environments).map(([env, mapping]) => (
              <div key={env} style={{ border: '1px solid var(--gray-200)', borderRadius: '0.5rem', padding: '0.75rem', fontSize: '0.875rem' }}>
                <div style={{ fontWeight: 600, textTransform: 'uppercase', marginBottom: '0.5rem' }}>{env}</div>
                <div style={{ color: 'var(--gray-300)' }}>Runtime: <span style={{ color: 'var(--foreground)' }}>{mapping.hydra_runtime_id}</span></div>
                <div style={{ color: 'var(--gray-300)' }}>dbt Env: <span style={{ color: 'var(--foreground)' }}>{mapping.dbt_environment_id}</span></div>
                <div style={{ color: 'var(--gray-300)' }}>dbt Project: <span style={{ color: 'var(--foreground)' }}>{mapping.dbt_project_id}</span></div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ marginTop: '2rem' }}>
        <div style={{ display: 'flex', gap: '2rem', borderBottom: '1px solid var(--gray-200)', marginBottom: '1.5rem' }}>
          <button style={{ padding: '0.5rem 0', borderBottom: '2px solid var(--primary)', fontWeight: 600, background: 'none', border: 'none', cursor: 'pointer', color: 'var(--foreground)' }}>
            Overview & Metrics
          </button>
          <button style={{ padding: '0.5rem 0', fontWeight: 500, background: 'none', border: 'none', cursor: 'pointer', color: 'var(--gray-300)' }}>
            Configurations
          </button>
          <button style={{ padding: '0.5rem 0', fontWeight: 500, background: 'none', border: 'none', cursor: 'pointer', color: 'var(--gray-300)' }}>
            Logs
          </button>
        </div>

        <div className="grid">
          <div className="card" style={{ gridColumn: '1 / -1' }}>
            <h4 style={{ marginBottom: '1rem', fontSize: '1rem', fontWeight: 600 }}>Run Status & Error Summary</h4>
            {!runHistory && !runHistoryError && (
              <div style={{ color: 'var(--gray-300)', fontSize: '0.875rem' }}>Loading run history...</div>
            )}
            {runHistoryError && (
              <div style={{ color: '#b91c1c', fontSize: '0.875rem' }}>
                Failed to load run history. Check backend `/tenants/{'{id}'}/runs` contract.
              </div>
            )}
            {runHistory && (
              <div style={{ display: 'grid', gap: '1rem' }}>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    border: '1px solid var(--gray-200)',
                    borderRadius: '0.5rem',
                    padding: '0.75rem',
                  }}
                >
                  <div style={{ fontSize: '0.875rem' }}>
                    <div style={{ color: 'var(--gray-300)' }}>Health</div>
                    <div style={{ fontWeight: 600, textTransform: 'uppercase' }}>{runHistory.health}</div>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--gray-300)' }}>
                    Last update: {new Date(runHistory.lastUpdatedAt).toLocaleString()}
                  </div>
                </div>
                {runHistory.runs.map((run) => (
                  <div key={run.runId} style={{ border: '1px solid var(--gray-200)', borderRadius: '0.5rem', padding: '0.875rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
                      <div style={{ fontSize: '0.875rem', fontWeight: 600 }}>{run.runId}</div>
                      <span className={`status-badge status-${run.status === 'failed' ? 'inactive' : run.status === 'success' ? 'active' : 'provisioning'}`}>
                        {run.status}
                      </span>
                    </div>
                    <div style={{ display: 'grid', gap: '0.25rem', fontSize: '0.8125rem', color: 'var(--gray-300)' }}>
                      <div>Attempt: <span style={{ color: 'var(--foreground)' }}>{run.attempt}/{run.maxAttempts}</span></div>
                      <div>Started: <span style={{ color: 'var(--foreground)' }}>{new Date(run.startedAt).toLocaleString()}</span></div>
                      {run.finishedAt && <div>Finished: <span style={{ color: 'var(--foreground)' }}>{new Date(run.finishedAt).toLocaleString()}</span></div>}
                      {run.durationSeconds && <div>Duration: <span style={{ color: 'var(--foreground)' }}>{run.durationSeconds}s</span></div>}
                      <div>Correlation ID: <span style={{ color: 'var(--foreground)' }}>{run.correlationId}</span></div>
                      {run.runtimeLogUrl && (
                        <div>
                          Runtime diagnostics:{' '}
                          <a
                            href={run.runtimeLogUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ color: 'var(--primary)' }}
                          >
                            Open logs
                          </a>
                        </div>
                      )}
                    </div>

                    {run.error && (
                      <div style={{ marginTop: '0.75rem', borderTop: '1px solid var(--gray-200)', paddingTop: '0.75rem', fontSize: '0.8125rem' }}>
                        <div style={{ fontWeight: 600, marginBottom: '0.375rem' }}>Error Envelope</div>
                        <div style={{ color: 'var(--gray-300)' }}>
                          Category: <span style={{ color: 'var(--foreground)' }}>{run.error.category}</span> ·
                          Reason: <span style={{ color: 'var(--foreground)' }}> {run.error.reasonCode}</span> ·
                          Retryable: <span style={{ color: 'var(--foreground)' }}> {run.error.isRetryable ? 'yes' : 'no'}</span>
                        </div>
                        <div style={{ color: 'var(--gray-300)', marginTop: '0.25rem' }}>
                          Suggested action: <span style={{ color: 'var(--foreground)' }}>{run.error.suggestedAction}</span>
                        </div>
                        {run.error.retryAfterSeconds !== undefined && (
                          <div style={{ color: 'var(--gray-300)', marginTop: '0.25rem' }}>
                            Retry after: <span style={{ color: 'var(--foreground)' }}>{run.error.retryAfterSeconds}s</span>
                          </div>
                        )}
                      </div>
                    )}

                    {run.finalSummary && (
                      <div style={{ marginTop: '0.75rem', borderTop: '1px solid var(--gray-200)', paddingTop: '0.75rem', fontSize: '0.8125rem' }}>
                        <div style={{ fontWeight: 600, marginBottom: '0.375rem' }}>Final Attempt Summary</div>
                        <div style={{ color: 'var(--gray-300)' }}>
                          Root cause: <span style={{ color: 'var(--foreground)' }}>{run.finalSummary.rootCause}</span>
                        </div>
                        <div style={{ color: 'var(--gray-300)', marginTop: '0.25rem' }}>
                          Remediation: <span style={{ color: 'var(--foreground)' }}>{run.finalSummary.remediation}</span>
                        </div>
                      </div>
                    )}

                    {run.modelFailures.length > 0 && (
                      <div style={{ marginTop: '0.75rem', borderTop: '1px solid var(--gray-200)', paddingTop: '0.75rem', fontSize: '0.8125rem' }}>
                        <div style={{ fontWeight: 600, marginBottom: '0.375rem' }}>Model-level failures</div>
                        {run.modelFailures.map((failure) => (
                          <div key={`${run.runId}-${failure.model}`} style={{ color: 'var(--gray-300)' }}>
                            {failure.model}: <span style={{ color: 'var(--foreground)' }}>{failure.message}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card">
            <h4 style={{ marginBottom: '1rem', fontSize: '0.875rem', fontWeight: 600, color: 'var(--gray-300)' }}>Events Per Second</h4>
            <div style={{ height: '100px', display: 'flex', alignItems: 'flex-end', gap: '4px' }}>
              {[40, 45, 30, 55, 70, 65, 80, 85, 75, 90, 95, 80, 70, 75, 85].map((h, i) => (
                <div key={i} style={{ flex: 1, height: `${h}%`, backgroundColor: 'var(--primary)', borderRadius: '2px 2px 0 0', opacity: 0.7 }} />
              ))}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '1rem' }}>
              <span style={{ fontSize: '1.5rem', fontWeight: 700 }}>1.2k</span>
              <span style={{ color: '#10b981', fontSize: '0.875rem', fontWeight: 600 }}>+12%</span>
            </div>
          </div>
          <div className="card">
            <h4 style={{ marginBottom: '1rem', fontSize: '0.875rem', fontWeight: 600, color: 'var(--gray-300)' }}>Consumer Lag</h4>
            <div style={{ height: '100px', display: 'flex', alignItems: 'flex-end', gap: '4px' }}>
              {[10, 15, 12, 8, 5, 7, 10, 12, 15, 20, 18, 15, 12, 10, 8].map((h, i) => (
                <div key={i} style={{ flex: 1, height: `${h}%`, backgroundColor: '#ef4444', borderRadius: '2px 2px 0 0', opacity: 0.7 }} />
              ))}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '1rem' }}>
              <span style={{ fontSize: '1.5rem', fontWeight: 700 }}>42 ms</span>
              <span style={{ color: '#ef4444', fontSize: '0.875rem', fontWeight: 600 }}>-5%</span>
            </div>
          </div>
          <div className="card">
            <h4 style={{ marginBottom: '1rem', fontSize: '0.875rem', fontWeight: 600, color: 'var(--gray-300)' }}>Uptime</h4>
            <div style={{ height: '100px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
               <div style={{ position: 'relative', width: '80px', height: '80px' }}>
                  <svg viewBox="0 0 36 36" style={{ transform: 'rotate(-90deg)' }}>
                    <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="var(--gray-200)" strokeWidth="3" />
                    <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#10b981" strokeWidth="3" strokeDasharray="99.9, 100" />
                  </svg>
                  <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', fontWeight: 700, fontSize: '0.875rem' }}>
                    99.9%
                  </div>
               </div>
            </div>
            <div style={{ textAlign: 'center', marginTop: '1rem' }}>
              <span style={{ color: 'var(--gray-300)', fontSize: '0.75rem' }}>Cluster Healthy</span>
            </div>
          </div>
        </div>

        <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '1rem', marginTop: '2.5rem' }}>Generated Configurations</h2>
        <div className="grid">
          <div className="card">
            <h4 style={{ marginBottom: '1rem', fontSize: '0.875rem', fontWeight: 600 }}>verification</h4>
            <pre style={{
              backgroundColor: 'var(--gray-100)',
              padding: '1rem',
              borderRadius: '0.5rem',
              fontSize: '0.75rem',
              overflowX: 'auto',
              maxHeight: '300px'
            }}>
              {verification ? JSON.stringify(verification, null, 2) : 'Loading...'}
            </pre>
          </div>
          <div className="card">
            <h4 style={{ marginBottom: '1rem', fontSize: '0.875rem', fontWeight: 600 }}>profiles.yml</h4>
            <pre style={{ 
              backgroundColor: 'var(--gray-100)', 
              padding: '1rem', 
              borderRadius: '0.5rem', 
              fontSize: '0.75rem',
              overflowX: 'auto',
              maxHeight: '300px'
            }}>
              {profiles || 'Loading...'}
            </pre>
          </div>
          <div className="card">
            <h4 style={{ marginBottom: '1rem', fontSize: '0.875rem', fontWeight: 600 }}>dbt_project.yml</h4>
            <pre style={{
              backgroundColor: 'var(--gray-100)',
              padding: '1rem',
              borderRadius: '0.5rem',
              fontSize: '0.75rem',
              overflowX: 'auto',
              maxHeight: '300px'
            }}>
              {dbtProject || 'Loading...'}
            </pre>
          </div>
          <div className="card">
            <h4 style={{ marginBottom: '1rem', fontSize: '0.875rem', fontWeight: 600 }}>vars.json</h4>
            <pre style={{ 
              backgroundColor: 'var(--gray-100)', 
              padding: '1rem', 
              borderRadius: '0.5rem', 
              fontSize: '0.75rem',
              overflowX: 'auto',
              maxHeight: '300px'
            }}>
              {vars ? JSON.stringify(vars, null, 2) : 'Loading...'}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}
