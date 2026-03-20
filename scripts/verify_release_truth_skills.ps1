$ErrorActionPreference = "Stop"

$checks = @(
    @{
        Path = "C:\Users\Sam\.claude\skills\execute-plan\SKILL.md"
        Patterns = @(
            "Deployable Plan Completion Rule",
            "IMPLEMENTED_NOT_MERGED",
            "MERGED_NOT_DEPLOYED",
            "DEPLOYED_NOT_VERIFIED"
        )
    },
    @{
        Path = "C:\Users\Sam\.claude\skills\ship\SKILL.md"
        Patterns = @(
            "Truthful Shipping Rule",
            "READY_TO_SHIP",
            "MERGED_NOT_DEPLOYED",
            "DEPLOYED_NOT_VERIFIED"
        )
    },
    @{
        Path = "F:\Dropbox\Projects\BEI-ERP\.claude\skills\execute-plan-bei-erp\SKILL.md"
        Patterns = @(
            "Merge/Live Truth Rule",
            "implemented but not merged and not live",
            "Stage-Chain Handshake",
            "Status: READY_TO_DEPLOY",
            "Decision needed: none",
            "LIVE TRUTH:"
        )
    },
    @{
        Path = "F:\Dropbox\Projects\BEI-ERP\.claude\skills\deploy\SKILL.md"
        Patterns = @(
            "Merge/Live Truth Rule",
            "Stage-Chain Handshake",
            "Status: READY_FOR_E2E",
            "Direct-Execution Fallback",
            "NOT_MERGED_NOT_LIVE",
            "MERGED_NOT_LIVE",
            "DEPLOYED_NOT_VERIFIED",
            "Release truth:"
        )
    },
    @{
        Path = "F:\Dropbox\Projects\BEI-ERP\.claude\skills\ship-bei-erp\SKILL.md"
        Patterns = @(
            "BEI Live Truth Contract",
            "NOT_SHIPPED_NOT_MERGED",
            "MERGED_NOT_LIVE",
            "DEPLOYED_NOT_VERIFIED"
        )
    },
    @{
        Path = "F:\Dropbox\Projects\BEI-ERP\.claude\skills\execute-plan\SKILL.md"
        Patterns = @(
            "Project override:",
            "IMPLEMENTED_NOT_MERGED",
            "MERGED_NOT_LIVE",
            "DEPLOYED_NOT_VERIFIED"
        )
    },
    @{
        Path = "F:\Dropbox\Projects\BEI-ERP\.claude\skills\ship\SKILL.md"
        Patterns = @(
            "Project override:",
            "NOT_SHIPPED_NOT_MERGED",
            "READY_TO_SHIP",
            "MERGED_NOT_DEPLOYED",
            "DEPLOYED_NOT_VERIFIED"
        )
    },
    @{
        Path = "F:\Dropbox\Projects\BEI-ERP\.agents\skills\execute-plan-bei-erp\SKILL.md"
        Patterns = @(
            "Merge/Live Truth Rule",
            "Stage-Chain Handshake",
            "Status: READY_TO_DEPLOY",
            "LIVE TRUTH:"
        )
    },
    @{
        Path = "F:\Dropbox\Projects\BEI-ERP\.agents\skills\deploy\SKILL.md"
        Patterns = @(
            "Merge/Live Truth Rule",
            "Stage-Chain Handshake",
            "Status: READY_FOR_E2E",
            "Direct-Execution Fallback",
            "NOT_MERGED_NOT_LIVE",
            "MERGED_NOT_LIVE",
            "DEPLOYED_NOT_VERIFIED"
        )
    },
    @{
        Path = "F:\Dropbox\Projects\BEI-ERP\.agents\skills\ship-bei-erp\SKILL.md"
        Patterns = @(
            "BEI Live Truth Contract",
            "NOT_SHIPPED_NOT_MERGED",
            "MERGED_NOT_LIVE",
            "DEPLOYED_NOT_VERIFIED"
        )
    },
    @{
        Path = "F:\Dropbox\Projects\BEI-ERP\.agents\skills\execute-plan\SKILL.md"
        Patterns = @(
            "Project override:",
            "IMPLEMENTED_NOT_MERGED",
            "MERGED_NOT_LIVE",
            "DEPLOYED_NOT_VERIFIED"
        )
    },
    @{
        Path = "F:\Dropbox\Projects\BEI-ERP\.agents\skills\ship\SKILL.md"
        Patterns = @(
            "Project override:",
            "NOT_SHIPPED_NOT_MERGED",
            "READY_TO_SHIP",
            "MERGED_NOT_DEPLOYED",
            "DEPLOYED_NOT_VERIFIED"
        )
    },
    @{
        Path = "F:\Dropbox\Projects\BEI-ERP\scripts\orchestration\run_stage_chain.ps1"
        Patterns = @(
            "READY_TO_DEPLOY",
            "READY_FOR_E2E",
            "READY_TO_CLOSEOUT",
            "missing-status-line",
            "invalid-stage-status:",
            "Decision needed:"
        )
    }
)

$failures = New-Object System.Collections.Generic.List[string]

foreach ($check in $checks) {
    if (-not (Test-Path -LiteralPath $check.Path)) {
        $failures.Add("Missing file: $($check.Path)")
        continue
    }

    $content = Get-Content -LiteralPath $check.Path -Raw
    foreach ($pattern in $check.Patterns) {
        if ($content -notmatch [regex]::Escape($pattern)) {
            $failures.Add("Missing pattern '$pattern' in $($check.Path)")
        }
    }
}

if ($failures.Count -gt 0) {
    Write-Host "FAIL: release-truth skill verification failed." -ForegroundColor Red
    $failures | ForEach-Object { Write-Host " - $_" -ForegroundColor Red }
    exit 1
}

Write-Host "PASS: release-truth skill verification passed for source and mirror files." -ForegroundColor Green
