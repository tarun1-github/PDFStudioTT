# Production TLS Validation (`DB_TRUST_SERVER_CERTIFICATE=no`)

## Current Status: **BLOCKED** (Pending SQL Server Root CA Certificate)
- Strict Mode A (`DB_ENCRYPT=yes`, `DB_TRUST_SERVER_CERTIFICATE=no`) was tested via `test_strict_tls_fails_closed_without_ca_and_redacts_secrets` and **fails closed** with ODBC Error `08001 / -2146893019` (`certificate chain was issued by an authority that is not trusted`) without silently falling back to `TrustServerCertificate=yes`.

## Transition Procedure
1. Obtain the SQL Server Root CA `.cer` from your DBA/PKI team.
2. Import into Windows `Cert:\LocalMachine\Root`:
   ```powershell
   Import-Certificate -FilePath C:\path\to\sql-root-ca.cer -CertStoreLocation Cert:\LocalMachine\Root
   ```
3. Confirm the server certificate SAN includes `10.106.44.20` (or update `DB_SERVER` to the DNS FQDN).
4. Set `DB_ENCRYPT=yes` and `DB_TRUST_SERVER_CERTIFICATE=no` in `E:\Projects\PDFStudio\app\.env`.
5. Validate connectivity, Alembic, and health:
   ```powershell
   .\scripts\test_mssql.ps1
   .\.venv\Scripts\python.exe -m alembic current
   ```
