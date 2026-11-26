$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $PSScriptRoot
Set-Location $AppRoot

Write-Host "Checking Python..." -ForegroundColor Cyan
python --version

if (-not (Test-Path "$AppRoot\.venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment at $AppRoot\.venv ..." -ForegroundColor Cyan
    python -m venv "$AppRoot\.venv"
} else {
    Write-Host "Virtual environment already exists at $AppRoot\.venv" -ForegroundColor Green
}

Write-Host "Checking ODBC Driver 18 for SQL Server..." -ForegroundColor Cyan
$odbc = Get-OdbcDriver -Name "*ODBC Driver 18 for SQL Server*" -ErrorAction SilentlyContinue
if (-not $odbc) {
    Write-Warning "ODBC Driver 18 for SQL Server was not detected. Install Microsoft ODBC Driver 18 before connecting to MSSQL."
} else {
    $odbc | Select-Object Name, Platform | Format-Table -AutoSize
}

Write-Host "Checking LibreOffice..." -ForegroundColor Cyan
$lo = Get-Command soffice -ErrorAction SilentlyContinue
if (-not $lo -and -not (Test-Path "C:\Program Files\LibreOffice\program\soffice.exe")) {
    Write-Warning "LibreOffice is not installed. Office (DOCX/XLSX/PPTX) conversion requires: winget install TheDocumentFoundation.LibreOffice"
} else {
    Write-Host "LibreOffice detected." -ForegroundColor Green
}
