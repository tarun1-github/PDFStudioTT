# Pilot UAT Plan – PDF Studio

## Scope & Roles
UAT validates all 11 core workflows across three RBAC roles:
- **Engineer** (`engineer1`): Upload, convert, compile, Learning Book Creator, PDF Manager, personal storage, read shared library, processing history.
- **Team Lead** (`lead1`): All Engineer capabilities plus publishing approved documents to Shared Library and viewing team jobs.
- **Admin** (`admin1`): User management, role assignment, audit log inspection, application settings, and operational health checks.

## Automated UAT Execution
```powershell
cd E:\Projects\PDFStudio\app
.\.venv\Scripts\python.exe -m pytest tests\test_pilot_uat.py tests\test_document_conversion.py -v
```

## Expected Results & Rollback
- All UAT API, RBAC (`401`/`403`/`200`), PDF output validation, and Office conversion tests pass with 0 failures.
- **Rollback**: Stop pilot services via `.\scripts\stop_all.ps1`; no destructive database changes are made during UAT.
