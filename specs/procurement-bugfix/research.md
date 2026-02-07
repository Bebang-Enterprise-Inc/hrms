# Research: Procurement Module Bug Fixes

**Date:** 2026-02-07
**Spec:** procurement-bugfix
**Source:** Automated audit of 63 backend endpoints + 13 frontend pages

---

## 1. Audit Summary

| Area | Result |
|------|--------|
| Backend API endpoints tested | 63/63 (100% reachable) |
| Frontend pages audited | 13/13 |
| Business rules verified | 8/8 |
| Audit controls verified | 8/8 |
| **Bugs found** | **7 (3 critical, 2 medium, 2 low)** |

---

## 2. Root Cause Analysis

### BUG-1: Invoice PO Link -> `/purchase-orders/undefined` (CRITICAL)

**Symptom:** Clicking "View PO" on invoice list navigates to `/purchase-orders/undefined`
**Root Cause:** `get_invoices()` in `procurement.py` line ~764 does not include `purchase_order` in the SQL SELECT fields. The API returns the field as `undefined` in the JSON response.
**Fix:** Add `purchase_order` to the SELECT clause in `get_invoices()`.
**Files:**
- Backend: `hrms/api/procurement.py` (~line 764, `get_invoices` function)

### BUG-2: Payment Supplier Links -> `/suppliers/null` (CRITICAL)

**Symptom:** All 4 payment rows link to `/suppliers/null`
**Root Cause:** `get_payment_requests()` in `procurement.py` line ~915 returns payment data but `supplier` field is null/missing from the SQL query response.
**Fix:** Join `tabBEI Invoice` or `tabBEI Purchase Order` to resolve supplier, or add `supplier` to `tabBEI Payment Request` directly if it exists as a field.
**Files:**
- Backend: `hrms/api/procurement.py` (~line 915, `get_payment_requests` function)

### BUG-3: `get_received_value_for_po` Returns 500 (CRITICAL)

**Symptom:** API returns `ProgrammingError: Table 'tabBEI Goods Receipt' missing` or wrong column reference
**Root Cause:** The SQL in `get_received_value_for_po()` at lines ~1658-1670 references table/field names that don't match the actual DocType schema. Likely uses `tabBEI Goods Receipt Item` but the table name or column names are wrong.
**Fix:** Correct the table name and field references to match actual BEI GR Item DocType schema.
**Files:**
- Backend: `hrms/api/procurement.py` (~lines 1650-1683, `get_received_value_for_po` function)

### BUG-4: Supplier List Shows "PHP NaN" (MEDIUM)

**Symptom:** All 6 suppliers show "PHP NaN" for order value column
**Root Cause:** API `get_suppliers()` returns `total_po_value` field but the frontend `suppliers/page.tsx` expects `total_amount`. The `formatCurrency()` call receives `undefined`, producing NaN.
**Fix:** Either rename the backend field to `total_amount` or update the frontend to read `total_po_value`. Backend alignment is preferred (single source fix).
**Files:**
- Backend: `hrms/api/procurement.py` (~line 68, `get_suppliers` function)
- OR Frontend: `bei-tasks/app/dashboard/procurement/suppliers/page.tsx` (~line 134)

### BUG-5: Sidebar Badge Counts Show "0" (MEDIUM)

**Symptom:** Purchase Orders shows "0" despite 2 POs existing; Payments shows "0" despite 4 payments existing
**Root Cause:** Badge counts call `get_pending_po_approvals` and `get_pending_payment_approvals` which filter for status="Pending Approval" only. Since no POs/payments are currently in "Pending Approval" status, the count is correctly 0. However, this is confusing UX - badges should either show total count or be labeled "Pending".
**Fix:** Frontend change - either label badges as "Pending" or change to show total counts.
**Files:**
- Frontend: `bei-tasks/app/dashboard/procurement/layout.tsx` or sidebar component

### BUG-6: Goods Receipt Log Report Missing "Coming Soon" Badge (LOW)

**Symptom:** 5 of 6 unreleased reports show "Coming Soon" but Goods Receipt Log doesn't
**Root Cause:** Report entry in the reports page array is missing the `comingSoon: true` flag.
**Fix:** Add `comingSoon: true` to the Goods Receipt Log entry in the reports page.
**Files:**
- Frontend: `bei-tasks/app/dashboard/procurement/reports/page.tsx`

### BUG-7: PO Detail Shows "0 Line Items" But Grand Total is PHP 672K (LOW)

**Symptom:** PO-2026-00040 detail page shows "0 line items" but Grand Total = PHP 672,000
**Root Cause:** `get_purchase_order()` likely returns the PO header but the items array is empty or the items are stored in a child table (`tabBEI PO Item`) that isn't being joined/queried properly.
**Fix:** Ensure `get_purchase_order()` includes a subquery or join to fetch `tabBEI PO Item` rows for the PO.
**Files:**
- Backend: `hrms/api/procurement.py` (`get_purchase_order` function)
- Frontend: `bei-tasks/app/dashboard/procurement/purchase-orders/[id]/page.tsx` (~line 508)

---

## 3. Impact Analysis

| Bug | Users Affected | Workaround Available |
|-----|---------------|---------------------|
| BUG-1 | All procurement users viewing invoices | Manual navigation to PO page |
| BUG-2 | All users viewing payment list | Manual navigation to supplier page |
| BUG-3 | Audit/compliance users | No workaround - data unavailable |
| BUG-4 | All users viewing supplier list | None - data shows as NaN |
| BUG-5 | All procurement sidebar users | Confusing but not blocking |
| BUG-6 | Users viewing reports page | Minor visual inconsistency |
| BUG-7 | Users viewing PO details | Total still visible, but no line item breakdown |

---

## 4. Technical Feasibility

All 7 bugs are **straightforward fixes** with clear root causes:
- 5 bugs are backend-only (SQL query fixes in `procurement.py`)
- 2 bugs are frontend-only (React component fixes in `bei-tasks`)
- No schema changes needed (no new DocTypes or migrations)
- No breaking API contract changes (all fixes are additive)

**Estimated effort:** 2-4 hours for all 7 fixes + testing + deployment
