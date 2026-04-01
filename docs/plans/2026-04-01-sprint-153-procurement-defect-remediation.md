# Sprint S153 — Procurement Defect Remediation (S152 Findings)

```yaml
sprint: S153
branch: s153-procurement-defect-remediation
status: GO
plan_file: docs/plans/2026-04-01-sprint-153-procurement-defect-remediation.md
depends_on: S152
registry_row: "| S153 | Sprint 153 | s153-procurement-defect-remediation | — | GO — Fix 7 open defects from S152 E2E testing |"
completed_date:
execution_summary:
```

---

## Why This Exists

S152 ran a full E2E browser acceptance test of the procurement workflow (PR → PO → GR → Invoice → RFP → 4-Level Approval → OR). Result: **33/40 PASS, 10 defects found, 3 fixed in-sprint**. The remaining 7 open defects block real finance team usage and prevent 2 test scenarios from passing (A13 OR upload, R03 partial GR).

This sprint fixes all 7 open defects. No new features — just make existing features actually work.

---

## Design Rationale (For Cold-Start Agents)

### Why these defects matter
- **DEFECT-4 (GR warehouse):** Every GR from a PR-based PO has an empty warehouse → inventory tracking breaks
- **DEFECT-7 (RFP payment method):** Users can't create RFPs without manually selecting payment method — form silently fails
- **DEFECT-8 (OR upload):** No way to close the payment cycle — finance can't record receipt of official receipts
- **DEFECT-2 (CEO approval):** Sam gets approval fatigue from approving every PO for suppliers flagged as "new"

### Why a separate sprint (not inline fixes)
- S152 was a testing sprint — it found defects but its branch has test artifacts, not production code
- These fixes touch both repos (hrms + bei-tasks) and need clean PRs from a dedicated branch
- Each fix needs its own L3 re-verification against the S152 scenarios

### Source references
- Defect register: `output/l3/S152/DEFECTS.md`
- S152 plan: `docs/plans/2026-03-31-sprint-152-procurement-e2e-acceptance.md`
- S152 test scripts: `scripts/testing/l3_s152_*.mjs`

---

## Defect Inventory (7 open, ordered by severity)

| # | Defect | Severity | Repo | Fix Type |
|---|--------|----------|------|----------|
| D4 | GR warehouse empty when PO has no ship_to | HIGH | hrms + bei-tasks | [EXTEND] Default warehouse in backend + editable field in frontend |
| D8 | OR upload button missing on approved RFP | MEDIUM | bei-tasks | [BUILD] Add OR upload dialog to payment detail page |
| D7 | RFP payment method not auto-selected | MEDIUM | bei-tasks | [EXTEND] Default to "Bank Transfer" on RFP form |
| D2 | CEO approval triggered for all "new vendor" POs | MEDIUM | hrms | [EXTEND] Check new_supplier_window (30 days) in approval logic |
| D10 | PO conversion toast shows "undefined" | INFO | bei-tasks | [FIX] Return PO name in conversion response |
| D1 | PR has no Submit/Approve workflow | LOW | bei-tasks | [SKIP] — Design decision, not a defect. PRs go directly to Convert to PO. |
| D9 | Price variance override not in PO form | LOW | bei-tasks | [SKIP] — Working as designed. Variance guard protects against data entry errors. |

**In scope: 5 fixes (D4, D8, D7, D2, D10). Out of scope: 2 skips (D1, D9).**

---

## Phase Budget

| Phase | Units | Description |
|-------|-------|-------------|
| Phase 1: Backend Fixes (hrms) | 8 | D4 warehouse default, D2 new vendor window |
| Phase 2: Frontend Fixes (bei-tasks) | 10 | D8 OR upload, D7 payment method, D10 toast, D4 editable warehouse |
| Phase 3: L3 Re-Verification + S152 Corner Cuts | 14 | Fix defects + re-test S152 soft passes |
| Phase 4: Closeout | 2 | Plan + registry update, evidence commit |
| **TOTAL** | **34** | |

---

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s153-procurement-defect-remediation origin/production`. NEVER write code on production.
3. Read `output/l3/S152/DEFECTS.md` for full defect descriptions and evidence.
4. Read `docs/plans/SPRINT_REGISTRY.md` for cross-sprint context.
5. Begin Phase 1.

---

## Phase 1: Backend Fixes — hrms (8 units)

### FIX-D4: GR Warehouse Default (3 units) [EXTEND]

**File:** `hrms/api/procurement.py` — `create_goods_receipt()`

**Problem:** When a PO has empty `ship_to` (common for PR-based POs), the GR is created with empty `warehouse`. The frontend field is read-only.

**Fix:**
```python
# In create_goods_receipt(), after line ~2057
if not data.get("warehouse"):
    # Try PO ship_to first
    if po and po.ship_to:
        data["warehouse"] = po.ship_to
    else:
        # Default to company main warehouse
        default_wh = frappe.db.get_single_value("BEI Settings", "default_receiving_warehouse")
        if not default_wh:
            default_wh = frappe.db.sql(
                "SELECT name FROM `tabWarehouse` WHERE name LIKE %s AND is_group = 0 LIMIT 1",
                "%Stores - BEI%", as_list=True
            )
            default_wh = default_wh[0][0] if default_wh else None
        if default_wh:
            data["warehouse"] = default_wh
        else:
            frappe.throw(_("Warehouse is required. Set a default receiving warehouse in BEI Settings."))
```

**Sentry:** `set_backend_observability_context(module="procurement", action="create_goods_receipt", mutation_type="create")`  — already exists, no change needed.

### FIX-D2: New Vendor CEO Approval Window (5 units) [EXTEND]

**File:** `hrms/hr/doctype/bei_purchase_order/bei_purchase_order.py` or `hrms/api/procurement.py`

**Problem:** Every PO for supplier `1T1MI3` (1 To 1 Marketing) triggers CEO approval because `is_new_supplier=1` never clears. The system should check if the supplier has been active for >30 days (configurable window).

**Fix:** In the PO creation/normalization logic where `requires_ceo_approval` is set:
```python
# Check if supplier is genuinely new (within window)
if supplier_doc.is_new_supplier:
    window_days = flt(settings.get("new_vendor_window_days", 30))
    supplier_created = getdate(supplier_doc.creation)
    if date_diff(nowdate(), supplier_created) > window_days:
        # Supplier is no longer "new" — clear the flag
        frappe.db.set_value("BEI Supplier", supplier_doc.name, "is_new_supplier", 0)
        normalized["requires_ceo_approval"] = 0
    else:
        normalized["requires_ceo_approval"] = 1
```

Also add `new_vendor_window_days` to BEI Settings if not already present.

**HARD BLOCKER:** Do NOT remove the CEO approval for genuinely new suppliers. Only clear the flag after the window expires.

---

## Phase 2: Frontend Fixes — bei-tasks (10 units)

### FIX-D8: OR Upload Button on Payment Detail (4 units) [BUILD]

**File:** `bei-tasks/app/dashboard/procurement/payments/[id]/page.tsx`

**Problem:** After RFP is approved, the payment detail page has no OR upload button. Finance cannot record receipt of official receipts.

**Fix:**
1. Add `useUploadOfficialReceipt()` hook in `use-procurement.ts`:
   ```typescript
   export function useUploadOfficialReceipt() {
     const queryClient = useQueryClient();
     return useMutation({
       mutationFn: ({ name, or_number, or_date, or_amount, or_attachment }: {
         name: string; or_number: string; or_date: string; or_amount: number; or_attachment?: string;
       }) => fetchAPI(`/payment-requests/${name}/upload-or`, {
         method: 'POST', body: JSON.stringify({ or_number, or_date, or_amount, or_attachment }),
       }),
       onSuccess: () => {
         queryClient.invalidateQueries({ queryKey: ['payment-requests'] });
         toast.success('Official Receipt uploaded');
       },
     });
   }
   ```

2. Add `POST /payment-requests/:name/upload-or` route in `[...slug]/route.ts` mapping to `hrms.api.procurement.upload_official_receipt`

3. Add OR upload dialog on payment detail page, visible when status is "Approved" or "Paid" or "Paid - Awaiting OR":
   - OR Number (required text input)
   - OR Date (required date input)
   - OR Amount (required number input, default to payment_amount)
   - File attachment (optional)
   - Submit button

### FIX-D7: RFP Payment Method Default (2 units) [EXTEND]

**File:** `bei-tasks/app/dashboard/procurement/payments/new/page.tsx`

**Problem:** Payment Method field is blank and required. Form silently fails without selection.

**Fix:** Default `payment_mode` to "Bank Transfer" in form `defaultValues`:
```typescript
const form = useForm({
  defaultValues: {
    // ...existing defaults
    payment_mode: 'Bank Transfer',  // FIX-D7: default to most common method
  },
});
```

### FIX-D10: PO Conversion Toast (1 unit) [FIX]

**File:** `bei-tasks/app/dashboard/procurement/purchase-requisitions/[id]/page.tsx`

**Problem:** Toast shows "Converted to PO: undefined" — the PO name from the API response isn't captured.

**Fix:** In the convert-to-PO success handler, read the PO name from the mutation response:
```typescript
toast.success(`Converted to PO: ${result.name || result.po_name || 'created'}`);
```

### FIX-D4-frontend: GR Warehouse Editable (3 units) [EXTEND]

**File:** `bei-tasks/app/dashboard/procurement/goods-receipts/new/page.tsx`

**Problem:** Warehouse field is read-only. When PO has no ship_to, user cannot set it.

**Fix:** Make warehouse field editable (not read-only) when the auto-filled value is empty. If PO has ship_to, keep it read-only with the auto-filled value. If empty, show as editable with a dropdown of available warehouses.

---

## Phase 3: L3 Re-Verification + S152 Corner Cut Remediation (14 units)

Two groups: (A) verify the 5 defect fixes, (B) re-test the 7 S152 scenarios that had soft passes or missing assertions.

### Group A: Defect Fix Verification (6 scenarios)

| # | User | Action | Expected Outcome | Failure Means |
|---|------|--------|-------------------|---------------|
| L3-A01 | test.finance | Create GR from PR-based PO → verify warehouse field | Warehouse auto-defaults to "Stores - BEI" | FIX-D4 not working |
| L3-A02 | test.finance | Approve RFP → click "Upload OR" → fill OR number, date, amount → submit | or_status="OR Received", status→"Closed" | FIX-D8 not working |
| L3-A03 | test.finance | Open `/payments/new` → verify payment method field | payment_mode="Bank Transfer" pre-filled | FIX-D7 not working |
| L3-A04 | test.finance | Convert PR to PO → read toast text content | Toast shows actual PO name (e.g., "PO-2026-XXXXX"), NOT "undefined" | FIX-D10 not working |
| L3-A05 | test.finance | Create PO for supplier created >30 days ago | requires_ceo_approval=0, Mae-only approval (no CEO) | FIX-D2 not working |
| L3-A06 | test.warehouse | Create GR where PO has no ship_to → edit warehouse dropdown | Warehouse field is editable, can select from list | FIX-D4-frontend not working |

### Group B: S152 Corner Cut Remediation (8 scenarios)

These re-test S152 scenarios that had soft passes, skipped assertions, or missing coverage.

| # | S152 Gap | User | Action | Expected Outcome | Why This Was Missed |
|---|----------|------|--------|-------------------|---------------------|
| L3-B01 | D02 CSV export | test.finance | AP Invoices tab → click Export CSV → verify downloaded file | CSV file downloaded, row count matches API total (714+) | S152 captured csvRows=0 but still marked PASS |
| L3-B02 | D04 Supplier timeline | test.finance | AP Supplier Ledger → click a supplier → verify timeline panel | Timeline shows PO/GR/Invoice entries with dates, amounts, doc-type badges | S152 found timeline=false but marked PASS on supplier count alone |
| L3-B03 | A08 Invoice verify | test.finance | After invoice creation → navigate to invoice detail → click "Verify" button | Invoice status changes from "Pending 3-Way Match" to "Verified" | S152 left invoice in "Pending 3-Way Match" without clicking Verify |
| L3-B04 | R03 Partial GR | test.warehouse | Create GR → edit qty fields to 50% of ordered → submit | PO status = "Partially Received" (NOT "Fully Received") | S152 couldn't test because GR form had no editable qty (needs FIX-D4-frontend) |
| L3-B05 | RFP rejection L1 | test.finance | Create RFP → submit → L1 Reviewer REJECTS with reason | Status = "Rejected", rejection level = "Review", reason recorded | S152 only tested L2 rejection |
| L3-B06 | RFP rejection L3 | sam@bebang.ph | Create RFP → L1 approve → L2 approve → L3 CFO REJECTS | Status = "Rejected", rejection level = "CFO", reason recorded | S152 only tested L2 rejection |
| L3-B07 | Multi-RFP icons | test.finance | AP Payments tab → find Chain A RFP (3 green + 1 gray) and Chain C RFP (4 green) | Chain A: 3 CheckCircle2 (green) + 1 Circle (gray). Chain C: 4 CheckCircle2 (green). Rejected RFP: XCircle at rejection level. | S152 only had 1 payment row visible, couldn't verify patterns |
| L3-B08 | D03 Aging columns | test.finance | AP Aging tab → verify ALL bucket column headers | Headers include "Current", "1-30", "31-60", "61-90", "90+" as text | S152 found current=false, marked PASS on row count only |

### Execution Notes

- **L3-B04 depends on FIX-D4-frontend** — GR form must have editable qty fields before partial GR can be tested
- **L3-B01 requires file download interception** — use Playwright `page.waitForEvent('download')` and read the file
- **L3-B02 requires clicking into supplier detail** — the timeline panel loads lazily after supplier selection
- **L3-B07 requires multiple RFPs to exist** — use RFPs created during L3-A02 + L3-B05 + L3-B06 runs
- All scenarios use `/l3-v2-bei-erp` with browser-only Playwright. **ZERO API mutations.**

---

## Phase 4: Closeout (2 units)

1. Update this plan: `status: GO` → `status: COMPLETED`, add `completed_date`, `execution_summary`
2. Update `output/l3/S152/DEFECTS.md`: mark D2, D4, D7, D8, D10 as FIXED with PR references
3. Update `docs/plans/SPRINT_REGISTRY.md` row with COMPLETED status + PR numbers
4. Commit evidence: `git add -f output/l3/S153/ docs/plans/`

---

## Requirements Regression Checklist

- [ ] Does FIX-D4 default warehouse to "Stores - BEI" when PO has no ship_to?
- [ ] Does FIX-D4 throw a clear error if no default warehouse can be found?
- [ ] Does FIX-D8 show OR upload button on "Approved", "Paid", and "Paid - Awaiting OR" statuses?
- [ ] Does FIX-D8 require OR number and date before submission?
- [ ] Does FIX-D7 default payment_mode to "Bank Transfer" on the RFP creation form?
- [ ] Does FIX-D2 only clear is_new_supplier after the configured window (default 30 days)?
- [ ] Does FIX-D2 still require CEO approval for genuinely new suppliers (within window)?
- [ ] Does FIX-D10 show the actual PO name in the conversion toast?
- [ ] Does every new/modified @frappe.whitelist() endpoint call set_backend_observability_context()?
- [ ] Is the `POST /payment-requests/:name/upload-or` route added to the bei-tasks API proxy?

### S152 Corner Cut Remediation Checks
- [ ] Is the AP Invoices CSV export verified by actually reading the downloaded file and counting rows? (Not just checking button exists)
- [ ] Is the Supplier Ledger timeline verified by reading actual PO/GR/Invoice entries in the panel? (Not just checking supplier count)
- [ ] Is the Invoice "Verify" button clicked and status confirmed as "Verified"? (Not left in "Pending 3-Way Match")
- [ ] Is partial GR tested with actual qty edits (50% of ordered) and PO status = "Partially Received"?
- [ ] Is RFP rejection tested at L1 AND L3 (not just L2)?
- [ ] Are AP Payments approval icons verified per-RFP (Chain A=3 green+1 gray, Chain C=4 green, Rejected=red X)?
- [ ] Are Aging matrix column headers verified as text content (not just column count)?
- [ ] Is every PASS backed by value verification (actual text/number content), NOT existence checking?

---

## Autonomous Execution Contract

```yaml
completion_condition:
  - All 5 fixes (D2, D4, D7, D8, D10) implemented and deployed
  - All 6 Group A (defect fix verification) scenarios PASS
  - All 8 Group B (S152 corner cut remediation) scenarios PASS — 14 total
  - DEFECTS.md updated with FIXED status for all 5
  - S152 soft-pass scenarios re-verified with airtight evidence
  - Plan status updated to COMPLETED
  - SPRINT_REGISTRY.md updated
stop_only_for:
  - Missing BEI Settings field that needs DocType migration
  - Business decision on new vendor window duration
continue_without_pause_through:
  - Backend fixes
  - Frontend fixes
  - PR creation
  - L3 re-verification
  - Closeout
blocker_policy:
  programmatic: fix and continue
  business: pause and ask (e.g., new vendor window days)
signoff_authority: single-owner (Sam)
canonical_closeout_artifacts:
  - output/l3/S153/form_submissions.json
  - output/l3/S153/state_verification.json
  - output/l3/S152/DEFECTS.md (updated)
  - docs/plans/2026-04-01-sprint-153-procurement-defect-remediation.md
  - docs/plans/SPRINT_REGISTRY.md
```

---

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

---

## Key File Paths

| What | Path |
|------|------|
| Defect register | `output/l3/S152/DEFECTS.md` |
| GR creation backend | `hrms/api/procurement.py` — `create_goods_receipt()` |
| PO approval logic | `hrms/hr/doctype/bei_purchase_order/bei_purchase_order.py` |
| PO normalization | `hrms/api/procurement.py` — around line 1174 |
| Payment detail page | `bei-tasks/app/dashboard/procurement/payments/[id]/page.tsx` |
| Payment new page | `bei-tasks/app/dashboard/procurement/payments/new/page.tsx` |
| PR detail page | `bei-tasks/app/dashboard/procurement/purchase-requisitions/[id]/page.tsx` |
| GR new page | `bei-tasks/app/dashboard/procurement/goods-receipts/new/page.tsx` |
| Procurement hooks | `bei-tasks/hooks/use-procurement.ts` |
| API route proxy | `bei-tasks/app/api/procurement/[...slug]/route.ts` |
| S152 test scripts | `scripts/testing/l3_s152_*.mjs` |
