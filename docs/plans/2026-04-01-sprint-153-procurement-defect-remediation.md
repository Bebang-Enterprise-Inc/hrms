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
| Phase 0: DocType Migration | 2 | Add `default_receiving_warehouse` Link field to BEI Settings + migrate |
| Phase 1: Backend Fixes (hrms) | 8 | D4 warehouse fallback, D2 CEO ratchet fix |
| Phase 2: Frontend Fixes (bei-tasks) | 10 | D8 OR upload, D7 payment method, D10 toast hook fix, D4 editable warehouse |
| Phase 2.5: Deploy Gate | 1 | Create PRs (hrms + bei-tasks), user merges, verify both deployed before Phase 3 |
| Phase 3: L3 Re-Verification + S152 Corner Cuts | 14 | Verify defect fixes + re-test S152 soft passes |
| Phase 4: Closeout | 2 | Plan + registry update, evidence commit |
| **TOTAL** | **37** | |

**AUDIT BLOCKER RESOLVED:** Phase 0 added for DocType migration. Phase 2.5 added as explicit deploy gate between code changes and L3 testing.

---

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s153-procurement-defect-remediation origin/production`. NEVER write code on production.
3. Read `output/l3/S152/DEFECTS.md` for full defect descriptions and evidence.
4. Read `docs/plans/SPRINT_REGISTRY.md` for cross-sprint context.
5. Begin Phase 1.

---

## Phase 0: DocType Migration (2 units) [PRE-REQUISITE]

### Add `default_receiving_warehouse` to BEI Settings

**AUDIT BLOCKER (CRITICAL):** The field `default_receiving_warehouse` does NOT exist in `bei_settings.json`. FIX-D4 code that calls `get_single_value("BEI Settings", "default_receiving_warehouse")` will silently return `None`.

**Fix:**
1. Add to `hrms/hr/doctype/bei_settings/bei_settings.json`:
   ```json
   {"fieldname": "default_receiving_warehouse", "fieldtype": "Link", "options": "Warehouse", "label": "Default Receiving Warehouse"}
   ```
2. Add to `field_order` array in the procurement section
3. Run `bench migrate` after deploy
4. Set value to "Stores - BEI" via BEI Settings page

---

## Phase 1: Backend Fixes — hrms (8 units)

### FIX-D4: GR Warehouse Fallback (3 units) [EXTEND]

**File:** `hrms/api/procurement.py` — `create_goods_receipt()`

**Problem:** When a PO has empty `ship_to` (common for PR-based POs), the GR is created with empty `warehouse`. The frontend field is read-only.

**AUDIT CORRECTION:** Code at line 2056 already does `data["warehouse"] = po.ship_to` when PO has ship_to. The fix is ONLY for the fallback when PO.ship_to is empty.

**Fix:** Add fallback AFTER the existing po.ship_to check (line ~2057):
```python
# Existing code already handles: data["warehouse"] = po.ship_to
# Add fallback for when po.ship_to is empty:
if not data.get("warehouse"):
    default_wh = frappe.db.get_single_value("BEI Settings", "default_receiving_warehouse")
    if default_wh:
        data["warehouse"] = default_wh
    else:
        frappe.throw(_("Warehouse is required. Set a default receiving warehouse in BEI Settings."))
```

**HARD BLOCKER:** Phase 0 (DocType migration) MUST complete before this fix. Without the field in BEI Settings, `get_single_value` returns None silently.

**Sentry:** Already exists on `create_goods_receipt`, no change needed.

### FIX-D2: New Vendor CEO Approval — Fix One-Way Ratchet (5 units) [EXTEND]

**File:** `hrms/hr/doctype/bei_purchase_order/bei_purchase_order.py` — `check_new_vendor_ceo_requirement()`

**Problem:** `requires_ceo_approval` is set to 1 when `is_new_supplier` returns True, but NEVER set back to 0. A PO saved while supplier was "new" stays stuck requiring CEO forever, even after the supplier ages past the window.

**AUDIT CORRECTIONS:**
1. `is_new_supplier` is a **computed `@property`** on BEI Supplier — it already checks the window via `new_supplier_window_days` in BEI Settings. There is NOTHING to "clear" on the supplier.
2. The correct field name is `new_supplier_window_days` (NOT `new_vendor_window_days` as originally written).
3. The bug is in `check_new_vendor_ceo_requirement` — it only sets `requires_ceo_approval = 1`, never `= 0`.
4. **WARNING (DM-5):** `bei_payment_request.py` reads `is_new_supplier` via `frappe.db.get_value` (stored field) while `bei_supplier.py` defines it as a `@property` (computed). If BEI Supplier DocType also has a stored `is_new_supplier` column, it can go stale. Audit this during execution.

**Fix:**
```python
def check_new_vendor_ceo_requirement(self):
    if self.supplier:
        supplier_doc = frappe.get_doc("BEI Supplier", self.supplier)
        if supplier_doc.is_new_supplier:  # @property, recomputes each call
            self.requires_ceo_approval = 1
        else:
            self.requires_ceo_approval = 0  # AUDIT FIX: clear the ratchet
```

**HARD BLOCKER:** Do NOT use `frappe.db.set_value` to mutate the supplier's `is_new_supplier` — it's a computed property, not a stored field.

---

## Phase 2: Frontend Fixes — bei-tasks (10 units)

### FIX-D8: OR Upload Button on Payment Detail (4 units) [BUILD]

**File:** `bei-tasks/app/dashboard/procurement/payments/[id]/page.tsx`

**Problem:** After RFP is paid, the payment detail page has no OR upload button. Finance cannot record receipt of official receipts.

**AUDIT CORRECTIONS:**
1. **Route already exists** — `POST /payment-requests/:name/upload-or` is already at line 188 of route.ts. Do NOT add it again.
2. **Status visibility CORRECTED** — backend at `procurement.py:4798` only accepts "Paid" and "Paid - Awaiting OR". Showing button at "Approved" will produce a 400 error. **Show button ONLY at "Paid" and "Paid - Awaiting OR".**
3. **TypeScript gap** — Add `or_status?: string` to the `PaymentRequestDetail` interface. Hide button when `or_status === 'OR Received'`.
4. **File attachment flow** — For the optional `or_attachment` field, use the same pattern as GR photo upload: POST to `/api/frappe/api/method/upload_file` → get `file_url` → include as `or_attachment`.

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

2. Add OR upload dialog on payment detail page:
   - **Visible when:** `status === "Paid" || status === "Paid - Awaiting OR"` AND `or_status !== "OR Received"`
   - **NOT visible at "Approved"** (backend rejects it)
   - OR Number (required text input)
   - OR Date (required date input)
   - OR Amount (required number input, default to payment_amount)
   - File attachment (optional, uses upload_file → file_url pattern)
   - Submit button with loading/error states

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

**AUDIT CORRECTION:** The page handler uses a static string `'PO created successfully'` — this cannot produce "undefined". The bug is in the `useConvertPRToPO` hook's `onSuccess` callback which references `data.po_number` but the backend returns `po_name`.

**File:** `bei-tasks/hooks/use-procurement.ts` — `useConvertPRToPO` hook

**Fix:** In the hook's `onSuccess`, change `data.po_number` to `data.po_name`:
```typescript
onSuccess: (data) => {
  queryClient.invalidateQueries({ queryKey: ['purchase-requisitions'] });
  queryClient.invalidateQueries({ queryKey: ['purchase-orders'] });
  toast.success(`Converted to PO: ${data.po_name}`);  // FIX: was data.po_number (undefined)
},
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
| L3-A05 | test.finance | **Precondition:** verify supplier `1T1MI3` creation date is >30 days ago via API. Then create PO for that supplier → verify requires_ceo_approval=0 | requires_ceo_approval=0, Mae-only approval (no CEO). If supplier is <30 days old, use a different supplier or adjust `new_supplier_window_days` to 1 in BEI Settings for the test. | FIX-D2 not working |
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
| L3-B07 | Multi-RFP icons | test.finance | **Depends on:** L3-A02, L3-B05, L3-B06 (creates the RFPs). AP Payments tab → find approved RFP, rejected-at-L1 RFP, rejected-at-L3 RFP → verify icon patterns per row | Approved: all green checks. L1-rejected: red X at reviewer level. L3-rejected: green L1+L2, red X at CFO. | S152 only had 1 payment row visible, couldn't verify patterns |
| L3-B08 | D03 Aging columns | test.finance | AP Aging tab → verify ALL bucket column headers | Headers include "Current", "1-30", "31-60", "61-90", "90+" as text | S152 found current=false, marked PASS on row count only |

---

## Phase 2.5: Deploy Gate (1 unit)

**AUDIT BLOCKER RESOLVED:** Phase 3 tests MUST run against deployed code, not local changes.

1. Create **hrms PR** from branch `s153-procurement-defect-remediation` → base `production`
2. Create **bei-tasks PR** from matching branch → base `main`
3. **STOP and wait** for Sam to merge both PRs
4. Verify hrms deployed: `curl https://hq.bebang.ph/api/method/ping` returns 200
5. Verify bei-tasks deployed: `curl https://my.bebang.ph/login` returns 200
6. Commit L3 evidence to branch: `git add -f output/l3/S153/ && git push`
7. **Only then** proceed to Phase 3

---

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
  - output/l3/S153/api_mutations.json
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

## Reusable Test Scripts (DO NOT recreate — extend these)

The S152 test scripts are committed to production via Bebang-Enterprise-Inc/hrms#409. S153 should **extend** these scripts, not rewrite them.

| Script | Purpose | Reuse In S153 |
|--------|---------|---------------|
| `scripts/testing/l3_s152_helpers.mjs` | Shared: browser login, `browserCreatePO`, `browserApprovePO`, `browserCreateGR`, `browserCreateInvoice`, `browserCreateRFP`, `browserSubmitAndApproveRFP`, `browserRejectPO`, `browserRejectRFP`, evidence tracking, PNG generator | **YES — import all browser actions from here. Do NOT duplicate.** |
| `scripts/testing/l3_s152_chain_a.mjs` | Chain A: PR→PO≤500K→Mae→GR→Invoice→RFP 3-level→OR | Copy + modify for L3-A02 (OR upload test) and L3-B03 (invoice verify) |
| `scripts/testing/l3_s152_chain_bc.mjs` | Chain B: >500K dual + Chain C: >1M CEO | Copy + modify for L3-A05 (CEO window test) |
| `scripts/testing/l3_s152_edge_cases.mjs` | PO reject, RFP reject, partial GR, variance | Copy + modify for L3-B04 (partial GR), L3-B05/B06 (L1/L3 rejection) |
| `scripts/testing/l3_s152_dashboards.mjs` | AP CC + procurement pages | Copy + modify for L3-B01 (CSV), L3-B02 (timeline), L3-B07 (icons), L3-B08 (aging cols) |
| `scripts/testing/l3_s152_run_all.mjs` | Master runner | Extend to include S153 scripts |

**Key patterns already solved in helpers (do NOT re-solve):**
- Login with email match: `loginAs(browser, 'mae')` / `loginAs(browser, 'butch')` / `loginAs(browser, 'sam')`
- PO approval chain: `browserSubmitPO` → `browserApprovePO(mae)` → `browserApprovePO(butch)` → `browserApprovePO(sam)`
- GR from PO: `browserCreateGR` handles PO card click, qty fill, photo upload, submit
- Invoice from PO+GR: `browserCreateInvoice` handles PO card, GR card, invoice#, dates
- RFP 4-level: `browserSubmitAndApproveRFP` handles submit + approve per level
- PHT date calculation: `new Date(Date.now() + 8 * 3600000).toISOString().slice(0, 10)`
- Toast dismissal: `page.evaluate(() => document.querySelectorAll('[data-sonner-toast]').forEach(t => t.remove()))`

**Scenario definitions:** `docs/testing/scenarios/modules/s152-procurement-e2e.md` (35 scenarios — extend for S153)

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
| BEI Settings DocType | `hrms/hr/doctype/bei_settings/bei_settings.json` |
| BEI Supplier DocType | `hrms/hr/doctype/bei_supplier/bei_supplier.py` (has `is_new_supplier` @property) |
| Audit findings | `output/plan-audit/s153-procurement-defect-remediation/*.md` |

---

## Audit History

### Audit v1 — 2026-04-01 (4 domain agents + code verifier)

**Auditors:** frappe-backend, frontend, deployment-qa, code-verifier
**Result:** 4 blockers, 6 warnings, 5 stale claims corrected, 3 new gaps added

**Amendments applied to authoritative sections above:**

| # | Finding | Amendment |
|---|---------|-----------|
| 1 | `default_receiving_warehouse` field missing from BEI Settings | Added Phase 0 (DocType migration) as pre-requisite |
| 2 | FIX-D4 code already has `po.ship_to` default at line 2056 | Reduced scope to fallback-only when ship_to is empty |
| 3 | FIX-D2: `is_new_supplier` is a `@property`, not a stored field | Rewrote fix to clear `requires_ceo_approval` ratchet instead |
| 4 | Field name is `new_supplier_window_days` not `new_vendor_window_days` | Corrected throughout plan |
| 5 | Upload-or route already exists in route.ts line 188 | Removed duplicate route creation from FIX-D8 |
| 6 | OR upload button at "Approved" status = backend 400 error | Changed visibility to "Paid" and "Paid - Awaiting OR" only |
| 7 | `or_status` not in TypeScript interface | Added to FIX-D8 requirements |
| 8 | FIX-D10 bug is in hook (`po_number` vs `po_name`), not page handler | Changed fix location to `use-procurement.ts` |
| 9 | No deploy gate between Phase 2 and Phase 3 | Added Phase 2.5 with explicit PR + deploy verification |
| 10 | `api_mutations.json` missing from evidence contract | Added to canonical closeout artifacts |
| 11 | L3-A05 missing supplier data precondition | Added creation date check + fallback |
| 12 | L3-B07 dependency on L3-A02/B05/B06 not explicit | Added dependency note to scenario |
| 13 | DM-5 risk: `bei_payment_request.py` reads `is_new_supplier` as stored field | Added WARNING to FIX-D2 for audit during execution |
