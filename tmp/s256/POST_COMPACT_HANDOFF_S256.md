# Post-Compact Handoff — S256 AP Master v3.10 + Source-of-Truth Redesign

**Created:** 2026-05-22 PHT
**Author:** Claude Opus 4.7 — handoff to future self after `/compact`
**Session UUID:** `0271331a-41d5-4b35-8699-cba8264fb405`
**JSONL transcript:** `C:\Users\Sam\.claude\projects\F--Dropbox-Projects-BEI-ERP\0271331a-41d5-4b35-8699-cba8264fb405.jsonl` (1.6 MB)

To recover the original session for context: run `/find-conversations-bei-erp` and look for "S255 closeout + S256 plan write" or session ID `0271331a-41d5-4b35-8699-cba8264fb405`.

Predecessor handoffs (for deeper history):
- `F:\Dropbox\Projects\BEI-ERP\tmp\finance_ap_audit\POST_COMPACT_HANDOFF_S255.md` (S255 pre-execution handoff, 2026-05-19)
- `C:\Users\Sam\.claude\projects\F--Dropbox-Projects-BEI-ERP\memory\s255-handoff-2026-05-19.md` (memory pointer)
- Session `517586f9-ff15-4d3d-b71d-d63a8d41ef24.jsonl` (the S255 design + execution session that ran 2026-05-12 → 2026-05-19)

---

## STEP 1 — START HERE AFTER COMPACT

1. **Read this file completely first** — it has every link, ID, path, decision, person, signed answer, and outstanding item.
2. **Load `/finance-ap` skill** via the Skill tool (already mirrored to all 3 skill dirs; verify intact via Phase 0 of S256).
3. **Read** (only as needed):
   - `docs/plans/2026-05-22-sprint-256-ap-source-redesign.md` — THE PLAN to execute
   - `docs/plans/SPRINT_REGISTRY.md` — S256 row at the bottom; Next = S257
   - `F:\Downloads\2026-05-20 - S255 Closeout Questionnaire for Finance and Accounting v2 with Answer_signed.pdf` — Denise's signed authority
   - `tmp/s255_followup/CLOSEOUT_EXECUTION_2026-05-22.md` — what S255 already executed (do NOT re-do these)
   - `tmp/s255_followup/closeout_execution_log.json` — per-op data + row IDs

---

## STEP 2 — STATE MACHINE: where we are RIGHT NOW

### S255 status

✅ **MERGED.** PR #760, merged 2026-05-20T01:15:03Z. Apps Script v3.9 is LIVE on production (versionNumber=16). Cloud Scheduler ENABLED.

### S255 closeout execution (post-merge, 2026-05-22)

✅ **DONE.** Executed direct ops per Denise's signed PDF. Documented in `tmp/s255_followup/CLOSEOUT_EXECUTION_2026-05-22.md`:
- Denise PP ACL: 3 users removed (Bea Garcia intern, Liezel Acero, Maika Talisayon)
- Intercompany migration: 5 of 7 ambiguous rows moved HO → Intercompany (rows 2382, 2574, 2934, 3831, 3929)
- 3M Dragon retag: 6 rows on Suppliers SOA `Denise PP - Masterlist` → `Denise PP - Manual`
- Suzuyo retag: 18 Denise-PP-sourced rows → `Denise PP - Manual`
- Cross-source dedup: 3 rows deleted (rows 317, 1110, 1196 — kept FPM per Denise D1)
- Bridge readers granted on 5 upstream sheets (FPM, Compliance App, Bank Balances LIVE, Cashflow Tracker - CEO, PCM): 17 new + 3 already present = 20 grants live

### S256 status

🟡 **PLAN WRITTEN, NOT EXECUTED.**
- Plan file at `docs/plans/2026-05-22-sprint-256-ap-source-redesign.md` (committed locally on branch `s256-ap-source-redesign`)
- Registry row added in `docs/plans/SPRINT_REGISTRY.md`
- Branch `s256-ap-source-redesign` created from `origin/production` HEAD `9bd905db2`
- Worktree at `F:/Dropbox/Projects/BEI-ERP-s256-ap-source-redesign`
- **Not pushed to origin yet** — push happens during execution at Phase 9.7
- **Not audited yet** — Sam may want to run `/audit-plan-bei-erp` first

### Cloud Scheduler current state

✅ **ENABLED** (cron `0 * * * *` xx:00 PHT, asia-southeast1 region, job `ap-auto-view-hourly-refresh`).

The S255 closeout briefly paused it 2026-05-22 ~02:14 PHT → resumed ~02:18 PHT (~4 min window).

---

## STEP 3 — THE STORY (compressed)

1. **S255 written 2026-05-19** — plan to fix the 11-item backlog (Avis Chat msg from 2026-05-18). Plan version 1.0. canonical_scope: none.
2. **S255 audited 2026-05-19** — 9 CRITICAL + 8 WARNING blockers found.
3. **S255 v1.1 amendments applied 2026-05-20** — Sam directive: "amend plan to resolve everything without changing the specs." All 17 blockers resolved (display-only rename, BILLED ENTITY for PP col 15, tighter intercompany predicate, scheduler pause primitive, dry-run gate, etc.).
4. **S255 executed 2026-05-20** — Sam: "Continue through ALL 10 remaining phases this session. Push all BUT amend when needed with new discoveries for a full working system. Including testing everything and making sure there are zero defects."
   - All 10 phases done (0, 1, 2, 3, 4, 5, 6, 7, 8, 9a, 9b)
   - Production promoted to v3.9 / versionNumber=16
   - Dry-run gate 4/4 PASS, post-deploy verify 5/5 PASS
   - 331 rows migrated to Intercompany, 19 dupes deleted, 16/16 tabs strict-locked (96/96 pairs)
   - PR #760 created → Sam merged
5. **S255 closeout questionnaire generated 2026-05-20** — Sam requested DOCX questionnaire for Finance team. Generated with BEI letterhead + SDT click-to-toggle checkboxes (v2 fix after v1 used legacy FORMCHECKBOX requiring double-click).
6. **Denise signed 2026-05-21 08:40:58 UTC** — via Documenso (Sig ID `CMPF8QBLQ03LTMT1WTAUO7ISY`). James did not countersign (Sam directive 2026-05-22: ignore that).
7. **S255 closeout direct ops executed 2026-05-22** — per Denise's signed answers (see Section 4 below). Logged in `tmp/s255_followup/CLOSEOUT_EXECUTION_2026-05-22.md`.
8. **S256 plan written 2026-05-22** — covers remaining items that need code (v3.10 patches) or research (source-of-truth redesign + Bridge PII audit). 10 phases / 72 work units.

---

## STEP 4 — DENISE'S SIGNED ANSWERS (verbatim — most important section)

**Signatory:** Denise Marielle P. Almario, Finance Supervisor
**Signed at:** 2026-05-21 08:40:58 UTC via Documenso
**Signature ID:** `CMPF8QBLQ03LTMT1WTAUO7ISY`
**IP:** 124.105.20.131 (Windows/Chrome 148)
**Reason:** "I am the owner of this document"

### Section A — People on the 2-Week Payment Plan sheet

| Q | Question | Denise's answer | Status |
|---|---|---|---|
| A1.1 | Is Joevic part of Finance/Accounting? | ☒ **YES** | Confirmed |
| A1.2 | What does Joevic handle? | "Supplier Payments" | Confirmed |
| A1.3 | Should Joevic keep editor access? | ☒ **Yes, keep as editor** | No action |
| A2.1 | Is Bea Garcia an active intern? | ☒ **No / she's left** | Confirmed |
| A2.2 | Recommended access level for Bea? | ☒ **Remove access (no longer needed)** | ✅ EXECUTED 2026-05-22 |
| A3 drew@ Andrew Manansala | | ☒ **Keep** | No action |
| A3 liezel@ Liezel Acero | | ☒ **Remove** — "They just assisted in the initial completion of the file." | ✅ EXECUTED 2026-05-22 |
| A3 maika@ Maika Talisayon | | ☒ **Remove** — "They just assisted in the initial completion of the file." | ✅ EXECUTED 2026-05-22 |
| A3 marco@ Marco Limosnero | | ☒ **Keep** | No action |
| A3 julius@ Julius Tin-ga | | ☒ **Keep** (view-only retained) | No action |

### Section B — 7 ambiguous Intercompany candidates

| # | Sheet row | Particulars | Denise's pick | Status |
|---|---|---|---|---|
| 1 | 2382 | Transfer to BPI BEI to facilitate check clearing adjustment | ☒ **Yes — move** | ✅ MOVED to Intercompany 2026-05-22 |
| 2 | 2574 | Transfer of Fund from UB Snack House to BPI for processing (typo "Trasnfer") | ☒ **Yes — move** | ✅ MOVED to Intercompany 2026-05-22 |
| 3 | 2925 | Rental for the month of March 2026 — Soltea Commercial Corp | ☒ **No — keep** | Kept on HO ✓ |
| 4 | 2934 | To Fund the AUB account for the PDC issued rental payment | ☒ **Yes — move** | ✅ MOVED to Intercompany 2026-05-22 |
| 5 | 3195 | OJT Allowance for the month of March 1-15, 2026 Cut Off | ☒ **No — keep** | Kept on HO ✓ |
| 6 | 3831 | RFP 1801 Fund Transfer From UB - Snack House to BEI | ☒ **Yes — move** | ✅ MOVED to Intercompany 2026-05-22 |
| 7 | 3929 | RFP 1910 To Fund AUB Account for the PCD Shaw Rental Monthly | ☒ **Yes — move** | ✅ MOVED to Intercompany 2026-05-22 |

### 🟥 Section B FREE-TEXT ADDENDUM (verbatim — critical for S256)

> "Any other notes about how you classify inter-company transfers? If the transfers are between companies that are Bebang branded and other affiliated entities that are non-Bebang branded namely:
> - B CUBED VENTURES CORP
> - BB ESTANCIA FOOD CORP
> - BEIFRANCHISE FOOD OPC
> - DAY ONES FOOD AND DRINK ESTABLISHMENTS CORP
> - DMD HOLDINGS INC
> - HALO-HALO ALABANG TOWN FOOD CORP
> - HALO-HALO TERMINAL FOOD CORP
> - HFFM SOLENAD FOOD SERVICES INC
> - JL TRADE OPC PERPETUAL FOOD CORP
> - RED TALDAWA FOODS OPC
> - RESTO TECH INC
> - SWEET HARMONY FOOD CORP
> - TAJ FOOD CORP
> - TUNGSTEN CAPITAL HOLDINGS OPC"

→ **These 14 entities are ALL intercompany partners.** Current v3.9 predicate only matches `^Bebang\s+(Enterprise|Kitchen|Shaw)\s+Inc\.?` — S256 Phase 2 broadens this to include all 14.

### Section C — Bypass-procurement suppliers

| Q | Denise's answer | Status |
|---|---|---|
| C1 — Tag 3M Dragon as "Denise PP - Manual"? | ☒ **YES** — tag them so they're easy to filter | ✅ EXECUTED 2026-05-22 (6 rows retagged) |
| C2 — Other bypass suppliers | "3MD Logistics, Pinnacle, Royal Cold Storage, Fourkoolitz, Suzuyo" | ✅ Suzuyo executed (18 Denise PP rows); Pinnacle/RCS/Fourkoolitz had 0 Denise PP rows on AP Master |

→ **S256 Phase 5** auto-tags these 5 patterns at SEED time so future entries get `Denise PP - Manual` automatically.

### Section D — Duplicates

| Q | Denise's answer |
|---|---|
| D1 — When same invoice appears archived SOA + FPM, which to keep? | ☒ **Keep the FPM version (it has the RFP / payment status)** ✅ APPLIED to 3 cross-source dupes 2026-05-22 |

### 🟥 Section D2 SOURCE-OF-TRUTH DIRECTIVE (verbatim — critical for S256)

> "D2 Notes: Revise the source data of Head Office tab, Suppliers SOA tab and CAPEX Tab. For the suppliers soa get the source from Procurement App and the beginning balances will be coming from 'Denise PP' and the current transactions will be coming from the Procurement App. For the Head Office, get the source from the RFP App and the beginning balances will be coming from '05 - AP Opening Balance Head Office'. For the CAPEX, beginning is the CAPEX File and the current transactions will be coming from RFP App."

→ **S256 Phase 4a/4b/4c** implements this redesign. Phase 1 INVESTIGATION GATE: if Procurement App or `05 - AP Opening Balance HO` file can't be located, sub-phases defer to S257.

### Section E — Bridge access expansion

All 5 sheets: ☒ **Yes — grant view**

| Sheet | Status |
|---|---|
| Finance Payment Monitoring (FPM) | ✅ GRANTED 2026-05-22 (bea.p@ added; 3 others already had it from prior setup) |
| Compliance App | ✅ ALL 4 BRIDGE USERS GRANTED 2026-05-22 |
| Bank Balances LIVE | ✅ ALL 4 BRIDGE USERS GRANTED 2026-05-22 |
| Cashflow Tracker — CEO | ✅ ALL 4 BRIDGE USERS GRANTED 2026-05-22 |
| Petty Cash Monitoring (PCM) | ✅ ALL 4 BRIDGE USERS GRANTED 2026-05-22 |

### 🟥 Section E2 FORBIDDEN (critical for S256 Phase 6)

> "E2 Sheets / tabs / cells [Bridge should NEVER see]: **Personal Info, Salary details**"

→ **S256 Phase 6** audits all 5 newly-granted sheets for hidden salary/PII tabs; if found, applies `protectedRange` (warningOnly=false, editors=owner-only) to hide those specific tabs from Bridge.

### "Any other feedback?"

> "Suggestions, issues, or things we missed: **None**"

---

## STEP 5 — S256 PLAN SUMMARY (the 6 items)

**Plan file:** `docs/plans/2026-05-22-sprint-256-ap-source-redesign.md`
**Branch:** `s256-ap-source-redesign` (committed locally; not pushed)
**Worktree:** `F:/Dropbox/Projects/BEI-ERP-s256-ap-source-redesign`
**Phases:** 10 (0, 1, 2, 3, 4a, 4b, 4c, 5, 6, 7, 8, 9)
**Units:** 72 (under 80-unit ceiling)
**canonical_scope:** none (Google Apps Script + Sheets only)

| # | Item | Phase | Source of authority |
|---|---|---|---|
| 1 | **Broaden intercompany predicate to 14 non-Bebang affiliates** | Phase 2 (v3.10 code) + Phase 3 (one-time migration) | Denise Section B free-text |
| 2 | **Auto-tag 3PL bypass suppliers at seed time** (3MD/Pinnacle/RCS/Fourkoolitz/Suzuyo) | Phase 5 | Denise C2 |
| 3 | **FPM-SOA-aware dedup race fix** (stops XYZCO row re-add) | Phase 2 | Closeout op5 observation |
| 4 | **Source-of-truth redesign** (Procurement App SOA + 05-AP-Opening HO + Denise PP→opening-only) | Phase 4a/4b/4c (CONDITIONAL on Phase 1 gate) | Denise D2 |
| 5 | **Bridge PII audit on 5 sheets** + restrict confirmed-PII tabs | Phase 6 | Denise E2 |
| 6 | **/finance-ap team-training refresh** (S255+S256 entries, 96/96 locks, Joevic role, Bridge access) | Phase 7 | Carryover from S255 |

### Phase 1 INVESTIGATION GATE

S256's biggest risk is the source-of-truth redesign (item 4). Denise referenced 3 new upstreams:
- "Procurement App" — likely a sheet that exists; need to find ID
- "05 - AP Opening Balance Head Office" — opening-balance file; need to find or create
- "CAPEX File" — may be the existing CAPEX tab or a separate archive

Phase 1 investigates ALL 3. If any are missing/incomplete, sub-phases 4a/4b/4c defer to S257. The other v3.10 patches (items 1, 2, 3, 5, 6) ship regardless.

---

## STEP 6 — KEY CONTEXT (preserved across compaction)

### People — CURRENT STATE

| Person | Email | Role | Status |
|---|---|---|---|
| **Sam Karazi** | sam@bebang.ph | CEO, sole approver | ACTIVE — owns everything; ignore James-didn't-sign per Sam directive 2026-05-22 |
| **Denise Almario** | denise@bebang.ph | Finance **Supervisor** (her signed PDF says "Finance Supervisor" — predecessor handoff said "Finance Lead"; trust the signature) | ACTIVE — owns FPM + Denise PP; signed S255 closeout questionnaire 2026-05-21 |
| **James Tamaca** | james.tamaca@bebang.ph | F&A Manager (started ~2026-05-18) | ACTIVE — did NOT countersign questionnaire (OK per Sam) |
| **Ms. Mel (Angelamel Letada)** | angelamel@bebang.ph | AP data entry / Project Cost | ACTIVE |
| **Avis Lyndelle Principe** | avislyndelle@bebang.ph | Compliance / cross-functional reader | ACTIVE |
| **Cayla Cabagnot** | cayla@bebang.ph | Compliance — VAT/EWT tagging | ACTIVE |
| **Luwi Azusano** | luwi@bebang.ph | Compliance — VAT/EWT tagging | ACTIVE |
| **Ian Dionisio** | ian@bebang.ph | SCM head | ACTIVE — logs Goods Receipts |
| **Bethina Oabel** | bethina@bebang.ph | Head Office monitoring | ACTIVE |
| **Izza May Salva** | izza@bebang.ph | Writer on AP Master | ACTIVE |
| **Je-Ann Torato** | je-ann@bebang.ph | FPM RFP processing | ACTIVE |
| **Joevic Almajar** | joevic@bebang.ph | Supplier Payments (CONFIRMED by Denise A1) | ACTIVE — kept as editor on Denise PP |
| **Marco Limosnero** | marco@bebang.ph | Kept as editor on Denise PP per Denise A3 | ACTIVE |
| **Andrew Manansala (drew@)** | drew@bebang.ph | Kept as editor per Denise A3 | ACTIVE |
| **Julius Tin-ga** | julius@bebang.ph | Kept as view-only per Denise A3 | ACTIVE (reader) |
| ~~Bea Garcia (intern)~~ | bea.garcia.intern@bebang.ph | REMOVED 2026-05-22 (Denise A2: she's left) | REMOVED |
| ~~Liezel Acero~~ | liezel@bebang.ph | REMOVED 2026-05-22 (Denise A3: initial completion only) | REMOVED |
| ~~Maika Talisayon~~ | maika@bebang.ph | REMOVED 2026-05-22 (Denise A3: initial completion only) | REMOVED |
| ~~Roberose Pulido~~ | roberose@bebang.ph | DOWNGRADED to commenter in S255 P8 | view-only |
| **Bridge contractors (4)** | anna.r@bridge-ph.com, flor.a@bridge-ph.com, bea.p@bridge-ph.com, accountant.outsource@bridge-ph.com | Fractional CFO + DD auditors | ✅ READER on: AP Master + Denise PP + FPM + Compliance + Bank Balances + Cashflow + PCM |
| Resigned (DO NOT include) | juanna@, alyssa@, butch@ | Past finance team | Removed since 2026-05-12 |

### Sheets ecosystem (8 total)

| Name | ID | Owner |
|---|---|---|
| **BEI AP Master** | `1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c` | Sam |
| **FPM (Finance Payment Monitoring)** | `1t4wJLiAfIMJm6fe-x6h4eZn_S_Lx1AGN5ORd5Ywhcyw` | Denise |
| **Compliance AppSheet** | `1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q` | Sam |
| **PCM** | `1_5BSZeNL9A_o5QO6WD4L42gGjYY6-yCDfgTp01y0fpo` | Sam |
| **BGF** | `1dfIyAeGH_5ga_mjA1o-WWN9xM6VO3v7XKKoU1Jtq1eI` | Mae (ACL not always readable to Sam) |
| **Bank Balances LIVE** | `19kSR8HQdveZVleMZORGQetHXVCxaeDy6EMlKfe2G77w` | Sam |
| **Cashflow Tracker — CEO** | `1W2GERTwbODqfbHM70XpJJEtFwL-jIPbb2zzwC0Rcfeg` | Sam |
| **Project: 2-Week Payment Plan (Denise's)** | `13cyYaPLmjL0TPaeqyYd2esjJNYj-5qJCDS8OZLdhURU` | Denise |

### Apps Script live state

| Item | Value |
|---|---|
| Project ID | `1pE8wt_z8NA9q__PNbUilJ72UE0_EI3DmurJekkw6mbgtHr8hosnKsNRF` |
| Production deployment ID | `AKfycbw-AuqJq6OyMV6DGarGWEruDoez04OETlWFQoeppNjvzoeSOJOomPOZNsVPE9iuV6ZC_Q` |
| Web app URL | `https://script.google.com/macros/s/AKfycbw-AuqJq6OyMV6DGarGWEruDoez04OETlWFQoeppNjvzoeSOJOomPOZNsVPE9iuV6ZC_Q/exec` |
| Web app token | `bei-ap-sync-2026-04` |
| **Current version** | **16 (v3.9)** — promoted 2026-05-20 |
| Cloud Scheduler job | `ap-auto-view-hourly-refresh` (cron `0 * * * *`, asia-southeast1, **ENABLED**) |
| Source on origin/production | `scripts/google_apps/s255_ap_view_hourly_sync_v39.gs` (~95K bytes) |
| v3.8 backup (for rollback) | `output/s255/script_source_backup_v38.gs` (committed to origin/production) |
| Next deploy target | v3.10 / versionNumber=17 via S256 Phase 8 |

### AP Master tab structure (19 tabs post-S255)

**3 entry tabs (writable by 6 users):**
- `Suppliers SOA` — 19 cols (resized from 22 in S255 P1)
- `Head Office` — 19 cols
- `CAPEX` — 20 cols

**16 strict-locked tabs (sam@ only — 96/96 lock checks PASS per S255 P9a):**
- `All Liabilities`, `Summary`, `Commissary`, `Head Office (BEI)`, `Needs Attention`
- `Needs RFP`, `With Finance (No RFP)`, `Check Released`, `In Pipeline`, `VAT Gaps`
- `PAID`, `_sync_log`, `_sync_log_v3`, `_dry_run_preview`
- `Payment Plan` (30 cols; mirror runs until Sam flips `payment_plan_mirror_disabled` flag)
- **`Intercompany` (NEW from S255 P2)** — 336 rows after S255 closeout migration (was 331)

### Header positions

- Suppliers SOA: header row 17
- Head Office: header row 17
- CAPEX: header row 19 (different!)
- Payment Plan: header row 3
- Intercompany: header row 17
- All other locked tabs: row 17

### Bridge engagement context

- Bridge (`bridge-ph.com`) = BEI's fractional CFO + DD auditor (engaged ~2026-05-14)
- 4 user emails: `anna.r@`, `flor.a@`, `bea.p@`, `accountant.outsource@`
- After S256 closeout, Bridge will have:
  - **EDITOR** on: Denise PP (3 users originally; `accountant.outsource@` is also writer per closeout audit)
  - **READER** on: AP Master + FPM + Compliance + Bank Balances + Cashflow + PCM
  - Denise E2: never expose Personal Info / Salary — S256 Phase 6 audits + restricts if needed

---

## STEP 7 — RUNNABLE COMMANDS (copy-paste ready)

### Re-establish worktree (if needed)

```bash
cd F:/Dropbox/Projects/BEI-ERP && git fetch origin --prune
# Worktree should already exist:
git worktree list | grep s256
# If missing, recreate:
# git worktree add F:/Dropbox/Projects/BEI-ERP-s256-ap-source-redesign s256-ap-source-redesign
```

### Verify S256 commit exists locally

```bash
cd F:/Dropbox/Projects/BEI-ERP-s256-ap-source-redesign
git log --oneline -3
# Should show: 02666326b plan(s256): write AP Master v3.10 + source-of-truth redesign plan
```

### Audit the plan

```bash
# From any directory; the audit skill writes to output/plan-audit/
/audit-plan-bei-erp docs/plans/2026-05-22-sprint-256-ap-source-redesign.md
```

### Execute the plan (when Sam says go)

```bash
/execute-plan-bei-erp docs/plans/2026-05-22-sprint-256-ap-source-redesign.md
```

### Sanity check Apps Script production state

```bash
cd F:/Dropbox/Projects/BEI-ERP && python -u -c "
from google.oauth2 import service_account
from googleapiclient.discovery import build
creds = service_account.Credentials.from_service_account_file('credentials/task-manager-service.json', scopes=['https://www.googleapis.com/auth/script.projects']).with_subject('sam@bebang.ph')
api = build('script', 'v1', credentials=creds, cache_discovery=False)
content = api.projects().getContent(scriptId='1pE8wt_z8NA9q__PNbUilJ72UE0_EI3DmurJekkw6mbgtHr8hosnKsNRF').execute()
print('Current source size:', len(next(f for f in content['files'] if f['name']=='Code')['source']))
"
```

### Verify Cloud Scheduler

```bash
gcloud scheduler jobs describe ap-auto-view-hourly-refresh \
  --project=quiet-walker-475722-s2 --location=asia-southeast1 --format="value(state)"
# Expected: ENABLED
```

### Find Procurement App + `05 - AP Opening Balance HO` (Phase 1 investigation prep)

```bash
cd F:/Dropbox/Projects/BEI-ERP && python -c "
from google.oauth2 import service_account
from googleapiclient.discovery import build
creds = service_account.Credentials.from_service_account_file('credentials/task-manager-service.json', scopes=['https://www.googleapis.com/auth/drive']).with_subject('sam@bebang.ph')
drive = build('drive', 'v3', credentials=creds, cache_discovery=False)
for q in ['Procurement App', 'Procurement AppSheet', '05 - AP Opening Balance', 'AP Opening Balance Head Office', 'Compliance AppSheet Suppliers']:
    res = drive.files().list(q=f\"name contains '{q}' and trashed=false\", fields='files(id,name,owners,modifiedTime)', includeItemsFromAllDrives=True, supportsAllDrives=True).execute()
    print(f'=== {q} ===')
    for f in res.get('files', [])[:5]:
        print(f'  {f[\"id\"]}  {f[\"name\"]}  ({f.get(\"owners\",[{}])[0].get(\"emailAddress\",\"?\")})')
"
```

---

## STEP 8 — WHAT TO DO IMMEDIATELY AFTER COMPACT

The user (Sam) will likely give one of these directions. Match the right action:

| User says | Action |
|---|---|
| "go audit S256" / "audit the plan" | `/audit-plan-bei-erp docs/plans/2026-05-22-sprint-256-ap-source-redesign.md` |
| "go execute S256" / "execute the plan" | `/execute-plan-bei-erp docs/plans/2026-05-22-sprint-256-ap-source-redesign.md` |
| "verify state" / "check state" | Run sanity-check commands above (Apps Script state, scheduler state, Denise PP ACL, Bridge ACL on 5 sheets) |
| "what was decided" / "what's pending" | Re-summarise from this handoff + DEFECTS.md analogue |
| "amend the plan" | Read the plan, ask which section, edit |
| Other | Answer using this handoff |

### Critical reminders preserved across compaction

- **Bridge (`bridge-ph.com`) is AUTHORIZED** — DO NOT REVOKE any access. They are reader on AP Master + 5 upstream sheets after S255 closeout.
- **James Tamaca's countersign is NOT required** — Sam directive 2026-05-22.
- **Denise IS the Finance Supervisor** (her signed PDF says so). Predecessor handoff said "Finance Lead" — use what she wrote.
- **Joevic Almajar handles "Supplier Payments"** (confirmed by Denise A1). Add to /finance-ap roster in S256 Phase 7.
- **PR-Handoff rule:** Agents create PRs and STOP. Sam merges. Never auto-merge.
- **Cloud Scheduler pause primitive:** S256 Phase 0.5 pauses; Phase 8.5 resumes. Use this pattern from S255.
- **S256 worktree is committed but not pushed** — push happens in Phase 9.7 during execution.
- **Phase 1 INVESTIGATION GATE controls scope** — if Procurement App or `05 - AP Opening Balance HO` missing, defer 4a/4b/4c to S257. The v3.10 patches (intercompany broadening + auto-tag + dedup fix) ship regardless.

---

## STEP 9 — IF SOMETHING'S BROKEN

| Symptom | Diagnose | Fix |
|---|---|---|
| `s256-ap-source-redesign` branch not on local repo | `git branch -a \| grep s256` | Worktree should exist; if cleaned up, `git worktree add F:/Dropbox/Projects/BEI-ERP-s256-ap-source-redesign s256-ap-source-redesign` |
| Apps Script no longer triggers | `gcloud scheduler jobs describe ap-auto-view-hourly-refresh ...` | Resume scheduler if paused |
| Denise PP sheet inaccessible | Re-grant Sam access | (very unlikely; Denise owns) |
| Bridge readers can't see a sheet | Check ACL via Drive API impersonating owner | Re-grant per S255 closeout pattern |
| `output/s255/script_source_backup_v38.gs` (v3.8 rollback) missing | Was committed in S255 P0; should be on origin/production | Re-pull from `git show origin/production:output/s255/script_source_backup_v38.gs` |
| v3.9 production source needed | `scripts/google_apps/s255_ap_view_hourly_sync_v39.gs` on origin/production | Read with `git show` from any worktree |

---

## STEP 10 — KEY FILE INVENTORY (full path reference)

### S256 (this sprint)

- `F:/Dropbox/Projects/BEI-ERP-s256-ap-source-redesign/docs/plans/2026-05-22-sprint-256-ap-source-redesign.md` — **THE PLAN**
- `F:/Dropbox/Projects/BEI-ERP-s256-ap-source-redesign/docs/plans/SPRINT_REGISTRY.md` — S256 row added
- `F:/Dropbox/Projects/BEI-ERP-s256-ap-source-redesign/tmp/s256/POST_COMPACT_HANDOFF_S256.md` — this file
- Commit on `s256-ap-source-redesign`: `02666326b plan(s256): write AP Master v3.10 + source-of-truth redesign plan`

### S255 closeout evidence (already-executed work)

- `F:/Dropbox/Projects/BEI-ERP/tmp/s255_followup/CLOSEOUT_EXECUTION_2026-05-22.md` — full write-up
- `F:/Dropbox/Projects/BEI-ERP/tmp/s255_followup/closeout_execution_log.json` — per-op JSON log
- `F:/Dropbox/Projects/BEI-ERP/tmp/s255_followup/fact_check_result.json` — system state pre-execution
- `F:/Dropbox/Projects/BEI-ERP/tmp/s255_followup/post_closeout_sync.json` — live sync verification after ops
- `F:/Dropbox/Projects/BEI-ERP/tmp/s255_followup/execute_closeout_ops.py` — the script we ran
- `F:/Dropbox/Projects/BEI-ERP/tmp/s255_followup/fact_check_state.py` — fact-check script
- `F:/Dropbox/Projects/BEI-ERP/tmp/s255_followup/intercompany_ambiguous.json` — copied from S255 evidence
- `F:/Dropbox/Projects/BEI-ERP/tmp/s255_followup/dedup_cleanup_log.json` — copied from S255 evidence
- `F:/Dropbox/Projects/BEI-ERP/tmp/s255_followup/denise_pp_baseline.json` — copied from S255 evidence

### S255 production evidence (on origin/production via PR #760)

- `output/s255/SUMMARY.md`
- `output/s255/DEFECTS.md`
- `output/s255/script_source_backup_v38.gs` (rollback target)
- `output/s255/post_deploy_verify.json` (5/5 PASS)
- `output/s255/payment_plan_cutover_runbook.md`
- `scripts/google_apps/s255_ap_view_hourly_sync_v39.gs` (current production source)
- `docs/plans/2026-05-19-sprint-255-ap-system-hardening-team-requests.md` (S255 plan, status COMPLETED)

### Denise's signed PDF + questionnaire

- `F:\Downloads\2026-05-20 - S255 Closeout Questionnaire for Finance and Accounting v2 with Answer_signed.pdf` — Denise's signed responses (1 MB PDF)
- `F:\Dropbox\Projects\BEI-ERP\data\_CONSOLIDATED\01_FINANCE\questionnaires\2026-05-20 - S255 Closeout Questionnaire for Finance and Accounting v2.docx` — the questionnaire I generated
- Google Doc copy: https://docs.google.com/document/d/1RJi17jjwQGPB1VIJ8Nm8CCD5SLJiYZW19ZQM_0olEYc/edit

### Skill files

- `.claude/skills/finance-ap/SKILL.md` + `references/` (Bridge section + permissions log)
- Mirrors at `.agent/skills/finance-ap/` and `.agents/skills/finance-ap/`
- Auto-sync script: `scripts/sync_claude_skills_to_codex.ps1 -SkillName "finance-ap"`

### S255 predecessor handoffs (historical)

- `F:\Dropbox\Projects\BEI-ERP\tmp\finance_ap_audit\POST_COMPACT_HANDOFF_S255.md` — 2026-05-19 handoff (S255 pre-execution)
- `C:\Users\Sam\.claude\projects\F--Dropbox-Projects-BEI-ERP\memory\s255-handoff-2026-05-19.md` — memory pointer

---

## STEP 11 — THE 6-ITEM CHECKLIST FOR S256 EXECUTION

When executing S256, check off these 6 items in `output/s256/SUMMARY.md`:

- [ ] **1. Intercompany broadened to 14 affiliates** (Phase 2 v3.10 patch + Phase 3 one-time migration; affiliate-count migrated logged in `intercompany_affiliate_migration_log.json`)
- [ ] **2. Auto-tag bypass suppliers at seed time** (Phase 5; `BYPASS_3PL_PATTERNS` const in v3.10; backfill in `auto_tag_bypass_log.json`)
- [ ] **3. FPM-SOA-aware dedup fix** (Phase 2; `skipped_existing_fpm_soa` counter + `'FPM-SOA'` check in seedFromDenisePaymentPlan_)
- [ ] **4. Source-of-truth redesign** (Phase 4a/4b/4c — CONDITIONAL on Phase 1 gate; if deferred, DEFECTS.md captures it)
- [ ] **5. Bridge PII audit** (Phase 6; `bridge_pii_audit.json`; restrictions applied if confirmed PII found)
- [ ] **6. /finance-ap team-training refresh** (Phase 7; 3 mirrors sha256 identical; S255 deployed entry; 96/96 locks; Joevic + Bridge expansion noted)

---

## PROMPT TO SEND TO YOURSELF AFTER COMPACT

> Continue the BEI AP work. Read `F:\Dropbox\Projects\BEI-ERP-s256-ap-source-redesign\tmp\s256\POST_COMPACT_HANDOFF_S256.md` first — it has everything (session UUID, JSONL path, Denise's signed answers verbatim, file paths, people, sheets, Apps Script state, S256 plan summary).
>
> Then proceed depending on what I tell you:
> - "go audit S256" → `/audit-plan-bei-erp docs/plans/2026-05-22-sprint-256-ap-source-redesign.md`
> - "go execute S256" → `/execute-plan-bei-erp docs/plans/2026-05-22-sprint-256-ap-source-redesign.md`
> - "verify state" → run the sanity checks in STEP 7
> - "amend the plan" → edit the plan file at `F:/Dropbox/Projects/BEI-ERP-s256-ap-source-redesign/docs/plans/2026-05-22-sprint-256-ap-source-redesign.md`
> - Other questions → answer using this handoff
>
> Critical reminders:
> - **Bridge (`bridge-ph.com`) is AUTHORIZED** — DO NOT REVOKE anything. They are reader on AP Master + 5 upstream sheets.
> - **James's countersign is NOT required** — Sam directive 2026-05-22.
> - **Denise is Finance Supervisor** (her signed title) — not "Finance Lead".
> - **Joevic Almajar handles Supplier Payments** — confirmed by Denise A1.
> - **PR-Handoff rule:** Agents create PRs and STOP. Sam merges.
> - **S256 worktree is committed but NOT pushed** — push at Phase 9.7.
> - **Phase 1 INVESTIGATION GATE controls scope** — if Procurement App or `05 - AP Opening Balance HO` missing, defer 4a/4b/4c to S257. The v3.10 patches still ship.
> - **Cloud Scheduler is currently ENABLED** — pause at Phase 0.5 of S256 execution, resume at Phase 8.5.
> - **S255 PR #760 is MERGED** (2026-05-20). v3.9 is LIVE (versionNumber=16).
> - **JSONL session this handoff came from:** `C:\Users\Sam\.claude\projects\F--Dropbox-Projects-BEI-ERP\0271331a-41d5-4b35-8699-cba8264fb405.jsonl` — use `/find-conversations-bei-erp` to recover deeper context if needed.

---

END OF HANDOFF FILE.
