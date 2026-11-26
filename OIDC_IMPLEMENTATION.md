# Corporate OIDC / SSO Implementation Guide

## Architecture (`backend/security/oidc.py`, `backend/security/auth.py`, `backend/routers/auth.py`)
- **Flow**: Authorization Code Flow with PKCE (`S256`) via `generate_pkce_pair()` and `build_authorization_url()`.
- **Discovery & JWKS**: `fetch_oidc_discovery()` caches `.well-known/openid-configuration`; `verify_oidc_jwt()` validates RS256/ES256 signatures via `PyJWKClient`.
- **Claims & Fail-Closed Validation**: Requires and validates `iss`, `aud`, `exp`, `sub`, and `nonce`. Any invalid/expired/tampered token raises an error and returns `401 Unauthorized`.
- **Group-to-Role Mapping (Anti-Escalation)**: `map_groups_to_roles()` maps only explicitly configured `OIDC_GROUP_ADMIN`, `OIDC_GROUP_TEAM_LEAD`, and `OIDC_GROUP_ENGINEER` claims. Unmapped groups fail closed with `403 Forbidden`.
- **Session & Logout**: `POST /api/auth/logout` clears the `HttpOnly`, `SameSite=Lax`, `Secure` `pdfstudio_session` cookie.
- **Dev Isolation**: `X-Username` header auth is rejected (`401`) whenever `APP_ENV != "development"` or `OIDC_ENABLED=true`.

## Configuration Placeholders (`.env.example`)
Set `OIDC_ENABLED=true`, `APP_ENV=production`, and populate `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_AUDIENCE`, `OIDC_JWKS_URI`, `OIDC_REDIRECT_URI`, and `OIDC_GROUP_*` from your approved corporate IdP.
