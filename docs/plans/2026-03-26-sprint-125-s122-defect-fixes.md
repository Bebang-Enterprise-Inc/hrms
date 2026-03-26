---
canonical_sprint_id: S125
display: Sprint 125
status: PR_CREATED
branch: s125-s122-defect-fixes
lane: single
created_date: 2026-03-26
completed_date:
deployed_at:
backend_pr: n/a (F5 cleanup via API, no code change)
frontend_pr: "#254"
l3_result: pending (run in fresh session after deploy)
execution_summary: "F1 critical status fix + F2 banner expiry fix in PR #254. F5 test account revert done via API."
depends_on: S122
---

# S125 — S122 Store Inventory Dashboard Defect Fixes

**Goal:** Fix 3 in-scope defects and 1 collateral defect discovered during S122 L3 testing. All issues are UX/data quality — no architecture changes needed.

**Origin:** S122 L3 testing (2026-03-26) revealed defects in the store inventory dashboard. Evidence: `output/l3/S122/defects.json`, screenshots in `output/l3/S122/artifacts/`.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

S122 shipped the store inventory dashboard. L3 testing with real data from Araneta Gateway (164 SKUs) revealed:
1. **49% of items shown as "Critical"** because `is_oos` comes from the orderable catalog (commissary ATP), not from store stock levels. A store can have stock on hand but the item is "OOS" at the commissary — misleading on a store inventory dashboard.
2. **Order window banner shows "0:00 left"** with an active "Place Order" link when the countdown reaches zero, instead of switching to the closed/grey state.
3. **All orders in history show "Pending Approval"** — this is stale BEI Store Order data in Frappe, not a frontend bug. Noted as collateral but tracked here for visibility.

### Key decisions
- **D1 fix:** Change `getStockStatus()` to derive "critical" from `actual_qty <= 0` only (store's own stock), not from `is_oos` (commissary OOS). The `is_oos` flag is still shown as a secondary indicator but does not drive the Critical badge.
- **D2 fix:** When countdown reaches 0 or negative, switch banner to the grey "closed" variant. Clear the interval.
- **D3 (collateral):** No code fix — document for operations team to review stale order statuses.

---

## Scope (8 units)

| Task | Type | Repo | File | Description | Units |
|------|------|------|------|-------------|-------|
| F1 | FIX | bei-tasks | `hooks/use-store-inventory.ts` | **[FIX] Critical status based on store stock, not commissary OOS.** Change `getStockStatus()`: remove `item.is_oos` from the critical condition. Critical = `actual_qty <= 0` only. Keep `is_oos` on the `StoreInventoryItem` type for display but do not use it to drive the status badge. **HARD BLOCKER:** Do NOT remove `is_oos` from the data — it's used for "OOS at commissary" indicator. Only remove it from `getStockStatus()`. | 2 |
| F2 | FIX | bei-tasks | `_components/OrderWindowBanner.tsx` | **[FIX] Banner shows "0:00 left" instead of switching to closed state.** In the countdown `useEffect`, when `remaining <= 0`, clear the interval and set a `expired` state flag. When `expired` is true, render the grey "Next delivery" banner even if `schedule?.allowed` was true at page load. This handles the case where the order window closes while the user is on the page. | 2 |
| F3 | FIX | bei-tasks | `_components/MyStockView.tsx` | **[FIX] "Needs Attention" count too high.** After F1, the Needs Attention default view should show far fewer items (only those with `actual_qty <= 0` or `is_low_stock`). Verify the toggle count drops from 86 to a reasonable number (~items with zero store stock). No code change expected — this is a verification task after F1. | 1 |
| F4 | DOC | bei-erp | Plan file | **[DOC] Record collateral: stale BEI Store Order statuses.** All Araneta Gateway orders (Jan-Mar 2026) show "Pending Approval" in the Order History tab. The order approval workflow may not be updating status after approval/delivery. Document in plan for operations team review — NOT a code fix. | 1 |
| F5 | CLEANUP | bei-erp/frappe | Frappe API | **[CLEANUP] Revert test account warehouse assignments.** Restore test.crew1 branch to TEST-STORE-BGC, test.area stores to TEST-STORE-BGC + TEST-STORE-MAKATI. Remove test.area from Araneta Gateway and 3MD Logistics `custom_area_supervisor`. | 1 |
| F6 | BUILD | bei-tasks | PR + deploy | **[BUILD] Create PR, push, Vercel auto-deploys.** Single PR for F1+F2+F3. | 1 |

**Total: 8 units**

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| test.crew1@bebang.ph | Load inventory page at Araneta Gateway | Critical count < 20 (was 81 before fix). Only items with actual_qty=0 are Critical. | F1 getStockStatus fix not working |
| test.crew1@bebang.ph | Check an item with stock > 0 but is_oos=true | Status shows "Healthy" or "Low" — NOT "Critical" | F1 still using is_oos for critical |
| test.crew1@bebang.ph | View "Needs Attention" default | Shows reasonable count (items with 0 qty + low stock), not 86 | F3 needs attention still inflated |
| test.crew1@bebang.ph | Stay on page until order window closes (or load when countdown=0) | Banner switches to grey "Next delivery: {day}" — NOT "0:00 left" with active link | F2 countdown not switching to closed |
| test.crew1@bebang.ph | After F5 cleanup: verify test.crew1 store assignment | useUserStore returns TEST-STORE-BGC (not Araneta Gateway) | F5 revert incomplete |

Evidence files:
```
output/l3/S125/form_submissions.json
output/l3/S125/api_mutations.json
output/l3/S125/state_verification.json
```

---

## Requirements Regression Checklist

- [ ] Does `getStockStatus()` use only `actual_qty <= 0` for critical (NOT `is_oos`)?
- [ ] Is `is_oos` still available on `StoreInventoryItem` for display?
- [ ] Does `OrderWindowBanner` switch to grey/closed when countdown reaches 0?
- [ ] Does `OrderWindowBanner` clear the interval on expiry?
- [ ] Are test accounts reverted to test warehouses after testing?
- [ ] Is the stale order status issue documented (not coded)?

---

## Autonomous Execution Contract

- **completion_condition:**
  - `getStockStatus()` no longer uses `is_oos` for critical
  - Banner switches to closed state on countdown expiry
  - Critical count at Araneta Gateway significantly reduced from 81 (only items with `actual_qty <= 0` should be Critical)
  - L3 scenarios pass
  - Test accounts reverted
  - Test accounts reverted to test warehouses (verified via API)
  - Plan YAML status = COMPLETED
  - SPRINT_REGISTRY.md updated
  - Evidence committed: `git add -f output/l3/S125/ docs/plans/ && git push`

- **stop_only_for:**
  - Business decision: should `is_low_stock` also be excluded from critical? (currently included — seems correct)

- **continue_without_pause_through:**
  - code → PR → deploy → L3 → closeout

- **signoff_authority:** single-owner (Sam Karazi, CEO)

---

## Collateral Defect Log

### COLLATERAL-1: All BEI Store Orders at Araneta show "Pending Approval"
- **Severity:** MAJOR
- **Component:** Frappe `BEI Store Order` DocType workflow
- **Evidence:** Order History tab shows 12+ orders from Jan-Mar 2026, all status "Pending Approval"
- **Impact:** Store managers see misleading historical data — orders that were likely approved/delivered still show Pending
- **Suggested investigation:** Check if the order approval flow (`approve_order` in `hrms/api/store.py`) correctly updates the document status. Check if there's a workflow state transition missing after Material Request creation.
- **Action:** Sam to investigate. Check if `approve_order` in `hrms/api/store.py` updates BEI Store Order status correctly. NOT a code fix in this sprint — requires business process review.

---

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch (bei-tasks, NOT BEI-ERP):** `cd ../bei-tasks && git fetch origin main && git checkout -b s125-s122-defect-fixes origin/main`. bei-tasks main branch is `main`, not `production`.
3. Read `hooks/use-store-inventory.ts` — the `getStockStatus()` function.
4. Read `app/dashboard/store-ops/inventory/_components/OrderWindowBanner.tsx` — the countdown logic.
5. Make changes, test, create PR.
6. **Commit evidence:** `git add -f output/l3/S125/ && git push` (required by release manager gate).

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.
