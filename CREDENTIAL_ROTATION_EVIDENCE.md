# SQL Credential Rotation Evidence (`pdfstudio_app`)

- **Owner**: SQL Server DBA & Application Owner
- **Status**: **PENDING**
- **Date Completed (Procedure & Redaction)**: 2026-11-26
- **Outstanding Dependency**: DBA execution of `ALTER LOGIN [pdfstudio_app]` and secret vault update.

## Verification Checklist
| Check | Status | Evidence |
|---|---|---|
| Rotation Procedure Documented | **COMPLETED** | [SQL_CREDENTIAL_ROTATION.md](SQL_CREDENTIAL_ROTATION.md) |
| Secret Redaction in Logs/Errors | **VERIFIED** | `test_strict_tls_fails_closed_without_ca_and_redacts_secrets` (PASSED) |
| New `pdfstudio_app` Credential Tested (App/Worker/API/Alembic) | **PENDING** | Awaiting DBA rotation |
| Rollback Readiness | **DOCUMENTED** | [SQL_CREDENTIAL_ROTATION.md](SQL_CREDENTIAL_ROTATION.md) |
