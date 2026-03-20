[CmdletBinding()]
param(
    [string]$Workspace = "F:/Dropbox/Projects/BEI-ERP",
    [string]$OutputRoot = "",
    [string[]]$RepoPaths = @(
        "F:/Dropbox/Projects/BEI-ERP",
        "F:/Dropbox/Projects/bei-tasks"
    )
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Parse-WorktreeList {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$Lines
    )

    $entries = @()
    $current = $null
    foreach ($rawLine in @($Lines)) {
        $line = [string]$rawLine
        if ([string]::IsNullOrWhiteSpace($line)) {
            if ($null -ne $current) {
                $entries += [pscustomobject]$current
                $current = $null
            }
            continue
        }

        if ($line -like "worktree *") {
            if ($null -ne $current) {
                $entries += [pscustomobject]$current
            }
            $current = @{
                worktree_path = $line.Substring(9)
                head = ""
                branch = ""
                detached = $false
                bare = $false
                locked = $false
                prunable = $false
            }
            continue
        }

        if ($null -eq $current) {
            continue
        }

        if ($line -like "HEAD *") {
            $current.head = $line.Substring(5)
            continue
        }
        if ($line -like "branch *") {
            $current.branch = $line.Substring(7)
            continue
        }
        if ($line -eq "detached") {
            $current.detached = $true
            continue
        }
        if ($line -eq "bare") {
            $current.bare = $true
            continue
        }
        if ($line -like "locked*") {
            $current.locked = $true
            continue
        }
        if ($line -like "prunable*") {
            $current.prunable = $true
            continue
        }
    }

    if ($null -ne $current) {
        $entries += [pscustomobject]$current
    }

    return $entries
}

function Get-SafeName {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    return (($Value -replace "^[A-Za-z]:", "") -replace "[\\/:\s]+", "_").Trim("_")
}

$workspaceAbs = (Resolve-Path $Workspace).Path
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $workspaceAbs "output/worktree-snapshots"
}
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$snapshotRoot = Join-Path $OutputRoot $stamp
New-Item -ItemType Directory -Force -Path $snapshotRoot | Out-Null

$manifest = [ordered]@{
    generated_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    workspace = $workspaceAbs
    snapshot_root = $snapshotRoot
    repos = @()
}

foreach ($repoPathRaw in $RepoPaths) {
    $repoPath = (Resolve-Path $repoPathRaw).Path
    $repoName = Split-Path $repoPath -Leaf
    $repoDir = Join-Path $snapshotRoot $repoName
    New-Item -ItemType Directory -Force -Path $repoDir | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $repoDir "worktrees") | Out-Null

    $bundlePath = Join-Path $repoDir "all-refs.bundle"
    & git -C $repoPath bundle create $bundlePath --all | Out-Null

    $worktreeLines = & git -C $repoPath worktree list --porcelain
    $worktrees = Parse-WorktreeList -Lines $worktreeLines

    $repoManifest = [ordered]@{
        repo_name = $repoName
        repo_path = $repoPath
        root_head = (& git -C $repoPath rev-parse HEAD).Trim()
        current_branch = (& git -C $repoPath rev-parse --abbrev-ref HEAD).Trim()
        bundle_path = $bundlePath
        worktrees = @()
    }

    foreach ($worktree in $worktrees) {
        $safeWorktreeName = Get-SafeName -Value $worktree.worktree_path
        $worktreeDir = Join-Path (Join-Path $repoDir "worktrees") $safeWorktreeName
        New-Item -ItemType Directory -Force -Path $worktreeDir | Out-Null

        $statusPath = Join-Path $worktreeDir "status.txt"
        $statusLines = & git -C $worktree.worktree_path status --short
        $statusLines | Set-Content -Path $statusPath

        $trackedPatchPath = Join-Path $worktreeDir "tracked.patch"
        $untrackedPath = Join-Path $worktreeDir "untracked.txt"
        $statusEntries = @($statusLines)
        $dirty = $statusEntries.Count -gt 0

        if ($dirty) {
            & git -C $worktree.worktree_path diff --binary HEAD > $trackedPatchPath
            & git -C $worktree.worktree_path ls-files --others --exclude-standard > $untrackedPath
        } else {
            "" | Set-Content -Path $trackedPatchPath
            "" | Set-Content -Path $untrackedPath
        }

        $repoManifest.worktrees += [ordered]@{
            worktree_path = $worktree.worktree_path
            head = $worktree.head
            branch = $worktree.branch
            detached = $worktree.detached
            bare = $worktree.bare
            locked = $worktree.locked
            prunable = $worktree.prunable
            dirty = $dirty
            status_path = $statusPath
            tracked_patch_path = $trackedPatchPath
            untracked_path = $untrackedPath
            status_entries = $statusEntries.Count
        }
    }

    $repoManifestPath = Join-Path $repoDir "repo-manifest.json"
    $repoManifest | ConvertTo-Json -Depth 8 | Set-Content -Path $repoManifestPath
    $manifest.repos += $repoManifest
}

$manifestPath = Join-Path $snapshotRoot "manifest.json"
$manifest | ConvertTo-Json -Depth 8 | Set-Content -Path $manifestPath

Write-Host ("SNAPSHOT_ROOT={0}" -f $snapshotRoot)
Write-Host ("MANIFEST_PATH={0}" -f $manifestPath)
