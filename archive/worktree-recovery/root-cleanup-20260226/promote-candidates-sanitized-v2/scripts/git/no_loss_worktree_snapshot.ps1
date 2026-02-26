param(
  [string]$OutputRoot = "output/worktree-snapshots"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-Worktrees {
  $lines = git worktree list --porcelain
  $items = @()
  $current = @{}

  foreach ($line in $lines) {
    if ([string]::IsNullOrWhiteSpace($line)) {
      if ($current.ContainsKey("worktree")) {
        $items += [PSCustomObject]@{
          Path = $current["worktree"]
          BranchRef = if ($current.ContainsKey("branch")) { $current["branch"] } else { "" }
          Branch = if ($current.ContainsKey("branch")) { ($current["branch"] -replace "^refs/heads/", "") } else { "(detached)" }
          Head = if ($current.ContainsKey("HEAD")) { $current["HEAD"] } else { "" }
        }
      }
      $current = @{}
      continue
    }

    $parts = $line -split " ", 2
    if ($parts.Count -eq 2) {
      $current[$parts[0]] = $parts[1]
    } else {
      $current[$parts[0]] = ""
    }
  }

  if ($current.ContainsKey("worktree")) {
    $items += [PSCustomObject]@{
      Path = $current["worktree"]
      BranchRef = if ($current.ContainsKey("branch")) { $current["branch"] } else { "" }
      Branch = if ($current.ContainsKey("branch")) { ($current["branch"] -replace "^refs/heads/", "") } else { "(detached)" }
      Head = if ($current.ContainsKey("HEAD")) { $current["HEAD"] } else { "" }
    }
  }

  return $items
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$root = Join-Path $OutputRoot $timestamp
New-Item -ItemType Directory -Path $root -Force | Out-Null

$worktrees = Get-Worktrees

$manifest = @()
foreach ($wt in $worktrees) {
  $safeName = ($wt.Branch -replace '[^a-zA-Z0-9._-]', '_')
  $wtDir = Join-Path $root $safeName
  New-Item -ItemType Directory -Path $wtDir -Force | Out-Null

  $statusShort = git -C $wt.Path status --short
  $statusLong = git -C $wt.Path status
  $statusShort | Out-File -FilePath (Join-Path $wtDir "status.short.txt") -Encoding utf8
  $statusLong | Out-File -FilePath (Join-Path $wtDir "status.long.txt") -Encoding utf8

  $log = git -C $wt.Path log --oneline -n 30
  $log | Out-File -FilePath (Join-Path $wtDir "log.oneline.txt") -Encoding utf8

  $diff = git -C $wt.Path diff
  $diff | Out-File -FilePath (Join-Path $wtDir "worktree.diff.patch") -Encoding utf8

  $staged = git -C $wt.Path diff --staged
  $staged | Out-File -FilePath (Join-Path $wtDir "index.diff.patch") -Encoding utf8

  $untracked = git -C $wt.Path ls-files --others --exclude-standard
  $untracked | Out-File -FilePath (Join-Path $wtDir "untracked.list.txt") -Encoding utf8

  $dirtyCount = ($statusShort | Measure-Object).Count
  $untrackedCount = ($untracked | Measure-Object).Count

  $upstream = ""
  $ahead = "no-upstream"
  $behind = "no-upstream"
  $upstreamProbe = git -C $wt.Path rev-parse --abbrev-ref --symbolic-full-name "@{u}" 2>$null
  if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($upstreamProbe)) {
    $upstream = $upstreamProbe.Trim()
    $counts = git -C $wt.Path rev-list --left-right --count "$upstream...HEAD" 2>$null
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($counts)) {
      $parts = $counts.Trim() -split "\s+"
      if ($parts.Count -ge 2) {
        $behind = $parts[0]
        $ahead = $parts[1]
      }
    }
  }

  $manifest += [PSCustomObject]@{
    path = $wt.Path
    branch = $wt.Branch
    head = $wt.Head
    dirty_count = $dirtyCount
    untracked_count = $untrackedCount
    upstream = $upstream
    ahead = $ahead
    behind = $behind
    snapshot_dir = $wtDir
  }
}

$manifestPath = Join-Path $root "manifest.json"
$manifest | ConvertTo-Json -Depth 5 | Out-File -FilePath $manifestPath -Encoding utf8

$bundlePath = Join-Path $root "all-refs.bundle"
git bundle create $bundlePath --all | Out-Null

Write-Host "No-loss snapshot complete:"
Write-Host "  root: $root"
Write-Host "  manifest: $manifestPath"
Write-Host "  bundle: $bundlePath"
Write-Host "  worktrees: $($manifest.Count)"
