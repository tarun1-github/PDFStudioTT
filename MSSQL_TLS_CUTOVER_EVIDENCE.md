# MSSQL TLS Cutover Evidence (`CPDB` on `10.106.44.20:1433`)

- **Owner**: SQL Server DBA & Windows Infrastructure Administrator
- **Status**: **BLOCKED** (Mode A `DB_TRUST_SERVER_CERTIFICATE=no` fails without Root CA)
- **Date Completed (Fail-Closed Verification)**: 2026-11-26
- **Outstanding Dependency**: Install SQL Server Root CA certificate into `Cert:\LocalMachine\Root`.

## Verification Checks
| Check | Status | Evidence |
|---|---|---|
| `Cert:\LocalMachine\Root` SQL CA Check | **NOT PRESENT** | `Get-ChildItem Cert:\LocalMachine\Root` returned no SQL/`10.106.44.20` CA cert |
| Mode A Fail-Closed Behavior | **VERIFIED** | `test_strict_tls_fails_closed_without_ca_and_redacts_secrets` (PASSED) |
| Mode B Authorized Test Mode | **ACTIVE (TEST ONLY)** | `test_mssql_live_connectivity_and_schema` (PASSED) |
| Live Mode A App / Worker / Alembic / `/health/db` | **BLOCKED** | Awaiting CA certificate installation & `.env` switch to `DB_TRUST_SERVER_CERTIFICATE=no` |
