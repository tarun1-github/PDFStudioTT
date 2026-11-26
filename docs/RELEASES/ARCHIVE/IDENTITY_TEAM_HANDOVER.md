# Identity Team Handover Checklist – Corporate OIDC / SSO

## Required From Corporate Identity Team
- [ ] Approved `OIDC_ISSUER` URL (supporting `.well-known/openid-configuration` and JWKS)
- [ ] Approved `OIDC_CLIENT_ID` (Authorization Code Flow with PKCE `S256`)
- [ ] Registered `OIDC_REDIRECT_URI` (`https://<host-or-ip>:8501/...`) and post-logout redirect URI
- [ ] Required scopes: `openid profile email`
- [ ] Group claim name (`OIDC_ROLE_CLAIM`, default `groups`) and object/group IDs for:
  - `OIDC_GROUP_ENGINEER`
  - `OIDC_GROUP_TEAM_LEAD`
  - `OIDC_GROUP_ADMIN`
- [ ] Approved token & session TTL (`SESSION_TTL_MINUTES`)

## Evidence Application Owner Must Collect
- Screenshot/log of successful `Engineer`, `Team Lead`, and `Admin` OIDC logins (without tokens/secrets).
- Verification that `X-Username` dev header returns `401` when `APP_ENV=production`.
- Signed sign-off in [CORPORATE_SSO_VALIDATION.md](CORPORATE_SSO_VALIDATION.md).
