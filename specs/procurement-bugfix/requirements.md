# Requirements: Procurement Module Bug Fixes

**Date:** 2026-02-07
**Spec:** procurement-bugfix
**Priority:** CRITICAL - Fix before user training

---

## User Stories

### REQ-1: Invoice-to-PO Navigation [CRITICAL] [FIX]

**As a** procurement user viewing the invoice list,
**I want** to click a PO reference link on any invoice row,
**So that** I can navigate to the associated purchase order detail page.

**Acceptance Criteria:**
- [ ] Invoice list shows PO reference as clickable link
- [ ] Clicking the link navigates to `/procurement/purchase-orders/{po_id}`
- [ ] Link is never `undefined` or `null`
- [ ] Works for all invoices that have an associated PO

**Root Cause:** `get_invoices()` API missing `purchase_order` in SELECT

---

### REQ-2: Payment-to-Supplier Navigation [CRITICAL] [FIX]

**As a** finance user viewing the payments list,
**I want** to click a supplier name on any payment row,
**So that** I can navigate to the supplier detail page.

**Acceptance Criteria:**
- [ ] Payment list shows supplier name as clickable link
- [ ] Clicking the link navigates to `/procurement/suppliers/{supplier_code}`
- [ ] Link is never `null` for any payment that has an associated supplier
- [ ] Works for all 4+ existing payment records

**Root Cause:** `get_payment_requests()` API not returning `supplier` field

---

### REQ-3: Received Value Audit Report [CRITICAL] [FIX]

**As an** internal auditor checking procurement compliance,
**I want** to query the received value for any purchase order,
**So that** I can verify partial delivery limits and 3-way match accuracy.

**Acceptance Criteria:**
- [ ] `get_received_value_for_po` endpoint returns 200 with valid data
- [ ] Response includes: ordered_value, received_value, variance
- [ ] Works for PO-2026-00040 (known test PO with GR)
- [ ] No 500 ProgrammingError

**Root Cause:** Wrong table/field names in SQL query

---

### REQ-4: Supplier Order Value Display [MEDIUM] [FIX]

**As a** procurement manager viewing the supplier list,
**I want** to see the total PO value for each supplier as a formatted currency,
**So that** I can assess supplier spend at a glance.

**Acceptance Criteria:**
- [ ] Supplier list shows formatted PHP currency (e.g., "PHP 153,300,000")
- [ ] Never displays "PHP NaN" or "PHP undefined"
- [ ] Shows "PHP 0" for suppliers with no POs
- [ ] Works for all 6+ existing suppliers

**Root Cause:** Backend field name mismatch (`total_po_value` vs `total_amount`)

---

### REQ-5: Sidebar Badge Accuracy [MEDIUM] [FIX]

**As a** procurement user navigating the module,
**I want** sidebar badges to accurately reflect pending work,
**So that** I know which sections need my attention.

**Acceptance Criteria:**
- [ ] Badges labeled "Pending" (not just a number)
- [ ] Show 0 when no items pending approval (correct behavior)
- [ ] OR show total counts with clear label (e.g., "2 total")
- [ ] Consistent behavior across Purchase Orders and Payments badges

**Root Cause:** Badges show pending approval count (correct) but label is ambiguous

---

### REQ-6: Reports Page Consistency [LOW] [FIX]

**As a** user browsing the procurement reports page,
**I want** all unreleased reports to have a "Coming Soon" badge,
**So that** I can distinguish between live and upcoming reports.

**Acceptance Criteria:**
- [ ] Goods Receipt Log report has "Coming Soon" badge
- [ ] All 6 unreleased reports have consistent "Coming Soon" styling
- [ ] Only live reports (AP Aging, Supplier Performance) are clickable

**Root Cause:** Missing flag on one report entry

---

### REQ-7: PO Detail Line Items [LOW] [FIX]

**As a** procurement user viewing a purchase order detail,
**I want** to see the line items (products, quantities, prices),
**So that** I can verify what was ordered.

**Acceptance Criteria:**
- [ ] PO-2026-00040 shows its line items (not "0 line items")
- [ ] Each item shows: name, quantity, unit price, total
- [ ] Item count matches the actual items in the PO
- [ ] Grand total = sum of line item totals

**Root Cause:** `get_purchase_order()` not returning items from child table

---

## Non-Functional Requirements

### NFR-1: No Breaking Changes
- All fixes must be backward-compatible
- No API contract changes that would break existing frontend code
- No database schema changes (no migrations needed)

### NFR-2: Test Coverage
- Each bug fix must be verified via API call and/or Chrome DevTools snapshot
- Backend fixes verified with curl against production
- Frontend fixes verified with browser navigation

### NFR-3: Code Review
- All changes reviewed by Opus code-reviewer before merge
- Security check: no SQL injection in fixed queries
- Performance check: no N+1 queries introduced
