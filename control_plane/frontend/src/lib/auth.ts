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

/**
 * Server-only OIDC utilities — PKCE flow implementation using Node.js crypto.
 * Never import this module in client components.
 */

import { randomBytes, createHash } from 'crypto';

export const OIDC_ISSUER_URL = process.env.OIDC_ISSUER_URL ?? '';
export const OIDC_CLIENT_ID = process.env.OIDC_CLIENT_ID ?? '';
export const OIDC_CLIENT_SECRET = process.env.OIDC_CLIENT_SECRET ?? '';
export const OIDC_REDIRECT_URI =
  process.env.OIDC_REDIRECT_URI ?? 'http://localhost:3000/api/auth/callback';
export const AUTH_DISABLED = process.env.AUTH_DISABLED === 'true';

export function generateCodeVerifier(): string {
  return randomBytes(32).toString('base64url');
}

export function generateCodeChallenge(verifier: string): string {
  return createHash('sha256').update(verifier).digest('base64url');
}

export function generateState(): string {
  return randomBytes(16).toString('hex');
}

interface OidcConfig {
  authorization_endpoint: string;
  token_endpoint: string;
  end_session_endpoint?: string;
}

const _oidcConfigCache: Map<string, OidcConfig> = new Map();

export async function fetchOidcConfig(issuerUrl: string): Promise<OidcConfig> {
  if (_oidcConfigCache.has(issuerUrl)) {
    return _oidcConfigCache.get(issuerUrl)!;
  }
  const res = await fetch(`${issuerUrl.replace(/\/$/, '')}/.well-known/openid-configuration`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error(`Failed to fetch OIDC discovery: ${res.status}`);
  const cfg = (await res.json()) as OidcConfig;
  _oidcConfigCache.set(issuerUrl, cfg);
  return cfg;
}

interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  expires_in?: number;
  token_type?: string;
}

export async function exchangeCode(params: {
  code: string;
  codeVerifier: string;
  tokenEndpoint: string;
}): Promise<TokenResponse> {
  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    code: params.code,
    redirect_uri: OIDC_REDIRECT_URI,
    client_id: OIDC_CLIENT_ID,
    code_verifier: params.codeVerifier,
  });
  if (OIDC_CLIENT_SECRET) body.set('client_secret', OIDC_CLIENT_SECRET);

  const res = await fetch(params.tokenEndpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Token exchange failed (${res.status}): ${text}`);
  }
  return res.json() as Promise<TokenResponse>;
}

export async function exchangeRefreshToken(params: {
  refreshToken: string;
  tokenEndpoint: string;
}): Promise<TokenResponse> {
  const body = new URLSearchParams({
    grant_type: 'refresh_token',
    refresh_token: params.refreshToken,
    client_id: OIDC_CLIENT_ID,
  });
  if (OIDC_CLIENT_SECRET) body.set('client_secret', OIDC_CLIENT_SECRET);

  const res = await fetch(params.tokenEndpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  });
  if (!res.ok) throw new Error(`Token refresh failed (${res.status})`);
  return res.json() as Promise<TokenResponse>;
}
