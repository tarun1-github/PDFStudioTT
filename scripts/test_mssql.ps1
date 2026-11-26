$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $PSScriptRoot
Set-Location $AppRoot
$Py = "$AppRoot\.venv\Scripts\python.exe"
$EnvFile = "$AppRoot\.env"

Write-Host "=== PDF Studio MSSQL Connectivity & Configuration Check ===" -ForegroundColor Cyan

# 1. Confirm .env exists
if (-not (Test-Path $EnvFile)) {
    Write-Host "FAIL: .env file not found at $EnvFile" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] .env file found" -ForegroundColor Green

# 2. Confirm required DB keys exist without displaying values
$envContent = Get-Content $EnvFile
$requiredKeys = @("DB_SERVER", "DB_PORT", "DB_DATABASE", "DB_USER", "DB_PASSWORD", "DB_DRIVER", "DB_ENCRYPT", "DB_TRUST_SERVER_CERTIFICATE")
$missingKeys = @()
foreach ($key in $requiredKeys) {
    $line = $envContent | Where-Object { $_ -match "^\s*$key\s*=" } | Select-Object -First 1
    if (-not $line) {
        $missingKeys += $key
    }
}
if ($missingKeys.Count -gt 0) {
    Write-Host "FAIL: Missing required .env keys: $($missingKeys -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Required DB configuration keys present in .env (values hidden)" -ForegroundColor Green

# 3. Confirm ODBC Driver 18 is installed
$odbc18 = Get-OdbcDriver -Name "*ODBC Driver 18 for SQL Server*" -ErrorAction SilentlyContinue
if (-not $odbc18) {
    Write-Host "FAIL: ODBC Driver 18 for SQL Server is not installed." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] ODBC Driver 18 for SQL Server installed" -ForegroundColor Green

# 4. Confirm server and port reachable
$serverLine = ($envContent | Where-Object { $_ -match "^\s*DB_SERVER\s*=" } | Select-Object -First 1)
$portLine = ($envContent | Where-Object { $_ -match "^\s*DB_PORT\s*=" } | Select-Object -First 1)
$dbServer = ($serverLine -split "=", 2)[1].Trim()
$dbPort = [int](($portLine -split "=", 2)[1].Trim())
$tcp = Test-NetConnection -ComputerName $dbServer -Port $dbPort -WarningAction SilentlyContinue
if (-not $tcp.TcpTestSucceeded) {
    Write-Host "FAIL: TCP connection to ${dbServer}:${dbPort} failed." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] TCP connectivity to ${dbServer}:${dbPort} succeeded" -ForegroundColor Green

# 5. Test SQLAlchemy connection & SELECT @@SERVERNAME, DB_NAME(), GETDATE()
if (-not (Test-Path $Py)) {
    Write-Host "FAIL: Virtual environment missing at $Py" -ForegroundColor Red
    exit 1
}

$checkScript = @'
import json, sys
from backend.database.connection import check_database_health
res = check_database_health()
print(json.dumps(res, indent=2))
sys.exit(0 if res.get("connected") else 1)
'@

$checkScript | & $Py -
if ($LASTEXITCODE -eq 0) {
    Write-Host "PASS: MSSQL SQLAlchemy connection verified." -ForegroundColor Green
    exit 0
} else {
    Write-Host "FAIL: MSSQL SQLAlchemy connection failed. See sanitized error above." -ForegroundColor Red
    exit 1
}
