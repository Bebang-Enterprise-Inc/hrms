[CmdletBinding()]
param(
    [string[]]$SourceRoots = @("C:\Users\Sam\.agents\skills", ".claude/skills"),
    [string[]]$FallbackSourceRoots = @("C:\Users\Sam\.agents_backup_2026-02-15\skills"),
    [string[]]$CommandRoots = @("C:\Users\Sam\.claude\commands", ".claude/commands"),
    [string[]]$DestinationRoots = @(".agents/skills", ".agent/skills"),
    [hashtable]$CommandSkillMap = @{ ssh = "ssh.md"; kimi = "kimi.md" },
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Assert-Directory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "$Name directory not found: $Path"
    }
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

function Ensure-SkillEntryFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SkillName,
        [Parameter(Mandatory = $true)]
        [string]$SkillPath
    )

    $entryCandidates = Get-ChildItem -LiteralPath $SkillPath -File | Where-Object { $_.Name -ieq "skill.md" }
    $upperSkillFile = $entryCandidates | Where-Object { $_.Name -ceq "SKILL.md" } | Select-Object -First 1

    if (-not $upperSkillFile -and $entryCandidates.Count -gt 0) {
        $sourceEntry = $entryCandidates | Select-Object -First 1
        $tempName = "__codex_skill_casefix__.tmp"
        $tempPath = Join-Path $SkillPath $tempName

        if (Test-Path -LiteralPath $tempPath -PathType Leaf) {
            Remove-Item -LiteralPath $tempPath -Force
        }

        Rename-Item -LiteralPath $sourceEntry.FullName -NewName $tempName -Force
        Rename-Item -LiteralPath $tempPath -NewName "SKILL.md" -Force
        $upperSkillFile = Get-ChildItem -LiteralPath $SkillPath -File | Where-Object { $_.Name -ceq "SKILL.md" } | Select-Object -First 1
    }

    if (-not $upperSkillFile) {
        # Some global skills use <skill-name>.md rather than SKILL.md.
            $altCandidate = Get-ChildItem -LiteralPath $SkillPath -File |
            Where-Object {
                $_.Extension -ieq ".md" -and
                $_.Name -ine "SKILL.md" -and
                $_.Name -ine "skill.md" -and
                $_.BaseName -ieq $SkillName
            } |
            Select-Object -First 1

            if ($altCandidate) {
                $destSkillFile = Join-Path $SkillPath "SKILL.md"
                Copy-Item -LiteralPath $altCandidate.FullName -Destination $destSkillFile -Force

                $firstLine = (Get-Content -LiteralPath $destSkillFile -TotalCount 1 -ErrorAction SilentlyContinue)
                $normalizedFirstLine = if ($firstLine) { $firstLine.TrimStart([char]0xFEFF).Trim() } else { "" }
                if ([string]::IsNullOrWhiteSpace($normalizedFirstLine) -or $normalizedFirstLine -ne "---") {
                    $existing = Get-Content -LiteralPath $destSkillFile -Raw -ErrorAction SilentlyContinue
                    $frontmatter = @(
                        "---"
                    "name: $SkillName"
                    "description: Imported Claude global skill. Use when tasks match this skill's domain."
                    "---"
                    ""
                ) -join [Environment]::NewLine
                Set-Content -LiteralPath $destSkillFile -Value ($frontmatter + $existing)
            }

            $upperSkillFile = Get-Item -LiteralPath $destSkillFile
        }
    }

    return $upperSkillFile
}

function Ensure-SkillFrontmatterFields {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SkillName,
        [Parameter(Mandatory = $true)]
        [string]$SkillFilePath,
        [Parameter(Mandatory = $false)]
        [string]$DefaultDescription = "Use when tasks match this skill's domain."
    )

    if (-not (Test-Path -LiteralPath $SkillFilePath -PathType Leaf)) {
        return $false
    }

    $content = Get-Content -LiteralPath $SkillFilePath -Raw -ErrorAction SilentlyContinue
    if ([string]::IsNullOrWhiteSpace($content)) {
        return $false
    }

    $content = $content.TrimStart([char]0xFEFF)
    $match = [regex]::Match($content, '^(?s)---\r?\n(?<fm>.*?)\r?\n---(?<rest>.*)$')

    if (-not $match.Success) {
        $frontmatter = @(
            "---"
            "name: $SkillName"
            "description: $DefaultDescription"
            "---"
            ""
        ) -join [Environment]::NewLine
        Set-Content -LiteralPath $SkillFilePath -Value ($frontmatter + $content) -NoNewline
        return $true
    }

    $fm = $match.Groups['fm'].Value
    $rest = $match.Groups['rest'].Value
    $hasName = [regex]::IsMatch($fm, '(?m)^\s*name\s*:')
    $hasDescription = [regex]::IsMatch($fm, '(?m)^\s*description\s*:')

    if ($hasName -and $hasDescription) {
        return $true
    }

    $fmLines = @($fm -split '\r?\n')
    if (-not $hasName) {
        $fmLines = @("name: $SkillName") + $fmLines
    }
    if (-not $hasDescription) {
        $fmLines += "description: $DefaultDescription"
    }

    $newFrontmatter = ($fmLines -join [Environment]::NewLine)
    $newContent = @(
        "---"
        $newFrontmatter
        "---"
    ) -join [Environment]::NewLine

    Set-Content -LiteralPath $SkillFilePath -Value ($newContent + $rest) -NoNewline
    return $true
}

if (-not $SourceRoots -or $SourceRoots.Count -eq 0) {
    throw "At least one source root must be provided."
}

$normalizedSources = $SourceRoots |
    Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
    Select-Object -Unique

if (-not $normalizedSources -or $normalizedSources.Count -eq 0) {
    throw "At least one non-empty source root must be provided."
}

$normalizedCommandRoots = @()
if ($CommandRoots) {
    $normalizedCommandRoots = $CommandRoots |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        Select-Object -Unique
}

$script:ExistingFallbackRoots = @()
if ($FallbackSourceRoots) {
    $script:ExistingFallbackRoots = $FallbackSourceRoots |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        Where-Object { Test-Path -LiteralPath $_ -PathType Container } |
        Select-Object -Unique
}

foreach ($sourceRoot in $normalizedSources) {
    Assert-Directory -Path $sourceRoot -Name "Source"
}

$skillMap = @{}
$sourceSkillCounts = @{}
$overrides = New-Object System.Collections.Generic.List[string]
$sourceWarnings = New-Object System.Collections.Generic.List[string]
$commandSkillSources = @{}
$commandOverrides = New-Object System.Collections.Generic.List[string]

foreach ($sourceRoot in $normalizedSources) {
    $skillsInRoot = Get-ChildItem -LiteralPath $sourceRoot -Directory | Sort-Object Name
    $sourceSkillCounts[$sourceRoot] = $skillsInRoot.Count

    foreach ($skill in $skillsInRoot) {
        $resolved = Resolve-SkillSourcePath -SkillDir $skill
        if ($resolved.Warning) {
            $sourceWarnings.Add($resolved.Warning)
        }

        if (-not $resolved.Path) {
            continue
        }

        if ($skillMap.ContainsKey($skill.Name)) {
            $previous = $skillMap[$skill.Name]
            $overrides.Add("$($skill.Name): '$($previous.SourceRoot)' -> '$sourceRoot'")
        }

        $skillMap[$skill.Name] = @{
            SkillName   = $skill.Name
            SourceRoot  = $sourceRoot
            SourcePath  = $resolved.Path
        }
    }
}

foreach ($commandRoot in $normalizedCommandRoots) {
    if (-not (Test-Path -LiteralPath $commandRoot -PathType Container)) {
        continue
    }

    if (-not $CommandSkillMap) {
        continue
    }

    foreach ($entry in $CommandSkillMap.GetEnumerator()) {
        $skillName = [string]$entry.Key
        $relativePath = [string]$entry.Value

        if ([string]::IsNullOrWhiteSpace($skillName) -or [string]::IsNullOrWhiteSpace($relativePath)) {
            continue
        }

        if ($skillMap.ContainsKey($skillName)) {
            $sourceWarnings.Add("Skipping command skill '$skillName' from '$commandRoot' because a source skill with the same name already exists.")
            continue
        }

        $candidatePath = Join-Path $commandRoot $relativePath
        if (-not (Test-Path -LiteralPath $candidatePath -PathType Leaf)) {
            continue
        }

        if ($commandSkillSources.ContainsKey($skillName)) {
            $previous = $commandSkillSources[$skillName]
            $commandOverrides.Add("${skillName}: '$($previous.SourceRoot)' -> '$commandRoot'")
        }

        $commandSkillSources[$skillName] = @{
            SkillName  = $skillName
            SourceRoot = $commandRoot
            SourcePath = $candidatePath
        }
    }
}

$skills = @($skillMap.Values | Sort-Object SkillName)
$commandSkills = @($commandSkillSources.Values | Sort-Object SkillName)
if (($skills.Count + $commandSkills.Count) -eq 0) {
    Write-Output "No skill directories found in source roots or configured command roots."
    exit 0
}

if (-not $DestinationRoots -or $DestinationRoots.Count -eq 0) {
    throw "At least one destination root must be provided."
}

$normalizedDestinations = $DestinationRoots |
    Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
    Select-Object -Unique

if (-not $normalizedDestinations -or $normalizedDestinations.Count -eq 0) {
    throw "At least one non-empty destination root must be provided."
}

foreach ($destinationRoot in $normalizedDestinations) {
    if (-not (Test-Path -LiteralPath $destinationRoot -PathType Container)) {
        if ($DryRun) {
            Write-Output "Would create destination directory: $destinationRoot"
        } else {
            New-Item -ItemType Directory -Path $destinationRoot -Force | Out-Null
            Write-Output "Created destination directory: $destinationRoot"
        }
    }

    $synced = New-Object System.Collections.Generic.List[string]
    $normalized = New-Object System.Collections.Generic.List[string]
    $warnings = New-Object System.Collections.Generic.List[string]
    $copyFailures = New-Object System.Collections.Generic.List[string]

    foreach ($skill in $skills) {
        $sourceSkillPath = $skill.SourcePath
        $destinationSkillPath = Join-Path $destinationRoot $skill.SkillName

        if ($DryRun) {
            Write-Output "Would sync ($destinationRoot): $($skill.SkillName) from $($skill.SourceRoot)"
        } else {
            if (-not (Test-Path -LiteralPath $destinationSkillPath -PathType Container)) {
                New-Item -ItemType Directory -Path $destinationSkillPath -Force | Out-Null
            }

            $null = & robocopy $sourceSkillPath $destinationSkillPath /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
            $exitCode = $LASTEXITCODE
            if ($exitCode -gt 7) {
                $copyFailures.Add("robocopy failed for '$($skill.SkillName)' (source '$($skill.SourceRoot)') with exit code $exitCode")
                continue
            }

            $upperSkillFile = Ensure-SkillEntryFile -SkillName $skill.SkillName -SkillPath $destinationSkillPath
            if (-not $upperSkillFile) {
                $warnings.Add("No SKILL.md or skill.md found for '$($skill.SkillName)'")
            } else {
                $frontmatterOk = Ensure-SkillFrontmatterFields -SkillName $skill.SkillName -SkillFilePath $upperSkillFile.FullName
                if (-not $frontmatterOk) {
                    $warnings.Add("Unable to normalize frontmatter for '$($skill.SkillName)'")
                }
                $normalized.Add($skill.SkillName)
            }
        }

        $synced.Add($skill.SkillName)
    }

    foreach ($commandSkill in $commandSkills) {
        $destinationSkillPath = Join-Path $destinationRoot $commandSkill.SkillName
        $destinationSkillFile = Join-Path $destinationSkillPath "SKILL.md"

        if ($DryRun) {
            Write-Output "Would sync command-as-skill ($destinationRoot): $($commandSkill.SkillName) from $($commandSkill.SourceRoot)"
        } else {
            if (-not (Test-Path -LiteralPath $destinationSkillPath -PathType Container)) {
                New-Item -ItemType Directory -Path $destinationSkillPath -Force | Out-Null
            }

            Copy-Item -LiteralPath $commandSkill.SourcePath -Destination $destinationSkillFile -Force
            $upperSkillFile = Ensure-SkillEntryFile -SkillName $commandSkill.SkillName -SkillPath $destinationSkillPath
            if (-not $upperSkillFile) {
                $warnings.Add("No SKILL.md found after copying command '$($commandSkill.SkillName)'")
            } else {
                $frontmatterOk = Ensure-SkillFrontmatterFields -SkillName $commandSkill.SkillName -SkillFilePath $upperSkillFile.FullName
                if (-not $frontmatterOk) {
                    $warnings.Add("Unable to normalize frontmatter for command skill '$($commandSkill.SkillName)'")
                }
                $normalized.Add($commandSkill.SkillName)
            }
        }

        $synced.Add($commandSkill.SkillName)
    }

    Write-Output ""
    Write-Output "Synced $($synced.Count) skill directories to '$destinationRoot'."

    if ($normalized.Count -gt 0) {
        Write-Output "Ensured SKILL.md entry file for $($normalized.Count) skills in '$destinationRoot'."
        if ($normalized.Count -le 20) {
            foreach ($name in $normalized) {
                Write-Output " - $name"
            }
        }
    }

    if ($warnings.Count -gt 0) {
        Write-Output "Warnings for '$destinationRoot':"
        foreach ($warning in $warnings) {
            Write-Output " - $warning"
        }
    }

    if ($copyFailures.Count -gt 0) {
        Write-Output "Copy failures for '$destinationRoot':"
        foreach ($failure in $copyFailures) {
            Write-Output " - $failure"
        }
    }
}

Write-Output ""
Write-Output "Source roots used (in precedence order; later roots win on duplicates):"
foreach ($sourceRoot in $normalizedSources) {
    Write-Output " - $sourceRoot ($($sourceSkillCounts[$sourceRoot]) skills)"
}

if ($overrides.Count -gt 0) {
    Write-Output "Duplicate skill names resolved by precedence: $($overrides.Count)"
}

if ($commandOverrides.Count -gt 0) {
    Write-Output "Duplicate command skill names resolved by precedence: $($commandOverrides.Count)"
}

if ($sourceWarnings.Count -gt 0) {
    Write-Output "Source warnings:"
    foreach ($warning in $sourceWarnings) {
        Write-Output " - $warning"
    }
}

if ($script:ExistingFallbackRoots.Count -gt 0) {
    Write-Output "Fallback source roots used:"
    foreach ($fallbackRoot in $script:ExistingFallbackRoots) {
        Write-Output " - $fallbackRoot"
    }
}

if ($commandSkills.Count -gt 0) {
    Write-Output "Command files mirrored as skills:"
    foreach ($commandSkill in $commandSkills) {
        Write-Output " - $($commandSkill.SkillName) <= $($commandSkill.SourceRoot)"
    }
}
