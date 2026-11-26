# Security & Corporate OIDC Implementation Plan

## 1. Current Authentication Mode (Development Only)
- When `APP_ENV=development` and `OIDC_ENABLED=false`, requests authenticate via the `X-Username` header in `backend/security/auth.py`.
- Outside `APP_ENV=development`, header authentication is **strictly rejected** (`401 Unauthorized`).

## 2. Corporate OIDC / SSO Implementation Plan (Required for Production)
1. **Identity Provider Discovery**: Configure `OIDC_ISSUER` (e.g., Microsoft Entra ID / Okta / Keycloak) and fetch `.well-known/openid-configuration` on startup.
2. **Authorization Code Flow + PKCE**: Enable Streamlit's native `st.login()` / `[auth]` OIDC configuration (or reverse-proxy OIDC) using `OIDC_CLIENT_ID` with PKCE (`S256`).
3. **JWKS Signature Verification**: Cache the IdP's `jwks_uri` keys in FastAPI (`PyJWT` / `authlib`) and verify RS256/ES256 signatures on every `Authorization: Bearer <token>` request.
4. **Claims Validation**: Enforce `iss == OIDC_ISSUER`, `aud == OIDC_CLIENT_ID`, and `exp > now()`.
5. **User-to-Role Mapping**: Map IdP `groups` / `roles` claims to `pdfstudio.roles` (`Engineer`, `Team Lead`, `Admin`), provisioning `pdfstudio.users` by `external_subject` (`sub`).
6. **Logout & Session Expiration**: Clear Streamlit session state and redirect to the IdP `end_session_endpoint` on logout; enforce token `exp` in FastAPI.

## 3. File Storage & Audit Controls
- Per-user isolation under `E:\Projects\PDFStudio\data\users\<storage_folder>\` with `resolve_safe_path` traversal protection.
- Extension allowlist, `MAX_UPLOAD_MB` cap, and file-signature validation (`%PDF-`, `PK`).
- Audit events recorded in `pdfstudio.audit_logs` for uploads, PDF generation, shared publishing, user/role/setting changes, and job failures (never logging passwords, tokens, or file contents).
