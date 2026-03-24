---
canonical_sprint_id: S111
status: DEPLOYED
branch: s111-submit-permission-hardening
pr: 343
created: 2026-03-24
completed_date: null
execution_summary: null
depends_on: null
audit: "2026-03-24 — CONDITIONAL GO, 3 blockers resolved by amendment v1"
---

# Sprint 110: Submit Permission Hardening — Commissary & Cross-Module

## Problem Statement

S108 fixed the "Serial and Batch Bundle" PermissionError in 3 `warehouse.py` submit calls. L3 testing discovered the **same bug pattern** exists across the entire commissary module and other API files. Additionally, commissary files have **zero Sentry instrumentation** on 60 of 69 `@frappe.whitelist()` endpoints.

### Bugs Discovered (S108 L3 Collateral)

**Bug 1: Unprotected `.submit()` calls across commissary**

15 `.submit()` calls across 5 commissary files have NO `_run_as_system_user("Administrator")` wrapping. Any non-admin user calling these endpoints with batched items will hit the same PermissionError Jay encountered:

> "does not have doctype access via role permission for document Serial and Batch Bundle"

| File | Line | Call | DocType | Risk | Wrap Pattern |
|------|------|------|---------|------|-------------|
| `commissary_bom.py` | 85 | `bom.submit()` | BOM | LOW | `_run_as_system_user` only |
| `commissary_bom.py` | 177 | `new_bom.submit()` | BOM | LOW | `_run_as_system_user` only |
| `commissary.py` | 646 | `se.submit()` | Stock Entry | **HIGH** | `_clear_legacy` + `_run_as_system_user` |
| `commissary.py` | 795 | `se.submit()` | Stock Entry | **HIGH** | `_clear_legacy` + `_run_as_system_user` |
| `commissary.py` | 976 | `sales_invoice.submit()` | Sales Invoice | MEDIUM | `_run_as_system_user` only |
| `commissary.py` | 990 | `purchase_invoice.submit()` | Purchase Invoice | MEDIUM | `_run_as_system_user` only |
| `commissary.py` | 2054 | `se.submit()` | Stock Entry | **HIGH** | `_clear_legacy` + `_run_as_system_user` |
| `commissary_dashboard.py` | 715 | `se.submit()` | Stock Entry | **HIGH** | `_clear_legacy` + `_run_as_system_user` |
| `commissary_quality.py` | 301 | `qi.submit()` | Quality Inspection | LOW | `_run_as_system_user` only |
| `commissary_quality.py` | 552 | `se.submit()` | Stock Entry | **HIGH** | `_clear_legacy` + `_run_as_system_user` |
| `commissary_requisition.py` | 258 | `mr.submit()` | Material Request | MEDIUM | `_run_as_system_user` only |
| `commissary_requisition.py` | 292 | `mr.submit()` | Material Request | MEDIUM | `_run_as_system_user` only |
| `commissary_requisition.py` | 615 | `wo.submit()` | Work Order | MEDIUM | `_run_as_system_user` only |
| `commissary_requisition.py` | 634 | `se.submit()` | Stock Entry | **HIGH** | `_clear_legacy` + `_run_as_system_user` |
| `commissary_requisition.py` | 670 | `se.submit()` | Stock Entry | **HIGH** | `_clear_legacy` + `_run_as_system_user` |

**Bug 2: Zero Sentry instrumentation on 60 of 69 commissary endpoints**

| File | `@frappe.whitelist()` count | `set_backend_observability_context()` count | Gap |
|------|---------------------------|---------------------------------------------|-----|
| `commissary_bom.py` | 5 | 0 | **5** |
| `commissary.py` | 25 | 0 | **25** |
| `commissary_requisition.py` | 16 | 0 | **16** |
| `commissary_quality.py` | 15 | 4 | **11** |
| `commissary_dashboard.py` | 8 | 5 | **3** |
| **Total** | **69** | **9** | **60** |

60 of 69 commissary endpoints have NO Sentry context. Errors in production are invisible.

### Known Deferred Gaps (Out of S110 Scope)

31 additional unprotected `.submit()` calls exist outside commissary (same bug pattern):
- `store.py`: 7 calls (5 Stock Entry, 1 MR, 1 JE)
- `inventory.py`: 9 calls (Stock Entry, Stock Reconciliation)
- `picking.py`: 1 call, `marketing_giveaways.py`: 1 call, `billing.py`: 1 JE, `pcf.py`: 1 JE
- `procurement.py`: 3 JV calls, `erp_sync.py`: 2 calls
- `supervisor.py`: 2 calls, `transfer_requests.py`: 1, `transfers.py`: 1

These are documented for a follow-on sprint. S110 focuses on commissary (the active production blocker).

## Design Rationale (For Cold-Start Agents)

**Why this exists:** S108 fixed 3 warehouse `.submit()` calls but the same bug exists in 15 more places across commissary. The commissary team uses Stock Entry submit paths daily for production logging, hub transfers, and wastage. Any batched item (FG004 Buko Pandan Jelly, FG002 Banana Cinnamon, etc.) will trigger the permission error.

**Why `_run_as_system_user("Administrator")` wrapping:** The codebase already uses this pattern (warehouse.py). The `.submit()` call needs elevated privileges because ERPNext v15 auto-creates Serial and Batch Bundle child documents during submit, and `ignore_permissions` on `.insert()` does NOT cascade to child docs created during `.submit()`. The `_run_as_system_user` context manager temporarily elevates the session user.

**Why TWO wrap patterns:** Stock Entry submits need BOTH `_clear_legacy_serial_batch_fields_after_auto_bundle()` AND `_run_as_system_user()`. Non-Stock-Entry DocTypes (BOM, Sales Invoice, Purchase Invoice, Quality Inspection, Material Request, Work Order) only need `_run_as_system_user()` because they do not create Serial and Batch Bundle child documents. `_clear_legacy_serial_batch_fields_after_auto_bundle` iterates `stock_entry.items` looking for `serial_and_batch_bundle` fields — calling it on non-Stock-Entry docs is a harmless no-op but misleading.

**Why local copies of `_run_as_system_user`:** The codebase already has local copies in `commissary_dashboard.py:36`, `store.py:44`, and `inventory.py:53`. Importing from `warehouse.py` at module level risks circular imports (warehouse.py lazily imports from commissary.py inside function bodies). Following the established pattern of local copies is safer.

**Why Sentry is included:** 60 of 69 commissary endpoints have zero observability. If commissary users hit errors, we have no Sentry trail. This was already proven by S108 — Jay's error was only caught because warehouse.py had Sentry.

**Source references:**
- S108 plan: `docs/plans/2026-03-24-sprint-108-stock-entry-submit-permissions.md`
- S108 L3 defects: `output/l3/S108/DEFECTS.md`
- Warehouse fix pattern: `hrms/api/warehouse.py` lines 860, 1348-1349
- Local copy pattern: `hrms/api/commissary_dashboard.py:36`, `hrms/api/store.py:44`
- ERPNext issue: `ignore_permissions` doesn't cascade to child docs during submit
- Audit findings: `output/plan-audit/submit-permission-hardening/`

## Scope

- **Files modified:** 5 (`commissary_bom.py`, `commissary.py`, `commissary_quality.py`, `commissary_dashboard.py`, `commissary_requisition.py`)
- **Submit wraps:** 15 calls (8 Stock Entry with `_clear_legacy` + wrap, 7 non-SE with wrap only)
- **Sentry additions:** 60 endpoints (5 + 25 + 16 + 11 + 3)
- **Total work units:** 12 (3 submit fix + 6 Sentry + 1 lint + 2 verify/deploy)
- **Risk:** LOW — mechanical wrapping of existing calls, proven pattern from S108

## Requirements Regression Checklist

- [ ] Are all 15 `.submit()` calls wrapped with `_run_as_system_user("Administrator")`?
- [ ] Is `_run_as_system_user` defined as a LOCAL COPY in each file that needs it (NOT imported from warehouse.py)?
- [ ] Are ONLY Stock Entry submits (8 calls) calling `_clear_legacy_serial_batch_fields_after_auto_bundle()` before submit?
- [ ] Are non-Stock-Entry submits (BOM, SI, PI, QI, MR, WO — 7 calls) wrapped with `_run_as_system_user` only, WITHOUT `_clear_legacy`?
- [ ] Does every `@frappe.whitelist()` function in all 5 files call `set_backend_observability_context()`?
- [ ] Is `from hrms.utils.sentry import set_backend_observability_context` imported in each file?
- [ ] Does `ruff format` and `ruff check` pass after changes?
- [ ] Are existing function signatures unchanged (no new required parameters)?
- [ ] Is the existing `frappe.db.savepoint` in `commissary_quality.py:298` preserved (not displaced by the wrap)?
- [ ] Does every new/modified `@frappe.whitelist()` endpoint call `set_backend_observability_context()`?

**HARD BLOCKER:** Do NOT import `_run_as_system_user` from `warehouse.py` at module level. This risks circular imports because `warehouse.py` lazily imports from `commissary.py`. Instead, define a local copy of `_run_as_system_user` in each commissary file (follow the pattern already used in `commissary_dashboard.py:36`, `store.py:44`, `inventory.py:53`).

**HARD BLOCKER:** `_clear_legacy_serial_batch_fields_after_auto_bundle` must ONLY be called before Stock Entry submits. Do NOT call it before BOM, Sales Invoice, Purchase Invoice, Quality Inspection, Material Request, or Work Order submits — it is a no-op on those DocTypes.

## Phase 1: Wrap Submit Calls (3 units)

### Task 1.1: Fix `commissary_bom.py` (2 submit calls)

Lines 85 and 177. Both are BOM submits — wrap with `_run_as_system_user` only (NO `_clear_legacy`).

Add a local `_run_as_system_user` context manager definition (copy from `commissary_dashboard.py:36`).

```python
# Pattern for NON-Stock-Entry DocTypes:
with _run_as_system_user("Administrator"):
    bom.submit()
```

### Task 1.2: Fix `commissary.py` (5 submit calls)

Lines 646, 795, 2054 (Stock Entry), 976 (Sales Invoice), 990 (Purchase Invoice).

Add a local `_run_as_system_user` context manager AND a local `_clear_legacy_serial_batch_fields_after_auto_bundle` (copy from `warehouse.py:182`).

```python
# Pattern for Stock Entry submits (lines 646, 795, 2054):
_clear_legacy_serial_batch_fields_after_auto_bundle(se)
with _run_as_system_user("Administrator"):
    se.submit()

# Pattern for non-Stock-Entry submits (lines 976, 990):
with _run_as_system_user("Administrator"):
    sales_invoice.submit()
```

### Task 1.3: Fix `commissary_dashboard.py`, `commissary_quality.py`, `commissary_requisition.py` (8 submit calls)

**`commissary_dashboard.py:715`** — Stock Entry. Already has local `_run_as_system_user` at line 36. Add local `_clear_legacy` copy and call before submit.

**`commissary_quality.py:301`** — Quality Inspection (wrap only, NO `_clear_legacy`). Preserve existing `frappe.db.savepoint("quality_inspection")` at line 298 — keep savepoint OUTSIDE the `_run_as_system_user` context.
**`commissary_quality.py:552`** — Stock Entry (`_clear_legacy` + wrap).

**`commissary_requisition.py:258,292`** — Material Request (wrap only).
**`commissary_requisition.py:615`** — Work Order (wrap only).
**`commissary_requisition.py:634,670`** — Stock Entry (`_clear_legacy` + wrap).

## Phase 2: Add Sentry Instrumentation (6 units)

### Task 2.1: Instrument `commissary_bom.py` (5 endpoints, 0 covered)

Add `set_backend_observability_context(module="commissary", action="<function_name>", mutation_type="<type>")` to all 5 `@frappe.whitelist()` functions.

### Task 2.2: Instrument `commissary.py` (25 endpoints, 0 covered)

Add Sentry context to all 25 `@frappe.whitelist()` functions. Use `module="commissary"` for all.

### Task 2.3: Instrument `commissary_requisition.py` (16 endpoints, 0 covered)

Add Sentry context to all 16 `@frappe.whitelist()` functions. Use `module="commissary"`.

### Task 2.4: Instrument remaining gaps in `commissary_quality.py` (11 uncovered) and `commissary_dashboard.py` (3 uncovered)

These already have partial coverage (4/15 and 5/8). Add Sentry to the remaining 11 + 3 = 14 uncovered endpoints.

### Task 2.5: Run ruff format + ruff check (1 unit)

Fix any linting issues introduced across all 5 files.

## Phase 3: Deploy + Verify (2 units)

### Task 3.1: Create PR, governor merge + deploy

Branch: `s111-submit-permission-hardening`
PR target: `production`

If governor issues merge conflict: `git fetch origin production && git rebase origin/production`, resolve conflicts, `git push --force-with-lease`. Governor will re-review.

### Task 3.2: Verify fix live + collect L3 evidence

Test commissary submit paths as non-admin user. Write evidence to `output/l3/S111/`.

**Required evidence files before closeout:**
- `output/l3/S111/api_mutations.json` — one entry per DocType tested
- `output/l3/S111/state_verification.json` — docstatus=1 confirmed, no PermissionError
- `output/l3/S111/form_submissions.json` — submit payloads and responses

### Rollback Plan

If a submit wrap breaks a commissary workflow post-deploy:
1. `git revert <merge-commit-sha>` on production
2. Push to trigger governor re-deploy
3. Expected time-to-rollback: ~5 minutes (governor pipeline)

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| test.commissary@bebang.ph | API: `commissary.log_production` with item_code=FG004, qty=1 | Success or NegativeStockError — NOT PermissionError | Stock Entry submit wrap not working |
| test.commissary@bebang.ph | API: `commissary.create_hub_transfer` with batched item | Success or stock error — NOT PermissionError | Hub transfer submit wrap not working |
| test.commissary@bebang.ph | API: `commissary_bom.create_bom` item_code=FG002, materials=[{item_code: RM001, qty: 1}] | BOM created and submitted — NOT PermissionError | BOM submit wrap not working |
| test.commissary@bebang.ph | API: `commissary_requisition.create_material_request` with test items | MR submitted — NOT PermissionError | MR submit wrap not working |
| test.commissary@bebang.ph | API: `commissary_quality.create_quality_inspection` for a batch | QI submitted — NOT PermissionError | QI submit wrap not working |
| test.commissary@bebang.ph | API: `commissary_requisition.start_work_order` | WO submitted — NOT PermissionError | WO submit wrap not working |
| sam@bebang.ph | Sentry API: check `bei-hrms` for events with `module=commissary` in last 30 min | Events with `action=log_production` or similar appear | Sentry instrumentation not deployed |

## Autonomous Execution Contract

- completion_condition:
  - all 15 submit calls wrapped (8 SE with `_clear_legacy` + wrap, 7 non-SE with wrap only)
  - all 60 uncovered endpoints have Sentry
  - ruff passes
  - PR merged by governor
  - live verification shows no permission error on commissary submits
  - L3 evidence files committed to branch (`git add -f output/l3/S111/ && git push`)
  - plan YAML status updated to COMPLETED and pushed (`git add -f docs/plans/`)
  - SPRINT_REGISTRY.md updated and pushed (`git add -f docs/plans/SPRINT_REGISTRY.md`)
- stop_only_for:
  - missing credentials/access
  - governor REJECT with unresolvable issue
- continue_without_pause_through:
  - implement -> PR -> governor poll -> deploy -> verify -> closeout
- blocker_policy:
  - programmatic -> fix and continue
  - governor REJECT -> read PR comment, fix code, push to same branch
  - governor NEEDS_FIX -> apply suggested fix, push to same branch
  - governor Merge Conflict -> `git fetch origin production && git rebase origin/production`, resolve, force-push
  - governor Deploy Failure -> check deploy logs, fix if code issue, push fix
- signoff_authority: single-owner

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s111-submit-permission-hardening origin/production`. NEVER write code on production. Verify: `git branch --show-current` must return `s111-submit-permission-hardening`.
3. **Verify helper pattern:** Read `hrms/api/commissary_dashboard.py:36` for the local `_run_as_system_user` copy. Read `hrms/api/warehouse.py:182` for `_clear_legacy_serial_batch_fields_after_auto_bundle`. These will be copied locally into each file that needs them.
4. **Phase 1:** Wrap all 15 submit calls using the TWO patterns:
   - Stock Entry (8 calls): `_clear_legacy` + `_run_as_system_user` wrap
   - Non-Stock-Entry (7 calls): `_run_as_system_user` wrap only
5. **Phase 2:** Add Sentry to all 60 uncovered endpoints across 5 files.
6. Run `ruff format` and `ruff check` on all 5 modified files.
7. Commit, push, create PR via `gh pr create`.
8. Poll governor for merge + deploy. Handle feedback per blocker_policy.
9. **Phase 3:** Verify fix live. Write evidence to `output/l3/S111/`.
10. Commit evidence: `git add -f output/l3/S111/ && git push`.
11. Closeout: update plan YAML + SPRINT_REGISTRY.md. `git add -f docs/plans/ && git push`.

## Sentry Observability

All 5 commissary files will have full Sentry coverage after this sprint:
- `commissary_bom.py` — 0 -> 5 endpoints instrumented (+5)
- `commissary.py` — 0 -> 25 endpoints instrumented (+25)
- `commissary_requisition.py` — 0 -> 16 endpoints instrumented (+16)
- `commissary_quality.py` — 4 -> 15 endpoints instrumented (+11)
- `commissary_dashboard.py` — 5 -> 8 endpoints instrumented (+3)
- **Total: 60 endpoints added**

Sentry project: `bei-hrms` (org: `bebang-enterprise-inc`)

## Execution Workflow
- Test Python changes: `/local-frappe`
- Deploy changes: governor-managed (create PR, governor handles merge + deploy + L1)
- E2E testing: API verification post-deploy

## Audit History

### v1 (2026-03-24) — 3 auditors, CONDITIONAL GO -> amended

Findings resolved by amendment:
1. **Sentry count 42 -> 60** — arithmetic error in original plan. 3 zero-coverage files = 46, plus 14 partial gaps = 60 total. Fixed in all sections.
2. **Two wrap patterns** — `_clear_legacy` only applies to Stock Entry submits (8 of 15). Non-SE DocTypes (BOM, SI, PI, QI, MR, WO) get `_run_as_system_user` only. Added Wrap Pattern column to submit table and split instructions in Phase 1.
3. **Local copy, not import** — `_run_as_system_user` must be a local copy per file (existing codebase pattern), not imported from warehouse.py (circular import risk). Updated HARD BLOCKER and boot sequence.
4. **L3 evidence files required** — added evidence file contract to Phase 3 and completion_condition.
5. **Governor conflict handling** — added merge conflict resolution to blocker_policy.
6. **Rollback plan** — added rollback section.
7. **`git add -f`** — added to closeout for docs/ and output/.
8. **Branch verification** — added `git branch --show-current` check to boot sequence.
9. **L3 scenarios expanded** — added Quality Inspection, Work Order, hub transfer scenarios (was 4, now 7).

Findings accepted as deferred:
- 31 unprotected submit calls outside commissary (store.py, inventory.py, etc.) — documented in Known Deferred Gaps.
- SI+PI async function missing `frappe.db.savepoint()` (DM-2) — out of S110 scope, flagged for follow-on.
- WO+SE sequence missing savepoint — out of S110 scope.

Audit artifacts: `output/plan-audit/submit-permission-hardening/`
