# Install bei-governor as a Windows Task Scheduler task that starts on login.
# Run this once: pwsh -File scripts/merge_governor/install_autostart.ps1

$TaskName = "bei-governor"
$Description = "BEI ERP AI Merge Governor — auto-starts on login, auto-restarts on crash"
$RepoDir = "F:\Dropbox\Projects\BEI-ERP"
$PythonExe = "C:\Users\Sam\AppData\Local\Programs\Python\Python312\python.exe"
$DopplerExe = "C:\Users\Sam\bin\doppler.exe"

# Build the launch command that fetches API key from Doppler and runs governor
$LaunchScript = @"
`$env:ANTHROPIC_API_KEY = & '$DopplerExe' secrets get ANTHROPIC_API_KEY --plain --project bei-erp --config dev
Set-Location '$RepoDir'
& '$PythonExe' -m scripts.merge_governor.governor_erp
"@

$ScriptPath = "$RepoDir\scripts\merge_governor\start_governor.ps1"
$LaunchScript | Out-File -FilePath $ScriptPath -Encoding utf8

# Remove existing task if present
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing task: $TaskName"
}

# Create the scheduled task
$Action = New-ScheduledTaskAction `
    -Execute "pwsh.exe" `
    -Argument "-WindowStyle Hidden -File `"$ScriptPath`"" `
    -WorkingDirectory $RepoDir

$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Description $Description `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -RunLevel Highest

Write-Host ""
Write-Host "Installed: $TaskName"
Write-Host "  Trigger: At logon"
Write-Host "  Restarts: 3 attempts, 1 min interval"
Write-Host "  Script: $ScriptPath"
Write-Host ""
Write-Host "To start now:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "To stop:       Stop-ScheduledTask -TaskName '$TaskName'"
Write-Host "To remove:     Unregister-ScheduledTask -TaskName '$TaskName'"
