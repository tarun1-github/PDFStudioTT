# Phase 11 Go-Live Checklist – PDF Studio

| # | Control / Workstream | Owner | Status | Evidence | Date Completed | Outstanding Dependency |
|---|---|---|---|---|---|---|
| 1 | Corporate OIDC / SSO Cutover | Identity & App Team | **PENDING / BLOCKED** | Code & unit tests pass (`test_security_hardening.py`); `OIDC_ENABLED=false` in `.env` | Code: 2026-11-26 | Approved corporate IdP Issuer, Client ID, Redirect URIs, Group IDs |
| 2 | Strict MSSQL TLS (`Mode A`) | DBA & Windows Admin | **BLOCKED** | Fail-closed verified (`test_strict_tls_fails_closed_without_ca_and_redacts_secrets`); no SQL Root CA in `Cert:\LocalMachine\Root` | Fail-closed: 2026-11-26 | Install SQL Server Root CA in `Cert:\LocalMachine\Root` & set `DB_TRUST_SERVER_CERTIFICATE=no` |
| 3 | `pdfstudio_app` Credential Rotation | DBA & App Owner | **PENDING** | Procedure documented (`SQL_CREDENTIAL_ROTATION.md`) & redaction verified | Doc: 2026-11-26 | DBA `ALTER LOGIN` + vault update |
| 4 | Windows Services (NSSM) & Least-Privilege Account | Windows Infra / IT | **PENDING** | Startup/shutdown scripts hardened (`scripts/*.ps1`); NSSM not installed | Scripts: 2026-11-26 | Install NSSM, create `SVC_PDFStudio`, lock `.env` ACLs |
| 5 | Firewall Rule (TCP `8501` only) | IT Network / Security | **PENDING** | Port `8000` bound to `127.0.0.1` | 2026-11-26 | Written IT firewall approval for TCP `8501` |
| 6 | End-to-End Functional & Load Baseline | QA / App Team | **COMPLETED (Pilot)** | 29/29 pytest tests passing; 20-user MSSQL load validated | 2026-11-26 | Re-run E2E with live corporate OIDC + Mode A TLS |
