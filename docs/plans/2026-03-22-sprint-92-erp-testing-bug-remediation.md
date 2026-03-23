# Sprint 92 — ERP Testing Bug Remediation (v3 — Hardened)

```yaml
canonical_sprint_id: S092
status: COMPLETED
completed_date: 2026-03-23
date: 2026-03-22
lanes: none
depends_on: none
total_work_units: 41
execution_summary:
  backend_pr: "hrms#309 (merged 2026-03-22T17:33Z, deploy SUCCESS)"
  frontend_pr_1: "bei-tasks#225 (merged 2026-03-22T17:39Z, Vercel SUCCESS)"
  frontend_pr_2: "bei-tasks#226 billing view-only (merged 2026-03-23T01:06Z, Vercel SUCCESS)"
  l3_regression: "7/8 PASS — REG-006 failure was pre-existing (fixed in PR #226)"
  fixes_shipped: 7 backend + 4 frontend + 1 billing view-only
  not_needed: "FIX-1 backend (normalization already handled TIN), FIX-3B (MR status already correct)"
  deferred: "ACCESS-003 vehicle creation UI (no standalone form exists)"
audit_history:
  - v1 (2026-03-22): initial plan, 42 units, 10 bugs
  - v2 (2026-03-22): 6-domain audit + code verifier, 5 critical blockers resolved
  - v3 (2026-03-23): deep forensic code audit, 4 root causes corrected, 2 items dropped, 3 new gaps added
  - v3.1 (2026-03-23): execution complete, L3 regression tested, billing false-affordance fixed
```

## Purpose

Fix all unresolved bugs and access issues reported during ERP user testing (March 19-20, 2026). This plan was rewritten after deep forensic code audit that changed the root cause for 4 of 10 bugs and dropped 2 items as not-bugs.

**Source evidence:**
- `tmp/s092_hardened_fix_matrix.md` — hardened fix table with exact line numbers (AUTHORITATIVE)
- `tmp/s092_deep_audit_bug001.md` — BUG-001 deep code audit
- `tmp/s092_deep_audit_logistics_warehouse.md` — logistics/warehouse deep code audit
- `tmp/s092_deep_audit_commissary_frontend.md` — commissary/frontend deep code audit
- `output/plan-audit/s092-erp-testing-bug-remediation/` — 6-domain audit + code verifier findings

---

## Design Rationale (For Cold-Start Agents)

### Why this exists
The team tested the ERP on March 19-20. 8 users across 5 departments reported 13 bugs and 3 access issues. 5 were fixed live (S081). 10 remained. Deep code audit reduced this to **8 real fixes** — 2 items were not bugs (ACCESS-002 is by design, ACCESS-003 is a frontend UI gap not a missing endpoint).

### Why this architecture — key corrections from deep audit
1. **BUG-001 is a frontend bug, not backend.** Backend `calculate_totals()` is correct. The frontend sends ex-VAT `grandTotal`. The "subtotal only counts first item" report was a misinterpretation — the number jumped because VAT was added server-side.
2. **BUG-006 needs a one-line fix, not 3 new role sets.** `create_trip` (dispatch.py:697) uses `SCM_ADMIN_ROLES` but `create_trip_from_route` (dispatch.py:1650) already uses `SCM_DISPATCH_ROLES`. They do the same thing. Just align the role set.
3. **ACCESS-002 (route editing) is intentionally admin-only.** Dropped from scope.
4. **ACCESS-003 (vehicle creation) — DocType already grants Warehouse User create permission.** The blocker is a missing frontend form. Investigate only; no backend endpoint needed.
5. **BUG-010 wastage has 7 reason codes** (not 6) and the real bug is unhandled `se.submit()` exceptions, not reason code validation.
6. **BUG-012 must use "With Issues" status** (not "Rejected" which doesn't exist in the DocType).
7. **BUG-011 has 3 missing pieces** (backend role check + frontend canManageStoreSchedule + roleToPersona mapping) plus a WAREHOUSE_USER frontend/backend mismatch.

### Known limitations
- Chat image attachments not downloadable via API. Bug symptoms from text descriptions only.
- "Commissary Supervisor" Frappe Role may not exist as a fixture — Phase 0 gate.
- MR status flow must be verified before FIX-3 can be finalized — Phase 0 gate.

---

## Requirements Regression Checklist

- [ ] All fixes preserve existing passing tests (`pytest hrms/tests/` green)
- [ ] `SCM_ADMIN_ROLES` is NOT modified (audit B-01)
- [ ] `create_trip` uses `SCM_DISPATCH_ROLES` (matches `create_trip_from_route`)
- [ ] PO server-side sum is AFTER rate→unit_cost normalization at line 899 (audit B-05)
- [ ] Frontend PO form sends VAT-inclusive grandTotal
- [ ] Wastage logging handles all 7 valid reason codes (not 6)
- [ ] Wastage `se.insert()/se.submit()` wrapped in try/except
- [ ] Wastage has permission check (currently has none)
- [ ] Warehouse receiving uses "With Issues" status (NOT "Rejected" — doesn't exist)
- [ ] `_run_as_system_user()` removed from warehouse.py (lines 647-649 and 1100-1105)
- [ ] Labor Plan: backend + frontend + roleToPersona all fixed together
- [ ] Sidebar: `"commissary"` in WAREHOUSE_USER `secondaryGroups` (not just allowList)
- [ ] WAREHOUSE_USER canManageStoreSchedule/backend mismatch resolved
- [ ] "Commissary Supervisor" Frappe Role verified to exist before deploying
- [ ] Backend PR merged before frontend PR (merge order)

---

## Phase 0 — Pre-Flight & Gates (3 units)

### Task 0.1: Verify production baseline
- Pull latest `production` branch, record SHA
- Run `pytest hrms/tests/ -x -q` to establish green baseline

### Task 0.2: Three mandatory gates
**GATE 1:** Check if Commissary Supervisor Frappe Role exists:
```python
frappe.db.exists("Role", "Commissary Supervisor")
```
If FALSE: create the Role via `frappe.get_doc({"doctype": "Role", "role_name": "Commissary Supervisor"}).insert()` before proceeding with FIX-7/FIX-8.

**GATE 2:** Read `approve_material_request` (warehouse.py:787-930) and confirm what MR status it sets after approval. If it does NOT set one of `"Ordered"`, `"Partially Ordered"`, or `"Transferred"`, that is the root cause of BUG-008/009 — the fix is aligning the status string, not changing `create_stock_transfer`.

**GATE 3:** Check if bei-tasks has a standalone vehicle creation form:
```bash
grep -r "create_vehicle\|add.*vehicle\|new.*vehicle" ../bei-tasks/app/ --include="*.tsx"
```
If found: ACCESS-003 is a frontend wiring issue. If not found: note for future sprint (not in S092 scope).

### Task 0.3: Reproduce bugs locally
- Test each bug against current code
- Skip any already fixed (update plan status)

---

## Phase 1 — PO Subtotal Fix (4 units)

### Task 1.1: Fix frontend PO grandTotal (BUG-001 primary fix) [EXTEND]
**File:** `../bei-tasks/app/dashboard/procurement/purchase-orders/new/page.tsx`
**Line:** 290
**Current:** `grandTotal: sub` (sends ex-VAT total)
**Fix:** `grandTotal: sub + (sub * 0.12)` — send VAT-inclusive total matching backend calculation.
Also add a VAT line to the form display so the user sees the breakdown.
**Test:** Create PO with 3 items. Form total must match saved PO total (no "jump").

### Task 1.2: Fix backend TIN threshold (BUG-001 secondary fix) [EXTEND]
**File:** `hrms/api/procurement.py`
**Line:** 867
**Current:** `po_value = flt(data.get("grand_total", 0))` — reads frontend (potentially wrong) value
**HARD BLOCKER:** The rate→unit_cost normalization is at lines 895-899. Server-side sum MUST be placed AFTER line 899.
**Fix:** After line 899, replace the TIN check's `po_value`:
```python
# After rate→unit_cost normalization (line 899)
po_value = sum(flt(i.get('unit_cost', 0)) * flt(i.get('qty', 0)) for i in data.get('items', []))
po_value_with_vat = po_value * 1.12
```
Use `po_value_with_vat` for TIN threshold check. Return `{"grand_total": po.grand_total, "subtotal": po.subtotal}` in API response.
**Test:** Create PO with items sent as `rate` (not `unit_cost`). Verify TIN check fires at VAT-inclusive value.

---

## Phase 2 — Logistics & Warehouse Fixes (12 units)

### Task 2.1: Fix trip creation role (BUG-006) [EXTEND]
**File:** `hrms/api/dispatch.py`
**Line:** 697
**Current:** `_check_scm_permission(SCM_ADMIN_ROLES, "create trips")`
**Fix:** `_check_scm_permission(SCM_DISPATCH_ROLES, "create trips")`
**DO NOT** create new role sets. DO NOT modify `scm_roles.py`. `SCM_DISPATCH_ROLES` already includes Warehouse User and is used by `create_trip_from_route` (line 1650) for the same operation.
**Test:** Warehouse User creates trip → 200. Billing endpoint → still 403 (SCM_ADMIN_ROLES unchanged).

### Task 2.2: Fix transfer 417 (BUG-008/009) [EXTEND]
**File:** `hrms/api/warehouse.py`
**Depends on:** Phase 0 GATE 2 (MR status investigation)
**Fix A — Blank source_warehouse guard:** Before `se.submit()` (~line 1098), add:
```python
if not source_warehouse:
    frappe.throw(_("Cannot create stock transfer: source warehouse is not set on Material Request {0}").format(mr_name))
```
**Fix B — MR status alignment:** If GATE 2 reveals `approve_material_request` sets a status not in `("Ordered", "Partially Ordered", "Transferred")`, add that status to the accepted set at line 997.
**Fix C — Remove `_run_as_system_user`:** Delete session elevation at lines 1100-1105. `ignore_permissions=True` is already set. Session swap misattributes stock entries to Administrator.
**Test:** Approve MR → create transfer → 200. Blank source_warehouse → clear error message.

### Task 2.3: Support full item rejection (BUG-012) [EXTEND]
**File:** `hrms/api/warehouse.py`
**Lines:** 607-608
**Current:** `if not accepted_items: frappe.throw(_("No accepted quantity..."))`
**CRITICAL:** Use `"With Issues"` status, NOT `"Rejected"`. BEI Warehouse Receiving DocType status options are: `Pending Warehouse Receive`, `Completed`, `With Issues`, `Cancelled`. There is NO `"Rejected"` option.
**Fix:**
```python
if not accepted_items:
    if rejected_items:
        # Full rejection is valid — set status and return
        receiving_doc.status = "With Issues"
        receiving_doc.save(ignore_permissions=True)
        frappe.db.commit()
        return {"success": True, "status": "fully_rejected", "rejected_items": rejected_items}
    frappe.throw(_("No accepted quantity to receive into warehouse"))
```
**Also fix:** Remove `_run_as_system_user()` at lines 647-649. `_enable_role_gated_write()` at line 646 already handles permissions.
**Test:** 100% rejected items → "With Issues" status, no throw. Partial acceptance → stock entries show real user (not Administrator).

### Task 2.4: Fix zero-quantity display (BUG-013) [EXTEND]
**File:** `hrms/api/warehouse.py`
**Lines:** 727-783 (`get_material_request_items`)
**Current:** Blank `from_warehouse` → Bin query skipped → `available_qty=0`
**Fix:** When `from_warehouse` is blank, resolve via `get_commissary_warehouse()` (commissary.py:39-71, 4-step waterfall). If still blank, sum across all warehouses:
```python
from hrms.api.commissary import get_commissary_warehouse

if not from_warehouse:
    from_warehouse = get_commissary_warehouse()
if from_warehouse:
    bin_qty = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": from_warehouse}, "actual_qty") or 0
else:
    bin_qty = flt(frappe.db.sql("SELECT SUM(actual_qty) FROM `tabBin` WHERE item_code = %s", item_code)[0][0])
```
**WARNING:** `get_commissary_warehouse()` never raises — silently falls back to canonical constant. Log which warehouse was resolved.
**Test:** MR item with blank from_warehouse → available_qty > 0 if stock exists.

### Task 2.5: Investigate vehicle creation UI (ACCESS-003) [INVESTIGATE]
**NOT a code fix.** Phase 0 GATE 3 determines if bei-tasks has a vehicle form.
- If yes: wire existing form to `_resolve_or_create_departure_vehicle` via `confirm_departure`
- If no: document as future sprint item (vehicle master management UI)
- Backend endpoint is NOT needed — DocType already grants Warehouse User `create=1`
**Deliverable:** Investigation note in bug tracker. No code change unless GATE 3 finds existing form.

### Task 2.6: Write tests for Phase 2 [BUILD]
**File:** `hrms/tests/test_s092_logistics_warehouse_fixes.py` (new)
- Warehouse User can create trip via `SCM_DISPATCH_ROLES`
- Warehouse User CANNOT access billing (SCM_ADMIN_ROLES unchanged)
- Transfer with blank source_warehouse returns clear error
- Full rejection sets "With Issues" status (not throw)
- MR items with blank from_warehouse show resolved stock qty

---

## Phase 3 — Commissary & RBAC Fixes (10 units)

### Task 3.1: Harden wastage logging (BUG-010) [EXTEND]
**File:** `hrms/api/commissary_quality.py`
**Lines:** 328-442 (`log_wastage`)
**Reason codes (7):** `expired`, `damaged`, `quality_fail`, `contaminated`, `production_loss`, `sampling`, `other`
**Fix 1 — Unhandled exception:** Wrap `se.insert()`/`se.submit()` at lines 426-427:
```python
try:
    se.insert(ignore_permissions=True)
    se.submit()
except Exception as e:
    frappe.db.rollback()
    return {"success": False, "error": f"Stock entry failed: {str(e)}"}
```
**Fix 2 — Missing permission check:** Add at function start:
```python
from hrms.utils.scm_roles import SCM_RECEIVING_ROLES
_check_scm_permission(SCM_RECEIVING_ROLES, "log wastage")
```
**Fix 3 — Log warehouse resolution:** After `get_commissary_warehouse()`, add `frappe.logger().info(f"Wastage warehouse resolved to: {warehouse}")`.
**Test:** 7 valid codes → success. Invalid code → structured error. Force stock validation fail → structured error (not 500). Unauthorized user → 403.

### Task 3.2: Fix Labor Plan visibility (BUG-011) [EXTEND]
**Pre-req:** Phase 0 GATE 1 — Commissary Supervisor role must exist in Frappe.

**Backend fix** — `hrms/api/supervisor.py:284`:
Add `"Commissary Supervisor"` to the fast-path role intersection:
```python
if user_roles.intersection({"System Manager", "Administrator", "HR User", "HR Manager", "Commissary Supervisor"}):
    return True
```

**WAREHOUSE_USER mismatch fix** — same function:
`canManageStoreSchedule` (frontend) includes WAREHOUSE_USER but `_user_can_manage_store_schedule` (backend) does NOT. Decision: **remove WAREHOUSE_USER from frontend** `canManageStoreSchedule` — Warehouse Users should not manage store schedules (they manage warehouse operations). This aligns frontend with backend without granting unintended access.

**Frontend fix 1** — `../bei-tasks/lib/roles.ts:716`:
Add `ROLES.COMMISSARY_SUPERVISOR` to hasRole array. Remove `ROLES.WAREHOUSE_USER` (mismatch fix):
```typescript
if (hasRole(userRoles, [
  ROLES.STORE_SUPERVISOR, ROLES.AREA_SUPERVISOR,
  ROLES.HR_USER, ROLES.HR_MANAGER,
  ROLES.COMMISSARY_SUPERVISOR,  // ADD
  // ROLES.WAREHOUSE_USER removed — backend doesn't support it
]))
```

**Frontend fix 2** — `../bei-tasks/lib/navigation-personas.ts:506`:
Add COMMISSARY_SUPERVISOR to `roleToPersona`:
```typescript
[ROLES.COMMISSARY_SUPERVISOR, "COMMISSARY_SUPERVISOR"],  // before WAREHOUSE_USER line
```

**Test:** Login as commissary.team → Labor Plan in sidebar. API call → 200. Refresh → persists. Warehouse User → NO Labor Plan tab (aligned with backend).

### Task 3.3: Fix QA/Commissary sidebar (ACCESS-001) [EXTEND]
**File:** `../bei-tasks/lib/sidebar-role-profiles.ts`

**Fix 1 — WAREHOUSE_USER profile (lines 60-83):**
Add `"commissary"` to `secondaryGroups` and commissary routes to `itemAllowList`:
```typescript
{
  roles: [ROLES.WAREHOUSE_USER, ROLES.DRIVER],
  profile: {
    primaryGroups: ["home", "warehouse"],
    secondaryGroups: ["commissary"],  // ADD
    itemAllowList: {
      home: [...],
      warehouse: [...],
      commissary: [ROUTES.COMMISSARY_QUALITY, ROUTES.COMMISSARY_WASTAGE],  // ADD
    },
  },
},
```

**Fix 2 — Merge logic (lines 108-112):**
Change `getSidebarProfileForRoles` from first-match-wins to union merge for multi-role users. Merge `primaryGroups`, `secondaryGroups`, and `itemAllowList`.

**HARD BLOCKER:** Single-role WAREHOUSE_USER must see warehouse + commissary QA/wastage. No regression for other roles.
**Test:** (a) Warehouse-only → warehouse + commissary QA visible. (b) Dual-role → full commissary + warehouse. (c) Store Supervisor → unchanged.

### Task 3.4: Write tests for Phase 3 [BUILD]
**File:** `hrms/tests/test_s092_commissary_fixes.py` (new)
- Wastage with each of 7 valid codes → success
- Wastage with invalid code → structured error
- Wastage stock failure → structured error (not 500)
- Unauthorized wastage call → 403
- Labor plan bootstrap for Commissary Supervisor → 200
- Labor plan bootstrap for Warehouse User → 403 (mismatch fix)

---

## Phase 4 — Test, PR, Governor Poll, Live Verification & Bug-Fix Loop (12 units)

> **The agent does NOT stop working after PR creation.** The full chain is:
> `local test → PR → poll governor → post-deploy L2-L4 like a real user → fix bugs → push → governor re-deploys → retest → closeout`

### Task 4.1: Run full test suite (local)
`pytest hrms/tests/ -x -q` — all existing + new tests green before any PR.

### Task 4.2: Create backend PR (hrms)
- Branch: `fix/s092-erp-testing-bugs`
- PR against `production` via `gh pr create`
- **Docker build:** Full build (`skip_build=false`, `no_cache=true`)
- **Rollback target:** SHA `857342975`

### Task 4.3: Poll governor until backend PR merges
The agent does NOT stop after PR creation. Poll until governor merges or rejects:
```bash
# Poll every 60s, timeout after 20 minutes
for i in $(seq 1 20); do
  state=$(gh pr view <PR_NUMBER> --repo Bebang-Enterprise-Inc/hrms --json state -q '.state')
  if [ "$state" = "MERGED" ]; then echo "MERGED"; break; fi
  if [ "$state" = "CLOSED" ]; then echo "REJECTED"; break; fi
  sleep 60
done
```
- **If MERGED:** continue to Task 4.4
- **If REJECTED/CLOSED:** read governor review comments, fix the issues, push to the same branch. Governor auto-re-reviews. Return to polling.
- **If timeout (20 min):** check governor health, check for merge conflicts. If conflict: rebase and force-push. If governor is down: flag as blocker but do NOT merge manually.

### Task 4.4: Create frontend PR (bei-tasks) — AFTER backend is deployed
- **Merge order:** Backend PR MUST be merged and deployed FIRST. Frontend RBAC changes reference backend endpoints that must exist.
- Branch in bei-tasks, PR against `main`
- Vercel auto-deploys preview on PR, production on merge to `main`
- Poll until merged (same pattern as Task 4.3, but for bei-tasks repo)

### Task 4.5: Live L2-L4 verification — test LIKE A REAL USER
After both PRs are merged and deployed, test on production as a real user would:

**L1 — API smoke (automated):**
- `create_purchase_order` with 3 multi-item payload → 200, verify VAT-inclusive grand_total
- `create_trip` as Warehouse User → 200
- `create_stock_transfer` with blank source_warehouse → clear error (not 417)
- `log_wastage` with valid reason → 200
- `log_wastage` as unauthorized user → 403
- `get_labor_plan_bootstrap` as commissary.team → 200
- `complete_warehouse_receiving` with 100% rejected → 200, status = "With Issues"
- `get_material_request_items` with blank from_warehouse → available_qty > 0

**L2 — Page render verification (browser via `/l2-page-check`):**
- Login as `commissary.team` on my.bebang.ph → page loads, no console errors
- Navigate to Labor Plan → tab visible in sidebar, page renders
- Navigate to QA queue → visible, page renders
- Login as `warehouse.user` → page loads
- Navigate to trip creation → page renders, form submits

**L3 — Workflow scenarios (browser via `/l3-v2`):**
- commissary.team: open Labor Plan → create plan → verify success toast
- commissary.team: open QA → log wastage with "expired" reason → verify success
- warehouse.user: create trip → assign driver → verify trip appears in list
- warehouse.user: open receiving → reject all items → verify "With Issues" status

**L4 — Negative/regression probes:**
- Warehouse User attempts billing endpoint → 403 (SCM_ADMIN_ROLES unchanged)
- Store Supervisor sidebar → unchanged from before (no regression)
- Invalid wastage reason code → structured error
- PO with items using `rate` field → TIN threshold computed correctly

### Task 4.6: Bug-fix loop (if L2-L4 failures found)
**If any L2-L4 test fails:**
1. Diagnose the failure from browser evidence / API response
2. Fix the code locally
3. Run `pytest hrms/tests/ -x -q` to verify no regression
4. Push fix to the SAME feature branch (not a new branch)
5. Governor auto-detects the push, re-reviews, re-deploys
6. Poll governor until merged (same as Task 4.3)
7. Re-run the failing L2-L4 tests
8. Repeat until ALL L2-L4 pass

**This loop continues until zero failures.** The agent does NOT declare success after one pass.

### Task 4.7: Closeout — update tracker + notify team
Only after ALL L1-L4 pass on production:
- Update `tmp/erp_chat_bugs_and_recommendations.md` with FIXED status for each bug
- Update `docs/plans/SPRINT_REGISTRY.md` with completion status
- Post summary to ERP Chat space via `/chat`

---

## Shell Prevention (S026)

Touches 3 operator-facing surfaces: sidebar profiles, Labor Plan tab, QA queue.

| Failure Pattern | Gate | Task |
|----------------|------|------|
| Role mismatch (sidebar shows items user can't access) | gate_action_wiring_complete | 3.2 — backend + frontend fixed together |
| Missing backend wiring (nav visible but API returns 403) | gate_dependency_map_complete | 3.2 — verify API returns 200 for commissary.team |
| Regression (single-role users lose sidebar items) | gate_navigation_placement_defined | 3.3 — HARD BLOCKER test |
| No-op fix (allowList without primaryGroups) | gate_dependency_map_complete | 3.3 — `secondaryGroups` added |

---

## Ground-Truth Lock (S028)

```yaml
evidence_sources:
  - tmp/s092_hardened_fix_matrix.md -> AUTHORITATIVE fix table with line numbers
  - tmp/s092_deep_audit_bug001.md -> BUG-001 forensic evidence
  - tmp/s092_deep_audit_logistics_warehouse.md -> logistics/warehouse forensic evidence
  - tmp/s092_deep_audit_commissary_frontend.md -> commissary/frontend forensic evidence
  - output/plan-audit/s092-erp-testing-bug-remediation/code_verification.md -> code verifier results
count_method:
  metric: fixes
  basis: hardened fix matrix entries
  method: count FIX-N entries in tmp/s092_hardened_fix_matrix.md
authoritative_sections:
  Phases 0-4 are authoritative for execution. Amendment log is traceability only.
```

---

## Phase Budget Contract (S029)

```yaml
phase_unit_budget:
  Phase 0: 3
  Phase 1: 4
  Phase 2: 12
  Phase 3: 10
  Phase 4: 12 (includes governor polling, L2-L4 browser testing, bug-fix loop)
total: 41
hard_limit: 15
preferred_split_threshold: 12
```

---

## Anti-Rewind Protection (S087)

```yaml
remote_truth_baseline:
  hrms: {branch: production, head_sha: "857342975"}
  bei-tasks: {branch: main, head_sha: "48c69c8"}

surface_ownership:
  - hrms/api/dispatch.py:697 -> S092 (one-line role change)
  - hrms/api/warehouse.py -> S092 (4 fixes: transfer, rejection, zero-qty, _run_as_system_user)
  - hrms/api/procurement.py:867 -> S092 (TIN threshold fix)
  - hrms/api/commissary_quality.py:426-427 -> S092 (wastage try/except)
  - hrms/api/supervisor.py:284 -> S092 (labor plan role check)
  - ../bei-tasks/app/dashboard/procurement/purchase-orders/new/page.tsx:290 -> S092 (VAT fix)
  - ../bei-tasks/lib/roles.ts:716 -> S092 (canManageStoreSchedule)
  - ../bei-tasks/lib/navigation-personas.ts:506 -> S092 (roleToPersona)
  - ../bei-tasks/lib/sidebar-role-profiles.ts:60-112 -> S092 (WAREHOUSE_USER profile + merge)

protected_surfaces:
  - hrms/utils/scm_roles.py -> NOT MODIFIED (DO NOT touch)
  - hrms/api/store.py -> NOT IN SCOPE
  - hrms/api/ordering.py -> NOT IN SCOPE
  - ../bei-tasks/lib/constants.ts -> NOT IN SCOPE

freshness_gate: rebase before PR creation
```

---

## Status Reconciliation Contract

Update on every status change:
1. This plan (phase status)
2. `tmp/erp_chat_bugs_and_recommendations.md` (fix status per bug)
3. `docs/plans/SPRINT_REGISTRY.md` (S092 status when sprint closes)

---

## Signoff Model

```yaml
mode: single-owner
approver: Sam Karazi
artifact: tmp/erp_chat_bugs_and_recommendations.md
```

---

## Autonomous Execution Contract

```yaml
completion_condition:
  - all Phase 0 gates passed
  - all Phase 1-3 fixes implemented and locally tested
  - all new tests passing locally
  - backend PR created, governor-merged, and deployed to production
  - frontend PR created, merged, and deployed to my.bebang.ph (AFTER backend)
  - ALL L1 API smoke tests passing on production
  - ALL L2 page render checks passing on production (browser)
  - ALL L3 workflow scenarios passing on production (browser)
  - ALL L4 negative/regression probes passing on production
  - bug-fix loop completed with zero remaining failures
  - bug tracker updated, team notified

stop_only_for:
  - Phase 0 GATE 1 fails (Commissary Supervisor role missing — create it, then continue)
  - Phase 0 GATE 2 reveals unexpected MR status (present options)
  - governor poll timeout >20 min AND governor is confirmed down
  - business-policy decision needed (e.g., should Warehouse User manage schedules?)

do_NOT_stop_for:
  - PR creation (continue to poll governor)
  - governor merge (continue to L2-L4 testing)
  - L2-L4 test failure (fix, push, governor re-deploys, retest)
  - governor rejects PR (read review, fix, push to same branch, governor re-reviews)
  - single test regression (fix and continue)

continue_without_pause_through:
  - code
  - local_test
  - pr_creation
  - governor_poll (60s intervals, 20 min timeout)
  - post_deploy_L1_smoke
  - post_deploy_L2_page_check (browser)
  - post_deploy_L3_workflow_test (browser)
  - post_deploy_L4_negative_probes
  - bug_fix_loop (fix → push → governor re-deploy → retest)
  - closeout

bug_fix_loop:
  trigger: any L2-L4 test failure after deploy
  action: diagnose → fix locally → pytest green → push to same branch → governor re-reviews → poll → retest
  exit: zero L2-L4 failures on production
  max_iterations: 5 (after 5 fix cycles with same failure, pause and present options)

blocker_policy:
  programmatic: fix and continue
  gate_failure: resolve gate, then continue
  governor_rejection: read review comments, fix, push to same branch, continue
  L2_L4_failure: enter bug-fix loop, continue
  repeated_failure_x3_same_issue: grounded research, then continue
  repeated_failure_x5_same_issue: pause and present options
  business_policy: pause and present options

signoff_authority: single-owner (Sam Karazi)

closeout_artifacts:
  - docs/plans/2026-03-22-sprint-92-erp-testing-bug-remediation.md (status: Completed)
  - docs/plans/SPRINT_REGISTRY.md (S092 row updated)
  - tmp/erp_chat_bugs_and_recommendations.md (all bugs marked FIXED)
```

---

## Execution Workflow

- Test Python locally: `/local-frappe`
- Create PRs: `gh pr create` (governor merges + deploys)
- Poll governor: `gh pr view <N> --json state -q '.state'` in 60s loop
- Post-deploy L1: `/l1-api-check`
- Post-deploy L2: `/l2-page-check` (browser — renders pages as real user)
- Post-deploy L3: `/l3-v2` (browser — executes workflow scenarios as real user)
- Bug-fix loop: fix → push → governor re-deploys → retest
- Full orchestration: `/execute-plan-bei-erp` (handles the entire chain automatically)

> **Note:** Deployment is governor-mediated. The agent creates PRs, polls until merged, then tests like a real user on production. If tests fail, the agent fixes and pushes — governor re-deploys — agent retests. This loop continues until zero failures.

## Execution Authority

This sprint is intended for **fully autonomous end-to-end execution including post-deploy verification.**
- Do NOT stop after PR creation — poll governor until merged.
- Do NOT stop after governor merge — run L2-L4 on production like a real user.
- Do NOT stop after finding L2-L4 failures — fix, push, governor re-deploys, retest.
- Do NOT declare success until ALL L1-L4 pass on production with zero failures.
- Only pause for items in `stop_only_for`.

## Agent Boot Sequence

1. Read this plan fully (v3 hardened).
2. Read `tmp/s092_hardened_fix_matrix.md` for exact line numbers and code.
3. Read `docs/plans/SPRINT_REGISTRY.md` for cross-sprint context.
4. Run `pytest hrms/tests/ -x -q` for green baseline.
5. Execute Phase 0 gates before any code changes.
6. After Phase 3: do NOT stop. Continue through Phase 4 (PR → poll → L2-L4 → fix loop → closeout).
7. Use `/execute-plan-bei-erp` for the full autonomous chain if available.

---

## Cold-Start Reference (for agents with zero context)

### Repository Locations
- **Backend (hrms):** `F:\Dropbox\Projects\BEI-ERP` — branch `production`, remote `Bebang-Enterprise-Inc/hrms`
- **Frontend (bei-tasks):** `F:\Dropbox\Projects\bei-tasks` — branch `main`, remote `Bebang-Enterprise-Inc/bei-tasks`
- All `../bei-tasks/` paths in this plan resolve to `F:\Dropbox\Projects\bei-tasks`

### Test Accounts (for L2-L4 browser testing)
- **URL:** https://my.bebang.ph/login
- **All passwords:** `BeiTest2026!`
- `commissary.team@bebang.ph` — Commissary Supervisor role (BUG-010, BUG-011, ACCESS-001)
- `warehouse.user@bebang.ph` — Warehouse User role (BUG-006, BUG-012, BUG-013)
- Full list: `memory/testing-accounts.md`

### How to Run Phase 0 Gates
**GATE 1** — Run via bench console on production Docker container:
```bash
# Via SSM into the EC2 instance, then:
docker exec -it frappe_docker-backend-1 bench --site hq.bebang.ph console
# Then in Python:
frappe.db.exists("Role", "Commissary Supervisor")
```
Or via local Frappe if available: `cd F:\Dropbox\Projects\BEI-ERP && bench --site test_site console`

**GATE 2** — Read the function locally:
```bash
# Read lines 787-930 of warehouse.py and search for where MR status is set
grep -n "status" hrms/api/warehouse.py | grep -i "ordered\|transferred\|approved"
```
The answer determines whether FIX-3B is needed. If `approve_material_request` sets status to one of `"Ordered"`, `"Partially Ordered"`, `"Transferred"`, no Fix B is needed.

### Slash Commands Used in Phase 4
These are Claude Code skill invocations (not shell commands):
- `/l1-api-check` — automated API smoke test against production endpoints
- `/l2-page-check` — Playwright browser test that renders pages and checks for errors
- `/l3-v2` — Playwright browser test that executes workflow scenarios from pre-written catalog
- `/chat` — Google Chat API skill. ERP space ID: `spaces/AAQA3NVVR6c`

### GitHub CLI Context
- **Backend PRs:** `gh pr create --repo Bebang-Enterprise-Inc/hrms --base production`
- **Frontend PRs:** `gh pr create --repo Bebang-Enterprise-Inc/bei-tasks --base main`
- **Poll backend:** `gh pr view <N> --repo Bebang-Enterprise-Inc/hrms --json state -q '.state'`
- **Poll frontend:** `gh pr view <N> --repo Bebang-Enterprise-Inc/bei-tasks --json state -q '.state'`

### Key File Paths (exact, not approximate)
| File | What to change |
|------|---------------|
| `hrms/api/dispatch.py:697` | SCM_ADMIN_ROLES → SCM_DISPATCH_ROLES |
| `hrms/api/warehouse.py:607-608` | Add full-rejection branch before throw |
| `hrms/api/warehouse.py:647-649` | Remove `_run_as_system_user()` |
| `hrms/api/warehouse.py:997-998` | MR status check (may need alignment) |
| `hrms/api/warehouse.py:1100-1105` | Remove `_run_as_system_user()` |
| `hrms/api/procurement.py:867` | Move po_value computation after line 899 |
| `hrms/api/commissary_quality.py:426-427` | Wrap in try/except |
| `hrms/api/supervisor.py:284` | Add "Commissary Supervisor" to role set |
| `../bei-tasks/app/dashboard/procurement/purchase-orders/new/page.tsx:290` | VAT-inclusive grandTotal |
| `../bei-tasks/lib/roles.ts:716` | Add COMMISSARY_SUPERVISOR, remove WAREHOUSE_USER |
| `../bei-tasks/lib/navigation-personas.ts:506` | Add roleToPersona entry |
| `../bei-tasks/lib/sidebar-role-profiles.ts:60-83` | Add secondaryGroups + commissary allowList |
| `../bei-tasks/lib/sidebar-role-profiles.ts:108-112` | Merge logic for multi-role users |
