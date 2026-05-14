---
sprint_id: S248
title: Sync Denise's 2-Week Payment Plan into AP Master
status: PLANNED
created_date: 2026-05-13
completed_date: null
canonical_scope: none
canonical_scope_rationale: |
  Google Apps Script patch + Google Sheets cell writes only. No Frappe
  `tabCompany`, `tabWarehouse`, `tabCustomer`, or `tabSupplier` mutations.
  Supplier names in AP Master entry tabs are PAYEE strings on the Google
  Sheet, not Frappe master records. No `hrms/api/*` files touched.

branch_name: s248-denise-sheet-sync
worktree: F:/Dropbox/Projects/BEI-ERP-denise-sheet-sync
repos_touched:
  - hrms (only for the Apps Script source file at `CEO/CashFlow/intercompany_gl/ap_view_hourly_sync_v4_fpm_seed_patch.gs` + this plan + `SPRINT_REGISTRY.md`)
# No bei-tasks. No Frappe migrations. No L3 scenarios.

depends_on:
  - S232/AP Master v3.6 live deployment (Apps Script project `1pE8wt_z8NA9q__PNbUilJ72UE0_EI3DmurJekkw6mbgtHr8hosnKsNRF`, deployment `AKfycbw-AuqJq6OyMV6DGarGWEruDoez04OETlWFQoeppNjvzoeSOJOomPOZNsVPE9iuV6ZC_Q`, web app token `bei-ap-sync-2026-04`). The FPM seed pattern this sprint clones was deployed 2026-05-13 08:12 PHT.

# AMENDMENT 2026-05-14 (Phase 0 evidence-mismatch normalization):
# Denise restructured her sheet 2026-05-13 10:16 PHT — split single `Payment Plan` tab
# into 4 working tabs to keep disputed AP separate from urgent AP per CEO directive:
#   - Suppliers w/o FD & Middleby  (594 data rows, ₱53.9M out)   → urgent AP
#   - Middleby                     (7 data rows, ₱4.85M out)     → disputed, eventually payable
#   - Forward Dynamics             (61 data rows, ₱978K out)     → disputed, eventually payable
#   - Masterlist                   (662 data rows, ₱59.8M out)   → consolidated view (= union of above)
# Same 25-col schema across all 4 tabs. Total outstanding moved ₱53.8M → ₱59.8M.
# Plan tasks 1.2 / 1.9 / Phase 2 spotcheck normalized inline below.

evidence_committed:
  - output/s248/SUMMARY.md
  - output/s248/DEFECTS.md
  - output/s248/v37_deployment.json                       # Phase 3 deploy proof
  - output/s248/first_live_sync.json                      # Phase 3 first hourly result
  - output/s248/dedup_verification.json                   # Phase 4 24h dedup proof
  - output/s248/migration_plan.md                         # Phase 5 migration design
  - output/s248/migration_executed.json                   # Phase 6 migration completion
  - output/s248/closeout_state.json                       # Phase 7 final state

evidence_transient:
  - tmp/s248/script_source_backup_v36.gs                  # Phase 0 pre-touch backup
  - tmp/s248/dry_run_*.json                               # Phase 2 dry-run iterations
  - tmp/s248/probe_*.json                                 # mid-run sanity probes
  - tmp/s248/denise_sheet_snapshot_*.csv                  # daily snapshots during monitoring
  - tmp/s248/traceback_*.txt                              # any error captures

execution_summary: null  # filled in at closeout
---

# Sprint S248 — Sync Denise's 2-Week Payment Plan into AP Master

## TL;DR for cold-start agents

Denise (Finance lead) created a parallel tracking sheet on 2026-05-12 called `Project: 2-Week Payment Plan` (sheet ID `13cyYaPLmjL0TPaeqyYd2esjJNYj-5qJCDS8OZLdhURU`). Her sheet has 604 rows totalling ₱53.8M outstanding supplier AP. Today's audit (2026-05-13, session 517586f9) proved that only ₱0 of her ₱53.8M is fully reconciled across AP Master + FPM + Compliance AppSheet — most of it is invisible to the AP Master infrastructure.

CEO directive 2026-05-13 PHT: **"I do not want her to work on a 3rd parallel sheet"** AND **"she can transfer back to AP Master as soon as the 2-week project is over and all data is synced automatically with no manual work."**

This sprint:
- **Phase 1-4 (TODAY):** Adds `seedFromDenisePaymentPlan_()` to the live Apps Script. Hourly Cloud Scheduler pulls her rows into AP Master Suppliers SOA / Head Office automatically. Her workflow is unchanged; her sheet becomes a *data source* for AP Master instead of a parallel silo.
- **Phase 5-6 (~2026-05-27, 2 weeks later):** Adds a 4th entry tab `Payment Plan` to AP Master with her column schema (Address, TIN, VAT/Nonvat, Terms, Description, Due Date, Paid Amount, separated aging columns). Bulk-migrates her 604 rows. Retires her standalone sheet to read-only archive. Denise works 100% inside AP Master going forward.

After Phase 6, **zero manual work**: hourly cron continues to sync FPM status → AP Master and tax fields → AP Master. The standalone Denise sheet stops being touched.

## Context Sources (Ground-Truth Lock)

### Evidence sources

| Source | What it proves | File path / ID |
|---|---|---|
| Denise's sheet | The 604 rows that need to flow into AP Master | Drive ID `13cyYaPLmjL0TPaeqyYd2esjJNYj-5qJCDS8OZLdhURU`, downloaded to `tmp/finance_ap_audit/denise_sheet_2026-05-12/payment_plan.csv` (129 KB) and `.json` (360 KB) |
| AP Master | Target sheet for the seed | Drive ID `1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c`; entry tabs `Suppliers SOA` (990 rows, header row 17, data row 18+) / `Head Office` (4,373 rows, header row 17) / `CAPEX` (172 rows, header row 19, has Store col) |
| Apps Script | The script we patch | Project ID `1pE8wt_z8NA9q__PNbUilJ72UE0_EI3DmurJekkw6mbgtHr8hosnKsNRF` (container-bound to AP Master). Repo source: `CEO/CashFlow/intercompany_gl/ap_view_hourly_sync_v4_fpm_seed_patch.gs`. Live deployment ID: `AKfycbw-AuqJq6OyMV6DGarGWEruDoez04OETlWFQoeppNjvzoeSOJOomPOZNsVPE9iuV6ZC_Q`. Token: `bei-ap-sync-2026-04`. Latest version: v13 (WebApp v3.6) deployed 2026-05-13. |
| FPM | Existing seed pattern to clone | Drive ID `1t4wJLiAfIMJm6fe-x6h4eZn_S_Lx1AGN5ORd5Ywhcyw`. Existing function `seedNewInvoicesFromFPM_` in Apps Script reads from this; we clone the pattern. |
| Compliance AppSheet | Reference for VAT/EWT — already wired | Drive ID `1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q`. No new integration with this sprint. |
| 4-way match | Proves the scope and direction | `tmp/finance_ap_audit/audit_2026-05-13/four_way_match.json` (525 KB). 604 rows analyzed: ALL_3=4, FPM_ONLY=275, DENISE_ONLY_GHOST=259, others=66. |
| Reconciliation Excel | Sam's review surface | `F:\downloads\AP_Master_Reconciliation_2026-05-13.xlsx` (116 KB, 11 tabs). |
| Sync log | Proves last sync state | AP Master tab `_sync_log_v3` row count 1,830. Last entry 2026-05-13 08:12:52 PHT (`invoice_seeded_from_fpm` CAPEX row 172). |

### Count method

- **Denise rows to scan:** total rows in Denise's `Payment Plan` tab minus 3 banner/header rows = 627 actual data rows. After filtering `outstanding > 0`, ~440 rows are candidates for appending. Verified count basis: `python -c "import json; d=json.load(open('tmp/finance_ap_audit/audit_2026-05-13/normalized_denise_pp.json')); print(len(d), sum(1 for r in d if r.get('outstanding',0) > 0))"` → 604 rows, 161 with outstanding > 0 (others are already paid — skipped).
- **Expected appends on first live run:** ~161 (rows with outstanding > 0). Some will be skipped if they already exist via FPM seed (lookup by supplier_norm + invKey + BEI-FIN). Conservative estimate: 100-150 new rows appended.
- **Expected total AP Master Suppliers SOA row count after Phase 3:** 990 → 1,100–1,150.

### Authoritative sections

Phases 0-7 below are authoritative for execution. The audit/amendment history (if added by `/audit-plan-bei-erp`) is traceability only.

### Unresolved-value policy

Any operator-facing label encountered that can't be verified gets `[UNVERIFIED — requires resolution]`. There are no unverified values in this plan as drafted.

## Worktree Boot (Phase 0 — see Agent Boot Sequence)

This sprint runs in a disposable worktree at `F:/Dropbox/Projects/BEI-ERP-denise-sheet-sync`, never in the main checkout. The closeout phase removes the worktree.

## Design Rationale (For Cold-Start Agents)

### Why this exists

Three accumulated decisions left Denise's tracker outside the AP Master ecosystem:

1. **2026-04-28** — Denise inherited Finance lead (Juanna resigned 2026-04-27). She needed a workspace she controlled.
2. **2026-05-07** — Butch (CFO) + Alyssa resigned. Skeleton-crew Finance team. Denise built her own sheet to manage 2-week pay planning.
3. **2026-05-12** — Commissary tab wipe incident triggered a strict-lock on 14 AP Master auto-rebuilt tabs (per the `/finance-ap` skill). Same day, Denise created `Project: 2-Week Payment Plan`. The strict-lock made AP Master feel "frozen" to her.

Today's audit (2026-05-13) proved:
- Of Denise's ₱53.8M outstanding, **₱0** is fully reconciled across AP Master + FPM + Compliance.
- ₱23.6M is GHOST (no trail anywhere).
- ₱29.2M is FPM-only (RFPs exist but no Compliance paperwork, no AP Master view).
- The 14-tab strict-lock didn't apply to the 3 entry tabs (Suppliers SOA / Head Office / CAPEX) — she COULD have added columns there — but didn't, likely because the script's `buildGrid()` writes 19-column entry tabs and would overwrite any custom columns on a legacy full rebuild.

### Why this architecture

**Alternatives considered (and rejected):**

| Option | Why rejected |
|---|---|
| Tell Denise to abandon her sheet and use AP Master directly | Her sheet has 10+ columns AP Master doesn't (Address, TIN, VAT/Nonvat, Terms, Description, Due Date, Paid Amount, separated aging columns). Forcing her into AP Master as-is loses her workflow value. |
| Add `IMPORTRANGE` formula to AP Master pulling from her sheet | IMPORTRANGE has rate limits, no dedup, can't write back. Also breaks if Denise changes her sheet structure. |
| Build a read-only mirror tab in AP Master via Apps Script | Doesn't solve the data-staying-in-her-sheet problem. AP Master summary tabs still wouldn't aggregate her rows. |
| Reverse-seed approach: Apps Script reads her sheet, appends new rows to AP Master entry tabs hourly | **CHOSEN.** Her sheet becomes a data source like FPM. Zero workflow change. Same proven pattern as `seedNewInvoicesFromFPM_` deployed today (2,329 rows appended on first run, no issues). |

**Why Phase 2 (migrate at 2-week mark):** Phase 1 alone leaves two sheets — better than three but still not single-source. The CEO directive says "she can transfer back to AP Master as soon as the 2-week project is over." Phase 2 formalizes that migration with the schema Denise actually uses.

### Key trade-off decisions

| Decision | Choice | Reason |
|---|---|---|
| Status mapping (Denise → AP Master enums) | Conservative mapping; unknown → `WITH FINANCE` | AP Master script's downstream summary tabs filter by status. Falling back to `WITH FINANCE` keeps the row in "needs RFP/processing" buckets, avoiding accidentally hiding it. |
| Route Denise rows to which entry tab? | Always Suppliers SOA in Phase 1 | Denise's tracker is mostly inventory suppliers. Head Office/CAPEX routing would require category-inference from Denise's "Goods/Services" column. Defer to Phase 5 migration where we add a dedicated `Payment Plan` tab. |
| Dedup keys | `supplier_norm + invKey(invoice)` AND `supplier_norm + BEI-FIN` | invoice-number normalization (strip leading zeros) catches Denise's `00048` matching AP Master's `48`. BEI-FIN matching catches cases where supplier invoice numbers don't exist on AP Master legacy. |
| Phase 5 migration timing | ~2026-05-27 (2-week mark) | Denise explicitly named her sheet "2-Week Payment Plan." The 2-week boundary is her natural close. Earlier migration disrupts her work; later defeats the 1-sheet goal. |
| Phase 5 tab name in AP Master | `Payment Plan` (not "Denise PP" or "2-Week Plan") | Stable name that survives Denise's role change. The pattern of [tab name = function] matches existing tabs (Suppliers SOA, Head Office, CAPEX). |

### Known limitations and their mitigations

| Limitation | Mitigation |
|---|---|
| Comma-separated invoices in Denise's sheet (e.g., Suzuyo row "0362,0363,0364…") get treated as single-row | Accept in Phase 1 (3 rows total, ₱2.6M). Phase 5 migration splits them into individual rows. |
| Apps Script execution time limit (6 min for runWebApp triggers) | Denise's 604 rows finish in <30 sec (FPM seed of 2,464 rows finished in 56.6 sec today). Well under limit. |
| Status field can't sync BACK from FPM to Denise's standalone sheet | Accepted for the 2-week window. After Phase 6 migration, the `Payment Plan` tab IS in AP Master, so FPM status syncs to it directly via existing `syncStatusFieldsFromFPM_`. |
| Denise might add a new invoice 5 minutes before the next hourly tick | Acceptable lag. Cron runs xx:12 PHT every hour. Worst case: 59 min delay before AP Master sees it. |
| If Phase 1 misroutes an inventory supplier to Suppliers SOA when it should be Head Office | Manual move via Suppliers SOA tab edit. Re-routing logic is in Phase 5 with Compliance Suppliers roster as the canonical reference. |

### Source references

- `tmp/finance_ap_audit/audit_2026-05-13/four_way_match.json` — 604 Denise rows classified
- `tmp/finance_ap_audit/audit_2026-05-13/DENISE_VS_INFRA_FINDINGS.md` — full audit narrative
- `tmp/finance_ap_audit/audit_2026-05-13/SYNC_DENISE_TO_AP_MASTER_PLAN.md` — design spec
- `tmp/finance_ap_audit/live_script/Code.gs` — current v3.6 Apps Script source (50,977 → 59,573 chars after FPM seed patch deployed today)
- `CEO/CashFlow/intercompany_gl/ap_view_hourly_sync_v4_fpm_seed_patch.gs` — repo source of the v4 FPM seed patch (the pattern this sprint clones)
- `.claude/skills/finance-ap/SKILL.md` — operational skill, includes script architecture
- `.claude/skills/finance-ap/references/script-v3.md` — Apps Script architecture detail

## Requirements Regression Checklist

Verify these BEFORE writing code. Each is a yes/no assertion the executing agent checks against its own implementation.

- [ ] Is `seedFromDenisePaymentPlan_(ss, fpmLookup, taxLookup, dryRun)` defined with the same signature shape as `seedNewInvoicesFromFPM_(ss, fpmLookup, taxLookup, dryRun)`?
- [ ] Does the new function read from sheet ID `13cyYaPLmjL0TPaeqyYd2esjJNYj-5qJCDS8OZLdhURU` tab `Payment Plan`?
- [ ] Is the header row treated as row 3 (0-indexed: 2)? Data starts row 4 (0-indexed: 3)?
- [ ] Are column indices read by NAME (not hardcoded position) using a header→index lookup, in case Denise re-orders columns?
- [ ] Does the dedup index include BOTH `supplier_norm + invKey(invoice)` AND `supplier_norm + 'FIN' + bei_fin`?
- [ ] Are rows with `outstanding <= 0` skipped (already paid)?
- [ ] Are appended rows tagged `SOURCE = 'Denise PP'` in column A?
- [ ] Are statuses mapped via `mapDeniseToApStatus_()` with fallback to `WITH FINANCE`?
- [ ] Is `computeAgingBucket_(days)` returning the 6 canonical buckets matching AP Master's existing `aging_bucket` values?
- [ ] Does `doRefreshAllTabs_v3_` call `seedFromDenisePaymentPlan_` AFTER `seedNewInvoicesFromFPM_` so FPM seeds first (and Denise rows are deduped against the FPM-seeded ones)?
- [ ] Does the new function log via `logEvent_('INFO', 'denise_seed_appended', {...})` like the FPM seed?
- [ ] Is the dry-run path exercised first (`?fn=refreshAllTabs&dryRun=1`) BEFORE the live deploy?
- [ ] Does v3.7 get deployed via `script.projects.versions.create` + `script.projects.deployments.update` (NOT by changing the existing deployment in place)?
- [ ] Phase 4 monitors for 24 hours via `_sync_log_v3` row count before declaring stability?
- [ ] Phase 5 reads Compliance Suppliers roster to classify supplier_type before routing migration rows to Suppliers SOA vs Head Office?
- [ ] Phase 6 retires Denise's standalone sheet by renaming + comment-only ACL (not deletion)?

## Phase Budget Contract

| Phase | Description | Estimated units |
|---|---|---|
| Phase 0 | Worktree boot + audit + source backup | 2 |
| Phase 1 | Write `seedFromDenisePaymentPlan_()` + helpers + wire into `doRefreshAllTabs_v3_` | 5 |
| Phase 2 | Dry-run + manual review of would-append rows | 3 |
| Phase 3 | Deploy v3.7 + trigger first live sync | 3 |
| Phase 4 | 24-hour monitor (≥24 hourly cycles via Cloud Scheduler) | 2 |
| Phase 5 | Phase 6 migration plan + Compliance Suppliers roster routing logic | 5 |
| Phase 6 | Execute migration: add `Payment Plan` tab to AP Master + bulk-import Denise's rows | 4 |
| Phase 7 | Retire Denise's standalone sheet + closeout artifacts | 2 |
| **Total** | | **26 units** |

- **Hard limit:** 80 (well under)
- **Preferred split threshold:** 12 per phase (max here is 5)
- **Status:** within budget

## Anti-Rewind / Concurrent-Run Protection

### Ownership matrix

| Surface | Owner | Notes |
|---|---|---|
| Apps Script project `1pE8wt_z8NA9q__PNbUilJ72UE0_EI3DmurJekkw6mbgtHr8hosnKsNRF` HEAD content | S248 (this sprint) | No other sprint may push to this project HEAD until S248 closeout. |
| `CEO/CashFlow/intercompany_gl/ap_view_hourly_sync_v4_fpm_seed_patch.gs` | S248 | Edit the existing FPM-seed patch file to also include the Denise seed. Don't create a new file. |
| AP Master Suppliers SOA / Head Office / CAPEX entry tabs | Script-writes only (no human entry during S248 monitoring window unless coordinated) | Ms. Mel (angelamel) and Denise are the only humans who edit these. They keep working normally. The seed only APPENDS, never modifies existing rows. |
| AP Master `Payment Plan` tab (new in Phase 6) | S248 creates it; ongoing edits owned by Denise + Sam after migration | Strict-lock blocks all other team members. |
| Denise's standalone sheet `13cyYaPLmjL0TPaeqyYd2esjJNYj-5qJCDS8OZLdhURU` | Denise (read-only for the script) | Script reads but never writes to her sheet during the 2-week window. Phase 7 renames + comment-locks it. |

### Protected surfaces

These must NOT regress during S248 execution:

| Surface | Behavior to preserve | Verification |
|---|---|---|
| FPM seed (`seedNewInvoicesFromFPM_`) | Continues to seed FPM rows hourly | Phase 3 first-run result shows `fpm_seed.scanned > 0` even though `appended` may be 0 |
| Status sync (`syncStatusFieldsFromFPM_`) | Continues to sync FPM status to AP Master entry tabs | `status_sync.nochange + status_sync.updates > 0` per cycle |
| Tax sync (`syncTaxFieldsFromCompliance_`) | Continues to sync Compliance VAT/EWT | `tax_sync.nochange + tax_sync.updates > 0` per cycle |
| Banner row 4 on entry tabs | Stays as-is (already stale per RF-7 in today's audit — this sprint doesn't address banner) | Visual check after Phase 3 deploy |
| `_sync_log_v3` audit trail | Continues to log every cycle | Row count grows by 1+ per hour |

### Remote-truth baseline

| Item | Value |
|---|---|
| Apps Script live version | 13 (WebApp v3.6) as of 2026-05-13 ~10:30 PHT |
| Apps Script project HEAD source size | 59,573 chars |
| AP Master Suppliers SOA row count | 990 |
| AP Master Head Office row count | 4,373 |
| AP Master CAPEX row count | 172 |
| Denise sheet row count | 631 rows (banner + header + 627 data + 2 trailing) |
| `_sync_log_v3` row count | 1,830 |
| hrms repo HEAD branch | `production` (default) |
| Latest commits on production | `35e050990 registry(s242): update row to PLANNED_AUDITED_v1.1 + scope expansion` |

Capture exact SHA via `git rev-parse origin/production` in Phase 0 step 6.

### Pre-touch backup

Phase 0 step 5 runs:
```bash
mkdir -p tmp/s248
python tmp/finance_ap_audit/audit_2026-05-13/extract_compliance.py  # already run — confirm output exists
```
And:
```python
# Phase 0 step 5b: backup current Apps Script source before editing
from google.oauth2 import service_account
from googleapiclient.discovery import build
creds = service_account.Credentials.from_service_account_file('credentials/task-manager-service.json',
    scopes=['https://www.googleapis.com/auth/script.projects']).with_subject('sam@bebang.ph')
api = build('script', 'v1', credentials=creds, cache_discovery=False)
content = api.projects().getContent(scriptId='1pE8wt_z8NA9q__PNbUilJ72UE0_EI3DmurJekkw6mbgtHr8hosnKsNRF').execute()
code = next(f for f in content['files'] if f['name']=='Code')['source']
open('tmp/s248/script_source_backup_v36.gs','w',encoding='utf-8').write(code)
print(f"Backed up {len(code)} chars to tmp/s248/script_source_backup_v36.gs")
```

## Surface Ownership Matrix (output/s248/SXXX_SURFACE_OWNERSHIP_MATRIX.csv)

Generated in Phase 0 step 7. Schema:
```
surface,owner_sprint,protected,verification_method
script-project-1pE8wt,S248,yes,script.projects.getContent SHA compare
ap-master-suppliers-soa-tab,S248-write-only,yes,row count + last-row payee match
ap-master-head-office-tab,S248-write-only,yes,row count + last-row payee match
ap-master-capex-tab,no-S248-writes,yes,row count unchanged
denise-pp-sheet,S248-read-only,yes,sheet revisionHistory unchanged for service-account writes
```

## Zero-Skip Enforcement

Every task below has a `MUST_MODIFY` or `MUST_CONTAIN` assertion or a verification script step. The phase gate is a Python script (`output/s248/verify_phase{N}.py`) that returns 0 only if all checks pass. **Skipping is forbidden.** If a task cannot complete, the agent STOPS and asks Sam.

### Forbidden agent behaviors

- Marking partial work as DONE
- Replacing a task with a simpler version without Sam's approval
- "Deferred to next sprint" — there is no next sprint for this work; if a phase can't complete, STOP
- Combining tasks and dropping features
- Self-grading verifications based on prose description instead of filesystem evidence
- Silently retrying deploy if it fails — STOP and present the error

### Phase completion checklist format

After each phase, write `output/s248/phase{N}_checklist.md`:

| Task | Status | Evidence (file path + assertion) | Skipped? | If skipped, why? |
|---|---|---|---|---|
| 1.1 | DONE | `git diff CEO/CashFlow/intercompany_gl/ap_view_hourly_sync_v4_fpm_seed_patch.gs` contains `function seedFromDenisePaymentPlan_` | NO | n/a |
| ... | | | | |

## Status Reconciliation Contract

When any of these change, update ALL in the same work unit:

1. `output/s248/SUMMARY.md` — running status narrative
2. `output/s248/closeout_state.json` — machine-readable status
3. `output/s248/v37_deployment.json` — Phase 3 deploy proof
4. This plan's YAML metadata (`status` field — PLANNED → IN_PROGRESS → COMPLETED)
5. `docs/plans/SPRINT_REGISTRY.md` S248 row — Status column

## Signoff Model

- **Mode:** single-owner
- **Approver of record:** Sam Karazi (CEO)
- **Signoff artifact:** `output/s248/closeout_state.json` with `closeout_state.signed_off_by = "sam@bebang.ph"` and `closeout_state.signed_off_at = <ISO timestamp>`
- **Note:** Per the 2026-05-07 memory (`finance-team-2026-04-15.md`), CFO seat is vacant. Sam approves alone. No Butch/Alyssa/Juanna sign-off rows.

## Autonomous Execution Contract

### Completion condition

This sprint is COMPLETE when ALL of the following are true:

- [ ] Phases 0-7 all show `status=DONE` in their respective phase checklist files
- [ ] `output/s248/v37_deployment.json` exists and shows `version_number=14 (or higher)` and `deployment_id=AKfycbw-AuqJq6OyMV6DGarGWEruDoez04OETlWFQoeppNjvzoeSOJOomPOZNsVPE9iuV6ZC_Q`
- [ ] `output/s248/first_live_sync.json` shows `denise_seed.appended >= 100 AND denise_seed.appended <= 200` (within expected range)
- [ ] `output/s248/dedup_verification.json` shows zero duplicate rows in AP Master after 24h
- [ ] `output/s248/migration_executed.json` shows `payment_plan_tab_created=true AND rows_migrated >= 600`
- [ ] Denise's standalone sheet name contains `[ARCHIVED 2026-05-27]` prefix
- [ ] Denise's standalone sheet ACL has Sam as Owner, Denise as Commenter (no Editors)
- [ ] AP Master `Payment Plan` tab is strict-protected (editors = sam@ + denise@ only)
- [ ] PR created in hrms repo with branch `s248-denise-sheet-sync`, plan + script + closeout artifacts committed
- [ ] `docs/plans/SPRINT_REGISTRY.md` S248 row status changed to `COMPLETED`
- [ ] This plan's YAML `status: COMPLETED` and `completed_date` filled in
- [ ] PR shared with Sam — agent STOPS, does NOT merge

### Stop-only-for

- Missing credentials/access (Apps Script API permission revoked, Drive API failures)
- Destructive approval needed (e.g., renaming Denise's sheet — actually IS destructive in some sense; agent presents the rename plan and waits for Sam's go in Phase 7)
- Genuine business-policy decision (e.g., Denise rejects the migration plan in Phase 5 — escalate to Sam)
- Direct conflict with unrelated in-flight changes (e.g., someone else pushed to the Apps Script project between Phase 0 backup and Phase 3 deploy)

### Continue without pause through

- Phase 0 → Phase 1 → Phase 2 (dry-run) → Phase 3 (deploy v3.7) → Phase 4 (24h monitor) → Phase 5 (plan migration) → Phase 6 (execute migration) → Phase 7 (closeout)

**Exception:** Phase 4 by definition takes ~24 hours of wall-clock time waiting for Cloud Scheduler ticks. The agent can either:
- (a) Run other validation work in parallel during the wait
- (b) Suspend with a re-entry note in `output/s248/phase4_resume_at.json` (resume after `2026-05-14 10:30 PHT` or later)

Phase 5-6 should ideally be a fresh agent session (~2026-05-27, 2 weeks after Phase 3). If the executing agent is the same session that ran Phase 1-4, hand off via the closeout note in `output/s248/phase4_done_resume_at.json`.

### Blocker policy

- **Programmatic** (script syntax error, dedup logic wrong) → fix and continue
- **Evidence mismatch** (Denise sheet schema changed between Phase 0 and Phase 6) → re-snapshot, normalize plan, continue
- **Repeated technical failure x3** (Apps Script deploy fails 3 times in a row) → grounded research (read GAS API docs, check `output/s248/traceback_*.txt`), then continue
- **Business-data/policy** (Denise's sheet contains a column we don't know how to map) → pause, ask Sam
- **Active-run conflict** (someone else patched the Apps Script during S248) → pause, present diff, ask Sam how to merge

### Canonical closeout artifacts (all required at PR creation)

- `output/s248/SUMMARY.md`
- `output/s248/DEFECTS.md` (empty if no defects)
- `output/s248/v37_deployment.json`
- `output/s248/first_live_sync.json`
- `output/s248/dedup_verification.json`
- `output/s248/migration_plan.md`
- `output/s248/migration_executed.json`
- `output/s248/closeout_state.json`
- `output/s248/phase0_checklist.md` through `output/s248/phase7_checklist.md`
- `docs/plans/2026-05-13-sprint-248-denise-sheet-sync.md` (this file, YAML updated)
- `docs/plans/SPRINT_REGISTRY.md` (S248 row updated)
- `CEO/CashFlow/intercompany_gl/ap_view_hourly_sync_v4_fpm_seed_patch.gs` (the edited script source)

## Phase 0 — Agent Boot Sequence

> First numbered action. Do not skip.

1. **Read this plan fully** — TL;DR through Autonomous Execution Contract.

2. **Read related references** (in this order, only as needed):
   - `tmp/finance_ap_audit/audit_2026-05-13/DENISE_VS_INFRA_FINDINGS.md` (full audit context)
   - `tmp/finance_ap_audit/audit_2026-05-13/SYNC_DENISE_TO_AP_MASTER_PLAN.md` (design spec including the 50-line patch outline)
   - `.claude/skills/finance-ap/SKILL.md` + `references/script-v3.md` (Apps Script architecture)
   - `tmp/finance_ap_audit/live_script/Code.gs` (current v3.6 live source — to understand what's already there)

3. **Spawn worktree:**
   ```bash
   BR=s248-denise-sheet-sync
   WT=F:/Dropbox/Projects/BEI-ERP-${BR##*/}
   cd F:/Dropbox/Projects/BEI-ERP && git fetch origin --prune
   git worktree add "$WT" -B "$BR" origin/production
   cd "$WT"
   ```

4. **Record remote-truth baseline:**
   ```bash
   git rev-parse origin/production > output/s248/baseline_sha.txt
   mkdir -p output/s248 tmp/s248
   ```

5. **Backup current Apps Script source** (pre-touch):
   - Run the Python snippet in §Pre-touch backup above. Confirms `tmp/s248/script_source_backup_v36.gs` ≥ 59,000 chars.

6. **Sanity-check the production state:**
   - `python -u -c "from google.oauth2 import service_account; from googleapiclient.discovery import build; c=service_account.Credentials.from_service_account_file('credentials/task-manager-service.json',scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']).with_subject('sam@bebang.ph'); s=build('sheets','v4',credentials=c,cache_discovery=False); print({tab: len(s.spreadsheets().values().get(spreadsheetId='1bQ6mO1FXD4VYcLt8m-yklkV7pyYhSWqU7b8K0bVgG7c', range=f'\\'{tab}\\'!A:A').execute().get('values',[])) for tab in ['Suppliers SOA','Head Office','CAPEX','_sync_log_v3']})"`
   - Expected: `{'Suppliers SOA': 990, 'Head Office': 4373, 'CAPEX': 172, '_sync_log_v3': 1830}` (±1 row drift acceptable).
   - Save to `output/s248/baseline_sheet_state.json`.

7. **Write surface ownership matrix:** `output/s248/SXXX_SURFACE_OWNERSHIP_MATRIX.csv` per §Anti-Rewind matrix above.

**MUST_CONTAIN check:**
- `output/s248/baseline_sha.txt` is non-empty
- `tmp/s248/script_source_backup_v36.gs` size ≥ 59000 chars
- `output/s248/baseline_sheet_state.json` contains `"Suppliers SOA"` and `"_sync_log_v3"` keys
- `output/s248/SXXX_SURFACE_OWNERSHIP_MATRIX.csv` has ≥ 5 rows

## Phase 1 — Build `seedFromDenisePaymentPlan_()`

Author the function inside `CEO/CashFlow/intercompany_gl/ap_view_hourly_sync_v4_fpm_seed_patch.gs`. Follow the 50-line outline in `tmp/finance_ap_audit/audit_2026-05-13/SYNC_DENISE_TO_AP_MASTER_PLAN.md`.

### Tasks

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 1.1 | Add `seedFromDenisePaymentPlan_(ss, fpmLookup, taxLookup, dryRun)` function. | MUST_MODIFY: `CEO/CashFlow/intercompany_gl/ap_view_hourly_sync_v4_fpm_seed_patch.gs`. MUST_CONTAIN: `function seedFromDenisePaymentPlan_` |
| 1.2 | Function reads from sheet ID `13cyYaPLmjL0TPaeqyYd2esjJNYj-5qJCDS8OZLdhURU` via 4 tabs in priority order: (a) `Suppliers w/o FD & Middleby` → SOURCE `Denise PP`, (b) `Middleby` → SOURCE `Denise PP - Disputed (Middleby)`, (c) `Forward Dynamics` → SOURCE `Denise PP - Disputed (FD)`, (d) `Masterlist` → SOURCE `Denise PP - Masterlist` (safety net, only seeds rows not already deduped from a/b/c). Per CEO 2026-05-14: Middleby + FD are disputed-but-eventually-payable; keep them tagged distinctly in AP Master so urgent vs disputed AP can be filtered. | MUST_CONTAIN: `13cyYaPLmjL0TPaeqyYd2esjJNYj-5qJCDS8OZLdhURU` AND `'Suppliers w/o FD & Middleby'` AND `'Middleby'` AND `'Forward Dynamics'` AND `'Masterlist'` AND `'Denise PP - Disputed (Middleby)'` AND `'Denise PP - Disputed (FD)'` |
| 1.3 | Build header→index map for Denise's columns: `Supplier`, `Address`, `TIN`, `VAT/NONVAT`, `GOODS/SERVICES`, `Invoice Date`, `Terms`, `BEI FIN`, `Invoice No`, `DESCRIPTION`, `VATABLE SALES`, `VAT`, `EWT`, `GROSS Amount`, `Paid Amount`, `Outstanding Balance`, `DUE DATE`, `AGING (days)`, `Status`. Do NOT hardcode column positions. | MUST_CONTAIN: `var headerMap = {};` or equivalent dynamic header lookup |
| 1.4 | Build dedup index from AP Master Suppliers SOA + Head Office (data starts row 18). Index by `supplier_norm + '|' + invKey(invoice)` AND `supplier_norm + '|FIN|' + bei_fin`. | MUST_CONTAIN: `existingKeys.add(` |
| 1.5 | Iterate Denise rows starting at index 3 (row 4). Skip blank Supplier. Skip `outstanding <= 0`. | MUST_CONTAIN: `if (outstanding <= 0)` |
| 1.6 | Map Denise status to AP Master status via new helper `mapDeniseToApStatus_(s)`. Fallback to `WITH FINANCE`. | MUST_CONTAIN: `function mapDeniseToApStatus_` AND `return 'WITH FINANCE'` |
| 1.7 | Compute aging bucket via `computeAgingBucket_(days)`. Buckets: `Not Yet Due` / `0-30 days` / `31-60 days` / `61-90 days` / `91-120 days` / `Over 120 days`. | MUST_CONTAIN: `function computeAgingBucket_` AND `'Over 120 days'` |
| 1.8 | Build the 19-column row in AP Master schema order: SOURCE=<per-tab tag from task 1.2>, PAYEE, INVOICE NO., INVOICE DATE, AMOUNT, OUTSTANDING, AGING, AGING BUCKET, STATUS, BEI-FIN, RFP No.='', METHOD='', CHECK NO.='', CATEGORY=<'Supplier Payments' for regular; 'Disputed - Eventually Payable' for Middleby/FD>, CLASSIFICATION='', BILLED TO='', VATABLE, VAT, EWT. | MUST_CONTAIN: `'Denise PP'` AND `'Supplier Payments'` AND `'Disputed - Eventually Payable'` |
| 1.9 | Append rows to `Suppliers SOA` only (Phase 1; routing logic deferred to Phase 5). | MUST_CONTAIN: `getSheetByName('Suppliers SOA')` AND `.setValues(toAppend)` |
| 1.10 | Log every successful append via `logEvent_('INFO', 'denise_seed_appended', {tab, rows, start_row})`. | MUST_CONTAIN: `logEvent_('INFO', 'denise_seed_appended'` |
| 1.11 | Add Denise seed call to `doRefreshAllTabs_v3_(dryRun)` AFTER the existing FPM seed call. | MUST_MODIFY: `doRefreshAllTabs_v3_` function body. MUST_CONTAIN inside: `seedFromDenisePaymentPlan_(ss, fpmLookup, taxLookup, dryRun)` AND `stats.denise_seed = ` |
| 1.12 | Return stats dict from seed function: `{scanned, appended, skipped_existing, skipped_paid, skipped_blank}`. | MUST_CONTAIN: `return {scanned:` |

### Phase 1 verification script

Write `output/s248/verify_phase1.py`:

```python
import subprocess, re, sys
SRC = 'CEO/CashFlow/intercompany_gl/ap_view_hourly_sync_v4_fpm_seed_patch.gs'
code = open(SRC,'r',encoding='utf-8').read()
checks = {
    'seedFromDenisePaymentPlan_ defined': 'function seedFromDenisePaymentPlan_' in code,
    'Denise sheet ID present': '13cyYaPLmjL0TPaeqyYd2esjJNYj-5qJCDS8OZLdhURU' in code,
    'mapDeniseToApStatus_ defined': 'function mapDeniseToApStatus_' in code,
    'WITH FINANCE fallback present': "return 'WITH FINANCE'" in code or 'return "WITH FINANCE"' in code,
    'computeAgingBucket_ defined': 'function computeAgingBucket_' in code,
    'Over 120 days bucket present': 'Over 120 days' in code,
    'SOURCE Denise PP literal present': "'Denise PP'" in code or '"Denise PP"' in code,
    'Wired into doRefreshAllTabs_v3_': 'seedFromDenisePaymentPlan_(ss, fpmLookup, taxLookup, dryRun)' in code,
    'denise_seed in stats': 'stats.denise_seed' in code,
    'logEvent_ for append': "'denise_seed_appended'" in code,
    'outstanding > 0 filter': re.search(r'outstanding\s*<=\s*0', code) is not None,
}
fails = [k for k,v in checks.items() if not v]
print('Phase 1 checks:')
for k,v in checks.items():
    print(f'  [{ "OK" if v else "FAIL" }] {k}')
if fails:
    print(f'\nFAIL: {len(fails)} check(s) failed')
    sys.exit(1)
print('\nPASS: all 11 checks passed')
sys.exit(0)
```

Run: `python output/s248/verify_phase1.py` — must exit 0 before Phase 2.

**Phase 1 gate:** `verify_phase1.py` exits 0 AND `output/s248/phase1_checklist.md` written with all 12 tasks DONE.

## Phase 2 — Dry-run

### Tasks

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 2.1 | Push edited Apps Script HEAD via `script.projects.updateContent`. Do NOT promote to a version yet. | MUST_CONTAIN in `output/s248/phase2_push.json`: `"status": "ok"` |
| 2.2 | Hit dry-run URL: `<WEB_APP_URL>?key=bei-ap-sync-2026-04&fn=refreshAllTabs&dryRun=1`. (Note: `dryRun=1` runs the FULL cycle in dry mode — writes go to `_dry_run_preview` tab instead of real tabs.) | MUST_CONTAIN in HTTP response JSON: `"dry_run": true` AND `"denise_seed":` |
| 2.3 | Capture dry-run response to `output/s248/dry_run_phase2.json`. | MUST_CONTAIN: `denise_seed.scanned > 0` |
| 2.4 | Verify `denise_seed.appended` is in range `[80, 200]` (100-150 expected, with ±50 tolerance). | If outside range, INVESTIGATE before proceeding to Phase 3 — likely indicates a dedup/filter bug. Do NOT just adjust the range. |
| 2.5 | Spot-check 5 random rows from dry-run preview: each should have SOURCE='Denise PP', valid AGING BUCKET, valid mapped STATUS. | MUST_CONTAIN in `output/s248/dry_run_spotcheck.csv`: 5 rows with all required columns populated |

### Phase 2 verification script

`output/s248/verify_phase2.py`:

```python
import json, sys
d = json.load(open('output/s248/dry_run_phase2.json'))
assert d.get('dry_run') is True, 'not a dry-run response'
ds = d.get('denise_seed', {})
assert ds.get('scanned',0) > 0, 'denise seed not scanning'
appended = ds.get('appended', 0)
assert 80 <= appended <= 200, f'appended count {appended} outside [80,200] range — investigate'
# spotcheck
import csv
rows = list(csv.DictReader(open('output/s248/dry_run_spotcheck.csv', encoding='utf-8')))
assert len(rows) == 5, 'expected 5 spotcheck rows'
for r in rows:
    assert r.get('SOURCE') == 'Denise PP', f"row missing SOURCE: {r}"
    assert r.get('AGING BUCKET') in ('Not Yet Due','0-30 days','31-60 days','61-90 days','91-120 days','Over 120 days'), f"bad bucket: {r}"
print(f'PASS: dry-run shows {appended} rows ready to append, all 5 spotcheck rows valid')
sys.exit(0)
```

**Phase 2 gate:** `verify_phase2.py` exits 0.

## Phase 3 — Deploy v3.7 + first live sync

### Tasks

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 3.1 | Promote HEAD to version via `script.projects.versions.create` with description: `WebApp v3.7 — Denise PP seed (S248)`. | MUST_CONTAIN in `output/s248/v37_deployment.json`: `"versionNumber": 14` (or higher) |
| 3.2 | Update production deployment `AKfycbw-AuqJq6OyMV6DGarGWEruDoez04OETlWFQoeppNjvzoeSOJOomPOZNsVPE9iuV6ZC_Q` to point at new version via `script.projects.deployments.update`. | MUST_CONTAIN in same JSON: `"deploymentConfig.versionNumber": 14` (or higher) |
| 3.3 | Wait 30 seconds for deployment propagation. Then hit live URL: `<WEB_APP_URL>?key=bei-ap-sync-2026-04&fn=refreshAllTabs`. | MUST_CONTAIN in `output/s248/first_live_sync.json`: HTTP 200 |
| 3.4 | Verify live response shows `denise_seed.appended` close to dry-run value (within ±10 rows). | MUST_CONTAIN: `denise_seed.appended >= 80` |
| 3.5 | Re-pull AP Master Suppliers SOA row count. Expect 990 + appended count. | MUST_CONTAIN in `output/s248/sheet_state_after_phase3.json`: `Suppliers SOA >= 1070` (if appended >= 80) |
| 3.6 | Re-pull `_sync_log_v3`. Expect 1830 + (number of log events from this run). | MUST_CONTAIN: `_sync_log_v3 >= 1840` |
| 3.7 | Verify the FPM seed and Status sync still ran (didn't break them). | MUST_CONTAIN: `fpm_seed.scanned > 0 AND status_sync.tabs_seen contains Suppliers SOA` |

### Phase 3 verification script

`output/s248/verify_phase3.py`:

```python
import json, sys
dep = json.load(open('output/s248/v37_deployment.json'))
assert dep.get('versionNumber', 0) >= 14, f"version too low: {dep.get('versionNumber')}"
assert dep.get('deploymentConfig',{}).get('versionNumber', 0) >= 14, 'deployment not pointing at v14+'
live = json.load(open('output/s248/first_live_sync.json'))
ds = live.get('denise_seed', {})
assert ds.get('appended', 0) >= 80, f"live appended too low: {ds.get('appended')}"
# Protected surfaces — FPM and status sync still working
fpm = live.get('seed',{}).get('fpm_seed',{})
assert fpm.get('scanned',0) > 0, 'FPM seed regressed'
ss = live.get('status_sync',{})
assert 'Suppliers SOA' in ss.get('tabs_seen',{}), 'status sync regressed'
state = json.load(open('output/s248/sheet_state_after_phase3.json'))
assert state['Suppliers SOA'] >= 1070, f"SOA row count too low: {state['Suppliers SOA']}"
assert state['_sync_log_v3'] >= 1840, f"sync log not updated: {state['_sync_log_v3']}"
print(f"PASS: v3.7 deployed (version={dep['versionNumber']}), {ds['appended']} Denise rows appended, protected surfaces healthy")
sys.exit(0)
```

**Phase 3 gate:** `verify_phase3.py` exits 0.

## Phase 4 — 24-hour monitor

> **Time-bound:** This phase requires wall-clock time. Either the agent waits, or it suspends and resumes via `output/s248/phase4_resume_at.json`.

### Tasks

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 4.1 | Wait minimum 24 hours after Phase 3 (≥24 hourly Cloud Scheduler cycles). | MUST_CONTAIN in `output/s248/phase4_monitor_window.json`: `"phase3_end": <ts1>`, `"phase4_check": <ts2>`, `ts2 - ts1 >= 86400 seconds` |
| 4.2 | Re-pull `_sync_log_v3` and verify ≥24 new log entries. | MUST_CONTAIN: row count delta ≥ 24 |
| 4.3 | Re-pull AP Master Suppliers SOA. Verify no orphan/duplicate rows. | MUST_CONTAIN in `output/s248/dedup_verification.json`: zero duplicate `(supplier_norm, invKey)` pairs |
| 4.4 | Inspect any new `'Denise PP'` rows appended after Phase 3 — should match new rows on Denise's sheet. | MUST_CONTAIN: append count matches new Denise rows |
| 4.5 | Check error logs (`_sync_log_v3` rows where `event` contains `error` or `failed`) for last 24h — should be zero. | MUST_CONTAIN: `error_count: 0` |

### Phase 4 verification script

`output/s248/verify_phase4.py`:

```python
import json, sys
m = json.load(open('output/s248/phase4_monitor_window.json'))
assert m['ts2'] - m['ts1'] >= 86400, 'monitor window < 24h'
d = json.load(open('output/s248/dedup_verification.json'))
assert d['duplicate_pairs'] == 0, f"duplicates found: {d['duplicate_pairs']}"
assert d['error_count'] == 0, f"errors in sync log: {d['error_count']}"
assert d['log_delta_24h'] >= 24, f"too few sync cycles: {d['log_delta_24h']}"
print(f"PASS: 24h stable, {d['log_delta_24h']} sync cycles, 0 dupes, 0 errors")
sys.exit(0)
```

**Phase 4 gate:** `verify_phase4.py` exits 0 AND `output/s248/phase4_done_resume_at.json` written with a resume timestamp ≥ `2026-05-27 09:00 PHT`.

## Phase 5 — Migration plan (~2026-05-27)

Authors the Phase 6 migration. Writes `output/s248/migration_plan.md`.

### Tasks

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 5.1 | Pull current Denise sheet snapshot. Compare against the Phase 0 baseline (`tmp/s248/denise_sheet_snapshot_phase0.csv` written in Phase 0) — list any schema changes. | MUST_CONTAIN in `output/s248/migration_plan.md`: section `## Schema Diff` |
| 5.2 | Pull current Compliance Suppliers roster (Drive ID `1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q` tab `Suppliers`). Classify each Denise supplier as INVENTORY / HEAD OFFICE / CAPEX based on Compliance category. | MUST_CONTAIN: `## Supplier Type Routing` with classification per supplier |
| 5.3 | Design AP Master `Payment Plan` tab schema. Columns 1-19 match the existing 3 entry tabs (SOURCE, PAYEE, INVOICE NO., …, VATABLE, VAT, EWT). Columns 20-30 add Denise's extras: Address, TIN, VAT/Nonvat, Terms, Description, Due Date, Paid Amount, separated aging buckets (Not Yet Due / 0-30 / 31-60 / 61-90 / 91-120 / Over 120). | MUST_CONTAIN: `## Tab Schema` with 30 columns listed |
| 5.4 | Plan how `buildGrid()` / `syncStatusFieldsFromFPM_()` will treat the new tab. (Decision: treat as a 4th entry tab; existing aggregations include it; status sync writes to it.) | MUST_CONTAIN: `## Script Changes` section |
| 5.5 | Plan ACL: strict-lock to `sam@bebang.ph` (Owner) + `denise@bebang.ph` (Editor). Block all others. | MUST_CONTAIN: `## ACL Plan` |
| 5.6 | Plan archival of Denise's standalone sheet: rename to `[ARCHIVED 2026-05-27] Project: 2-Week Payment Plan`, downgrade Denise's role to Commenter, remove Editor role from anyone else. | MUST_CONTAIN: `## Archival Plan` |
| 5.7 | Sanity-check: confirm Sam still approves the migration. Send a Chat ping to Sam summarising the plan; wait for explicit ack before Phase 6. | MUST_CONTAIN in `output/s248/sam_ack.json`: `"sam_approved": true` |

**Phase 5 gate:** `output/s248/migration_plan.md` exists with all 6 required sections AND `sam_ack.json.sam_approved == true`.

## Phase 6 — Execute migration

### Tasks

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 6.1 | Add `Payment Plan` tab to AP Master via Sheets API (`batchUpdate.addSheet`). Set strict protection per Phase 5 ACL. | MUST_CONTAIN in `output/s248/migration_executed.json`: `payment_plan_tab_created: true` |
| 6.2 | Write 30-column header row. | MUST_CONTAIN: `header_written: true` |
| 6.3 | Bulk-import Denise's 604 rows into the new tab. Use Phase 5's supplier-type routing to also COPY into Suppliers SOA / Head Office / CAPEX entry tabs with appropriate `SOURCE='Denise PP migrated'` tag (one-time migration only — going forward, only the Payment Plan tab is the source). | MUST_CONTAIN: `rows_migrated >= 600` |
| 6.4 | Modify Apps Script: `seedFromDenisePaymentPlan_` becomes a no-op (returns `{retired: true}`) after the migration date. Remove the dependency on the external Denise sheet. | MUST_MODIFY: `CEO/CashFlow/intercompany_gl/ap_view_hourly_sync_v4_fpm_seed_patch.gs`. MUST_CONTAIN: `retired_from_denise_pp_date` constant set to `2026-05-27` |
| 6.5 | Update `syncStatusFieldsFromFPM_` and `buildGrid` to include `Payment Plan` as a 4th entry tab. | MUST_CONTAIN: `'Payment Plan'` in the entry-tab list of both functions |
| 6.6 | Deploy v3.8 with the migration changes. | MUST_CONTAIN in `output/s248/v38_deployment.json`: `"versionNumber": >= 15` |
| 6.7 | Trigger one immediate sync. Verify `Payment Plan` tab is now picked up by status sync. | MUST_CONTAIN in response: `tabs_seen.Payment Plan: >= 600` |

### Phase 6 verification script

`output/s248/verify_phase6.py`:

```python
import json, sys
m = json.load(open('output/s248/migration_executed.json'))
assert m.get('payment_plan_tab_created') is True, 'tab not created'
assert m.get('rows_migrated', 0) >= 600, f"rows migrated {m.get('rows_migrated')} < 600"
v38 = json.load(open('output/s248/v38_deployment.json'))
assert v38.get('versionNumber', 0) >= 15, f"v3.8 version too low: {v38.get('versionNumber')}"
# Code change verified
code = open('CEO/CashFlow/intercompany_gl/ap_view_hourly_sync_v4_fpm_seed_patch.gs').read()
assert "'Payment Plan'" in code or '"Payment Plan"' in code, 'Payment Plan tab not referenced in code'
assert 'retired_from_denise_pp_date' in code, 'retirement constant not set'
# Live sync proof
live = json.load(open('output/s248/sync_after_migration.json'))
assert live['status_sync']['tabs_seen'].get('Payment Plan', 0) >= 600, 'status sync not picking up Payment Plan tab'
print(f"PASS: Payment Plan tab created with {m['rows_migrated']} rows, v3.8 deployed, status sync wired")
sys.exit(0)
```

**Phase 6 gate:** `verify_phase6.py` exits 0.

## Phase 7 — Closeout

### Tasks

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 7.1 | Rename Denise's standalone sheet to `[ARCHIVED 2026-05-27] Project: 2-Week Payment Plan` via Drive API. | MUST_CONTAIN in `output/s248/closeout_state.json`: `denise_sheet_renamed: true` |
| 7.2 | Downgrade ACL: Sam = Owner, Denise = Commenter, remove any other editors. | MUST_CONTAIN: `denise_sheet_acl_locked: true` |
| 7.3 | Update `docs/plans/SPRINT_REGISTRY.md` S248 row: change status `PLANNED` → `COMPLETED`, fill PR number when available. | MUST_MODIFY: `docs/plans/SPRINT_REGISTRY.md` |
| 7.4 | Update THIS plan's YAML: `status: COMPLETED`, `completed_date: 2026-05-27`, write `execution_summary`. | MUST_MODIFY: `docs/plans/2026-05-13-sprint-248-denise-sheet-sync.md` |
| 7.5 | Write `output/s248/SUMMARY.md` with execution narrative (≤ 80 lines). | MUST_CONTAIN: SUMMARY.md exists with non-empty content |
| 7.6 | Write `output/s248/DEFECTS.md` (empty file if no defects, else list each defect with severity + status). | MUST_CONTAIN: DEFECTS.md exists |
| 7.7 | Commit + push: `git add -f docs/plans/2026-05-13-sprint-248-denise-sheet-sync.md docs/plans/SPRINT_REGISTRY.md output/s248/ CEO/CashFlow/intercompany_gl/ap_view_hourly_sync_v4_fpm_seed_patch.gs && git commit -m "S248: Denise PP sync + migration to AP Master Payment Plan tab" && git push -u origin s248-denise-sheet-sync` | MUST_MODIFY: branch `s248-denise-sheet-sync` pushed to origin |
| 7.8 | Create PR: `GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms --base production --title "S248: Sync Denise's Payment Plan into AP Master" --body-file output/s248/SUMMARY.md` | MUST_CONTAIN PR URL in `output/s248/pr.json` |
| 7.9 | Worktree closeout: `cd F:/Dropbox/Projects/BEI-ERP && git worktree remove F:/Dropbox/Projects/BEI-ERP-denise-sheet-sync` | Worktree dir no longer exists |
| 7.10 | STOP. Report PR # to Sam. Do NOT merge. | Agent terminates here. |

### Phase 7 verification script

`output/s248/verify_phase7.py`:

```python
import json, sys, os
c = json.load(open('output/s248/closeout_state.json'))
assert c.get('denise_sheet_renamed') is True
assert c.get('denise_sheet_acl_locked') is True
# Plan YAML
plan = open('docs/plans/2026-05-13-sprint-248-denise-sheet-sync.md').read()
assert 'status: COMPLETED' in plan, 'plan YAML not updated'
assert 'completed_date:' in plan and '2026-05-' in plan, 'completed_date not set'
# Registry
reg = open('docs/plans/SPRINT_REGISTRY.md').read()
assert '`S248`' in reg and 'COMPLETED' in reg, 'registry not updated'
# Files exist
for p in ['output/s248/SUMMARY.md', 'output/s248/DEFECTS.md', 'output/s248/pr.json']:
    assert os.path.exists(p), f'missing {p}'
print('PASS: closeout complete')
sys.exit(0)
```

**Phase 7 gate:** `verify_phase7.py` exits 0 AND PR URL is in `output/s248/pr.json` AND worktree removed.

## Failure Response

(Per `.claude/docs/qa-test-library-discipline.md` §Failure Discipline pattern, adapted for this Apps-Script sprint.)

### Mode A — App/script bug (real Apps Script regression)
Examples: dedup logic fails, status mapping wrong, FPM seed regresses.
Response: file as defect in `output/s248/DEFECTS.md`, fix the code, re-run verify script, re-deploy. Do NOT downgrade the assertions to make them pass.

### Mode B — Plan bug (this plan has a wrong assertion or expected count)
Example: dry-run returns 220 appended rows instead of expected 80-200 because Denise added more invoices today.
Response: investigate, document the actual count basis, update the plan inline (with same-edit normalization per the Ground-Truth Lock rule). Do NOT just bump the upper bound.

### Mode C — Brittleness (intermittent Apps Script timeout)
Example: occasional 502 from `/exec` URL when the sync overruns 6 minutes.
Response: fix the LIBRARY (split the sync into smaller batches), not the spec (no `retry(3)` masking). If ≥3 library-level fixes happen during execution, emit `output/s248/LIBRARY_IMPROVEMENTS.md` summarizing what was strengthened.

## Notes / Out-of-scope

- **Banner refresh (RF-7 from today's audit)** is NOT addressed in this sprint. The banner remains stale (₱81.66M legacy view). A separate fix is needed for `buildGrid()` to be called by `doRefreshAllTabs_v3_`, or a new `recomputeBanners_()` function. Documented for future sprint.
- **Compliance AppSheet upstream gap (RF-5: ICON 00183, 14 other invoices)** is NOT addressed. The Denise seed makes them visible in AP Master, but the procurement workflow break (suppliers bypass Compliance) remains. Belongs in the team-questions doc for SCM/Ian + Compliance/Cayla.
- **Middleby ₱19.78M credit hold** is a separate decision (see `output/s248/SUMMARY.md` carried over from today's audit). Not in S248 scope.
