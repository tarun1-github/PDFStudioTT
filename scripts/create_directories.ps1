$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $PSScriptRoot
$Py = "$AppRoot\.venv\Scripts\python.exe"

if (-not (Test-Path $Py)) {
    throw "Virtual environment missing. Run scripts\setup_environment.ps1 first."
}

& $Py -c "from backend.security.storage import ensure_storage_layout; print('Storage initialized at:', ensure_storage_layout())"
