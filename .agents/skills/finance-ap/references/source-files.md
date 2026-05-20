# Source Files — Where Everything Lives

Quick lookups for the canonical location of each artifact.

## Apps Script source

| What | Where |
|---|---|
| **v3 (LATEST production)** | `F:\Dropbox\Projects\BEI-ERP\CEO\CashFlow\intercompany_gl\ap_view_hourly_sync_v3.gs` (1,047 lines) |
| v2 (legacy, kept for back-compat baseline seed) | `F:\Dropbox\Projects\BEI-ERP\CEO\CashFlow\intercompany_gl\ap_view_hourly_sync.gs` (538 lines) |
| Cashflow Tracker bound script | `F:\Dropbox\Projects\BEI-ERP\CEO\CashFlow\cashflow_hourly_sync.gs` |
| Live deployment ID | Apps Script project ID is **different** from the sheet ID; see `script-v3.md` for the web app URL |

## Team guide docs (Google Docs, all created 2026-04-21)

| Doc | ID | Repo backup |
|---|---|---|
| BEI AP Master - Team Guide | `1HM60vlRn_1ZE0K5TmX_mPgooR8U0q_xdjvqgZhtN5JI` | `tmp/finance_ap_audit/files/AP_MASTER_TEAM_GUIDE.docx` |
| Card 2 - Filing CAPEX Invoice (Ms. Mel) | `1RJM-D-mD2ulflB6odtKXObN8vjteYGzvpTobzLcIhbk` | `tmp/finance_ap_audit/files/FILING_CAPEX_INVOICE.docx` |
| Card 3 - Your PCM Workbook (Angela) | `1nfFqae_d-LwKUA47xIMf-Bt5OZFhaAZCg5y95eWtZkY` | `tmp/finance_ap_audit/files/PCM_WORKBOOK.docx` |
| Card - Finance + Compliance | `1VPDdnra8oPc-agLcAj-XV_OD2rM2ztiAxzFwdT_-wTo` | `tmp/finance_ap_audit/files/FINANCE_AND_COMPLIANCE.docx` |
| BEI AP Flow Diagram (PNG) | `1F6IzUYzHE2G2cVyU9x07GH_D9wohXKUr` | `tmp/finance_ap_audit/files/BEI_AP_FLOW_DIAGRAM.png` |
| BEI Receiving — Team Playbook | `1XOBZ1J4SO_OAkh9AG1UiB9V1wdvTDuF_ncGk60VSbBs` | `tmp/finance_ap_audit/files/BEI_RECEIVING_TEAM_PLAYBOOK.docx` |
| BEI Deliveries — 3PL Dock Card | `1zlb5ZAXmyN1Y_HaXOJl_rNc-6cXy-Q1d2Uw3xbIq5EY` | `tmp/finance_ap_audit/files/BEI_DELIVERY_DOCK_CARD.docx` |
| BEI Supplier SI Upload — FAQ | `1YERz3hHrekYoOVORTnRTumjjnMRch0hjVjLyFe3Qd9A` | `tmp/finance_ap_audit/files/BEI_SUPPLIER_SI_UPLOAD.docx` |

The plain-text extracts (for grep) live at `tmp/finance_ap_audit/extracted_text/*.txt`.

## Audit + investigation artifacts

| What | Where |
|---|---|
| 2026-04-15 forensic audit | `CEO\CashFlow\FORENSIC_AUDIT_2026-04-15.md` |
| 2026-04-15 accounting team briefing | `CEO\CashFlow\ACCOUNTING_TEAM_BRIEFING_2026-04-15.md` |
| CEO/Cashflow README (top-level) | `CEO\CashFlow\README.md` |
| Intercompany GL plan | `CEO\CashFlow\intercompany_gl\2026-04-15-Intercompany-GL-Plan-v2.docx` |
| Tagging list (for legacy entries) | `CEO\CashFlow\intercompany_gl\Intercompany-Tagging-List.xlsx` |
| Intercompany tagging review | `CEO\CashFlow\intercompany_gl\INTERCOMPANY_TAGGING_LIST.md` |
| Audit categories | `CEO\CashFlow\intercompany_gl\AUDIT_CATEGORIES.md` |
| Audit totals | `CEO\CashFlow\intercompany_gl\AUDIT_TOTALS.md` |
| Per-section reviews | `CEO\CashFlow\intercompany_gl\REVIEW_SUPPLIERS_SOA.md`, `REVIEW_HO_AP.md`, `REVIEW_BGF_CAPEX.md`, `REVIEW_OTHER_SHEETS.md` |
| Consolidated AP CSV (post-reconciliation) | `CEO\CashFlow\intercompany_gl\consolidated_ap.csv` |

## Frappe-side AP integration

| What | Where |
|---|---|
| ERP sync entry point (Python, Frappe app) | `hrms\api\erp_sync.py` |
| AP opening sync function | `hrms.api.erp_sync.sync_ap_opening` (POST endpoint `/api/method/hrms.api.erp_sync.sync_ap_opening`) |
| Sheets Receiver (EC2 service) | `hrms\services\sheets_receiver\*.py` |
| Sheets Receiver config (which sheets to watch) | `hrms\services\sheets_receiver\config.py` |
| Sheets Receiver main + webhook | `hrms\services\sheets_receiver\main.py`, `webhook.py` |
| AP exception reports | `hrms\services\sheets_receiver\ap_exception_reports.py` |
| Tests | `hrms\tests\test_erp_sync.py`, `test_sheets_receiver_*.py` |

## BDO reconciliation (post-payment cleanup)

| What | Where |
|---|---|
| Weekly cron script | `scripts\weekly_bdo_reconciliation.py` |
| Catchup script (2026-05-01) | `scripts\catchup_bdo_clearance.py` |
| GitHub Actions workflow | `.github\workflows\weekly-bdo-reconciliation.yml` |
| Schedule | Tue-Fri 07:00 PHT |

## Session transcripts (read-only, for reference)

| Session | Date range | JSONL path |
|---|---|---|
| `048a293d-4930-461b-ae25-112adc3a3493` | 2026-04-14 → 04-21 | `~\.claude\projects\F--Dropbox-Projects-BEI-ERP\048a293d-*.jsonl` |
| `cea426b3-ed2c-407a-a516-2cb419c94c85` (S210 receiving) | 2026-04-18 → 04-26 | same dir |
| `f66941ce-82bf-4a60-ae78-711f94383088` (AP Cashflow build) | 2026-04-20 → 04-27 | same dir |
| `df990b2b-a895-4f50-b9f4-7e2ce2cebf94` (AP Cashflow v2) | 2026-04-21 → 04-27 | same dir |
| `16af35c5-a0e4-4c14-be51-d60b97a45b1c` (BDO catchup) | 2026-04-29 → 05-02 | same dir |
| `517586f9-ff15-4d3d-b71d-d63a8d41ef24` (TODAY — current) | 2026-05-12 | same dir |

To resume any of these:
```bash
claude --resume <session-id>
```

## Quick-reference IDs (for paste)

```
AP Master:                  1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c
FPM:                        1t4wJLiAfIMJm6fe-x6h4eZn_S_Lx1AGN5ORd5Ywhcyw
Compliance AppSheet:        1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q
PCM (native):               1_5BSZeNL9A_o5QO6WD4L42gGjYY6-yCDfgTp01y0fpo
BGF Investments:            1dfIyAeGH_5ga_mjA1o-WWN9xM6VO3v7XKKoU1Jtq1eI
Bank Balances:              19kSR8HQdveZVleMZORGQetHXVCxaeDy6EMlKfe2G77w
Cashflow Tracker:           1W2GERTwbODqfbHM70XpJJEtFwL-jIPbb2zzwC0Rcfeg
AP Master Team Guide:       1HM60vlRn_1ZE0K5TmX_mPgooR8U0q_xdjvqgZhtN5JI
ARCHIVED AP Opening SOA:    1ZHe2VoAFa94ET4I68C1jWM7nMzTdTCvttwZbICaLtB4
ARCHIVED AP Opening HO:     1jSwZRyIPisU4jiKS-Tn9VFoLukQI8UNoW13Hoov-75Y
ARCHIVED Stores Replenish:  19qfXxz7N67oNcys9lb7XnmNzZCSpEdWQWXbRxaVTKN8
```

```
Apps Script web app URL:    https://script.google.com/macros/s/AKfycbw-AuqJq6OyMV6DGarGWEruDoez04OETlWFQoeppNjvzoeSOJOomPOZNsVPE9iuV6ZC_Q/exec
Token (?key=...):           bei-ap-sync-2026-04
Default route:              ?fn=refreshAllTabs
Dry run:                    ?fn=refreshAllTabs&dryRun=1
Legacy v2 wipe-rebuild:     ?fn=refreshAllTabs&mode=v2  (DESTRUCTIVE)
Health check:               ?fn=runDiagnostics
```

## Related skills

- `/procurement` — Sheets Receiver, Frappe sync endpoints, AP opening Python side (`sync_ap_opening`). Stale as of 2026-05-12 (last updated 2026-03-11 — predates this AP system entirely).
- `/dr-gr-rfp` — Receiving infrastructure (DR → GR → RFP). Upstream of AP — once a GR exists, an RFP gets created in FPM, which ultimately writes back to AP Master via the v3 sync.
- `/google` — Drive/Sheets/Docs API patterns. Use this when you need to add/remove permissions or pull doc content programmatically.

## Service account (for any programmatic checks)

| Item | Value |
|---|---|
| File | `credentials/task-manager-service.json` |
| Email | `task-manager-service@quiet-walker-475722-s2.iam.gserviceaccount.com` |
| Domain-wide delegation | Enabled — impersonate `sam@bebang.ph` |
| Required scope (Drive ops) | `https://www.googleapis.com/auth/drive` |
| Required scope (Sheets read) | `https://www.googleapis.com/auth/spreadsheets.readonly` |
| Required scope (Sheets write) | `https://www.googleapis.com/auth/spreadsheets` |
| Required scope (Apps Script source pull) | `https://www.googleapis.com/auth/script.projects` |
