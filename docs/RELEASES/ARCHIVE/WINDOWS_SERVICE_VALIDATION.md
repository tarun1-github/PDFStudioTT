# Windows Service & Host Validation Record

- **Owner**: Windows Infrastructure / IT Operations
- **Status**: **PENDING**
- **Date Completed (PowerShell Scripts)**: 2026-11-26
- **Outstanding Dependency**: NSSM installation, `SVC_PDFStudio` service account creation, NTFS ACL lockdown, and IT firewall approval for TCP `8501`.

## Host Inspection Evidence (2026-11-26)
- `Get-Command nssm`: Not installed.
- `Get-Service -Name "PDFStudio*"`: No Windows services registered.
- PowerShell scripts (`start_api.ps1`, `start_worker.ps1`, `start_dashboard.ps1`, `start_all.ps1`, `stop_all.ps1`): Hardened with port/process duplicate checks and log files under `E:\Projects\PDFStudio\data\logs\`.
- API Binding: `127.0.0.1:8000` (internal only). Dashboard Binding: `0.0.0.0:8501`.
