# S141 Procurement Module Investigation Findings

**Date:** 2026-03-28
**Investigator:** Claude (code analysis + API tracing)
**Method:** Static code analysis of bei-tasks frontend + hrms backend

---

## Summary

9 issues identified across 3 groups. Root causes determined for all.

---

## Group 1: PO Page Bugs

### Issue 1: No Pagination on PO Page
- **Root Cause:** `MISSING_UI`
- **File:** `bei-tasks/app/dashboard/procurement/purchase-orders/page.tsx`
- **Details:** `page` state (line 497) and `setPage` exist but no Previous/Next buttons. `setPage` only called to reset to 1 on search/filter change (lines 669, 678). The table renders `allPOs?.data?.map(...)` but stops at 20 rows (pageSize=20).
- **Backend:** `get_purchase_orders` already supports `page`, `page_size` params and returns `total` count (577 POs). `PaginatedResponse<T>` type includes `total_pages`.
- **Reference Pattern:** GR page (`goods-receipts/page.tsx` lines 340-366) has working pagination with "Showing X to Y of Z" + Previous/Next buttons.
- **Fix:** Copy GR pagination pattern after the PO table (after line 746).

### Issue 2: Empty "Approved" Tab
- **Root Cause:** `NOT_IMPLEMENTED`
- **File:** `bei-tasks/app/dashboard/procurement/purchase-orders/page.tsx` lines 901-903
- **Details:** `TabsContent value="approved"` contains only a comment `{/* Similar table for approved POs */}`. No query, no table, no data.
- **Fix:** Add a separate `usePurchaseOrders` call with status filter for Approved/Fully Received/Partially Received, render table with pagination.
- **HARD BLOCKER CHECK:** `buildOperationalProcurementFilters` passes `status` directly. For array status, need to verify backend handles `["in", [...]]` format. Alternative: use comma-separated or separate queries.

### Issue 3: Missing Status Filter Options
- **Root Cause:** `MISSING_UI`
- **File:** `bei-tasks/app/dashboard/procurement/purchase-orders/page.tsx` lines 684-693
- **Details:** Status dropdown has: Draft, Pending Mae, Pending Butch, Approved, Sent to Supplier, Partially Received, Fully Received. Missing: "Pending CEO Approval" (added in S132) and "Cancelled" (15 POs exist with this status).
- **Note:** `statusColors` map (line 83-93) already includes both `Pending CEO Approval` and `Cancelled` — only the dropdown is missing them.
- **Fix:** Add two `SelectItem` entries.

---

## Group 2: Dashboard Data Issues (All Zeros)

### Issue 4-8: Total Outstanding, Overdue, Avg Payment Days, AP Aging, Outstanding by Supplier — ALL ₱0
- **Root Cause:** `NO_DATA`
- **Backend Analysis:**
  - `get_dashboard_kpis()` (line 2743): Queries `tabBEI Invoice` for `total_outstanding` and `overdue_amount`. Returns COALESCE(..., 0).
  - `get_aging_analysis()` (line 2839): Queries `tabBEI Invoice` WHERE payment_status != 'Paid'.
  - `get_outstanding_by_supplier()` (line 2817): LEFT JOIN `tabBEI Invoice` on `tabBEI Supplier`.
  - `get_payment_schedule()` (line 2895): Queries `tabBEI Invoice` WHERE payment_status != 'Paid'.
- **Why empty:** BEI procurement is still Google Sheet-based. The sync pipeline creates POs and GRs from the Compliance App, but **invoices are NOT synced**. `tabBEI Invoice` has 0 records. Therefore ALL invoice-dependent KPIs correctly return 0.
- **Cards that DO have data:**
  - `mtd_po_value` / `mtd_po_count` — queries `tabBEI Purchase Order` (577 exist) ✅
  - `pending_po_approvals` — queries `tabBEI Purchase Order` ✅
  - `active_suppliers` — queries `tabBEI Supplier` (145 exist) ✅
- **Fix:** Show "No invoice data synced yet" empty state for invoice-dependent cards instead of misleading ₱0. This is NOT a bug — it's expected behavior for the current migration stage. Adding fake data would be worse.

---

## Group 3: Duplicate Sidebar

### Issue 9: Two Sidebars Visible
- **Root Cause:** `ARCHITECTURE_OVERLAP`
- **File 1:** `bei-tasks/app/dashboard/procurement/layout.tsx` — renders its own `<aside>` sidebar with 8 items (Dashboard, Suppliers, Purchase Orders, Goods Receipts, Invoices, Payments, OR Follow-up, Reports + Settings)
- **File 2:** `bei-tasks/components/layout/nav-main.tsx` — the main app sidebar includes a "Procurement" section with 25+ items (same 8 plus Critical Items Control Tower, Critical Stockout Incidents, Purchase Requisitions, Approvals, SOA, Monthly Spend, Supplier Performance, etc.)
- **Result:** On desktop (lg+), both sidebars render: the main nav on the far left, and the procurement inner sidebar next to it. User sees duplicate navigation.
- **Fix:** Remove the inner sidebar from `layout.tsx`. The main nav already has all procurement items. The layout should just render `{children}` wrapped in `RoleGuard`.

---

## Classification Summary

| Issue | Page | Root Cause | Fix Type | Units |
|-------|------|-----------|----------|-------|
| 1. No PO pagination | purchase-orders | MISSING_UI | Add UI component | 1 |
| 2. Empty Approved tab | purchase-orders | NOT_IMPLEMENTED | Add query + table | 2 |
| 3. Missing status filters | purchase-orders | MISSING_UI | Add 2 SelectItems | 0.5 |
| 4. Total Outstanding ₱0 | dashboard | NO_DATA | Empty state | 1 |
| 5. Overdue Amount ₱0 | dashboard | NO_DATA | Empty state | (same) |
| 6. Avg Payment Days 0 | dashboard | NO_DATA | Empty state | (same) |
| 7. AP Aging ₱0 | dashboard | NO_DATA | Empty state | 1 |
| 8. Outstanding by Supplier empty | dashboard | NO_DATA | Empty state | (same) |
| 9. Duplicate sidebar | layout | ARCHITECTURE_OVERLAP | Remove inner sidebar | 1 |

**Total estimated units: ~6.5** (much less than the 31 estimated in the plan because Phase 0 investigation was done via code analysis rather than browser automation, and the fixes are straightforward)
