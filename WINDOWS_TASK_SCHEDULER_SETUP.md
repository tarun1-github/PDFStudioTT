# Windows Task Scheduler Setup (`PDFStudio-TestEnvironment`)

## Scripts
- [scripts/start_pdfstudio.bat](scripts/start_pdfstudio.bat) — Launches `start_all.ps1` and logs to `E:\Projects\PDFStudio\data\logs\startup.log`.
- [scripts/start_pdfstudio.vbs](scripts/start_pdfstudio.vbs) — Hidden launcher for Task Scheduler (`wscript.exe`).
- [scripts/stop_pdfstudio.bat](scripts/stop_pdfstudio.bat) — Gracefully stops only PDF Studio processes via `stop_all.ps1`.
- [scripts/check_pdfstudio.ps1](scripts/check_pdfstudio.ps1) — Verifies API (`8010`), MSSQL, Worker, and Dashboard (`8502`).
- [scripts/register_task_scheduler.ps1](scripts/register_task_scheduler.ps1) — Registers `PDFStudio-TestEnvironment` with `AtStartup` trigger, 3 restarts (1-min interval), and `MultipleInstances IgnoreNew`.

## Registration Status: **BLOCKED (Requires Elevated Administrator PowerShell)**
Running `Register-ScheduledTask` as `TT-WIN11\admin` (`IS_ADMIN: False`) returned `Access is denied (HRESULT 0x80070005)`.

## Exact Administrator Command to Complete Registration
Open an **Administrator** PowerShell prompt and run:
```powershell
cd E:\Projects\PDFStudio\app
.\scripts\register_task_scheduler.ps1
Get-ScheduledTask -TaskName "PDFStudio-TestEnvironment"
```
If the task must run without an interactive user session, specify `-User "SYSTEM"` or a dedicated least-privilege service account with "Log on as a batch job" rights.
