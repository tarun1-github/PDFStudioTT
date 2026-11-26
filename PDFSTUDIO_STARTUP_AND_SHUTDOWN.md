# PDF Studio Startup and Shutdown Guide

## Start All Services
```powershell
cd E:\Projects\PDFStudio\app
.\scripts\start_pdfstudio.bat
```
Starts FastAPI (`127.0.0.1:8010`), waits for `/health`, starts the MSSQL background worker, and starts Streamlit (`0.0.0.0:8502`). Duplicate instances are automatically skipped.

## Health Check
```powershell
.\scripts\check_pdfstudio.ps1
```

## Stop All Services (Safe Isolation)
```powershell
.\scripts\stop_pdfstudio.bat
```
Stops only processes whose command line belongs to `E:\Projects\PDFStudio\app` (`uvicorn`, `streamlit`, `backend.worker.runner`). Unrelated processes (such as `PID 14840` on port `8000`) are never touched.
