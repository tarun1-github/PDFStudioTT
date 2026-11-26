# MSSQL Load Test Plan (`CPDB.pdfstudio`)

## Objective
Validate real Microsoft SQL Server (`10.106.44.20:1433`, `CPDB.pdfstudio`) concurrency, row-lock job claiming (`UPDLOCK, READPAST, ROWLOCK`), SQLAlchemy connection pooling (`pool_size=10, max_overflow=10`), worker throughput, retry handling, and cleanup across **3, 8, 15, and 20 concurrent users**.

## Safety & Isolation Rules
- Every run creates unique `load_<run_id>_<i>` test users and writes files into an isolated temporary `STORAGE_ROOT`.
- Existing business users, jobs, and documents are never modified or deleted.
- The `finally:` block deletes **only** `AuditLog`, `GeneratedDocument`, `PdfJob`, and `User` records created during the test run.

## Execution Command
```powershell
cd E:\Projects\PDFStudio\app
.\.venv\Scripts\python.exe -m pytest tests\test_mssql_load.py -v -s
```
