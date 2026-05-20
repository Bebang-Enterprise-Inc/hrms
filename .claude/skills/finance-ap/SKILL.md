---
name: finance-ap
description: BEI Accounts Payable operating reference — the BEI AP Master sheet (3 data-entry + 7 summary tabs), the v3 field-sync Apps Script that auto-updates it, and the 4-sheet ecosystem (FPM, Compliance, PCM, AP Master) that feeds it. Use whenever the user mentions AP Master, Suppliers SOA, Head Office invoices, CAPEX filing, payable aging, Finance Payment Monitoring, RFP status, BDO check clearing, Ms. Mel's data entry, Denise's payment status updates, Angela's PCM, the hourly auto-sync script, "entries disappearing", access issues on AP-related sheets, or any question about how BEI tracks supplier liabilities from invoice entry through payment release. Also covers the 4 archived sheets (05-AP Opening Balance SOA, 05-AP Opening Balance HO, STORES REPLENISHMENTS RECON, CHECK DISBURSEMENT TRACKER) and why they're being retired.
---

# Finance AP — BEI Accounts Payable System

This skill captures everything about BEI's Accounts Payable infrastructure: the BEI AP Master sheet, the Apps Script that auto-syncs it hourly, the supporting sheets (FPM, Compliance, PCM, BGF), the ownership contracts, and the history of fixes. Built up from the April–May 2026 S211 cutover work.

## Why this exists

Before the 2026-04-21 cutover, seven separate sheets tracked the same AP information. Every time Juanna marked an invoice Paid, Denise had to re-type the status into two or three other sheets. Different sheets showed different numbers for the same invoice. The team spent hours each week reconciling sheets that should have agreed.

The fix: **one sheet** (BEI AP Master) is the single accounts payable register. Each piece of info has **one owner** who types it in one place. Every other tab/sheet reads it via the **v3 field-sync Apps Script** running hourly via Cloud Scheduler.

Net effect: Ms. Mel types invoices in the data-entry tabs. Denise tags payment status in FPM. Cayla tags VAT/EWT in Compliance. The 7 summary tabs (All Liabilities, Needs RFP, Check Released, In Pipeline, VAT Gaps, PAID, With Finance) auto-populate. Sam sees the live picture in Cashflow Tracker. No one types the same thing twice.

## The system in one diagram

```
        DATA-ENTRY SOURCES                          AP MASTER (target)
        ─────────────────                          ──────────────
                                                   ┌─────────────────┐
   ┌──────────────────┐                            │ Suppliers SOA   │ ← data entry
   │ FINANCE PAYMENT  │ ─── status, RFP No, ─────► │ Head Office     │ ← data entry
   │ MONITORING (FPM) │     check, method, date    │ CAPEX           │ ← data entry
   │ Denise / Juanna  │                            ├─────────────────┤
   └──────────────────┘                            │ All Liabilities │ ← auto
                                                   │ Needs RFP       │ ← auto
   ┌──────────────────┐                            │ With Finance    │ ← auto
   │ COMPLIANCE APP   │ ─── VAT, EWT, vatable ───► │ Check Released  │ ← auto
   │ Cayla / Luwi     │                            │ In Pipeline     │ ← auto
   └──────────────────┘                            │ VAT Gaps        │ ← auto
                                                   │ PAID            │ ← auto
   ┌──────────────────┐                            └─────────────────┘
   │ 05 AP Opening    │     append-only seed                ▲
   │ Balance — SOA    │ ──► (initial baseline)              │
   │ (archived)       │                            ┌────────┴────────┐
   └──────────────────┘                            │   AP MASTER     │ ──► PCM (per-store CAPEX)
                                                   │ v3 field-sync   │ ──► Cashflow Tracker
   ┌──────────────────┐                            │ hourly via CSch │ ──► sheets-receiver → Frappe
   │ 05 AP Opening    │     append-only seed       └─────────────────┘
   │ Balance — HO     │ ──►
   │ (archived)       │
   └──────────────────┘
```

## At a glance — the 4 live + 4 archived sheets

| # | Sheet | ID | Role | Owner |
|---|---|---|---|---|
| **L1** | **BEI AP Master** (titled "AP Suppliers - Payment Status (Auto-View)") | `1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c` | **THE AP register** (17 tabs: 3 entry + 7 summary + 7 internal) | sam@bebang.ph |
| L2 | FINANCE PAYMENT MONITORING (FPM) | `1t4wJLiAfIMJm6fe-x6h4eZn_S_Lx1AGN5ORd5Ywhcyw` | RFP approval + payment status | denise@bebang.ph |
| L3 | Procurement Compliance AppSheet Database | `1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q` | VAT, EWT, PO Items source | Ashish + Cayla/Luwi |
| L4 | Bebang - Project Cost Monitoring (PCM) | `1_5BSZeNL9A_o5QO6WD4L42gGjYY6-yCDfgTp01y0fpo` | Per-store CAPEX budgets (67 tabs) | Angela |
| L5 | BGF, INVESTMENTS and CAPEX | `1dfIyAeGH_5ga_mjA1o-WWN9xM6VO3v7XKKoU1Jtq1eI` | Partner Reserve, Franchise Fee, BGF capital | Angela |
| L6 | BEI Bank Balances — LIVE | `19kSR8HQdveZVleMZORGQetHXVCxaeDy6EMlKfe2G77w` | Daily bank balance (58 accounts) | Denise |
| L7 | CASHFLOW TRACKER — CEO | `1W2GERTwbODqfbHM70XpJJEtFwL-jIPbb2zzwC0Rcfeg` | CEO dashboard (cash position, 8-week forecast) | sam@bebang.ph |
| **A1** | 05 - AP Opening Balance (PHP 24.4M) | `1ZHe2VoAFa94ET4I68C1jWM7nMzTdTCvttwZbICaLtB4` | **ARCHIVED** — SOA opening balance baseline | (no owner) |
| A2 | 05 - AP Opening Balance Head Office | `1jSwZRyIPisU4jiKS-Tn9VFoLukQI8UNoW13Hoov-75Y` | **ARCHIVED** — HO opening balance baseline | (no owner) |
| A3 | STORES REPLENISHMENTS RECON Y2026 | `19qfXxz7N67oNcys9lb7XnmNzZCSpEdWQWXbRxaVTKN8` | **DISCONTINUED** — intercompany cash, not third-party AP | (no owner) |
| A4 | CHECK DISBURSEMENT TRACKER | (see history) | **DISCONTINUED** — replaced by BDO weekly reconciliation | (no owner) |

## The Apps Script in one paragraph

The hourly auto-sync runs as a Google Apps Script web app deployed at:
- **URL:** `https://script.google.com/macros/s/AKfycbw-AuqJq6OyMV6DGarGWEruDoez04OETlWFQoeppNjvzoeSOJOomPOZNsVPE9iuV6ZC_Q/exec`
- **Token:** `bei-ap-sync-2026-04` (sent as `?key=...` query parameter)
- **Trigger:** Cloud Scheduler hits the URL hourly with `?fn=refreshAllTabs`
- **Source in repo:** `CEO/CashFlow/intercompany_gl/ap_view_hourly_sync_v3.gs` (1,047 lines, v3 = field-sync)

The script reads from FPM (status, RFP no, check, method), Compliance (VAT, EWT), and the two archived AP Opening sheets (initial seed for unmatched invoices), then writes **only to SCRIPT_OWNED columns** in the three data-entry tabs. It never overwrites a non-blank human cell. Conflicts get logged to the `_sync_conflicts` tab.

## When to load which reference

| You want to know... | Read |
|---|---|
| **Per-role training: which sheet each person uses, which tabs they CAN'T edit, clickable links, lock verification proof (2026-05-14)** | **`references/team-training-2026-05-14.md`** ← read this for anything team-facing |
| The 17 tabs of AP Master + 19-column schema of each edit tab + ownership-per-column | `references/ap-master-structure.md` |
| How the v3 field-sync Apps Script works, the doGet entry point, the 3 sync functions, conflict logging | `references/script-v3.md` |
| Every sheet ID, doc ID, owner, modified date, tab list across the entire ecosystem | `references/sheets-inventory.md` |
| Who edits what, why each role has what access, current permissions per sheet | `references/permissions.md` |
| Why entries disappear, why someone can't access a sheet, how to debug sync issues | `references/troubleshooting.md` |
| Chronological narrative (Apr 14 → today) of how the system was built and fixed | `references/history.md` |
| Where the script lives in the repo, where the team guide docs are, all the file paths | `references/source-files.md` |
| The 7 legacy training guide docs (Receiving Playbook, Dock Card, SI Upload FAQ, AP Master Team Guide, CAPEX Filing card, PCM Workbook card, Finance & Compliance card) — superseded by team-training-2026-05-14.md but kept for reference | `references/team-guides.md` |

Each reference file is independent — no chains. Read only what the current question needs.

## Standing rules

1. **One owner per field.** Never type the same thing into two sheets. If you see overlap, one of the two is being auto-generated — find which.
2. **AP Master data-entry tabs (Suppliers SOA / Head Office / CAPEX) are HUMAN-OWNED.** Ms. Mel types invoices here. The script preserves these cells.
3. **AP Master summary tabs (All Liabilities / Needs RFP / etc.) are SCRIPT-OWNED.** Only Sam edits them manually; the team reads only.
4. **Status changes happen in FPM, not in AP Master.** Denise tags Paid/Cleared in FPM; the script propagates within the hour.
5. **VAT/EWT changes happen in Compliance AppSheet, not in AP Master.** Cayla/Luwi tag here; the script propagates within the hour.
6. **CAPEX entries require a Store dropdown selection.** Ms. Mel cannot save a CAPEX row without picking a store.
7. **PCM's bottom section is live-fed from AP Master per store.** Angela's old manual paid/owed columns are RETIRED — do not re-add them.
8. **The 4 archived sheets are READ-ONLY references.** Do not type new entries into them; they are kept for audit trail and opening-balance lookup only.
9. **The script is owned by sam@bebang.ph.** Container-bound; runs under Sam's auth. All audit log entries show as Sam in the sheet revision history — that's expected.
10. **DRY_RUN before destructive sync.** When fixing the script, hit `?fn=refreshAllTabs&dryRun=1` first; writes go to `_dry_run_preview` tab.

## Bridge — Fractional CFO + Due Diligence Auditor (engaged 2026-05-14)

**Bridge** (`bridge-ph.com`) is the external accounting firm BEI engaged as **fractional CFO** and to **audit the whole system for Due Diligence readiness**.

| What you'll see | What it means |
|---|---|
| `accountant.outsource@bridge-ph.com` writing in Denise's `Project: 2-Week Payment Plan` sheet | Bridge fractional CFO doing AP review — AUTHORIZED, not an unauthorized outside contractor |
| Bridge questions about AP aging / SOA / invoice trails | They're building the DD package; answer fully — they're acting on Sam's behalf |
| Bridge requests for read access to other sheets (FPM, Compliance, PCM, BGF) | Grant via Sam; reader/commenter typically sufficient for DD review |
| Bridge proposing schema changes | Treat like any other improvement proposal — Sam approves; if accepted, plan a sprint (e.g., S255) |

The Bridge engagement makes ACL audits more permissive than the "outside contractor = security risk" default. **Don't downgrade or remove `accountant.outsource@bridge-ph.com` without explicit Sam approval.**

## Critical operational facts (as of 2026-05-12)

- **TOTAL PAYABLES (Suppliers SOA + HO):** ₱59.5M (from `AP AGING PER SUPPLIER` tab on archived `1ZHe...` sheet) — but cross-validated against email SOAs gives **₱33–60M likely-unpaid** (see `troubleshooting.md`).
- **Aging breakdown (Suppliers only):** NOT YET DUE ₱215K / 0-30 ₱1.73M / 31-60 ₱3.0M / 61-90 ₱16.4M / 91-120 ₱17.8M / over 120 ₱20.5M.
- **Top single AP supplier:** RIGHT GOOD SOUTH OPERATIONS INC — ₱6.15M (all in 91-120 bucket).
- **Sam is sole approver** while CFO seat is vacant (Butch resigned 2026-05-07).
- **Denise is finance lead** since 2026-04-28 (Juanna left 2026-04-27).
- **Sync runs hourly** at xx:12 PHT each hour. Last sync: see `_sync_log_v3` tab in AP Master.

## 🟥 INCIDENT 2026-05-12 — Commissary tab wipe + the 14-tab strict lock

**What happened:** Avis reported "every time the team updates the sheet, entries disappear." Investigation revealed Ms. Angela (Angelamel Letada / Ms. Mel) was typing new invoices directly into the **`Commissary` tab** on AP Master. The `Commissary` tab is auto-rebuilt every hour by the script — her entries got wiped on the next refresh.

**Root cause was 3-pronged:**
1. **4 of the 17 tabs had NO protection** (`Summary`, `Commissary`, `Head Office (BEI)`, `Needs Attention`) — these were added AFTER the original Team Guide and never documented. Team typed in them without warning.
2. **Avis had `commenter` role** on AP Master (could see, couldn't edit). She also wasn't on FPM, archived sheets, PCM, etc.
3. **Seed function only reads from archived sheets** (`1ZHe...`, `1jSwZRy...`), never from FPM. Active FPM-originated entries never propagate to AP Master — **1,865 FPM rows worth ₱455.7M are missing.**

**Actions taken (2026-05-12):**
1. ✅ **Strict-locked all 14 auto-rebuilt tabs** (editors=sam@bebang.ph only). Team CANNOT type in them — they get a hard block, not just a warning.
2. ✅ Upgraded Avis from `commenter` → `writer` on AP Master + granted writer on 7 other AP sheets.
3. ✅ Removed `juanna@bebang.ph`, `alyssa@bebang.ph`, `butch@bebang.ph` access (resigned). 7 access entries revoked across AP Master, FPM, Bank Balances, Cashflow Tracker, Compliance.
4. ✅ Updated AP Master Team Guide doc with complete 17-tab map + "WHEN ENTRIES DISAPPEAR" + "DAILY WORKFLOW" sections.
5. ✅ Updated Filing CAPEX Invoice card + Finance + Compliance card (Juanna → past tense, Butch → CFO vacant indefinitely).
6. 🟧 **Seed function patch WRITTEN but NOT DEPLOYED** — `CEO/CashFlow/intercompany_gl/ap_view_hourly_sync_v4_fpm_seed_patch.gs`. Adds FPM as a seed source. Sam must deploy via Apps Script editor.
7. 🟧 **1,865 lost FPM entries cataloged** — `F:\downloads\FPM_Lost_Entries_2026-05-12.xlsx`. Will auto-restore once the seed patch is deployed.

**See `troubleshooting.md` → "Commissary incident" for full forensic detail.**

## Where the team should ACTUALLY type (sheet locking + daily workflow)

### Locked tabs (CANNOT type — auto-rebuilt by script)
All **15** of these are strict-protected (editors=Sam only). **Lock verified 2026-05-14** — every AP Master writer was impersonated and tested; 90/90 lock checks passed:
`All Liabilities`, `Summary`, `Commissary`, `Head Office (BEI)`, `Needs Attention`, `Needs RFP`, `With Finance (No RFP)`, `Check Released`, `In Pipeline`, `VAT Gaps`, `PAID`, `_sync_log`, `_sync_log_v3`, `_dry_run_preview`, **`Payment Plan`** (new 2026-05-14, auto-mirrored from Denise's standalone sheet hourly)

### Unlocked tabs (TYPE HERE)
The 3 data-entry tabs on AP Master:
- **`Suppliers SOA`** — inventory supplier invoices
- **`Head Office`** — head office operating expenses
- **`CAPEX`** — contractor/project invoices (Store dropdown REQUIRED)

### What goes WHERE (sheet → tab → who types)

| Task | Sheet | Tab | Who types |
|---|---|---|---|
| New inventory supplier invoice | BEI AP Master | Suppliers SOA | Ms. Mel (angelamel) |
| New HO expense | BEI AP Master | Head Office | Ms. Mel |
| New CAPEX invoice | BEI AP Master | CAPEX | Ms. Mel |
| Update RFP / payment status | FPM | RFP Summary | Denise / je-ann |
| Tag VAT / EWT | Compliance AppSheet | PO Items / Advance Invoices | Cayla / Luwi |
| Per-store CAPEX budget | PCM | (per-store tab top section) | Angela |
| Partner Reserve / Franchise Fee / BGF | BGF Investments | (own tabs) | Angela |
| Daily bank balance | BEI Bank Balances | Bank Accounts | Denise |
| See cash position | Cashflow Tracker | 4 tabs (read-only) | (everyone reads) |

## Reference files at a glance (table of contents)

- `references/ap-master-structure.md` — 17 tabs, 19-column edit-tab schema, HUMAN_OWNED vs SCRIPT_OWNED columns
- `references/script-v3.md` — v3 Apps Script architecture, doGet entry point, the 3 sync functions, dry-run mode, _sync_conflicts
- `references/sheets-inventory.md` — every sheet ID, name, owner, tab list, role in the ecosystem
- `references/permissions.md` — editor matrix per sheet, who's missing, how to add new team members
- `references/troubleshooting.md` — "data disappearing", access blocked, sync didn't fire, etc.
- `references/history.md` — chronological narrative from 2026-04-14 (Sam asked Claude to find AP automation) through 2026-05-02 (BDO catchup reconciliation)
- `references/source-files.md` — repo paths, doc IDs, Drive URLs, source-of-truth pointers
- `references/team-guides.md` — the 7 training-guide DOCXs (Receiving + AP Master + CAPEX + PCM + Finance/Compliance)


## DD Readiness (S255 — 2026-05-20)

Bridge (`bridge-ph.com`) is BEI's fractional CFO + DD auditor (engaged ~2026-05-14). The 3 Bridge writers `anna.r@`, `flor.a@`, `bea.p@` are AUTHORIZED contractors on Denise PP. They may need expanded read access to other sheets during DD.

### Bridge access matrix (live audit 2026-05-20)

- **BEI AP Master**: no Bridge access
- **FPM**: `anna.r@bridge-ph.com` (reader), `kim.c@bridge-ph.com` (reader), `flor.a@bridge-ph.com` (reader), `accountant.outsource@bridge-ph.com` (reader), `erica.d@bridge-ph.com` (reader)
- **Compliance AppSheet**: no Bridge access
- **PCM**: no Bridge access
- **BGF**: no Bridge access
- **Bank Balances LIVE**: no Bridge access
- **Cashflow Tracker - CEO**: no Bridge access
- **Project: 2-Week Payment Plan (Denise)**: `anna.r@bridge-ph.com` (writer), `flor.a@bridge-ph.com` (writer), `bea.p@bridge-ph.com` (writer)

### DD package recommended exports

When Bridge requests the AP audit package, prepare:
1. AP outstanding by payee + aging (filter AP Master Suppliers SOA + HO + CAPEX + Intercompany on OUTSTANDING > 0)
2. Payment plan (next 2 weeks) — AP Master Payment Plan tab native + filter view
3. RFP processing pipeline — FPM RFP Summary tab
4. Supplier compliance — Compliance AppSheet Suppliers tab
5. Audit trail — `_sync_log_v3` tab on AP Master + git history of `scripts/google_apps/s248_ap_view_hourly_sync_v3*.gs`

See `output/s255/dd_package_checklist.md` for full checklist.
