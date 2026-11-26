$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $PSScriptRoot
$Py = "$AppRoot\.venv\Scripts\python.exe"

if (-not (Test-Path $Py)) {
    throw "Virtual environment missing. Run scripts\setup_environment.ps1 first."
}

& $Py -m pip install --upgrade pip
& $Py -m pip install -r "$AppRoot\requirements.txt"
