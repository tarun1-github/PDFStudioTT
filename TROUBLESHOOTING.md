# Troubleshooting Guide

## 1. ODBC Driver 18 SSL Certificate Error (`-2146893019`)
**Symptom**: `SSL Provider: The certificate chain was issued by an authority that is not trusted.`
**Cause**: `DB_TRUST_SERVER_CERTIFICATE=no` with a SQL Server certificate not in the Windows Trusted Root store.
**Fix**: Import the SQL Server CA certificate into Windows Trusted Root Certification Authorities, or for dev/internal servers set `DB_TRUST_SERVER_CERTIFICATE=yes` in `.env`.

## 2. LibreOffice Missing for DOCX/XLSX/PPTX
**Symptom**: `LibreOffice (soffice.exe) is not installed on this machine.`
**Fix**: Install LibreOffice:
```powershell
winget install TheDocumentFoundation.LibreOffice
```

## 3. FastAPI Backend Offline in Dashboard
**Symptom**: `Cannot reach the FastAPI backend.`
**Fix**: Run `.\scripts\start_api.ps1` and verify `http://127.0.0.1:8000/health` returns `{"status": "ok"}`.

## 4. Permission Denied on `pdfstudio` Schema
**Fix**: Have a DBA execute the `GRANT` script in [DATABASE_SETUP.md](DATABASE_SETUP.md).
