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

import { useSearchParams } from 'next/navigation';
import { Activity, LogIn } from 'lucide-react';

export default function LoginPage() {
  const searchParams = useSearchParams();
  const error = searchParams.get('error');

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'var(--background)',
      }}
    >
      <div className="card" style={{ maxWidth: '400px', width: '100%', textAlign: 'center', padding: '2.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
          <Activity color="#0070f3" size={36} />
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700 }}>HydraStream</h1>
        </div>

        <p style={{ color: 'var(--gray-300)', marginBottom: '2rem' }}>
          Sign in to manage your streaming infrastructure.
        </p>

        {error && (
          <div
            style={{
              backgroundColor: '#fef2f2',
              border: '1px solid #fecaca',
              borderRadius: '0.375rem',
              padding: '0.75rem 1rem',
              marginBottom: '1.5rem',
              color: '#b91c1c',
              fontSize: '0.875rem',
            }}
          >
            {decodeURIComponent(error)}
          </div>
        )}

        <a
          href="/api/auth/login"
          className="btn btn-primary"
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', width: '100%' }}
        >
          <LogIn size={18} />
          Sign in with OIDC
        </a>

        <p style={{ marginTop: '1.5rem', fontSize: '0.75rem', color: 'var(--gray-300)' }}>
          Control Plane v0.1.0-alpha
        </p>
      </div>
    </div>
  );
}
