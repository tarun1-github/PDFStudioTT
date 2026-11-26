$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $PSScriptRoot
Set-Location $AppRoot
$Py = "$AppRoot\.venv\Scripts\python.exe"
$LogDir = "E:\Projects\PDFStudio\data\logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

if (-not (Test-Path $Py)) { throw "Virtual environment missing. Run scripts\setup_environment.ps1 first." }
if (-not (Test-Path "$AppRoot\.env")) { throw ".env file missing at $AppRoot\.env" }

$dup = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*$AppRoot*" -and $_.CommandLine -like "*backend.worker.runner*"
}
if ($dup) {
    Write-Warning "Worker already running (PID $($dup[0].ProcessId)). Skipping duplicate worker startup."
    exit 0
}

Write-Host "Starting PDF Studio Background Worker..." -ForegroundColor Cyan
& $Py -m backend.worker.runner 2>&1 | Tee-Object -FilePath "$LogDir\worker.log" -Append
