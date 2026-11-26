# DBA Team Handover Checklist – Strict TLS & Credential Rotation

## Required From DBA Team
- [ ] Export SQL Server Root CA certificate (`.cer`) for `10.106.44.20:1433` (`CPDB`) with SAN matching server address/FQDN.
- [ ] Rotate `pdfstudio_app` SQL login password (`ALTER LOGIN [pdfstudio_app] WITH PASSWORD = N'<FROM_VAULT>'`) and deliver via approved secret vault.
- [ ] Confirm `pdfstudio_app` retains least-privilege permissions on `CPDB.pdfstudio` only.

## Evidence Application Owner Must Collect
- `scripts/test_mssql.ps1` passing with `Mode A (Encrypted, Strict CA Certificate Validation)` (`DB_TRUST_SERVER_CERTIFICATE=no`).
- `alembic current` and `GET /health/db` returning `"connected": true`.
- Updated [MSSQL_TLS_CUTOVER_EVIDENCE.md](MSSQL_TLS_CUTOVER_EVIDENCE.md) and [CREDENTIAL_ROTATION_EVIDENCE.md](CREDENTIAL_ROTATION_EVIDENCE.md).
