# Corporate SSO / OIDC Validation Record

- **Owner**: Corporate Identity Team & Application Security Engineer
- **Status**: **PENDING** (OIDC remains disabled: `OIDC_ENABLED=false`, `APP_ENV=development`)
- **Date Completed (Code & Mocked RS256 Validation)**: 2026-11-26
- **Outstanding Dependency**: Approved corporate Identity Provider configuration.

## Required Corporate IdP Inputs (Checklist)
- [ ] `OIDC_ISSUER` (Issuer URL)
- [ ] `OIDC_CLIENT_ID`
- [ ] `OIDC_REDIRECT_URI` & Logout Redirect URI
- [ ] Required scopes (`openid profile email`)
- [ ] Group claim name (`OIDC_ROLE_CLAIM`, e.g., `groups`)
- [ ] `OIDC_GROUP_ENGINEER`, `OIDC_GROUP_TEAM_LEAD`, `OIDC_GROUP_ADMIN`
- [ ] Token & session expiry policy (`SESSION_TTL_MINUTES`)

## Validation Matrix
| Check | Automated Test Evidence | Live IdP Evidence |
|---|---|---|
| Engineer / Team Lead / Admin Role Mapping | `test_oidc_jwt_validation_and_fail_closed` (PASSED) | Pending live IdP |
| Expired Token / Invalid Signature / Issuer / Audience | `test_oidc_jwt_validation_and_fail_closed` (PASSED) | Pending live IdP |
| Unmapped Group Anti-Escalation (`403`) | `test_oidc_jwt_validation_and_fail_closed` (PASSED) | Pending live IdP |
| Logout & Session Cookie Clearing | `test_production_rejects_dev_header_and_logout_clears_cookie` (PASSED) | Pending live IdP |
| Dev Header Rejected in `APP_ENV=production` | `test_production_rejects_dev_header_and_logout_clears_cookie` (PASSED) | Pending live IdP |
