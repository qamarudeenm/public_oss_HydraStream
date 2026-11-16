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
import { Plus, Loader2, Search, Filter } from 'lucide-react';
import { useState } from 'react';

export default function TenantsList() {
  const { data: tenants, error, isLoading } = useSWR<Tenant[]>('/tenants', fetcher);
  const [searchTerm, setSearchTerm] = useState('');

  if (error) return <div className="card">Failed to load tenants</div>;
  if (isLoading) return <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}><Loader2 className="animate-spin" /></div>;

  const filteredTenants = tenants?.filter(t => 
    t.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
    t.id.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 className="title">Tenants</h1>
          <p style={{ color: 'var(--gray-300)' }}>Manage your isolated tenant environments.</p>
        </div>
        <Link href="/tenants/new" className="btn btn-primary" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Plus size={18} />
          Create Tenant
        </Link>
      </div>

      <div className="card" style={{ marginBottom: '1.5rem', display: 'flex', gap: '1rem', alignItems: 'center' }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <Search size={18} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--gray-300)' }} />
          <input 
            type="text" 
            placeholder="Search by name or ID..." 
            style={{ paddingLeft: '2.5rem' }}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <button className="btn" style={{ backgroundColor: 'var(--gray-100)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Filter size={18} />
          Filter
        </button>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead style={{ backgroundColor: 'var(--gray-100)', textAlign: 'left' }}>
            <tr>
              <th style={{ padding: '1rem' }}>Tenant Name</th>
              <th style={{ padding: '1rem' }}>ID</th>
              <th style={{ padding: '1rem' }}>Flink Version</th>
              <th style={{ padding: '1rem' }}>dbt Version</th>
              <th style={{ padding: '1rem' }}>Environment Mappings</th>
              <th style={{ padding: '1rem' }}>Status</th>
              <th style={{ padding: '1rem' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredTenants && filteredTenants.length > 0 ? (
              filteredTenants.map((tenant) => (
                <tr key={tenant.id} style={{ borderTop: '1px solid var(--gray-200)' }}>
                  <td style={{ padding: '1rem', fontWeight: 500 }}>{tenant.name}</td>
                  <td style={{ padding: '1rem', color: 'var(--gray-300)', fontSize: '0.875rem' }}>{tenant.id}</td>
                  <td style={{ padding: '1rem' }}>{tenant.flink_version}</td>
                  <td style={{ padding: '1rem' }}>{tenant.dbt_version}</td>
                  <td style={{ padding: '1rem', fontSize: '0.875rem' }}>
                    {Object.entries(tenant.environments)
                      .map(([env, mapping]) => `${env}:${mapping.hydra_runtime_id}`)
                      .join(', ')}
                  </td>
                  <td style={{ padding: '1rem' }}>
                    <span className={`status-badge status-${tenant.status}`}>{tenant.status}</span>
                  </td>
                  <td style={{ padding: '1rem' }}>
                    <Link href={`/tenants/${tenant.id}`} style={{ color: 'var(--primary)', fontWeight: 500 }}>Manage</Link>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={7} style={{ padding: '2rem', textAlign: 'center', color: 'var(--gray-300)' }}>
                  No tenants found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
