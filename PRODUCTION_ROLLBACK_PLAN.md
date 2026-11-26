# Production Rollback Plan – PDF Studio

## Trigger Conditions
Rollback immediately if after cutover:
- `/health/db` fails authentication or TLS validation.
- OIDC login fails for valid corporate identities.
- Background worker fails > 20% of valid jobs.

## Rollback Steps
1. **Stop Services**:
   ```powershell
   cd E:\Projects\PDFStudio\app
   .\scripts\stop_all.ps1
   # Or if NSSM services are registered:
   # nssm stop PDFStudio-Dashboard; nssm stop PDFStudio-Worker; nssm stop PDFStudio-API
   ```
2. **Database**: Do **not** drop `pdfstudio` tables. If a schema migration caused a regression, run `.\.venv\Scripts\python.exe -m alembic downgrade -1` (or restore `CPDB` from pre-cutover backup per `BACKUP_RECOVERY_TEST_PLAN.md`).
3. **Configuration**: Restore previous `.env` from the IT secret vault and revert `OIDC_ENABLED` / `DB_TRUST_SERVER_CERTIFICATE` only if authorized for pilot fallback.
4. **Verify**: Run `.\scripts\test_mssql.ps1` and `.\scripts\start_all.ps1`.
