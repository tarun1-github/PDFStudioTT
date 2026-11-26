# SQL Credential Rotation Procedure (`pdfstudio_app`)

## Rules
- Never place passwords in scripts, logs, or Git.
- Always validate the new credential before retiring the old one (or schedule a brief maintenance window).

## Rotation Steps
1. **Generate Strong Secret**: Generate a new 24+ character password in your approved secret manager / vault.
2. **Update SQL Server Login** (executed by DBA in `master`):
   ```sql
   ALTER LOGIN [pdfstudio_app] WITH PASSWORD = N'<FROM_VAULT>';
   ```
3. **Update Application Host**: Update `DB_PASSWORD` in `E:\Projects\PDFStudio\app\.env` (restricted NTFS ACLs to the service account and Administrators only).
4. **Verify All Components**:
   ```powershell
   cd E:\Projects\PDFStudio\app
   .\scripts\test_mssql.ps1
   .\.venv\Scripts\python.exe -m alembic current
   .\scripts\stop_all.ps1
   .\scripts\start_all.ps1
   ```
   Confirm `GET http://127.0.0.1:8000/health/db` returns `"connected": true`.
5. **Rollback**: Revert `DB_PASSWORD` in `.env` and `ALTER LOGIN [pdfstudio_app] WITH PASSWORD = N'<PREVIOUS_VAULT_SECRET>'`, then restart services.
