param(
    [int]$Days = 30,
    [string]$ProjectPath = "",
    [string]$OutputMarkdown = "docs/reports/SKILL_USAGE_LAST_30_DAYS.md",
    [string]$OutputJson = "scratchpad/reports/claude_command_usage_30d_latest.json",
    [int]$Top = 25
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if ([string]::IsNullOrWhiteSpace($ProjectPath)) {
    $ProjectPath = $repoRoot
}

$mdDir = Split-Path -Parent $OutputMarkdown
if ($mdDir) {
    New-Item -ItemType Directory -Path $mdDir -Force | Out-Null
}

$jsonDir = Split-Path -Parent $OutputJson
if ($jsonDir) {
    New-Item -ItemType Directory -Path $jsonDir -Force | Out-Null
}

$args = @(
    "scripts/report_claude_command_usage.py",
    "--days", "$Days",
    "--project-filter", "$ProjectPath",
    "--output-json", "$OutputJson",
    "--output-md", "$OutputMarkdown",
    "--top", "$Top"
)

python @args
if ($LASTEXITCODE -ne 0) {
    throw "Skill usage snapshot generation failed with exit code $LASTEXITCODE."
}

Write-Host "Skill usage snapshot updated:"
Write-Host "  Markdown: $OutputMarkdown"
Write-Host "  JSON: $OutputJson"
