# Flow 07: Daily Store Cycle
**Departments:** Store Staff → Store Supervisor → Finance (verification) | **Scanned:** 2026-02-23 | **Agent:** flow-tracer-3

## Flow Diagram (Mermaid)

```mermaid
sequenceDiagram
    participant Staff as Store Staff/OIC
    participant OpenPage as /store-ops/opening
    participant MidPage as /store-ops/midshift
    participant HandPage as /store-ops/handover
    participant ClosePage as /store-ops/closing
    participant PosPage as /store-ops/pos
    participant DepPage as /store-ops/deposit
    participant StoreAPI as store.py API
    participant SupAPI as supervisor.py API
    participant BillingAPI as billing.py (monthly)
    participant OpenDT as BEI Store Opening Report
    participant CloseDT as BEI Store Closing Report
    participant PosDT as BEI POS Upload
    participant DepDT as BEI Bank Deposit
    participant Sup as Area Supervisor
    participant FeedPage as /supervisor/reports-feed
    participant Finance as Finance/Billing

    Staff->>OpenPage: Open store, fill 22-item checklist + 5 photos
    OpenPage->>StoreAPI: submit_opening_report()
    StoreAPI->>OpenDT: INSERT (status=Submitted)
    OpenPage-->>Staff: Success

    Staff->>MidPage: 3–4 PM window: fill midshift check
    MidPage->>StoreAPI: submit_midshift_check()
    StoreAPI->>OpenDT: Midshift checklist created (BEI Mid Shift Handover)

    Staff->>HandPage: Cashier handover — signature + X-reading photo
    HandPage->>StoreAPI: submit_mid_shift_handover()
    StoreAPI->>OpenDT: BEI Mid Shift Handover INSERT

    Staff->>ClosePage: Stage 1: Cash count, petty cash, delivery fund
    ClosePage->>StoreAPI: get_or_create_closing_report() then submit_closing_stage1_cash()
    StoreAPI->>CloseDT: Stage 1 saved (cash_variance computed)

    Staff->>ClosePage: Stage 2: Inventory spot check + checklist
    ClosePage->>StoreAPI: submit_closing_stage2_checklist()
    StoreAPI->>CloseDT: Stage 2 saved

    Staff->>ClosePage: Stage 3: X/Z-reading photos + store area photos
    ClosePage->>StoreAPI: submit_closing_stage3_photos()
    StoreAPI->>CloseDT: stage_completed=3, auto-links POS Upload if found, status=Submitted

    Staff->>PosPage: Upload 5 POS files (base64): Discount, Transaction, Product Mix, Daily Sales, Sales Summary
    PosPage->>StoreAPI: upload_pos_data()
    StoreAPI->>PosDT: INSERT; date mismatch detection via pos_parser; no Supabase sync triggered

    Staff->>DepPage: Submit bank deposit entries + photos
    DepPage->>StoreAPI: submit_bank_deposit()
    StoreAPI->>DepDT: INSERT (BEI Bank Deposit + entries + photos)

    Sup->>FeedPage: Load reports feed for today
    FeedPage->>SupAPI: get_reports_feed() — aggregates 5 report types chronologically
    FeedPage->>SupAPI: get_stores_compliance_summary() — who submitted/missed
    SupAPI-->>Sup: Combined feed: opening, closing, midshift, POS, deposit per store

    Sup->>FeedPage: Mark report as Reviewed or Flag for revision
    FeedPage->>SupAPI: mark_report_reviewed() / request_report_revision()
    SupAPI->>CloseDT: status=Reviewed or status=Flagged
    SupAPI-->>Staff: GChat notification if Flagged (revision_notes sent)

    Finance->>BillingAPI: (1st of month, 6AM cron) scheduled_monthly_billing()
    BillingAPI->>CloseDT: SQL aggregate gross_sales/net_sales from all closing reports for prior month
    BillingAPI->>Finance: BEI Billing Schedule created (Draft) per store
```

## Step-by-Step Trace

| Step | Actor | Action | Frontend Page | API Endpoint | DocType Created/Updated | Status |
|------|-------|--------|---------------|-------------|------------------------|--------|
| 1 | Store Staff | Resolve store identity | Auto (hook) | `store.get_user_store` | Warehouse (read) | LIVE |
| 2 | Store Staff | Complete 22-item opening checklist + 5 required photos with watermarks | `/dashboard/store-ops/opening` | `store.submit_opening_report` | BEI Store Opening Report (INSERT), bei_opening_checklist_item (child) | LIVE |
| 3 | Store Staff | Mid-shift check (3–4 PM gate on frontend only) | `/dashboard/store-ops/midshift` | `store.submit_midshift_check` | BEI Mid Shift Handover, BEI Midshift Checklist (child) | LIVE |
| 4 | Store Staff | Cashier handover — X-reading photo + signature capture | `/dashboard/store-ops/handover` | `store.submit_mid_shift_handover` | BEI Mid Shift Handover (UPDATE — same DocType as midshift) | LIVE |
| 5 | Store Staff | Closing Stage 1: Cash count entry (gross cash, petty cash, delivery fund) — cash_variance auto-computed | `/dashboard/store-ops/closing` | `store.get_or_create_closing_report`, `store.submit_closing_stage1_cash` | BEI Store Closing Report (CREATE then UPDATE stage 1) | LIVE |
| 6 | Store Staff | Closing Stage 2: Inventory spot check + 21-item closing checklist | `/dashboard/store-ops/closing` | `store.submit_closing_stage2_checklist` | BEI Store Closing Report (UPDATE stage 2), bei_closing_checklist_item, bei_inventory_spot_check_item | LIVE |
| 7 | Store Staff | Closing Stage 3: X-reading + Z-reading photos + 10 store area photos + equipment temps. Auto-links today's POS Upload if found. | `/dashboard/store-ops/closing` | `store.submit_closing_stage3_photos` | BEI Store Closing Report (UPDATE stage 3 — stage_completed=3, pos_upload auto-linked) | LIVE |
| 8 | Store Staff | Upload 5 POS report files (base64). Date mismatch detection via pos_parser compares claimed date vs. Sales Summary file date. Mismatch tags doc with `has_date_mismatch=1` but does NOT block upload. | `/dashboard/store-ops/pos` | `store.upload_pos_data` | BEI POS Upload (INSERT — 5 files saved as Frappe File attachments) | LIVE |
| 9 | Store Staff | Submit bank deposit slip(s) + photos | `/dashboard/store-ops/deposit` | `store.submit_bank_deposit` | BEI Bank Deposit (INSERT), BEI Bank Deposit Entry (child), BEI Bank Deposit Photo (child) | LIVE |
| 10 | Area Supervisor | Load today's reports feed: chronological view of all 5 report types across all stores in area | `/dashboard/supervisor/reports-feed` | `supervisor.get_reports_feed` | Reads: Opening, Closing, Midshift, POS Upload, Bank Deposit (no write) | LIVE |
| 11 | Area Supervisor | Check compliance summary — which stores submitted/missed opening and closing | `/dashboard/supervisor/reports-feed` | `supervisor.get_stores_compliance_summary` | Reads: BEI Store Opening/Closing Report | LIVE |
| 12 | Area Supervisor | Review opening or closing report; mark Reviewed | `/dashboard/supervisor/reports-feed` | `supervisor.mark_report_reviewed` | BEI Store Opening/Closing Report (status=Reviewed; Frappe Comment added) | LIVE |
| 13 | Area Supervisor | Flag report for revision with notes | `/dashboard/supervisor/reports-feed` | `supervisor.request_report_revision` | BEI Store Opening/Closing Report (status=Flagged); GChat notification to submitter | LIVE |
| 14 | Area Supervisor | View cash variance flagged reports (threshold PHP 100) | `/dashboard/supervisor/reports-feed` | `supervisor.get_variance_flagged_reports` | Reads: BEI Store Closing Report (|variance| > 100) | LIVE |
| 15 | Finance Cron | 1st of every month at 6 AM: aggregate prior month's closing reports per store; create BEI Billing Schedule (Draft) with gross_sales, net_sales, maintenance charges rolled in | Scheduled (no UI trigger) | `billing.scheduled_monthly_billing` → `billing.generate_monthly_billing` | BEI Billing Schedule (INSERT per store with sales from BEI Store Closing Report SQL aggregate; `docstatus=1` closing reports only) | LIVE |

## Handoff Points

| From Dept | To Dept | Trigger | Mechanism | Status |
|-----------|---------|---------|-----------|--------|
| Store Staff | Area Supervisor | Closing report Stage 3 completion sets status=Submitted | No push notification; supervisor must poll `/reports-feed` | PARTIAL — passive polling, no active alert |
| Store Staff | Area Supervisor | POS upload completion | No notification; upload appears in feed | PASSIVE |
| Store Staff | Area Supervisor | Bank deposit submission | No notification; deposit appears in feed | PASSIVE |
| Area Supervisor | Store Staff | Report flagged for revision | `request_report_revision` → Google Chat notification to submitter | LIVE |
| Store Closing Reports | Finance (billing) | Monthly cron (1st of month, 6 AM) reads all submitted (`docstatus=1`) closing reports for prior month | Scheduled job: `scheduled_monthly_billing` SQL aggregate on `tabBEI Store Closing Report` | LIVE — but only reads docstatus=1 (submitted) docs; BEI Store Closing Report is NOT submittable (status-driven only, no docstatus) — this creates a MISMATCH |
| Maintenance Dept | Finance (billing) | Monthly billing includes `charge_to_store=1` maintenance costs | `generate_monthly_billing` queries `tabBEI Maintenance Request` for `billing_status IS NULL OR billing_status = 'Not Billed'` and rolls them into billing line item | LIVE |

## Broken Links / Gaps

| ID | Location | Problem | Impact | Severity |
|----|----------|---------|--------|----------|
| FL07-BL01 | `billing.generate_monthly_billing` line 275 | Queries BEI Store Closing Report with `docstatus = 1` but BEI Store Closing Report is NOT a submittable DocType (it is status-driven only). No closing report will ever have `docstatus = 1`. Finance monthly billing reads zero closing report data every month. | Monthly billing grossly undercounts or misses store sales data for all stores | CRITICAL |
| FL07-BL02 | `store.submit_midshift_check` | Frontend enforces 3–4 PM time gate; backend has no corresponding validation. Direct API call bypasses gate. | Midshift reports can be submitted at any time via API; compliance data is unreliable | LOW |
| FL07-BL03 | `store.upload_pos_data` | POS data is stored in BEI POS Upload as Frappe File attachments only. No sync to Supabase, no parsing of sales figures into structured fields (`gross_sales`, `net_sales` fields exist on DocType per `get_pos_uploads` return but are never populated by `upload_pos_data`). | Closing report Stage 3 auto-links POS Upload by name, but the `pos_total_sales` field the supervisor sees in the feed comes from the closing report's own cash count — not parsed from POS files. Supabase has no record of POS uploads from the app. | HIGH |
| FL07-BL04 | `supervisor.get_area_store_reports` (report_type=pos_upload) | Returns `gross_sales`, `net_sales`, `transaction_count` from BEI POS Upload. These fields are never written by `upload_pos_data`. Supervisor sees null/0 for POS metrics in the feed. | Supervisor sees empty sales figures from POS upload records | HIGH |
| FL07-BL05 | `supervisor.mark_report_reviewed` / `request_report_revision` | Only works for BEI Store Opening Report and BEI Store Closing Report. POS Upload and Bank Deposit records have no review/flag mechanism. Supervisor cannot mark POS upload or deposit as reviewed. | Supervisor approval workflow incomplete for POS and deposit step | MEDIUM |
| FL07-BL06 | `store.submit_bank_deposit` | Bank deposit has no link to BEI Store Closing Report. Bank deposit data is standalone; Finance and the monthly billing generator do not read bank deposit records for reconciliation or billing input. | Daily cash reconciliation (closing cash vs. bank deposit) is not automated; purely manual check | MEDIUM |
| FL07-BL07 | No dedicated supervisor landing page (SUP-G01 from dept scan) | `get_area_dashboard` is loaded from visits page dual-mode. Supervisor must navigate to visits page to see opening/closing report counts. There is no area supervisor home page. | UX gap; supervisors have no focused daily operations view | HIGH |

## Error Paths

| Trigger | What Happens | User Experience | Status |
|---------|-------------|----------------|--------|
| POS upload — date mismatch (file date ≠ claimed date) | `frappe.log_error` is called; doc gets `has_date_mismatch=1`; upload proceeds with warning | Frontend receives `warning` and `date_mismatch: true` in response; date mismatch confirmation modal shown before submission | LIVE — modal shown; Finance cannot currently filter mismatch docs (no FE page for it) |
| Opening/Closing photo fails base64 decode | `save_base64_image` → `frappe.throw("Invalid image data")` | User gets error; form submission blocked | LIVE |
| Closing Stage 3 — missing required photo (X-read or Z-read) | `frappe.throw(_("X-Reading Opening photo is required"), title=_("Missing Photo"))` | User sees validation error | LIVE |
| Bank deposit — `store` not resolvable via `resolve_warehouse()` | `frappe.throw(_("Could not find Store: {0}"))` | User sees error; deposit not saved | LIVE |
| Monthly billing cron — store has no closing reports | `if not sales_data.gross_sales and not sales_data.net_sales: skipped += 1` | Store is silently skipped; no billing generated; no alert | PARTIALLY HANDLED — no operator notification when stores are skipped |
| Monthly billing cron — savepoint rollback | Per-store `savepoint` + `frappe.db.rollback(save_point)` | Error is appended to `errors[]` list; `frappe.log_error` called | LIVE — errors logged but no GChat alert |
| `request_report_revision` — `send_notification` to submitter | Calls GChat notification on submitter; if GChat not configured, falls back silently | If GChat unconfigured, revision flag is set but submitter receives no notification | Silently degrades |

## Improvement Suggestions

1. **FL07-BL01 CRITICAL FIX**: Change the `billing.generate_monthly_billing` query from `docstatus = 1` to `status = 'Submitted'` (or remove the docstatus filter entirely) since BEI Store Closing Report is status-driven and never has `docstatus = 1`. Alternatively, mark BEI Store Closing Report as submittable and call `doc.submit()` when Stage 3 completes.

2. **FL07-BL03 — POS Structured Parsing**: After POS file upload, parse the 5 files asynchronously (frappe.enqueue) using `hrms.utils.pos_parser` to extract `gross_sales`, `net_sales`, `transaction_count`, `void_count`, `discount_amount` and store them as numeric fields on BEI POS Upload. This enables the supervisor reports feed to show real POS metrics.

3. **FL07-BL03 — Supabase Sync**: The daily POS sync GitHub Action (`scripts/sync_scm_daily.bat`) runs independently of the in-app POS upload. These two data flows (direct API upload vs. scheduled Supabase sync) are not reconciled. Document the canonical source for Finance reporting.

4. **Supervisor Push Notifications**: When a store completes closing Stage 3 (stage_completed=3), send a GChat notification to the area supervisor. Currently supervisors must manually poll the reports feed.

5. **Bank Deposit Reconciliation**: Link BEI Bank Deposit to BEI Store Closing Report (add `closing_report` Link field). Add a reconciliation check in the supervisor feed: compare closing cash count vs. deposit total.

6. **POS / Deposit Review Actions**: Extend `mark_report_reviewed` and `request_report_revision` to support BEI POS Upload and BEI Bank Deposit doctypes (add them to the allowed doctypes list in supervisor.py).
