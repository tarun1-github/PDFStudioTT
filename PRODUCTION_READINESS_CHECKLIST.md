# Production Readiness Checklist – PDF Studio

## Completed Controls (Pilot Verified)
- [x] **MSSQL Integration**: `CPDB.pdfstudio` schema and 9 tables created via Alembic (`0001_initial`).
- [x] **SQL Credential Redaction**: SQLAlchemy `creator=` pattern + `redact_sensitive()` prevents `UID`/`PWD` exposure in URLs, logs, and tracebacks.
- [x] **RBAC & Storage Isolation**: `Engineer`, `Team Lead`, `Admin` enforced in backend APIs; path traversal, invalid extensions, corrupt headers, and oversized uploads blocked.
- [x] **Audit Logging**: Uploads, PDF generation, shared publishing, user/role/setting updates, and job failures logged in `pdfstudio.audit_logs`.
- [x] **Office & PDF Processing**: Image-to-PDF, TXT/MD/DOCX/XLSX/PPTX/HTML-to-PDF (LibreOffice headless), PDF Compiler, Learning Book Creator, and PDF Manager verified.
- [x] **Operational Monitoring**: `/health`, `/health/db`, `/health/dependencies`, and `/health/operations` active.
- [x] **Windows Service Scripts**: Duplicate-process guards and file logging in `scripts/`.

## Pending Production Blockers (Must Complete Before Production Cutover)
- [ ] **Corporate OIDC / SSO**: Configure `OIDC_ENABLED=true`, `OIDC_ISSUER`, `OIDC_CLIENT_ID`, JWKS verification, and group-to-role mapping; set `APP_ENV=production` (disables `X-Username` dev auth).
- [ ] **Production TLS (`Mode A`)**: Install SQL Server Root CA certificate into `Cert:\LocalMachine\Root` and set `DB_TRUST_SERVER_CERTIFICATE=no` (with `DB_ENCRYPT=yes`).
- [ ] **Credential Rotation**: Rotate `pdfstudio_app` SQL password through DBA.
- [ ] **Windows Firewall & NSSM**: Obtain IT approval for inbound TCP `8501` and register NSSM Windows services.
