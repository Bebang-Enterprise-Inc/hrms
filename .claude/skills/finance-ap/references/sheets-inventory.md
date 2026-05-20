# Sheets Inventory

Every Google Sheet and Doc that touches the BEI AP system. Use this when you need an ID, a tab name, an owner, or to know whether a sheet is live or archived.

## Live sheets (do not retire)

### L1 — BEI AP Master (the register)
- **Drive name:** `AP Suppliers - Payment Status (Auto-View)` (planned rename to `BEI AP Master`)
- **ID:** `1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c`
- **URL:** https://docs.google.com/spreadsheets/d/1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c/edit
- **Owner:** sam@bebang.ph
- **Created:** 2026-04-16 13:23 PHT
- **Last modified:** Hourly by script (most recent: 2026-05-12 09:12 PHT)
- **Tab count:** 17
- **Tabs:** see `ap-master-structure.md`
- **Apps Script bound:** Yes (v3 field-sync — see `script-v3.md`)

### L2 — FINANCE PAYMENT MONITORING (FPM)
- **Drive name:** `FINANCE PAYMENT MONITORING`
- **ID:** `1t4wJLiAfIMJm6fe-x6h4eZn_S_Lx1AGN5ORd5Ywhcyw`
- **URL:** https://docs.google.com/spreadsheets/d/1t4wJLiAfIMJm6fe-x6h4eZn_S_Lx1AGN5ORd5Ywhcyw/edit
- **Owner:** denise@bebang.ph (previously juanna@bebang.ph until 2026-04-27)
- **Created:** 2026-02-22 05:13 PHT
- **Last modified:** 2026-05-12 09:24 PHT (Denise updates throughout the day)
- **Key tab:** `RFP Summary` — read by AP Master script
- **Role:** RFP approval pipeline, payment status, BDO check clearing (weekly reconciliation tags `Paid/ Cleared` + `BDO Cleared Date`)

### L3 — Procurement Compliance AppSheet Database
- **Drive name:** `Procurement Compliance Appsheet Database`
- **ID:** `1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q`
- **URL:** https://docs.google.com/spreadsheets/d/1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q/edit
- **Owner:** sam@bebang.ph
- **Modified:** Daily (Cayla / Luwi tag VAT and EWT)
- **Key tabs:** `PO Items` (PO-level VAT totals), `Advance Invoices` (per-invoice EWT)
- **Read by:** AP Master v3 script's `syncTaxFieldsFromCompliance_()` and the Procurement Sheets Receiver (separate Python sync to Frappe — see `/procurement` skill)

### L4 — Bebang - Project Cost Monitoring (PCM)
- **Drive name:** `Bebang - Project Cost Monitoring (native)`
- **ID:** `1_5BSZeNL9A_o5QO6WD4L42gGjYY6-yCDfgTp01y0fpo`
- **URL:** https://docs.google.com/spreadsheets/d/1_5BSZeNL9A_o5QO6WD4L42gGjYY6-yCDfgTp01y0fpo/edit
- **Owner:** sam@bebang.ph
- **Created:** 2026-04-20 11:07 PHT (native Sheets version replaced the old uploaded XLSX)
- **Tab count:** 67 (one per store + SUMMARY + FUND RESERVES + `_CAPEX_FROM_AP_MASTER` + `_AUDIT_RECONCILIATION`)
- **Key live-feed tabs:** `_CAPEX_FROM_AP_MASTER` (5000×25) pulls CAPEX rows from AP Master; `_AUDIT_RECONCILIATION` (2000×8)
- **Owner role:** Angela — types top section per store (budget); bottom section auto-fills from AP Master

### L5 — BGF, INVESTMENTS and CAPEX
- **Drive name:** `BGF, INVESTMENTS and CAPEX (native)`
- **ID:** `1dfIyAeGH_5ga_mjA1o-WWN9xM6VO3v7XKKoU1Jtq1eI`
- **URL:** https://docs.google.com/spreadsheets/d/1dfIyAeGH_5ga_mjA1o-WWN9xM6VO3v7XKKoU1Jtq1eI/edit
- **Owner:** (none — orphaned after Juanna)
- **Tab count:** 6 — `Reserved Funds`, `AS OF NOV 19`, `BGF`, `Franchise Fee`, etc.
- **Role:** Standalone — Partner Reserve, Franchise Fee, BGF capital tracking (Angela)
- **Does NOT feed AP Master**

### L6 — BEI Bank Balances — LIVE
- **Drive name:** `BEI Bank Balances — LIVE`
- **ID:** `19kSR8HQdveZVleMZORGQetHXVCxaeDy6EMlKfe2G77w`
- **URL:** https://docs.google.com/spreadsheets/d/19kSR8HQdveZVleMZORGQetHXVCxaeDy6EMlKfe2G77w/edit
- **Owner:** sam@bebang.ph
- **Created:** 2026-04-17 02:03 PHT
- **Tab count:** 1 — `Bank Accounts` (1100×110, 58 BEI bank accounts)
- **Role:** Denise updates daily balance per account; Cashflow Tracker reads this

### L7 — CASHFLOW TRACKER — CEO
- **Drive name:** `CASHFLOW TRACKER — CEO`
- **ID:** `1W2GERTwbODqfbHM70XpJJEtFwL-jIPbb2zzwC0Rcfeg`
- **URL:** https://docs.google.com/spreadsheets/d/1W2GERTwbODqfbHM70XpJJEtFwL-jIPbb2zzwC0Rcfeg/edit
- **Owner:** sam@bebang.ph
- **Created:** 2026-04-17 01:12 PHT
- **Tab count:** 4 — `01 - Today's Position`, `02 - This Week`, `03 - 8-Week Forecast`, `04 - Top Actions Today`
- **Role:** CEO dashboard. Reads Bank Balances + AP Master + FPM. Has its own bound Apps Script (`cashflow_hourly_sync.gs` in `CEO/CashFlow/`)

## Archived sheets (read-only references — DO NOT type new entries)

### A1 — 05 - AP Opening Balance (PHP 24.4M)
- **Drive name:** `05 -  AP Opening Balance(PHP 24.4M)` (note the double space)
- **ID:** `1ZHe2VoAFa94ET4I68C1jWM7nMzTdTCvttwZbICaLtB4`
- **URL:** https://docs.google.com/spreadsheets/d/1ZHe2VoAFa94ET4I68C1jWM7nMzTdTCvttwZbICaLtB4/edit
- **Owner:** (none — orphaned)
- **Created:** 2026-01-21 14:44 PHT
- **Last modified:** 2026-05-12 05:10 PHT (Denise is still touching it — should NOT be)
- **Tab count:** 3 — `SUPPLIERS SOA` (1520×33), `Sheet7`, `AP AGING PER SUPPLIER` (1355×26 — TOTAL PAYABLES ₱59.5M as of today)
- **Was retired:** 2026-04-21 (S211 cutover)
- **Why kept:** Opening balance baseline + AP AGING PER SUPPLIER (legacy live view that team still trusts)

### A2 — 05 - AP Opening Balance Head Office
- **ID:** `1jSwZRyIPisU4jiKS-Tn9VFoLukQI8UNoW13Hoov-75Y`
- **URL:** https://docs.google.com/spreadsheets/d/1jSwZRyIPisU4jiKS-Tn9VFoLukQI8UNoW13Hoov-75Y/edit
- **Owner:** (none — orphaned)
- **Created:** 2026-02-27 05:39 PHT
- **Last modified:** 2026-05-12 06:10 PHT (Roberose touched it today — should NOT be)
- **Tab count:** 1 — `Detailed HEAD OFFICE` (2560×35)
- **Was retired:** 2026-04-21 (data migrated to AP Master `Head Office` + `CAPEX` tabs)

### A3 — STORES REPLENISHMENTS RECON Y2026
- **ID:** `19qfXxz7N67oNcys9lb7XnmNzZCSpEdWQWXbRxaVTKN8`
- **URL:** https://docs.google.com/spreadsheets/d/19qfXxz7N67oNcys9lb7XnmNzZCSpEdWQWXbRxaVTKN8/edit
- **Owner:** (none — orphaned)
- **Created:** 2026-02-04 03:39 PHT
- **Last modified:** 2026-05-12 08:04 PHT (still being edited — needs review)
- **Tab count:** 50 (one per store, plus STORE SUMMARY and STORE DIRECTORY)
- **Was retired:** 2026-04-21 — Liezel's intercompany cash reconciliation, NOT third-party AP. **Should not have been put in AP Master scope at all.**

### A4 — CHECK DISBURSEMENT TRACKER
- **ID:** unknown (referenced in Team Guide as "stale since Jan 8")
- **Owner:** Denise (was)
- **Was retired:** 2026-04-21 — replaced by BDO weekly reconciliation script (`scripts/weekly_bdo_reconciliation.py`)

## Supporting docs (training guides)

All created 2026-04-21 by Sam:

| Doc | ID | Audience |
|---|---|---|
| BEI AP Master - Team Guide | `1HM60vlRn_1ZE0K5TmX_mPgooR8U0q_xdjvqgZhtN5JI` | Ms. Mel, Denise, Angela, Cayla, Luwi |
| Card 2 - Filing CAPEX Invoice (Ms. Mel) | `1RJM-D-mD2ulflB6odtKXObN8vjteYGzvpTobzLcIhbk` | Ms. Mel |
| Card 3 - Your PCM Workbook (Angela) | `1nfFqae_d-LwKUA47xIMf-Bt5OZFhaAZCg5y95eWtZkY` | Angela |
| Card - Finance + Compliance (Juanna Denise Cayla Luwi) | `1VPDdnra8oPc-agLcAj-XV_OD2rM2ztiAxzFwdT_-wTo` | Denise, Cayla, Luwi |
| BEI AP Flow Diagram | `1F6IzUYzHE2G2cVyU9x07GH_D9wohXKUr` (PNG) | Reference |
| BEI Receiving — Team Playbook | `1XOBZ1J4SO_OAkh9AG1UiB9V1wdvTDuF_ncGk60VSbBs` | Cayla, Ian, Denise (S210 sprint) |
| BEI Deliveries — 3PL Dock Card | `1zlb5ZAXmyN1Y_HaXOJl_rNc-6cXy-Q1d2Uw3xbIq5EY` | 3MD + Pinnacle dock staff |
| BEI Supplier SI Upload — FAQ | `1YERz3hHrekYoOVORTnRTumjjnMRch0hjVjLyFe3Qd9A` | 98 suppliers |

## Other connected services (not Google Sheets)

- **Sheets Receiver** (Python on EC2) — syncs FPM, Compliance, AP Opening into Frappe `Purchase Invoice` via webhook. Code in `hrms/services/sheets_receiver/`. See `/procurement` skill for details.
- **BDO Weekly Reconciliation** (Python in GitHub Actions) — `scripts/weekly_bdo_reconciliation.py`. Scans BDO weekly XLSX uploads → matches check numbers → flips FPM rows to `Paid/ Cleared`. Runs Tue-Fri 07:00 PHT. The 2026-05-01 catchup processed 32 rows worth ₱7.18M.
- **Frappe Purchase Invoice** — destination DocType for the `sync_ap_opening` endpoint. Receiver key: `ap_opening_balance`. See `/procurement` skill.

## Quick lookups

**"I need to type a new inventory supplier invoice"** → AP Master → `Suppliers SOA` tab.
**"I need to update a payment status"** → FPM → `RFP Summary` tab (NOT AP Master).
**"I need to fix VAT/EWT"** → Compliance AppSheet (NOT AP Master).
**"I need to see what we owe a specific supplier"** → AP Master → `All Liabilities` tab → filter Payee. (Or `AP AGING PER SUPPLIER` on archived A1 for the legacy aging view.)
**"I need to see today's bank position"** → Cashflow Tracker → tab `01 - Today's Position`.
**"I need to see how much we owe overall, with aging"** → archived A1's `AP AGING PER SUPPLIER` tab (kept live until AP Master `All Liabilities` matches it column-for-column).
