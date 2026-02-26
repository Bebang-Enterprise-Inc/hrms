---
**Last Scanned:** 2026-02-23 | **Previous Scan:** 2026-02-17
**Commit:** 7b998877f | **Health Score:** 93% LIVE
---

# Department Feature Matrix: Expenses & PCF

## Summary

- Frontend pages: 9 (expense) + 4 (accounting review) = 13 total
- Backend endpoints: 28 total (26 LIVE, 2 PASS-THROUGH/STUB)
- DocTypes: 5 (BEI Expense Request, BEI PCF Batch, BEI PCF Batch Item, BEI Petty Cash Fund, BEI Expense Training Data)
- Health Score: 93% LIVE

## Feature Matrix

| Feature | Frontend Page | FE Status | Backend API | BE Status | Notes |
|---------|--------------|-----------|-------------|-----------|-------|
| Expense list | `/dashboard/expense` | LIVE | `expense.get_my_expenses` | LIVE | |
| Submit expense | `/dashboard/expense/submit` | LIVE | `expense.submit_expense` | LIVE | Base64 photo; background OCR via Gemini |
| Expense detail | `/dashboard/expense/[id]` | LIVE | `expense.get_expense_status` | LIVE | |
| Background OCR | (background job) | N/A | `expense.process_expense_background` | LIVE | Gemini 2.0 Flash → match score → AI classify |
| Receipt OCR | (internal) | N/A | `expense_ocr.extract_receipt_data` | LIVE | Requires gemini_api_key in site_config |
| AI Classification | (internal) | N/A | `expense_classifier.classify_expense` | LIVE | 3-tier: rule-based → ML → OpenAI GPT-3.5 |
| Accounting review dashboard | `/dashboard/accounting/expenses` | LIVE | `expense_review.get_review_dashboard` | LIVE | |
| Accounting review queue | `/dashboard/accounting/expenses/review` | LIVE | `expense_review.get_expenses_for_review` | LIVE | |
| Individual expense review | `/dashboard/accounting/expenses/[id]` | LIVE | `expense_review.approve_expense`, `reject_expense` | LIVE | Shows OCR data + match score + AI suggestion |
| Batch review | `/dashboard/accounting/expenses/batch` | LIVE | `pcf.approve_batch`, `reject_batch` | LIVE | |
| PCF status dashboard | `/dashboard/expense/pcf` | LIVE | `pcf.get_pcf_status` | LIVE | Threshold progress bar |
| PCF add expense | `/dashboard/expense/pcf/add` | LIVE | `pcf.add_expense_to_pending` | LIVE | |
| PCF pending list | `/dashboard/expense/pcf/pending` | LIVE | `pcf.get_my_pending_expenses` | LIVE | |
| PCF manual batch submit | PCF pending page (button) | LIVE | `pcf.submit_batch_now` | LIVE | Custodian only |
| PCF batch history | `/dashboard/expense/pcf/history` | LIVE | `pcf.get_batch_history` | LIVE | |
| PCF batch detail | `/dashboard/expense/pcf/history/[id]` | LIVE | `pcf.get_batch_details` | LIVE | |
| PCF request replenishment | Accounting batch page | LIVE | `pcf.request_replenishment` | LIVE | Sets flag only; no GL entry (GAP-036) |
| PCF create fund (admin) | — | UNKNOWN | `pcf.create_pcf_fund` | LIVE | **GAP-035: no admin frontend** |
| PCF update settings (admin) | — | UNKNOWN | `pcf.update_pcf_settings` | LIVE | **GAP-035: no admin frontend** |
| PCF assign custodian (admin) | — | UNKNOWN | `pcf.assign_pcf_custodian` | LIVE | **GAP-035: no admin frontend** |
| PCF threshold auto-submit | (scheduler) | N/A | `pcf.check_threshold_and_auto_submit` | LIVE | Hourly; Redis cache lock |
| PCF month-end auto-submit | (scheduler) | N/A | `pcf.check_month_end_auto_submit` | LIVE | Daily (day 29 of month) |

## DocType Relationships

| DocType | Link Fields | Child Tables | Submittable? |
|---------|-------------|-------------|--------------|
| BEI Expense Request | employee→Employee, store→Warehouse, batch→BEI PCF Batch, internal_final_coa→Account | None | No |
| BEI PCF Batch | store→Warehouse, company→Company, submitted_by→User | items (BEI PCF Batch Item) | No |
| BEI Petty Cash Fund | store→Warehouse, custodian→User, backup_custodian→User | None | No |
| BEI Expense Training Data | expense_reference→BEI Expense Request | None | No |

## Hooks & Scheduler Events

| Event | DocType | Handler | Purpose |
|-------|---------|---------|---------|
| on_update | BEI Expense Request | `pcf.on_expense_update` | Recalculates PCF totals |
| on_trash | BEI Expense Request | `pcf.on_expense_delete` | Recalculates PCF totals |
| validate | BEI PCF Batch | `pcf.validate_pcf_batch` | **PASS-THROUGH (GAP-095)** |
| on_update | BEI PCF Batch | `pcf.on_batch_update` | **PASS-THROUGH (GAP-096)** |
| hourly | Scheduler | `pcf.check_threshold_and_auto_submit` | Auto-submit |
| daily | Scheduler | `pcf.check_month_end_auto_submit` | Month-end sweep |

## Gaps Found

| ID | Feature | Blocker Type | Severity | Notes |
|----|---------|-------------|----------|-------|
| GAP-034 | ML model absent on EC2 | Deployment | High | .joblib file not deployed; falls to OpenAI or manual |
| GAP-035 | PCF admin panel: no frontend | Frontend | High | PCF setup requires Frappe Desk |
| GAP-036 | PCF replenishment lifecycle | Design | High | Flag only; no GL entry, no cheque tracking |
| GAP-095 | validate_pcf_batch hook is no-op | Code Quality | Low | Dead code |
| GAP-096 | on_batch_update hook is no-op | Code Quality | Low | Dead code |

## Improvements

| Feature | Current State | Suggested Improvement | Priority |
|---------|--------------|----------------------|----------|
| Batch replenishment workflow | Flag only | Add BEI PCF Replenishment DocType with full lifecycle | HIGH |
| ML model retrain | Manual bench command only | Monthly scheduler retrain when >50 corrections | MEDIUM |
| Receipt photo compression | Raw base64 (3-8MB) | Add client-side canvas compression before encode | HIGH |
| Classification accuracy tracking | Corrections stored but no dashboard | Add monthly accuracy report by classification method | MEDIUM |
