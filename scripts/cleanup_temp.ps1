$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $PSScriptRoot
Set-Location $AppRoot
$Py = "$AppRoot\.venv\Scripts\python.exe"

if (-not (Test-Path $Py)) {
    throw "Virtual environment missing. Run scripts\setup_environment.ps1 first."
}

& $Py -c "from backend.security.storage import cleanup_temp_files; print('Removed temp files:', cleanup_temp_files(24))"
