# Procurement Operational Efficiency Roadmap

**Purpose:** Brainstorming document capturing all findings, defects, and improvement recommendations from S107–S116 procurement testing. This is NOT an execution plan — it's a reference for prioritizing what to build next.

**Prepared for:** Sam Karazi (CEO), Mae Karazi (CPO), Luwi Azusano & Cayla Cabagnot (Procurement)

**Date:** 2026-03-25

**Source evidence:**
- `output/l3/S108/TRAINING_FORM_TESTS.md` — S108 form submission test results
- `output/l3/S108/COLLATERAL_BUGS.md` — S108 collateral bug report
- `output/l3/S109/DEFECTS.md` — S109 comprehensive defect report
- `output/l3/S109/results.json` — S109 full test results (31 tests)
- `output/l3/S116-retest/` — S116 retest with financial validation (4 agents + fact-check)
- `output/l3/S116-retest/payment_chain.json` — Full procurement chain test
- `output/l3/S116-retest/FACT_CHECK.md` — Adversarial fact-check (7.5/10 trust score)
- `tmp/luwi_training_doc.md` — Procurement Training Guide v2.0

---

## Part 1: Current State — What Works

Tested on live production (my.bebang.ph) 2026-03-24/25 with real form submissions, POST captures, and financial math validation.

### Forms That Work End-to-End

| Form | Status | Financial Math | Evidence |
|------|--------|---------------|----------|
| Purchase Requisition | PASS | Total: 10×84 + 5×195 = P1,815 correct | PR-2026-02988 created |
| Purchase Order | PASS | VAT 12%: P1,000 × 0.12 = P120 correct | PO-2026-02989 created |
| Goods Receipt | PASS | Qty validation, over-delivery protection works | GR-2026-02990 created |
| Invoice | PASS | VAT P26,400 on P220K subtotal correct, 3-way match P672K | INV-2026-03020 created |
| Payment Request | PASS | Limited to payable received value (audit control 2.3) | PAY-2026-03021 created |
| Supplier | PASS | Auto-gen code SUPP-{timestamp} works | TEST-S116-FINANCIAL-6697 |

### Pages That Work

All 9 procurement pages load with data:
- Dashboard (KPIs: P5.1M outstanding, P5.0M overdue, P37.5M MTD PO value)
- Purchase Requisitions (499 PRs)
- Purchase Orders (PO list + 41 pending approval)
- Goods Receipts (1,026 records)
- Invoices (52 records, 3-way match visible)
- Payments (42 records)
- Suppliers (145 suppliers)
- OR Follow-up (1 overdue entry, P250K, 81 days)
- Reports (7 reports render with data)

### Features Confirmed Working

- Smart Pricing auto-fill (RM001 → P195 contracted price)
- VAT auto-calculation based on supplier profile (12% for VAT Registered)
- Department dropdown fetches from API (not hardcoded)
- UOM dropdown fetches from API (29 options vs 14 hardcoded)
- Over-delivery protection (5% tolerance, configurable)
- Duplicate invoice detection
- PO auto-send on approval (supplier email required)
- Google Chat notifications for approvals
- OR Follow-up with escalation tracking
- Warehouse RBAC for GR access

---

## Part 2: Defects Fixed (S107–S116)

| Sprint | Defect | Fix |
|--------|--------|-----|
| S107 | Department dropdown sends "Commissary" instead of "Commissary - BEI" | API returns {value: Link ID, label: display name} |
| S107 | UOM dropdown hardcoded to 14 options | Fetches all 29 from API |
| S107 | No price auto-fill on item_code | onBlur handler calls get_item_last_price |
| S107 | Qty field NaN on input | Safe Number() conversion |
| S108 | PR creation MandatoryError (date_required, purpose, requested_by) | Backend auto-sets all mandatory defaults |
| S108 | Frontend sends "justification" but DocType field is "purpose" | Frontend maps justification→purpose |
| S112 | OR Follow-up missing from sidebar | Added with overdue badge |
| S112 | WAREHOUSE_USER excluded from PROCUREMENT module | Added to roles.ts |
| S112 | Supplier code doesn't auto-generate | SUPP-{timestamp} auto-gen in backend |
| S112 | Empty error toast on every page | Hook retry:0, double-toast fix |
| S116 | Invoice redirect to /invoices/undefined | Null-check result.name, fallback to list |
| S116 | PO approval dialog stays open on RBAC error | Close dialog in catch block |
| S116 | Supplier "Total Orders" shows PNaN | Null coalesce ?? 0 |

---

## Part 3: Open Defects (Not Yet Fixed)

| # | Severity | Defect | Impact on Luwi | Source |
|---|----------|--------|----------------|--------|
| 1 | MEDIUM | Invoice badge "Variance Detected" but 3-way match text says "All amounts match" — stale `match_status` field | Luwi investigates non-existent variances, wastes time | S116 Agent 2 |
| 2 | MEDIUM | Invoice verification requires file attachment before "Submit for Verification" works — no inline error, just blocks silently | Luwi creates invoice, can't proceed, doesn't know why | S116 chain test |
| 3 | LOW | No EWT field visible in invoice form UI — training guide promises it | Luwi expects to see withholding tax on invoices | S116 Agent 2 |
| 4 | LOW | PO search combobox in invoice form filters by status — "Partially Received" POs don't appear | Luwi can't find POs for partial deliveries | S116 chain test |
| 5 | INFO | Payment amount limited to "payable received value" (audit control 2.3) with no explanation on screen | Luwi enters invoice total, gets rejected, confused | S116 chain test |
| 6 | INFO | PO Summary and AP Aging reports link to hq.bebang.ph (Frappe native), not embedded | Context switch for Luwi — leaves my.bebang.ph for 2 reports | S116 Agent 4 |

---

## Part 4: Operational Bottlenecks (High-Volume Problems)

These are not bugs — they're design gaps that become painful at 100+ transactions/day.

### BOTTLENECK 1: No Bulk/Batch Operations

**Problem:** Every PO, GR, invoice, and payment is created one at a time. At 100+ daily:
- Creating 50 POs = 50 form fills, ~2 hours of repetitive work
- Recording 30 GRs = 30 form fills
- Each requires page navigation, dropdown selection, manual data entry

**Current flow (per PO):**
```
Navigate to PO list → Click New PO → Select supplier → Add item 1 →
Add item 2 → ... → Add item N → Review totals → Click Create →
Wait for response → Verify redirect → Back to list → Repeat
```

**Recommendations to discuss:**
- [ ] **Bulk PO from Excel/CSV upload** — upload a spreadsheet with supplier, items, qty, price → batch-create 50 POs in one action
- [ ] **PO templates** — save "Weekly Commissary Restock" as a template with items pre-filled, reuse with qty adjustments
- [ ] **Duplicate PO** — copy button on PO detail that pre-fills a new PO with same supplier + items
- [ ] **Quick GR from PO** — when PO is fully received, one-click "Received as ordered" instead of filling each qty

**Questions for Sam/Mae/Luwi:**
1. How many POs does Luwi create per day on average? Per week?
2. Are there recurring POs (same supplier, same items, different quantities)?
3. Would Excel upload be preferred over templates?
4. Does Luwi often receive partial deliveries, or are most deliveries complete?

---

### BOTTLENECK 2: Approval Single Point of Failure

**Problem:** Mae Karazi is the ONLY CPO approver. No delegate, no batch approval.

**Current state:**
- 41 POs pending Mae's approval (as of 2026-03-24 dashboard)
- Each approval = open PO → read details → click Approve → type comment → confirm
- 41 × ~2 minutes each = ~80 minutes just for approvals
- If Mae is unavailable, all procurement stops

**Recommendations to discuss:**
- [ ] **Batch approval** — checkbox select multiple POs → "Approve Selected" button → one confirmation for all
- [ ] **Delegate approver** — Mae can temporarily assign approval authority to Luwi or Cayla for POs under a threshold (e.g., P100K)
- [ ] **Auto-approve for established suppliers under threshold** — if supplier is 30+ days old AND PO is under P50K, auto-approve without Mae
- [ ] **Escalation timer** — if Mae hasn't approved within 4 hours (not 24), auto-escalate to Butch

**Questions for Sam/Mae:**
1. Is Mae comfortable with batch approval (reviewing a list then approving all at once)?
2. Should there be a delegate when Mae is out? Who?
3. Would auto-approve for small POs with established suppliers be acceptable?
4. Is the 24-hour reminder timer too slow? What's the right escalation time?

---

### BOTTLENECK 3: No "What Do I Do Today?" Queue

**Problem:** Luwi checks 6 separate pages daily to find her work. No unified inbox.

**Current daily routine:**
```
1. Check PR list → any new PRs to convert to POs?
2. Check PO list → any approved POs to send?
3. Check GR list → any deliveries to record?
4. Check Invoice list → any invoices to process?
5. Check Payment list → any payments to submit?
6. Check OR Follow-up → any missing receipts to chase?
```

**Recommendations to discuss:**
- [ ] **Procurement Inbox/Task Queue** — single page showing:
  - "You have 12 PRs to process" (link to filtered PR list)
  - "5 deliveries expected today" (from PO delivery dates)
  - "8 invoices pending verification"
  - "3 payment requests ready to create"
  - "2 ORs overdue > 14 days"
  - "41 POs waiting for Mae's approval" (visible to Mae)
- [ ] **Dashboard quick actions already exist** — but they're generic. Make them contextual: "3 urgent items" not just "New PO"
- [ ] **Daily email digest** — automated morning summary via Google Chat or email

**Questions for Luwi:**
1. What's the first thing you check when you log in?
2. How much time do you spend navigating between pages vs doing actual work?
3. Would a morning summary (Chat message or email) listing today's tasks be useful?

---

### BOTTLENECK 4: GR → Invoice → Payment Is Three Separate Workflows

**Problem:** When a supplier delivers goods + invoice simultaneously (common), Luwi must navigate 3 pages and fill 3 forms.

**Current flow:**
```
Page 1: Create GR (select PO, fill qty, upload delivery note)
Page 2: Create Invoice (select same PO, type invoice#, dates, upload invoice scan)
Page 3: Wait for verification → Create Payment Request
```

**Recommendations to discuss:**
- [ ] **"Record Delivery" combined flow** — single page:
  1. Select PO → items auto-populate
  2. Fill received qty (GR part)
  3. Enter supplier invoice # + date (Invoice part)
  4. Upload scanned invoice (required for verification)
  5. Click "Record Delivery" → system creates GR + Invoice in one action
  6. Auto-routes invoice for verification
- [ ] **Quick payment after verification** — when invoice reaches "Verified", show a "Create Payment" button directly on the invoice detail (instead of navigating to Payments > New)

**Questions for Sam/Mae:**
1. How often do suppliers deliver goods + invoice at the same time?
2. Would combining GR + Invoice into one form save significant time?
3. Is there a compliance reason to keep them as separate workflows?

---

### BOTTLENECK 5: Invoice Verification Requires File Attachment (Hidden Blocker)

**Problem:** The system silently blocks invoice verification when no file is attached. No error message — just nothing happens.

**Testing evidence:** Invoice INV-2026-03020 was created via API, but `verify_invoice_match` returned `"Please attach the supplier invoice"`. The UI has no inline feedback for this.

**Recommendations to discuss:**
- [ ] **Make file upload REQUIRED on the invoice form** — not optional with a hidden post-save blocker
- [ ] **Show clear error** when verification is attempted without file: "Cannot verify: please attach supplier invoice first"
- [ ] **Invoice OCR** (future) — scan/photograph supplier invoice → auto-extract invoice#, date, line items, amounts → reduce manual data entry

**Questions for Sam:**
1. Is there a business reason the file is required? (Audit trail?)
2. Should we make it required on the form itself, or keep it optional but with clear feedback?

---

### BOTTLENECK 6: No Expected Deliveries View

**Problem:** Luwi doesn't know what deliveries to expect today. She reacts when suppliers show up rather than preparing in advance.

**Recommendations to discuss:**
- [ ] **Delivery Calendar** — weekly view showing expected deliveries from PO delivery dates
- [ ] **"Deliveries This Week" widget** on dashboard — supplier name, PO#, expected date, items
- [ ] **Late delivery alerts** — auto-flag POs past expected delivery date with no GR

**Questions for Luwi:**
1. Do suppliers usually deliver on the expected date?
2. How far in advance do you need to know about deliveries?
3. Is there a warehouse team that needs this info too?

---

### BOTTLENECK 7: Payment Amount Confusion

**Problem:** Testing revealed that payment amount is limited to "payable received value" (GR qty × rate), not invoice total. This is correct for audit control, but the screen shows no explanation.

**Example from testing:**
- Invoice total: P5,000
- Payable received value: P560
- Luwi enters P5,000 → rejected → confused

**Recommendations to discuss:**
- [ ] **Auto-fill payment amount** with the correct payable value
- [ ] **Tooltip explaining** "Payment limited to P560 (received value per audit control 2.3). Invoice total is P5,000 — remaining P4,440 will be payable after additional goods are received."
- [ ] **Show the calculation breakdown** on the payment form: received qty × rate = payable amount

---

### BOTTLENECK 8: No Mobile Experience

**Problem:** Warehouse staff recording GRs at the dock need mobile. GR form is desktop-only.

**Recommendations to discuss:**
- [ ] **Mobile-responsive GR form** — works on phone/tablet at the dock
- [ ] **Camera integration** — photograph delivery note directly in the app
- [ ] **Barcode scanning** (future) — scan item barcodes to auto-fill received qty

**Questions for Sam:**
1. Does the warehouse team currently use phones/tablets for receiving?
2. Is mobile GR recording a priority or a nice-to-have?

---

## Part 5: Financial System Gaps

### GAP 1: EWT Not Visible on Invoice Form

**Finding:** The invoice form shows subtotal, VAT, and grand total — but no EWT (withholding tax) field. The training guide (Section 4) explicitly says EWT is calculated and deducted.

**Questions:**
- Is EWT calculated only at payment time (not invoice time)?
- Should the invoice show: "Subtotal + VAT - EWT = Grand Total"?
- Or is the current model correct: EWT only applies at payment?

### GAP 2: 3-Way Match Badge Inconsistency

**Finding:** Invoice INV-2026-00042 shows badge "Variance Detected" but text says "All amounts match — ready for payment processing." The `match_status` field appears stale.

**Fix needed:** When PO=GR=Invoice amounts match, badge should say "Matched" not "Variance Detected."

### GAP 3: Payment Term Tracking Not Visible

**Finding:** Training guide (Section 9) says the system warns about late payments based on supplier payment terms. No evidence of this warning appearing during testing.

**Questions:**
- Is payment term warning implemented?
- Where should it appear — on the payment form or the invoice detail?

---

## Part 6: Suggested Sprint Priorities

### Immediate (this week — before Luwi's volume ramps up)

| Priority | Item | Type | Effort |
|----------|------|------|--------|
| P0 | Fix 3-way match badge inconsistency | Bug fix | 1 unit |
| P0 | Show clear error when invoice file missing for verification | UX fix | 2 units |
| P0 | Auto-fill payment amount with payable received value | UX fix | 2 units |
| P0 | Show EWT on invoice or clarify it's payment-only | Clarify/fix | 2 units |
| P1 | Batch PO approval for Mae (select + approve multiple) | Feature | 8 units |

### Short-term (next 2 weeks)

| Priority | Item | Type | Effort |
|----------|------|------|--------|
| P1 | Procurement task queue / daily inbox | Feature | 12 units |
| P1 | Combined GR + Invoice form ("Record Delivery") | Feature | 15 units |
| P1 | PO templates for recurring orders | Feature | 8 units |
| P2 | PO duplicate/copy button | Feature | 3 units |
| P2 | Delivery calendar widget | Feature | 8 units |

### Medium-term (next month)

| Priority | Item | Type | Effort |
|----------|------|------|--------|
| P2 | Delegate approver for Mae (proxy approval) | Feature | 10 units |
| P2 | Bulk PO creation from Excel upload | Feature | 15 units |
| P2 | Auto-approve for small POs with established suppliers | Feature | 8 units |
| P3 | Mobile-responsive GR form | Feature | 12 units |
| P3 | Invoice OCR (scan → auto-fill) | Feature | 20+ units |

---

## Part 7: Open Questions for Brainstorm

1. **Volume reality check:** How many POs/GRs/invoices does Luwi process per day currently? Is "100+" accurate or is the actual volume lower?

2. **Approval delegation:** Is Mae comfortable delegating PO approval? What threshold would she accept? Does Butch need to approve every high-value PO, or could Mae solo-approve up to P1M?

3. **Combined GR+Invoice:** Is there a compliance/audit reason to keep GR and Invoice as separate forms? Or can we safely combine them?

4. **EWT timing:** When exactly should EWT be calculated — at PO creation, invoice creation, or payment creation? The training guide says PO, but testing shows it may only appear at payment.

5. **Supplier onboarding:** 20 suppliers have "Missing Documents" status. Is there a process to get them compliant? Should the system block POs for non-compliant suppliers?

6. **Report access:** PO Summary and AP Aging link to hq.bebang.ph. Should these be embedded in my.bebang.ph, or is the external link acceptable?

7. **Mobile priority:** Is mobile GR recording a real need, or do warehouse staff use laptops at the dock?

8. **OR Follow-up:** Only 1 entry visible (P250K, 81 days overdue). Is this feature actively used? Does Luwi actually chase ORs, or is it low priority?

---

## Appendix: Test Evidence Summary

| Sprint | Tests Run | Pass | Fail | Blocked | Key Achievement |
|--------|-----------|------|------|---------|-----------------|
| S107 | 6 | 6 | 0 | 0 | Department/UOM from API, price auto-fill |
| S108 | 3 | 3 | 0 | 0 | PR creation works end-to-end |
| S109 | 31 | 27 | 1 | 3 | All 6 forms + detail pages + reports tested |
| S112 | — | — | — | — | Sidebar, RBAC, supplier code, toast fixes (by parallel agent) |
| S116 | 19 | 18 | 0 | 1 | Financial validation, defect fixes, full chain |
| S116-chain | 4 | 4 | 0 | 0 | PO→GR→Invoice→Verify→Payment + Mae approval |
| **Total** | **63** | **58** | **1** | **4** | |

Fact-check score: 7.5/10 (PARTIALLY_TRUSTWORTHY — tests were real, evidence has minor hygiene issues with duplicate screenshots)
