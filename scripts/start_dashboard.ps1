$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $PSScriptRoot
Set-Location $AppRoot
$Py = "$AppRoot\.venv\Scripts\python.exe"
$LogDir = "E:\Projects\PDFStudio\data\logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

if (-not (Test-Path $Py)) { throw "Virtual environment missing. Run scripts\setup_environment.ps1 first." }
if (-not (Test-Path "$AppRoot\.env")) { throw ".env file missing at $AppRoot\.env" }

$envLines = Get-Content "$AppRoot\.env"
$appHost = (($envLines | Where-Object { $_ -match "^\s*APP_HOST\s*=" } | Select-Object -First 1) -split "=", 2)[1].Trim()
$appPort = [int]((($envLines | Where-Object { $_ -match "^\s*APP_PORT\s*=" } | Select-Object -First 1) -split "=", 2)[1].Trim())
if (-not $appHost) { $appHost = "0.0.0.0" }
if (-not $appPort) { $appPort = 8502 }

$existing = Get-NetTCPConnection -LocalPort $appPort -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    Write-Warning "Port $appPort is already in use (PID $($existing[0].OwningProcess)). Skipping duplicate Dashboard startup."
    exit 0
}

Write-Host "Starting PDF Studio Dashboard on ${appHost}:${appPort}..." -ForegroundColor Cyan
& $Py -m streamlit run frontend\streamlit_app.py --server.address $appHost --server.port $appPort --server.headless true 2>&1 | Tee-Object -FilePath "$LogDir\dashboard.log" -Append
