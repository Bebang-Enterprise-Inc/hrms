# Start Here (Frappe HR / BEI ERP Workspace)

**Last Updated:** 2026-02-26  
**Owner:** Sam Karazi  
**Next Review:** 2026-03-05

---

## ⚠️ CRITICAL: Correct Working Directory

**ALWAYS start Claude Code from:**
```
F:\Dropbox\Projects\BEI-ERP
```

**NOT from:**
```
C:\Users\Sam\Projects\Claude\BEI-ERP  ← EMPTY, DO NOT USE
C:\Users\Sam\.cursor\Projects\*       ← LEGACY, DO NOT USE
```

---

## Workspace Overview

This workspace contains **3 connected branches**:

1. **Frappe ERP/HR (core system + project brain)** ← THIS REPO
   - Location: `F:\Dropbox\Projects\BEI-ERP`

2. **BEI Tasks (supplements ERP workflows)**
   - Location: `C:\Users\Sam\Projects\Claude\bei-tasks`
   - Deployed: https://my.bebang.ph

3. **Bebang Analytics (dashboards + ETL supporting ERP decisions)**
   - Location: `C:\Users\Sam\.cursor\Projects\bebang-analytics`

---

## Infrastructure Documentation

| Document | Description |
|----------|-------------|
| [Dropbox Setup](./infrastructure/DROPBOX_SETUP.md) | File sync configuration, working directory setup |
| [Doppler Setup](./infrastructure/DOPPLER_SETUP.md) | Secrets management (API keys, credentials) |
| [AWS Setup Guide](./infrastructure/AWS_Setup_Guide.md) | AWS infrastructure (EC2, RDS) |
| [Google OAuth Runbook](./GOOGLE_OAUTH_RUNBOOK.md) | Google Workspace integration |
| [Frappe MCP Setup](./FRAPPE_MCP_SETUP.md) | MCP server configuration |
| [Repository Inventory](./architecture/REPOSITORY_INVENTORY.md) | Exact repo names, remotes, branches, commits |
| [Infrastructure Inventory](./architecture/INFRASTRUCTURE_INVENTORY.md) | AWS/network/DNS/cert/secrets/data-store/backups snapshot |
| [Hosting and Domains](./architecture/HOSTING_AND_DOMAINS.md) | Domain-to-hosting mapping and evidence divergence register |
| [Flow Catalog](./architecture/FLOW_CATALOG.md) | Cross-department flow index + L3 flow coverage status |
| [Architecture Snapshot (2026-02)](./architecture/snapshots/2026-02.md) | Monthly architecture baseline and open evidence divergences |
| [Branch Intent (Rajat Handoff)](./architecture/BRANCH_INTENT_handoff-rajat-sad-2026-02-26.md) | Explains this handoff branch scope and guardrails for future agents |

---

## ERP Program (Questionnaires, Follow-ups, Master Data)

### Project Brain (READ FIRST)
- `data/04_Project_Management/Import_Log/CONTEXT.md` - Decisions, policies, SOT
- `data/04_Project_Management/Import_Log/PROGRESS_INDEX.md` - Routing table
- `data/04_Project_Management/Import_Log/progress/_CURRENT.md` - Last 30 days

### Department Data
- Questionnaires (answers): `data/Department_Specs/`
- Follow-ups (pending): `data/Follow-Ups/`
- Inbox (new items): `docs/inbox/`

### Quick Pointers
- `docs/erp/README.md`
- `docs/erp/ERP_DEPARTMENT_PLANS_2025-12-28.md`
- `docs/erp/DEPARTMENT_STATUS_Frappe_Readiness_2025-12-31.md`

---

## ERP Migration (Feb 1, 2026 Go-Live)

**Master Plan:** `docs/plans/ERP_MIGRATION_MASTER_PLAN_2026-01-14.md`

### Key Documents
| Document | Purpose |
|----------|---------|
| Migration Master Plan | Overall timeline and phases |
| Frappe Apps Plan | 12 apps specification |
| Ops Forms & SOPs | Forms extraction report |

### Master Data (Ready for Import)
| Data | Location |
|------|----------|
| Supplier Master | `data/Procurement_Database/runs/2026-01-07/outputs/SUPPLIER_MASTER_FINAL_2026-01-07.csv` |
| SKU/Item Master | `data/Procurement_Database/FORENSIC_EXTRACTION/Copy of Compliance App Database__SKU_Master.csv` |
| Opening Inventory | `data/Inventory/OPENING_INVENTORY_SUMMARY_2026-01-14.csv` |
| Warehouse Tree | `docs/erp/WAREHOUSE_TREE_2025-12-31.csv` |

### Key Decisions (2026-01-14)
- **Valuation:** Moving Average (ERP costing) + FIFO (Ops stock rotation)
- **Commissary:** Bebang Kitchen Inc. (separate company, intercompany transfers)
- **PO Approval:** Mae ≤500K sole, Mae+Butch >500K joint, CEO for new vendors

---

## Finance Data Extraction

**Latest Extraction:** 2026-01-17

| Metric | Value |
|--------|-------|
| Files Processed | 55 |
| Sheets Extracted | 318 |
| Total Rows | 114,162 |
| Success Rate | 100% |

**Output Location:** `data/Finance_REPROCESSING/runs/2026-01-17/P1_owner_impersonation/`

See: `data/Finance_REPROCESSING/runs/2026-01-17/EXTRACTION_SESSION_SUMMARY.md`

---

## HR Masterlist Import

### Brain Files
- `docs/masterlist-import/CONTEXT.md`
- `docs/masterlist-import/PROGRESS.md`
- `data/01_HR_&_Payroll/Masterlists/_Project_Brain/`

### Quick Pointer
- `docs/masterlist/README.md`

---

## Slash Commands Available

| Command | Description |
|---------|-------------|
| `/extract-data` | Extract and validate data from spreadsheets |
| `/extraction-audit` | Forensic audit of extracted data |
| `/reset-brain` | Reset project brain context |

Commands are defined in: `.claude/commands/`

---

## Secrets Management

**DO NOT** store credentials in files. Use Doppler:

```bash
# Get a secret
doppler secrets get GOOGLE_CLIENT_ID --plain

# Run with secrets injected
doppler run -- python my_script.py
```

Project: `bei-erp` | Config: `dev`

See: [Doppler Setup](./infrastructure/DOPPLER_SETUP.md)

---

## Organization Rules

1. **User-facing docs** should be reachable from `docs/` at max 2 folders deep
2. **Data files** go in `data/` organized by domain
3. **Credentials** go in Doppler, NOT in files
4. **Always work from Dropbox location** - never legacy Cursor paths
