# Sprint 93 — ERP Team Recommendations Lane A: Store & Warehouse Operations

```yaml
canonical_sprint_id: S093
status: GO (code-verified, 6 blockers patched, audit-hardened 2026-03-23: DR DocType resolved, is_emergency guard added, route ref corrected)
date: 2026-03-23
lanes: A (of A/B split — regrouped by file ownership)
depends_on: S092 (bug fixes must be deployed first)
total_work_units: 42
```

## Purpose

Implement 5 team recommendations touching store operations and warehouse workflows. Grouped by shared file ownership to eliminate cross-sprint conflicts.

**This sprint owns:** `store.py`, `ordering.py`, `warehouse.py` (dispatch/picking/handoff sections), `picking.py`
**S094 owns:** `procurement.py`, `commissary_dashboard.py`, `commissary.py`, `commissary_quality.py`

| ID | Recommendation | Classification | Source |
|----|---------------|----------------|--------|
| UX-001 | Store ordering policy: any-time orders, date selector, 12 NN next-day cutoff, dual approval after cutoff | [EXTEND] | Sam's policy decision |
| UX-014 | DR visibility before truck arrival: item-level manifest for stores | [BUILD] | Avis Principe |
| UX-011 | Commissary handoff initiation button + warehouse notification | [EXTEND] | Ian Dionisio |
| UX-012 | Open orders view in picking (trip-independent) | [EXTEND] | Ian Dionisio |
| UX-013 | Billing credit display on returns (backend exists, frontend missing) | [EXTEND] | Ian Dionisio |

**Source evidence:**
- `tmp/erp_chat_issues_extracted.md` — original recommendations
- `tmp/s093_file_ownership_map.md` — file-level dependency mapping

---

## Design Rationale (For Cold-Start Agents)

### Why this exists
During ERP testing on March 19-20, the team reported 15 UX issues. 4 were fixed live. The remaining 11 are split across S093 (this) and S094, regrouped by shared file ownership after dependency audit revealed the original split had cross-sprint file conflicts.

### Key decisions (locked)

**UX-001 — Ordering policy (Sam Karazi, locked 2026-03-23):**
- Stores can order **any time** — no emergency order concept needed
- For **next-day delivery**: cutoff is **12:00 NN the day before**
  - BEFORE cutoff: unlimited orders + edits, no approval needed
  - AFTER cutoff: edits allowed but require approval from BOTH Area Supervisor AND Ian (Warehouse Manager)
- For **day-after-tomorrow+**: no cutoff, order any time
- A **date selector** must be added to the ordering form
- Multiple orders per store per day per cargo category allowed before cutoff
- Do NOT remove `is_emergency` field from historical orders — just stop creating new ones

**UX-013 — Billing returns (duplication audit finding):**
Backend already implements billing credits: `_create_store_issue_credit_note()` (store.py:3105), `_calculate_delivery_return_credit()` (store.py:3047), `_find_original_billing()` (store.py:3633). The API response already returns `credit_note` and `credit_note_status` fields (bei-tasks route.ts:308-318). **Only the frontend display is missing** — the returns success page doesn't render the credit note reference.

### Duplication audit highlights
- UX-001: Cutoff logic exists (`_get_order_cutoff`, `_validate_order_cutoff`). Emergency bypass exists. Missing: date selector, multi-order, dual approval, remove emergency concept.
- UX-011: Backend handoff queue fully built (`create_warehouse_receiving`, `get_pending_warehouse_receivings`, `complete_warehouse_receiving`). Missing: commissary-side initiation button + notification.
- UX-012: Picking UI fully built but trip-centric. Missing: pre-trip open orders panel.
- UX-013: **Backend DONE.** Frontend display missing.
- UX-014: Trip status endpoint exists. Missing: DR as structured record + item manifest endpoint.

---

## Requirements Regression Checklist

- [ ] Ordering allows any-time orders (no emergency flow for same-day)
- [ ] Date selector on ordering form with delivery date picker
- [ ] Next-day orders: 12 NN cutoff enforced — after cutoff, dual approval required
- [ ] Dual approval = Area Supervisor first, then Warehouse Manager (Ian)
- [ ] Multiple orders per store per day per category allowed before cutoff
- [ ] `is_emergency` field preserved on historical orders (not removed)
- [ ] DR stored as structured link (BEI Store Order → BEI Trip Stop), not just comment
- [ ] Store receiving page shows DR number + item manifest before truck arrives
- [ ] Commissary transfer page has "Send to Warehouse" button
- [ ] Warehouse notified (in-app + Chat) on handoff initiation
- [ ] Picking page has "Open Orders" tab showing approved MRs not yet on trips
- [ ] Returns success page shows credit note reference (already in API response)
- [ ] All changes preserve existing test suite green
- [ ] store.py, ordering.py, warehouse.py not touched by S094 (except UX-010 narrow exception)

---

## Phase 0 — Pre-Flight + DocType Migration (4 units)

### Task 0.1: Verify S092 deployed + baseline
- Confirm S092 bug fixes are live
- Pull latest `production` + `main`, record SHAs
- `pytest hrms/tests/ -x -q` green

### Task 0.2: Add 6 missing fields to BEI Store Order DocType [BUILD]
**HARD BLOCKER (code verifier):** All 6 fields are ABSENT from `bei_store_order.json`. Tasks 1.2, 2.1, 2.2 will fail without them.
Add to `hrms/hr/doctype/bei_store_order/bei_store_order.json`:
1. `requires_dual_approval` (Check, default 0)
2. `approval_stage` (Select: `Single Approval|Pending Area Supervisor|Pending Warehouse Manager|Fully Approved`)
3. `second_approver` (Link → User)
4. `second_approval_date` (Datetime)
5. `dr_number` (Data, read_only 1)
6. `trip_stop` (Link → BEI Trip Stop)
Run `bench migrate` after adding fields.

### Task 0.3: ~~Verify BEI Delivery Receipt DocType exists~~ RESOLVED
**AUDIT RESOLVED (2026-03-23):** `BEI Delivery Receipt` DocType confirmed MISSING on production via Frappe API (`DoesNotExistError`). No DocType directory exists in codebase either. Resolution: Option A adopted — DR counter in Task 2.1 now queries `tabBEI Store Order.dr_number` instead. **No blocker remains.** Skip this task.

### Task 0.4: Verify UX-013 backend status
Run locally to confirm billing credit works:
```python
frappe.call("hrms.api.store.process_store_return", store_issue="<test_issue>")
```
If credit note is created: UX-013 is frontend-only. If broken: add backend fix tasks.

---

## Phase 1 — Store Ordering Policy Overhaul (12 units)

### Task 1.1: Redesign ordering cutoff + multi-order logic [EXTEND]
**File:** `hrms/api/store.py`
**Functions:** `_get_order_cutoff()` (~line 1899), `_validate_order_cutoff()` (~line 1924), `validate_order_schedule()` (~line 1949), `submit_order()` (~line 1979, duplicate guard at lines 2031-2046)

**Fix:**
1. **New `_validate_order_window(delivery_date)`** replaces `_validate_order_cutoff()`:
```python
def _validate_order_window(delivery_date, store):
    today = frappe.utils.today()
    tomorrow = frappe.utils.add_days(today, 1)
    now_hour = frappe.utils.now_datetime().hour

    if str(delivery_date) == str(tomorrow) and now_hour >= 12:
        return {"allowed": True, "requires_dual_approval": True,
                "message": "Next-day order after 12 NN cutoff — requires Area Supervisor + Warehouse Manager approval"}
    return {"allowed": True, "requires_dual_approval": False}
```
2. **Remove duplicate guard** at lines 2031-2046 entirely — the guard checks `order_date` (today), not `delivery_date`. Removing it allows multiple orders per day. No replacement guard needed — orders are scoped by `delivery_date` + `cargo_category` naturally.
3. **Add `delivery_date` validation**: date must be >= tomorrow (no same-day orders to warehouse)
4. **Remove emergency order creation** from new orders — but preserve `is_emergency` field reads for historical data. **Hide the emergency dialog** in the frontend ordering page (state variables `emergencyOpen`, `emergencyReason`, `emergencyNotes` at lines 279-283) — do NOT delete the code, just conditionally hide the UI for new orders.
5. **AUDIT FIX (2026-03-23): Add explicit `is_emergency` rejection guard.** `is_emergency` is wired into 13 locations (cutoff bypass at lines 1934/2010, duplicate guard bypass at 2031, urgent approval routing at 2114/2121/2141, critical alerts at 2195/2206/2212). In `submit_order()`, after the new `_validate_order_window()` call, add an explicit guard:
```python
if cint(is_emergency):
    frappe.throw(_("Emergency orders are no longer accepted. Use the date selector to place next-day orders."))
```
This prevents legacy clients or API callers from bypassing the new ordering policy by passing `is_emergency=True`.

**HARD BLOCKER:** Do NOT delete the `is_emergency` column or any code that READS it. Only stop WRITING it on new orders.

### Task 1.2: Implement dual-approval workflow [EXTEND]
**File:** `hrms/api/store.py` — `_resolve_order_approval_routing()` (~line 991), `approve_order()` (~line 2257)
**DocType:** `hrms/hr/doctype/bei_store_order/bei_store_order.json`

**Fix:**
1. Add fields to BEI Store Order DocType: `requires_dual_approval` (Check), `second_approver` (Link to User), `second_approval_date` (Datetime), `approval_stage` (Select: Pending AS / Pending WM / Fully Approved)
2. In `_resolve_order_approval_routing()`: when `requires_dual_approval`, route first to Area Supervisor
3. In `approve_order()`: if `approval_stage == "Pending AS"` and approver is Area Supervisor, set stage to `"Pending WM"` (don't mark fully approved yet). When Warehouse Manager approves, set `"Fully Approved"`.
4. Order enters fulfillment queue only when `approval_stage == "Fully Approved"` or `requires_dual_approval == False`

### Task 1.3: Add delivery date selector to frontend [EXTEND]
**File:** `../bei-tasks/app/dashboard/store-ops/ordering/page.tsx`
**Hooks:** `../bei-tasks/hooks/use-ordering.ts`

**Fix:**
1. Add Shadcn `DatePicker` component defaulting to next scheduled delivery date
2. `useOrderSchedule` returns available dates — wire picker to this
3. When delivery_date == tomorrow and time > 12 NN: show amber banner "This order requires dual approval"
4. Wire selected `delivery_date` to `useSubmitOrder` call
5. Update `order-approvals/page.tsx` to show approval stage badge (Pending AS / Pending WM / Approved)

### Task 1.4: Write ordering tests [BUILD]
**File:** `hrms/tests/test_s093_ordering_policy.py` (new)
- Order for tomorrow at 11:59 AM → no dual approval
- Order for tomorrow at 12:01 PM → requires dual approval
- Order for day-after-tomorrow at any time → no dual approval
- Multiple orders same store/day/category → all succeed
- Dual approval: AS approves → stage moves to Pending WM → WM approves → Fully Approved
- Dual approval: AS rejects → order rejected (doesn't reach WM)
- Historical emergency orders: `is_emergency` field readable, not written on new orders
- New order with `is_emergency=True` → rejected with explicit error message (guard test)

---

## Phase 2 — DR Visibility + Warehouse Workflows (12 units)

### Task 2.1: Structure DR as linked record [EXTEND]
**File:** `hrms/api/ordering.py` — `_generate_dr_internal()` (~line 137), `generate_dr()` (~line 185)
**DocType:** `hrms/hr/doctype/bei_store_order/bei_store_order.json`

**AUDIT FIX (2026-03-23):** `BEI Delivery Receipt` DocType does NOT exist on production (confirmed via API). The current `_generate_dr_internal()` catches the missing-table error silently (lines 146-152) and defaults `last_num=0`. DRs are stored only as Comment strings, never as DocType records. **Resolution: Option A (minimal).** Do NOT create the DocType. Fix the counter query to read from `BEI Store Order.dr_number` instead.

**Fix:**
1. Add `dr_number` (Data) and `trip_stop` (Link) fields to BEI Store Order if not present (Task 0.2 handles this)
2. In `_generate_dr_internal()`, **replace the counter query** (lines 146-152):
```python
# OLD (queries nonexistent DocType):
# result = frappe.db.sql("SELECT MAX(...) FROM `tabBEI Delivery Receipt`")
# NEW (queries BEI Store Order where dr_number is already stored):
try:
    result = frappe.db.sql(
        "SELECT MAX(CAST(SUBSTRING(dr_number, 3) AS UNSIGNED)) FROM `tabBEI Store Order` WHERE dr_number IS NOT NULL AND dr_number != ''"
    )
    last_num = result[0][0] if result and result[0][0] else 0
except Exception:
    last_num = 0
```
3. After generating DR number, store linkage on the order:
```python
frappe.db.set_value("BEI Store Order", order_name, {
    "dr_number": dr_number,
    "trip_stop": trip_stop_name
})
```

### Task 2.2: Add pre-arrival manifest endpoint [BUILD]
**File:** `hrms/api/store.py` — extend or complement `get_expected_deliveries()` (~line 2496)

**Fix:** New endpoint `get_pending_deliveries_with_manifest(store)`:
```python
@frappe.whitelist()
def get_pending_deliveries_with_manifest(store=None):
    if not store:
        store = _resolve_user_store()
    trips = get_expected_deliveries(store)
    for trip in trips:
        orders = frappe.db.get_all("BEI Store Order",
            filters={"trip_stop": trip["stop_name"], "store": store, "dr_number": ["is", "set"]},
            fields=["name", "dr_number", "status"])
        for order in orders:
            order["items"] = frappe.db.get_all("BEI Store Order Item",
                filters={"parent": order["name"]},
                fields=["item_code", "item_name", "qty", "uom"])
        trip["orders"] = orders
    return trips
```

### Task 2.3: Add manifest to store receiving page [EXTEND]
**File:** `../bei-tasks/app/dashboard/receiving/page.tsx`
**Hook:** `../bei-tasks/hooks/use-receiving.ts`

**Fix:** Replace `useExpectedDeliveries` with `usePendingDeliveriesWithManifest`. Show DR number + expandable item list per trip card.

### Task 2.4: Add handoff notification to existing commissary transfer [EXTEND]
**File:** `hrms/api/warehouse.py` — after `create_warehouse_receiving()` (~line 441)
**Frontend:** `../bei-tasks/app/dashboard/commissary/transfer/page.tsx` (line 425)

**Code verifier finding:** "Send to Warehouse" button ALREADY EXISTS at line 425 and calls `create_warehouse_receiving` via `createWarehouseHandoff` → commissary/route.ts:826. Do NOT add a second button.

**Fix (backend only):** Add notification at the end of `create_warehouse_receiving()`:
```python
# At end of create_warehouse_receiving, after line 511:
_notify_warehouse_handoff(receiving_doc.name)

def _notify_warehouse_handoff(receiving_name):
    """Notify warehouse team of incoming handoff via GChat + in-app."""
    # GChat notification
    from hrms.api.google_chat import send_bot_message
    send_bot_message(
        space_id="spaces/AAQA3NVVR6c",
        text=f"📦 New commissary handoff: {receiving_name}. Check warehouse receiving queue."
    )
```
**Fix (frontend):** Wire notification response display in the success state after "Send to Warehouse" (show receiving_name to the user). Do NOT add a new button.

**HARD BLOCKER:** Call existing `create_warehouse_receiving()` — do NOT duplicate its logic.

### Task 2.5: Add open orders view to picking [EXTEND]
**File:** `hrms/api/picking.py` or `hrms/api/warehouse.py` — new endpoint
**Frontend:** `../bei-tasks/app/dashboard/warehouse/picking/page.tsx`

**Fix (backend):**
```python
@frappe.whitelist()
def get_open_orders_for_picking(warehouse=None):
    _check_scm_permission(SCM_DISPATCH_ROLES, "view open orders")
    if not warehouse:
        warehouse = _resolve_user_warehouse()
    return frappe.db.get_all("Material Request",
        filters={"status": ["in", ["Ordered", "Partially Ordered"]], "set_warehouse": warehouse},
        fields=["name", "transaction_date", "status", "set_warehouse", "total_qty"],
        order_by="transaction_date asc")
```
**Fix (frontend):** Add "Open Orders" tab to picking page.

### Task 2.6: Surface billing credit on returns page [EXTEND]
**File:** `../bei-tasks/app/dashboard/inventory/returns/page.tsx`
**Current:** API already returns `credit_note` and `credit_note_status` (route.ts:308-318). Frontend success screen (lines 265-295) only shows generic `submitMessage`.

**Code verifier finding:** Credit note data is in `data.data.finance_results[]` array, NOT in `data.message`. The frontend must extract from `finance_results`, not the generic message string.
**AUDIT FIX (2026-03-23):** The `credit_note` and `credit_note_status` fields are in `app/api/inventory/returns/route.ts:308-318` (NOT the procurement route). The response shape is `{ data: { finance_results: [{ credit_note, credit_note_status, ... }] } }`.

**Fix:** After successful return submission, extract and render:
```tsx
{data?.data?.finance_results?.map((fr: any) => (
  fr.credit_note && (
    <div key={fr.credit_note} className="mt-2 text-sm text-green-600">
      Credit Note: {fr.credit_note} ({fr.credit_note_status})
    </div>
  )
))}
```
**This is frontend-only — no backend change needed.**

### Task 2.7: Write tests for Phase 2 [BUILD]
**File:** `hrms/tests/test_s093_warehouse_dr.py` (new)
- DR stored as structured link on Store Order
- Manifest endpoint returns items per trip per store
- Handoff initiation creates warehouse receiving record
- Open orders returns only approved MRs not on trips
- Credit note reference in API response (verify existing)

---

## Phase 3 — Testing, PR, Governor, L2-L4 & Bug-Fix Loop (14 units)

> **The agent does NOT stop after PR creation.** Full chain: local test → PR → poll governor → L2-L4 like real user → fix loop → closeout.

### Task 3.1: Run full test suite
`pytest hrms/tests/ -x -q` — all existing + new tests green.

### Task 3.2: Create backend PR (hrms)
- Branch: `feat/s093-store-warehouse-ops`
- PR against `production`, full Docker build
- Poll governor every 60s, 20-min timeout
- If rejected: fix, push same branch, governor re-reviews

### Task 3.3: Create frontend PR (bei-tasks) — AFTER backend deployed
- Branch in bei-tasks, PR against `main`
- Poll until merged

### Task 3.4: Live L2-L4 verification — test LIKE A REAL USER

**L1 — API smoke:**
- `submit_order` with delivery_date = tomorrow at 11 AM → 200, no dual approval
- `submit_order` with delivery_date = tomorrow at 1 PM → 200, requires_dual_approval = true
- `get_pending_deliveries_with_manifest` → returns DR + items
- `create_warehouse_receiving` (commissary handoff) → 200 + GChat notification sent
- `get_open_orders_for_picking` → returns approved MRs

**L2 — Page renders (browser):**
- Store ordering page → date picker visible
- Store receiving page → DR number + items shown for scheduled trips
- Commissary transfer → "Send to Warehouse" button visible
- Warehouse picking → "Open Orders" tab visible
- Returns success → credit note reference displayed

**L3 — Workflow scenarios (browser):**
- Place order for tomorrow before noon → submit succeeds, single approval
- Place order for tomorrow after noon → submit succeeds, dual approval banner, AS approves → WM approves → fully approved
- Place 3 orders for same day → all succeed
- Commissary sends handoff → warehouse sees in pending queue
- Store receiving shows incoming items before truck arrives

**L4 — Negative/regression:**
- Order for yesterday → rejected
- Dual approval: AS rejects → WM never sees it
- Empty open orders → shows "No pending orders" message
- Store with no scheduled deliveries → empty manifest

### Task 3.5: Bug-fix loop
Fix → push → governor re-deploys → retest. Loop until zero failures. Max 5 iterations per issue.

### Task 3.6: Closeout
Update `tmp/erp_chat_bugs_and_recommendations.md`, sprint registry, `/chat` notification.

---

## Shell Prevention (S026)

| Failure Pattern | Gate | Task |
|----------------|------|------|
| Date picker renders but doesn't wire to API | gate_action_wiring_complete | 1.3 |
| Dual approval banner shows but second approver can't act | gate_mutation_outcomes_defined | 1.2 |
| DR manifest shows but items list is empty | gate_dependency_map_complete | 2.1/2.2 |
| "Send to Warehouse" button visible but API 403 | gate_action_wiring_complete | 2.4 |
| Open Orders tab shows but always empty | gate_dependency_map_complete | 2.5 |
| Credit note in API but not rendered | gate_action_wiring_complete | 2.6 |

---

## Phase Budget Contract (S029)

```yaml
phase_unit_budget:
  Phase 0: 4 (includes DocType migration + DR DocType verification)
  Phase 1: 12
  Phase 2: 12
  Phase 3: 14 (governor + L2-L4 + fix loop)
total: 42
hard_limit: 15
note: Phase 3 at 14 (below 15 ceiling). Includes 7 Task 3.4 sub-tests + fix loop.
```

---

## Anti-Rewind Protection (S087)

```yaml
remote_truth_baseline:
  hrms: {branch: production, head_sha: "[set at Phase 0]"}
  bei-tasks: {branch: main, head_sha: "[set at Phase 0]"}

surface_ownership:
  - hrms/api/store.py -> S093 (ordering + manifest + returns credit display)
  - hrms/api/ordering.py -> S093 (DR linkage)
  - hrms/api/warehouse.py (handoff/picking sections) -> S093
  - hrms/api/picking.py -> S093 (open orders endpoint)
  - hrms/hr/doctype/bei_store_order/ -> S093 (new fields)
  - ../bei-tasks/app/dashboard/store-ops/ordering/page.tsx -> S093
  - ../bei-tasks/app/dashboard/store-ops/order-approvals/page.tsx -> S093
  - ../bei-tasks/app/dashboard/receiving/page.tsx -> S093
  - ../bei-tasks/app/dashboard/commissary/transfer/page.tsx -> S093
  - ../bei-tasks/app/dashboard/warehouse/picking/page.tsx -> S093
  - ../bei-tasks/app/dashboard/inventory/returns/page.tsx -> S093

protected_surfaces:
  - hrms/api/procurement.py -> S094 OWNS
  - hrms/api/commissary_dashboard.py -> S094 OWNS
  - hrms/api/commissary.py -> S094 OWNS
  - hrms/utils/scm_roles.py -> NOT MODIFIED

s094_narrow_exception:
  - S094 may touch warehouse.py:476-495 (receiving item loop) and store.py:2558-2574 (receiving expiry check) for UX-010 shelf life gate ONLY
  - These are isolated functions that S093 does not modify
```

---

## Autonomous Execution Contract

```yaml
completion_condition:
  - all phases complete, all tests passing
  - backend + frontend PRs merged by governor
  - ALL L1-L4 pass on production with zero failures
  - bug-fix loop completed

stop_only_for:
  - BEI Store Order DocType missing new fields (add them first)
  - S094 has merge conflict on shared files (coordinate)
  - business-policy clarification (dual approval details)

do_NOT_stop_for:
  - PR creation, governor merge, L2-L4 failure (fix loop)

continue_without_pause_through:
  - code → local_test → pr_creation → governor_poll → L2-L4 → bug_fix_loop → closeout

bug_fix_loop:
  trigger: any L2-L4 failure
  action: diagnose → fix → pytest → push same branch → governor re-reviews → poll → retest
  exit: zero failures
  max_iterations: 5 per issue

signoff_authority: single-owner (Sam Karazi)
closeout_artifacts:
  - docs/plans/2026-03-23-sprint-93-erp-team-recommendations-lane-a.md
  - docs/plans/SPRINT_REGISTRY.md
  - tmp/erp_chat_bugs_and_recommendations.md
```

---

## Execution Workflow

- Test: `/local-frappe`
- PRs: `gh pr create` (governor merges + deploys)
- Poll: `gh pr view <N> --json state -q '.state'`
- L2-L4: `/l1-api-check`, `/l2-page-check`, `/l3-v2`
- Full chain: `/execute-plan-bei-erp`

## Execution Authority

Fully autonomous end-to-end execution. Do NOT stop after PR creation. Poll governor, run L2-L4, fix loop until zero failures.

## Agent Boot Sequence

1. Read this plan fully.
2. Read `tmp/erp_chat_issues_extracted.md` for original team recommendations.
3. Read `docs/plans/SPRINT_REGISTRY.md` for cross-sprint context.
4. Verify S092 is deployed.
5. `pytest hrms/tests/ -x -q` for green baseline.
6. Execute phases sequentially. Do NOT stop after Phase 2.

## Cold-Start Reference

- **Backend:** `F:\Dropbox\Projects\BEI-ERP`, branch `production`, remote `Bebang-Enterprise-Inc/hrms`
- **Frontend:** `F:\Dropbox\Projects\bei-tasks`, branch `main`, remote `Bebang-Enterprise-Inc/bei-tasks`
- **Test accounts:** All passwords `BeiTest2026!`. URL: https://my.bebang.ph/login
- **Slash commands:** `/l1-api-check`, `/l2-page-check`, `/l3-v2`, `/chat` (space `spaces/AAQA3NVVR6c`)
- **Merge order:** S092 → S093 (this) → S094
