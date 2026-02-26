param(
    [string]$TaskName = "BEI_Claude_Skill_Usage_Report",
    [string]$StartTime = "06:45"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$generatorScript = Join-Path $repoRoot "scripts\\generate_skill_usage_snapshot.ps1"

if (-not (Test-Path $generatorScript)) {
    throw "Generator script not found: $generatorScript"
}

$quotedScript = $generatorScript.Replace('"', '""')
$taskRun = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$quotedScript`""

$createArgs = @(
    "/Create",
    "/TN", $TaskName,
    "/TR", $taskRun,
    "/SC", "DAILY",
    "/ST", $StartTime,
    "/F"
)

& schtasks @createArgs | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create scheduled task '$TaskName'."
}

Write-Host "Scheduled task installed/updated: $TaskName"
Write-Host "Runs daily at: $StartTime"
Write-Host "Command: $taskRun"
Write-Host ""
& schtasks /Query /TN $TaskName /FO LIST /V
