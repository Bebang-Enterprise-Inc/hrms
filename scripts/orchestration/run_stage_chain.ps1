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

function Resolve-AbsolutePath {
    param([string]$Path, [string]$BaseDir)
    if ([string]::IsNullOrWhiteSpace($Path)) {
        return ""
    }
    if ([System.IO.Path]::IsPathRooted($Path)) {
        return (Resolve-Path $Path).Path
    }
    return (Resolve-Path (Join-Path $BaseDir $Path)).Path
}

function New-UtcNow {
    return (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
}

function Write-AutoChainStatus {
    param(
        [hashtable]$State,
        [string]$JsonPath,
        [string]$MdPath
    )

    $State | ConvertTo-Json -Depth 8 | Set-Content $JsonPath

    $lines = @()
    $lines += "# AutoChain Status"
    $lines += ""
    $lines += "- run_unit: $($State.run_unit)"
    $lines += "- run_type: $($State.run_type)"
    $lines += "- current_stage: $($State.current_stage)"
    $lines += "- gate: $($State.gate)"
    $lines += "- next_stage: $($State.next_stage)"
    $lines += "- next_action: $($State.next_action)"
    $lines += "- plan_path: $($State.plan_path)"
    $lines += "- reason: $($State.reason)"
    $lines += "- updated_utc: $($State.updated_utc)"
    $lines += ""
    $lines += "## Stage Results"
    $lines += ""
    $lines += "| stage | exit_code | status | log_path | finished_utc |"
    $lines += "|---|---:|---|---|---|"
    foreach ($stage in @("audit", "execute", "deploy", "e2e", "closeout")) {
        if ($State.stages.ContainsKey($stage)) {
            $s = $State.stages[$stage]
            $lines += "| $stage | $($s.exit_code) | $($s.status) | $($s.log_path) | $($s.finished_utc) |"
        } else {
            $lines += "| $stage | - | - | - | - |"
        }
    }

    $lines | Set-Content $MdPath
}

function Invoke-CodexStage {
    param(
        [string]$Stage,
        [string]$Prompt,
        [string]$WorkspaceDir,
        [string]$RunDir,
        [int]$StageTimeoutMins,
        [int]$StallTimeoutMins,
        [int]$PollSeconds,
        [int]$MaxReworkHits
    )

    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $stdoutLogPath = Join-Path $RunDir ("AUTOCHAIN_{0}_{1}.log" -f $Stage, $stamp)
    $stderrLogPath = Join-Path $RunDir ("AUTOCHAIN_{0}_{1}.stderr.log" -f $Stage, $stamp)

    $codexCmd = Get-Command codex -ErrorAction SilentlyContinue
    if (-not $codexCmd) {
        @(
            ("stage={0}" -f $Stage),
            "result=codex-not-found"
        ) | Set-Content $stdoutLogPath

        return @{
            stage = $Stage
            exit_code = 127
            status = "NO-GO"
            log_path = $stdoutLogPath
            stderr_log_path = $stderrLogPath
            termination_reason = "codex-not-found"
            finished_utc = (New-UtcNow)
        }
    }

    $wrapper = @"
`$ErrorActionPreference = 'Stop'
`$prompt = [Environment]::GetEnvironmentVariable('AUTOCHAIN_PROMPT')
if ([string]::IsNullOrWhiteSpace(`$prompt)) {
    Write-Error 'AUTOCHAIN_PROMPT missing'
    exit 127
}
codex exec `$prompt -s danger-full-access -C '$WorkspaceDir'
exit `$LASTEXITCODE
"@

    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($wrapper))
    $proc = Start-Process -FilePath "pwsh" -ArgumentList @(
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-EncodedCommand", $encoded
    ) -WorkingDirectory $WorkspaceDir -WindowStyle Hidden -RedirectStandardOutput $stdoutLogPath -RedirectStandardError $stderrLogPath -Environment @{ AUTOCHAIN_PROMPT = $Prompt } -PassThru

    $startedAt = Get-Date
    $lastGrowthAt = $startedAt
    [long]$lastSize = 0
    [int]$reworkHits = 0
    $terminationReason = "completed"

    while (-not $proc.HasExited) {
        Start-Sleep -Seconds $PollSeconds
        $now = Get-Date

        $stdoutLen = if (Test-Path $stdoutLogPath) { (Get-Item $stdoutLogPath).Length } else { 0 }
        $stderrLen = if (Test-Path $stderrLogPath) { (Get-Item $stderrLogPath).Length } else { 0 }
        $size = $stdoutLen + $stderrLen
        if ($size -gt $lastSize) {
            $lastSize = $size
            $lastGrowthAt = $now
        }

        $tail = if (Test-Path $stdoutLogPath) {
            Get-Content -Path $stdoutLogPath -Tail 80 -ErrorAction SilentlyContinue | Out-String
        } else {
            ""
        }

        if ($tail -match "(?i)rework loop active|missing packet handoff|no commit beyond base") {
            $reworkHits += 1
        }

        if (($now - $startedAt).TotalMinutes -ge $StageTimeoutMins) {
            $terminationReason = "stage-timeout"
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            break
        }

        if (($now - $lastGrowthAt).TotalMinutes -ge $StallTimeoutMins) {
            $terminationReason = "log-stall-timeout"
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            break
        }

        if ($reworkHits -ge $MaxReworkHits) {
            $terminationReason = "rework-loop-detected"
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            break
        }
    }

    try { $proc.Refresh() } catch {}
    $exitCode = if ($terminationReason -eq "completed") { $proc.ExitCode } else { 124 }
    $outputText = ""
    if (Test-Path $stdoutLogPath) {
        $outputText += (Get-Content -Raw $stdoutLogPath)
    }
    if (Test-Path $stderrLogPath) {
        $outputText += "`n" + (Get-Content -Raw $stderrLogPath)
    }

    $reportedStatus = if ($outputText -match "(?im)^Status:\s*(GO|NO-GO)\b") {
        $Matches[1].Trim().ToUpperInvariant()
    } elseif ($exitCode -eq 0) {
        "GO"
    } else {
        "NO-GO"
    }

    return @{
        stage = $Stage
        exit_code = $exitCode
        status = $reportedStatus
        log_path = $stdoutLogPath
        stderr_log_path = $stderrLogPath
        termination_reason = $terminationReason
        finished_utc = (New-UtcNow)
    }
}

$workspaceAbs = Resolve-AbsolutePath -Path $Workspace -BaseDir (Get-Location).Path
$planAbs = if ([string]::IsNullOrWhiteSpace($PlanPath)) { "" } else { Resolve-AbsolutePath -Path $PlanPath -BaseDir $workspaceAbs }
$runDir = Join-Path $workspaceAbs ("output/agent-runs/{0}" -f $RunUnit)
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$statusJson = Join-Path $runDir "AUTOCHAIN_STATUS.json"
$statusMd = Join-Path $runDir "AUTOCHAIN_STATUS.md"
$lockJson = Join-Path $runDir "AUTOCHAIN_LOCK.json"

$state = @{
    run_unit = $RunUnit
    run_type = $RunType
    plan_path = if ($planAbs) { $planAbs } else { "<not-provided>" }
    current_stage = $StartFrom
    gate = "IN_PROGRESS"
    next_stage = $StartFrom
    next_action = "launch $StartFrom"
    reason = "autochain launched"
    started_utc = (New-UtcNow)
    updated_utc = (New-UtcNow)
    stages = @{}
}

@{
    run_unit = $RunUnit
    lock_owner = "validator-release"
    status = "running"
    stage = $StartFrom
    updated_at = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssK")
    workspace = $workspaceAbs
    plan_path = $state.plan_path
    runner_pid = $PID
} | ConvertTo-Json -Depth 5 | Set-Content $lockJson

Write-AutoChainStatus -State $state -JsonPath $statusJson -MdPath $statusMd

$stageOrder = @("audit", "execute", "deploy", "e2e", "closeout")
$startIndex = [Array]::IndexOf($stageOrder, $StartFrom)
$stopIndex = [Array]::IndexOf($stageOrder, $StopAfter)
if ($startIndex -lt 0 -or $stopIndex -lt 0 -or $stopIndex -lt $startIndex) {
    throw "Invalid stage range: $StartFrom -> $StopAfter"
}
$stagesToRun = $stageOrder[$startIndex..$stopIndex]

$prompts = @{
    audit = "Use /plan-audit-bei-erp on `"$($state.plan_path)`". Update output artifacts under output/agent-runs/$RunUnit and end with lines: Status: and Decision needed:."
    execute = "Use /execute-plan-bei-erp for run unit `"$RunUnit`". Continue execution and update output/agent-runs/$RunUnit artifacts. End with lines: Status: and Decision needed:."
    deploy = "Use /deploy for run unit `"$RunUnit`". Continue from integration through deploy and update output/agent-runs/$RunUnit artifacts. End with lines: Status: and Decision needed:."
    e2e = "Use /e2e-test for run unit `"$RunUnit`" after deploy. Write evidence under output/agent-runs/$RunUnit and end with lines: Status: and Decision needed:."
    closeout = "Finalize closeout for run unit `"$RunUnit`". Update output/agent-runs/$RunUnit artifacts and end with lines: Status: and Decision needed:."
}

foreach ($stage in $stagesToRun) {
    $state.current_stage = $stage
    $state.next_stage = $stage
    $state.next_action = "launch $stage"
    $state.reason = "running $stage"
    $state.updated_utc = (New-UtcNow)
    Write-AutoChainStatus -State $state -JsonPath $statusJson -MdPath $statusMd

    $result = Invoke-CodexStage -Stage $stage -Prompt $prompts[$stage] -WorkspaceDir $workspaceAbs -RunDir $runDir -StageTimeoutMins $StageTimeoutMinutes -StallTimeoutMins $StallTimeoutMinutes -PollSeconds $PollIntervalSeconds -MaxReworkHits $MaxReworkLoopHits
    $state.stages[$stage] = $result
    $state.updated_utc = (New-UtcNow)

    if ($result.exit_code -ne 0 -or $result.status -eq "NO-GO") {
        $state.gate = "NO-GO"
        $state.reason = "stage $stage failed"
        $state.next_stage = "none"
        $state.next_action = "none"
        Write-AutoChainStatus -State $state -JsonPath $statusJson -MdPath $statusMd

        @(
            ("stage={0}" -f $stage),
            ("exit_code={0}" -f $result.exit_code),
            ("status={0}" -f $result.status),
            ("reason={0}" -f $result.termination_reason)
        ) | Add-Content (Join-Path $runDir ("AUTOCHAIN_{0}.log" -f (Get-Date -Format "yyyyMMdd")))

        @(
            ("run_unit={0}" -f $RunUnit),
            "lock_owner=validator-release",
            "status=stopped",
            ("stage={0}" -f $stage),
            ("updated_at={0}" -f (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssK"))
        ) | Out-Null

        @{
            run_unit = $RunUnit
            lock_owner = "validator-release"
            status = "stopped"
            stage = $stage
            updated_at = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssK")
            workspace = $workspaceAbs
            plan_path = $state.plan_path
            runner_pid = $PID
        } | ConvertTo-Json -Depth 5 | Set-Content $lockJson

        Write-Host ("AUTOCHAIN_GATE={0}" -f $state.gate)
        exit 1
    }
}

$state.gate = "GO"
$state.current_stage = $StopAfter
$state.next_stage = "none"
$state.next_action = "none"
$state.reason = "all requested stages completed"
$state.updated_utc = (New-UtcNow)
Write-AutoChainStatus -State $state -JsonPath $statusJson -MdPath $statusMd

@{
    run_unit = $RunUnit
    lock_owner = "validator-release"
    status = "completed"
    stage = $StopAfter
    updated_at = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssK")
    workspace = $workspaceAbs
    plan_path = $state.plan_path
    runner_pid = $PID
} | ConvertTo-Json -Depth 5 | Set-Content $lockJson

Write-Host ("AUTOCHAIN_GATE={0}" -f $state.gate)
