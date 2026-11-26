# Windows Deployment, Pilot Operations & Backup Guide

## 1. Team Pilot Network & Concurrency Architecture (10–20 Users)
- **Streamlit Frontend**: Binds to `0.0.0.0:8501` (accessible on `http://10.106.44.24:8501` once IT approves the inbound TCP `8501` Windows Firewall rule).
- **FastAPI Backend**: Binds to `127.0.0.1:8000` (internal loopback only; not exposed directly to client browsers).
- **Background Worker**: Single worker process with `MAX_CONCURRENT_JOBS=3` and MSSQL `UPDLOCK, READPAST, ROWLOCK` row-locking.
- **SQL Connection Pool**: `pool_size=10`, `max_overflow=10`, `pool_pre_ping=True` (supports 20 concurrent pilot users).
- **Logs**: `E:\Projects\PDFStudio\data\logs\api.log`, `worker.log`, `dashboard.log`.

## 2. Startup & Shutdown
```powershell
cd E:\Projects\PDFStudio\app
.\scripts\start_all.ps1   # Checks ports 8000/8501 and worker PID to prevent duplicates
.\scripts\stop_all.ps1    # Stops all PDF Studio uvicorn/streamlit/worker processes
.\scripts\cleanup_temp.ps1 # Purges temp files older than 24 hours
```

## 3. Production TLS Transition Plan (`DB_TRUST_SERVER_CERTIFICATE=no`)
1. Obtain the SQL Server Root CA certificate from your DBA/PKI team.
2. Install into Windows **Local Computer > Trusted Root Certification Authorities** (`Cert:\LocalMachine\Root`).
3. Verify the certificate SAN matches `10.106.44.20` (or the SQL Server DNS name in `DB_SERVER`).
4. Update `.env`: set `DB_ENCRYPT=yes` and `DB_TRUST_SERVER_CERTIFICATE=no`.
5. Run `.\scripts\test_mssql.ps1` and confirm `tls_mode` reports **Mode A (Encrypted, Strict CA Certificate Validation)**.

## 4. Backup & Recovery Plan
- **MSSQL (`CPDB.pdfstudio`)**: Daily full database backup + 15-minute transaction log backups managed by SQL Server Agent (30-day retention).
- **Personal Storage (`E:\Projects\PDFStudio\data\users\`)**: Daily incremental robocopy/VSS snapshot to network backup storage (30-day retention).
- **Shared Library (`E:\Projects\PDFStudio\data\shared\`)**: Daily snapshot + versioned archive (90-day retention).
- **Configuration**: Back up `.env.example`, `alembic/`, and `scripts/` in Git (never commit `.env` or secrets; store production secrets in a privileged vault).
- **Recovery Procedure**: Restore `CPDB` to point-in-time -> restore `E:\Projects\PDFStudio\data\` -> verify `.\scripts\test_mssql.ps1` -> start services via `.\scripts\start_all.ps1`.

## 5. Windows Service Deployment (NSSM)
Register `PDFStudio-API`, `PDFStudio-Worker`, and `PDFStudio-Dashboard` with NSSM pointing to `E:\Projects\PDFStudio\app\.venv\Scripts\python.exe` with `WorkingDirectory = E:\Projects\PDFStudio\app` and automatic restart on failure.
