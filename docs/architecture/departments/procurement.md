---
**Last Scanned:** 2026-02-23 | **Previous Scan:** 2026-02-17
**Commit:** 7b998877f | **Health Score:** 100% LIVE
---

# Department Feature Matrix: Procurement

## Summary

- Frontend pages: 33 (procurement/ directory)
- Backend endpoints: 81 @frappe.whitelist() functions in procurement.py (4,232 lines)
- DocTypes: 12 (BEI Supplier, BEI Purchase Requisition, BEI PR Item, BEI Purchase Order, BEI PO Item, BEI Goods Receipt, BEI GR Item, BEI Invoice, BEI Payment Request, BEI Match Exception, BEI Acknowledgement Receipt, BEI Delivery Rate)
- Health Score: 100% LIVE
- Sprint 09: PO Aging + Price History audit pages now live

## Feature Matrix

| Feature | Frontend Page | FE Status | Backend API | BE Status | Notes |
|---------|--------------|-----------|-------------|-----------|-------|
| Procurement Dashboard | `/procurement` | LIVE | `get_dashboard_kpis`, `get_outstanding_by_supplier`, `get_monthly_po_trend` | LIVE | |
| Supplier List/Create/Edit | `/procurement/suppliers/...` | LIVE | `get_suppliers`, `create_supplier`, `update_supplier` | LIVE | Hard-block on bank/TIN duplicates |
| PR List/Create/Approval | `/procurement/purchase-requisitions/...` | LIVE | `create_purchase_requisition`, `approve_pr`, `reject_pr` | LIVE | |
| PO List/Create | `/procurement/purchase-orders/...` | LIVE | `create_purchase_order`, `get_purchase_orders` | LIVE | **GAP-016: NOT submittable; approved POs editable** |
| PO Approval (Mae ≤500K / Butch >500K) | `/procurement/approvals` | LIVE | `approve_po_mae`, `approve_po_butch` | LIVE | |
| GR List/Create/Submit/Inspect | `/procurement/goods-receipts/...` | LIVE | `create_goods_receipt`, `submit_goods_receipt`, `complete_gr_inspection` | LIVE | |
| Invoice List/Create/3-Way Match | `/procurement/invoices/...` | LIVE | `create_invoice`, `submit_invoice_for_verification`, `verify_invoice_match` | LIVE | |
| Payment Request List/Create | `/procurement/payments/...` | LIVE | `create_payment_request` | LIVE | Full guard: GR check, date, dual approval, double-payment guard |
| Payment 4-Level Approval | `/procurement/approvals` | LIVE | `approve_payment_review`, `approve_payment_budget`, `approve_payment_cfo`, `approve_payment_ceo` | LIVE | CEO for new supplier or >1M |
| Mark Payment Complete | `/procurement/payments/[id]` | LIVE | `mark_payment_complete` | LIVE | **GAP-041: wrong AP account (2101001 vs 2101101); DM-1 violation** |
| OR Upload + Follow-up | `/procurement/or-follow-up` | LIVE | `upload_official_receipt`, `send_or_follow_up` | LIVE | **GAP-048: send_or_follow_up sends nothing; only logs comment** |
| Match Exception Approval | `/procurement/approvals` | LIVE | `approve_match_exception`, `reject_match_exception` | LIVE | Multi-tier routing |
| Advance Payment Tracking | `/dashboard/accounting/outstanding-advances` | LIVE | `tag_advance_to_gr`, `get_outstanding_advances`, `get_advance_subsidiary_ledger` | LIVE | **GAP-043: supplier_name vs supplier ID mismatch** |
| Supplier Performance Report | `/procurement/reports/supplier-performance` | LIVE | `get_supplier_performance_report` | LIVE | |
| PO Aging (Sprint 09) | `/procurement/audit/aging` | LIVE | `get_open_po_aging` | LIVE | New in Sprint 09 |
| Price History (Sprint 09) | `/procurement/audit/price-history` | LIVE | `get_price_history`, `check_price_variance` | LIVE | >5% variance alerts; >10% blocks at PO creation |
| Single Source Supplier | — | MISSING | `get_single_source_suppliers` | LIVE | **GAP-017: no frontend; ₱23.6M audit finding** |
| Supplier Duplicates/Quality | Partial (buried in settings) | PARTIAL | `get_supplier_duplicates`, `get_supplier_data_quality` | LIVE | **GAP-077: no dedicated audit page** |
| G-046 Inter-company Invoice | No procurement FE | NOT IN PROCUREMENT | `commissary._create_intercompany_invoices_async` | LIVE | **GAP-042: invisible from procurement module** |

## DocType Relationships

| DocType | Link Fields | Child Tables | Submittable? |
|---------|-------------|-------------|--------------|
| BEI Supplier | frappe_supplier→Supplier, payment_terms→Payment Terms Template | None | No |
| BEI Purchase Requisition | requested_by→User, department→Department, delivery_to→Warehouse | items (BEI PR Item) | No |
| BEI Purchase Order | pr_reference→BEI Purchase Requisition, supplier→BEI Supplier, ship_to→Warehouse, frappe_po→Purchase Order | items (BEI PO Item) | **No (GAP-016)** |
| BEI Goods Receipt | purchase_order→BEI Purchase Order, supplier→BEI Supplier, warehouse→Warehouse | items (BEI GR Item) | No |
| BEI Invoice | supplier→BEI Supplier, purchase_order→BEI Purchase Order, frappe_purchase_invoice→Purchase Invoice | None | No |
| BEI Payment Request | supplier→BEI Supplier, invoice→BEI Invoice, frappe_payment_entry→Payment Entry | None | No |
| BEI Match Exception | purchase_order→BEI Purchase Order, requested_by→User | None | No |

## Gaps Found

| ID | Feature | Blocker Type | Severity | Notes |
|----|---------|-------------|----------|-------|
| GAP-016 | BEI Purchase Order not submittable | Architecture | High | Procurement fraud risk; approved POs editable |
| GAP-017 | Single Source Supplier: no frontend | Frontend | High | ₱23.6M audit finding unmonitored from UI |
| GAP-018 | Form 2307: no DocType (duplicate of GAP-015) | Architecture | High | |
| GAP-041 | EWT JV wrong AP account | Bug | Medium | 2101001 vs 2101101; DM-1 violation |
| GAP-042 | G-046 not visible in Procurement | Integration | High | Procurement cannot audit inter-company transactions |
| GAP-043 | Advance ledger supplier name/ID mismatch | Bug | Medium | Drill-down returns wrong data |
| GAP-077 | Supplier duplicates/quality: no dedicated page | Frontend | Medium | |

## Improvements

| Feature | Current State | Suggested Improvement | Priority |
|---------|--------------|----------------------|----------|
| PO submittable enforcement | is_submittable=0 | Set is_submittable=1; submit on Mae approval | HIGH |
| G-046 procurement visibility | Silent async; not in procurement module | Add inter-company invoice tab on PO/GR detail | HIGH |
| Single Source Supplier UI | Backend live; no frontend | Add /procurement/audit/single-source/page.tsx | HIGH |
| EWT JV account fix | Wrong account + DM-1 violation | Fix account to 2101101; remove party from EWT row | MEDIUM |
