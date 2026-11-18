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
import { exchangeCode, fetchOidcConfig, OIDC_ISSUER_URL } from '@/lib/auth';

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const code = searchParams.get('code');
  const state = searchParams.get('state');
  const error = searchParams.get('error');

  if (error) {
    const description = searchParams.get('error_description') ?? error;
    return NextResponse.redirect(
      new URL(`/login?error=${encodeURIComponent(description)}`, request.url),
    );
  }

  const cookieStore = await cookies();
  const storedState = cookieStore.get('hs_pkce_state')?.value;
  const codeVerifier = cookieStore.get('hs_pkce_verifier')?.value;

  if (!code || !state || state !== storedState || !codeVerifier) {
    return NextResponse.redirect(new URL('/login?error=invalid_state', request.url));
  }

  try {
    const oidcConfig = await fetchOidcConfig(OIDC_ISSUER_URL);
    const tokens = await exchangeCode({ code, codeVerifier, tokenEndpoint: oidcConfig.token_endpoint });

    const sessionExpiry = new Date(Date.now() + (tokens.expires_in ?? 3600) * 1000);
    const sessionOpts = {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax' as const,
      path: '/',
    };

    cookieStore.set('hs_session', tokens.access_token, { ...sessionOpts, expires: sessionExpiry });

    if (tokens.refresh_token) {
      const refreshExpiry = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000);
      cookieStore.set('hs_refresh', tokens.refresh_token, { ...sessionOpts, expires: refreshExpiry });
    }

    cookieStore.delete('hs_pkce_verifier');
    cookieStore.delete('hs_pkce_state');

    return NextResponse.redirect(new URL('/', request.url));
  } catch (err) {
    console.error('Token exchange error:', err);
    return NextResponse.redirect(new URL('/login?error=token_exchange_failed', request.url));
  }
}
