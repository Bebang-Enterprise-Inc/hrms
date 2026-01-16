# Current Progress (Rolling 30 Days)

> **Window:** 2025-12-17 to 2026-01-16
> **Last Updated:** 2026-01-16
> **For detailed topic history, see the topic-specific files in this folder.**

---

## 2026-01-16 (Today)

### Employee Data Enrichment Campaign COMPLETE
- **93 PAYROLL_ONLY employees identified** in 3-way audit (Frappe vs Payroll vs Biometrics)
- **SQL Import:** 91/93 employees imported (674 → 765 active employees)
  - 2 skipped: duplicate "RS BRYAN PE" and Bio ID conflict
  - Bio IDs assigned: 9001014 - 9001104
- **Script:** `data/_tools/generate_payroll_only_employee_sql.py`
- **SQL File:** `data/Finance_AP_AR/hr_audit/PAYROLL_ONLY_EMPLOYEE_INSERT.sql`
- See: `hr-employee-import.md`

### Employee Enrichment Dashboard BUILT
- **PWA Dashboard:** `/hrms/dashboard/enrichment`
- **Backend API:** `hrms/api/enrichment.py` (8 endpoints)
- **Frontend:** `frontend/src/views/enrichment/Dashboard.vue`
- **Custom Fields Migration:** `hrms/patches/v16_0/add_employee_enrichment_fields.py`
- **Features:**
  - Summary cards (Total, Verified, Pending, Issues)
  - Progress bar by store
  - Employee list with status badges
  - Mark as Verified / Report Issue actions
  - Store filter for multi-store supervisors
- **Deployment Status:**
  - ✅ Custom fields created (8 fields on Employee DocType)
  - ✅ Frontend PWA built and deployed
  - ❌ Backend API blocked - Docker image uses `--preload`, hot-patching doesn't work
  - **Next Step:** Rebuild Docker image `bebang/erpnext-hrms:v15` with code changes

### Store Supervisor Training Guide CREATED
- **Output:** `data/04_Project_Management/Training/STORE_SUPERVISOR_DATA_VERIFICATION_GUIDE.docx`
- **Script:** `data/_tools/generate_store_supervisor_training_guide.py`
- **Contents:** 12 pages covering:
  1. Overview (Purpose, Timeline, Success Criteria)
  2. Your Role as Data Steward
  3. Accessing the Dashboard
  4. Verification Checklist
  5. How to Update Records
  6. Common Issues and Solutions
  7. Escalation and Support

---

## 2026-01-15

### SCM Centralized Database COMPLETE (Supabase)
- **Initial Bulk Load:** 60,462 rows from 13 Google Sheets files
- **Categories:** Commissary (32,652), Inventory (16,650), Procurement (10,524), Logistics (355)
- **Daily Sync Automation:** Task Scheduler at 6:00 AM
- **Key Table:** `scm_data` in Supabase
- **Assessment:** `SCM_DATA_MIGRATION_ASSESSMENT_2026-01-15.md`
- See: `inventory-opening.md`

### Store Dashboard Extraction COMPLETE (Supabase)
- **Total Rows:** 10,760 from 44 stores
- **Sheet Types:** INVENTORY (4,840), WASTAGE (4,486), SS RECORDS (725), PMIX RECORDS (709)
- **Daily Sync Automation:** Task Scheduler at 6:30 AM
- **Key Table:** `store_dashboard_data` in Supabase
- **Audit:** `STORE_DASHBOARD_AUDIT_2026-01-15.md`
- See: `inventory-opening.md`

### Store Code Dictionary Created
- 44 store codes mapped to full names
- Cross-validated with ADMS device logs
- SM Taytay (SMTAY) confirmed opened Jan 9, 2026
- File: `STORE_CODE_DICTIONARY.md`

### Data Quality Fixes
- SMV: Fixed duplicate rows with inconsistent date formats
- TGR: Manually inserted missing Jan 11 data
- All 43 stores now have complete Jan 1-14 data (SMTAY expected partial - opened Jan 9)

### Scripts Created
- `data/_tools/sync_scm_to_supabase.py` - SCM daily sync
- `data/_tools/bulk_load_scm_to_supabase.py` - SCM initial load
- `data/_tools/extract_store_dashboards.py` - Store dashboard initial extraction
- `data/_tools/sync_store_dashboards.py` - Store dashboard daily sync
- `scripts/sync_scm_daily.bat` - Task Scheduler wrapper
- `scripts/sync_store_dashboards_daily.bat` - Task Scheduler wrapper

### Critical SKU Analysis COMPLETE
- **Top 10 SKUs identified** for daily counting based on:
  - PMIX sales data (23,463 units, Jan 1-14)
  - SCM issuance data (32,536 transactions)
  - BOM composition and unit costs
- **Top 3:** Frozen Ice Milk, Leche Flan, Buko Pandan Jelly
- **Added to:** ERP Master Plan Section 3.6
- See: `inventory-opening.md`

### Business Cutoff Confirmed
- **2:00 AM** confirmed as business day cutoff
- Added to ERP Master Plan (resolved decision)

### Permission Matrix APPROVED (Blocker Resolved)
- **File:** `docs/erp/PERMISSION_MATRIX_2026-01-15.md`
- **Roles Defined:** 12 operational + 8 SCM + 15+ HQ roles
- **DocType Permissions:** Full C/R/W/D/S/A/P matrix for all BEI DocTypes
- **Named Users:** 28 HQ/management personnel mapped
- **Key Updates:**
  - Herdie Hernandez (VP Ops) terminated 2026-01-16 - Ops reports to CFO
  - Drew Manansala confirmed as BD Director (Contractor, PHP 120K/mo)
  - BD team (3 members) added to system roles
- **Status:** **APPROVED by CEO** (2026-01-15) - CFO/Ops/HR to review within 2 weeks of go-live

### ERP Master Data Import COMPLETE (SQL Bulk)
- **Method:** Direct SQL via AWS SSM (same pattern as employee import)
- **UOM:** 12 units imported (Pack, Can, Kg, Jar, Bottle, etc.)
- **Item Groups:** 10 groups (Products → Raw Material/Commissary/Packaging/Non-Stock)
- **Warehouse:** 51 warehouses (All → Commissary/External/Stores hierarchy)
- **Supplier:** 77 suppliers from Supplier Master
- **Item Master:** 92 items from SKU Master
- **Total Records:** 242 records imported in < 5 seconds
- **Verification Counts in ERP:**
  - UOM: 247 total (12 new + existing ERPNext standard)
  - Warehouse: 62 total (51 new + parent nodes)
  - Supplier: 110 total (77 new + existing)
  - Item: 177 total (92 new + existing)
- **Scripts:** `data/_tools/generate_master_data_sql.py`
- **SQL Files:** `data/_tools/sql_output/MASTER_DATA_IMPORT.sql`, `ITEM_IMPORT_FIXED.sql`
- **Note:** Nested set rebuild required for Item Group and Warehouse trees

### AP/AR Opening Balance Extraction COMPLETE
- **Source:** Google Drive API with Domain-Wide Delegation
- **Users Searched:** alyssa@, butch@, izza@, ivy@, accounting@ (all @bebang.ph)
- **AP Balance Extracted:** PHP 24,422,197.67 (158 records, 36 suppliers)
- **AR Finding:** MINIMAL - BEI is B2C retail (cash/card), no external credit customers
- **Aging Summary:**
  - 16-30 Days Overdue: PHP 2,791,738.11
  - Above 31 Days Overdue: PHP 21,630,459.56
- **Top 3 Suppliers:**
  1. RIGHT GOODS SOUTH OPERATIONS INC. (PHP 3.86M)
  2. MAX'S BAKESHOP INC. (PHP 2.70M)
  3. SUZUYO WHITELANDS LOGISTICS, INC. (PHP 2.51M)
- **Files Generated:**
  - `data/Finance_AP_AR/AP_OPENING_BALANCE_2026-01-15.csv`
  - `data/Finance_AP_AR/AP_SUPPLIER_SUMMARY_2026-01-15.csv`
  - `data/Finance_AP_AR/AP_AR_EXTRACTION_REPORT_2026-01-15.md`
  - `data/Finance_AP_AR/google_drive_exports/*.csv` (17 raw files)
- See: `finance-apex.md`

---

## 2026-01-14

### ADMS Unknown PIN Investigation COMPLETE
- **Root Cause:** Legacy Bio IDs vs New Bio IDs mismatch
- 70,000+ "ADMS Unknown" checkins were legitimate device punches from legacy PINs
- **Resolution:** Proceed with device reset + re-enrollment (Option B)
- See: `biometrics-adms.md`

### Frappe HR Employee Import COMPLETE (676 employees)
- Deleted 69,521 checkins + 535 employees via SQL
- Imported 676 active employees via SQL INSERT (< 5 seconds)
- **Method:** Direct SQL via AWS SSM (NOT API - 100x faster)
- See: `hr-employee-import.md`

### Employee Master Data Consolidation COMPLETE
- Merged all data sources: HR Masterlist, SSOT files, Bio ID assignments, Payroll Master, UnionBank
- Output: `EMPLOYEE_MASTER_COMPLETE_2026-01-14.csv` (947 employees total, 676 active)
- See: `hr-employee-import.md`

### ADMS Connectivity Re-Test (Addendum 122)
- SM Caloocan: **CONNECTED** (SN corrected)
- The Terminal: **NOT CONNECTED** (IT needs to verify device config)
- Current: 44/45 devices connected
- See: `biometrics-adms.md`

### Frappe UI Apps Comprehensive Plan (Addendum 123)
- Analyzed 50+ Ops/SCM/Commissary processes
- Recommended 12 Frappe apps in 4 bundles
- Technical scope: 29 DocTypes, 12 PWA views, 3 Desk pages
- See: `erp-migration.md`

### ERP Migration Master Plan + Opening Inventory
- Master plan finalized: `docs/plans/ERP_MIGRATION_MASTER_PLAN_2026-01-14.md`
- Opening inventory extracted: `data/Inventory/OPENING_INVENTORY_SUMMARY_2026-01-14.csv`
- See: `erp-migration.md`, `inventory-opening.md`

---

## 2026-01-13

### Herdie VP Ops Removal (Addendums 108-111)
- Evidence pack prepared from Jan 09 emails + contract clauses
- For-cause termination report generated (termination date: 2026-01-16)
- Middleby pause contacts identified

### Staff Coverage Workflow (Addendum 112)
- Workflow designed for staff coverage + temporary PIN punching
- Relief staff handling defined
- See: `docs/plans/STAFF_COVERAGE_WORKFLOW_AND_BIOMETRICS_TEMP_PIN_PLAN_2026-01-13.md`

### 3MD/Bulacan Commissary Variance (Addendum 116)
- Dan NTE evidence extraction
- Bidding/scope-change audit initiated

### Master Tracker Updates (Addendums 113-116)
- Glossary + per-item recommendations added
- Plans folder cleanup: moved completed to `plans/Completed/`
- Ops + HR prioritized (align to fast-track pilot)

---

## 2026-01-12

### Inbox Intake Sprint (Addendums 95-98)
- Sales + Finance + Logistics + Store Daily Monitoring extraction
- Data quality check for ERP import readiness
- Google Drive/Sheets service account tested

### POS/Online Sales Export Requirements (Addendums 99-101)
- POS export requirements memo
- Website/online sales export requirements memo
- Omnichannel sales-to-cash playbook created

### Inventory Control Workflow (Addendum 103)
- ERP-first inventory plan
- Sales-to-cash decisions confirmed

### Department Inputs Master Tracker (Addendums 105-107)
- Comprehensive per-department inputs checklist
- Follow-ups de-duplicated
- Ana designated as SSOT owner

---

## 2026-01-11

### ERP Automation Fast-Track (Addendums 84-88)
- Week 1-4 plan created
- Guessing-free requirements artifacts
- Pilot + rollout readiness assets

### Procurement Transition (Addendums 91-92)
- Mae runbook created
- Authority memo + supplier notice

### Private Email Audits (Addendums 89-90)
- Aldrin mailbox review
- Attachments completed

---

## 2026-01-10

### Employee SSOT Rebuild (Addendums 79-80)
- Missing identity pack audit
- DOB/Gender backfill from HR audit return
- Schedule files reprocessed

### Private Email Audits (Addendums 81-83)
- Herdie ↔ Middleby review
- "3 day work week" correspondence reviewed

---

## 2026-01-09

### ADMS Pilot + Improvements (Addendums 72-77)
- Follow-ups audit + archiving
- ADMS Unknown Bio ID catcher implemented
- Device automation command queue framework
- MB10-VL manual evidence collected
- Remote commands wire-format validated

### UnionBank Payroll Batches (Addendum 78)
- Frappe employee upload list created

---

## 2026-01-08

### ADMS Receiver Build (Addendums 64-71)
- ZKBioTime licensing alternatives researched
- Bio ID re-enrollment plan audit
- Option A (ADMS Receiver) step-by-step plan
- Receiver built + E2E simulation on PROD
- 1 real device ready (Head Office 1)
- Comprehensive cloud test

### Google Drive Backup (Addendums 66-67)
- Incremental sync implemented
- Full project backup (non-secret)

---

## 2026-01-07

### Biometric Clean Slate Decision (Addendums 52-63)
- Factory reset all 44 machines decision made
- Re-enrollment plan generated (672 employees)
- Cloud biometric setup guide created
- Device SN mapping + real-time integration audit
- Management org chart generated + corrections

### Supplier Master Finalization (Addendum 59)
- Reviewed GC list
- 184 verified suppliers

### Frappe HR Demo (Addendum 60)
- Granted Employee Create/Delete access (Ronald + Archie)

---

## 2026-01-06

### Ops Ingestion Audit (Addendum 46)
- Sales close artifacts analyzed
- ERP wiring gaps identified

### HR/Finance Return Audit (Addendums 47-51)
- 10% critical gaps identified
- Biometrics inbox: date ranges extracted
- HR duplicate Bio IDs confirmed
- Finance return completeness assessed

---

## 2026-01-05

### Training Program (Addendums 34, 45)
- 1-week intensive program designed
- Department-specific plans created
- Operations data ingestion (manuals, checklists, labor plans)

### Procurement + Supplier Processing (Addendums 39-44)
- RFP Type processing
- HR + Finance meeting responses processed
- Supplier verification cleanup
- New Supplier ID generation

### Follow-Ups Consolidation (Addendums 33, 36-38)
- Master consolidated decisions document
- Final project docs sync
- Chimes chat analysis

---

## 2026-01-04

### APEX Analysis (Addendums 19-20)
- Store P&L last-month coverage: 43/43 matched
- Store identity triangulation across 3 sources

### Procurement + Policy (Addendums 21-31)
- Prompting best practices added
- Real-time ERP wiring follow-ups
- PO >500K approval policy (two-step)
- Procurement draw.io validation
- Inbox cleanup + questionnaire consolidation
- Ops follow-ups consolidated
- Ops Manual 2024 processed
- Cross-dept meeting agenda prepared
- DOCX conversion tool + batch conversion

---

## 2025-12-31

### ERP Docs Audit + Master Data
- Raw file handling normalized
- Master data exports generated:
  - Warehouse tree (47 rows)
  - POS item master (38 items)
  - BOM crosswalk + canonical (250 rows)
  - Finance payroll review (179 rows)

---

## 2025-12-25

### Data Files Recovery
- Located missing team questionnaires + store sheets
- Created recovery bundle at `C:\Users\Sam\backups\data_Recovery_2025-12-25\`

---

## 2025-12-24

### Analytics Dashboard
- Upgraded to Refine v5 + shadcn/ui
- Deployed to Vercel (bebang-analytics)
- Supabase data lake adopted
- 5,563 daily records ingested from 41 stores
