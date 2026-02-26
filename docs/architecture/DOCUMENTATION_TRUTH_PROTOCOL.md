# Documentation Truth Protocol - BEI ERP

**Last Updated:** 2026-02-26  
**Owner:** Sam Karazi  
**Next Review:** 2026-03-05  
**Purpose:** Ensure architecture and operations documents are updated from verified code/setup evidence, never assumptions.

## Policy

1. Every material claim in architecture docs must reference a source file or command output.
2. If evidence is missing, mark it as `Evidence Gap`; do not fill with assumed values.
3. Any metric in SAD must include a measurement date.
4. If live code contradicts docs, docs must be updated in the same work cycle or explicitly marked stale.

## Mandatory Verification Checks

Run these checks before updating SAD and related architecture docs:

```powershell
# Backend code footprint
$apiPy=(Get-ChildItem hrms/api -File -Filter *.py | Measure-Object).Count
$whitelist=(rg "^\s*@frappe\.whitelist" hrms/api -g "*.py" | Measure-Object).Count
$beiDocTypes=(Get-ChildItem hrms/hr/doctype -Recurse | Where-Object { $_.PSIsContainer -and $_.Name -like 'bei_*' } | Measure-Object).Count

# Frontend footprint (sibling repo)
$apiRoutes=(Get-ChildItem ../bei-tasks/app/api -Recurse -File | Where-Object { $_.Name -match '^route\.(ts|tsx|js|jsx)$' } | Measure-Object).Count
$pages=(Get-ChildItem ../bei-tasks/app -Recurse -File | Where-Object { $_.Name -match '^page\.(ts|tsx|js|jsx)$' } | Measure-Object).Count

# Endpoint reachability
Invoke-WebRequest https://hq.bebang.ph/api/method/frappe.ping -UseBasicParsing
Invoke-WebRequest https://my.bebang.ph -UseBasicParsing
```

Automated drift checker (same logic used in CI):

```powershell
python scripts/docs/documentation_truth_check.py --frontend-path <path-to-BEI-Tasks-repo> --max-age-days 7
```

## Required Cross-Checks

1. SAD counts must match latest command outputs.
2. Route map claims must be reconciled with current `bei-tasks` app structure.
3. Deployment/DR claims must match `.github/workflows/build-and-deploy.yml` and current runbooks.
4. Ownership and ADR references must resolve to existing files.

## Update Cadence

1. Per architecture-affecting release: update SAD metrics and evidence table.
2. Weekly: run full documentation drift check against live code and workflow files.
3. Monthly: review SLO, DR, and security sections for stale values and unresolved gaps.

## Quality Gate

Documentation update is complete only if all are true:

1. Evidence commands were run and outputs reflected in docs.
2. No stale metrics remain in SAD core summary or appendix.
3. All referenced files/paths exist.
4. Open gaps are explicit and tracked in roadmap.
5. Required architecture docs include metadata (`Last Updated`, `Owner`, `Next Review`).
6. Local markdown links resolve for required architecture docs.
7. Markdown lint gate passes for required architecture docs.

## CI Enforcement

Documentation drift is enforced in GitHub Actions:

- Workflow: `.github/workflows/documentation-truth-check.yml`
- Gate behavior: fails the pipeline when code/document metrics drift, required metadata is missing/stale, local links break, or markdown lint checks fail.
