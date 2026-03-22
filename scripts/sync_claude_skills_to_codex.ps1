[CmdletBinding()]
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$GlobalSkillsRoot = "C:\Users\Sam\.claude\skills",
    [string]$ProjectSkillsRoot,
    [string]$GlobalBackupRoot = "C:\Users\Sam\.agents_backup_2026-02-15\skills",
    [string[]]$MirrorRoots,
    [string[]]$SkillName
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $ProjectSkillsRoot) {
    $ProjectSkillsRoot = Join-Path $RepoRoot ".claude\skills"
}

if (-not $MirrorRoots -or @($MirrorRoots).Count -eq 0) {
    $MirrorRoots = @(
        (Join-Path $RepoRoot ".agents\skills"),
        (Join-Path $RepoRoot ".agent\skills")
    )
}

function Get-UsableSkillDirs {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root,
        [string]$BackupRoot,
        [string]$SourceLabel
    )

    $skills = @{}

    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        Write-Warning "Skill source root not found: $Root"
        return $skills
    }

    foreach ($item in Get-ChildItem -LiteralPath $Root -Directory -Force | Sort-Object Name) {
        $skillDir = $item.FullName
        $skillMd = Join-Path $skillDir "SKILL.md"

        if (Test-Path -LiteralPath $skillMd -PathType Leaf) {
            $skills[$item.Name] = $skillDir
            continue
        }

        $backupDir = $null
        if ($BackupRoot) {
            $candidate = Join-Path $BackupRoot $item.Name
            if (Test-Path -LiteralPath (Join-Path $candidate "SKILL.md") -PathType Leaf) {
                $backupDir = $candidate
            }
        }

        if ($backupDir) {
            Write-Warning "Using backup copy for $SourceLabel skill '$($item.Name)': $backupDir"
            $skills[$item.Name] = $backupDir
            continue
        }

        Write-Warning "Skipping $SourceLabel skill '$($item.Name)' because SKILL.md is missing."
    }

    return $skills
}

function Sync-SkillDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceDir,
        [Parameter(Mandatory = $true)]
        [string]$DestinationDir
    )

    $parentDir = Split-Path -Path $DestinationDir -Parent
    if (-not (Test-Path -LiteralPath $parentDir -PathType Container)) {
        New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
    }

    $replacedCleanly = $false

    if (Test-Path -LiteralPath $DestinationDir) {
        try {
            Remove-Item -LiteralPath $DestinationDir -Recurse -Force
            $replacedCleanly = $true
        } catch {
            Write-Warning "Could not remove '$DestinationDir' cleanly. Falling back to in-place merge. $($_.Exception.Message)"
        }
    } else {
        $replacedCleanly = $true
    }

    if ($replacedCleanly) {
        Copy-Item -LiteralPath $SourceDir -Destination $DestinationDir -Recurse -Force
        return
    }

    if (-not (Test-Path -LiteralPath $DestinationDir -PathType Container)) {
        New-Item -ItemType Directory -Path $DestinationDir -Force | Out-Null
    }

    $sourceChildren = Get-ChildItem -LiteralPath $SourceDir -Force
    foreach ($child in $sourceChildren) {
        $targetPath = Join-Path $DestinationDir $child.Name

        if ($child.PSIsContainer) {
            Sync-SkillDirectory -SourceDir $child.FullName -DestinationDir $targetPath
            continue
        }

        Copy-Item -LiteralPath $child.FullName -Destination $targetPath -Force
    }
}

$globalSkills = Get-UsableSkillDirs -Root $GlobalSkillsRoot -BackupRoot $GlobalBackupRoot -SourceLabel "global"
$projectSkills = Get-UsableSkillDirs -Root $ProjectSkillsRoot -BackupRoot $null -SourceLabel "project"

$orderedSources = @(
    @{ Label = "global"; Skills = $globalSkills },
    @{ Label = "project"; Skills = $projectSkills }
)

$selectedNames = @()
$requestedNames = @(
    @($SkillName) |
        ForEach-Object { $_ -split "," } |
        ForEach-Object { $_.Trim() } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
)
if ($requestedNames.Count -gt 0) {
    $selectedNames = @($requestedNames | Sort-Object -Unique)
}

$mirrorSummary = @{}
foreach ($mirrorRoot in $MirrorRoots) {
    if (-not (Test-Path -LiteralPath $mirrorRoot -PathType Container)) {
        New-Item -ItemType Directory -Path $mirrorRoot -Force | Out-Null
    }

    $mirrorSummary[$mirrorRoot] = [ordered]@{
        Copied    = 0
        Overwrote = 0
    }
}

foreach ($source in $orderedSources) {
    foreach ($name in ($source.Skills.Keys | Sort-Object)) {
        if ($selectedNames.Count -gt 0 -and $name -notin $selectedNames) {
            continue
        }

        $sourceDir = $source.Skills[$name]

        foreach ($mirrorRoot in $MirrorRoots) {
            $destinationDir = Join-Path $mirrorRoot $name
            if ($source.Label -eq "project" -and (Test-Path -LiteralPath $destinationDir)) {
                $mirrorSummary[$mirrorRoot].Overwrote++
            }

            Sync-SkillDirectory -SourceDir $sourceDir -DestinationDir $destinationDir
            $mirrorSummary[$mirrorRoot].Copied++
        }
    }
}

Write-Host "Claude skill mirrors updated."
Write-Host "Repo root: $RepoRoot"
Write-Host "Global source: $GlobalSkillsRoot"
Write-Host "Project source: $ProjectSkillsRoot"

if ($selectedNames.Count -gt 0) {
    Write-Host "Skill filter: $($selectedNames -join ', ')"
}

foreach ($mirrorRoot in $MirrorRoots) {
    $stats = $mirrorSummary[$mirrorRoot]
    Write-Host ("- {0}: copied {1}, project overrides {2}" -f $mirrorRoot, $stats.Copied, $stats.Overwrote)
}
