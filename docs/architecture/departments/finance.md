---
**Last Scanned:** 2026-02-23 | **Previous Scan:** 2026-02-17
**Commit:** 7b998877f | **Health Score:** 100% LIVE (all functions use real DB calls)
---

# Department Feature Matrix: Finance & Accounting

## Summary

- Frontend pages: 13 (accounting: 8, billing: 5, reports: 1 task-only)
- Backend endpoints: 42 LIVE (expense_review.py: 8, billing.py: 18, soa.py: 3, procurement.py accounting section: 13)
- DocTypes: 9 (BEI Invoice, BEI Payment Request, BEI Billing Schedule, BEI Billing Line Item, BEI Statement of Account, BEI SOA Line Item, BEI Match Exception, BEI Acknowledgement Receipt, BEI Delivery Rate)
- Health Score: 100% LIVE — no stubs
- Scheduler: `scheduled_monthly_billing` runs at 6 AM on 1st of each month

## Feature Matrix

| Feature | Frontend Page | FE Status | Backend API | BE Status | Notes |
|---------|--------------|-----------|-------------|-----------|-------|
| Accounting Dashboard | `/dashboard/accounting` | LIVE | `expense_review.get_review_dashboard` | LIVE | |
| Expense List | `/dashboard/accounting/expenses` | LIVE | `expense_review.get_pending_review` | LIVE | |
| Expense Detail | `/dashboard/accounting/expenses/[id]` | LIVE | `expense_review.get_expense_detail` | LIVE | 3-way: manual vs OCR vs match |
| Expense Review | `/dashboard/accounting/expenses/review` | LIVE | `expense_review.approve_expense`, `reject_expense` | LIVE | |
| Batch Approve | `/dashboard/accounting/expenses/batch` | LIVE | `expense_review.batch_approve` | LIVE | |
| Awaiting OR Dashboard | `/dashboard/accounting/awaiting-or` | LIVE | `procurement.get_awaiting_or_list`, `get_or_aging_summary` | LIVE | |
| Match Exceptions Queue | `/dashboard/accounting/exceptions` | LIVE | `procurement.get_match_exceptions`, `approve_match_exception` | LIVE | CPO/CFO/CEO tiers |
| Outstanding Advances | `/dashboard/accounting/outstanding-advances` | LIVE | `procurement.get_outstanding_advances`, `get_advance_aging_summary` | LIVE | |
| Billing List | `/dashboard/billing` | LIVE | `billing.get_billing_list` | LIVE | |
| Billing Detail | `/dashboard/billing/my-billings/[id]` | LIVE | `billing.get_billing_detail` | LIVE | |
| Billing Approval | `/dashboard/billing/approval` | LIVE | `billing.get_pending_billings`, `approve_billing`, `reject_billing` | LIVE | Pending→Approved→Sent→Paid |
| Delivery Rate Management | `/dashboard/billing/rates` | LIVE | `billing.get_delivery_rates`, `set_delivery_rate`, `approve_rate` | LIVE | Draft→Pending Review→Active |
| Statement of Account | — | MISSING | `soa.generate_soa`, `get_soa_list`, `send_soa_to_store` | LIVE | **GAP-013: zero frontend** |
| 3PL Rate Lookup | — | MISSING | `billing.get_3pl_rates` | LIVE | **GAP-014** |
| 3PL Reconciliation | — | MISSING | `billing.generate_3pl_reconciliation` | LIVE | **GAP-014** |
| 3PL Payment Request (JV) | — | MISSING | `billing.create_3pl_payment_request` | LIVE | **GAP-014; GAP-089: duplicate JE possible** |
| AP Aging Report | (widget only) | PARTIAL | `procurement.get_ap_aging_report`, `get_supplier_aging` | LIVE | **GAP-047: no dedicated page** |
| Form 2307 EWT Certificate | — | MISSING | `procurement.generate_form_2307_entry` | LIVE | **GAP-015: data in tabComment, no PDF** |
| Franchise Payment Apply | `/dashboard/billing/my-billings/[id]` | LIVE | `procurement.apply_franchise_payment` | LIVE | FIFO invoice application; auto-generates AR |
| Monthly Billing Auto-generate | Scheduled only | N/A | `billing.scheduled_monthly_billing` | LIVE | 1st of month 6AM cron |
| Finance Reports | `/dashboard/reports` | PARTIAL (tasks only) | — | N/A | **GAP-079: no billing/AP/expense reports** |
| Monthly billing trigger | — | NOT BUILT | `billing.generate_monthly_billing` | LIVE | **GAP-090: no manual trigger UI** |

## DocType Relationships

| DocType | Link Fields | Child Tables | Submittable? |
|---------|-------------|-------------|--------------|
| BEI Invoice | supplier→BEI Supplier, purchase_order→BEI Purchase Order, frappe_purchase_invoice→Purchase Invoice | None | No |
| BEI Payment Request | supplier→BEI Supplier, invoice→BEI Invoice, frappe_payment_entry→Payment Entry | None | No |
| BEI Billing Schedule | store→Department, trip_reference→BEI Distribution Trip | line_items (BEI Billing Line Item) | No |
| BEI Statement of Account | store→Department | line_items (BEI SOA Line Item) | **Yes** |
| BEI Match Exception | purchase_order→BEI Purchase Order, requested_by→User | None | No |
| BEI Acknowledgement Receipt | billing_schedule→BEI Billing Schedule, store→Department | None | No |
| BEI Delivery Rate | store→Department, set_by→User | None | No |

## Gaps Found

| ID | Feature | Blocker Type | Severity | Notes |
|----|---------|-------------|----------|-------|
| GAP-013 | SOA: 3 endpoints, zero frontend | Frontend | High | Finance cannot generate SOA from app |
| GAP-014 | 3PL Billing: 5+ endpoints, zero frontend | Frontend | High | No 3PL billing UI |
| GAP-015 | Form 2307 in tabComment | Architecture | High | Not searchable, no PDF for BIR |
| GAP-021 | Monthly billing queries docstatus=1 on non-submittable DocType | Bug | High | Billing schedule returns empty if query uses docstatus |
| GAP-047 | AP Aging: no dedicated page | Frontend | Medium | Buried in dashboard widget |
| GAP-048 | OR Follow-up: no notification sent | Bug | Medium | Only comment logged; supplier never notified |
| GAP-078 | doc_events not wired to BEI billing | Automation | Medium | Payment Entry lifecycle not linked to BEI Payment Request |
| GAP-079 | Finance reports frontend missing | Frontend | Medium | /dashboard/reports has tasks only |
| GAP-089 | 3PL JE idempotency: duplicate JE possible | Bug | Medium | No check for existing JE for same period+partner |
| GAP-090 | Monthly billing: no manual trigger UI | Frontend | Medium | Finance cannot re-run billing for corrected period |

## Improvements

| Feature | Current State | Suggested Improvement | Priority |
|---------|--------------|----------------------|----------|
| Form 2307 storage | JSON in tabComment | Create BEI Form 2307 DocType with PDF print format | HIGH |
| SOA frontend | Backend complete, no frontend | Add /dashboard/billing/soa/ pages | HIGH |
| 3PL billing frontend | All endpoints built, no UI | Add /dashboard/billing/3pl/ module | HIGH |
| doc_events for BEI billing | Payment Entry hooks call upstream expense_claim | Add BEI Payment Request on_update handler | MEDIUM |
| AP aging dedicated page | Buried in widgets | Add /dashboard/accounting/ap-aging/ with per-supplier drill-down | MEDIUM |
