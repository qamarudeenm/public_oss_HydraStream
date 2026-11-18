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

import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Link from "next/link";
import { LayoutDashboard, Users, Settings, Activity } from "lucide-react";
import { AuthProvider } from "@/components/AuthProvider";
import { LogoutButton } from "@/components/LogoutButton";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "HydraStream Control Plane",
  description: "Manage your real-time dbt + Flink platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <AuthProvider>
          <div className="app-container">
            <aside className="sidebar">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '2rem' }}>
                <Activity color="#0070f3" size={32} />
                <h1 style={{ fontSize: '1.25rem', fontWeight: 700 }}>HydraStream</h1>
              </div>
              <nav>
                <ul className="nav-list">
                  <li key="nav-dashboard" className="nav-item">
                    <Link href="/" className="nav-link">
                      <LayoutDashboard size={20} />
                      <span>Dashboard</span>
                    </Link>
                  </li>
                  <li key="nav-tenants" className="nav-item">
                    <Link href="/tenants" className="nav-link">
                      <Users size={20} />
                      <span>Tenants</span>
                    </Link>
                  </li>
                  <li key="nav-settings" className="nav-item">
                    <Link href="/settings" className="nav-link">
                      <Settings size={20} />
                      <span>Settings</span>
                    </Link>
                  </li>
                </ul>
              </nav>
              <div style={{ marginTop: 'auto', padding: '1rem', borderTop: '1px solid var(--gray-200)' }}>
                <LogoutButton />
                <p style={{ fontSize: '0.75rem', color: 'var(--gray-300)', marginTop: '0.5rem' }}>Version 0.1.0-alpha</p>
              </div>
            </aside>
            <main className="main-content">
              {children}
            </main>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
