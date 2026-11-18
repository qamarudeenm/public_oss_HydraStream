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

import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { AUTH_DISABLED, OIDC_ISSUER_URL, exchangeRefreshToken, fetchOidcConfig } from '@/lib/auth';

export async function GET() {
  if (AUTH_DISABLED) {
    return NextResponse.json({ token: 'dev-bypass-token', disabled: true });
  }

  const cookieStore = await cookies();
  const sessionToken = cookieStore.get('hs_session')?.value;

  if (sessionToken) {
    return NextResponse.json({ token: sessionToken });
  }

  const refreshTokenValue = cookieStore.get('hs_refresh')?.value;
  if (!refreshTokenValue) {
    return NextResponse.json({ token: null });
  }

  try {
    const oidcConfig = await fetchOidcConfig(OIDC_ISSUER_URL);
    const tokens = await exchangeRefreshToken({
      refreshToken: refreshTokenValue,
      tokenEndpoint: oidcConfig.token_endpoint,
    });

    const sessionExpiry = new Date(Date.now() + (tokens.expires_in ?? 3600) * 1000);
    cookieStore.set('hs_session', tokens.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      expires: sessionExpiry,
    });

    if (tokens.refresh_token) {
      cookieStore.set('hs_refresh', tokens.refresh_token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        path: '/',
        expires: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000),
      });
    }

    return NextResponse.json({ token: tokens.access_token });
  } catch {
    cookieStore.delete('hs_refresh');
    return NextResponse.json({ token: null });
  }
}
