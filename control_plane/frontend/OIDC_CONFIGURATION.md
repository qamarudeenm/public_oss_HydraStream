# OIDC Provider Configuration Guide

This document describes how to configure an OIDC provider for the HydraStream Control Plane frontend.

## Flow Overview

The frontend uses the **Authorization Code flow with PKCE** (RFC 7636). No client secret is required for public clients (PKCE-only). A client secret is supported for confidential clients.

```
Browser → GET /api/auth/login
  → (generates code_verifier + code_challenge, sets cookies)
  → redirect to {OIDC_ISSUER_URL}/authorize?...

OIDC Provider → user authenticates → redirect to /api/auth/callback?code=...

Browser → GET /api/auth/callback
  → exchanges code for tokens (server-side, includes code_verifier)
  → sets httpOnly session cookie (hs_session)
  → redirect to /

Browser → GET / (authenticated)
  → proxy.ts reads hs_session cookie → passes request
```

## Required Provider Configuration

### Redirect URIs (must be registered)

| Environment | Redirect URI |
|-------------|-------------|
| Local dev   | `http://localhost:3000/api/auth/callback` |
| Production  | `https://your-domain.com/api/auth/callback` |

### Scopes

Request the following scopes: `openid email profile`

### Grant Type

Enable: `authorization_code`

### PKCE

Enable PKCE (`S256` code challenge method). Most providers enable this by default for public clients.

## Environment Variables

Copy `.env.local.example` to `.env.local` and set:

```bash
OIDC_ISSUER_URL=https://your-provider.example.com
OIDC_CLIENT_ID=hydrastream-frontend
OIDC_CLIENT_SECRET=                          # optional for PKCE-only
OIDC_REDIRECT_URI=http://localhost:3000/api/auth/callback
```

## Provider-Specific Notes

### Google Identity Platform (Production)

Google Identity Platform is the production OIDC provider for HydraStream. It uses standard
Google OAuth 2.0 endpoints, so no Firebase SDK is required.

**Setup steps:**

1. In GCP Console → APIs & Services → Credentials → Create OAuth client ID
2. Application type: **Web application**
3. Name: `hydrastream-frontend`
4. Authorized redirect URIs: `https://control-plane.hydrastream.dev/api/auth/callback`
   - Also add `http://localhost:3000/api/auth/callback` for local development
5. Note the **Client ID** (format: `<numbers>-<hash>.apps.googleusercontent.com`)

**Environment variables:**

```bash
OIDC_ISSUER_URL=https://accounts.google.com
OIDC_CLIENT_ID=<numbers>-<hash>.apps.googleusercontent.com
OIDC_CLIENT_SECRET=   # leave empty for PKCE-only public client
OIDC_REDIRECT_URI=https://control-plane.hydrastream.dev/api/auth/callback
```

**Backend variables** (must match the same client ID):

```bash
CONTROL_PLANE_OIDC_ISSUER_URL=https://accounts.google.com
CONTROL_PLANE_OIDC_AUDIENCE=<numbers>-<hash>.apps.googleusercontent.com
```

Google ID tokens have `aud = client_id`, so the backend audience must equal `OIDC_CLIENT_ID`.

**Google Identity Platform in GCP Console:**
- Navigate to: APIs & Services → Identity Platform (or Firebase Auth in Firebase Console)
- Enable Email/Password and Google Sign-In providers as needed
- The OAuth consent screen must be configured (OAuth consent screen → External or Internal)

### Keycloak

1. Create a realm (e.g., `hydrastream`)
2. Create a client with `Client ID = hydrastream-frontend`
3. Set `Client authentication = Off` (public client) for PKCE-only
4. Add redirect URI: `http://localhost:3000/api/auth/callback`
5. Set issuer: `https://keycloak.example.com/realms/hydrastream`

The backend expects the audience claim to be `hydrastream-control-plane`. Configure this in the Keycloak client scope or as an audience mapper.

### Auth0

1. Create an application (type: Regular Web Application or SPA)
2. Set callback URL: `http://localhost:3000/api/auth/callback`
3. Set issuer: `https://your-tenant.auth0.com`
4. Configure the API audience (`hydrastream-control-plane`) and ensure access tokens include it

### Okta

1. Create an application (type: Web or SPA)
2. Set sign-in redirect URI: `http://localhost:3000/api/auth/callback`
3. Set issuer: `https://your-tenant.okta.com/oauth2/default`

## Development / Test Mode (Auth Bypass)

For local development without an OIDC provider:

```bash
# .env.local
AUTH_DISABLED=true
```

Also set on the backend:
```bash
CONTROL_PLANE_AUTH_DISABLED=true
```

Playwright tests automatically bypass auth by injecting a fake `hs_session` cookie. The backend must run with `CONTROL_PLANE_AUTH_DISABLED=true` for tests to pass, since the token value is not validated.

## Security Notes

- Tokens are stored in **httpOnly cookies** — inaccessible to JavaScript
- PKCE prevents authorization code interception attacks
- The `hs_session` cookie is delivered to the client via `/api/auth/session` (same-origin only)
- Set `OIDC_REDIRECT_URI` to your production domain in production environments
- Cookie `secure` flag is automatically set in `NODE_ENV=production`
