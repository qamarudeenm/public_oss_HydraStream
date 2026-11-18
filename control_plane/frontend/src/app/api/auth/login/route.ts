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

import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import {
  generateCodeVerifier,
  generateCodeChallenge,
  generateState,
  fetchOidcConfig,
  OIDC_ISSUER_URL,
  OIDC_CLIENT_ID,
  OIDC_REDIRECT_URI,
  AUTH_DISABLED,
} from '@/lib/auth';

export async function GET(request: NextRequest) {
  if (AUTH_DISABLED) {
    return NextResponse.redirect(new URL('/', request.url));
  }

  if (!OIDC_ISSUER_URL || !OIDC_CLIENT_ID) {
    return NextResponse.json(
      { error: 'OIDC provider not configured. Set OIDC_ISSUER_URL and OIDC_CLIENT_ID.' },
      { status: 500 },
    );
  }

  const codeVerifier = generateCodeVerifier();
  const codeChallenge = generateCodeChallenge(codeVerifier);
  const state = generateState();

  let oidcConfig;
  try {
    oidcConfig = await fetchOidcConfig(OIDC_ISSUER_URL);
  } catch (err) {
    console.error('OIDC discovery failed:', err);
    return NextResponse.json({ error: 'OIDC discovery failed' }, { status: 502 });
  }

  const authUrl = new URL(oidcConfig.authorization_endpoint);
  authUrl.searchParams.set('client_id', OIDC_CLIENT_ID);
  authUrl.searchParams.set('redirect_uri', OIDC_REDIRECT_URI);
  authUrl.searchParams.set('response_type', 'code');
  authUrl.searchParams.set('scope', 'openid email profile');
  authUrl.searchParams.set('code_challenge', codeChallenge);
  authUrl.searchParams.set('code_challenge_method', 'S256');
  authUrl.searchParams.set('state', state);

  const cookieStore = await cookies();
  const pkceOpts = { httpOnly: true, secure: process.env.NODE_ENV === 'production', sameSite: 'lax' as const, path: '/' };
  cookieStore.set('hs_pkce_verifier', codeVerifier, pkceOpts);
  cookieStore.set('hs_pkce_state', state, pkceOpts);

  return NextResponse.redirect(authUrl.toString());
}
