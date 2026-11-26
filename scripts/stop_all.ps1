$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $PSScriptRoot

$procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*$AppRoot*" -and (
        $_.CommandLine -like "*uvicorn*" -or
        $_.CommandLine -like "*streamlit*" -or
        $_.CommandLine -like "*backend.worker.runner*"
    )
}

if (-not $procs) {
    Write-Host "No running PDF Studio processes found." -ForegroundColor Gray
    exit 0
}

foreach ($p in $procs) {
    Write-Host "Stopping PID $($p.ProcessId): $($p.Name)" -ForegroundColor Yellow
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}
Write-Host "All PDF Studio processes stopped." -ForegroundColor Green
