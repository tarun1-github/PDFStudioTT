# Installation Guide

## Prerequisites
1. **Windows 11** (x64)
2. **Python 3.12+ x64** (`python --version`)
3. **Microsoft ODBC Driver 18 for SQL Server** (`Get-OdbcDriver -Name "*ODBC Driver 18*"`)
4. **LibreOffice** (required for `DOCX`, `XLSX`, `PPTX`, `HTML` conversion):
   ```powershell
   winget install TheDocumentFoundation.LibreOffice
   ```

## Steps
1. Create and verify the virtual environment:
   ```powershell
   cd E:\Projects\PDFStudio\app
   .\scripts\setup_environment.ps1
   ```
2. Install Python dependencies (includes `streamlit[pdf]` / `streamlit-pdf` for inline PDF previews):
   ```powershell
   .\scripts\install_dependencies.ps1
   ```
3. Initialize storage directories:
   ```powershell
   .\scripts\create_directories.ps1
   ```
4. Configure `.env` (copy from `.env.example` if starting fresh) with MSSQL credentials.
5. Run database setup and migrations (see [DATABASE_SETUP.md](DATABASE_SETUP.md)).
6. Run automated tests:
   ```powershell
   .\scripts\test_application.ps1
   ```
