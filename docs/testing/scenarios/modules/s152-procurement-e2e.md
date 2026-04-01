# S152 Procurement E2E Acceptance Scenarios

## Chain A: Standard Flow (≤P500K, Mae-only PO, 3-level RFP)

### S152-A01: Create Purchase Requisition
- **Type:** happy
- **Role:** test.finance@bebang.ph
- **Route:** `/dashboard/procurement/purchase-requisitions/new`
- **Payload:**
  - department: "Operations"
  - date_required: tomorrow
  - purpose: "S152 Chain A — E2E acceptance test"
  - items: 3 items from item picker, qty 5-20 each
- **Assert:**
  - PR created with auto-generated PR number
  - Status = "Draft"
  - total_estimated_cost > 0
  - DB verify: `fDoc("BEI Purchase Requisition", name)` → status=Draft

### S152-A02: Submit PR for Approval
- **Type:** happy
- **Role:** test.finance@bebang.ph
- **Depends:** S152-A01
- **Route:** `/dashboard/procurement/purchase-requisitions/[A01.name]`
- **Action:** Click "Submit for Approval" button
- **Assert:**
  - Status → "Pending Approval"
  - DB verify: status field = "Pending Approval"

### S152-A03: Approve PR (CEO)
- **Type:** happy
- **Role:** sam@bebang.ph (password: 2289454)
- **Depends:** S152-A02
- **Route:** `/dashboard/procurement/purchase-requisitions/[A01.name]`
- **Action:** Click "Approve" → enter comment "S152 Chain A approved"
- **Assert:**
  - Status → "Approved"
  - approved_by contains sam
  - approval_date set
  - DB verify: status=Approved, approved_by set

### S152-A04: Convert PR to PO
- **Type:** happy
- **Role:** test.finance@bebang.ph
- **Depends:** S152-A03
- **Route:** `/dashboard/procurement/purchase-requisitions/[A01.name]` → Convert to PO → `/dashboard/procurement/purchase-orders/new`
- **Action:**
  - Click "Convert to PO"
  - Select supplier from dropdown (existing, not new vendor)
  - Verify items auto-populated from PR
  - Set delivery date
  - Ensure grand_total ≤ P500,000
  - Click "Create PO"
- **Assert:**
  - PO created with pr_reference = A01.name
  - requires_dual_approval = 0
  - Items match PR items
  - VAT calculated at 12%
  - DB verify: PO exists, pr_reference set, requires_dual_approval=0

### S152-A05: Mae Approves PO (≤500K — Mae only)
- **Type:** happy
- **Role:** mae@bebang.ph (EMAIL MATCH REQUIRED)
- **Depends:** S152-A04
- **Route:** `/dashboard/procurement/purchase-orders/[A04.po_name]`
- **Action:**
  - Submit PO for approval (as test.finance first)
  - Login as mae@bebang.ph
  - Verify "Approve" button IS visible
  - Click "Approve" → comment "S152 Mae approved"
- **Assert:**
  - Status → "Approved" (NOT "Pending Butch" — this is ≤500K)
  - mae_approval = "Approved"
  - mae_approval_date set
  - DB verify: status=Approved, mae_approval=Approved

### S152-A06: Send PO to Supplier
- **Type:** happy
- **Role:** test.finance@bebang.ph
- **Depends:** S152-A05
- **Route:** `/dashboard/procurement/purchase-orders/[A04.po_name]`
- **Action:** Click "Send to Supplier"
- **Assert:**
  - Status → "Sent to Supplier"
  - sent_to_supplier_date set
  - DB verify: status="Sent to Supplier"

### S152-A07: Create Goods Receipt
- **Type:** happy
- **Role:** test.warehouse@bebang.ph
- **Depends:** S152-A06
- **Route:** `/dashboard/procurement/goods-receipts/new`
- **Action:**
  - Select PO from dropdown
  - Verify items auto-populated from PO
  - Set receipt_date = today
  - Set accepted_qty = ordered_qty for all items (full receipt)
  - Upload supplier invoice photo (150KB test PNG)
  - Click "Create GR"
- **Assert:**
  - GR created linked to PO
  - Status = "Accepted" or "Pending Inspection"
  - PO status updated to "Fully Received"
  - DB verify: GR exists with purchase_order link, PO status="Fully Received"

### S152-A08: Create Invoice with 3-Way Match
- **Type:** happy
- **Role:** test.finance@bebang.ph
- **Depends:** S152-A07
- **Route:** `/dashboard/procurement/invoices/new`
- **Action:**
  - Select PO from dropdown
  - Select/verify GR linked
  - Enter supplier_invoice_no = "SI-S152-A-001"
  - Enter invoice_date = today, due_date = today + 30 days
  - Verify amounts match PO/GR
  - Submit
- **Assert:**
  - Invoice created with PO + GR references
  - match_status = "Matched" (amounts equal)
  - Status → "Verified"
  - DB verify: match_status="Matched", status="Verified"

### S152-A09: Create Payment Request (RFP)
- **Type:** happy
- **Role:** test.finance@bebang.ph
- **Depends:** S152-A08
- **Route:** `/dashboard/procurement/payments/new`
- **Action:**
  - Select invoice from dropdown
  - Verify payment_amount auto-fills from invoice
  - Set rfp_type = "Vendor Invoice"
  - Set payment_mode = "Bank Transfer"
  - Click create
- **Assert:**
  - RFP created with invoice link
  - payment_amount = invoice grand_total
  - ceo_required = 0 (≤1M, existing supplier)
  - DB verify: ceo_required=0, payment_amount matches

### S152-A10: RFP Level 1 — Reviewer Approve
- **Type:** happy
- **Role:** test.finance@bebang.ph (Accounts Manager role)
- **Depends:** S152-A09
- **Route:** `/dashboard/procurement/payments/[A09.name]`
- **Action:**
  - Submit for approval
  - Approve at Level 1 with comment "S152 L1 reviewer — docs complete"
- **Assert:**
  - reviewer_status = "Approved"
  - Status → "Pending Budget Approval"
  - DB verify: reviewer_status="Approved", reviewer set, reviewer_date set

### S152-A11: RFP Level 2 — Budget Approve
- **Type:** happy
- **Role:** test.finance@bebang.ph (Accounts Manager role)
- **Depends:** S152-A10
- **Route:** `/dashboard/procurement/payments/[A09.name]`
- **Action:** Approve at Level 2 with comment "S152 L2 budget confirmed"
- **Assert:**
  - budget_status = "Approved"
  - Status → "Pending CFO Approval"
  - DB verify: budget_status="Approved", budget_approver set

### S152-A12: RFP Level 3 — CFO Approve (No CEO needed)
- **Type:** happy
- **Role:** sam@bebang.ph (System Manager role)
- **Depends:** S152-A11
- **Route:** `/dashboard/procurement/payments/[A09.name]`
- **Action:** Approve at Level 3 with comment "S152 L3 CFO approved"
- **Assert:**
  - cfo_status = "Approved"
  - Status → "Approved" (NOT "Pending CEO" since ≤1M)
  - CEO step was NOT required
  - DB verify: cfo_status="Approved", status="Approved"

### S152-A13: Upload Official Receipt
- **Type:** happy
- **Role:** test.finance@bebang.ph
- **Depends:** S152-A12
- **Route:** `/dashboard/procurement/payments/[A09.name]` or `/dashboard/accounting/awaiting-or`
- **Action:**
  - Upload OR: number="OR-S152-A-001", date=today, amount=payment_amount
  - Attach file
- **Assert:**
  - or_status = "OR Received"
  - Status → "Closed"
  - DB verify: or_status="OR Received", or_number, or_date, or_amount set

---

## Chain B: Dual PO Approval (>P500K)

### S152-B01: Create PO >P500K (Standalone, No PR)
- **Type:** happy
- **Role:** test.finance@bebang.ph
- **Route:** `/dashboard/procurement/purchase-orders/new`
- **Payload:**
  - supplier: existing active supplier (NOT new vendor)
  - items: high-value items totaling > P500,000
  - delivery_date: today + 7
- **Assert:**
  - PO created with grand_total > 500000
  - requires_dual_approval = 1
  - "Requires dual approval" badge visible
  - DB verify: requires_dual_approval=1

### S152-B02: Mae Approves >500K PO → Pending Butch
- **Type:** happy
- **Role:** mae@bebang.ph (EMAIL MATCH)
- **Depends:** S152-B01
- **Route:** `/dashboard/procurement/purchase-orders/[B01.name]`
- **Action:**
  - (test.finance submits for approval first)
  - Login as mae → Approve
- **Assert:**
  - Status → "Pending Butch Approval" (NOT "Approved")
  - mae_approval = "Approved"
  - DB verify: status="Pending Butch Approval"

### S152-B03: Butch Approves >500K PO
- **Type:** happy
- **Role:** butch@bebang.ph (EMAIL MATCH)
- **Depends:** S152-B02
- **Route:** `/dashboard/procurement/purchase-orders/[B01.name]`
- **Action:** Login as butch → Approve
- **Assert:**
  - Status → "Approved"
  - butch_approval = "Approved"
  - butch_approval_date set
  - DB verify: status="Approved", butch_approval="Approved"

### S152-B04: Chain B Completion (GR → Invoice → RFP 3-level → OR)
- **Type:** happy
- **Role:** test.warehouse, test.finance, sam
- **Depends:** S152-B03
- **Action:** Full chain same as A07-A13 but using B01 PO
- **Assert:**
  - All documents created and linked
  - RFP approved through 3 levels (no CEO since <1M)
  - OR uploaded, status=Closed

---

## Chain C: CEO Approval (New Vendor PO + >P1M RFP)

### S152-C01: Create PO with New Vendor >P1M
- **Type:** happy
- **Role:** test.finance@bebang.ph
- **Route:** `/dashboard/procurement/purchase-orders/new`
- **Payload:**
  - supplier: new vendor (S152 test vendor, is_new_supplier=1)
  - items: high-value items totaling > P1,000,000
- **Assert:**
  - requires_dual_approval = 1
  - requires_ceo_approval = 1
  - Both badges visible
  - DB verify: requires_dual_approval=1, requires_ceo_approval=1

### S152-C02: Mae Approves New Vendor PO
- **Type:** happy
- **Role:** mae@bebang.ph (EMAIL MATCH)
- **Depends:** S152-C01
- **Assert:** Status → "Pending Butch Approval"

### S152-C03: Butch Approves New Vendor PO
- **Type:** happy
- **Role:** butch@bebang.ph (EMAIL MATCH)
- **Depends:** S152-C02
- **Assert:** Status → "Pending CEO Approval" (NOT "Approved" — new vendor triggers CEO)

### S152-C04: CEO Approves New Vendor PO
- **Type:** happy
- **Role:** sam@bebang.ph (password: 2289454, EMAIL MATCH)
- **Depends:** S152-C03
- **Route:** `/dashboard/procurement/purchase-orders/[C01.name]`
- **Action:** Login as sam → Approve with comment "S152 CEO approved — new vendor + >1M"
- **Assert:**
  - ceo_approval = "Approved"
  - Status → "Approved"
  - DB verify: ceo_approval="Approved", status="Approved"

### S152-C05: Chain C GR + Invoice
- **Type:** happy
- **Role:** test.warehouse, test.finance
- **Depends:** S152-C04
- **Action:** Create GR (full receipt) + Invoice (3-way match)
- **Assert:** GR accepted, Invoice verified, amounts >1M

### S152-C06: Create RFP >P1M (CEO Required)
- **Type:** happy
- **Role:** test.finance@bebang.ph
- **Depends:** S152-C05
- **Route:** `/dashboard/procurement/payments/new`
- **Assert:**
  - ceo_required = 1 (triggered by >1M AND/OR new supplier)
  - "Requires CEO approval" badge visible
  - DB verify: ceo_required=1

### S152-C07: RFP L1+L2 Approve
- **Type:** happy
- **Role:** test.finance@bebang.ph
- **Depends:** S152-C06
- **Assert:** L1 reviewer → L2 budget → "Pending CFO Approval"

### S152-C08: RFP L3 CFO Approve → Pending CEO (NOT Approved)
- **Type:** happy
- **Role:** sam@bebang.ph
- **Depends:** S152-C07
- **Assert:**
  - cfo_status = "Approved"
  - Status → "Pending CEO Approval" (NOT "Approved" — >1M triggers CEO)
  - DB verify: status="Pending CEO Approval"

### S152-C09: RFP L4 CEO Approve >P1M
- **Type:** happy
- **Role:** sam@bebang.ph (password: 2289454)
- **Depends:** S152-C08
- **Route:** `/dashboard/procurement/payments/[C06.name]`
- **Action:** Approve Level 4 with comment "S152 CEO — P1.4M disbursement authorized"
- **Assert:**
  - ceo_status = "Approved"
  - ceo_approver = sam
  - Status → "Approved"
  - DB verify: ceo_status="Approved", status="Approved"

---

## Rejection & Edge Cases

### S152-R01: PO Rejection by Mae
- **Type:** negative
- **Role:** mae@bebang.ph
- **Action:** Create small PO, submit, Mae rejects with reason "pricing too high"
- **Assert:**
  - Status → "Rejected"
  - rejection_reason = "pricing too high"
  - DB verify: status="Rejected"

### S152-R02: RFP Rejection at Level 2 (Budget)
- **Type:** negative
- **Role:** test.finance@bebang.ph
- **Action:** Create Invoice+RFP, L1 approve, L2 reject with reason "budget exceeded"
- **Assert:**
  - Status → "Rejected"
  - Rejection level and reason recorded
  - DB verify: status="Rejected"

### S152-R03: Partial Goods Receipt
- **Type:** edge
- **Role:** test.warehouse@bebang.ph
- **Action:** Create GR from PO, set accepted_qty = 50% of ordered_qty
- **Assert:**
  - GR accepted
  - PO status → "Partially Received" (NOT "Fully Received")
  - DB verify: PO status="Partially Received"

### S152-R04: Invoice 3-Way Match Variance
- **Type:** edge
- **Role:** test.finance@bebang.ph
- **Action:** Create invoice where amount ≠ PO/GR amount
- **Assert:**
  - match_status = "Variance Detected"
  - Needs variance approval
  - DB verify: match_status="Variance Detected"

### S152-R05: Approve Invoice Variance
- **Type:** edge
- **Role:** test.finance@bebang.ph
- **Depends:** S152-R04
- **Action:** Approve variance with notes "vendor bulk discount"
- **Assert:**
  - Status → "Verified"
  - variance_approved_by set
  - DB verify: status="Verified"

---

## Dashboard Validation

### S152-D01: AP Command Center — Overview KPIs
- **Type:** dashboard
- **Role:** test.finance@bebang.ph
- **Route:** `/dashboard/accounting/ap-command-center`
- **Assert:**
  - 6 KPI cards show non-zero values
  - AP Aging Distribution bars render
  - Outstanding by Supplier list non-empty
  - Cross-check Outstanding total via API

### S152-D02: AP Command Center — Invoices CSV Export
- **Type:** dashboard
- **Role:** test.finance@bebang.ph
- **Route:** `/dashboard/accounting/ap-command-center?tab=invoices`
- **Assert:**
  - CSV export downloads ALL invoices (count ≥ 714)
  - Row count matches API total

### S152-D03: AP Command Center — Aging Matrix
- **Type:** dashboard
- **Role:** test.finance@bebang.ph
- **Route:** `/dashboard/accounting/ap-command-center?tab=aging`
- **Assert:**
  - Multi-supplier grid (NOT single row)
  - Column totals sum correctly
  - Grand total matches Overview Outstanding AP

### S152-D04: AP Command Center — Supplier Ledger
- **Type:** dashboard
- **Role:** test.finance@bebang.ph
- **Route:** `/dashboard/accounting/ap-command-center?tab=supplier-ledger`
- **Assert:**
  - 100+ suppliers in list (NOT 3)
  - Select supplier → timeline loads
  - Timeline shows POs, GRs, Invoices, Payments with correct badges

### S152-D05: AP Payments — Approval Icons
- **Type:** dashboard
- **Role:** test.finance@bebang.ph
- **Route:** `/dashboard/accounting/ap-command-center?tab=payments`
- **Assert:**
  - Chain A RFP: 3 green checks, 1 gray (no CEO)
  - Chain C RFP: 4 green checks (all levels)
  - Rejected RFP: red X at rejection level

### S152-D06: PO List Page Verification
- **Type:** dashboard
- **Role:** test.finance@bebang.ph
- **Route:** `/dashboard/procurement/purchase-orders`
- **Assert:**
  - All S152 POs visible in list
  - Status filters work
  - Pagination works (577+ POs)
  - "Approved" tab populated

### S152-D07: Procurement Dashboard KPIs
- **Type:** dashboard
- **Role:** test.finance@bebang.ph
- **Route:** `/dashboard/procurement`
- **Assert:**
  - KPI cards non-zero
  - Charts render
  - Quick action links functional
