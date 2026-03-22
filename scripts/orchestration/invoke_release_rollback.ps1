[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RunUnit,
    [string]$Workspace = "F:/Dropbox/Projects/BEI-ERP",
    [string]$ReportPath = "",
    [string]$SiteName = "hq.bebang.ph",
    [string[]]$BackendServices = @("frappe_backend", "scheduler", "queue-short", "queue-long"),
    [string]$DatabaseBackup = "",
    [string]$PublicFilesArchive = "",
    [string]$PrivateFilesArchive = "",
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-AbsolutePath {
    param(
        [string]$Path,
        [string]$BaseDir
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return ""
    }

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $BaseDir $Path))
}

function New-UtcNow {
    return (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

function Get-RunUnitArtifactPrefix {
    param([string]$Value)

    if ($Value -match '^(s\d{3})') {
        return $Matches[1].ToUpperInvariant()
    }

    return "RUN"
}

function Invoke-Step {
    param(
        [string]$Label,
        [string]$Command,
        [switch]$Execute
    )

    $result = [ordered]@{
        label = $Label
        command = $Command
        status = if ($Execute) { "executed" } else { "planned" }
        output = ""
    }

    if ($Execute) {
        $output = & pwsh -NoLogo -NoProfile -NonInteractive -Command $Command 2>&1
        if ($LASTEXITCODE -ne 0) {
            $result.status = "failed"
            $result.output = ($output | Out-String).Trim()
            return $result
        }

        $result.output = ($output | Out-String).Trim()
    }

    return $result
}

$workspaceAbs = Resolve-AbsolutePath -Path $Workspace -BaseDir (Get-Location).Path
$runDir = Join-Path $workspaceAbs ("output/agent-runs/{0}" -f $RunUnit)
$backendDir = Join-Path $runDir "backend-integration"
New-Item -ItemType Directory -Force -Path $backendDir | Out-Null

$artifactPrefix = Get-RunUnitArtifactPrefix -Value $RunUnit
$reportAbs = if ([string]::IsNullOrWhiteSpace($ReportPath)) {
    Join-Path $backendDir ("{0}_ROLLBACK_REPORT.json" -f $artifactPrefix)
} else {
    Resolve-AbsolutePath -Path $ReportPath -BaseDir $workspaceAbs
}

$steps = @()
foreach ($service in $BackendServices) {
    $steps += Invoke-Step -Label ("rollback_backend::{0}" -f $service) -Command ("docker service rollback {0}" -f $service) -Execute:$Apply
}

$steps += Invoke-Step -Label "rollback_frontend::vercel" -Command "vercel rollback" -Execute:$Apply

if (-not [string]::IsNullOrWhiteSpace($DatabaseBackup)) {
    $restoreCommand = "bench --site {0} restore {1}" -f $SiteName, $DatabaseBackup
    if (-not [string]::IsNullOrWhiteSpace($PublicFilesArchive)) {
        $restoreCommand += " --with-public-files {0}" -f $PublicFilesArchive
    }
    if (-not [string]::IsNullOrWhiteSpace($PrivateFilesArchive)) {
        $restoreCommand += " --with-private-files {0}" -f $PrivateFilesArchive
    }

    $steps += Invoke-Step -Label "rollback_database::restore" -Command $restoreCommand -Execute:$Apply
    $steps += Invoke-Step -Label "rollback_database::migrate" -Command ("bench --site {0} migrate" -f $SiteName) -Execute:$Apply
}

$failedSteps = @($steps | Where-Object { $_.status -eq "failed" })
$report = [ordered]@{
    run_unit = $RunUnit
    generated_utc = New-UtcNow
    mode = if ($Apply) { "apply" } else { "dry-run" }
    site_name = $SiteName
    backend_services = $BackendServices
    database_backup = $DatabaseBackup
    public_files_archive = $PublicFilesArchive
    private_files_archive = $PrivateFilesArchive
    status = if ($failedSteps.Count -gt 0) { "FAIL" } else { "PASS" }
    blocking_next_action = if ($failedSteps.Count -gt 0) { [string]$failedSteps[0].label } else { "none" }
    steps = $steps
}

$report | ConvertTo-Json -Depth 8 | Set-Content -Path $reportAbs

Write-Host ("ROLLBACK_STATUS={0}" -f $report.status)
Write-Host ("ROLLBACK_REPORT={0}" -f $reportAbs)

if ($report.status -ne "PASS") {
    exit 1
}

exit 0
