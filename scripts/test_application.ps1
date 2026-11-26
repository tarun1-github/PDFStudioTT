$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $PSScriptRoot
Set-Location $AppRoot
$Py = "$AppRoot\.venv\Scripts\python.exe"

if (-not (Test-Path $Py)) {
    throw "Virtual environment missing. Run scripts\setup_environment.ps1 first."
}

& $Py -m pytest tests -v
