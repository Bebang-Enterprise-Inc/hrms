---
canonical_sprint_id: S124
display: Sprint 124
status: GO
branch: s124-commissary-inventory-routing-fix
created_date: 2026-03-26
completed_date:
execution_summary:
depends_on: S121
---

# S124: Commissary Inventory Routing Fix

## Problem Statement

Commissary operators cannot use production logging or wastage tracking forms on my.bebang.ph. Root cause: the `erp_sync.py` warehouse alias map routes all "Shaw BLVD" variants to `Shaw BLVD - Bebang Enterprise Inc.` (BEI store) instead of `Shaw BLVD - BKI` (commissary warehouse). This means:

1. **Inventory sync skips the commissary warehouse** -- yesterday's 100-store sync (March 25) populated every store except Shaw BLVD - BKI. The commissary has only 10 of 69 BOM-required items stocked (from a March 13 initial load).
2. **Production blocked** -- `check_production_feasibility()` queries `Bin.actual_qty` in the commissary warehouse, finds zero raw materials (e.g., A041 Rice Crispies Raw, A025 White Sugar), returns `can_produce: false`.
3. **Wastage fails** -- batch-tracked FG items (e.g., FG003 Rice Crispies, `has_batch_no=1`) have zero stock in Shaw BLVD - BKI, so no active batches exist. The Material Issue Stock Entry fails on submit.

**S121 context:** S121 (merged PR #349, 2026-03-25) fixed Shaw BLVD routing in `transforms.py` (Ian's warehouse sync path) but explicitly noted the store sync code path (`erp_sync.py`) was NOT affected. This sprint fixes the remaining code path.

## Design Rationale (For Cold-Start Agents)

**Why two Shaw BLVD warehouses exist:**
- `Shaw BLVD - BKI` = commissary (Bebang Kitchen Inc.), where production happens
- `Shaw BLVD - Bebang Enterprise Inc.` = legacy store warehouse, correctly disabled for store operations
- The commissary module's `get_commissary_warehouse()` prefers BKI warehouses. All inventory sync data for Shaw must go to BKI.

**Why the alias map must take precedence over company-preference lookup:**
- `_resolve_warehouse()` calls `_resolve_warehouse_exact_or_name()` first, which does a `warehouse_name` DB lookup with `WAREHOUSE_COMPANY_PREFERENCE = ("Bebang Enterprise Inc.", "Bebang Kitchen Inc.")`. BEI is checked first, so "Shaw BLVD" resolves to BEI before the alias map is ever consulted.
- Fix: check `WAREHOUSE_ALIAS_DOCNAME_MAP` before the generic exact/name lookup.

**No procurement impact:**
- Procurement syncs use full docnames (e.g., `"Shaw BLVD - Bebang Enterprise Inc."`) from existing PO/PR documents. These match exactly via `frappe.db.exists()` before the alias map is checked. Only shorthand labels from Google Sheets are affected.

## Scope

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| A1 | FIX | `hrms/api/erp_sync.py` | Change all Shaw entries in `WAREHOUSE_ALIAS_DOCNAME_MAP` from BEI to BKI | 1 |
| A2 | FIX | `hrms/api/erp_sync.py` | Collapse duplicate Shaw checks in `_resolve_warehouse_alias()` into single `"SHAW" in normalized -> BKI` | 1 |
| A3 | FIX | `hrms/api/erp_sync.py` | Add alias map pre-check in `_resolve_warehouse()` before generic exact/name lookup | 2 |
| B1 | DEPLOY | — | Deploy erp_sync.py changes to production (Frappe Docker) | 2 |
| B2 | VERIFY | — | Re-trigger inventory sync for Shaw BLVD via `erp_sync.sync_inventory` | 2 |
| C1 | VERIFY | — | Confirm Shaw BLVD - BKI has BOM raw materials stocked (A041, A025, etc.) | 1 |
| C2 | VERIFY | — | Test commissary production form (log production for any FG item) | 2 |
| C3 | VERIFY | — | Test commissary wastage form (log wastage for FG003 Rice Crispies) | 2 |
| D1 | CLOSEOUT | — | Update plan status, sprint registry, commit | 1 |

**Total: 14 units** (under 15-unit phase budget)

## Code Changes (Already Applied)

All 3 code changes (A1-A3) are already applied to `hrms/api/erp_sync.py` on the working tree. The executing agent must:

1. Verify the changes are present in the file
2. Create the sprint branch from production
3. Commit the changes
4. Create PR

### A1: Alias Map (lines 41-55)

All Shaw BLVD variants now route to `Shaw BLVD - BKI`:
```python
WAREHOUSE_ALIAS_DOCNAME_MAP = {
    # Shaw BLVD is the commissary, operated by BKI (Bebang Kitchen Inc.)
    "SHAW": "Shaw BLVD - BKI",
    "SHAW BOULEVARD": "Shaw BLVD - BKI",
    "SHAW BLVD": "Shaw BLVD - BKI",
    # ... all variants -> BKI
}
```

### A2: Fuzzy Matcher (line 338)

Collapsed two checks into one:
```python
if "SHAW" in normalized:
    return _resolve_warehouse_exact_or_name("Shaw BLVD - BKI")
```

### A3: Alias Map Pre-Check (lines 393-402)

Added alias map lookup before generic exact/name lookup:
```python
normalized = _normalize_warehouse_label(value)
docname_alias = WAREHOUSE_ALIAS_DOCNAME_MAP.get(normalized)
if docname_alias:
    resolved = _resolve_warehouse_exact_or_name(docname_alias)
    if resolved:
        return resolved
```

## Sentry Observability

No new `@frappe.whitelist()` endpoints are created or modified. The fix is in internal helper functions only. DM-7 not applicable.

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| test.commissary@bebang.ph | Open Production page, select any FG item with a BOM (e.g., FG004 Buko Pandan Jelly) | Feasibility check passes, production form is submittable | Raw materials still not in BKI warehouse |
| test.commissary@bebang.ph | Open Wastage page, select FG003 (Rice Crispies), qty=1, reason=contaminated | Batch dropdown shows active batches OR form submits without batch | FG003 still has zero stock in BKI |
| System | Query `Bin` for `Shaw BLVD - BKI` with `actual_qty > 0` | >= 30 items with stock (vs 22 before fix) | Sync did not route to BKI |
| System | Query `Bin` for items A041, A025 in `Shaw BLVD - BKI` | Both have `actual_qty > 0` | BOM raw materials still missing |

## Requirements Regression Checklist

- [ ] Do all Shaw BLVD aliases in `WAREHOUSE_ALIAS_DOCNAME_MAP` point to `"Shaw BLVD - BKI"`?
- [ ] Is the generic `"SHAW" in normalized` catch-all routing to BKI (not BEI)?
- [ ] Does `_resolve_warehouse()` check the alias map BEFORE `_resolve_warehouse_exact_or_name()`?
- [ ] Does `_resolve_warehouse("Shaw BLVD - Bebang Enterprise Inc.")` still return BEI? (exact match must still work for procurement)
- [ ] Is `erp_sync.py` syntax valid? (`python -c "import ast; ast.parse(open('hrms/api/erp_sync.py').read())"`)

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s124-commissary-inventory-routing-fix origin/production`
3. Verify code changes A1-A3 are present in `hrms/api/erp_sync.py` (they were applied on the working tree before branching -- cherry-pick or re-apply if needed).
4. Run Requirements Regression Checklist.
5. Commit, create PR via `gh pr create`.
6. **STOP.** User handles merge and deploy.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

## Autonomous Execution Contract

- completion_condition:
  - Code changes committed to branch `s124-commissary-inventory-routing-fix`
  - PR created and number recorded in SPRINT_REGISTRY.md
  - After user merges + deploys: inventory re-synced, L3 scenarios verified
  - Plan YAML status updated to COMPLETED and pushed
- stop_only_for:
  - Missing credentials/access
  - Merge conflict with production that can't be auto-resolved
  - L3 scenario failures after deploy that indicate a deeper issue
- continue_without_pause_through:
  - code verification, commit, PR creation, registry update
- blocker_policy:
  - programmatic -> fix and continue
  - environment/runtime -> debug, continue
  - business-data/policy -> pause
- signoff_authority: single-owner (Sam)
- canonical_closeout_artifacts:
  - `docs/plans/2026-03-26-sprint-124-commissary-inventory-routing-fix.md` (status -> COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (row updated)

## Execution Workflow

- Deploy changes: `/deploy-frappe`
- E2E testing: `/l3-v2`
