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

import { useEffect } from 'react';
import Link from 'next/link';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="card" style={{ textAlign: 'center', padding: '4rem' }}>
      <h2 className="title" style={{ color: '#ef4444' }}>Something went wrong!</h2>
      <p className="subtitle">We encountered an unexpected error in the dashboard.</p>
      <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
        <button className="btn btn-primary" onClick={() => reset()}>Try again</button>
        <Link href="/" className="btn" style={{ backgroundColor: 'var(--gray-100)' }}>Go Home</Link>
      </div>
    </div>
  );
}
