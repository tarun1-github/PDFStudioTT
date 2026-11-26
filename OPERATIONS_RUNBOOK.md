# Operations Runbook – PDF Studio

## 1. Health & Monitoring Endpoints
| Endpoint | Purpose | Healthy Signal |
|---|---|---|
| `GET /health` | API liveness | `{"status": "ok"}` |
| `GET /health/db` | MSSQL `CPDB.pdfstudio` connectivity & TLS mode | `"connected": true`, `"schema_exists": true` |
| `GET /health/dependencies` | LibreOffice, storage root, disk space (`disk_free_gb`), OIDC flag | `"libreoffice_installed": true`, `"storage_ready": true` |
| `GET /health/operations` | Backlog (`queued_jobs`), active (`processing_jobs`), `failed_jobs`, `oldest_queued_seconds`, `sql_pool` | `failed_jobs` stable, `oldest_queued_seconds < 120` |

## 2. Recommended Alert Thresholds (Proposed for Approval)
- **API / Dashboard Down**: 2 consecutive failed HTTP health checks (30s interval).
- **Worker Stopped**: `queued_jobs > 0` AND `oldest_queued_seconds > 180` with `processing_jobs == 0`.
- **SQL Connection Failure**: `/health/db` returns `"connected": false`.
- **Low Disk Space**: `disk_free_gb < 10.0` (Warning), `< 5.0` (Critical).
- **Repeated Job Failures**: `failed_jobs` increases by >= 5 within 15 minutes.

## 3. Incident Response & Service Control
```powershell
cd E:\Projects\PDFStudio\app
.\scripts\stop_all.ps1
.\scripts\test_mssql.ps1
.\scripts\start_all.ps1
```
Logs are located at `E:\Projects\PDFStudio\data\logs\api.log`, `worker.log`, and `dashboard.log`.
