# Database Setup (MSSQL)

PDF Studio uses the existing `CPDB` database on `10.106.44.20:1433` with a dedicated `pdfstudio` schema.

## Tables Created in `pdfstudio`
1. `pdfstudio.users`
2. `pdfstudio.roles`
3. `pdfstudio.user_roles`
4. `pdfstudio.pdf_jobs`
5. `pdfstudio.uploaded_files`
6. `pdfstudio.generated_documents`
7. `pdfstudio.shared_documents`
8. `pdfstudio.audit_logs`
9. `pdfstudio.application_settings`

## Least-Privilege DBA Provisioning Script
If the application SQL account lacks schema/table permissions, run the following as a DBA in `CPDB`:

```sql
USE CPDB;
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'pdfstudio')
BEGIN
    EXEC('CREATE SCHEMA pdfstudio');
END
GO

-- Grant least-privilege rights on the pdfstudio schema only
GRANT SELECT, INSERT, UPDATE, DELETE, ALTER, REFERENCES ON SCHEMA::pdfstudio TO [pdfstudio_app];
GRANT CREATE TABLE TO [pdfstudio_app];
GO
```

## Verify Connectivity & Run Migrations
```powershell
cd E:\Projects\PDFStudio\app
.\scripts\test_mssql.ps1
.\.venv\Scripts\python.exe -m alembic upgrade head
```

## TLS Certificate Note (ODBC Driver 18)
ODBC Driver 18 enables `Encrypt=yes` by default. If your SQL Server uses an internal/self-signed certificate:
- **Recommended for production**: Install the SQL Server root CA certificate into Windows **Local Computer > Trusted Root Certification Authorities**.
- **Development/testing**: Set `DB_TRUST_SERVER_CERTIFICATE=yes` in `.env`.
