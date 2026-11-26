# Production Deployment & Hardening Runbook

## 1. Windows Service Account & Directory ACLs
- Run `PDFStudio-API`, `PDFStudio-Worker`, and `PDFStudio-Dashboard` under a dedicated **least-privilege Windows service account** (e.g., `SVC_PDFStudio`).
- Grant `SVC_PDFStudio` Modify access **only** to `E:\Projects\PDFStudio\data\` and Read/Execute access to `E:\Projects\PDFStudio\app\`. Restrict `E:\Projects\PDFStudio\app\.env` ACLs to `Administrators` and `SVC_PDFStudio` only.

## 2. Service Startup Order & NSSM Policy
1. `PDFStudio-API` (`127.0.0.1:8000` — internal only, never exposed on firewall)
2. `PDFStudio-Worker` (`backend.worker.runner` — single process, `MAX_CONCURRENT_JOBS=3`)
3. `PDFStudio-Dashboard` (`0.0.0.0:8501` — exposed only after IT firewall approval for TCP `8501`)
- Configure NSSM `AppRestartDelay 5000`, `AppExit Default Restart`, and log rotation (`AppRotateFiles 1`, `AppRotateBytes 10485760` -> `E:\Projects\PDFStudio\data\logs\`).
- `scripts/start_all.ps1` and `scripts/stop_all.ps1` enforce port/process duplicate checks and graceful termination.
