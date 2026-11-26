# Backup & Recovery Test Plan (Non-Destructive)

## 1. Backup Scope
1. **MSSQL (`CPDB`, schema `pdfstudio`)**: Daily full backup + 15-minute transaction log backups (30-day retention).
2. **Personal Storage (`E:\Projects\PDFStudio\data\users\`)**: Daily incremental VSS/robocopy backup (30-day retention).
3. **Shared Library (`E:\Projects\PDFStudio\data\shared\`)**: Daily snapshot + versioned archive (90-day retention).
4. **Configuration**: `app\` source, `alembic/`, `scripts/`, and `.env.example` in Git; production `.env` secrets stored in IT secret vault.

## 2. Non-Destructive Recovery Drill Procedure
*Never run destructive restore tests against live `CPDB`.*
1. **Database**: Restore the latest `CPDB` backup to an **isolated staging/sandbox SQL instance** (e.g. `CPDB_RESTORE_TEST`) and verify all 9 tables in `pdfstudio` (`SELECT COUNT(*) FROM pdfstudio.users`, `pdfstudio.pdf_jobs`, `pdfstudio.generated_documents`).
2. **Personal & Shared Storage**: Restore `users/` and `shared/` snapshots to a temporary verification directory (`E:\Projects\PDFStudio\data_restore_test\`) and verify sample PDFs open cleanly with `pypdf.PdfReader`.
3. **Configuration**: Reconstruct `.env` from `.env.example` + vault secrets and run `.\scripts\test_mssql.ps1` against the staging target.

## 3. Rollback
Remove temporary staging directory `E:\Projects\PDFStudio\data_restore_test\` and drop the temporary staging database `CPDB_RESTORE_TEST` after verification.
