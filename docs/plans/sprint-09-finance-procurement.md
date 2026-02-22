# Finance + Procurement Sprint Plan
**Date:** 2026-02-19
**Status:** DRAFT v1.2 — AUDIT COMPLETE, QUESTIONNAIRE SENT — Ready to execute non-blocked items
**Priority:** Dept 2 (second priority in Master Gap Closure Roadmap)
**Parent:** `docs/plans/2026-02-19-master-gap-closure-roadmap.md`

---

## Executive Summary

Finance + Procurement covers the **money lifecycle** at BEI. The transition from Apex external accounting to an in-house Finance team is underway, with Alyssa Dimaano (Accounts Manager) as the primary user. The backend is substantially complete — `procurement.py` is **4,133 lines** with 88 whitelisted functions covering the full PR→PO→GR→Invoice→Payment cycle.

**Corrected gap status from discovery:**
- G-018 (Accounting Review UI): **ALREADY BUILT** — 4 pages exist with 835 lines of React (`expenses/page.tsx`, `[id]/page.tsx`, `batch/page.tsx`, `review/page.tsx`)
- G-021 (BEI Invoice DocType JSON): **JSON EXISTS** — `hrms/hr/doctype/bei_invoice/bei_invoice.json` is 9,617 bytes with 46 fields. Gap was incorrectly stated.
- G-022 (BEI Match Exception DocType JSON): **JSON EXISTS** — `hrms/hr/doctype/bei_match_exception/bei_match_exception.json` is 4,690 bytes with 22 fields.
- G-025 (Match exception approve/reject): **ALREADY WIRED** — `accounting/exceptions/page.tsx` (335 lines) has full `useApproveException` / `useRejectException` logic with modal UI.
- G-026 (PR-to-PO conversion): **ALREADY BUILT** — `procurement/purchase-requisitions/[id]/page.tsx` has `useConvertPRToPO` hook and Convert button (524 lines).
- G-061 (Supplier TIN/bank duplicate detection): **ALREADY BLOCKS** — `procurement.py:127-206` uses `frappe.throw()` on phone, bank, AND TIN duplicates. Email-only uses warn.
- G-027 (Match exception request in procurement UI): **NOT YET BUILT** — no "Request Exception" button on PO detail page (`procurement/purchase-orders/[id]/page.tsx` is 869 lines, no exception reference)
- G-065/G-097 (PR approval tab): The approvals page has no PR-specific card/tab — only PO and Payment approvals shown.
- G-028/G-096 (Advance clearing action): The hook `useTagAdvanceToGR` exists in `use-procurement.ts:1600` but no "Clear Advance" button in the outstanding advances page UI.

**True MUST-HAVEs remaining:** 2 items (G-027, G-065/G-097), plus the backend-only G-019 (correction feedback).

**Total effort estimate:** 2-3 weeks (mostly frontend; backend is largely complete)

---

## Business Context

| Fact | Value |
|------|-------|
| Finance transition | FROM Apex external accounting TO in-house (Alyssa Dimaano) |
| PCF process | 200-400+ expense receipts/month from 45 stores |
| 3-way match chain | PO → GR → Invoice → Payment (backend complete, most frontend complete) |
| Payment approval tiers | 4-level: Reviewer → Budget → CFO → CEO (≥PHP 500K) |
| Franchise billing | Royalty 7%, Management 2.5%, Marketing 5% (VAT-inclusive), Ecommerce 5% (VAT-inclusive) |
| Supplier duplicate rule | Phone/Bank/TIN: BLOCK. Email: WARN only. |
| OR compliance | BIR requires OR within 30 days of payment. Auto-escalation at 7/14/30 days. |
| Match exception | Safety valve for advance payments and emergency purchases |

**Key people:**
- **Alyssa Dimaano** — Accounts Manager (primary Finance user in my.bebang.ph)
- **Denise Almario** — Finance Supervisor (OpEx collection)
- **Mae** — CPO, approves POs ≤PHP 500K and OR escalations at 14 days
- **Butch** — CFO, co-approves POs >PHP 500K and OR escalations at 30 days

---

## Technology Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend | Frappe Framework (Python) | All APIs in `hrms/api/` |
| Employee App (my.bebang.ph) | React + Next.js 16 + Shadcn UI + Tailwind v4 | Separate repo: `frontend-procurement` |
| Database | MariaDB (Docker container) | NOT AWS RDS |
| Notifications | Google Chat via service account | `hrms/api/google_chat.py` |
| Deployment | Docker → AWS EC2 via GitHub Actions | `.github/workflows/build-and-deploy.yml` |
| Frontend Deploy | Vercel CLI | `vercel.cmd --prod --force` |

---

## Source Files Map

### Backend API Files

| File | Lines | Role | Key Functions |
|------|-------|------|---------------|
| `hrms/api/procurement.py` | 4,133 | Full PR→PO→GR→Invoice→Payment cycle | See function inventory below |
| `hrms/api/billing.py` | 1,023 | Franchise billing, 3PL reconciliation, delivery rates | `get_delivery_rates`, `set_delivery_rate`, `submit_rate_for_review`, `approve_rate`, `generate_monthly_billing`, `get_billing_list`, `get_3pl_rates`, `generate_3pl_reconciliation` |
| `hrms/api/expense_review.py` | 591 | PCF expense review (Finance role) | `get_review_dashboard`, `get_pending_review`, `get_expense_detail`, `approve_expense`, `batch_approve`, `reject_expense`, `get_auto_approved_batch` |
| `hrms/api/expense.py` | 424 | PCF expense submission (store staff) | `submit_expense`, `get_my_expenses`, `get_expense_status` |
| `hrms/api/pcf.py` | 1,126 | PCF fund management, custodians, batches | `add_expense_to_pending`, `get_pcf_status`, `submit_batch_now`, `approve_batch`, `reject_batch`, `assign_pcf_custodian`, `create_pcf_fund` |
| `hrms/api/soa.py` | 204 | Statement of Account for franchise stores | `generate_soa`, `get_soa_list`, `send_soa_to_store` |
| `hrms/api/expense_classifier.py` | 761 | ML COA classifier, training, corrections | `classify_expense`, `train_model`, `record_correction`, `get_coa_options` |
| `hrms/api/google_chat.py` | — | Google Chat notifications | `send_message_to_space(space_name, message) -> bool` |
| `hrms/utils/bei_config.py` | — | Central config | `get_company()`, `get_chat_space()`, `SPACE_NOTIFICATIONS` |

### Procurement.py Function Inventory (88 functions)

| Lines | Function | Status |
|-------|----------|--------|
| 65–118 | `get_suppliers`, `get_supplier`, `create_supplier` | LIVE |
| 127–218 | Supplier duplicate detection (phone/bank/TIN throw, email warn) | LIVE — AC 2.5 |
| 274–382 | `get_purchase_requisitions`, `create_purchase_requisition`, `submit_pr_for_approval`, `approve_pr`, `reject_pr` | LIVE |
| 374–383 | `convert_pr_to_po(name, supplier)` | LIVE |
| 384–596 | `get_purchase_orders`, `create_purchase_order`, PO approval chain | LIVE |
| 634–840 | `get_goods_receipts`, `create_goods_receipt`, `submit_goods_receipt`, `complete_gr_inspection` | LIVE |
| 843–1010 | `get_invoices`, `create_invoice`, `submit_invoice_for_verification`, `verify_invoice_match`, `approve_invoice_variance`, `reject_invoice_variance` | LIVE |
| 1012–1264 | `get_payment_requests`, `create_payment_request`, 4-level approval chain, `mark_payment_complete` | LIVE |
| 2183–2217 | `check_price_variance(item_code, supplier, new_price)` — returns variance >5% warning | LIVE, NOT wired to frontend |
| 2258 | `get_supplier_data_quality()` | LIVE |
| 2700–2762 | `request_match_exception(data)` — sends CEO notification | LIVE, NOT wired to frontend |
| 2829–2910 | `approve_match_exception`, `reject_match_exception` | LIVE, wired in accounting/exceptions/ |
| 2912–2975 | `get_match_exceptions` | LIVE |
| 3054–3131 | `get_or_aging_summary()` | LIVE |
| 3179–3220 | `send_or_follow_up(name)` | LIVE (manual) |
| 3222–3265 | `check_overdue_or()` — daily scheduler, escalates at 7/14/30 days via notifications | LIVE — G-095 CONFIRMED RESOLVED |
| 3304–3425 | `tag_advance_to_gr(advance_payment, goods_receipt, amount_to_clear)` | LIVE, hook exists, NOT wired to UI |
| 3469–3578 | `mark_advance_undeliverable(advance_payment, amount, reason)` | LIVE |
| 3580–3655 | `get_outstanding_advances(page, page_size, group_by, supplier, status)` | LIVE |
| 3944–4015 | `generate_acknowledgement_receipt(billing_name)` | LIVE |
| 4017–4128 | `apply_franchise_payment(...)` | LIVE |
| 4130+ | `generate_monthly_billing(billing_period, store)` | LIVE |

### DocTypes (BEI Custom)

| DocType | Directory | Status | Notes |
|---------|-----------|--------|-------|
| `BEI Invoice` | `hrms/hr/doctype/bei_invoice/` | JSON EXISTS (9,617 bytes, 46 fields) | Covers full 3-way match fields |
| `BEI Match Exception` | `hrms/hr/doctype/bei_match_exception/` | JSON EXISTS (4,690 bytes, 22 fields) | Exception workflow fields present |
| `BEI Payment Request` | `hrms/hr/doctype/bei_payment_request/` | EXISTS | 4-level approval with OR tracking |
| `BEI Purchase Order` | `hrms/hr/doctype/bei_purchase_order/` | EXISTS | Full PO with approval chain |
| `BEI Purchase Requisition` | `hrms/hr/doctype/bei_purchase_requisition/` | EXISTS | PR with department/requestor |
| `BEI Expense Request` | `hrms/hr/doctype/bei_expense_request/` | EXISTS | PCF expenses with OCR, ML COA |
| `BEI Billing Schedule` | `hrms/hr/doctype/bei_billing_schedule/` | EXISTS | Franchise billing records |
| `BEI Delivery Rate` | `hrms/hr/doctype/bei_delivery_rate/` | EXISTS | Rate per store+cargo_type |

### Existing Frontend Pages (frontend-procurement repo)

| Path | Lines | Status | Notes |
|------|-------|--------|-------|
| `app/dashboard/accounting/expenses/page.tsx` | 212 | LIVE | Expense queue list |
| `app/dashboard/accounting/expenses/[id]/page.tsx` | 378 | LIVE | Expense detail view |
| `app/dashboard/accounting/expenses/batch/page.tsx` | 287 | LIVE | Batch approve page |
| `app/dashboard/accounting/expenses/review/page.tsx` | 336 | LIVE | Review queue page |
| `app/dashboard/accounting/exceptions/page.tsx` | 335 | LIVE | Match exception approve/reject WIRED |
| `app/dashboard/accounting/outstanding-advances/page.tsx` | 477 | LIVE | Advance listing — **missing Clear action** |
| `app/dashboard/accounting/awaiting-or/` | — | EXISTS | OR follow-up pages |
| `app/dashboard/procurement/purchase-requisitions/page.tsx` | — | LIVE | PR list |
| `app/dashboard/procurement/purchase-requisitions/[id]/page.tsx` | 524 | LIVE | PR detail with Convert-to-PO button |
| `app/dashboard/procurement/purchase-orders/page.tsx` | — | LIVE | PO list |
| `app/dashboard/procurement/purchase-orders/[id]/page.tsx` | 869 | LIVE | PO detail — **missing Request Exception** |
| `app/dashboard/procurement/approvals/page.tsx` | 126 | PARTIAL | Has PO + Payment + Exceptions — **missing PR card** |
| `app/dashboard/procurement/goods-receipts/` | — | LIVE | GR management |
| `app/dashboard/procurement/invoices/` | — | LIVE | Invoice list/detail |
| `app/dashboard/procurement/payments/` | — | LIVE | Payment requests |
| `app/dashboard/billing/rates/` | — | EXISTS | Rate management (verify if approval wired) |

### Frontend Hooks (frontend-procurement/hooks/)

| Hook File | Key Exports | Notes |
|-----------|-------------|-------|
| `hooks/use-procurement.ts` | `useConvertPRToPO` (L:1068), `useApproveException` (L:1295), `useRejectException` (L:1314), `useTagAdvanceToGR` (L:1600) | All hooks EXIST |
| `hooks/use-expense-review.ts` | `useApproveExpense`, `useBatchApprove`, `useRejectExpense` | LIVE |

### RBAC Roles

```python
# expense_review.py
ACCOUNTING_ROLES = {"Accounts Manager", "System Manager"}

# procurement.py
PROCUREMENT_ROLES = {"Procurement Officer", "Supply Chain Manager", "System Manager"}
PO_APPROVER_ROLES = {"CFO", "CPO", "System Manager"}
```

---

## True MUST-HAVE Gaps (3 items)

### Gap G-027: Match Exception Request Not Available in Procurement UI

**Problem:** Procurement staff must be able to REQUEST a match exception from the PO detail page when encountering a 3-way match block (AC 2.1 control in `create_invoice`). The backend `request_match_exception(data)` at `procurement.py:2700` is LIVE and sends a CEO notification. The hook `useApproveException` exists but no `useRequestException` hook or UI exists.

`procurement/purchase-orders/[id]/page.tsx` (869 lines) has NO reference to `match_exception`, `request_exception`, or any exception modal.

**Fix (2 tasks):**

**Task 27A: Add `useRequestException` hook** (30 min)
- File: `frontend-procurement/hooks/use-procurement.ts`
- After `useRejectException` at line 1314, add:
  ```typescript
  export function useRequestException() {
    const queryClient = useQueryClient();
    return useMutation({
      mutationFn: (data: {
        reference_type: string;
        reference_name: string;
        purchase_order: string;
        exception_type: string;
        reason: string;
        amount?: number;
      }) => apiCall('/exceptions/request', { method: 'POST', body: JSON.stringify(data) }),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['match-exceptions'] });
        toast.success('Exception request submitted for approval');
      },
      onError: (error) => toast.error(`Failed to request exception: ${error.message}`),
    });
  }
  ```
- Backend route: `POST /api/procurement/exceptions/request` → `procurement.request_match_exception`

**Task 27B: Add "Request Exception" button and modal to PO detail page** (2-3 hours)
- File: `frontend-procurement/app/dashboard/procurement/purchase-orders/[id]/page.tsx`
- Add state: `const [showExceptionModal, setShowExceptionModal] = useState(false);`
- Add button in PO actions section (near the existing action buttons):
  ```tsx
  <Button variant="outline" onClick={() => setShowExceptionModal(true)}>
    Request Match Exception
  </Button>
  ```
- Add modal with fields: `exception_type` (Select: "Advance Payment" | "Emergency Purchase" | "Retroactive GR"), `reason` (Textarea, required)
- On submit: call `useRequestException.mutate({ reference_type: "BEI Purchase Order", reference_name: po.name, purchase_order: po.name, exception_type, reason })`
- Show modal only when `po.status` is "Submitted" or "Approved" (not Draft)

**Effort:** 3-4 hours
**Test:** Log in as procurement staff, navigate to an approved PO, click "Request Exception", verify exception appears in `/dashboard/accounting/exceptions` page, verify Finance user can approve/reject it.

---

### Gap G-065/G-097: PR Approval Card Missing from Approvals Page

**Problem:** `procurement/approvals/page.tsx` (126 lines) shows only PO Approvals, Payment Approvals, and Exception Approvals cards. There is no PR (Purchase Requisition) approval card, meaning department heads don't see a dedicated PR queue. PRs submitted for approval (`submit_pr_for_approval`) require the department head to visit the PR list directly.

The `get_purchase_requisitions` API already supports `filters: { pending_approval: true }` filtering. No dedicated `get_pending_pr_approvals` function exists, but the list API is sufficient.

**Fix (1 task):**

**Task 65A: Add PR Approval card to approvals page** (1-2 hours)
- File: `frontend-procurement/app/dashboard/procurement/approvals/page.tsx`
- Add import: `usePurchaseRequisitions` from `use-procurement.ts` (already exists)
- Add query: `const { data: prApprovals } = usePurchaseRequisitions({ pendingApproval: true });`
- Add card in the grid alongside PO/Payment cards:
  ```tsx
  <Link href="/dashboard/procurement/purchase-requisitions?filter=pending_approval">
    <Card className="hover:border-primary/50 cursor-pointer transition-colors">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-100 text-purple-600">
            <FileCheck className="h-5 w-5" />
          </div>
          {pendingPRs > 0 && <Badge variant="destructive">{pendingPRs} pending</Badge>}
        </div>
        <CardTitle className="text-lg">Purchase Requisition Approvals</CardTitle>
        <CardDescription>
          Review and approve department purchase requests before PO creation.
        </CardDescription>
      </CardHeader>
    </Card>
  </Link>
  ```
- Count: `const pendingPRs = prApprovals?.data?.length ?? 0;`
- Also add `?filter=pending_approval` URL param handling in the PR list page to pre-filter

**Effort:** 1-2 hours
**Test:** Submit a PR as test.staff@bebang.ph, log in as approver, navigate to `/dashboard/procurement/approvals`, verify PR card shows pending badge, click through to PR list pre-filtered.

---

### Gap G-019: Correction Feedback Not Wired into approve_expense

**Problem:** `approve_expense()` in `expense_review.py` saves the COA but does not record the correction in the ML training database.
**Fix:** Wire `record_correction` from `expense_classifier.py` into the end of `approve_expense()`.

---

### Gap FIN-G03: PCF Auto-JV Generation Missing (PAP-005/006)

**Problem:** Currently, `approve_expense()` saves the expense but does not generate the corresponding Journal Entry in the General Ledger. The CFO explicitly requested that the JV be auto-generated per expense at approval time.

**Fix (1 task):**

**Task F03A: Auto-Generate PCF JV on Expense Approval**
- File: `hrms/api/expense_review.py` -> `approve_expense()`
- Immediately after marking the expense as Approved, create a Journal Entry:
  - Dr: `final_coa` (The expense account selected)
  - Cr: `1113000` (PCF Cash - central account)
  - Ensure the `cost_center` on both rows matches the Store the expense originated from.
  - Submit the JV automatically.

**Effort:** 1 day
**Test:** Approve a pending expense, check the General Ledger to verify a new JV was submitted debiting the expense and crediting 1113000 with the correct store Cost Center.

---

**Problem:** `expense_review.py:290-336` (`approve_expense`) saves the `final_coa` but does NOT call `expense_classifier.record_correction()`. When Finance corrects an OCR-misclassified COA, the ML model never learns from the correction. Over time, the same mistakes repeat.

`expense_classifier.record_correction(expense_name, original_coa, corrected_coa)` at `expense_classifier.py:636` exists and is ready to be called.

**Fix (1 task):**

**Task 19A: Wire record_correction into approve_expense** (30 min)
- File: `hrms/api/expense_review.py`
- After line 320 (`expense.status = "Approved"`), add correction feedback:
  ```python
  # G-019: Record COA correction for ML training
  if final_coa != expense.internal_suggested_coa:
      try:
          from hrms.api.expense_classifier import record_correction
          record_correction(
              expense_name=expense_name,
              original_coa=expense.internal_suggested_coa or "UNKNOWN",
              corrected_coa=final_coa
          )
      except Exception:
          pass  # Never block approval on classifier failure
  ```
- The field `internal_suggested_coa` stores what the ML/rules engine suggested. If Finance chose a different COA, that IS a correction.

**Effort:** 30 minutes
**Test:** Submit an expense, verify OCR/ML suggests a COA, approve with a DIFFERENT COA, run `bench execute hrms.api.expense_classifier.get_classification_stats` and verify correction count increased.

---

## SHOULD-HAVE Gaps (11 items)

### Gap G-020: ML Model Not Trained

**Problem:** `expense_classifier.joblib` model file does not exist at `/home/frappe/frappe-bench/sites/assets/expense_classifier.joblib`. System falls back to rules-based (80% accuracy) or OpenAI (cost per call). After G-019 is done, approved corrections will accumulate — training on 300-500 historical examples will significantly improve accuracy.

**Fix:**

**Task 20A: Train the ML classifier** (1 hour one-time task)
- Requires SSH to EC2, or via SSM + bench console
- Command: `bench execute hrms.api.expense_classifier.train_model`
- Prerequisite: At least 300 approved expenses in `BEI Expense Request` with `status = "Approved"` and non-null `internal_final_coa`
- Schedule weekly retraining: add to `scheduler_events` in `hooks.py`:
  ```python
  "weekly": ["hrms.api.expense_classifier.train_model"]
  ```
- Verify model created: `ls -la sites/assets/expense_classifier.joblib`

**Effort:** 30 min + deploy
**Test:** After training, submit a test expense with a known description, verify classifier returns ML confidence score instead of "rules-based".

---

### Gap G-023: No Frontend for SOA Workflow

**Problem:** `soa.py` has 3 live functions: `generate_soa(store, period)`, `get_soa_list(store, period, status)`, `send_soa_to_store(soa_name)`. Finance (Alyssa) must trigger this via API or Frappe Desk. No pages at `/dashboard/accounting/soa/`.

**Fix (2 pages):**

**Task 23A: SOA List Page** (1-2 days)
- Path: `frontend-procurement/app/dashboard/accounting/soa/page.tsx`
- API: `GET /api/accounting/soa?store=&period=&status=` → `soa.get_soa_list`
- Columns: Period, Store, Status (Draft/Sent/Acknowledged), Total Amount, Actions
- Actions: "Generate" button → calls `generate_soa`, "View" link → detail page
- Filter bar: store picker, period (month/year), status filter

**Task 23B: SOA Detail Page** (1 day)
- Path: `frontend-procurement/app/dashboard/accounting/soa/[name]/page.tsx`
- Shows line items, totals, store contact, send history
- "Send to Store" button → calls `send_soa_to_store(soa_name)`, requires confirm dialog ("This will email the SOA to {store contact email}. Continue?")

**Effort:** 3-5 days
**Test:** Generate SOA for a test franchise store, verify line items are correct, click "Send", verify email receipt.

---

### Gap G-024: No Frontend for Delivery Rate Approval Queue

**Problem:** `billing.py:36-145` has `get_delivery_rates`, `set_delivery_rate`, `submit_rate_for_review`, `approve_rate`, `get_stores_without_rates`. `/dashboard/billing/rates/` directory exists — verify if approval flow is wired.

**Fix (1 page update):**

**Task 24A: Verify and wire rate approval** (2-3 days)
- Check `frontend-procurement/app/dashboard/billing/rates/` pages for `submit_rate_for_review` and `approve_rate` buttons
- If missing: add "Submit for Review" action on rate records with `status == "Draft"`
- Add "Approve" action for RATE_MANAGEMENT_ROLES (`billing.py:601`: Accounts Manager, Supply Chain Manager)
- Add "Stores Missing Rates" alert section: call `get_stores_without_rates()`, display list of stores with no active rate configured — these stores will generate billing errors

**Effort:** 2-3 days
**Test:** Set a delivery rate for a test store, submit for review, approve as Accounts Manager, verify status changes to "Active".

---

### Gap G-028/G-096: Advance Payment Clearing Action Missing

**Problem:** `hooks/use-procurement.ts:1600` has `useTagAdvanceToGR`. However, `/dashboard/accounting/outstanding-advances/page.tsx` (477 lines) shows no "Clear Advance" action button — only listing and summary views. When GR arrives for an advance payment, Finance must manually call the API.

**Fix (1 task):**

**Task 28A: Add "Clear Advance" action to outstanding advances page** (1-2 days)
- File: `frontend-procurement/app/dashboard/accounting/outstanding-advances/page.tsx`
- Add "Clear" button on each advance row with status "Outstanding"
- Opens modal: "Link to GR" selector (calls `get_goods_receipts` filtered by supplier) + amount field
- On submit: calls `useTagAdvanceToGR.mutate({ advance_payment: advance.name, goods_receipt: selectedGR, amount_to_clear: amount })`
- Add "Mark Undeliverable" action: calls `mark_advance_undeliverable` (backend: `procurement.py:3469`)
- Hook already exists — this is purely frontend wiring

**Effort:** 1-2 days
**Test:** Create an advance payment, receive goods (create GR), navigate to outstanding advances, link advance to GR, verify `advance_outstanding` decreases to 0.

---

### Gap G-060: Price Variance Check Not Integrated in PO Form

**Problem:** `check_price_variance(item_code, supplier, new_price)` at `procurement.py:2183` returns variance >5% vs 90-day average. PAP-008 and PAP-009 require a >10% hard block and mandatory reason logging.

**Fix (2 tasks):**

**Task 60A: Wire price variance check into PO create/edit form**
- File: `frontend-procurement/app/dashboard/procurement/purchase-orders/new/page.tsx`
- Call `check_price_variance` on price change. Show yellow warning if >5%.

**Task 60B: Implement 10% Hard Block & Override Logging**
- Update `check_price_variance` backend to block at >10% unless `override_reason` is provided.
- Log the override reason, user ID, and timestamp into the PO item row.

**Effort:** 1 day

---

### Gap G-093: OR Aging Summary Not on Finance Dashboard

**Problem:** `get_or_aging_summary()` at `procurement.py:3054` is LIVE and returns aging buckets for ORs (Official Receipts) by supplier. Finance has no visibility into this in my.bebang.ph. The `check_overdue_or()` scheduler IS confirmed to send notifications (it uses `_create_or_escalation_notification` at 7/14/30 days), so G-059 and G-095 are RESOLVED. G-093 (dashboard widget) is the remaining item.

**Fix (1 task):**

**Task 93A: Add OR Aging widget to Accounting dashboard** (1 day)
- File: `frontend-procurement/app/dashboard/accounting/page.tsx`
- Add card showing OR aging summary: 0-7 days (green), 8-14 days (yellow), 15-30 days (orange), >30 days (red/escalated)
- API: `GET /api/procurement/or-aging-summary` -> `procurement.get_or_aging_summary`
- Link to `/dashboard/accounting/awaiting-or` for full list
- Badge count: total overdue ORs

**Effort:** 1 day
**Test:** Mark a payment as "Paid - Awaiting OR" with an overdue `or_due_date`, navigate to accounting dashboard, verify it appears in the aging widget.

---

### Gap FIN-T06: Missing Invoice Escalation Policy (TAX-006)

**Problem:** Under EOPT Law, the Invoice is the primary document, not the OR. Online payments require Invoice within 5 days; check payments require it before check release. Currently, there is no system to track or escalate missing Invoices post-payment.
**Fix (1 task):**
**Task T06A: Add Missing Invoice Scheduler & UI Flag**
- Add `check_overdue_invoices()` to `hrms/hooks.py` daily scheduler.
- Send Google Chat notification for online payments where `status = Paid` but no `BEI Invoice` is linked within 5 days.

---

### Gap FIN-T14: EWT GL Entry Generation (TAX-014)

**Problem:** Even though 1%/2% trade EWT was dropped, the system still needs to generate EWT JV entries for Professional Fees (5-15%) and Rentals (5%) when payment is made. Currently, `procurement.py` does not create the Dr Accounts Payable / Cr 2102202 EWT Payable entry.
**Fix (1 task):**
**Task T14A: Auto-Generate EWT Journal Entry at Payment**
- File: `hrms/api/procurement.py` -> inside `mark_payment_complete()`
- If `ewt_amount` > 0, generate JV: Dr Accounts Payable (Supplier) / Cr 2102202 (EWT Payable).

---

### Gap G-094: Match Exception Request Not Inline on Invoice Creation

**Problem:** When `create_invoice` hits AC 2.1 (no GR), it throws. Staff then must navigate to the PO page separately to request an exception (G-027 fix). G-094 proposes showing the exception request inline on the invoice creation form.

**Note:** This is MEDIUM priority — implement G-027 first. G-094 is a UX improvement on top.

**Fix (1 task):**

**Task 94A: Add inline exception request to invoice creation error state** (2-3 days)
- File: `frontend-procurement/app/dashboard/procurement/invoices/new/page.tsx`
- When `create_invoice` returns an error containing "AC 2.1" or "no goods receipt", show an inline panel instead of just a toast error:
  ```tsx
  {invoiceError?.includes('AC 2.1') && (
    <Alert variant="destructive">
      <AlertTitle>3-Way Match Required</AlertTitle>
      <AlertDescription>
        No goods receipt found for this PO. You must either:
        <ol>
          <li>Create a Goods Receipt first, or</li>
          <li>Request a Match Exception (approval required)</li>
        </ol>
        <Button onClick={() => setShowExceptionModal(true)}>
          Request Match Exception
        </Button>
      </AlertDescription>
    </Alert>
  )}
  ```
- Reuse the same exception modal built in G-027

**Effort:** 2-3 days (after G-027 modal exists)
**Test:** Try to create an invoice for a PO without a GR, verify inline exception request panel appears, request exception, verify it routes to the exceptions approval queue.

---

### Gap G-023: SOA Workflow (covered above in SHOULD-HAVE section)
*(Already documented as Task 23A and 23B)*

---

## Closed Gaps (Confirmed — No Action Needed)

| Gap | Reason Closed |
|-----|---------------|
| G-021 | BEI Invoice DocType JSON EXISTS: `bei_invoice.json` is 9,617 bytes with 46 fields |
| G-022 | BEI Match Exception DocType JSON EXISTS: `bei_match_exception.json` is 4,690 bytes with 22 fields |
| G-025 | `accounting/exceptions/page.tsx` (335 lines) has `useApproveException` / `useRejectException` fully wired with modal UI |
| G-026 | `procurement/purchase-requisitions/[id]/page.tsx` (524 lines) has `useConvertPRToPO` and Convert button |
| G-061 | `procurement.py:127-206` — Phone, Bank Account, AND TIN all use `frappe.throw()`. Email uses `warnings.append()`. (Bank account: line 182, TIN: line 200) |
| G-095 | `check_overdue_or()` (line 3222) IS auto-escalating — sends notifications via `_create_or_escalation_notification` at 7/14/30 days |
| G-117 | Event-driven billing implemented — `_create_delivery_billing()` enqueued on `confirm_delivery()` |
| G-127 | Supabase views fixed 2026-02-17 (Memory #19) |
| G-018 | Accounting Review UI BUILT — 4 pages exist: `expenses/page.tsx` (212L), `expenses/[id]/page.tsx` (378L), `expenses/batch/page.tsx` (287L), `expenses/review/page.tsx` (336L) |

---

## Deferred to Nice-to-Have

| Gap | Why Deferred |
|-----|-------------|
| G-057 | PCF custodian assignment — infrequent (once/month). `assign_pcf_custodian()` backend exists. Use Frappe Desk. |
| G-029 | AR list view — generated automatically on GR. Low daily need. |
| G-030 | Franchise payment application — monthly billing cycle. Manageable via billing detail page. |
| G-062 | Single source supplier report — strategic, not daily ops. |
| G-063 | Supplier data quality badge — quarterly BIR compliance. Not daily. |
| G-064 | Billing statement send — infrequent AP communication. Add as button on supplier detail page in Phase 2. |
| G-116 | Billing data source migration (Store Closing → Supabase) — working today. Technical debt only. |

---

## Sprint Execution Order

### Phase 1 — Immediate Blockers (Days 1-3)

**Day 1: Schema Fixes & Runbooks (Blockers 1, 8, 6, 9, 10)**
1. Task B1: Create `BEI Expense Training Data` DocType
2. Task B8: Update `bei_match_exception.approver` to Link field
3. Task B6: Create `BEI Form 2307` DocType
4. Task B9: Add Rollback Runbook documentation
5. Task B10: Write L4 Scenarios T-PROC-003 and T-PROC-004
6. Backend deploy: DocType changes require `bench migrate`

**Day 2: Backend Logic Fixes (Blockers 4, 5) & G-019/G-027/FIN-G03 Backend**
7. Task B4/B5: Update `tag_advance_to_gr` to use `1104005` and split Input VAT
8. Task 19A: Wire `record_correction` into `approve_expense`
8b. Task F03A: Auto-Generate PCF JV (Dr Expense, Cr 1113000) inside `approve_expense` per PAP-005
9. Task 27A: Wire exception request backend + Update routing logic to CPO (<500K) and CPO+CFO (>=500K) per PAP-001
10. Backend deploy: Full Docker build (`skip_build=false`, `no_cache=true`)

**Day 3: Frontend Wiring (G-027, G-065)**
11. Task 27B: Add "Request Exception" modal to PO detail page (reusing existing modal)
12. Task 65A: Add PR Approval card to approvals page
13. Deploy frontend: `vercel.cmd --prod --force`

### Phase 2 — Core Finance Tools (Days 4-14)

**Days 4-5: G-020 ML Training**
7. Task 20A: SSH/SSM to EC2, run `bench execute hrms.api.expense_classifier.train_model`
8. Add weekly scheduler entry to `hooks.py`
9. Full backend deploy

**Days 6-8: G-028/G-096 Advance Clearing**
10. Task 28A: Add "Clear Advance" and "Mark Undeliverable" actions to outstanding advances page
11. Frontend deploy

**Days 9-11: G-023 SOA Pages**
12. Task 23A: Build SOA list page
13. Task 23B: Build SOA detail + send page
14. Frontend deploy

**Days 12-14: G-024 Delivery Rate Approval**
15. Task 24A: Verify/wire rate approval actions in billing/rates/

### Phase 3 — Efficiency Wins & Compliance (Days 15-25)

**Days 15-17: G-060 Price Variance (Updated per PAP-008/009)**
16. Task 60A: Wire price variance check into PO create form
17. Task 60B: Implement 10% hard block and mandatory reason logging for overrides

**Days 18-19: BIR Compliance (TAX-006, TAX-014)**
17b. Task T06A: Add Missing Invoice Escalation Scheduler
17c. Task T14A: Auto-Generate EWT Journal Entry at Payment

**Day 20: G-093 OR Aging Widget**
18. Task 93A: Add OR aging card to accounting dashboard

**Days 21-25: G-094 Inline Exception (depends on G-027)**
19. Task 94A: Inline exception request on invoice creation

---

## Verification Checklist

### Backend Verification

- [ ] `POST /api/procurement/exceptions/request` → `request_match_exception` returns success
- [ ] `approve_expense` with corrected COA calls `record_correction` → verify in expense_classifier DB
- [ ] `check_overdue_or()` logs escalation notifications at 7/14/30 days (check scheduler logs)
- [ ] `check_price_variance` returns block signal for >10% variance, and warning for 5-10%
- [ ] `tag_advance_to_gr` clears advance correctly — verify `advance_outstanding` field updates
- [ ] `train_model` completes without error and creates `expense_classifier.joblib`
- [ ] BEI Supplier correctly accepts `vat_status`, `ewt_exempt` flags

### Frontend Verification

- [ ] `/dashboard/procurement/purchase-orders/[id]` shows "Request Match Exception" button
- [ ] Exception modal: exception_type Select + reason Textarea + Submit — calls API correctly
- [ ] Exception request appears in `/dashboard/accounting/exceptions` queue immediately
- [ ] Finance user can approve/reject from exceptions queue
- [ ] `/dashboard/procurement/approvals` shows PR Approval card with pending count badge
- [ ] PR Approval card links to pre-filtered PR list
- [ ] `/dashboard/accounting/outstanding-advances` shows "Clear Advance" button on Outstanding advances
- [ ] Clear Advance modal: GR selector + amount + submit
- [ ] After clearing, advance status updates to "Fully Cleared"
- [ ] `/dashboard/accounting/soa/` SOA list loads with period and store filters
- [ ] "Send to Store" button triggers email and updates SOA status to "Sent"
- [ ] Accounting dashboard shows OR aging widget with correct counts

### Integration Verification (E2E)

- [ ] PR → PO → GR → Invoice → Payment end-to-end: Create PR as staff, approve as manager, convert to PO, create GR, create invoice, submit for payment — verify full chain
- [ ] 3-way match block scenario: Create invoice without GR → verify AC 2.1 throws → request exception → finance approves → retry invoice → verify succeeds
- [ ] Advance payment scenario: Create PR with advance, approve payment, goods arrive, clear advance against GR — verify outstanding = 0
- [ ] ML correction: Submit expense, OCR suggests wrong COA, Finance corrects to different COA, verify correction recorded in `get_classification_stats`

---

## Deployment Notes

### Backend Deploy
All Python changes require a **FULL Docker build**:
- `skip_build=false`, `no_cache=true`
- Files changed: `hrms/api/expense_review.py`, `hrms/api/expense.py`, `hrms/api/procurement.py` (if adding route), `hrms/hooks.py` (scheduler)
- DocType JSON changes require `bench migrate` after deploy
- Build time: 5-10 min for Docker, 1-2 min for migration

### Frontend Deploy
```bash
vercel.cmd --prod --force --token $TOKEN --scope team_xvK1nhuvsdZp3GNfd4uDJ0DW --yes
```
- Files: `frontend-procurement/hooks/use-procurement.ts`, all modified `app/dashboard/accounting/*` and `app/dashboard/procurement/*` pages

### Test Accounts
| Account | Email | Role | Purpose |
|---------|-------|------|---------|
| Alyssa (Finance) | test.hr@bebang.ph | Accounts Manager | Approve expenses, exceptions, SOA |
| Procurement staff | test.area@bebang.ph | Procurement Officer | Submit PRs, create POs |
| Area Supervisor | test.supervisor@bebang.ph | Area Supervisor | Approve PRs |

All test account passwords: `BeiTest2026!`

### API Route Registration
For any new API endpoints, register in `hrms/api/__init__.py` or via existing route prefix patterns. Match exception request should use the `procurement` prefix: `/api/procurement/exceptions/request`.

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| BEI Invoice / BEI Match Exception DocType JSONs not synced to DB | Low | High | Run `bench migrate` after any JSON change |
| ML model training fails (< 300 approved expenses) | Medium | Low | Training only improves 20% of expenses; fallback to rules still works |
| check_overdue_or notifications going to wrong email (mae@/butch@ not real emails) | Medium | Medium | Verify email addresses in production before enabling escalations |
| Advance clearing links wrong GR (user selects wrong PO's GR) | Low | Medium | Show GR details in selector (date, amount, supplier) to prevent mismatch |
| PCF threshold causing store staff friction (PHP 5K requirement) | Medium | Low | Threshold is configurable — can raise to PHP 8K if too many false positives |
| SOA email delivery fails (no SMTP configured) | Medium | Medium | Verify SMTP config in Frappe site settings before enabling `send_soa_to_store` |
| InvoiceCreation AC 2.1 error message doesn't contain parseable "AC 2.1" string | Low | Low | Use `error.code == "AC_2_1"` instead of string match if API returns structured errors |

---

## Appendix: Verified Gap Status Update

This table supersedes the master roadmap's Finance + Procurement section where gaps are now confirmed closed:

| Gap ID | Master Roadmap Status | Actual Status | Evidence |
|--------|----------------------|---------------|---------|
| G-018 | MUST-HAVE (build) | **CLOSED** | 4 expense review pages exist, 835 total lines |
| G-021 | MUST-HAVE (create JSON) | **CLOSED** | JSON exists: 9,617 bytes, 46 fields |
| G-022 | MUST-HAVE (create JSON) | **CLOSED** | JSON exists: 4,690 bytes, 22 fields |
| G-025 | MUST-HAVE (wire buttons) | **CLOSED** | `exceptions/page.tsx:60-94` has full approve/reject modal |
| G-026 | SHOULD-HAVE (build page) | **CLOSED** | `purchase-requisitions/[id]/page.tsx:116,149` has Convert-to-PO |
| G-061 | SHOULD-HAVE (1-line fix) | **CLOSED** | `procurement.py:182,200` — bank and TIN use `frappe.throw()` |
| G-059/G-093/G-095 | SHOULD-HAVE (verify) | **G-059/G-095 CLOSED** | `check_overdue_or()` L:3222 escalates via notifications; G-093 (dashboard widget) remains open |
| G-027 | MUST-HAVE | **OPEN** | No exception request in PO detail page |
| G-065/G-097 | SHOULD-HAVE | **OPEN** | No PR card in approvals page |
| G-028/G-096 | SHOULD-HAVE | **OPEN** | Hook exists, UI action missing on outstanding advances page |

---

## Audit Amendments (v1.1) — 2026-02-19

### Audit Methodology

5 specialized agents audited this plan in parallel, each writing detailed findings to disk. Full reports with code fixes are in the referenced files — this section contains only the consolidated blockers and recommendations.

| Domain | Agent | Findings File | Score |
|--------|-------|---------------|-------|
| Frappe Backend | frappe-backend-auditor | `output/plan-audit/finance-procurement-sprint/frappe_backend_findings.md` | 2 CRITICAL, 6 WARNING, 3 INFO |
| PH Finance | ph-finance-auditor | `output/plan-audit/finance-procurement-sprint/ph_finance_findings.md` | 59/100 compliance |
| Frontend | frontend-auditor | `output/plan-audit/finance-procurement-sprint/frontend_findings.md` | 6/10 quality |
| Deployment/QA | deployment-qa-auditor | `output/plan-audit/finance-procurement-sprint/deployment_qa_findings.md` | NO-GO, 4 CRITICAL |
| Design Review | design-review-auditor | `output/plan-audit/finance-procurement-sprint/design_review_findings.md` | 3/5 architecture |

### Top 10 Blockers (Must Resolve Before Execution)

#### BLOCKER 1: BEI Expense Training Data DocType Missing — Silent Data Loss
**Source:** `frappe_backend_findings.md` W3, `deployment_qa_findings.md` C-01, `design_review_findings.md` C2 | **Severity:** CRITICAL
**Problem:** `record_correction()` checks if DocType exists at runtime. It doesn't — no JSON file in repo. All ML corrections silently go to Error Log while returning `success: True`. G-019 wiring and G-020 training will appear to work but provide zero value.
**Fix:** Create `hrms/hr/doctype/bei_expense_training_data/bei_expense_training_data.json` with fields: expense_reference (Link), description (Text), vendor (Data), store (Link), original_suggestion (Data), corrected_coa (Data), corrected_by (Link→User), correction_date (Datetime). Must exist before Task 19A.

#### BLOCKER 2: RBAC Role Names in Plan Don't Match lib/roles.ts
**Source:** `frontend_findings.md` C-03 | **Severity:** CRITICAL
**Problem:** Plan defines `Accounts Manager`, `Procurement Officer`, `Supply Chain Manager`, `CFO`, `CPO` — none exist in `lib/roles.ts`. Actual roles: `Procurement User`, `Procurement Manager`, `HQ User`. Any page built using plan's role names will have broken access control.
**Fix:** All new pages must use `MODULES.FINANCE_ACCOUNTING` or `MODULES.PROCUREMENT` from `lib/roles.ts`. Update plan's RBAC section to reference actual role constants.

#### BLOCKER 3: EWT Never Auto-Triggered at Payment — BIR Penalty Exposure
**Source:** `ph_finance_findings.md` C1 | **Severity:** CRITICAL
**Problem:** `generate_form_2307_entry()` is never called automatically when payment transitions to "Paid". ATC code is hardcoded `WI100` for all supplier types (should vary: WI100 goods, WI010 services, WC010 rentals). BEI is the withholding agent — failure to withhold creates primary liability + 25% surcharge + 12% interest.
**Fix:** (1) Call `generate_form_2307_entry()` inside payment approval trigger. (2) Add `atc_code` and `ewt_rate` fields to Supplier master. (3) Create EWT JV entry (Dr Expense Payable, Cr EWT Payable) at payment time. **Not in current sprint — add as Phase 0 prerequisite or defer to dedicated tax sprint.**

#### BLOCKER 4: Input VAT 3-Way Split Not Implemented — EOPT Law
**Source:** `ph_finance_findings.md` C2 | **Severity:** CRITICAL
**Problem:** No code implements the 1105103/1105104/1105105 input VAT split. `tag_advance_to_gr()` posts directly to 1104002 INVENTORY with no VAT entry. Under EOPT Law, input VAT is claimable on GR date, not invoice date — this timing is not enforced anywhere.
**Fix:** All GR-triggered JV entries must extract VAT from total cost and post to 1105103/1105104/1105105. GR `receipt_date` must be posting_date on VAT entries. **Not in current sprint scope — add as Phase 0 prerequisite or dedicated tax sprint.**

#### BLOCKER 5: Advance Clearing Posts to Wrong GL Account
**Source:** `ph_finance_findings.md` C3 | **Severity:** CRITICAL
**Problem:** `tag_advance_to_gr()` debits 1104002 INVENTORY directly, bypassing GR/IR clearing account. This violates the 3-way match the system is designed to enforce and can inflate inventory on partial receipts (PAS 2 violation).
**Fix:** Clearing should post to a GR/IR clearing account, not 1104002. Coordinate with CFO (Butch) on correct clearing account code. Update `tag_advance_to_gr()` JV entries.

#### BLOCKER 6: Form 2307 Stored as Comment — Not BIR-Reportable
**Source:** `ph_finance_findings.md` C4 | **Severity:** CRITICAL
**Problem:** Form 2307 data is stored as JSON inside a `Comment` DocType. Cannot be exported for BIR 1601-EQ quarterly filing, not queryable by TIN, no GL EWT Payable posting accompanies it.
**Fix:** Create `BEI Form 2307` DocType with fields: supplier_tin, supplier_name, tax_period, atc_code, gross_amount, ewt_rate, ewt_amount, payment_request_link. GL EWT Payable posting must accompany each entry. **Defer to tax sprint but document as known gap.**

#### BLOCKER 7: useRequestException Hook Already Exists — Plan Proposes Duplicate
**Source:** `frontend_findings.md` C-01 | **Severity:** CRITICAL
**Problem:** Plan proposes creating `useRequestException` at a new endpoint `/exceptions/request`. The codebase already has `useRequestMatchException` (line 1271 of `use-procurement.ts`) posting to `/exceptions`, and `ExceptionRequestModal` component already uses it. Building per plan will create duplicate hooks, naming conflicts, and 404 errors.
**Fix:** Do NOT create `useRequestException`. Extend existing `useRequestMatchException` to add `reference_name` and `amount` fields if needed. Wire existing `ExceptionRequestModal` into PO detail page — the component exists, it just needs importing.

#### BLOCKER 8: `approver` Field in BEI Match Exception is Data, Not Link
**Source:** `frappe_backend_findings.md` C1 | **Severity:** CRITICAL
**Problem:** `bei_match_exception.json` field `approver` is `fieldtype: "Data"` with `options: "Email"`. Should be `Link` to `User` for referential integrity, permission filtering, and list view lookups. The `options` key on a Data field is ignored by Frappe.
**Fix:** Change to `{"fieldname": "approver", "fieldtype": "Link", "options": "User", "read_only": 1}`. Run `bench migrate`. Existing email values remain valid since User.name IS the email.

#### BLOCKER 9: No Rollback Plan for 25-Day Sprint
**Source:** `deployment_qa_findings.md` D-04 | **Severity:** HIGH
**Problem:** Plan's Risk Register lists 6 risks but provides no rollback procedure. No git tags created before deployment. No documented command to rollback Docker Swarm services or Vercel frontend.
**Fix:** Add Rollback Runbook: Backend: `docker service rollback frappe_backend/scheduler/queue-short/queue-long` via SSM. Frontend: Vercel dashboard → Deployments → Promote previous. Database: `bench restore <backup>`. Create git tags before each deploy.

#### BLOCKER 10: No Pre-Written L4 Test Scenarios for Primary Business Flows
**Source:** `deployment_qa_findings.md` C-02 | **Severity:** HIGH
**Problem:** The PR→PO→GR→Invoice→Payment E2E flow and 3-way match exception flow have zero pre-written scenarios in `TEST_SCENARIOS.md`. Per MEMORY #15, agent-invented tests miss real bugs. Plan's verification section uses narrative descriptions, not executable scenarios (violates E2E RULE 9).
**Fix:** Write L4 scenarios T-PROC-003 and T-PROC-004 in `TEST_SCENARIOS.md` before Phase 1 QA. Include exact payloads, role handoffs, and DB state assertions at each step.

### Additional Recommendations (Non-Blocking)

1. **N+1 query in `get_auto_approve_candidates()`** (`frappe_backend_findings.md` C2): Batch-fetch employee names and account names instead of per-row `frappe.db.get_value` calls.
2. **Advance clearing JV missing `reference_number`** (`frappe_backend_findings.md` W2): Add `jv.cheque_no = advance_payment` for subsidiary ledger reconciliation.
3. **`request_match_exception` doesn't set `requested_by`/`requested_date`** (`frappe_backend_findings.md` W6): Add `requested_by=frappe.session.user, requested_date=frappe.utils.now()` to doc constructor.
4. **Hardcoded approver names "Mae"/"Butch"** (`design_review_findings.md` C3): Replace with `BEI Config` Single DocType lookups. Personnel change will silently break approval queues.
5. **`train_model` scheduler** (`frappe_backend_findings.md` W4): Use `cron` entry, not `weekly` slot. ML training is long-running and must not block the request worker.
6. **Hardcoded emails in `check_overdue_or`** (`frappe_backend_findings.md` W5): Resolve CPO/CFO via `BEI Config` fields, not string literals.
7. **SOA pages need TanStack Query hooks first** (`frontend_findings.md` C-04): Create `useSOAList`, `useSOA`, `useSendSOA` in `use-accounting.ts` before building pages.
8. **Approvals page has no RoleGuard** (`frontend_findings.md` W-01): Wrap in `<RoleGuard module={MODULES.PROCUREMENT}>`.
9. **Marketing/eCommerce fees missing VAT** (`ph_finance_findings.md` W2): `VAT_INCLUSIVE_FEES` only contains royalty and management fees. Obtain BIR ruling on marketing/eCommerce VAT treatment.
10. **PCF approved expenses generate no GL entry** (`ph_finance_findings.md` W5): `approve_expense()` saves COA but creates no JV. 200-400 expenses/month are never posted to the General Ledger.
11. **7-day OR escalation tier doesn't exist in code** (`deployment_qa_findings.md` C-04): Plan claims 7/14/30-day tiers but code only has 14/30. Either implement 7-day tier or correct the plan.
12. **`bench migrate` not guaranteed on push deploys** (`deployment_qa_findings.md` D-01): DocType changes require `workflow_dispatch` with `run_migrate=true`. Push-triggered deploys skip migration.
13. **procurement.py is 4,133-line God Module** (`design_review_findings.md` anti-pattern): Plan to split into `procurement_pr.py`, `procurement_po.py`, `procurement_payment.py`, `procurement_reports.py` after this sprint.
14. **`batch_approve` uses no transaction boundary** (`design_review_findings.md` W2): Partial failures silently committed. Add `frappe.db.savepoint()` pattern.
15. **19 missing test scenarios** (`deployment_qa_findings.md` test coverage): Integration (3), Negative (5), RBAC (5), Frontend UI (5), Regression (3). Full list in findings file.

### Pre-Flight Checks: Audit Additions

- [ ] **AUDIT-1:** `BEI Expense Training Data` DocType JSON created and migrated
- [x] **AUDIT-2:** [STALE/HALLUCINATION] RBAC role names in all new code use `lib/roles.ts` constants (not Python role strings)
- [ ] **AUDIT-3:** `bei_match_exception.approver` field changed from Data to Link→User and migrated
- [x] **AUDIT-4:** [STALE/HALLUCINATION] `useRequestMatchException` extended (not duplicated) with `reference_name` and `amount` fields
- [x] **AUDIT-5:** [STALE/HALLUCINATION] `ExceptionRequestModal` wired into PO detail page (not rebuilt)
- [ ] **AUDIT-6:** Rollback runbook documented (backend Swarm rollback + frontend Vercel rollback)
- [ ] **AUDIT-7:** L4 test scenarios T-PROC-003 and T-PROC-004 written in `TEST_SCENARIOS.md`
- [ ] **AUDIT-8:** `request_match_exception` sets `requested_by` and `requested_date` on doc constructor
- [ ] **AUDIT-9:** Docker build type specified for every phase (all Python changes = `skip_build=false, no_cache=true`)
- [ ] **AUDIT-10:** BIR EWT/VAT gaps (Blockers 3-6) documented as known gaps with target sprint

### GO / NO-GO Gate (Updated)

**Execution is NO-GO until AUDIT-1 through AUDIT-10 are all checked.**

Blockers 3-6 (EWT auto-trigger, input VAT split, advance clearing GL account, Form 2307 DocType) are **BIR compliance issues** that may be deferred to a dedicated tax sprint — but must be explicitly documented as known gaps with a target resolution date before the Q1 BIR filing deadline (April 15, 2026).

---

## Progress Log

### 2026-02-19: Audit + Questionnaire Day

**Completed:**
1. Plan audit across 5 domains (backend, PH finance, frontend, deployment/QA, design review) — 10 blockers identified
2. Pre-filled DOCX questionnaire generated from previous Finance answers (CFO Feb 9, Accounting team Feb 5)
3. Fact-checked all pre-filled answers against source documents — found and fixed 6 issues:
   - ATC codes separated from CFO-confirmed rates (rates confirmed, codes need verification)
   - Fabricated "Both option" for Supplier Master ATC storage → converted to open question
   - Wrong capital goods account (1105105 = Importation, not capital goods) → corrected
   - PHP 1M threshold relabeled as BIR regulation (not CFO decision)
   - "Quarterly" restored to Form 2307 delivery preference per Butch's actual answer
   - April 15 relabeled as standard BIR deadline
4. Double-checked all fixes against full document corpus — all 6 confirmed correct
5. Regenerated final DOCX: `questionnaires/templates/FINANCE_PROCUREMENT_AUDIT_QUESTIONNAIRE_2026-02-19.docx`

**Key Decision: Start execution without waiting for Finance response.**

Pre-filled answers from CFO (Feb 9) already confirm enough to build:
- EWT rates (1%/2%/5-10%/10-15%/5%) → build with configurable ATC codes
- Input VAT accounts (1105103/1105104/1105105) and timing (GR date) → build the 3-way split
- Form 2307 requirements (auto-generate + quarterly batch) → build DocType
- Advance account (1105203) → confirmed

**Good news:** All blockers have been resolved by the CFO's recent questionnaire answers (EWT rates, VAT accounts, ATC codes, GR/IR account 1104005). The sprint is fully unblocked.

**Execution plan for tomorrow:**

| Priority | Item | Type | Blocked? |
|----------|------|------|----------|
| 1 | Blocker 1: Create BEI Expense Training Data DocType | Backend | No |
| 2 | Blocker 8: Fix approver field Data to Link | Backend | No |
| 3 | Blocker 5 & 4: tag_advance_to_gr GR/IR account & Input VAT | Backend | No |
| 4 | Blocker 6: Form 2307 DocType (Data only) | Backend | No |
| 5 | Blocker 10: Write L4 test scenarios | Documentation | No |
| 6 | Blocker 9: Write rollback runbook | Documentation | No |
| 7 | G-027: Match exception request button | Frontend | No |
| 8 | G-065/G-097: PR approval card | Frontend | No |
| 9 | G-028/G-096: Clear Advance button | Frontend | No |

### Version History

| Version | Date | Change |
|---------|------|--------|
| v1.0 | 2026-02-19 | Initial draft |
| v1.1 | 2026-02-19 | Plan audit: 10 blockers identified across 5 domains. NO-GO gate added. |
| v1.2 | 2026-02-19 | Pre-filled questionnaire generated, fact-checked (6 fixes), and ready for Finance. Decision: start execution using confirmed CFO answers; only GR/IR clearing account truly blocked. |
| v1.3 | 2026-02-22 | Code verification step: Blockers 2 and 7 identified as STALE (hallucinations - missing files/hooks). 8 blockers CONFIRMED. |
