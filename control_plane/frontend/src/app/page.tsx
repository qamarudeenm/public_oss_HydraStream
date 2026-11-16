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

import useSWR from 'swr';
import { fetcher } from '@/lib/api';
import { Tenant } from '@/lib/types';
import Link from 'next/link';
import { Plus, Server, Database, Loader2 } from 'lucide-react';

export default function Dashboard() {
  const { data: tenants, error, isLoading } = useSWR<Tenant[]>('/tenants', fetcher);

  if (error) return <div className="card">Failed to load tenants</div>;
  if (isLoading) return <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}><Loader2 className="animate-spin" /></div>;

  const activeCount = tenants?.filter(t => t.status === 'active').length || 0;
  const provisioningCount = tenants?.filter(t => t.status === 'provisioning').length || 0;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 className="title">System Overview</h1>
          <p style={{ color: 'var(--gray-300)' }}>Manage your streaming infrastructure and tenants.</p>
        </div>
        <Link href="/tenants/new" className="btn btn-primary" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Plus size={18} />
          Create Tenant
        </Link>
      </div>

      <div className="grid" style={{ marginBottom: '3rem' }}>
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
            <span style={{ color: 'var(--gray-300)', fontWeight: 500 }}>Active Tenants</span>
            <Server size={20} color="var(--primary)" />
          </div>
          <p style={{ fontSize: '2rem', fontWeight: 700 }}>{activeCount}</p>
        </div>
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
            <span style={{ color: 'var(--gray-300)', fontWeight: 500 }}>Provisioning</span>
            <Loader2 size={20} color="#eab308" />
          </div>
          <p style={{ fontSize: '2rem', fontWeight: 700 }}>{provisioningCount}</p>
        </div>
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
            <span style={{ color: 'var(--gray-300)', fontWeight: 500 }}>Total Pipelines</span>
            <Database size={20} color="#10b981" />
          </div>
          <p style={{ fontSize: '2rem', fontWeight: 700 }}>{tenants?.length || 0}</p>
        </div>
      </div>

      <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '1rem' }}>Recent Tenants</h2>
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead style={{ backgroundColor: 'var(--gray-100)', textAlign: 'left' }}>
            <tr>
              <th style={{ padding: '1rem' }}>Tenant Name</th>
              <th style={{ padding: '1rem' }}>ID</th>
              <th style={{ padding: '1rem' }}>Flink Version</th>
              <th style={{ padding: '1rem' }}>Status</th>
              <th style={{ padding: '1rem' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {tenants && tenants.length > 0 ? (
              tenants.slice(0, 5).map((tenant) => (
                <tr key={tenant.id} style={{ borderTop: '1px solid var(--gray-200)' }}>
                  <td style={{ padding: '1rem', fontWeight: 500 }}>{tenant.name}</td>
                  <td style={{ padding: '1rem', color: 'var(--gray-300)', fontSize: '0.875rem' }}>{tenant.id}</td>
                  <td style={{ padding: '1rem' }}>{tenant.flink_version}</td>
                  <td style={{ padding: '1rem' }}>
                    <span className={`status-badge status-${tenant.status}`}>{tenant.status}</span>
                  </td>
                  <td style={{ padding: '1rem' }}>
                    <Link href={`/tenants/${tenant.id}`} style={{ color: 'var(--primary)', fontWeight: 500 }}>Details</Link>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5} style={{ padding: '2rem', textAlign: 'center', color: 'var(--gray-300)' }}>
                  No tenants found. Create your first one to get started.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
