$ErrorActionPreference = "Continue"
$AppRoot = Split-Path -Parent $PSScriptRoot
Set-Location $AppRoot
$EnvFile = "$AppRoot\.env"
$Py = "$AppRoot\.venv\Scripts\python.exe"

Write-Host "=== PDF Studio Production Readiness Validation (Non-Destructive) ===" -ForegroundColor Cyan

if (-not (Test-Path $EnvFile)) {
    Write-Host "[FAIL] .env file missing at $EnvFile" -ForegroundColor Red
    exit 1
}

$envLines = Get-Content $EnvFile
function Get-EnvFlag([string]$key) {
    $m = $envLines | Where-Object { $_ -match "^\s*$key\s*=" } | Select-Object -First 1
    if (-not $m) { return "" }
    return ($m -split "=", 2)[1].Trim()
}

# 1. OIDC Configuration Presence (never print secrets)
$oidcEnabled = (Get-EnvFlag "OIDC_ENABLED").ToLower()
$oidcIssuer = Get-EnvFlag "OIDC_ISSUER"
$oidcClient = Get-EnvFlag "OIDC_CLIENT_ID"
$appEnv = (Get-EnvFlag "APP_ENV").ToLower()
if ($oidcEnabled -eq "true" -and $oidcIssuer -and $oidcClient -and $appEnv -eq "production") {
    Write-Host "[PASS] OIDC configuration present and APP_ENV=production" -ForegroundColor Green
} else {
    Write-Host "[NOT CONFIGURED] Corporate OIDC/SSO (OIDC_ENABLED='$oidcEnabled', APP_ENV='$appEnv')" -ForegroundColor Yellow
}

# 2. SQL CA Certificate Presence in Cert:\LocalMachine\Root
$caCert = Get-ChildItem Cert:\LocalMachine\Root -ErrorAction SilentlyContinue | Where-Object {
    $_.Subject -like "*SQL*" -or $_.Subject -like "*10.106.44.20*" -or $_.Subject -like "*CPDB*"
}
if ($caCert) {
    Write-Host "[PASS] SQL Server CA certificate found in Cert:\LocalMachine\Root" -ForegroundColor Green
} else {
    Write-Host "[BLOCKED] No SQL Server Root CA certificate found in Cert:\LocalMachine\Root" -ForegroundColor Yellow
}

# 3. Strict TLS Mode & DB Connectivity (never expose credentials)
$dbTsc = (Get-EnvFlag "DB_TRUST_SERVER_CERTIFICATE").ToLower()
if ($dbTsc -ne "no" -and $dbTsc -ne "false" -and $dbTsc -ne "0") {
    Write-Host "[BLOCKED] Strict TLS not enabled (DB_TRUST_SERVER_CERTIFICATE='$dbTsc'; production requires 'no')" -ForegroundColor Yellow
} else {
    & $Py -c "import sys; from backend.database.connection import check_database_health; r=check_database_health(); print('[PASS] Strict TLS DB connectivity verified' if r.get('connected') else '[FAIL] Strict TLS DB check failed: ' + str(r.get('error'))); sys.exit(0 if r.get('connected') else 1)"
}

# 4. NSSM & Windows Services Status
$nssm = Get-Command nssm -ErrorAction SilentlyContinue
$svcs = Get-Service -Name "PDFStudio*" -ErrorAction SilentlyContinue
if ($nssm -and $svcs -and ($svcs | Where-Object { $_.Status -eq "Running" }).Count -ge 3) {
    Write-Host "[PASS] NSSM installed and PDFStudio services running" -ForegroundColor Green
} else {
    Write-Host "[NOT CONFIGURED] NSSM services not installed/running (nssm=$([bool]$nssm), services=$(@($svcs).Count))" -ForegroundColor Yellow
}

# 5. TCP 8501 Firewall Rule Status
$fw8501 = Get-NetFirewallRule -Enabled True -Direction Inbound -ErrorAction SilentlyContinue |
    Get-NetFirewallPortFilter -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -eq "8501" }
if ($fw8501) {
    Write-Host "[PASS] Inbound firewall rule for TCP 8501 is enabled" -ForegroundColor Green
} else {
    Write-Host "[NOT CONFIGURED] Approved inbound firewall rule for TCP 8501 not found" -ForegroundColor Yellow
}

# 6. Port 8000 External Exposure Check
$fw8000 = Get-NetFirewallRule -Enabled True -Direction Inbound -Action Allow -ErrorAction SilentlyContinue |
    Get-NetFirewallPortFilter -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -eq "8000" }
$listen8000 = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalAddress -ne "127.0.0.1" -and $_.LocalAddress -ne "::1" }
if ($fw8000 -or $listen8000) {
    Write-Host "[FAIL] Port 8000 appears externally exposed or allowed on firewall" -ForegroundColor Red
} else {
    Write-Host "[PASS] Port 8000 is not externally exposed" -ForegroundColor Green
}
