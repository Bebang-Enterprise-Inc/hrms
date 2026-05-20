# History — How the BEI AP System Was Built

Chronological narrative from 2026-04-14 (Sam first asked about AP automation) to 2026-05-12 (today). Each entry is sourced from session transcripts (`~/.claude/projects/F--Dropbox-Projects-BEI-ERP/*.jsonl`) plus git history.

## 2026-04-14 — The starting question

**Tuesday 02:40 PHT.** Session `048a293d-4930-461b-ae25-112adc3a3493` begins. Sam: "Check our automations we did have the AR, AP, Suppliers SOA automatically extracted daily before. I need you to find that."

Sam provides URLs:
- AP: `1ZHe2VoAFa94ET4I68C1jWM7nMzTdTCvttwZbICaLtB4` (the future archived A1)
- AR: `1puwkr5hzrki9srxq10_jOeb5mfngkbo-VVpydmAf2kQ`

**02:53 PHT** — Discovery: a Docker service `sheets-receiver` is running on EC2 (same server as Frappe). It registers Google Drive Watches on both sheets and syncs to Frappe `Purchase Invoice` via webhook. **The sync may have stalled.** This is the foundation that will later become the `/procurement` skill.

## 2026-04-15 — Forensic audit + ₱30M variance discovery

**01:05 PHT.** Forensic audit script written: `tmp/finance_extract/forensic_audit.py`.

**01:06 PHT.** Audit results: `[suppliers_ap] 'SUPPLIERS SOA' formal dims: 1520 x 33, non-empty: 740 rows, 15502 cells`. Date range: 2024-12-16 to 2026-12-20.

**01:10 PHT.** Forensic Audit report saved at `CEO/CashFlow/FORENSIC_AUDIT_2026-04-15.md`. Findings:
- SUPPLIERS SOA — 738 invoices, LIVE
- AP AGING PER SUPPLIER — live
- ₱35.5M supplier gap between the two views

**01:27 PHT.** Root cause of the ₱30M variance:
- No enforced cross-reference between two systems (~₱25M effect)
- SUPPLIERS SOA shows ₱73.94M "open"
- RFP Summary shows different number

**01:31 PHT.** Reconciliation script written: `tmp/finance_extract/reconciliation.py`. Joins SUPPLIERS SOA against RFP Summary via RFP ID + invoice_no.

**01:33 PHT.** Reconciled TRUE Inventory AP: **₱51.42M**.
- IN PIPELINE (RFP processing, will be paid): **410 invoices, ₱42.6M**
- OPEN — no RFP in pipeline (stuck): **41 invoices**

**01:39 PHT.** Accounting team briefing doc: `CEO/CashFlow/ACCOUNTING_TEAM_BRIEFING_2026-04-15.md`.

**08:33 PHT.** Q1 surfaces: Where did BKI commissary payables move after March 17?
**11:34 PHT.** 8-week projection math complete (starting state Cash = ₱120,955,043 from Bank Balances 04/14).

## 2026-04-16 — The "PAID residual" bug, the BKI double-counting bug, and proportional VAT

**09:06 PHT.** Formulas preserved across 6 audit files (AP Opening Balance HO, etc.).

**14:56 PHT.** First version of `ap_view_hourly_sync.gs` written. Functions: `setupHourlyTrigger`, `removeTrigger`, `onOpen`, `refreshAllTabs`, `normalizeKey`, `toNum`. 11,449 chars. Saved at `CEO/CashFlow/intercompany_gl/ap_view_hourly_sync.gs`. This is **v1** (informally — not yet called v1; just "the script").

**15:05 PHT.** Sam: "Now fix the same in the Apps Script."

**15:27 PHT.** **PAID residuals bug found.** The HO AP sheet had 206 rows marked PAID but with **outstanding balance NOT zeroed** — the team's auto-zeroing formula had failed.

**15:28 PHT.** Fixed → HO AP corrected from ₱38.4M to **₱33,400,855**. The ₱5M difference was 206 PAID residuals (₱2.3M) + 87 FPM-matched paid items (₱2.7M) that needed zeroing.

**16:13 PHT.** **BKI double-counting bug found.** The Supplier Payments tab had `+ bki` rows that were ALREADY in `real_payables`. Fixed in both Python and Apps Script. Supplier Payments dropped from ₱37.7M to **₱25.7M**.

**22:33 PHT.** Apps Script v2 written (15,152 chars). Now reads: FPM RFP Summary (payment status overlay), Suppliers SOA from 1ZHe... (invoice ledger), AP Opening Balance HO from 1jSwZRy... (HO + CAPEX). "One invoice = one row. No duplication."

**23:10 PHT.** Apps Script v2.1 with VAT/EWT overlay (17,394 chars).

**23:15 PHT.** Investigation: Non-VAT Suppliers vs Team Error. Pattern analysis of which suppliers have VAT = 0 by design vs by error.

**23:41 PHT.** **Proportional VAT fix.** Compliance has VAT at the PO level (totals across multiple invoices under one PO). The script now splits each PO's total VAT proportionally across invoices by `invoice_amount / po_total_amount`. This is the algorithm baked into v3's `syncTaxFieldsFromCompliance_()`.

**23:42 PHT.** Backup of Compliance App taken before VAT correction was applied: `BACKUP — Procurement Compliance AppSheet — 2026-04-17 (before VAT correction)`.

## 2026-04-17 — Cashflow Tracker + bank balances baseline

**00:38 PHT.** Updates to `CEO/CashFlow/README.md`.

**01:12 PHT.** **CASHFLOW TRACKER — CEO** sheet created (`1W2GERTwbODqfbHM70XpJJEtFwL-jIPbb2zzwC0Rcfeg`).

**02:03 PHT.** **BEI Bank Balances — LIVE** sheet created (`19kSR8HQdveZVleMZORGQetHXVCxaeDy6EMlKfe2G77w`). 58 BEI bank accounts.

**02:38 PHT.** `cashflow_hourly_sync.gs` written for the Cashflow Tracker (10,492 chars).

**04:19 PHT.** Backup of FPM taken: `BACKUP — FINANCE PAYMENT MONITORING (pre-BDO-catchup 2026-04-17)`.

**04:20 PHT.** Sam edits AP Master (`1ZHe...`) — last recorded human Sam edit on the archived sheet.

## 2026-04-18 → 2026-04-21 — Sprint S210 (Receiving) + Sprint S211 (AP cutover)

**2026-04-18 onwards.** Session `cea426b3-ed2c-407a-a516-2cb419c94c85` starts. Ian's question: "What does usually delay the GRs?" — kicks off the **S210 sprint** for the DR → GR → RFP receiving system. This is documented in the `/dr-gr-rfp` skill.

**2026-04-20 04:11 PHT.** Plan update: `PLAN_UPDATE_2026-04-20.md`. Discovery that "Pinnacle uses Viber" for delivery confirmations — completely outside the digital flow.

**2026-04-20 04:27 PHT.** In parallel session `f66941ce-82bf-4a60-ae78-711f94383088`: **"The sheet has 14 tabs, not 10."** Sam corrects an earlier assumption about how many tabs the AP Master would have. (Final live count is 17.)

**2026-04-20 04:47 PHT.** **Apps Script v2** (full version): "CONSOLIDATED AP View — Hourly Auto-Sync (v2 — with logging + self-heal + email alerts)". 26,014 chars. Saved at `CEO/CashFlow/intercompany_gl/ap_view_hourly_sync.gs`. This is the production v2.

**2026-04-20 05:28 PHT.** Apps Script error in Tagalog: `"Wala kang pahintulot na tumawag kay ScriptApp.getProjectTriggers"` (You don't have permission to call ScriptApp.getProjectTriggers). Side effect of running as the service account (which has no Apps Script permissions) vs running as Sam (who does). Fix: switch trigger model from `ScriptApp.newTrigger()` to Cloud Scheduler + web-app.

**2026-04-20 10:27 PHT.** **String-to-number coercion bug.** Source has `"00048"` (text-formatted invoice number), Apps Script writes to a General-formatted cell, Sheets coerces to `48`. It's a join-key issue, not a data gap. Fixed by storing keys with leading zeros preserved.

**2026-04-20 11:07 PHT.** PCM and BGF sheets created as NATIVE Google Sheets (`1_5BSZeNL...` and `1dfIyAeGH_...`), replacing the old uploaded XLSX. This decouples them from the Drive→Frappe upload pipeline.

**2026-04-20 13:28 PHT.** Apps Script v2 committed at 28,461 chars.

**2026-04-20 18:47 PHT.** **Apps Script v3 written.** Field-sync architecture replaces wipe-rebuild. Saved at `CEO/CashFlow/intercompany_gl/ap_view_hourly_sync_v3.gs`. 55,227 chars (1,047 lines). Constants `HUMAN_OWNED_COLS` and `SCRIPT_OWNED_COLS` defined. Three sync functions: `syncStatusFieldsFromFPM_`, `syncTaxFieldsFromCompliance_`, `seedNewInvoicesFromSources_`. Conflict logging to `_sync_conflicts`. Dry-run mode via `?dryRun=1`.

**2026-04-21 — S211 cutover day.**
- Team Guide docs created (all 8):
  - 00:49 — AP Master Team Guide, CAPEX Filing card, PCM Workbook card
  - 00:50 — BEI AP Flow Diagram (PNG)
  - 01:24 — Finance + Compliance card, all docs final version
  - 03:46-03:47 — BEI Receiving Team Playbook, Dock Card, Supplier SI Upload FAQ (S210 deliverables)
- 4 sheets retired: 05 - AP Opening Balance (PHP 24.4M), 05 - AP Opening Balance Head Office, STORES REPLENISHMENTS RECON Y2026, CHECK DISBURSEMENT TRACKER
- Receiving sheets ownership transferred from `commissary.team@bebang.ph` → `sam@bebang.ph` (S215)

## 2026-04-27 — Juanna's last day

Per the Team Guide: "Until Mon 2026-04-27, Juanna Alcober — Finance lead, Finance Payment Monitoring, approval flow. From Tue 2026-04-28, Denise Almario takes over."

Juanna resigns. FPM ownership transferred to Denise.

## 2026-04-28 → 2026-05-01 — BDO weekly reconciliation catch-up

Session `16af35c5-a0e4-4c14-be51-d60b97a45b1c`. Multi-day cleanup:

**2026-04-30 12:27 PHT.** Catchup diff for the BDO weekly reconciliation:
- Files processed: 4 (HO + Stores × 2 weeks)
- BDO check transactions extracted: 50 (47 unique after dedup)
- BDO total cleared amount: **₱8,147,162.61**
- FPM rows matched: **32**
- Total FPM ₱ to flip to `Paid/ Cleared`: **₱7,181,061.43**
- Orphans (in BDO but not FPM): 15 (mostly intercompany/petty)

**2026-05-01 03:31 PHT.** Production writes complete:
- FPM `RFP Summary`: **32 rows updated**, **16 status flips** to `Paid/ Cleared`, 80 cells written, ₱7.18M of cleared checks visible
- Drive `_Archive/`: 4 BDO source files moved (idempotency for next cron)
- Sample verified: 8/8 sampled rows show correct status + BDO Cleared Date + amount

**This is the most recent script-side fix.** From here on, the AP Master gets the updated status via the hourly v3 sync.

## 2026-05-07 — Butch, Alyssa, Juanna all resigned (final confirmation)

Per session memory note (`finance-team-2026-04-15.md`): "FINALIZED 2026-05-07 — Butch (CFO), Alyssa (head accountant), Juanna (head of finance) ALL resigned. CFO seat vacant indefinitely. Denise is finance lead. NEVER ask for their approval/signature in any plan or audit. Sam approves alone."

Their write access on AP Master and other sheets should have been revoked but **as of 2026-05-12 some still appear in the permissions matrix** — see `permissions.md`.

## 2026-05-12 (today) — Avis's access complaint surfaces

Avis Lyndelle Principe pings Sam: "Access to Receiving Masters and other related links are currently restricted. Hi Sir Sam I do not have access as well, my account is currently restricted. Before I already requested from you the access and it was already granted. but upon checking now, I am again restricted. By the way, I checked with Accounting regarding the AP Master. They mentioned that every time they update the sheet, the entries they input disappear afterwards."

Investigation confirms (this session):
- Avis IS Editor on `/dr-gr-rfp` receiving sheets (Sheet A, C, D — but missing from Sheet B Pinnacle)
- Avis is NOT on any AP Master / FPM / archived AP sheet — root cause of her "blocked" complaint
- "Entries disappear" is one of three things (see `troubleshooting.md`):
  - Team typing on archived `1ZHe...` instead of live AP Master `1bQ6mO...`
  - Team typing in SCRIPT_OWNED columns (which get overwritten by hourly sync)
  - v2 wipe-rebuild still firing somewhere

Skill `/finance-ap` created (this skill) to consolidate the knowledge that was scattered across 4 session transcripts, 8 docs, and the v3 script source.

## Key numbers (today)

- **Total AP (Suppliers + HO):** ₱59.5M (per archived A1's AP AGING PER SUPPLIER as of 2026-05-12) — vs email-SOA-derived ₱33–60M likely-unpaid range
- **Sync cadence:** hourly at xx:12 PHT
- **Sheet count in ecosystem:** 11 live or recently-touched + numerous opening balance snapshots per store

## Patterns to remember

1. **Sam writes scripts in Claude sessions, deploys directly to Apps Script editor.** The repo copy is often the last-committed but not necessarily the live-deployed. Always confirm against the live web app.
2. **Permissions drift.** New team members get added to /dr-gr-rfp sheets but not /finance-ap, or vice versa. Resignations don't always get cleanup.
3. **The accounting team holds onto retired sheets.** Edits happen on `1ZHe...` even months after S211 cutover. Either revoke or rename to `[ARCHIVED]` so it's visually clear.
4. **The Compliance App is the source of truth for VAT.** Don't accept "team will fix VAT on AP Master" as a solution — fix it in Compliance, let the sync propagate.
5. **One-day reconciliations happen in batches.** BDO catchup, Compliance VAT correction — these come in bursts that briefly inflate `_sync_conflicts`. Expected.
