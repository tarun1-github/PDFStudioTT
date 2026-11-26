$ErrorActionPreference = "Stop"
$TaskName = "PDFStudio-TestEnvironment"
$VbsPath = "E:\Projects\PDFStudio\app\scripts\start_pdfstudio.vbs"

if (-not (Test-Path $VbsPath)) {
    throw "Launcher VBS not found at $VbsPath"
}

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Scheduled task '$TaskName' already exists. Updating..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$VbsPath`"" -WorkingDirectory "E:\Projects\PDFStudio\app"
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 0) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "PDF Studio Test Environment (API 8010, Worker, Streamlit 8502)" `
    -ErrorAction Stop

Write-Host "Registered scheduled task '$TaskName' successfully." -ForegroundColor Green
