[CmdletBinding()]
param(
    [string]$ClaudeInstructions = ".claude/CLAUDE.md",
    [string[]]$SourceRoots = @("C:\Users\Sam\.claude\skills", ".claude/skills"),
    [string[]]$FallbackSourceRoots = @("C:\Users\Sam\.agents_backup_2026-02-15\skills"),
    [string[]]$CodexSkillRoots = @(".agents/skills", ".agent/skills"),
    [string[]]$MemoryCandidates = @(
        ".claude/memory.md",
        ".claude/MEMORY.md",
        "C:\Users\Sam\.claude\projects\F--Dropbox-Projects-BEI-ERP\memory\MEMORY.md"
    )
)

$ErrorActionPreference = "Stop"

function Resolve-ExistingPath {
    param([string[]]$Candidates)
    foreach ($candidate in $Candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    return $null
}

function Get-SourceEntryFile {
    param(
        [string]$SkillDir,
        [string]$SkillName
    )

    $upper = Join-Path $SkillDir "SKILL.md"
    $lower = Join-Path $SkillDir "skill.md"
    if (Test-Path -LiteralPath $upper -PathType Leaf) { return $upper }
    if (Test-Path -LiteralPath $lower -PathType Leaf) { return $lower }

    $alt = Get-ChildItem -LiteralPath $SkillDir -File -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Extension -ieq ".md" -and
            $_.Name -ine "SKILL.md" -and
            $_.Name -ine "skill.md" -and
            $_.BaseName -ieq $SkillName
        } |
        Select-Object -First 1

    if ($alt) { return $alt.FullName }
    return $null
}

function Resolve-SkillSourcePath {
    param(
        [Parameter(Mandatory = $true)]
        [System.IO.DirectoryInfo]$SkillDir
    )

    $item = Get-Item -LiteralPath $SkillDir.FullName -Force
    $isReparse = ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0

    $linkType = $item.LinkType
    if (-not $isReparse -or [string]::IsNullOrWhiteSpace($linkType)) {
        if (Test-Path -LiteralPath $SkillDir.FullName -PathType Container) {
            return @{
                Path = $SkillDir.FullName
                Warning = $null
            }
        }

        return @{
            Path = $null
            Warning = "Skipping inaccessible source skill '$($SkillDir.Name)' from '$($SkillDir.Parent.FullName)'"
        }
    }

    $target = $item.Target
    if ($target -is [System.Array]) {
        $target = $target | Select-Object -First 1
    }

    if ([string]::IsNullOrWhiteSpace($target)) {
        return @{
            Path = $SkillDir.FullName
            Warning = $null
        }
    }

    if (-not (Test-Path -LiteralPath $target -PathType Container)) {
        foreach ($fallbackRoot in $script:ExistingFallbackRoots) {
            $fallbackSkillPath = Join-Path $fallbackRoot $SkillDir.Name
            if (Test-Path -LiteralPath $fallbackSkillPath -PathType Container) {
                return @{
                    Path = $fallbackSkillPath
                    Warning = "Recovered broken junction skill '$($SkillDir.Name)' using fallback '$fallbackRoot'"
                }
            }
        }

        return @{
            Path = $null
            Warning = "Skipping broken junction skill '$($SkillDir.Name)' from '$($SkillDir.Parent.FullName)' (target '$target' missing)"
        }
    }

    return @{
        Path = $target
        Warning = $null
    }
}

$errors = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

if (-not (Test-Path -LiteralPath $ClaudeInstructions -PathType Leaf)) {
    $errors.Add("Missing Claude instructions file: $ClaudeInstructions")
}

$script:ExistingFallbackRoots = @()
if ($FallbackSourceRoots) {
    $script:ExistingFallbackRoots = $FallbackSourceRoots |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        Where-Object { Test-Path -LiteralPath $_ -PathType Container } |
        Select-Object -Unique
}

$normalizedSources = $SourceRoots |
    Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
    Select-Object -Unique

if (-not $normalizedSources -or $normalizedSources.Count -eq 0) {
    $errors.Add("No source roots configured.")
}

$resolvedMemory = Resolve-ExistingPath -Candidates $MemoryCandidates
if (-not $resolvedMemory) {
    $warnings.Add("No memory file found in expected locations.")
}

$skillMap = @{}
$sourceSkillCounts = @{}

foreach ($sourceRoot in $normalizedSources) {
    if (-not (Test-Path -LiteralPath $sourceRoot -PathType Container)) {
        $errors.Add("Missing source root: $sourceRoot")
        continue
    }

    $skillsInRoot = Get-ChildItem -LiteralPath $sourceRoot -Directory
    $sourceSkillCounts[$sourceRoot] = $skillsInRoot.Count

    foreach ($skill in $skillsInRoot) {
        $resolved = Resolve-SkillSourcePath -SkillDir $skill
        if ($resolved.Warning) {
            $warnings.Add($resolved.Warning)
        }

        if (-not $resolved.Path) {
            continue
        }

        $skillMap[$skill.Name] = @{
            SkillName  = $skill.Name
            SourceRoot = $sourceRoot
            SourcePath = $resolved.Path
        }
    }
}

$sourceSkills = @()
if ($skillMap.Count -eq 0) {
    $errors.Add("No skill directories found in source roots.")
} else {
    $sourceSkills = $skillMap.Values | Sort-Object SkillName
}

foreach ($codexRoot in $CodexSkillRoots) {
    if (-not (Test-Path -LiteralPath $codexRoot -PathType Container)) {
        $errors.Add("Missing Codex skill root: $codexRoot")
        continue
    }

    $destSkills = Get-ChildItem -LiteralPath $codexRoot -Directory | Sort-Object Name
    $destSkillNames = $destSkills | Select-Object -ExpandProperty Name
    $sourceSkillNames = $sourceSkills | Select-Object -ExpandProperty SkillName
    $extraSkills = $destSkillNames | Where-Object { $_ -notin $sourceSkillNames }
    if ($extraSkills.Count -gt 0) {
        $warnings.Add("Extra mirrored skills present in $codexRoot not found in current source set: $($extraSkills.Count)")
    }

    foreach ($srcSkill in $sourceSkills) {
        $srcSkillName = $srcSkill.SkillName
        $srcSkillPath = $srcSkill.SourcePath
        $dstSkillPath = Join-Path $codexRoot $srcSkillName

        if (-not (Test-Path -LiteralPath $dstSkillPath -PathType Container)) {
            $errors.Add("Missing mirrored skill in ${codexRoot}: $srcSkillName")
            continue
        }

        $srcEntry = Get-SourceEntryFile -SkillDir $srcSkillPath -SkillName $srcSkillName
        if (-not $srcEntry) {
            $errors.Add("Source skill missing entry file (SKILL.md/skill.md): $srcSkillName")
            continue
        }

        $dstEntry = Join-Path $dstSkillPath "SKILL.md"
        if (-not (Test-Path -LiteralPath $dstEntry -PathType Leaf)) {
            $errors.Add("Mirrored skill missing SKILL.md in ${codexRoot}: $srcSkillName")
            continue
        }

        $srcHash = (Get-FileHash -LiteralPath $srcEntry).Hash
        $dstHash = (Get-FileHash -LiteralPath $dstEntry).Hash
        $srcFirstLine = (Get-Content -LiteralPath $srcEntry -TotalCount 1 -ErrorAction SilentlyContinue)
        $srcHasFrontmatter = $false
        if ($srcFirstLine) {
            $srcHasFrontmatter = $srcFirstLine.TrimStart([char]0xFEFF).Trim() -eq "---"
        }

        if (-not $srcHasFrontmatter) {
            $warnings.Add("Skipped strict hash check for '$srcSkillName' in $codexRoot (source entry has no YAML frontmatter).")
            continue
        }

        if ($srcHash -ne $dstHash) {
            $errors.Add("Entry file hash mismatch for '$srcSkillName' in $codexRoot")
        }
    }
}

Write-Output "Claude instructions: $ClaudeInstructions"
if ($resolvedMemory) {
    Write-Output "Memory file: $resolvedMemory"
} else {
    Write-Output "Memory file: NOT FOUND"
}
Write-Output "Source skills (merged): $($sourceSkills.Count)"
Write-Output "Source roots:"
foreach ($sourceRoot in $normalizedSources) {
    if ($sourceSkillCounts.ContainsKey($sourceRoot)) {
        Write-Output " - $sourceRoot ($($sourceSkillCounts[$sourceRoot]) skills)"
    }
}
Write-Output "Codex roots checked: $($CodexSkillRoots -join ', ')"
if ($script:ExistingFallbackRoots.Count -gt 0) {
    Write-Output "Fallback roots: $($script:ExistingFallbackRoots -join ', ')"
}

if ($warnings.Count -gt 0) {
    Write-Output ""
    Write-Output "Warnings:"
    foreach ($warning in $warnings) {
        Write-Output " - $warning"
    }
}

if ($errors.Count -gt 0) {
    Write-Output ""
    Write-Output "Setup verification FAILED:"
    foreach ($errItem in $errors) {
        Write-Output " - $errItem"
    }
    exit 1
}

Write-Output ""
Write-Output "Setup verification PASSED."
