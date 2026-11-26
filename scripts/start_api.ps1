$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $PSScriptRoot
Set-Location $AppRoot
$Py = "$AppRoot\.venv\Scripts\python.exe"
$LogDir = "E:\Projects\PDFStudio\data\logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

if (-not (Test-Path $Py)) { throw "Virtual environment missing. Run scripts\setup_environment.ps1 first." }
if (-not (Test-Path "$AppRoot\.env")) { throw ".env file missing at $AppRoot\.env" }

$envLines = Get-Content "$AppRoot\.env"
$apiHost = (($envLines | Where-Object { $_ -match "^\s*API_HOST\s*=" } | Select-Object -First 1) -split "=", 2)[1].Trim()
$apiPort = [int]((($envLines | Where-Object { $_ -match "^\s*API_PORT\s*=" } | Select-Object -First 1) -split "=", 2)[1].Trim())
if (-not $apiHost) { $apiHost = "127.0.0.1" }
if (-not $apiPort) { $apiPort = 8010 }

$existing = Get-NetTCPConnection -LocalPort $apiPort -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    Write-Warning "Port $apiPort is already in use (PID $($existing[0].OwningProcess)). Skipping duplicate API startup."
    exit 0
}

Write-Host "Starting PDF Studio FastAPI on ${apiHost}:${apiPort}..." -ForegroundColor Cyan
& $Py -m uvicorn backend.main:app --host $apiHost --port $apiPort 2>&1 | Tee-Object -FilePath "$LogDir\api.log" -Append
