# Architecture Overview

- **Frontend**: Streamlit (`0.0.0.0:8502`, `frontend/streamlit_app.py`, `frontend/app_pages/`)
- **Backend API**: FastAPI + Uvicorn (`127.0.0.1:8010`, `backend/main.py`, `backend/routers/`)
- **Background Worker**: MSSQL-backed queue (`backend/worker/runner.py`) with `UPDLOCK, READPAST, ROWLOCK`
- **Database**: Microsoft SQL Server `CPDB`, schema `pdfstudio` (16 tables managed by Alembic `0001_initial` + `0002_governance`)
- **Storage**: `E:\Projects\PDFStudio\data` (`users/`, `shared/`, `temp/`, `templates/`, `logs/`)
