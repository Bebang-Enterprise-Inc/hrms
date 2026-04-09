# CONTEXT – Import / Data / Analytics Workstream

## Start here (Agent)
- Read first: `data/04_Project_Management/Import_Log/AGENT_RUNBOOK.md`
- Then read: `data/04_Project_Management/Import_Log/PROGRESS.md`
- Reference: `docs/data-dictionary/README.md` (entity definitions, field mappings, glossary)

> **Note (2025-01-14):** The `data/` folder was renamed from `ERP_Blueprint/` for clarity. All paths in this document use the new structure.

## What this log is for
This folder tracks **cross-project data ingestion + analytics work** so progress survives across sessions/models.

Primary scope:
- **Store Daily Monitoring (SMM)**: extract/clean multi-store Google Sheet/Excel workbooks and load into Supabase/Postgres.
- **Bebang Analytics dashboard**: Refine + Next.js + Shadcn UI + Supabase Auth/data, deployed to Vercel.

## Where the work lives

- **GO-LIVE APPROACH: PHASED DATA LOADING (2026-02-02)**

  **Plan:** `docs/plans/ERP_GOLIVE_PHASED_APPROACH_2026-02-02.md`

  | Phase | What | When | Status |
  |-------|------|------|--------|
  | **Phase 1** | Master Data (COA, Warehouse, Supplier, Item, Employee) | Now | ✅ **UPLOADED** |
  | **Phase 2** | Opening Balances (Inventory, AP, AR, Bank) | At Cutover | ⏳ Pending |

  **Key Decision:** Master data uploaded first for testing. Opening balances wait until cutover to avoid stale data.

- **COMMISSARY SUPERVISOR DASHBOARD (✅ LIVE + FULL E2E TESTED 2026-02-04)**

  | Component | Status | Location |
  |-----------|--------|----------|
  | Backend API | ✅ Live | `hrms/api/commissary.py` (12 endpoints) |
  | Frontend | ✅ Live | `my.bebang.ph/dashboard/commissary` (6 pages) |
  | Navigation | ✅ Added | Sidebar for Warehouse User, HR Manager, Admin |
  | E2E Production | ✅ PASS | MAT-STE-2026-00008, 00010 (with batch) |
  | E2E Wastage | ✅ PASS | MAT-STE-2026-00009 |
  | E2E Batch Creation | ✅ PASS | BATCH-FG006-2026-02-04 |

  **Features:**
  - Production tracking (log daily output) ✅ E2E Tested
  - Wastage tracking (log wastage with reasons) ✅ E2E Tested
  - Work orders management ✅ UI Tested
  - Quality control (inspections) ✅ UI Tested
  - Expiring stock / FEFO picking ✅ UI Tested
  - KPI dashboard (production count, orders, alerts, dispatches) ✅ UI Tested

  **Backend Fixes Applied (2026-02-04):**
  - Added Batch permission for Warehouse User role (Custom DocPerm)
  - Updated 19 FG items with shelf_life_in_days=30 for batch expiry

  **UI Bugs Fixed:** Work Orders null reference crash, Wastage API format mismatch

  **Live Test Data:** Stock entries created during E2E testing, batch with expiry date verified

  **Test Plan:** `docs/plans/COMMISSARY_E2E_TEST_PLAN_2026-02-04.md`

- **FINANCE & ACCOUNTING MODULE (✅ E2E COMPLETE 2026-02-06)**

  **Plan Files:**
  - Implementation: `docs/plans/2026-02-06-finance-accounting-module.md` (marked COMPLETE)
  - Original spec: `docs/plans/ACCOUNTING_MODULE_PLAN_2026-02-05.md`

  | Component | Status | Location |
  |-----------|--------|----------|
  | BEI Payment Request (RFP extension) | ✅ Deployed | `hrms/hr/doctype/bei_payment_request/` |
  | BEI Store Closing Report (variance alerts) | ✅ Deployed | `hrms/hr/doctype/bei_store_closing_report/` |
  | BEI Store Type master | ✅ Deployed | `hrms/hr/doctype/bei_store_type/` |
  | BEI Billing Schedule | ✅ Deployed | `hrms/hr/doctype/bei_billing_schedule/` |
  | BEI Billing Line Item | ✅ Deployed | `hrms/hr/doctype/bei_billing_line_item/` |
  | AP Aging endpoint | ✅ Deployed | `hrms/api/procurement.py` (get_ap_aging_report) |
  | Accounting Dashboard | ✅ Live | `my.bebang.ph/dashboard/accounting` |
  | Next.js API proxies | ✅ Live | `bei-tasks/app/api/accounting/` (dashboard + billing) |

  **E2E Test Results (8/8 PASS):**

  | Test | Result |
  |------|--------|
  | Payment Request - RFP Happy Path | ✅ PAY-2026-00049 |
  | Payment Request - Missing Required Fields (negative) | ✅ |
  | Store Closing Report - Cash Variance Alert | ✅ BEI-CLOSE-2026-00012 |
  | AP Aging Dashboard - 6 Buckets | ✅ |
  | Store Type Configuration - Managed Franchise Rates | ✅ |
  | Billing Schedule - Automated Calculation | ✅ BILL-2026-01-Operations - BEI |
  | RBAC - Accounting Dashboard Access | ✅ |
  | Payment Approval Workflow - 4-Level Chain | ✅ PAY-2026-00050, PAY-2026-00051 |

  **Bugs Found & Fixed (7):**
  - Missing `bei_billing_line_item.py` blocking migrations
  - Docker `exec -T` flag incompatible with EC2
  - CORS blocking accounting dashboard (created Next.js API proxy)
  - test.accounting user missing roles
  - BEI Payment Request not visible in Frappe Desk
  - RFP fields migration timeout
  - Billing Schedule `fetch_from: "store.store_type"` error (Department has no store_type)

  **Key Audit Finding:** 60% duplication eliminated vs original plan. Reused existing Payment Request (4-level approval), Closing Report (cash tracking), and Invoice (3-way match) instead of creating duplicate DocTypes.

  **Billing Fee Verification (Managed Franchise, PHP 1M gross):**
  - Royalty: 7% gross + 12% VAT = ₱78,400 ✅
  - Management: 2.5% gross + 12% VAT = ₱28,000 ✅
  - Marketing: 5% gross = ₱50,000 ✅
  - eCommerce: 5% online = ₱7,500 ✅
  - Delivery: (cost + 12% VAT) × 1.08 = ₱60,480 ✅
  - Logistics: (cost + 12% VAT) × 1.08 = ₱36,288 ✅

- **EXPENSE REQUEST SYSTEM (✅ E2E COMPLETE 2026-02-03)**

  | Component | Status | Location |
  |-----------|--------|----------|
  | Backend API | ✅ Live | `hrms/api/expense.py`, `expense_review.py`, `expense_ocr.py`, `expense_classifier.py` |
  | Frontend (Staff) | ✅ Live | `my.bebang.ph/dashboard/expense` (submit, list, detail) |
  | Frontend (Accountant) | ✅ Live | `my.bebang.ph/dashboard/accounting/expenses` (review, batch approve) |
  | OCR Integration | ✅ Live | Gemini 2.0 Flash for receipt extraction |
  | AI Classification | ✅ Live | Rule-based + AI COA classification cascade |

  **Features:**
  - Staff expense submission with receipt photo upload ✅ E2E Tested
  - Automatic OCR extraction of vendor, amount, date ✅ Deployed
  - AI-powered COA classification ✅ Deployed
  - Accountant review dashboard with batch approval ✅ E2E Tested
  - Match scoring between manual entry and OCR results

  **Bugs Fixed During E2E (3 commits):**
  - Store/warehouse field mapping (`6b02ca41d`)
  - Date picker UI - added year/month dropdowns (`db25fda`)
  - API permissions - removed redundant Cookie header (`db25fda`)

  **Test Accounts:**
  - Staff: `test.staff@bebang.ph` / `BeiTest2026!`
  - HR: `test.hr@bebang.ph` / `BeiTest2026!`

- **COMMISSARY OPERATIONS QUESTIONNAIRE (📋 SENT 2026-02-02)**

  | Field | Value |
  |-------|-------|
  | File | `scratchpad/COMMISSARY_OPERATIONS_QUESTIONNAIRE_2026-02-02.docx` |
  | Recipients | Arnold (R&D), Bryan C. Pe (Commissary Supervisor), Jennalyn Liwanag (QA) |
  | Status | Sent, awaiting responses |
  | ETA | Tomorrow (2026-02-03) |

  **Sections:** Production Planning, BOM/Recipes, Quality Control, Inventory, Order Fulfillment, Returns/Waste, Staff/Shifts, External Hubs, Reporting, Formula Variants

  **Key Discovery - FG020 Frozen Milk Formula Trial:**
  - **Original Formula:** Nestle Cream, Condensed Milk, Evap, etc.
  - **Griffith Trial Formula:** Powder-based formula from Griffith Foods
  - **Trial Stores:** 4 stores currently testing
  - **ERP Need:** Batch tracking to correlate formula variant (FG020-ORIGINAL vs FG020-GRIFFITH) with store quality feedback

- **MASTER DATA (Phase 1 - ✅ UPLOADED 2026-02-02)**

  | DocType | Expected | Actual | Status |
  |---------|----------|--------|--------|
  | Account | 297 | 297 | ✅ Uploaded |
  | Warehouse | 47 | 50 | ✅ Uploaded (47 new + 3 test) |
  | Supplier | 90 | 91 | ✅ Uploaded (90 new + 1 test) |
  | Item | 348 | 358 | ✅ Uploaded (348 new + 10 test) |
  | Employee | 592 | 597 | ✅ Uploaded (592 new + 5 test) |

  - SQL Generator: `scratchpad/generate_all_import_sql.py`
  - SQL Files staged to: `s3://bebang-bucket/imports/`
  - Import method: S3 → AWS SSM → Docker → MariaDB

  **Also configured during upload:**
  - UOMs, Item Groups, Stock Entry Types, Cost Center, Stock Adjustment Account, Fiscal Year 2026

  **Test Stock Added:** Stock Entry `MAT-STE-2026-00001` - 5 items in TEST-COMMISSARY - BEI

  **HR Enrichment Guide:** [Google Doc](https://docs.google.com/document/d/1oHLKI7gDzZyudV-dK_m6Mvq1PlVTbSuu6_BLjwOSgVc/edit)
  - 92 employees need manual bank/salary entry (no payroll match)
  - URL: hq.bebang.ph (not hrms.bebang.ph)
  - Assigned to: ronald@bebang.ph (HR Manager)

- **OPENING BALANCES (Phase 2 - AT CUTOVER)**

  | DocType | Records | Amount | Source | Status |
  |---------|---------|--------|--------|--------|
  | Purchase Invoice (AP) | 418 | PHP 66.2M | `data/_FINAL/AP_OPENING.csv` | ✅ Ready |
  | Sales Invoice (AR) | 219 | PHP 25.2M | `data/ERP_Reprocessing/2026-01-30/AR_AGING/` | ✅ Ready |
  | Stock Entry (Inventory) | TBD | TBD | Fresh count at cutover | ⏳ Pending |
  | Bank Balances | TBD | TBD | Statement at cutover | ⏳ Pending |

  **Decision:** Opening balances uploaded at cutover to avoid stale data. Team continues using current systems until then.

- **Employee Master (Legacy - 2026-01-14)**
  - Final CSV: `data/HR_Payroll_Masterlists/runs/2026-01-14/employee_master_complete/EMPLOYEE_MASTER_COMPLETE_2026-01-14.csv`
  - SQL file: `data/HR_Payroll_Masterlists/runs/2026-01-14/employee_master_complete/EMPLOYEE_INSERT.sql`
  - Import script: `data/_tools/generate_employee_sql.py`
  - **Status: Superseded by 2026-02-02 upload (592 enriched employees)**
  - Import method: Direct SQL via AWS SSM (see `.claude/skills/frappe-sql-bulk/SKILL.md`)

- **HR masterlist ingestion (Frappe HRMS)**
  - Progress: `docs/masterlist-import/PROGRESS.md`
  - Readme: `docs/masterlist-import/README.md`
  - Raw SSoT (archived): `data/Raw_Data_Archive/Inbox_Processed/2026-01-03/Updated Masterlist_Stores and Head Office/` (41 `.xlsx`)
  - Inbox drop zone: `docs/inbox/` (processed inputs moved to `data/Raw_Data_Archive/Inbox_Processed/YYYY-MM-DD/`)

- **Plans & Training (SSOT lives in `data/plans/`)**
  - Master Program: `data/plans/MASTER_TRAINING_PROGRAM_1WEEK.md`
  - Department plans, playbooks, runbooks, memos (MD + DOCX): `data/plans/`
  - Training folder pointer (legacy): `data/Training/README.md`
  - **Ops Onboarding Manual (Internal)**: `data/Ops_Manual/runs/2026-01-05_Ops_Ingestion/extracted_text/BEI ONBOARDING TRAINING MANUAL.txt`

- **Operations Data (Store Checklists, Labor Plans, Huddle Boards)**
  - Store Checklist: `data/Ops_Manual/runs/2026-01-05_Ops_Ingestion/extracted_text/Store Checklist - Opening and Closing Report Format.txt`
  - Labor Plan: `data/Ops_Manual/runs/2026-01-05_Ops_Ingestion/extracted_text/LABOR PLAN (1).txt`
  - Huddle Board: `data/Ops_Manual/runs/2026-01-05_Ops_Ingestion/extracted_text/BEBANG HUDDLE BOARD.txt`
  - Audit report (ERPNext/Frappe HR artifacts + knowledge gaps): `data/Ops_Manual/runs/2026-01-05_Ops_Ingestion/OPS_INGESTION_AUDIT_FOR_ERP_2026-01-06.md`

- **Meeting & Decisions Log**
  - Agenda & Decisions: `data/04_Project_Management/Meetings/`
  - Latest agenda: `2026-01-05_1300_ERPNext_Migration_Decisions_Agenda.docx`
  - **Meeting responses evidence (HR/Finance):**
    - Extraction run: `data/Meeting_Responses/runs/2026-01-05/`
    - Archived raw: `data/Raw_Data_Archive/Inbox_Processed/2026-01-05/HR_Finance_Meeting_Responses/`
    - Answer summaries:
      - `data/Department_Specs/FollowUp_Answers/FINANCE_Butch_Formoso_ERPNext_Policy_Decisions_Answered_2026-01-05.md`
      - `data/Department_Specs/FollowUp_Answers/HR_Ronald_Caringal_Attendance_BioID_Policy_Answered_2026-01-05.md`

- **Supabase (BEI Data Lake – canonical for Analytics / Tasks / ERP)**
  - Dashboard: `https://supabase.com/dashboard/project/csnniykjrychgajfrgua`
  - API URL: `https://csnniykjrychgajfrgua.supabase.co`
  - Credentials: stored in `.cursor/rules/99-secrets.local.mdc` (local-only; do not commit)

  **Data Tables (2026-01-15):**
  | Table | Rows | Source | Sync |
  |-------|------|--------|------|
  | `scm_data` | 60,181 | SCM Google Sheets (13 files) | Daily 6:00 AM |
  | `scm_sheet_hashes` | - | Change detection | Auto |
  | `scm_extraction_log` | - | Audit trail | Auto |
  | `store_dashboard_data` | 10,760 | Store Dashboards (44 stores) | Daily 6:30 AM |
  | `store_dashboard_sheet_hashes` | 176 | Change detection (44 x 4 sheets) | Auto |
  | `store_dashboard_extraction_log` | 44 | Audit trail | Auto |
  | `store_dashboard_quality_issues` | 0 | Data quality flags | Auto |

  **SCM Data Categories:**
  - Commissary (32,652 rows): Daily issuance transactions
  - Inventory (16,650 rows): Warehouse movements
  - Procurement (10,524 rows): PO tracking, pricing
  - Logistics (355 rows): Routes, delivery costs

  **Store Dashboard Data:**
  - INVENTORY (4,840 rows): Daily inventory counts
  - WASTAGE (4,486 rows): Wastage tracking
  - SS RECORDS (725 rows): Daily sales summary
  - PMIX RECORDS (709 rows): Product mix by flavor

- **SCM + Store Dashboard ETL Scripts (2026-01-15)**
  - SCM bulk load: `data/_tools/bulk_load_scm_to_supabase.py`
  - SCM daily sync: `data/_tools/sync_scm_to_supabase.py`
  - Store dashboard extraction: `data/_tools/extract_store_dashboards.py`
  - Store dashboard daily sync: `data/_tools/sync_store_dashboards.py`
  - Task Scheduler wrappers: `scripts/sync_scm_daily.bat`, `scripts/sync_store_dashboards_daily.bat`
  - Store Code Dictionary: `data/04_Project_Management/Import_Log/STORE_CODE_DICTIONARY.md`

- **Inventory Sheets Directory (2026-01-20)**
  - **Master Directory:** `data/Inventory/INVENTORY_SHEETS_DIRECTORY.md`
  - Contains: All Google Sheets links, last edit dates, access control, 3MD partnership sheets
  - **Active Sheets (13):** Central WHSE monitoring, weekly reports, supply chain sheets
  - **3MD External Sheets (2):** DRY and COLD inventory (owner: jjs041291@gmail.com)
  - **Access Granted:** sam@, angela@, islar@ added Jan 20, 2026
  - **Local Downloads:** `data/Inventory/3MD_Downloads/` (warning: Excel formulas broken)
  - **Note:** View 3MD sheets in Google Sheets online - UNIQUE() formulas don't export to Excel

- **Analytics + ETL repo (dashboard + pipelines)**
  - Local path: `C:/Users/Sam/.cursor/Projects/bebang-analytics`
  - GitHub: legacy analytics repo (planned rename to `bebang-analytics`)
  - Vercel projects: `bebang-analytics` (current target); legacy project deprecated

## Non-negotiable rules
- **Data safety**: never edit raw HR input files in-place; generate new outputs.
- **HR handoff**: only send HR `*_review_HR_FRIENDLY.csv` files.
- **Deployment**: for analytics/dashboard, **deploy via Vercel CLI with cache-bust** after pushes.
- **Secrets**: never commit credentials; keep tokens/keys in local-only rules.

## Active Employee Definition (IMPORTANT)

**Active Employee = Employee who received payment in the latest payroll.**

When searching for active employees:
1. Download the latest payroll files from Google Drive (e.g., `01_2026_BEI_Payroll Package_MMDDYYYY_Batch X_ClientFile.xlsx`)
2. Check the `ComprePayRun` sheet
3. Filter for employees where `Net Pay > 0`
4. Employees in the Masterfile but NOT in ComprePayRun with Net Pay > 0 are NOT active

**DO NOT** rely on:
- Masterfile alone (contains resigned employees not yet removed)
- DTRData alone (employees may have worked but not received pay)
- Employment Status field (unreliable - many "Probationary" are resigned)

**Active Employee Count (Jan 10, 2026 Payroll):** 604 employees received payment

## Audit Storage Policy
- **Location**: All audits are saved to `data/Audits/`
- **Subfolder naming**: Use the name of the person or department being audited (e.g., `procurement/`, `finance/`, `hr-ronald/`)
- **File naming**: `<AUDIT_TYPE>_AUDIT_REPORT_<YYYY-MM-DD>.md` and `.docx`
- **Example**: `data/Audits/procurement/PROCUREMENT_AUDIT_FINAL_2026-01-18.md`

## Procurement Process (AppSheet Systems)

### System Architecture
BEI uses **two separate AppSheet databases** for procurement:

| Database | Google Sheet ID | Purpose |
|----------|-----------------|---------|
| Procurement Compliance | `1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q` | POs, GRs, Suppliers |
| RFP App | `1-2xvSVhEI1_U_P5s6rG1-LnSvFil7LzJcdjkADeWAcg` | Payment requests |

**Key Personnel:**
- **Ian Dionisio** (ian@bebang.ph) - Warehouse Supervisor, documents all warehouse GRs
- **Cayla Cabagnot** - Procurement, creates PRs/POs/RFPs
- **Alyssa** (alyssa@bebang.ph) - Accounting Manager, payment processing

### Standard Workflow (Warehouse Items)
```
PR → PO → Supplier delivers to WAREHOUSE → Ian creates GR → Finance creates RFP → CFO approves → Payment
```
Items following this flow: Raw materials, packaging, consumables (delivered to 3MD, Jentec, RCS, Pinnacle warehouses)

### Direct-to-Store Workflow (No Warehouse GR Expected)
```
PR → PO → Supplier delivers DIRECTLY TO STORE → Finance creates RFP (no GR) → CFO approves → Payment
```
Items following this flow:
- **Mosaic Hospitality** - POS systems, store fixtures for new store openings
- **MATHEW GENERAL MERCHANDISE** - Smallwares (utensils, containers) for new stores
- **WIL TAILORS** - Staff uniforms (delivered to HR or stores)
- **Philippine Foodservice Equipment** - Kitchen equipment

**IMPORTANT:** When auditing procurement, DO NOT flag direct-to-store items as "missing GR" - this is expected behavior.

### Audit Status (2026-01-18)
- **Latest audit**: `data/Audits/procurement/PROCUREMENT_AUDIT_FINAL_2026-01-18.md`
- **Finding**: No significant issues. Initial flags were false positives due to:
  1. RFP not linked to GR (data entry gap, not missing delivery)
  2. Direct-to-store deliveries (legitimate process)
  3. Price variance from UOM entry errors (training issue)
- **Decision**: Skip formal audit, focus on ERPNext go-live (Feb 1, 2026)
- **Actual issues**: ~PHP 184K (Orangepop partial delivery, 3J Plastic never received) - low priority

### Supplier Master SSOT (2026-01-21) - CORRECTED

**Single Source of Truth:** `data/Procurement_SCM_Discovery/runs/2026-01-21/03_supplier_audit/SUPPLIER_MASTER_AUDITED_81_2026-01-21.csv`
- **Source:** Audit-confirmed file from arshier@bebang.ph
- **Google Drive:** `https://docs.google.com/spreadsheets/d/1TmENuP8HgCVbo3lJtTpe4PVemLCkPnGL`
- **Total Suppliers:** 81 (59 REGISTERED + 22 pending/blank status)
- **Extraction Audit:** PASS 100% accuracy

**Supplier Comparison Audit (2026-01-21 CORRECTED):**
- **30 unique payees** in POs/RFPs NOT in SSOT
- Many are NOT traditional suppliers (malls, employee reimbursements)
- **~8 actual suppliers** need to be added to SSOT
- **Red Flag:** M Tealicious has two different personal bank accounts

**Action Required Before ERP Go-Live:**
1. Review 8 actual supplier gaps (not malls/employees)
2. Investigate M Tealicious bank account discrepancy
3. Clarify if pending 22 suppliers need REGISTERED status

**Extracted Procurement Data (2026-01-21):**

| Database | Sheets | Rows | Registry ID |
|----------|--------|------|-------------|
| Procurement Compliance AppSheet | 8 | 6,429 | f82a89a5 |
| RFP App Database | 6 | 2,897 | e63e69b1 |

**Output Location:** `data/Procurement_SCM_Discovery/runs/2026-01-21/02_fresh_extraction/`

## Ops/SCM Process Inventory (Added 2026-01-21)

### Source
- **Google Sheet:** `1Oqwf5vVGofcV1GGAbRHUFMjzNxy78ZxX3CP8RPCGkQI`
- **Title:** BEBANG OPS / SCM PROCESS LIST
- **Extracted:** `data/Procurement_SCM_Discovery/runs/2026-01-21/04_ops_scm_process/`

### Process Inventory (69 Total)

| Department | Processes | Key Systems |
|------------|-----------|-------------|
| SUPPLY_CHAIN | 30 | AppSheet (PR/PO/GR), Google Sheets, Manual Docs |
| OPERATIONS | 30 | Google Sheets (Ordering, Reports), Manual Docs |
| COMMISSARY | 9 | Google Sheets (Production, KPI), Manual Docs |

### 4 Critical Store Features (Must be in ERP Day 1)

**CEO Decision:** ALL company processes should move to ERP (overrides Ops/SCM marking all as `For_ERP_Transfer = FALSE`)

| Feature | Current | ERP Target | Gap Status |
|---------|---------|------------|------------|
| **Store Ordering** | Google Form/Sheet | Material Request | Questionnaire sent |
| **Store Receiving** | Manual Docs | Purchase Receipt | Store-level process TBD |
| **Supplier Accreditation** | Manual Docs | Supplier workflow | Mostly documented |
| **Dispatch Logging** | Paper/Manual | Delivery Note | POD requirements TBD |

### Existing Questionnaire Coverage

From Herdie (Ops) and Aldrin (SCM) questionnaires (Dec 2025):
- **Warehouse receiving:** 12-step process documented (SCM Q33-D4)
- **Store replenishment:** 3-4x/week frozen/chilled, next-day delivery (Ops Q19-20)
- **Supplier accreditation:** BIR 2303, business reg, bank details, SCM Mgr + VP Ops approval (SCM Q11-12)
- **Delivery logistics:** By location/cluster, refer trucks + dry vans (SCM Q48-51)

### Gaps (Questionnaire Sent to Edlice/Dave)

- Store-level order approval workflow
- Store-level receiving process (vs warehouse)
- Proof of delivery requirements
- Exception handling (store closed, refused delivery)

**Questionnaire:** `data/Procurement_SCM_Discovery/runs/2026-01-21/05_store_ops_questionnaire/STORE_OPS_QUESTIONNAIRE_EdliceDave.docx`
**Due:** 2026-01-22

---

## Sales-to-cash policy (POS + Website + Aggregators)
- **Revenue recognition**: Sales entry only on **Delivered** (pre-orders are operational until delivered).
- **Website orders**: store_code/store_id is assigned **at order time**.
- **Reconciliation**: payment gateways and aggregators settle later; reconcile using clearing accounts and payout IDs.
- Canonical team docs:
  - `data/plans/Completed/OMNICHANNEL_SALES_TO_CASH_PLAYBOOK_2026-01-12.docx`
  - `data/plans/Completed/POS_EXPORT_REQUIREMENTS_FOR_ERP_ACCOUNTING_2026-01-12.docx`
  - `data/plans/Completed/ONLINE_SALES_EXPORT_REQUIREMENTS_FOR_ERP_ACCOUNTING_2026-01-12.docx`

## Inventory structure policy (commissary is a separate entity)
- Commissary is treated as a **separate entity** with its own inventory + manufacturing activity + P&L.
- Store inventories are owned/managed separately.
- Commissary → store movements must be recorded as an intercompany flow (and must reconcile).
- **Stock valuation (2026-01-14):** Moving Average for ERP costing (CFO decision), FIFO for physical stock rotation (Ops SOP)
- **Company structure:** Bebang Kitchen Inc. (Commissary) → Bebang Enterprise Inc. (Stores)
- Canonical team docs:
  - `data/plans/INVENTORY_END_TO_END_ERP_PLAN_2026-01-12.md`
  - `data/plans/Completed/INVENTORY_CONTROL_AND_STOCK_MOVEMENTS_PLAYBOOK_2026-01-12.docx`
  - `docs/plans/ERP_MIGRATION_MASTER_PLAN_2026-01-14.md` **(SSOT for Feb 1 go-live)**

## Store identity sources (Website vs ERP vs Accounting)
When tasks involve **store lists / names / addresses**, do not rely on a single file. Use:

- **Website store name + address (Superadmin API export)**
  - Latest export lives in: `docs/stores/Bebang_Halo-Halo_Stores_Locations_<YYYY-MM-DD>.csv`
  - `id` is the slug; `store_name` is the official display name; `address` is the official store locator address.

- **ERP locations/warehouses (Warehouse Tree export)**
  - Latest export lives in: `docs/erp/WAREHOUSE_TREE_<YYYY-MM-DD>.csv`
  - Includes **non-website hubs** (cold storage, logistics, commissary) that still matter for ERP.

- **Accounting/APEX store labels (workbook names)**
  - APEX workbook store names are inconsistent/abbreviated.
  - Always map using a saved triangulation table (below) rather than eyeballing names.

**Latest triangulation output (saved evidence):**
- `docs/erp/STORE_IDENTITY_TRIANGULATION_2026-01-04.csv`

**Generate/update the triangulation table:**
- `python data/_tools/build_store_identity_triangulation.py --apex-run-dir "data/Finance_APEX/runs/<run>" --date <YYYY-MM-DD>`

**Critical disambiguation:**
- `uptc` = **UP Town Center**
- `uptownbgc` = **Uptown Mall BGC**
- Never treat these as the same store.

## Attendance / Bio ID standardization (Frappe HRMS)

### ⭐ Active Employees Master File (SSOT - 2026-01-30)

**SINGLE SOURCE OF TRUTH for active employees:**
```
data/ERP_Reprocessing/2026-01-30/ACTIVE_EMPLOYEES_MASTER_FINAL.csv
```
(Also at: `.claude/rlm_state/active_employees_master/ACTIVE_EMPLOYEES_MASTER_FINAL.csv`)

| Metric | Value |
|--------|-------|
| **Total Active Employees** | **592** |
| **Unique Bio IDs** | 592 (100% unique) |
| **Bio ID Range** | 9000003 - 9001737 |
| **Source** | 45 store files from `F:\Downloads\Active Employees Verification` |
| **Columns** | bio_id, employee_name, employee_no, designation, store_code, store_name, department, status, date_of_joining, employment_type, gender, company, _source_file |

**ADMS Database:** 618 Bio IDs synced (592 master + 26 claimed missing from Google Sheet)

### Biometric Reset Status
- **Full Company Reset (2026-01-30):** ✅ 592 employees verified, ADMS synced
- **Re-enrollment Policy:** All team members enrolled with new, standardized Bio IDs (numeric-only, `9xxxxxx` series)
- **Opening Team:** 10 relief staff enrolled on ALL 42 store devices
- **Archived Files:** Old intermediate files renamed with `_ARCHIVED_20260130` suffix in `.claude/rlm_state/`

### Key Lesson (2026-01-30)
**ONLY use the Active Employees Verification folder files as source.** Old ADMS records may contain resigned/inactive employees. Always regenerate master file from source files, not from ADMS.

- **Audit Requirement:** HR still needs to match legacy Bio IDs to names for the Nov/Dec 2025 forensic audit.
  - Evidence: `data/Department_Specs/FollowUp_Answers/HR_Ronald_Caringal_Attendance_BioID_Policy_Answered_2026-01-05.md`

### Employee Location Audit (2026-01-21)
**Purpose:** Validate which employees are punching at which locations (location validation, not attendance tracking).

| Metric | Value |
|--------|-------|
| Period | Jan 14-21, 2026 (7 days) |
| Total Punches | 10,629 |
| Unique PINs (employees) | 518 |
| Active in Employee Master | 676 |
| **Coverage** | **76.6%** |
| Multi-Location Employees | 39 |

**Key Finding - Bio ID Mismatch:**
- PINs in ADMS (legacy format: 1, 10, 102403) do NOT match employee master (new `9xxxxxx` series)
- Data spans Jan 14-21, includes both pre-reset (legacy) and post-reset (new) periods
- Cannot directly join PINs to employee names without legacy mapping file

**Gap Analysis:**
| Category | Count | Notes |
|----------|-------|-------|
| Employees who punched | 518 | 76.6% of active |
| Missing employees | 158 | Did not punch in 7 days |
| Known Bio ID issues | 83 | From Jan 19 reset planning |
| Unexplained gap | ~75 | Leave, days off, HQ exempt |

**Output Files:** `data/ADMS/runs/2026-01-21_employee_location_audit/`
**Extraction Report:** `data/ADMS/runs/2026-01-21_employee_location_audit/EXTRACTION_REPORT.md`

### Head Office Biometric Enrollment Reset (2026-01-21) - IN PROGRESS

**Purpose:** Re-enroll all 83 Head Office employees on all 3 HO devices.

| Device | Serial | Records in ADMS |
|--------|--------|-----------------|
| Brittany Hotel | UDP3251600245 | 887 |
| Capital House | UDP3235200625 | 84 |
| Shaw Commissary | UDP3235200629 | 613 |

**Status:**
- ✅ 14 new Bio IDs assigned (9001684-9001697)
- ✅ Enrollment CSVs generated for all 3 devices
- ✅ ADMS data backed up (1,584 records)
- ⏳ **BLOCKING:** Archie must backup full 6-month device logs (ADMS only has data since Jan 5)

**Files:** `data/HR_Payroll_Masterlists/runs/2026-01-21_head_office_validated/`
**Backup:** `s3://bebang-frappe-hrms-backups/adms/head_office_attendance_backup_2026-01-21.csv`

**Key Decision:** Enrolling new users does NOT delete attendance logs. Only a factory reset would lose data.

- **Tooling**:
  - Policy doc: `docs/erp/BIO_ID_STANDARDIZATION_POLICY_2026-01-01.md`
  - Generator script: `data/_tools/generate_uniform_bio_ids.py`
  - Persistent registry: `data/HR_Payroll_Masterlists/bio_id_uniform_registry.csv`

- **ADMS Receiver (AWS → Frappe HRMS)**:
  - We ingest MB10‑VL ADMS/iClock pushes (ATTLOG) into the cloud receiver and write `Employee Checkin` rows to Frappe.
  - **Opening Team (relief staff)**: 10 employees enrolled on ALL 42 store devices (can punch anywhere).
  - **Staff coverage (relief staff) policy (2026-01-13)**:
    - Coverage can be cross-area, but **final approval stays with the Regional Manager (RM)**.
    - Use **Option B** for relief staff at a destination location: allow **temporary password/PIN punching** only for the approved shift window, then **disable after the shift**.
    - Plan (SSOT): `data/plans/STAFF_COVERAGE_WORKFLOW_AND_BIOMETRICS_TEMP_PIN_PLAN_2026-01-13.md`
  - Automation direction:
    - **⭐ Device SN Mapping SSOT (2026-01-30)**: [Google Sheet - Device SN Mapping VALIDATED](https://docs.google.com/spreadsheets/d/1_fkvjS2v4DabThMgHrq8vRXmgXjKiBQbEN6se_mDWro/edit)
      - Location: ERP Shared Drive → Bio-ADMS folder
      - Validated via ADMS server connection logs (ground truth)
      - Local backup: `IT_Device_SN_Mapping_CANONICAL_2026-01-07.csv` (superseded)
    - **Receiver allowlist = SN mapping**: the AWS receiver will accept a device SN only if it exists in the receiver's configured `SN_MAPPING_CSV`.
    - **Rollout config (AWS)**: ensure `SN_MAPPING_CSV=/repo/adms_receiver/sn_mapping_all.csv` (a deployed copy of the canonical mapping).
    - **Connectivity evidence (AWS)**: nginx access logs are written to container stdout, use `docker logs adms_receiver-adms-nginx-1` for last-seen SNs.
    - Operations runbook (SSOT): `data/plans/Completed/ADMS_RECEIVER_OPERATIONS_RUNBOOK_2026-01-14.md`
    - **Quick Reference:** `docs/ops/ADMS_OPERATIONS_QUICK_REFERENCE.md` ← AWS SSM commands, container names, common mistakes
    - **Full Reset Report (2026-01-30):** `data/HR_Payroll_Masterlists/runs/2026-01-29_verified_employees/ADMS_RESET_REPORT_2026-01-30.md`
    - Remote device automation handled via `GET /iclock/getrequest` + `POST /devicecmd`.
    - Format: `C:<ID>:<COMMAND_TEXT>` where `COMMAND_TEXT` uses tab-separated `key=value`.
    - Decision: **No ZKBioTime license or vendor software required.** We manage device enrollment and identity directly from AWS.

## ERP Migration Program (Feb 1, 2026 Go-Live)

**Master Plan (SSOT):** `docs/plans/ERP_MIGRATION_MASTER_PLAN_2026-01-14.md`

### Key Decisions (2026-01-05 to 2026-02-03)
| Decision | Resolution |
|----------|------------|
| **Admin Drive Structure** | **Store-centric with duplication** (2026-02-03). Each store folder gets _CORPORATE subfolder with copies of parent entity docs (AOI, Bylaws, COI, GIS). 117 copy operations pending. |
| Stock valuation | Moving Average (ERP costing), FIFO (Ops physical rotation) |
| Commissary structure | Bebang Kitchen Inc. (separate company) |
| Intercompany flow | Suppliers → Bebang Kitchen Inc. → Bebang Enterprise Inc. (stores) |
| PO Approval | Mae ≤500K sole, Mae+Butch >500K joint, CEO for new vendors |
| Cutover date | February 1, 2026 |
| Business cutoff | 2:00 AM (confirmed 2026-01-15) |
| Critical SKUs | Top 10 identified for daily counting (see Master Plan Section 3.6) |
| **Cost Centers** | BEI (root) → Stores/Commissary/Departments (groups) → Individual cost centers. **No sub-cost centers for stores** (use COA accounts for Labor/Utilities). One Company per legal entity for BIR/SEC. |
| Sales posting | Daily summarized entries with attachments |
| Bank reconciliation | Monthly |
| Commissary transfer pricing | Standard cost + markup, reviewed monthly |
| **Bio ID Format** | New `9xxxxxx` series (7 digits starting with 9). Legacy formats deprecated. |
| **Bio ID Delete Command** | `DATA DELETE FACE PIN=xxx` for ZKTeco MB10-VL face devices. `DATA DELETE USERINFO` only deletes metadata, not biometrics. |
| **IT Admin Credentials** | PIN: 9999, Password: 29984751, Privilege: 14 (Super Admin) - on ALL 45 devices |
| **Opening Team Enrollment** | 10 relief staff enrolled on ALL 42 store devices for coverage |
| **Enrollment Target** | 100% of 592 active employees within 2 days of Feb 1, 2026 |

### Master Data Ready for Import

**Note (2026-01-30):** All critical ERP data reprocessed with `/extract-data-v2.1` using correct Google Sheets API (`valueRenderOption=UNFORMATTED_VALUE`). Replaces previous extractions.

| Data | Status | File | Sheets | Rows |
|------|--------|------|--------|------|
| Chart of Accounts | **✅ COMPLETE** | `data/ERP_Reprocessing/2026-01-30/COA.csv` | 1 | 297 |
| COA Fund Details | **✅ COMPLETE** | `data/ERP_Reprocessing/2026-01-30/COA_FUND_DETAILS.csv` | 1 | 185 |
| Bank Directory | **✅ COMPLETE** | `data/ERP_Reprocessing/2026-01-30/BANK_DIRECTORY.csv` | 1 | 54 |
| EFT/PESONET Codes | **✅ COMPLETE** | `data/ERP_Reprocessing/2026-01-30/EFT_PESONET_CODES.csv` | 1 | 108 |
| Supplier Master | **✅ COMPLETE** | `data/ERP_Reprocessing/2026-01-30/SUPPLIER_MASTER_*.csv` | 4 | 81 |
| Opening Inventory | **✅ COMPLETE** | `data/ERP_Reprocessing/2026-01-30/INVENTORY_*.csv` | **31** | **35,446** |
| Warehouse Tree | **✅ COMPLETE** | `data/ERP_Reprocessing/2026-01-30/WAREHOUSE_TREE.csv` | 1 | 47 (43 stores + 4 3PLs) |
| Employee Master | **✅ SSOT** | `data/ERP_Reprocessing/2026-01-30/ACTIVE_EMPLOYEES_MASTER_FINAL.csv` | 1 | **592** |
| AP Opening Balance | **✅ READY** | `data/Finance_AP_AR/extractions/2026-01-30/ERPNEXT_AP_OPENING_COMPLETE.csv` | 1 | 411 |
| AR Aging (Y2026) | **✅ COMPLETE** | `data/ERP_Reprocessing/2026-01-30/AR_AGING/` | 6 | 446 |
| **Item Master (MERGED)** | **✅ READY** | `data/ERP_Migration_2026-01-31/ERPNEXT_ITEM_MASTER.csv` | 1 | **348** |
| **BOM Master** | **✅ COMPLETE** | `data/Procurement_Database/FORENSIC_EXTRACTION/Copy of Compliance App Database__BOM_Master.csv` | 1 | **250** |
| **Standard BOM (Detailed)** | **✅ COMPLETE** | `data/Procurement_Database/FORENSIC_EXTRACTION/Copy of Compliance App Database__Standard_BOM.csv` | 1 | **6,440** |
| Trial Balance | **❌ PENDING** | Oct 31 version exists - need Jan 31 refresh from Butch | - | - |

**Source Files (Google Sheets/Drive - Verified 2026-01-31):**

| Data | Google Drive Link | Owner | Notes |
|------|-------------------|-------|-------|
| COA | [1EXCd4Ah2n6Q42vQvTG3dYLFzPsPFhdbzmHp_2wBpN7g](https://docs.google.com/spreadsheets/d/1EXCd4Ah2n6Q42vQvTG3dYLFzPsPFhdbzmHp_2wBpN7g) | sam@bebang.ph | 2 sheets: COA (297) + Fund Details (185) |
| Bank Directory | [1rkQDLREjTG8eyqB7wO5rRsnkjvaasOgmnPcKnqjXNnY](https://docs.google.com/spreadsheets/d/1rkQDLREjTG8eyqB7wO5rRsnkjvaasOgmnPcKnqjXNnY) | sam@bebang.ph | 1 sheet, 54 banks |
| EFT/PESONET | [15hTWv8GY16lN4B4n2-VEVdwvSl-JujhpZ2NSatwR_Qk](https://docs.google.com/spreadsheets/d/15hTWv8GY16lN4B4n2-VEVdwvSl-JujhpZ2NSatwR_Qk) | sam@bebang.ph | 1 sheet, 108 PESONET codes |
| Inventory | [1Eh_BhDK_LgdOzJ002F7XUYLBsd4EM8ec7sPz43mudGc](https://docs.google.com/spreadsheets/d/1Eh_BhDK_LgdOzJ002F7XUYLBsd4EM8ec7sPz43mudGc) | ian@bebang.ph | 31 sheets, 35,446 rows |
| AR Aging | [1puwkr5hzrki9srxq10_jOeb5mfngkbo-VVpydmAf2kQ](https://docs.google.com/spreadsheets/d/1puwkr5hzrki9srxq10_jOeb5mfngkbo-VVpydmAf2kQ) | alyssa@bebang.ph | 6 sheets, 446 rows |
| Warehouse Tree | [1eIqP_48lOv3fMERrcKtDVm_BpKQV9wJx](https://docs.google.com/spreadsheets/d/1eIqP_48lOv3fMERrcKtDVm_BpKQV9wJx) | sam@bebang.ph | 47 rows (43 stores + 4 3PLs) |
| Supplier Master | N/A (uploaded Excel) | arshier@bebang.ph | 4 sheets, 81 suppliers |
| Employee Master | N/A (local files) | HR | 45 store files from `F:\Downloads\Active Employees Verification` |

**Related Google Sheets (reference only):**
- BEBANG STORE LIST: [15y7BkCB8OabKEwQYS4sfXJDFkS6QEATTZtXO1ujkWJw](https://docs.google.com/spreadsheets/d/15y7BkCB8OabKEwQYS4sfXJDFkS6QEATTZtXO1ujkWJw) (owner: ian@bebang.ph)

### Finance Data Extraction (2026-01-17)
**Status:** 100% VERIFIED - Ready for ERP import

**Forensic Audit Achievement (2026-01-17):**
- **100% ACCURACY** achieved across 104 primary data sheets
- 500,000+ cells verified against original Excel source files
- Key-based matching (EmployeeNo/AccountCode) with proper tolerance handling
- Audit report: `data/Finance_REPROCESSING/runs/2026-01-17/FINAL_AUDIT_REPORT_100_PERCENT.md`

**Files extracted (7 total):**
- COA: 217 GL accounts
- Bank Directory: 53 accounts + 35 store accounts
- EFT Bank Codes: 233 routing codes (PESONET/PDDTS/INSTAPAY)
- P&L Template: 72 line items
- Check Disbursement: 23,020 transactions
- Payroll Analysis: 41 stores
- Petty Cash Template: 14 periods

**Opening Balances:**
- **AP: PHP 68,080,089.48 (411 records, 39 suppliers)** - Re-extracted Jan 30 from SUPPLIERS SOA sheet
  - ⚠️ PHP 54.6M already overdue, PHP 10M due in February
  - Top supplier: MIDDLEBY WORLDWIDE (PHP 21.2M)
  - ERPNext file: `data/Finance_AP_AR/extractions/2026-01-30/ERPNEXT_AP_OPENING_COMPLETE.csv`
- **AR (JV/Partner): PHP 25,235,614.96 (220 items, 49 customers)** - Extracted Jan 30, 2026
- AR (External): Minimal (B2C retail model)
- Trial Balance: Oct 31 found (3,075 entries, 34 companies) - need Jan 31

### Go-Live Approach (Agreed 2026-02-01)

**Decision:** Launch with Minimum Viable Data, rectify accounting as we go.

| Data | Go-Live Status | Post-Go-Live Plan |
|------|----------------|-------------------|
| **AP Opening** | ✅ Ready (PHP 66M) | - |
| **AR Opening** | ✅ Ready (PHP 25M) | - |
| **Inventory** | ✅ Ready (35,446 rows from sheets) | Physical count in few days → Stock Reconciliation |
| **Bank Balances** | 🔄 Coming soon | Add as Opening Journal Entry |
| **Full Trial Balance** | ⏳ Few weeks | Post as Opening Equity adjustment when ready |

**Rationale:** Operational transactions (POs, GRs, Sales) are priority. Accounting true-up can happen after go-live without blocking operations.

**Completed:**
- ✅ Cost Center structure - Answered 2026-01-05 (see `data/Department_Specs/FollowUp_Answers/FINANCE_Butch_Formoso_ERPNext_Policy_Decisions_Answered_2026-01-05.md`)
- ✅ JV/Partner AR - Extracted Jan 30, 2026: **PHP 25,235,614.96** (220 items, 49 customers). See `data/ERP_Reprocessing/2026-01-30/AR_AGING/`

**Pending (to be rectified post-go-live):**
- Bank Balances as of Jan 31 → Owner will provide, import as Opening JE
- Full Trial Balance (all GL accounts) → Coming in few weeks, post as equity adjustment

**Request Memo:** `data/04_Project_Management/Memos/ERP_FINANCE_DATA_REQUEST_2026-01-16.docx`
**Extraction Summary:** `data/Finance_AP_AR/extractions/2026-01-16/MASTER_EXTRACTION_SUMMARY.md`

### ERP Master Data Validation Tracker (Updated 2026-01-21)

**Go-Live:** February 1, 2026
**Validation Deadline:** January 28, 2026

#### Validation Status by Department

| Dept | Data | Records | Extracted | Audited | Sent for Validation | Validated | ERP Import |
|------|------|---------|-----------|---------|---------------------|-----------|------------|
| **HR** | Employee Master | 765 | ✅ | ✅ | ✅ | ✅ | ✅ IMPORTED |
| **PROCUREMENT** | Supplier Master | 81 | ✅ | ✅ | ⏳ PENDING | - | - |
| **PROCUREMENT** | AppSheet (PR/PO/GR) | 6,429 | ✅ | ✅ | ⏳ PENDING | - | - |
| **PROCUREMENT** | RFP App | 2,897 | ✅ | ✅ | ⏳ PENDING | - | - |
| **SCM** | Opening Inventory | 39,255 | ✅ | ✅ | ⏳ PENDING | - | - |
| **SCM** | Warehouse Tree | 47 | ✅ | ✅ | ⏳ PENDING | - | - |
| **FINANCE** | Chart of Accounts | 217 | ✅ | ✅ | 📤 Jan 21 | ⏳ Due Jan 28 | - |
| **FINANCE** | Bank Directory | 88 | ✅ | ✅ | 📤 Jan 21 | ⏳ Due Jan 28 | - |
| **FINANCE** | EFT/PESONET Codes | 108 | ✅ | ✅ | 📤 Jan 21 | ⏳ Due Jan 28 | - |
| **FINANCE** | AP Opening Balance | **411** | ✅ Jan 30 | ✅ | **PHP 68.1M** | ✅ CORRECTED | Ready |
| **FINANCE** | Check Tracker Bank Dir | 53 | ✅ | ✅ | 📤 Jan 21 | ⏳ Due Jan 28 | - |
| **FINANCE** | Trial Balance | - | ⚠️ Oct 31 only | - | - | - | 🔄 Post-go-live (few weeks) |
| **FINANCE** | AR (JV/Partner) | **220** | ✅ Jan 30 | ✅ | **PHP 25.2M** | ✅ COMPLETE | Ready |
| **FINANCE** | Bank Balances | - | 🔄 Coming | - | - | - | 🔄 Post-go-live (opening JE) |
| **OPS** | Process List | 69 | ✅ | ✅ | ⏳ PENDING | - | - |
| **OPS** | Store Workflows | - | ⏳ | - | - | - | ❌ Questionnaire due Jan 22 |

#### Finance Validation Package (Sent Jan 21)

**Recipient:** Butch (CFO)
**Due Date:** January 28, 2026
**Package Location:** `data/Finance_Validation_Package_2026-01-21/`

| File | Records | Total |
|------|---------|-------|
| `01_COA_FOR_VALIDATION.csv` | 217 accounts | - |
| `02_BANK_DIRECTORY_FOR_VALIDATION.csv` | 53 accounts | - |
| `03_STORE_BANK_ACCOUNTS_FOR_VALIDATION.csv` | 35 accounts | 88 total |
| `04_EFT_PESONET_CODES_FOR_VALIDATION.csv` | 108 codes | - |
| ~~`05_AP_OPENING_BALANCE_FOR_VALIDATION.csv`~~ | ~~158 items~~ | ~~PHP 24.4M~~ **REPLACED** |
| **`ERPNEXT_AP_OPENING_COMPLETE.csv` (Jan 30)** | **411 items** | **PHP 68,080,089.48** |
| `06_CHECK_TRACKER_BANK_DIR_FOR_VALIDATION.csv` | 53 entries | - |
| `FINANCE_VALIDATION_PACKAGE_2026-01-21.xlsx` | Combined | All sheets |

#### Outstanding Items (BLOCKING Go-Live)

| # | Item | Owner | Due | Status |
|---|------|-------|-----|--------|
| 1 | Trial Balance as of Jan 31, 2026 | Butch | Jan 28 | ❌ NOT RECEIVED |
| 2 | ~~AP Opening Balance as of Jan 31, 2026~~ | ~~Butch~~ | ~~Jan 28~~ | ✅ **EXTRACTED Jan 30 (PHP 68.1M)** |
| 3 | AR (JV/Partner) as of Jan 31, 2026 | Butch | Jan 28 | ❌ NOT RECEIVED |
| 4 | Finance validation sign-off | Butch | Jan 28 | ❌ PENDING |
| 5 | Store Ops questionnaire | Edlice/Dave | Jan 22 | ❌ PENDING |

#### Validation Legend
- ✅ Complete
- ⏳ In Progress / Pending
- 📤 Sent for review
- ⚠️ Partial / Needs refresh
- ❌ Blocking / Missing

### Store P&L 2025 Complete Extraction (2026-01-19)

**Status:** COMPLETE - 226 monthly records from 36 stores

**Source:** Google Drive folder `1QRpFD-hlyP4hWbZWYCMq2Z2peyIwF6ID` (37 P&L files, all stores)

**Output Location:**
```
data/Finance/Store_PnL_2025/
├── extracted/
│   └── STORE_PNL_2025_COMPLETE_2026-01-19.csv  ← FINAL OUTPUT (226 rows, 27 columns)
└── [37 source .xlsx files downloaded from Google Drive]
```

**Scope:**
- 36 stores with monthly data (FAIRVIEW TERRACES has only quarterly - excluded)
- Full year coverage for 5 flagship stores (MEGAMALL, MARKET MARKET, SM MANILA, SM SOUTHMALL, SM VALENZUELA)
- Partial year for stores that opened mid-2025

**Fields Extracted:**
- Header: days_operated, avg_selling_price, cups_sold, avg_daily_cups, food_cost_pct_header
- Revenue: in_store_sales, online_sales, gross_sales, sales_discount, net_sales
- Costs: cost_of_sales, gross_profit, controllable_expenses, labor_cost, profit_after_controllables
- P&L: total_operating_expenses, operating_income, other_income, ebitda, net_income_before_tax, income_tax, net_income_after_tax
- Calculated: profit_margin_pct, food_cost_pct

**Validation:** 10/10 spot checks passed (cell-level comparison to source)

### Employee Master Details (Updated 2026-01-17)
- **765 active employees** in Frappe HR (after PAYROLL_ONLY import)
- **947 total employees** in master file (676 original + 91 PAYROLL_ONLY + 271 resigned)
- **726 with bank accounts** (36 active missing - not in payroll system)
- **Script**: `data/_tools/build_employee_master_complete.py`
- **Missing data report**: `data/HR_Payroll_Masterlists/runs/2026-01-14/employee_master_complete/ACTIVE_EMPLOYEES_MISSING_DATA_REPORT.csv`
- **Statutory IDs** (TIN, SSS, PhilHealth, Pag-IBIG) are NOT mandatory for Frappe import - can enrich later

### HR Data Source Hierarchy (Confirmed 2026-01-17)

**Authoritative order for employee data:**
| Rank | Source | Authoritative For | Notes |
|------|--------|-------------------|-------|
| 1 | **Official Masterlist 2025** | Job titles, departments, employee details | HR-maintained, most accurate |
| 2 | **Imported Employee Master (Jan 2026)** | Frappe HR data | Correctly derived from #1 |
| 3 | **Payroll Package Masterfile** | Salary, compensation data only | Uses simplified titles (NOT for HR) |

**Key Finding (2026-01-17):** Payroll system uses catch-all job titles like "Team Member" for 180+ employees who actually have specific roles (STORE CREW, CASHIER, COMMISSARY CREW, etc.). This is by design for payroll processing - do NOT use payroll data for HR role/department information.

**Evidence:** `data/Finance_REPROCESSING/runs/2026-01-17/10_improved_extraction/EMPLOYEE_DATA_DISCREPANCY_ANALYSIS.md`

### 3-Way Employee Audit (2026-01-16)
A reconciliation of Frappe HR vs Payroll System vs Biometrics revealed:
- **93 PAYROLL_ONLY employees** - Exist in payroll but NOT in Frappe HR (PHP 870K monthly payroll)
- **91 imported** via SQL (2 skipped: duplicate name, Bio ID conflict)
- **Bio IDs assigned:** 9001014 - 9001104
- **3-Way Audit CSV:** `data/Finance_AP_AR/hr_audit/3WAY_AUDIT_FRAPPE_LIVE_2026-01-16.csv`
- **Import SQL:** `data/Finance_AP_AR/hr_audit/PAYROLL_ONLY_EMPLOYEE_INSERT.sql`
- **Script:** `data/_tools/generate_payroll_only_employee_sql.py`

### Finance and Accounting Team (Updated 2026-01-17)

**Active Finance/Accounting Team (8 employees + CFO) - All in `Finance and Accounting - BEI` department:**
| Email | Name | Position | Bio ID |
|-------|------|----------|--------|
| alyssa@bebang.ph | Alyssa May Dimaano | Accounting Manager | 9000740 |
| izza@bebang.ph | Izza May Salva | Accounting Analyst | 9001015 |
| ivy@bebang.ph | Ivy Domingo | Accounting Analyst | 9000896 |
| liezel@bebang.ph | Liezel Acero | Accounting Analyst | 9000930 |
| angelamel@bebang.ph | Angelamel Letara | Accounting Analyst | 9001690 |
| juanna@bebang.ph | Juanna Marie Alcober | Finance Manager | 9001691 |
| denise@bebang.ph | Denise Marielle Almario | Finance Supervisor | 9000816 |
| je-ann@bebang.ph | Je-Ann Torato | Finance Analyst | 9000817 |

**CFO:** butch@bebang.ph - Alessandro Rey Formoso (Bio ID: 9000559)
- Currently in `Finance and Accounting - BEI` department
- Standard practice: CFO should be in `Executive - BEI` org unit (to be moved if desired)

**Reporting Hierarchy (configured 2026-01-17):**
```
CFO (Butch) ← reports_to: NULL
├── Accounting Manager (Alyssa) ← reports_to: Butch
│   ├── Accounting Analyst (Ivy)
│   ├── Accounting Analyst (Izza)
│   ├── Accounting Analyst (Liezel)
│   └── Accounting Analyst (Angelamel)
└── Finance Manager (Juanna) ← reports_to: Butch
    └── Finance Supervisor (Denise) ← reports_to: Juanna
        └── Finance Analyst (Je-Ann) ← reports_to: Denise
```

**Resigned:** Amelia C. Jamito (status: Left, relieving date: 2026-01-15)

### AppSheet Systems (Extracted 2026-01-17)

**3 production AppSheet databases discovered and extracted:**

| Database | Google Sheet ID | Sheets | Records | Purpose |
|----------|-----------------|--------|---------|---------|
| Procurement Compliance | `1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q` | 20 | 9,323 | PR→PO→GR workflow |
| RFP App (Payments) | `1-2xvSVhEI1_U_P5s6rG1-LnSvFil7LzJcdjkADeWAcg` | 14 | 2,865 | Payment requests |
| Compliance App (Ops) | `1diST4oBtW87ma2uY1umUn8EzFSMWGVi0kRL5FPE87iw` | 27 | 35,440 | Store operations |

**Owner:** ashish@bebang.ph (AppSheet developer)

**Key Tables for ERP Integration:**
| Table | Records | Key Fields |
|-------|---------|------------|
| Suppliers | 80 | Supplier Code, Name, Bank Details |
| Purchase Requisitions | 318 | PR No, Requestor, Date Required |
| Purchase Orders | 386 | PO No, Supplier, 46 columns |
| Goods Receipts | 598 | GR No, linked to PO |
| **RFP Data** | **593** | **69 columns - full payment workflow** |
| Payment Proofs | 351 | Proof attachments |
| Inventory | 13,340 | Store inventory (daily) |

**RFP (Payment) Workflow:**
```
Request Created → Review (494 approved) → CFO Approval (470 approved) → Payment
                      ↓                            ↓
                  32 rejected                   7 rejected
```

**Payment Methods:** Bank Transfer (~230), Check (~32)
**Data Quality Issue:** 10+ spelling variations for payment method (needs standardization)

**Extraction Location:** `data/AppSheet_Extraction/runs/2026-01-17/`
**Audit Report:** `data/AppSheet_Extraction/runs/2026-01-17/AUDIT_REPORT.md` (100% accuracy)

**Integration Opportunity:**
- AppSheet → ERPNext auto-sync for approved RFPs
- Auto-create Payment Entry + Journal Entry in ERPNext
- Bank API integration for payment execution

### Employee Data Enrichment System (Updated 2026-01-18)

**MOVED TO BEI TASKS:** The enrichment system has been rebuilt in BEI Tasks (React/Next.js) with enhanced self-service capabilities.

**Live URL:** `https://my.bebang.ph/dashboard/my-profile`

#### System Overview

The self-service enrichment system allows employees to fill in their own missing data with supervisor/HR approval workflow. This decentralizes data collection from HR to employees+supervisors.

#### Core Logic (Field States)

| State | Meaning | Action |
|-------|---------|--------|
| `empty` | No value | Employee fills → Supervisor approval |
| `editable` | Has value, unverified | Employee can edit → Supervisor approval |
| `pending` | Change awaiting approval | Shows old→new value with clock icon |
| `verified` | HR-verified | Read-only, "Request Correction" → Routes to HR |
| `readonly` | System field | No edit allowed (branch, designation) |

#### Approval Workflows

**Standard Fields (contact, emergency, personal):**
```
Employee submits → Supervisor approves → Field updated
```

**Banking Details (dual approval):**
```
Employee submits → Supervisor approves → HR approves → Field updated
```

**Verified Field Corrections:**
```
Employee requests correction (with reason) → HR directly (skips supervisor)
```

#### Features

1. **Self-Service Profile Page** (`/dashboard/my-profile`)
   - View all personal data in 6 collapsible sections
   - Edit editable fields inline
   - Request corrections for verified fields
   - Upload document proofs for gov IDs (optional)

2. **Enrichment Wizard** (auto-shows when profile < 80% complete)
   - Multi-step guided form
   - Only shows incomplete sections
   - Bulk submit all changes in single request

3. **Document Uploads** (for gov IDs)
   - Drag-drop file upload
   - Supports images and PDFs up to 10MB
   - Document preview in approval queue
   - Upload is optional but encouraged

4. **Supervisor Queue** (`/dashboard/queue`)
   - Unified queue for onboarding + enrichment requests
   - Document review for gov ID proofs
   - Approve/Reject/Forward to HR actions

5. **Completeness Dashboard** (`/dashboard/completeness`)
   - Category-by-category completion stats
   - Store heatmap
   - Employee gaps table

#### Custom Fields on Employee DocType (Created 2026-01-18)

**Gov ID Proof URLs:**
| Field | Type |
|-------|------|
| `custom_tin_proof_url` | Attach |
| `custom_sss_proof_url` | Attach |
| `custom_philhealth_proof_url` | Attach |
| `custom_pagibig_proof_url` | Attach |

**Gov ID Verification Flags:**
| Field | Type |
|-------|------|
| `custom_tin_verified` | Check |
| `custom_sss_verified` | Check |
| `custom_philhealth_verified` | Check |
| `custom_pagibig_verified` | Check |

#### Custom Fields on BEI Onboarding Request DocType (Created 2026-01-18)

| Field | Type | Options |
|-------|------|---------|
| `request_type` | Select | new_hire, update, fill_empty, correction |
| `correction_reason` | Small Text | Required for corrections |
| `requires_hr_review` | Check | Auto-set for banking changes |

#### BEI Tasks Repo Reference

For implementation details, see:
- Repo: `../bei-tasks` or `F:\Dropbox\Projects\bei-tasks`
- Context: `.claude/project-brain/CONTEXT.md`
- Progress: `.claude/project-brain/progress/_CURRENT.md`

**Key Files:**
- `app/dashboard/my-profile/page.tsx` - Self-service profile page
- `components/my-profile/enrichment-wizard.tsx` - Guided wizard
- `app/api/my-profile/enrichment/route.ts` - Bulk submit API
- `app/api/onboarding/approve/route.ts` - Approval with smart routing

### Frontend Stack Decision (UPDATED 2026-01-22)

**Decision:** ALL user-facing apps will be built using React + Shadcn UI, connecting to Frappe via API.

**Rationale Document:** `docs/architecture/FRONTEND_ARCHITECTURE_DECISION_2026-01-22.md`

**Why NOT Frappe UI:**
1. Frappe Docker images are IMMUTABLE - every code change requires rebuild (5-15 min cycle)
2. Frappe discontinued their Flutter mobile app due to JS incompatibility
3. Frappe UI designed for web/desktop first, not mobile-optimized for non-techy users
4. Need fast iteration for dynamic, growing app (Vercel deploys in 30-60 seconds)

| Component | Technology | Hosting |
|-----------|------------|---------|
| **All User Apps** | React + Shadcn UI + Next.js | Vercel |
| **Backend/API** | Frappe ERP + HRMS | AWS Docker |
| **Connection** | Frappe REST API | - |

**Current Domains:**
| Domain | Points To | Purpose |
|--------|-----------|---------|
| `hrms.bebang.ph` | Frappe ERP (AWS Docker) | HR/Payroll - same system |
| `erp.bebang.ph` | Frappe ERP (AWS Docker) | ERP alias - same system |
| `lfg.bebang.ph` | Frappe ERP (AWS Docker) | LFG alias - same system |
| `my.bebang.ph` | React App (Vercel) | Employee portal (to be renamed/expanded) |

**Note:** hrms/erp/lfg.bebang.ph are ALL aliases to the SAME Frappe instance.

### Production Database Architecture (Added 2026-01-23)

**CRITICAL DISCOVERY:** The Frappe system at `lfg.bebang.ph` uses a LOCAL Docker database, NOT AWS RDS.

| Component | Container | Details |
|-----------|-----------|---------|
| **Backend** | `frappe_docker-backend-1` | Frappe/ERPNext/HRMS |
| **Database** | `frappe_docker-db-1` | MariaDB (LOCAL, NOT RDS) |
| **Frontend** | `frappe_docker-frontend-1` | Nginx proxy |
| **Site Config** | `/home/frappe/frappe-bench/sites/lfg.bebang.ph/site_config.json` | DB connection |

**RDS Database (`frappe-hrms-db.ctmwomgscn66.ap-southeast-1.rds.amazonaws.com`) is NOT used by the live Frappe instance.**

**Correct Way to Insert Data:**
```bash
# Via AWS SSM
aws ssm start-session --target i-0bbb0ea05168a99f7
cd /home/ubuntu/frappe_docker
docker compose exec backend bench --site lfg.bebang.ph mariadb --execute "SQL HERE"
```

**Test Employees (Production):**
| Employee ID | Email | Roles |
|-------------|-------|-------|
| TEST-STAFF-001 | test.staff@bebang.ph | Store Staff |
| TEST-SUPERVISOR-001 | test.supervisor@bebang.ph | Store Supervisor |
| TEST-AREA-001 | test.area@bebang.ph | Area Supervisor |
| TEST-HR-001 | test.hr@bebang.ph | HR User |

**Password:** `BeiTest2026!`

---

### Sheets Receiver Service (Added 2026-01-31)

**Purpose:** Real-time Google Sheets → ERPNext sync with row-level change tracking.

**Status:** ✅ DEPLOYED & TESTED (2026-01-31)

| Component | Technology | Location |
|-----------|------------|----------|
| Service | FastAPI + Python | `/home/ubuntu/sheets-receiver/` on AWS |
| Container | `sheets-receiver` | Host network mode (port 8765) |
| Database | SQLite | `/app/data/sheets_receiver.db` |
| Webhook | Google Drive Watch API | `https://hq.bebang.ph/sheets-webhook` |

**Watched Sheets:**

| Sheet | Key Column | Spreadsheet ID |
|-------|------------|----------------|
| AR Aging | `invoice_no` | `1puwkr5hzrki9srxq10_jOeb5mfngkbo-VVpydmAf2kQ` |
| Inventory | `item_code` | `1Eh_BhDK_LgdOzJ002F7XUYLBsd4EM8ec7sPz43mudGc` |
| Chart of Accounts | `gl_code` | `1EXCd4Ah2n6Q42vQvTG3dYLFzPsPFhdbzmHp_2wBpN7g` |
| Bank Directory | `account_number` | `1rkQDLREjTG8eyqB7wO5rRsnkjvaasOgmnPcKnqjXNnY` |

**Key Features:**
- Row-level change detection (add/modify/delete with before/after values)
- Suspicious pattern alerts (mass edits, deletions, financial changes)
- Auto-renewing 24-hour watches (Google API limitation)

**API Endpoints:**
- `GET /api/changes` - Recent row-level changes
- `GET /api/changes/modified` - Edits to existing rows only
- `GET /api/alerts` - Suspicious pattern alerts
- `POST /api/sync/{sheet_key}?force=true` - Manual sync trigger

**Pending:** Deploy `hrms/api/erp_sync.py` to Frappe container (currently returns HTTP 417).

**Source:** `hrms/services/sheets_receiver/README.md`

---

### Docker Build Cache - CRITICAL LESSON (Added 2026-01-28)

**Issue:** Docker cache doesn't detect when git repo contents change during `bench get-app`.

**Symptom:** Build completes in ~2 min (should be ~10-15 min), deployed code returns 404 or "module has no attribute" errors.

**Root Cause:** `apps.json` didn't change, so Docker served cached layers from previous builds. The git clone happens inside a build layer, and Docker only checks if the Dockerfile/build args changed.

**Build Time Indicator:**
| Build Time | What It Means |
|------------|---------------|
| ~2 min | CACHED - Code NOT included, old code deployed |
| ~5-10 min | FRESH - Code included, new code deployed |

**Solution:** ALWAYS use `no_cache=true` for code changes:
```bash
gh workflow run "Build and Deploy Frappe HRMS" --repo Bebang-Enterprise-Inc/hrms -f no_cache=true -f run_migrate=true
```

**This is NORMAL Docker behavior**, not corruption or configuration error. The CI/CD workflow has a `no_cache` parameter specifically for this.

---

### Custom Login Page (hq.bebang.ph) - Added 2026-01-28

**Status:** DEPLOYED AND VERIFIED

**Problem:** Frappe's default login page depends on desk CSS bundles. Docker volume desync caused CSS 404s, breaking the login page.

**Solution:** Custom branded login page with self-contained CSS.

**Implementation:**
| File | Purpose |
|------|---------|
| `hrms/www/bei-login.html` | Self-contained login page with inline CSS |
| `hrms/www/bei-login.py` | Context handler (redirect if logged in) |
| `hrms/hooks.py` | `website_redirects` hook: `/login` → `/bei-login` |

**Key Discovery:** Frappe's `/login` route is handled specially and bypasses `page_renderer` hook. Must use `website_redirects` hook instead.

**Verification:**
```bash
curl -sI https://hq.bebang.ph/login | grep -i location
# Location: /bei-login
```

---

### Local Development Environment (Added 2026-01-23)

**Status:** FULLY FUNCTIONAL
**Location:** `docker-dev/`

**Quick Start:**
```bash
cd docker-dev
dev.bat start     # Windows (first run takes 10-15 minutes)
./dev.sh start    # Linux/Mac
```

**Access:**
| URL | Purpose |
|-----|---------|
| http://localhost:8000 | Frappe web UI |
| http://localhost:8000/api/method/frappe.ping | API test endpoint |
| localhost:3307 | MariaDB (user: root, pass: admin) |

**Login:** Administrator / admin

**Development Workflow:**
1. Edit files in `hrms/api/` locally
2. Run `dev.bat sync` (or `./dev.sh sync`) to copy files and clear cache
3. Test API at http://localhost:8000/api/method/hrms.api.<module>.<function>

**Key Files:**
| File | Purpose |
|------|---------|
| `docker-dev/docker-compose.yml` | Container orchestration |
| `docker-dev/dev.bat` | Windows helper script |
| `docker-dev/dev.sh` | Linux/Mac helper script |

**Configuration:**
- Uses upstream Frappe v15, ERPNext v15, HRMS v15 (matches production)
- BEI custom APIs mounted at `/bei-api` and synced on container start
- Named Docker volumes persist data across restarts (`docker-dev_frappe-bench`, `docker-dev_mariadb-data`)
- Bench installed at `/workspace/frappe-bench` (not `/home/frappe/frappe-bench`)

**Helper Commands:**
| Command | Description |
|---------|-------------|
| `dev.bat start` | Start all containers |
| `dev.bat stop` | Stop all containers |
| `dev.bat sync` | Copy API files and clear cache |
| `dev.bat logs` | Follow Frappe logs |
| `dev.bat shell` | Open bash in container |
| `dev.bat migrate` | Run database migrations |
| `dev.bat test` | Test hello API |
| `dev.bat reset` | Delete everything and start fresh |

**IMPORTANT:** To reset completely, run `docker compose down -v` then `dev.bat start`.

**my.bebang.ph Features (built, some unused):**
- Task management (active)
- Employee onboarding workflow (built, not used yet)
- Data enrichment/self-service (built, not used yet)
- Role-based UI customization (supported)
- Forced enrichment on login (supported)

**FINAL SPEC (Approved 2026-01-22):** `docs/plans/MY_BEBANG_PH_FINAL_SPEC_2026-01-22.md`

**34 Features Across 9 Modules:**

| # | Module | Features | Priority | Status |
|---|--------|----------|----------|--------|
| 1 | Daily Store Operations | 4 | P0 (Feb 01) | ✅ BACKEND COMPLETE |
| 2 | Inventory & Ordering | 4 | P0 (Feb 01) | ✅ BACKEND COMPLETE |
| 3 | Receiving & Dispatch | 3 | P0 (Feb 01) | ✅ BACKEND COMPLETE |
| 4 | HR Self-Service | 5 | P1 (Feb 15) | ✅ BACKEND COMPLETE |
| 5 | Employee Profile | 3 | P1 (Built) | ✅ COMPLETE |
| 6 | Communication & Feedback | 4 | P2 (Mar 01) | ✅ BACKEND COMPLETE |
| 7 | Supervisor Tools | 4 | P1 (Feb 15) | ✅ BACKEND COMPLETE |
| 8 | Dashboards & Analytics | 3 | P2 (Mar 01) | ✅ BACKEND COMPLETE |
| 9 | **Employee Clearance** | 4 | **P1 (Feb 15)** | ✅ BACKEND COMPLETE |

**Backend Build & Testing Status (2026-01-25): ✅ PRODUCTION READY**
- **Build Plan:** `docs/plans/MY_BEBANG_PH_BACKEND_BUILD_PLAN_2026-01-25.md` - COMPLETED
- **Testing Plan:** `docs/plans/MY_BEBANG_PH_TESTING_PLAN_2026-01-25.md` - COMPLETED
- **Commits:** `371c300f2` (build), `e9a3bf6cb` (fixes)
- **DocTypes Created:** 22 new (36 total BEI DocTypes)
- **API Endpoints:** 86 total across 7 modules
- **Testing Results:**
  - Phase 1 (Environment): ✅ ENV_READY
  - Phase 2 (71 Endpoints): ✅ ENDPOINTS_PASS (71/71)
  - Phase 3 (5 Workflows): ✅ WORKFLOWS_PASS (23/23 steps)
  - Phase 4 (Production): ✅ PRODUCTION_VERIFIED (5/5 critical endpoints)

**NEW Module 9 - Employee Clearance (addresses ~30 day manual process):**
- 21-day SLA target (IT: 3d, Finance: 5d, HR: 7d, Ops: 3d, Buffer: 3d)
- Auto-compute final pay from Frappe Payroll
- Self-service COE download after clearance

**36 BEI DocTypes Created** (25 standalone + 11 child tables):
- 7 Store Ops DocTypes (2026-01-24): BEI Store Order, BEI Store Order Item, BEI Store Receiving, BEI Store Receiving Item, BEI Distribution Trip, BEI Trip Stop, BEI FQI Report
- 22 New DocTypes (2026-01-25): Approval Queue, Store Visit, Weekly Labor Plan, CEO Complaint, Kudos, Announcement, Support Ticket, Cycle Count, Inventory Variance, Shelf Life Extension, Coverage Request, Opening/Closing Reports, Midshift Check, POS Data Upload

**NEW MODULE REQUIRED: Inventory Count App (2026-02-16)**

Discovered via Google Chat with Alyssa + forensic email audit of accounting team:
- **Problem:** Physical inventory counts done by 3rd party (Tricern Food Corp) on hard copies, then manually encoded into COS RECON spreadsheet by accounting team. Jan 31 count still not consolidated by Feb 16 (16 days delay).
- **Solution:** Build inventory count feature in my.bebang.ph allowing counters to input counts directly on mobile device, eliminating hard-copy-to-spreadsheet bottleneck.
- **Impact:** Unblocks monthly P&L production (COS RECON is the #1 blocker for January 2026 P&L)
- **Reference:** `Apex replacement/README.md` Section 10, `scratchpad/INVENTORY_COS_WORKFLOW_2026-02-16.md`

**Skills & Agents:**
- `.claude/skills/shadcn-react/SKILL.md` - Shadcn UI CLI 3.0, charts, sidebar
- `.claude/skills/frappe-external-app/SKILL.md` - React + Shadcn + frappe-react-sdk
- `.claude/agents/frappe-deploy.md` - Deployment specialist agent

**Repo Structure:**
- Keep separate repos (polyrepo) for BEI-ERP and BEI-Tasks
- BEI-ERP is SSOT for project context (CONTEXT.md, PROGRESS.md)
- BEI-Tasks contains the React frontend code

### Implementation Plans
- **FINAL SPEC (SSOT):** `docs/plans/MY_BEBANG_PH_FINAL_SPEC_2026-01-22.md`
- Original RLM Discovery: `docs/plans/MY_BEBANG_PH_COMPLETE_FEATURE_SPEC_2026-01-22.md`
- Frappe Apps Plan (12 apps, 29 DocTypes): `docs/plans/FRAPPE_UI_APPS_COMPREHENSIVE_PLAN_2026-01-14.md`
- Ops Forms & SOPs: `docs/plans/OPS_FORMS_EXTRACTION_REPORT_2026-01-14.md`
- Inventory Playbook: `docs/plans/Completed/INVENTORY_CONTROL_AND_STOCK_MOVEMENTS_PLAYBOOK_2026-01-12.md`

## Extraction Registry System (Added 2026-01-21)

**Purpose:** Track data from SOURCE → DOWNLOAD → EXTRACTION → AUDIT → VALIDATION → ERP IMPORT lifecycle.

### Registry Manager
- **Script:** `data/_tools/extraction_registry_manager.py`
- **Logic:** UPSERT (Update if exists, Insert if new) using `(department, source_file_name)` as unique key

### Department Registries
Located in `data/04_Project_Management/Extraction_Registry/`:

| Registry | Department | Pre-populated |
|----------|------------|---------------|
| `FINANCE_EXTRACTION_REGISTRY.csv` | FINANCE | 11 entries |
| `HR_EXTRACTION_REGISTRY.csv` | HR | 4 entries |
| `PROCUREMENT_EXTRACTION_REGISTRY.csv` | PROCUREMENT | 3 entries |
| `SCM_EXTRACTION_REGISTRY.csv` | SCM | 5 entries |
| `OPERATIONS_EXTRACTION_REGISTRY.csv` | OPERATIONS | 3 entries |

### Registry Schema (28 columns)
| Group | Fields |
|-------|--------|
| **Source** | source_system, source_file_name, source_sheet_count, source_row_count, source_column_count |
| **Extraction** | extraction_skill_used, extracted_file_path, extraction_date, extraction_status, extraction_notes |
| **Audit** | audit_skill_used, audit_status, audit_accuracy_pct, audit_cells_checked, audit_checks_passed, audit_checks_failed, audit_notes |
| **Validation** | validation_status, validated_by, validation_date, validation_notes |
| **ERP Import** | erp_import_status, erp_doctype, erp_records_created, erp_import_date, erp_import_notes |

### Separation of Concerns
| Skill | Updates |
|-------|---------|
| `/extract-data-v2` | Source fields + Extraction fields |
| `/audit-extraction-v2` | Audit fields only |
| Manual / Team | Validation fields |
| Import process | ERP Import fields |

### Python API
```python
from extraction_registry_manager import upsert_entry, find_entry, update_audit

# Register new extraction
entry = upsert_entry(
    department='HR',
    source_file_name='EMPLOYEE_MASTER_2026-01-14',
    source_type='EXCEL',
    extraction_status='COMPLETE',
    ...
)

# Find existing entry
entry = find_entry(department='HR', source_file_name='EMPLOYEE_MASTER_2026-01-14')

# Update audit results
update_audit(
    extraction_id=entry['extraction_id'],
    department='HR',
    audit_status='PASS',
    audit_accuracy_pct=100.0,
    ...
)
```

## Marketing Brain - Knowledge Base (Added 2026-01-26)

### Overview

A comprehensive database of ~350 marketing ideas extracted from books and videos, designed for AI-driven campaign brainstorming.

**Location:** `Marketing/`
**Full Documentation:** `Marketing/README.md`

### Context Size

| Content | Size | Tokens |
|---------|------|--------|
| Ideas files (33 JSON) | 1.96 MB | ~503K |
| Video transcripts (78) | 5.7 MB | ~1.5M |
| Book PDFs (17) | 68 MB | N/A (binary) |

**Challenge:** 503K tokens exceeds 200K context window by 2.5x. Cannot load all at once.

### Source Material

| Source | Items | Ideas Extracted |
|--------|-------|-----------------|
| Books | 17 PDFs from 7 authors | 130 ideas |
| Videos | 78 transcripts from 5 speakers | 219 ideas |

**Authors:** Hormozi, Sutherland, Cialdini, Priestley, Greene, Chou, others

### Recommended Framework: Memory Service MCP

Use the **existing Memory Service MCP** with structured taxonomy:

```
Tags: source, author, category, applicability, effort, tested, priority
```

**Brainstorming Workflow:**
1. `search_by_tag(["pricing", "qsr"])` - Query by category
2. `retrieve_with_quality_boost("bundle deals")` - Semantic search
3. `find_connected_memories(hash)` - Find related ideas
4. `rate_memory(hash, 1)` - Rate good ideas

### Alternative: Graphiti MCP (Future)

For production-grade temporal knowledge graphs with entity extraction.
- Requires Docker + Neo4j/FalkorDB
- ~$5-15 OpenAI API cost for ingestion

**References:**
- [Graphiti GitHub](https://github.com/getzep/graphiti)
- [Graphiti MCP by Zep](https://www.getzep.com/product/knowledge-graph-mcp/)
- [Knowledge Graph vs Vector DB](https://www.falkordb.com/blog/knowledge-graph-vs-vector-database/)

---

## Recursive Language Model (RLM) Methodology (Added 2026-01-20)

### When to Use RLM

**Use RLM for tasks that exceed context window limits:**
- Large Excel files (>1000 rows or many sheets)
- Multi-sheet workbooks requiring complete extraction
- Any task where loading full content would cause context overflow
- Complex extractions requiring cell-level verification

**Key Principle:** File content stays on disk, processed via REPL/chunks, never loaded fully into context.

### RLM Pattern Overview

```
1. DISCOVERY (Mandatory Phase 0)
   - List ALL sheets/tabs BEFORE extraction
   - Never assume structure - always discover
   - Output: discovery_report.json with complete schema

2. CHUNKED PROCESSING
   - Process file in chunks (e.g., 50 rows at a time)
   - Sub-agents handle individual chunks
   - Each chunk produces structured output

3. PROGRAMMATIC AGGREGATION
   - Python REPL aggregates sub-agent results
   - Final output assembled from verified chunks
   - No hallucination possible (data never in context)
```

### Critical Fix: Mandatory Discovery Phase

**Problem (Pre-2026-01-20):** Extractions often missed sheets because:
- Claude assumed file structure instead of discovering it
- Multi-sheet files had only first sheet extracted
- Audits gave FALSE PASS because they didn't check sheet coverage

**Solution:** Phase 0 (Discovery) is now MANDATORY:
```python
# BEFORE any extraction, run discovery:
python -c "
import pandas as pd
import json

# Get ALL sheets
excel_file = pd.ExcelFile('source.xlsx')
sheets = excel_file.sheet_names

discovery = {
    'total_sheets': len(sheets),
    'sheets': []
}

for sheet in sheets:
    df = pd.read_excel(excel_file, sheet_name=sheet)
    discovery['sheets'].append({
        'name': sheet,
        'rows': len(df),
        'columns': len(df.columns),
        'column_names': list(df.columns)
    })

print(json.dumps(discovery, indent=2))
"
```

### Critical Fix: Audit CHECK 0 (Sheet Coverage)

**Problem:** Audits gave 100% accuracy on incomplete data because they only checked extracted cells, not missing sheets.

**Solution:** CHECK 0 now runs FIRST and fails immediately if sheets are missing:
```python
# CHECK 0: Sheet Coverage (runs before any cell verification)
source_sheets = get_source_sheet_names(source_file)
extracted_sheets = get_extracted_sheet_names(extracted_file)

if len(extracted_sheets) < len(source_sheets):
    return {"status": "FAIL", "reason": "MISSING_SHEETS",
            "missing": list(set(source_sheets) - set(extracted_sheets))}
```

### Extraction Skills (Updated 2026-01-20)

| Skill | Use Case | Key Feature |
|-------|----------|-------------|
| `/extract-data-v1` | Row-by-row extraction | Complete data preservation |
| `/extract-data-v2` | Semantic extraction | Key financial items by month |
| `/audit-extraction-v1` | Sample-based audit | Cell-level verification (50 samples) |
| `/audit-extraction-v2` | RLM-powered audit | 6 checks including sheet coverage |

### Test Results (2026-01-20)

**Test File:** `2025 P&L - MARKET MARKET.xlsx` (13 sheets, 12 months + Sheet1)

| Extraction | Audit v1 | Audit v2 |
|------------|----------|----------|
| v1 (13 sheets, 901 rows) | PASS 100% | PASS (6 checks) |
| v2 (13 sheets, 120 items) | PASS 100% | PASS (6 checks) |

**Evidence:** `.claude/rlm_state/test3_all_audits_results.json`

### RLM State Directory

All RLM intermediate files live in `.claude/rlm_state/`:
- `discovery_report.json` - Sheet/schema discovery output
- `chunks/` - Processing chunks for sub-agents
- `*_extract_*.json` - Extraction outputs
- `*_audit_*.json` - Audit results

### Skills & Documentation

- **Extract v1:** `.claude/skills/extract-data-v1/SKILL.md`
- **Extract v2:** `.claude/skills/extract-data-v2/SKILL.md`
- **Audit v1:** `.claude/skills/audit-extraction-v1/SKILL.md`
- **Audit v2:** `.claude/skills/audit-extraction-v2/SKILL.md`
- **RLM Core:** `.claude/skills/rlm/SKILL.md`

## S172 Defects #11 + #20 — Operational Patterns (Append 2026-04-09)

### Defect #11 — Employee soft-delete order dependency (2-pass PUT pattern)

When changing an Employee from `Active` to `Left`, Frappe's Employee validator requires `relieving_date` to be populated BEFORE `status` flips. A single PUT with both fields in the same payload may fail because validators run in field-declaration order.

**Correct order:**
1. First PUT: set `relieving_date` alone
2. Second PUT: set `status = "Left"`

Agents + UI code that soft-delete employees should always do two sequential calls, not one combined payload.

### Defect #20 — Self-service OT filing requires a real attendance record

By design, `/dashboard/hr/overtime/apply` requires the employee to already have an Attendance record (from an ADMS biometric punch) for the requested OT date. This is NOT a bug — OT must be anchored to a real clock-in so it can be cross-checked against biometric logs.

If the employee worked but their attendance wasn't captured (device offline, card not scanned, etc.), the correct workflow is:

1. Employee files an **Attendance Correction Request** (separate doctype)
2. Supervisor approves the correction — an Attendance record is created
3. Employee returns to the OT apply page and files OT against the now-existing attendance record

The OT apply backend error message (`hrms/api/overtime_request.py:94`) was updated in S172 Phase 7 to explain this flow to the user so crew don't mistake it for a system bug.
