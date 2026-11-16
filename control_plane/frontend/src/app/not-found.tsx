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

import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="card" style={{ textAlign: 'center', padding: '4rem' }}>
      <h2 className="title">404 - Page Not Found</h2>
      <p className="subtitle">The page you are looking for doesn't exist.</p>
      <Link href="/" className="btn btn-primary">Return Home</Link>
    </div>
  );
}
