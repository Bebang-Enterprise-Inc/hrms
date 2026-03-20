[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RunUnit,
    [string]$Workspace = "F:/Dropbox/Projects/BEI-ERP",
    [string]$ReleasePairPath = "",
    [string]$ReportPath = "",
    [switch]$SkipFetch
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

function ConvertTo-Array {
    param($Value)

    if ($null -eq $Value) {
        return [object[]]@()
    }

    return [object[]]@($Value)
}

function Invoke-Git {
    param(
        [string]$RepoPath,
        [string[]]$Arguments
    )

    $output = & git -C $RepoPath @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw ("git {0} failed for {1}: {2}" -f ($Arguments -join " "), $RepoPath, (($output | Out-String).Trim()))
    }

    return (($output | Out-String).Trim())
}

function New-RuleResult {
    param(
        [string]$Rule,
        [string]$Status,
        [string]$Message
    )

    return [ordered]@{
        rule = $Rule
        status = $Status
        message = $Message
    }
}

$workspaceAbs = Resolve-AbsolutePath -Path $Workspace -BaseDir (Get-Location).Path
$runDir = Join-Path $workspaceAbs ("output/agent-runs/{0}" -f $RunUnit)
$releaseGateDir = Join-Path $runDir "release-gates"
New-Item -ItemType Directory -Force -Path $releaseGateDir | Out-Null

$artifactPrefix = Get-RunUnitArtifactPrefix -Value $RunUnit
$pairAbs = if ([string]::IsNullOrWhiteSpace($ReleasePairPath)) {
    Join-Path $releaseGateDir ("{0}_RELEASE_PAIR.json" -f $artifactPrefix)
} else {
    Resolve-AbsolutePath -Path $ReleasePairPath -BaseDir $workspaceAbs
}
$reportAbs = if ([string]::IsNullOrWhiteSpace($ReportPath)) {
    Join-Path $releaseGateDir ("{0}_RELEASE_PREFLIGHT_REPORT.json" -f $artifactPrefix)
} else {
    Resolve-AbsolutePath -Path $ReportPath -BaseDir $workspaceAbs
}

$report = [ordered]@{
    run_unit = $RunUnit
    checked_utc = New-UtcNow
    workspace = $workspaceAbs
    release_pair_path = $pairAbs
    report_path = $reportAbs
    status = "PASS"
    blocking_next_action = "none"
    rules = @()
    repos = @()
    sentinel_results = @()
}

$failures = [System.Collections.Generic.List[string]]::new()

function Add-Failure {
    param(
        [string]$Rule,
        [string]$Message
    )

    $report.rules += New-RuleResult -Rule $Rule -Status "FAIL" -Message $Message
    $failures.Add($Message) | Out-Null
}

function Add-Pass {
    param(
        [string]$Rule,
        [string]$Message
    )

    $report.rules += New-RuleResult -Rule $Rule -Status "PASS" -Message $Message
}

try {
    if (-not (Test-Path $pairAbs)) {
        Add-Failure -Rule "release_pair_present" -Message ("Missing release pair manifest: {0}" -f $pairAbs)
        throw "Missing release pair manifest"
    }

    $manifest = Get-Content -Raw -Path $pairAbs | ConvertFrom-Json -Depth 12
    Add-Pass -Rule "release_pair_present" -Message "Release pair manifest found."

    if (-not $manifest.release_ready) {
        Add-Failure -Rule "release_pair_release_ready" -Message "Release pair manifest is not marked release_ready=true."
    } else {
        Add-Pass -Rule "release_pair_release_ready" -Message "Release pair manifest is marked release-ready."
    }

    $repoEntries = ConvertTo-Array -Value $manifest.repos
    if ($repoEntries.Length -eq 0) {
        Add-Failure -Rule "release_pair_repos" -Message "Release pair manifest does not define any repos."
    }

    $sentinelEntries = ConvertTo-Array -Value $manifest.sentinel_results
    if ($sentinelEntries.Length -eq 0) {
        Add-Failure -Rule "release_pair_sentinels" -Message "Release pair manifest does not declare sentinel results."
    } else {
        Add-Pass -Rule "release_pair_sentinels" -Message ("Manifest declares {0} sentinel result(s)." -f $sentinelEntries.Length)
    }

    foreach ($repoEntry in $repoEntries) {
        $repoName = if ($repoEntry.name) { [string]$repoEntry.name } else { "unnamed-repo" }
        $repoPath = Resolve-AbsolutePath -Path ([string]$repoEntry.repo_path) -BaseDir $workspaceAbs
        $repoResult = [ordered]@{
            name = $repoName
            repo_path = $repoPath
            approved_lane_branch = [string]$repoEntry.approved_lane_branch
            canonical_branch = [string]$repoEntry.canonical_branch
            remote_ref = [string]$repoEntry.remote_ref
            expected_head_sha = [string]$repoEntry.expected_head_sha
            current_branch = ""
            head_sha = ""
            upstream_head_sha = ""
            merge_base_sha = ""
            dirty = $true
            status = "PASS"
            rules = @()
        }

        if (-not (Test-Path $repoPath)) {
            $repoResult.status = "FAIL"
            $repoResult.rules += New-RuleResult -Rule "repo_exists" -Status "FAIL" -Message ("Repo path does not exist: {0}" -f $repoPath)
            $report.repos += $repoResult
            Add-Failure -Rule ("repo_exists::{0}" -f $repoName) -Message ("Repo path does not exist: {0}" -f $repoPath)
            continue
        }

        try {
            if (-not $SkipFetch -and -not [string]::IsNullOrWhiteSpace($repoResult.remote_ref)) {
                $remoteName = ($repoResult.remote_ref -split '/')[0]
                Invoke-Git -RepoPath $repoPath -Arguments @("fetch", $remoteName, "--prune") | Out-Null
                $repoResult.rules += New-RuleResult -Rule "remote_fetch" -Status "PASS" -Message ("Fetched {0} before preflight checks." -f $remoteName)
            }

            $branch = Invoke-Git -RepoPath $repoPath -Arguments @("rev-parse", "--abbrev-ref", "HEAD")
            $headSha = Invoke-Git -RepoPath $repoPath -Arguments @("rev-parse", "HEAD")
            $dirtyOutput = Invoke-Git -RepoPath $repoPath -Arguments @("status", "--porcelain")

            $repoResult.current_branch = $branch
            $repoResult.head_sha = $headSha
            $repoResult.dirty = -not [string]::IsNullOrWhiteSpace($dirtyOutput)

            if ($repoResult.dirty) {
                $repoResult.status = "FAIL"
                $repoResult.rules += New-RuleResult -Rule "repo_clean" -Status "FAIL" -Message "Repo has uncommitted changes."
                Add-Failure -Rule ("repo_clean::{0}" -f $repoName) -Message ("Repo is dirty: {0}" -f $repoPath)
            } else {
                $repoResult.rules += New-RuleResult -Rule "repo_clean" -Status "PASS" -Message "Repo is clean."
            }

            if ([string]::IsNullOrWhiteSpace($repoResult.approved_lane_branch)) {
                $repoResult.status = "FAIL"
                $repoResult.rules += New-RuleResult -Rule "approved_lane_branch" -Status "FAIL" -Message "Manifest is missing approved_lane_branch."
                Add-Failure -Rule ("approved_lane_branch::{0}" -f $repoName) -Message ("Manifest is missing approved_lane_branch for {0}" -f $repoName)
            } elseif ($branch -ne $repoResult.approved_lane_branch) {
                $repoResult.status = "FAIL"
                $repoResult.rules += New-RuleResult -Rule "approved_lane_branch" -Status "FAIL" -Message ("Current branch {0} does not match approved lane {1}." -f $branch, $repoResult.approved_lane_branch)
                Add-Failure -Rule ("approved_lane_branch::{0}" -f $repoName) -Message ("Current branch {0} does not match approved lane {1} for {2}" -f $branch, $repoResult.approved_lane_branch, $repoName)
            } else {
                $repoResult.rules += New-RuleResult -Rule "approved_lane_branch" -Status "PASS" -Message ("Current branch matches approved lane {0}." -f $branch)
            }

            if ([string]::IsNullOrWhiteSpace($repoResult.expected_head_sha)) {
                $repoResult.status = "FAIL"
                $repoResult.rules += New-RuleResult -Rule "expected_head_sha" -Status "FAIL" -Message "Manifest is missing expected_head_sha."
                Add-Failure -Rule ("expected_head_sha::{0}" -f $repoName) -Message ("Manifest is missing expected_head_sha for {0}" -f $repoName)
            } elseif ($headSha -ne $repoResult.expected_head_sha) {
                $repoResult.status = "FAIL"
                $repoResult.rules += New-RuleResult -Rule "expected_head_sha" -Status "FAIL" -Message ("Current HEAD {0} does not match manifest SHA {1}." -f $headSha, $repoResult.expected_head_sha)
                Add-Failure -Rule ("expected_head_sha::{0}" -f $repoName) -Message ("Current HEAD {0} does not match manifest SHA {1} for {2}" -f $headSha, $repoResult.expected_head_sha, $repoName)
            } else {
                $repoResult.rules += New-RuleResult -Rule "expected_head_sha" -Status "PASS" -Message "Current HEAD matches the manifest SHA."
            }

            if ([string]::IsNullOrWhiteSpace($repoResult.remote_ref)) {
                $repoResult.status = "FAIL"
                $repoResult.rules += New-RuleResult -Rule "remote_ref" -Status "FAIL" -Message "Manifest is missing remote_ref."
                Add-Failure -Rule ("remote_ref::{0}" -f $repoName) -Message ("Manifest is missing remote_ref for {0}" -f $repoName)
            } else {
                $remoteHead = Invoke-Git -RepoPath $repoPath -Arguments @("rev-parse", $repoResult.remote_ref)
                $mergeBase = Invoke-Git -RepoPath $repoPath -Arguments @("merge-base", "HEAD", $repoResult.remote_ref)
                $repoResult.upstream_head_sha = $remoteHead
                $repoResult.merge_base_sha = $mergeBase

                if ($mergeBase -ne $remoteHead) {
                    $repoResult.status = "FAIL"
                    $repoResult.rules += New-RuleResult -Rule "remote_truth" -Status "FAIL" -Message ("HEAD is not based on the current remote truth of {0}." -f $repoResult.remote_ref)
                    Add-Failure -Rule ("remote_truth::{0}" -f $repoName) -Message ("HEAD is not based on {0} for {1}" -f $repoResult.remote_ref, $repoName)
                } else {
                    $repoResult.rules += New-RuleResult -Rule "remote_truth" -Status "PASS" -Message ("HEAD includes the current remote truth of {0}." -f $repoResult.remote_ref)
                }
            }

            $requiredSentinels = ConvertTo-Array -Value $repoEntry.required_sentinels
            if ($requiredSentinels.Length -eq 0) {
                $repoResult.status = "FAIL"
                $repoResult.rules += New-RuleResult -Rule "required_sentinels" -Status "FAIL" -Message "Manifest does not declare required_sentinels for this repo."
                Add-Failure -Rule ("required_sentinels::{0}" -f $repoName) -Message ("Manifest is missing required_sentinels for {0}" -f $repoName)
            } else {
                foreach ($sentinelId in $requiredSentinels) {
                    $matchingSentinels = @($sentinelEntries | Where-Object {
                        ([string]$_.id) -eq [string]$sentinelId -and
                        ([string]$_.repo) -eq $repoName -and
                        ([string]$_.status).ToLowerInvariant() -eq "passed"
                    })

                    if ($matchingSentinels.Length -eq 0) {
                        $repoResult.status = "FAIL"
                        $repoResult.rules += New-RuleResult -Rule ("required_sentinel::{0}" -f $sentinelId) -Status "FAIL" -Message ("Required sentinel {0} is missing or not passed." -f $sentinelId)
                        Add-Failure -Rule ("required_sentinel::{0}::{1}" -f $repoName, $sentinelId) -Message ("Required sentinel {0} did not pass for {1}" -f $sentinelId, $repoName)
                    } else {
                        $repoResult.rules += New-RuleResult -Rule ("required_sentinel::{0}" -f $sentinelId) -Status "PASS" -Message ("Required sentinel {0} passed." -f $sentinelId)
                    }
                }
            }
        } catch {
            $repoResult.status = "FAIL"
            $repoResult.rules += New-RuleResult -Rule "repo_exception" -Status "FAIL" -Message $_.Exception.Message
            Add-Failure -Rule ("repo_exception::{0}" -f $repoName) -Message ("Preflight exception for {0}: {1}" -f $repoName, $_.Exception.Message)
        }

        $report.repos += $repoResult
    }

    foreach ($sentinelEntry in $sentinelEntries) {
        $report.sentinel_results += [ordered]@{
            id = [string]$sentinelEntry.id
            repo = [string]$sentinelEntry.repo
            status = [string]$sentinelEntry.status
            evidence = [string]$sentinelEntry.evidence
        }
    }
} catch {
    if ($failures.Count -eq 0) {
        Add-Failure -Rule "preflight_exception" -Message $_.Exception.Message
    }
}

if ($failures.Count -gt 0) {
    $report.status = "FAIL"
    $report.blocking_next_action = $failures[0]
}

$report | ConvertTo-Json -Depth 10 | Set-Content -Path $reportAbs

Write-Host ("PREFLIGHT_STATUS={0}" -f $report.status)
Write-Host ("PREFLIGHT_REPORT={0}" -f $reportAbs)
if ($report.status -ne "PASS") {
    Write-Host ("PREFLIGHT_BLOCKING_NEXT_ACTION={0}" -f $report.blocking_next_action)
    exit 1
}

exit 0
