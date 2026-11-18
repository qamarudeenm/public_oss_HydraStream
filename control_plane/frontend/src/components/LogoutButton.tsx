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

import { LogOut } from 'lucide-react';
import { useAuth } from './AuthProvider';

export function LogoutButton() {
  const { logout, isLoading } = useAuth();

  if (isLoading) return null;

  return (
    <button
      onClick={logout}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        color: 'var(--gray-300)',
        fontSize: '0.875rem',
        padding: '0.5rem',
        borderRadius: '0.375rem',
        width: '100%',
      }}
      title="Sign out"
    >
      <LogOut size={16} />
      <span>Sign out</span>
    </button>
  );
}
