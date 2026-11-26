$ErrorActionPreference = "Stop"
$ScriptsDir = $PSScriptRoot
$AppRoot = Split-Path -Parent $ScriptsDir
$Py = "$AppRoot\.venv\Scripts\python.exe"
$LogDir = "E:\Projects\PDFStudio\data\logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

if (-not (Test-Path $Py)) { throw "Virtual environment missing." }
if (-not (Test-Path "$AppRoot\.env")) { throw ".env file missing." }

$envLines = Get-Content "$AppRoot\.env"
$apiHost = (($envLines | Where-Object { $_ -match "^\s*API_HOST\s*=" } | Select-Object -First 1) -split "=", 2)[1].Trim()
$apiPort = [int]((($envLines | Where-Object { $_ -match "^\s*API_PORT\s*=" } | Select-Object -First 1) -split "=", 2)[1].Trim())
$appHost = (($envLines | Where-Object { $_ -match "^\s*APP_HOST\s*=" } | Select-Object -First 1) -split "=", 2)[1].Trim()
$appPort = [int]((($envLines | Where-Object { $_ -match "^\s*APP_PORT\s*=" } | Select-Object -First 1) -split "=", 2)[1].Trim())
if (-not $apiHost) { $apiHost = "127.0.0.1" }
if (-not $apiPort) { $apiPort = 8010 }
if (-not $appHost) { $appHost = "0.0.0.0" }
if (-not $appPort) { $appPort = 8502 }

& "$ScriptsDir\create_directories.ps1"

$apiRunning = Get-NetTCPConnection -LocalPort $apiPort -State Listen -ErrorAction SilentlyContinue
if (-not $apiRunning) {
    Start-Process -FilePath $Py `
        -ArgumentList "-m", "uvicorn", "backend.main:app", "--host", $apiHost, "--port", "$apiPort" `
        -WorkingDirectory $AppRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput "$LogDir\api.out.log" `
        -RedirectStandardError "$LogDir\api.err.log"
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Seconds 1
        try {
            $r = Invoke-RestMethod -Uri "http://127.0.0.1:${apiPort}/health" -TimeoutSec 2
            if ($r.status -eq "ok") { break }
        } catch {}
    }
}

$workerRunning = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*$AppRoot*" -and $_.CommandLine -like "*backend.worker.runner*"
}
if (-not $workerRunning) {
    Start-Process -FilePath $Py `
        -ArgumentList "-m", "backend.worker.runner" `
        -WorkingDirectory $AppRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput "$LogDir\worker.out.log" `
        -RedirectStandardError "$LogDir\worker.err.log"
    Start-Sleep -Seconds 1
}

$dashRunning = Get-NetTCPConnection -LocalPort $appPort -State Listen -ErrorAction SilentlyContinue
if (-not $dashRunning) {
    Start-Process -FilePath $Py `
        -ArgumentList "-m", "streamlit", "run", "frontend\streamlit_app.py", "--server.address", $appHost, "--server.port", "$appPort", "--server.headless", "true" `
        -WorkingDirectory $AppRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput "$LogDir\dashboard.out.log" `
        -RedirectStandardError "$LogDir\dashboard.err.log"
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Seconds 1
        try {
            $d = Invoke-WebRequest -Uri "http://127.0.0.1:${appPort}/_stcore/health" -UseBasicParsing -TimeoutSec 2
            if ($d.StatusCode -eq 200) { break }
        } catch {}
    }
}

Write-Host "PDF Studio services started (API=${apiHost}:${apiPort}, Dashboard=${appHost}:${appPort})." -ForegroundColor Green
