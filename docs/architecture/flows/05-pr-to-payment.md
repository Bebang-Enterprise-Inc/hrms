# Flow 05: Purchase Requisition to Payment
**Departments:** Store/Commissary → Procurement → Warehouse (GR) → Finance (Invoice + Payment)
**Scanned:** 2026-02-23 | **Git Commit:** 7b998877f | **Agent:** flow-tracer-2

---

## Flow Diagram (Mermaid) — Part A: PR to Approved PO

```mermaid
sequenceDiagram
    participant Requester as Requester (Store/Commissary)
    participant PRPage as /procurement/purchase-requisitions/new
    participant PRAPI as procurement.create_purchase_requisition()
    participant PR as BEI Purchase Requisition
    participant DeptHead as Department Head
    participant ApprPage as /procurement/approvals
    participant PrApprAPI as procurement.approve_pr()
    participant ProcMgr as Procurement Manager
    participant POPage as /procurement/purchase-requisitions/[id]
    participant ConvertAPI as procurement.convert_pr_to_po()
    participant PO as BEI Purchase Order
    participant SubmitAPI as procurement.submit_po_for_approval()
    participant Mae as CPO (Mae)
    participant MaeAPI as procurement.approve_po_mae()
    participant Butch as CFO (Butch)
    participant ButchAPI as procurement.approve_po_butch()

    Requester->>PRPage: Fill PR form (items, dept, delivery_to)
    PRPage->>PRAPI: POST create_purchase_requisition(data)
    PRAPI->>PR: insert() status=Draft
    Requester->>ApprPage: submit_pr_for_approval(name)
    ApprPage->>PrApprAPI: POST submit_pr_for_approval() → PR.submit_for_approval()
    PR-->>PR: status=Pending Approval
    DeptHead->>ApprPage: Review PR
    ApprPage->>PrApprAPI: POST approve_pr(name) → PR.approve()
    PR-->>PR: status=Approved
    ProcMgr->>POPage: Click "Convert to PO" + select supplier
    POPage->>ConvertAPI: POST convert_pr_to_po(name, supplier) → PR.convert_to_po()
    ConvertAPI->>PO: insert() status=Draft; pr_reference linked
    Note over PO: AUDIT 2.8: TIN check if >250K annual; document warnings
    ProcMgr->>SubmitAPI: submit_po_for_approval(po_name)
    SubmitAPI->>PO: status=Pending Mae Approval
    Mae->>ApprPage: Review pending POs (get_pending_po_approvals)
    ApprPage->>MaeAPI: POST approve_po_mae(name)
    MaeAPI->>PO: mae_approval=1; if grand_total <= 500K → status=Approved
    alt grand_total > 500K
        MaeAPI->>PO: status=Pending Butch Approval
        Butch->>ApprPage: Review
        ApprPage->>ButchAPI: POST approve_po_butch(name)
        ButchAPI->>PO: butch_approval=1; status=Approved
    end
    ProcMgr->>POPage: send_po_to_supplier(name)
    Note over ProcMgr: Email sent to supplier
```

## Flow Diagram (Mermaid) — Part B: GR, Invoice, 3-Way Match, Payment

```mermaid
sequenceDiagram
    participant Supplier as Supplier (delivers goods)
    participant WH as Warehouse Staff
    participant GRPage as /procurement/goods-receipts/new
    participant GRAPI as procurement.create_goods_receipt()
    participant GR as BEI Goods Receipt
    participant QC as QC Inspector
    participant GRInspAPI as procurement.complete_gr_inspection()
    participant Finance as Finance Staff
    participant InvPage as /procurement/invoices/new
    participant InvAPI as procurement.create_invoice()
    participant Inv as BEI Invoice
    participant VerAPI as procurement.verify_invoice_match()
    participant PayPage as /procurement/payments/new
    participant PayAPI as procurement.create_payment_request()
    participant Pay as BEI Payment Request
    participant Reviewer as Finance Reviewer
    participant BudgetMgr as Budget Manager
    participant CFO as CFO (Butch)
    participant CEO as CEO
    participant MarkPaid as procurement.mark_payment_complete()

    Supplier->>WH: Delivers goods against PO
    WH->>GRPage: Create GR linked to PO (load_gr_from_po)
    GRPage->>GRAPI: POST create_goods_receipt(data)
    Note over GRAPI: AUDIT 2.4: Block if >500K PO missing dual approval
    Note over GRAPI: AUDIT 2.2: GR date >= PO date check
    GRAPI->>GR: insert() status=Draft
    WH->>GRPage: submit_goods_receipt(name)
    GRPage->>GRAPI: POST submit_goods_receipt() → GR.submit_receipt()
    GR-->>GR: status=Submitted
    QC->>GRPage: complete_gr_inspection(name, passed=True/False)
    GRPage->>GRInspAPI: POST complete_gr_inspection() → GR.complete_inspection()
    GR-->>GR: status=Accepted or Rejected
    Finance->>InvPage: Create Invoice linked to GR + PO
    InvPage->>InvAPI: POST create_invoice(data)
    Note over InvAPI: AUDIT 2.1: GR required (or Match Exception approved)
    Note over InvAPI: AUDIT 2.2: Invoice date >= PO date
    Note over InvAPI: AUDIT 2.4: >500K PO needs dual approval
    GRAPI->>Inv: insert() status=Draft
    Finance->>InvPage: submit_invoice_for_verification()
    InvPage->>VerAPI: POST submit_invoice_for_verification() → status=Pending Verification
    Finance->>InvPage: verify_invoice_match() — 3-way match
    InvPage->>VerAPI: POST verify_invoice_match() → Inv.verify_match()
    alt Match within tolerance
        Inv-->>Inv: status=Verified, match_status=Matched
    else Variance found
        Inv-->>Inv: match_status=Variance
        Finance->>InvPage: approve_invoice_variance() or reject_invoice_variance()
    end
    Finance->>PayPage: Create Payment Request linked to Invoice
    PayPage->>PayAPI: POST create_payment_request(data)
    Note over PayAPI: AUDIT 2.1: GR check; 2.2: date sequence; 2.3: <= received_value; 2.4: dual approval; 2.5: advance guard
    PayAPI->>Pay: insert() status=Pending Review; auto-set ceo_required if new supplier or >1M
    Reviewer->>ApprPage: approve_payment_review()
    Pay-->>Pay: status=Pending Budget Approval
    BudgetMgr->>ApprPage: approve_payment_budget()
    Pay-->>Pay: status=Pending CFO Approval
    CFO->>ApprPage: approve_payment_cfo()
    Pay-->>Pay: status=Pending CEO Approval (if ceo_required) or Approved
    alt ceo_required=1
        CEO->>ApprPage: approve_payment_ceo()
        Pay-->>Pay: status=Approved
    end
    Finance->>PayPage: mark_payment_complete(name, payment_reference)
    PayPage->>MarkPaid: POST mark_payment_complete()
    MarkPaid->>Pay: status=Paid; frappe_payment_entry linked
    Note over MarkPaid: If ewt_amount > 0 → auto-generate EWT Journal Entry
    Finance->>ORPage: upload_official_receipt(name, or_photo)
    Note over Finance: If variance <= 5% → auto-close; >5% → flag for review
```

---

## Step-by-Step Trace

| Step | Actor | Action | Frontend Page | API Endpoint | DocType Created/Updated | Status |
|------|-------|--------|---------------|-------------|------------------------|--------|
| 1 | Requester | Create Purchase Requisition | `/procurement/purchase-requisitions/new` | `procurement.create_purchase_requisition(data)` | BEI Purchase Requisition (Draft) + BEI PR Item | LIVE |
| 2 | Requester | Submit PR for approval | `/procurement/purchase-requisitions/[id]` | `procurement.submit_pr_for_approval(name)` → `PR.submit_for_approval()` | BEI Purchase Requisition (Pending Approval) | LIVE |
| 3 | Department Head | Review + approve PR | `/procurement/approvals` | `procurement.approve_pr(name)` → `PR.approve()` | BEI Purchase Requisition (Approved) | LIVE |
| 3a | (Alternative) | Reject PR | `/procurement/approvals` | `procurement.reject_pr(name, reason)` → `PR.reject()` | BEI Purchase Requisition (Rejected) | LIVE |
| 4 | Procurement Mgr | Convert approved PR to PO + select supplier | `/procurement/purchase-requisitions/[id]` | `procurement.convert_pr_to_po(name, supplier)` → `PR.convert_to_po()` | BEI Purchase Order (Draft) linked to BEI Purchase Requisition | LIVE |
| 4a | System | AUDIT 2.8: TIN check + document warnings | (inline in create_purchase_order/convert) | `procurement.create_purchase_order()` validation | BEI Supplier (read) | LIVE |
| 5 | Procurement Mgr | Submit PO for Mae's approval | `/procurement/purchase-orders/[id]` | `procurement.submit_po_for_approval(name)` → `PO.submit_for_approval()` | BEI Purchase Order (Pending Mae Approval) | LIVE |
| 6 | CPO (Mae) | Review PO approval queue | `/procurement/approvals` | `procurement.get_pending_po_approvals()` | BEI Purchase Order (read) | LIVE |
| 7 | CPO (Mae) | Approve PO (≤500K → final approval) | `/procurement/approvals` | `procurement.approve_po_mae(name)` → `PO.approve_mae()` | BEI Purchase Order (Approved OR Pending Butch Approval) | LIVE |
| 8 | CFO (Butch) | Approve PO (>500K dual approval) | `/procurement/approvals` | `procurement.approve_po_butch(name)` → `PO.approve_butch()` | BEI Purchase Order (Approved) | LIVE |
| 8a | (Alternative) | Either approver rejects PO | `/procurement/approvals` | `procurement.reject_po(name, reason, rejector)` → `PO.reject()` | BEI Purchase Order (Rejected) | LIVE |
| 9 | Procurement Mgr | Send PO to supplier via email | `/procurement/purchase-orders/[id]` | `procurement.send_po_to_supplier(name)` → `PO.send_to_supplier()` | BEI Purchase Order (Sent) | LIVE |
| 10 | Warehouse Staff | Create Goods Receipt from PO | `/procurement/goods-receipts/new` | `procurement.create_goods_receipt(data)` | BEI Goods Receipt (Draft) + BEI GR Item | LIVE |
| 10a | System | AUDIT 2.4: Block GR if >500K PO missing dual approval | (inline in create_goods_receipt) | — | BEI Purchase Order (read) | LIVE |
| 10b | System | AUDIT 2.2: Date sequence check (GR date >= PO date) | (inline) | — | — | LIVE |
| 10c | Warehouse | Load GR items from PO | `/procurement/goods-receipts/[id]` | `procurement.load_gr_from_po(name, purchase_order)` → `GR.load_from_po()` | BEI GR Item populated | LIVE |
| 11 | Warehouse Staff | Submit Goods Receipt | `/procurement/goods-receipts/[id]` | `procurement.submit_goods_receipt(name)` → `GR.submit_receipt()` | BEI Goods Receipt (Submitted) | LIVE |
| 12 | QC Inspector | Complete quality inspection (pass/fail) | `/procurement/goods-receipts/[id]` | `procurement.complete_gr_inspection(name, passed, notes)` → `GR.complete_inspection()` | BEI Goods Receipt (Accepted or Rejected) | LIVE |
| 13 | Finance Staff | Create Invoice linked to GR + PO | `/procurement/invoices/new` | `procurement.create_invoice(data)` | BEI Invoice (Draft) | LIVE |
| 13a | System | AUDIT 2.1: GR required check (or approved Match Exception) | (inline) | `procurement.create_invoice()` | BEI Match Exception (read) | LIVE |
| 13b | System | AUDIT 2.2: Invoice date >= PO date check | (inline) | — | — | LIVE |
| 13c | System | AUDIT 2.4: >500K PO dual approval check | (inline) | — | — | LIVE |
| 14 | Finance Staff | Submit invoice for 3-way match verification | `/procurement/invoices/[id]` | `procurement.submit_invoice_for_verification(name)` → `Inv.submit_for_verification()` | BEI Invoice (Pending Verification) | LIVE |
| 15 | Finance Staff | Verify 3-way match (PO vs GR vs Invoice) | `/procurement/invoices/[id]` | `procurement.verify_invoice_match(name)` → `Inv.verify_match()` | BEI Invoice (Verified / Variance) | LIVE |
| 15a | Finance (variance) | Approve invoice variance | `/procurement/invoices/[id]` | `procurement.approve_invoice_variance(name, notes)` | BEI Invoice (Verified) | LIVE |
| 15b | Finance (variance) | Reject invoice variance | `/procurement/invoices/[id]` | `procurement.reject_invoice_variance(name, reason)` | BEI Invoice (Rejected) | LIVE |
| 15c | Finance (no GR) | Request 3-way match exception | `/procurement/invoices/[id]` | `procurement.request_match_exception(...)` | BEI Match Exception (Pending CPO/CFO/CEO) | LIVE |
| 15d | CPO/CFO/CEO | Approve/reject match exception | `/dashboard/accounting/exceptions` | `procurement.approve_match_exception` / `reject_match_exception` | BEI Match Exception (Approved/Rejected) | LIVE |
| 16 | Finance Staff | Create Payment Request linked to Invoice | `/procurement/payments/new` | `procurement.create_payment_request(data)` | BEI Payment Request (Pending Review) | LIVE |
| 16a | System | AUDIT 2.1–2.5: All guards (GR, dates, received value, dual approval, advance guard) | (inline in create_payment_request) | — | Multiple DocTypes (read) | LIVE |
| 16b | System | Auto-set ceo_required=1 if new supplier or payment >₱1M | (inline) | — | BEI Payment Request | LIVE |
| 17 | Finance Reviewer | Approve at Review level | `/procurement/approvals` | `procurement.approve_payment_review(name)` | BEI Payment Request (Pending Budget Approval) | LIVE |
| 18 | Budget Manager | Approve at Budget level | `/procurement/approvals` | `procurement.approve_payment_budget(name)` | BEI Payment Request (Pending CFO Approval) | LIVE |
| 19 | CFO (Butch) | Approve at CFO level | `/procurement/approvals` | `procurement.approve_payment_cfo(name)` | BEI Payment Request (Pending CEO Approval or Approved) | LIVE |
| 20 | CEO | Approve at CEO level (new supplier or >₱1M) | `/procurement/approvals` | `procurement.approve_payment_ceo(name)` | BEI Payment Request (Approved) | LIVE |
| 21 | Finance Staff | Mark payment complete (with payment reference) | `/procurement/payments/[id]` | `procurement.mark_payment_complete(name, ...)` | BEI Payment Request (Paid) + Journal Entry (EWT if applicable) | LIVE — EWT JV has wrong AP account (P-G07) |
| 22 | Finance Staff | Upload Official Receipt | `/procurement/or-follow-up` | `procurement.upload_official_receipt(name, or_photo)` | BEI Payment Request (Paid or Paid-Awaiting OR or Closed) | LIVE |
| 22a | (Daily scheduler) | Check overdue invoices (missing OR) | (scheduler) | `procurement.check_overdue_invoices` | BEI Payment Request (read) | LIVE |

---

## Handoff Points

| From Dept | To Dept | Trigger | Mechanism | Status |
|-----------|---------|---------|-----------|--------|
| Requester | Dept Head / Procurement | PR status → Pending Approval | `submit_pr_for_approval()` updates status; approver sees in `/procurement/approvals` queue | LIVE — no GChat notification to approver |
| Procurement | CPO (Mae) | PO status → Pending Mae Approval | `submit_po_for_approval()` updates status; Mae sees in approval queue | LIVE — no GChat notification |
| CPO (Mae) | CFO (Butch) | PO value >500K: status → Pending Butch Approval | `approve_po_mae()` → `PO.approve_mae()` sets status | LIVE — no GChat notification |
| Approved PO | Supplier | PO sent via email | `send_po_to_supplier()` → `PO.send_to_supplier()` | LIVE |
| Supplier | Warehouse | Physical delivery triggers GR creation | Manual: warehouse creates GR in `/procurement/goods-receipts/new` | LIVE — no system trigger from PO to warehouse |
| Warehouse (GR) | Finance | GR accepted → Finance creates invoice | Finance navigates to `/procurement/invoices/new`; no automatic handoff | LIVE — manual; no GChat notification |
| Finance (Invoice) | Finance (Payment) | Invoice verified → Payment Request created | Finance navigates to `/procurement/payments/new`; links invoice | LIVE — manual; no automatic trigger |
| Finance (Payment Review) | Budget Manager | `approve_payment_review()` → status changes | Budget Mgr checks approval queue | LIVE — no GChat notification |
| Budget Manager | CFO | `approve_payment_budget()` → status changes | CFO checks approval queue | LIVE — no GChat notification |
| CFO | CEO (conditional) | `approve_payment_cfo()` → status=Pending CEO if ceo_required | CEO checks approval queue | LIVE — GChat notification sent on Match Exception CEO approval (different flow); not confirmed for payment |
| Finance | Accounting | OR uploaded → OR follow-up resolved | `upload_official_receipt()` updates status; daily check via `check_overdue_invoices` | LIVE — `send_or_follow_up` sends NO actual notification to supplier (P-G10) |

---

## Broken Links / Gaps

| ID | Location | Problem | Impact | Severity |
|----|----------|---------|--------|----------|
| BL-05-01 | Entire PR → PO → GR → Invoice → Payment chain | No GChat notifications at any handoff point (PR submitted, PR approved, PO submitted, PO approved, GR accepted, Invoice verified, Payment approved) | Each department must poll the approval queue; no push notifications means delays go undetected | HIGH |
| BL-05-02 | `procurement.mark_payment_complete()` EWT JV | Uses hardcoded `2101001 - ACCOUNTS PAYABLE-OTHERS` instead of `2101101 - ACCOUNTS PAYABLE - TRADE` used by `billing.py`; party set on BOTH JV rows (violates DM-1 — party should only be on AP row) | Incorrect GL account for EWT JV; party mapping violation creates reconciliation errors | MEDIUM |
| BL-05-03 | `BEI Purchase Order` DocType | Not submittable (`is_submittable=0`); approval via custom status field only; approved POs can be edited post-approval without docstatus protection | Procurement fraud risk: PO items can be modified after Mae/Butch approval; no audit trail | HIGH |
| BL-05-04 | `procurement.send_or_follow_up()` | Function increments counter and logs a comment but sends NO email or Google Chat to supplier | Supplier never receives follow-up; only internal comment is recorded despite FE showing "Send Follow-up" button | MEDIUM |
| BL-05-05 | `check_overdue_or` scheduler | `check_overdue_or` function exists in procurement.py but registration in `hooks.py` daily scheduler not confirmed | OR escalation may silently not fire; overdue ORs go unescalated | HIGH — needs verification |
| BL-05-06 | `procurement.get_single_source_suppliers()` | AUDIT 2.7 backend implemented (>80% concentration risk by supplier) but no frontend page exists | Internal Audit Jan 30 finding (RIGHT GOODS ₱23.6M) is unmonitored from UI | HIGH |
| BL-05-07 | `procurement.generate_form_2307_entry()` | Form 2307 EWT certificate data stored as JSON string in `tabComment` body — not a proper DocType; no PDF generation | Not searchable, no PDF for BIR submission, fragile string parsing; data integrity risk | HIGH |
| BL-05-08 | `procurement.get_advance_subsidiary_ledger()` | Queries `pr.supplier_name = %(supplier)s` but `get_outstanding_advances()` uses `supplier` (ID); inconsistent parameter meaning | Supplier drill-down from outstanding advances returns wrong data if supplier ID passed | MEDIUM |
| BL-05-09 | G-046 inter-company invoice | No procurement module page shows inter-company invoice status; G-046 lives in commissary.py | Procurement team cannot audit inter-company transactions from procurement module | HIGH |
| BL-05-10 | GR → Frappe Purchase Receipt link | `BEI Goods Receipt` has `frappe_purchase_receipt` link field; `create_goods_receipt()` does NOT create a standard Frappe Purchase Receipt | Frappe stock ledger is not updated on GR acceptance; inventory levels in ERPNext remain incorrect unless done separately | MEDIUM |
| BL-05-11 | `procurement.check_price_variance()` AUDIT 2.6 | Endpoint exists and blocks >10% price variance, but FE wiring on PO item entry is not confirmed from scan | Price variance guard may not fire on PO creation if frontend doesn't call it on item line entry | LOW |

---

## Error Paths

| Trigger | What Happens | User Experience | Status |
|---------|-------------|----------------|--------|
| PR rejected by dept head | `PR.reject(reason)` sets status=Rejected | Requester sees PR as Rejected; no notification sent | LIVE — no push notification |
| PO rejected by Mae or Butch | `PO.reject(reason, rejector)` sets status=Rejected | PO status shows Rejected; no notification to Procurement Mgr | LIVE — no push notification |
| GR created for >500K PO without dual approval | `frappe.throw()`: "Cannot create GR: PO {no} requires CFO (Butch) approval first" | Warehouse staff sees error; GR not created | LIVE |
| GR date < PO date | `frappe.throw()`: "GR date cannot be earlier than PO date" | Warehouse staff sees date sequence error | LIVE |
| Invoice created without GR and no approved exception | Returns `{success: False, requires_exception: True}` | FE shows exception request prompt; invoice NOT created | LIVE |
| Invoice date < PO date | `frappe.throw()`: "Invoice date cannot be earlier than PO date" | Finance staff sees date sequence error | LIVE |
| Payment amount exceeds received value (AUDIT 2.3) | `frappe.throw()`: "Payment amount exceeds received value" | Finance staff sees partial delivery control error | LIVE |
| Payment for PO fully covered by outstanding advance | `frappe.throw()`: "This PO is fully covered by an outstanding advance payment" | Finance staff sees duplicate payment blocked message | LIVE |
| OR variance >5% after upload | `upload_official_receipt()` flags for review instead of closing | Finance staff sees payment flagged for review; `send_or_follow_up` sends NO outbound notification | LIVE — partial |
| Invoice variance approved but wrong account in EWT JV | `mark_payment_complete()` creates JV with wrong GL account | Accounting journal entry posted to AP-Others instead of AP-Trade; no user-facing error | LIVE — silent accounting bug |
| QC inspection fails (passed=False) | `GR.complete_inspection(False, notes)` sets status=Rejected | GR marked Rejected; PO items not marked as received; manual re-GR needed | LIVE |

---

## Improvement Suggestions

1. **BL-05-01 (HIGH):** Add Google Chat notifications at each major approval handoff: PR submitted/approved, PO submitted/approved per level, GR accepted, Invoice verified. Use the existing `google_chat.send_message_to_space` pattern with procurement-specific space.

2. **BL-05-03 (HIGH):** Set `is_submittable=1` on BEI Purchase Order DocType. Submit on final approval (Mae for ≤500K, Butch for >500K). Require amendment for any post-approval item changes. This provides docstatus audit trail.

3. **BL-05-02 (MEDIUM):** Fix EWT JV in `mark_payment_complete()`: change AP account from `2101001` to `2101101`; remove `party` from the EWT/Withholding Tax row (DM-1 compliance — party only on the AP row).

4. **BL-05-05 (HIGH):** Verify and add `hrms.api.procurement.check_overdue_or` to `hooks.py` `scheduler_events.daily` list. Search hooks.py to confirm current registration status.

5. **BL-05-06 (HIGH):** Add `/procurement/audit/single-source/page.tsx` frontend page wired to `get_single_source_suppliers` — list suppliers with >80% concentration per item, ranked by annual spend.

6. **BL-05-07 (HIGH):** Create `BEI Form 2307` DocType with proper fields (supplier, period, ewt_amount, tax_type, certificate_no); add Frappe print format for PDF generation. Remove `tabComment` JSON storage.

7. **BL-05-10 (MEDIUM):** When `submit_goods_receipt()` is called, also create and submit a standard Frappe `Purchase Receipt` to update stock ledger entries. Link via `frappe_purchase_receipt` field already present on BEI GR.

8. **PO Close workflow:** Add `close_purchase_order` endpoint and "Close PO" action on PO detail page. Status → Closed when all GRs accepted and all invoices paid.
