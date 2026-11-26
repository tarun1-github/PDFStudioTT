# PDF Studio – Team Document Publishing Platform

Enterprise team platform for converting images and documents, compiling mixed formats, publishing Learning Books with cover/TOC/bookmarks, and managing team PDFs backed by Microsoft SQL Server (`CPDB.pdfstudio`).

## Architecture
- **Frontend**: Streamlit (`frontend/streamlit_app.py`, `frontend/app_pages/`)
- **Backend API**: FastAPI + Uvicorn (`backend/main.py`)
- **Background Worker**: MSSQL-backed queue (`backend/worker/runner.py`)
- **Database**: Microsoft SQL Server (`CPDB`, schema `pdfstudio`) via SQLAlchemy, `pyodbc`, ODBC Driver 18, and Alembic
- **Storage**: Isolated per-user and shared folders under `E:\Projects\PDFStudio\data`

## Quick Start (Windows 11)
```powershell
cd E:\Projects\PDFStudio\app
.\scripts\setup_environment.ps1
.\scripts\install_dependencies.ps1
.\scripts\create_directories.ps1
.\scripts\test_mssql.ps1
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -c "from backend.database.session import db_transaction; from backend.database.init_db import seed_database; db_ctx = db_transaction(); db = db_ctx.__enter__(); seed_database(db); db_ctx.__exit__(None, None, None)"
.\scripts\start_all.ps1
```

## Documentation
- [INSTALLATION.md](INSTALLATION.md)
- [DATABASE_SETUP.md](DATABASE_SETUP.md)
- [WINDOWS_DEPLOYMENT.md](WINDOWS_DEPLOYMENT.md)
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- [SECURITY.md](SECURITY.md)
- [USER_GUIDE.md](USER_GUIDE.md)
