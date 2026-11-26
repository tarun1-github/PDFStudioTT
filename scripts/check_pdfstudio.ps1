$ErrorActionPreference = "Continue"
$AppRoot = Split-Path -Parent $PSScriptRoot
$envLines = Get-Content "$AppRoot\.env"
$apiPort = [int]((($envLines | Where-Object { $_ -match "^\s*API_PORT\s*=" } | Select-Object -First 1) -split "=", 2)[1].Trim())
$appPort = [int]((($envLines | Where-Object { $_ -match "^\s*APP_PORT\s*=" } | Select-Object -First 1) -split "=", 2)[1].Trim())
if (-not $apiPort) { $apiPort = 8010 }
if (-not $appPort) { $appPort = 8502 }

Write-Host "=== PDF Studio Health Check ===" -ForegroundColor Cyan
try {
    $api = Invoke-RestMethod -Uri "http://127.0.0.1:${apiPort}/health" -TimeoutSec 3
    Write-Host "[OK] API (127.0.0.1:${apiPort}): $($api.status)" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] API (127.0.0.1:${apiPort}) unreachable" -ForegroundColor Red
}

try {
    $db = Invoke-RestMethod -Uri "http://127.0.0.1:${apiPort}/health/db" -TimeoutSec 5
    Write-Host "[OK] MSSQL: connected=$($db.connected) schema_exists=$($db.schema_exists)" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] MSSQL health check failed" -ForegroundColor Red
}

$worker = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*$AppRoot*" -and $_.CommandLine -like "*backend.worker.runner*"
}
if ($worker) {
    Write-Host "[OK] Worker running (PID $($worker[0].ProcessId))" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Worker not running" -ForegroundColor Red
}

try {
    $dash = Invoke-WebRequest -Uri "http://127.0.0.1:${appPort}/_stcore/health" -UseBasicParsing -TimeoutSec 3
    Write-Host "[OK] Dashboard (0.0.0.0:${appPort}): $($dash.Content.Trim())" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Dashboard (port ${appPort}) unreachable" -ForegroundColor Red
}
