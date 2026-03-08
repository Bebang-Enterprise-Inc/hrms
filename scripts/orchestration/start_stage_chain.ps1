[CmdletBinding()]
param(
    [string]$PlanPath = "",
    [Parameter(Mandatory = $true)]
    [string]$RunUnit,
    [ValidateSet("auto", "run_id", "run_group_id")]
    [string]$RunType = "auto",
    [ValidateSet("audit", "execute", "deploy", "e2e", "closeout")]
    [string]$StartFrom = "audit",
    [ValidateSet("audit", "execute", "deploy", "e2e", "closeout")]
    [string]$StopAfter = "closeout",
    [ValidateRange(5, 180)]
    [int]$StageTimeoutMinutes = 45,
    [ValidateRange(2, 60)]
    [int]$StallTimeoutMinutes = 12,
    [ValidateRange(5, 120)]
    [int]$PollIntervalSeconds = 15,
    [ValidateRange(1, 20)]
    [int]$MaxReworkLoopHits = 6,
    [string]$Workspace = "F:/Dropbox/Projects/BEI-ERP"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$runner = Join-Path $scriptRoot "run_stage_chain.ps1"
if (-not (Test-Path $runner)) {
    throw "Missing runner script: $runner"
}

$workspaceAbs = (Resolve-Path $Workspace).Path
$runDir = Join-Path $workspaceAbs ("output/agent-runs/{0}" -f $RunUnit)
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$launchLogPath = Join-Path $runDir ("AUTOCHAIN_LAUNCH_{0}.log" -f $stamp)

$args = @(
    "-NoLogo",
    "-NoProfile",
    "-NonInteractive",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$runner`""
)
if (-not [string]::IsNullOrWhiteSpace($PlanPath)) {
    $args += @("-PlanPath", "`"$PlanPath`"")
}
$args += @(
    "-RunUnit", "`"$RunUnit`"",
    "-RunType", "$RunType",
    "-StartFrom", "$StartFrom",
    "-StopAfter", "$StopAfter",
    "-StageTimeoutMinutes", "$StageTimeoutMinutes",
    "-StallTimeoutMinutes", "$StallTimeoutMinutes",
    "-PollIntervalSeconds", "$PollIntervalSeconds",
    "-MaxReworkLoopHits", "$MaxReworkLoopHits",
    "-Workspace", "`"$Workspace`""
)

$argLine = $args -join " "
$pwshPath = (Get-Command pwsh -ErrorAction Stop).Source
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $pwshPath
$psi.Arguments = $argLine
$psi.WorkingDirectory = $workspaceAbs
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
$proc = [System.Diagnostics.Process]::Start($psi)
if (-not $proc) {
    throw "Failed to launch stage chain runner process."
}

@(
    ("launched_utc={0}" -f (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")),
    ("launcher_pid={0}" -f $PID),
    ("runner_pid={0}" -f $proc.Id),
    ("pwsh_path={0}" -f $pwshPath),
    ("runner_script={0}" -f $runner),
    ("arguments={0}" -f $argLine)
) | Set-Content $launchLogPath

$lockPath = Join-Path $runDir "AUTOCHAIN_LOCK.json"
@{
    run_unit = $RunUnit
    launcher_pid = $PID
    runner_pid = $proc.Id
    stage_timeout_minutes = $StageTimeoutMinutes
    stall_timeout_minutes = $StallTimeoutMinutes
    poll_interval_seconds = $PollIntervalSeconds
    max_rework_loop_hits = $MaxReworkLoopHits
    launch_log_path = $launchLogPath
    status = "launched"
    launched_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
} | ConvertTo-Json -Depth 5 | Set-Content $lockPath

Write-Host ("LAUNCHED_RUNNER_PID={0}" -f $proc.Id)
Write-Host ("LOCK_FILE={0}" -f $lockPath)
Write-Host ("LAUNCH_LOG={0}" -f $launchLogPath)
