# S194 — data-testid Survey (Phase L0.2)

**Methodology:** `grep -c 'data-testid' app/dashboard/procurement/**/page.tsx` returns **0** for every core procurement page. All rows below are MISSING and must be added in Phase L1.

**Legend:**
- `MISSING` — no `data-testid` attribute present; Phase L1 MUST add it.
- `MISSING-NOOP` — field might not need a test-id (display-only). Skipped.
- `PRESENT` — already has `data-testid` from a prior sprint.

**Naming convention:** `procurement-<entity>-<action>[-<param>]`
Examples: `procurement-pr-submit`, `procurement-po-mae-approve`, `procurement-gr-inspect-reject-all`, `procurement-rfp-or-amount`.

## 1. Purchase Requisition — `app/dashboard/procurement/purchase-requisitions/{new,[id]}/page.tsx`

| # | Element | File | Line (approx) | testid name | Status |
|---|---|---|---|---|---|
| 1 | Department selector | `new/page.tsx` | form top | `procurement-pr-department` | MISSING |
| 2 | Purpose textarea | `new/page.tsx` | form body | `procurement-pr-purpose` | MISSING |
| 3 | Add-item button | `new/page.tsx` | items table | `procurement-pr-add-item` | MISSING |
| 4 | Item code picker (per row) | `new/page.tsx` | items row | `procurement-pr-item-code` (+row idx) | MISSING |
| 5 | Item qty input (per row) | `new/page.tsx` | items row | `procurement-pr-item-qty` (+row idx) | MISSING |
| 6 | Item notes input (per row) | `new/page.tsx` | items row | `procurement-pr-item-notes` (+row idx) | MISSING |
| 7 | Remove-item button (per row) | `new/page.tsx` | items row | `procurement-pr-remove-item` (+row idx) | MISSING |
| 8 | Submit button | `new/page.tsx` | 543 | `procurement-pr-submit` | MISSING |
| 9 | PR name in detail header | `[id]/page.tsx` | header | `procurement-pr-name` | MISSING |
| 10 | Approve button (detail) | `[id]/page.tsx` | actions | `procurement-pr-approve` | MISSING |
| 11 | Reject-open button (detail) | `[id]/page.tsx` | actions | `procurement-pr-reject-open` | MISSING |
| 12 | Reject reason textarea (dialog) | `[id]/page.tsx` | dialog | `procurement-pr-reject-reason` | MISSING |
| 13 | Reject-confirm button (dialog) | `[id]/page.tsx` | dialog | `procurement-pr-reject-confirm` | MISSING |
| 14 | Convert-to-PO button | `[id]/page.tsx` | actions | `procurement-pr-convert-to-po` | MISSING |
| 15 | Status badge | `[id]/page.tsx` | header | `procurement-pr-status-badge` | MISSING |

## 2. Purchase Order — `app/dashboard/procurement/purchase-orders/{new,[id]}/page.tsx`

| # | Element | File | Line (approx) | testid name | Status |
|---|---|---|---|---|---|
| 16 | Supplier picker | `new/page.tsx` | form | `procurement-po-supplier` | MISSING |
| 17 | From-PR picker | `new/page.tsx` | form | `procurement-po-source-pr` | MISSING |
| 18 | Item qty input (per row) | `new/page.tsx` | row | `procurement-po-item-qty` | MISSING |
| 19 | Item price input (per row) | `new/page.tsx` | row | `procurement-po-item-price` | MISSING |
| 20 | Submit (create) button | `new/page.tsx` | bottom | `procurement-po-create` | MISSING |
| 21 | Submit-for-approval button | `[id]/page.tsx` | 517 | `procurement-po-submit-for-approval` | MISSING |
| 22 | Reject-open button | `[id]/page.tsx` | 524 | `procurement-po-reject-open` | MISSING |
| 23 | Mae-approve button | `[id]/page.tsx` | 1015 (role-gated) | `procurement-po-mae-approve` | MISSING |
| 24 | Butch-approve button | `[id]/page.tsx` | ~1015 (role-gated) | `procurement-po-butch-approve` | MISSING |
| 25 | CEO-approve button | `[id]/page.tsx` | ~1015 (role-gated) | `procurement-po-ceo-approve` | MISSING |
| 26 | Reject reason textarea | `[id]/page.tsx` | dialog | `procurement-po-reject-reason` | MISSING |
| 27 | Reject-confirm button | `[id]/page.tsx` | 1059 | `procurement-po-reject-confirm` | MISSING |
| 28 | Send-to-supplier button | `[id]/page.tsx` | 671 | `procurement-po-send-to-supplier` | MISSING |
| 29 | Resend-to-supplier button | `[id]/page.tsx` | 675 | `procurement-po-resend` | MISSING |
| 30 | Status badge | `[id]/page.tsx` | header | `procurement-po-status-badge` | MISSING |
| 31 | PO grand-total display | `[id]/page.tsx` | header | `procurement-po-grand-total` | MISSING |
| 32 | requires_dual_approval badge | `[id]/page.tsx` | header | `procurement-po-dual-approval-badge` | MISSING |

## 3. Goods Receipt — `app/dashboard/procurement/goods-receipts/{new,[id]}/page.tsx`

| # | Element | File | Line (approx) | testid name | Status |
|---|---|---|---|---|---|
| 33 | From-PO picker | `new/page.tsx` | form top | `procurement-gr-source-po` | MISSING |
| 34 | Received qty (per row) | `new/page.tsx` | row | `procurement-gr-received-qty` | MISSING |
| 35 | Rejected qty (per row) | `new/page.tsx` | row | `procurement-gr-rejected-qty` | MISSING |
| 36 | Reject reason (per row) | `new/page.tsx` | row | `procurement-gr-reject-reason` | MISSING |
| 37 | Submit button | `new/page.tsx` | bottom | `procurement-gr-submit` | MISSING |
| 38 | Inspection complete button | `[id]/page.tsx` | actions | `procurement-gr-inspection-complete` | MISSING |
| 39 | Inspection rejected-all button | `[id]/page.tsx` | actions | `procurement-gr-reject-all` | MISSING |
| 40 | GR status badge | `[id]/page.tsx` | header | `procurement-gr-status-badge` | MISSING |
| 41 | Linked PO name | `[id]/page.tsx` | header | `procurement-gr-linked-po` | MISSING |

## 4. Invoice — `app/dashboard/procurement/invoices/{new,[id]}/page.tsx`

| # | Element | File | Line (approx) | testid name | Status |
|---|---|---|---|---|---|
| 42 | From-GR picker | `new/page.tsx` | form | `procurement-invoice-source-gr` | MISSING |
| 43 | Supplier invoice number | `new/page.tsx` | form | `procurement-invoice-supplier-inv-no` | MISSING |
| 44 | Invoice date | `new/page.tsx` | form | `procurement-invoice-date` | MISSING |
| 45 | Grand total | `new/page.tsx` | form | `procurement-invoice-grand-total` | MISSING |
| 46 | Submit button | `new/page.tsx` | bottom | `procurement-invoice-submit` | MISSING |
| 47 | Submit-for-verification button | `[id]/page.tsx` | actions | `procurement-invoice-submit-for-verification` | MISSING |
| 48 | Approve-variance button | `[id]/page.tsx` | actions | `procurement-invoice-approve-variance` | MISSING |
| 49 | Reject-variance button | `[id]/page.tsx` | actions | `procurement-invoice-reject-variance` | MISSING |
| 50 | 3-way match status badge | `[id]/page.tsx` | header | `procurement-invoice-match-badge` | MISSING |
| 51 | Status badge | `[id]/page.tsx` | header | `procurement-invoice-status-badge` | MISSING |

## 5. Payment Request (RFP) — `app/dashboard/procurement/payments/{new,[id]}/page.tsx`

| # | Element | File | Line (approx) | testid name | Status |
|---|---|---|---|---|---|
| 52 | From-Invoice picker | `new/page.tsx` | form | `procurement-rfp-source-invoice` | MISSING |
| 53 | Payment amount input | `new/page.tsx` | form | `procurement-rfp-amount` | MISSING |
| 54 | Payment date input | `new/page.tsx` | form | `procurement-rfp-date` | MISSING |
| 55 | `is_advance_payment` checkbox | `new/page.tsx` | form | `procurement-rfp-is-advance` | MISSING (HARD BLOCKER S194-22) |
| 56 | Submit (create) button | `new/page.tsx` | bottom | `procurement-rfp-create` | MISSING |
| 57 | Submit-for-approval button | `[id]/page.tsx` | 579 | `procurement-rfp-submit` | MISSING |
| 58 | Reject current stage button | `[id]/page.tsx` | 604 | `procurement-rfp-reject-open` | MISSING |
| 59 | Approve current stage button | `[id]/page.tsx` | 609 | `procurement-rfp-approve` | MISSING |
| 60 | Mark-complete button | `[id]/page.tsx` | 637 | `procurement-rfp-mark-complete` | MISSING |
| 61 | Transaction reference input | `[id]/page.tsx` | 637 adj. | `procurement-rfp-txn-ref` | MISSING |
| 62 | Open OR-upload dialog | `[id]/page.tsx` | 1040 | `procurement-rfp-or-open` | MISSING |
| 63 | OR number input | `[id]/page.tsx` | 1029 dialog | `procurement-rfp-or-number` | MISSING |
| 64 | OR date input | `[id]/page.tsx` | 1029 dialog | `procurement-rfp-or-date` | MISSING |
| 65 | OR amount input | `[id]/page.tsx` | 1029 dialog | `procurement-rfp-or-amount` | MISSING |
| 66 | OR attachment file input | `[id]/page.tsx` | 1029 dialog | `procurement-rfp-or-attachment` | MISSING |
| 67 | OR-upload confirm button | `[id]/page.tsx` | 1029 dialog | `procurement-rfp-or-submit` | MISSING |
| 68 | Level-specific tab (review/budget/cfo/ceo) | `[id]/page.tsx` | action panel | `procurement-rfp-tab-<level>` | MISSING |
| 69 | Status badge | `[id]/page.tsx` | header | `procurement-rfp-status-badge` | MISSING |
| 70 | Variance-flag badge (OR > 5%) | `[id]/page.tsx` | footer | `procurement-rfp-variance-badge` | MISSING |

## 6. Approvals queue — `app/dashboard/procurement/approvals/page.tsx` (S194-23 expanded)

| # | Element | File | Line (approx) | testid name | Status |
|---|---|---|---|---|---|
| 71 | Approval row (per PO) | `approvals/page.tsx` | list | `procurement-approvals-row` (+poName) | MISSING |
| 72 | Row-level approve action | `approvals/page.tsx` | row | `procurement-approvals-row-approve` | MISSING |
| 73 | Row-level reject action | `approvals/page.tsx` | row | `procurement-approvals-row-reject` | MISSING |

## 7. Match Exception — `app/dashboard/accounting/exceptions/page.tsx` (L0.4)

| # | Element | File | Line (approx) | testid name | Status |
|---|---|---|---|---|---|
| 74 | Status filter dropdown | `exceptions/page.tsx` | filters | `procurement-ox-status-filter` | MISSING |
| 75 | Exception row | `exceptions/page.tsx` | list | `procurement-ox-row` (+name) | MISSING |
| 76 | Approve-open button | `exceptions/page.tsx` | row | `procurement-ox-approve-open` | MISSING |
| 77 | Reject-open button | `exceptions/page.tsx` | row | `procurement-ox-reject-open` | MISSING |
| 78 | Comment textarea (dialog) | `exceptions/page.tsx` | dialog | `procurement-ox-comment` | MISSING |
| 79 | Approve-confirm button (dialog) | `exceptions/page.tsx` | dialog | `procurement-ox-approve-confirm` | MISSING |

---

## Summary

- **Total rows:** 79 (≥30 required ✔)
- **MISSING:** 79 (100%)
- **PRESENT:** 0

Every row will be added in Phase L1. The approximate line numbers are guides — Phase L1 will open each file, confirm the actual element location, and add the attribute. No existing `data-testid` will be renamed per the plan HARD BLOCKER.

## Phase L1 edit plan

Files to edit in Phase L1 (7 files to touch initially; add additional files only if the survey above is adapted when the actual page is opened):

1. `app/dashboard/procurement/purchase-requisitions/new/page.tsx` (rows 1-8)
2. `app/dashboard/procurement/purchase-requisitions/[id]/page.tsx` (rows 9-15)
3. `app/dashboard/procurement/purchase-orders/new/page.tsx` (rows 16-20)
4. `app/dashboard/procurement/purchase-orders/[id]/page.tsx` (rows 21-32)
5. `app/dashboard/procurement/goods-receipts/new/page.tsx` (rows 33-37)
6. `app/dashboard/procurement/goods-receipts/[id]/page.tsx` (rows 38-41)
7. `app/dashboard/procurement/invoices/new/page.tsx` (rows 42-46)
8. `app/dashboard/procurement/invoices/[id]/page.tsx` (rows 47-51)
9. `app/dashboard/procurement/payments/new/page.tsx` (rows 52-56)
10. `app/dashboard/procurement/payments/[id]/page.tsx` (rows 57-70)
11. `app/dashboard/procurement/approvals/page.tsx` (rows 71-73)
12. `app/dashboard/accounting/exceptions/page.tsx` (rows 74-79)
