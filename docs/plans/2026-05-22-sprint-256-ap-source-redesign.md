---
sprint_id: S256
title: AP Master v3.10 + source-of-truth redesign per Denise's signed S255 closeout (Procurement App + 05-AP-Opening-HO + intercompany broadening + auto-tag bypass + dedup race fix + Bridge PII audit + skill refresh)
status: COMPLETED
plan_version: 1.0
created_date: 2026-05-22
last_amended_date: null
completed_date: 2026-05-25
canonical_scope: none
canonical_scope_rationale: |
  Google Apps Script patch (v3.9 → v3.10) + Google Sheets schema/data work +
  upstream-source wiring (Procurement App, FPM, opening-balance files) +
  Bridge PII audit (read-only) + /finance-ap skill updates. No Frappe
  tabCompany / tabWarehouse / tabCustomer / tabSupplier mutations. No
  hrms/api/* files touched. Affiliate-entity expansion (14 non-Bebang
  brands) operates on PAYEE strings in Google Sheets, not on Frappe Customer
  records.

audit_status: null
audit_reference: null

branch_name: s256-ap-source-redesign
worktree: F:/Dropbox/Projects/BEI-ERP-s256-ap-source-redesign
repos_touched:
  - hrms (only for: `scripts/google_apps/s256_ap_view_hourly_sync_v310.gs`; `.claude/skills/finance-ap/*` skill updates; this plan + `SPRINT_REGISTRY.md`)

depends_on:
  - S255 PR #760 MERGED 2026-05-20T01:15:03Z (Apps Script v3.9 live, versionNumber=16)
  - Apps Script project `1pE8wt_z8NA9q__PNbUilJ72UE0_EI3DmurJekkw6mbgtHr8hosnKsNRF`, deployment `AKfycbw-AuqJq6OyMV6DGarGWEruDoez04OETlWFQoeppNjvzoeSOJOomPOZNsVPE9iuV6ZC_Q`, web app token `bei-ap-sync-2026-04`, current version 16 (v3.9)
  - S255 closeout execution 2026-05-22 (`tmp/s255_followup/CLOSEOUT_EXECUTION_2026-05-22.md`) — Denise PP ACL trimmed, 5 intercompany rows moved, 24 bypass-supplier rows retagged, 3 cross-source dupes deleted, Bridge readers granted on 5 upstream sheets

evidence_committed:
  - output/s256/SUMMARY.md
  - output/s256/DEFECTS.md
  - output/s256/S256_SURFACE_OWNERSHIP_MATRIX.csv
  - output/s256/baseline_state.json
  - output/s256/script_source_backup_v39.gs
  - output/s256/phase1_source_investigation.json
  - output/s256/v310_dryrun.json
  - output/s256/v310_dryrun_verify.json
  - output/s256/v310_deployment.json
  - output/s256/intercompany_affiliate_migration_log.json
  - output/s256/auto_tag_bypass_log.json
  - output/s256/dedup_race_fix_log.json
  - output/s256/source_redesign_log.json
  - output/s256/bridge_pii_audit.json
  - output/s256/cloud_scheduler_pause_log.json
  - output/s256/post_deploy_sync.json
  - output/s256/post_deploy_verify.json
  - output/s256/rollback_runbook.md
  - output/s256/phase{0..9}_checklist.md
  - output/s256/verify_phase{0..9}.py
  - output/s256/closeout_state.json
  - output/s256/pr.json

evidence_transient:
  - tmp/s256/dry_run_*.json
  - tmp/s256/probe_*.json
  - tmp/s256/grep_*.txt
  - tmp/s256/traceback_*.txt

execution_summary: |
  v3.10 deployed as version 17 on 2026-05-25. Procurement App seed WORKING (138 new rows).
  Intercompany broadened to 14 affiliates. 94 bypass-supplier rows retagged. FPM-SOA dedup active.
  Bridge PII audit: clean (no employee PII). Training doc + skill refreshed.
  2 non-blocking defects deferred (HO opening header detection, FPM-side auto-tag).
  Cloud Scheduler paused ~75 min, resumed.
---

# Sprint S256 — AP Master v3.10 + Source-of-Truth Redesign

## TL;DR for cold-start agents

You are executing Denise Marielle Almario's (Finance Supervisor) signed S255 closeout directives, dated 2026-05-21 (Documenso Sig `CMPF8QBLQ03LTMT1WTAUO7ISY`). The signed PDF lives at `F:\Downloads\2026-05-20 - S255 Closeout Questionnaire for Finance and Accounting v2 with Answer_signed.pdf`. **Sam approved every "Yes" in Section E** (Bridge access) and the source-redesign directive in Section D2. **Ignore the fact that James Tamaca did not countersign** — Denise is the sheet owner + Finance Lead and her answers are authoritative.

S255 already executed the data ops that did NOT need code (ACL removals, 5-row intercompany migration, 24-row 3M Dragon/Suzuyo retag, 3 cross-source dupes deleted, Bridge readers granted on 5 upstream sheets). See `tmp/s255_followup/CLOSEOUT_EXECUTION_2026-05-22.md`. S256 ships the code changes and policy work that S255 deferred.

Five things land in S256:

1. **v3.10 — broaden intercompany predicate to 14 non-Bebang affiliate entities** (Section B addendum). One-time migration of any HO rows matching the broadened set.
2. **v3.10 — auto-tag 3PL bypass suppliers** at FPM/Denise seed time (Section C2: 3MD Logistics, Pinnacle, Royal Cold Storage, Fourkoolitz, Suzuyo). Going forward, any Denise PP row matching one of these payees gets `SOURCE='Denise PP - Manual'` automatically.
3. **v3.10 — FPM-SOA-aware dedup fix** so the Denise PP seed recognises FPM-SOA-sourced rows as "already there" and stops re-adding XYZCO row 1196 every cycle.
4. **Source-of-truth redesign per Denise's D2 directive** (HIGHEST RISK — Phase 1 INVESTIGATION GATE):
   - Suppliers SOA: source = Procurement App; opening balances from Denise PP
   - Head Office: source = RFP App (FPM); opening balances from `05 - AP Opening Balance Head Office`
   - CAPEX: opening from CAPEX file; current from RFP App
   - If Phase 1 investigation finds Procurement App or `05 - AP Opening Balance HO` does not exist OR is incomplete, sub-phases 4a/4b/4c **defer to S257** and the v3.10 patches (#1, #2, #3) still ship.
5. **Bridge PII audit on 5 newly-granted sheets** (FPM, Compliance App, Bank Balances LIVE, Cashflow Tracker - CEO, PCM) — per Denise E2: "Bridge should NEVER see Personal Info, Salary details." Scan each sheet for hidden salary/personal-info tabs or cells. If found: restrict.

Plus housekeeping: `/finance-ap` team-training doc gets "S255 deployed" + "S256 in flight" entries, lock-verification count bumped from 90/90 → 96/96, Joevic role confirmed (handles Supplier Payments per Denise A1).

## Sources of authority (Ground-Truth Lock)

### Evidence sources

| Source | What it proves | Path |
|---|---|---|
| Denise's signed PDF (Documenso Sig `CMPF8QBLQ03LTMT1WTAUO7ISY`) | Every actionable directive in this plan | `F:\Downloads\2026-05-20 - S255 Closeout Questionnaire for Finance and Accounting v2 with Answer_signed.pdf` |
| S255 closeout execution log | What was already done 2026-05-22; baseline state for S256 | `tmp/s255_followup/CLOSEOUT_EXECUTION_2026-05-22.md` |
| S255 closeout execution JSON log | Per-op data including row IDs touched | `tmp/s255_followup/closeout_execution_log.json` |
| S255 P9b post-deploy verify | v3.9 production live since 2026-05-20 | `output/s255/post_deploy_verify.json` (origin/production) |
| Apps Script v3.9 source | Current production code as basis for v3.10 | `scripts/google_apps/s255_ap_view_hourly_sync_v39.gs` (origin/production) |
| Fact-check result 2026-05-22 | Current Suzuyo (50 rows, 18 Denise-PP-sourced), Coolitz (19 archive), Pinnacle/Royal Cold Storage/Fourkoolitz (0 rows), 3 cross-source dupes (now 0 after S255 closeout) | `tmp/s255_followup/fact_check_result.json` (regenerated at Phase 0) |

### Count method

- **v3.9 source line numbers** are validated against the file in the worktree at `scripts/google_apps/s255_ap_view_hourly_sync_v39.gs`. Phase 0 reads the file and confirms `function recomputeBanners_`, `existingIndex`, and `seedFromDenisePaymentPlan_` exist. If any anchor changed since 2026-05-20, the plan stops and re-baselines.
- **Existing intercompany rows** counted via Sheets API `'Intercompany'!A18:A` length (post-S255: ~336 rows).
- **PAYEE matches** for affiliate broadening: predicate eval'd Python-side against live HO data; expected match count published to `phase3_log.json` for human review BEFORE migration.
- **Bridge PII findings** counted per (sheet, tab, cell) tuple; published to `bridge_pii_audit.json`.

### Authoritative sections

Phases 0–9 below are authoritative. Amendments must update phase bodies in the same edit.

### Unresolved-value policy

- **Procurement App sheet ID** is `[UNVERIFIED — requires resolution at Phase 1]`. If it does not exist, sub-phase 4a defers to S257.
- **`05 - AP Opening Balance Head Office`** file path is `[UNVERIFIED — requires resolution at Phase 1]`. If it does not exist, sub-phase 4c defers to S257.
- **Affiliate-entity exact PAYEE spelling variants** (e.g., `B CUBED VENTURES CORP` vs `B Cubed Ventures Corp`) are `[UNVERIFIED — read live data at Phase 3.1]`.

## Worktree boot

Spawn at `F:/Dropbox/Projects/BEI-ERP-s256-ap-source-redesign` from `origin/production`. Closeout removes it.

```bash
cd F:/Dropbox/Projects/BEI-ERP && git fetch origin --prune
git worktree add F:/Dropbox/Projects/BEI-ERP-s256-ap-source-redesign -B s256-ap-source-redesign origin/production
cd F:/Dropbox/Projects/BEI-ERP-s256-ap-source-redesign
mkdir -p output/s256 tmp/s256
```

The worktree was already spawned at plan-writing time (2026-05-22). Re-use it for execution.

## Design Rationale (for cold-start agents)

### Why this exists

S255 closeout (2026-05-22) executed Denise's data-only directives. Three categories of work remained, each requiring code or research:

1. **v3.10 patches:** broaden the intercompany routing predicate (Denise's Section B free-text added 14 non-Bebang affiliate entities); auto-tag bypass 3PL suppliers at seed time (Denise C2); fix the dedup race where Denise PP seed re-adds XYZCO row 1196 every cycle (S255 P4 deleted it; S255 P9b verified one row re-appeared after deploy; today's closeout re-deleted it again).
2. **Source-of-truth redesign per Denise D2:** restructure the seed so Suppliers SOA is fed by the Procurement App (new upstream), Head Office is fed by FPM with opening balances from a `05 - AP Opening Balance Head Office` file, and CAPEX uses its own legacy file for opening balances. Denise PP becomes opening-balance-only — the continuous mirror via `payment_plan_mirror_disabled` flag (already in v3.9) gets flipped to `true` once new sources are wired.
3. **Bridge PII audit:** Sam approved Bridge view-access on FPM + Compliance + Bank Balances + Cashflow + PCM per Denise E. Denise E2 specified: never expose Personal Info / Salary. Audit each sheet for hidden tabs / cells containing salary or PII; if found, restrict.

### Why this architecture

**Alternatives considered for source-of-truth redesign:**

| Option | Why rejected / chosen |
|---|---|
| Keep Denise PP as continuous mirror; layer Procurement App on top | Rejected — Denise's directive is explicit: "the current transactions will be coming from the Procurement App". Denise PP becomes opening-balance-only. Two continuous sources would re-introduce dupes. |
| Build a separate "Procurement App seed" function from scratch | Rejected — `seedNewInvoicesFromFPM_` is already battle-tested. Mirror its pattern. |
| **CHOSEN:** Add `seedFromProcurementApp_()` mirroring the FPM seed shape; treat Denise PP as one-time opening-balance import via existing `seedFromDenisePaymentPlan_` then disable | Reuses existing dedup logic (`invNoVariants_`, `existingIndex`). One new seed function. Denise PP flip via existing `payment_plan_mirror_disabled` flag. |

**Alternatives considered for affiliate broadening:**

| Option | Why rejected / chosen |
|---|---|
| Loose regex `/Bebang|B Cubed|BB Estancia|BEIFranchise|.../i` | Rejected — risks false positives on similarly-named non-affiliate payees. |
| Maintain an explicit affiliate list in code (alongside the existing `Bebang Enterprise/Kitchen/Shaw Inc` set) | **CHOSEN.** Explicit allowlist. Future affiliates added one PR at a time, each Sam-approved. |
| Move affiliates into a Sheet that script reads at runtime | Rejected — adds runtime dependency; complicates rollback. Stick with const array in code. |

**Alternatives considered for dedup race fix:**

| Option | Why rejected / chosen |
|---|---|
| Tombstone deleted rows in a `_deleted` tab; seed checks tombstone first | Rejected — adds new tab + new dedup path; over-engineered. |
| Periodic manual dedup sweep | Rejected — Sam already runs this monthly via S255 P4-style scripts; we want zero-touch. |
| **CHOSEN:** Broaden `seedFromDenisePaymentPlan_` dedup to recognise FPM-SOA rows as "same supplier+invoice+amount already in AP Master" | One-line addition to the existing `invNoVariants_` dedup loop: include the row's SOURCE in the existingIndex key OR add a parallel `FB|payeeKey|amt` index entry for FPM-SOA rows that the Denise seed also consults. |

### Key trade-off decisions

| Decision | Choice | Reason |
|---|---|---|
| Investigation Gate at Phase 1 | If Procurement App or `05 - AP Opening Balance HO` missing → defer 4a/4b/4c to S257; ship v3.10 patches anyway | Don't block intercompany/auto-tag/dedup fixes on file-locating work that may take days |
| New Denise PP rows after source redesign | Stop seeding new Denise PP rows into AP Master once Procurement App is wired (mirror disabled, no new seed) | Denise's directive is "Denise PP = opening balances only". Once Procurement App is live, Denise's standalone sheet becomes archival |
| Bridge PII restriction mechanism | Per-tab protectedRange (warningOnly=false, editors=owner only) — hides salary/PII tabs from Bridge readers without removing them from sheet | Simpler than moving data; reversible |
| 3PL auto-tag detection at seed time | PAYEE regex match in `seedFromDenisePaymentPlan_` before SOURCE is assigned | One pattern check per row; minimal overhead |
| v3.10 numbering | `s256_ap_view_hourly_sync_v310.gs` (new file, save as) | Keep v3.9 backup intact for rollback; consistent with S255 v3.9 naming |

### Known limitations and mitigations

| Limitation | Mitigation |
|---|---|
| Procurement App schema unknown until Phase 1 investigation | Phase 1 reads the sheet structure, documents it, then sub-phase 4a maps fields to AP Master cols. If schema is too different from FPM, defer to S257 with proper schema-mapping sprint. |
| Affiliate PAYEE strings may have spelling variants in HO data | Phase 3.1 reads ALL HO rows, finds PAYEEs matching each of the 14 affiliates (case-insensitive, fuzzy), produces a `phase3_payee_audit.json` for Sam to confirm before migration |
| Bridge PII audit can't read tabs Bridge already can't see | Use impersonation of the sheet owner (Denise/Sam/Mae) to enumerate ALL tabs + ALL cells. Cross-check what Bridge would see. |
| Dedup race fix may inadvertently prevent legitimate new Denise PP entries | Test: before flipping fix, run dry-run and verify same-row-as-FPM-SOA gets skipped while a brand-new Denise PP entry still seeds |
| Cloud Scheduler runs at xx:00 PHT; destructive phases need pause window | Pause at Phase 0.5, resume at Phase 9b.5 (mirror S255 P0/P9b pattern) |

### Source references

- `scripts/google_apps/s255_ap_view_hourly_sync_v39.gs` — current production source (v3.9, 95K bytes, versionNumber=16)
- `output/s255/SUMMARY.md` — full S255 outcome
- `tmp/s255_followup/CLOSEOUT_EXECUTION_2026-05-22.md` — yesterday's data-op closeout
- `tmp/s255_followup/fact_check_result.json` — current state of bypass suppliers + intercompany rows
- `.claude/skills/finance-ap/SKILL.md` — operational skill (verify intact at Phase 0)
- `.claude/skills/finance-ap/references/team-training-2026-05-14.md` — training doc to refresh

## Requirements Regression Checklist

Verify these BEFORE writing code. Each is a yes/no assertion the executing agent checks.

- [ ] Is `/finance-ap` skill present in all 3 mirrors (`.claude/skills/`, `.agent/skills/`, `.agents/skills/`) and intact post-S255? (verify at Phase 0)
- [ ] Does v3.10 keep all v3.9 functions intact (recomputeBanners_, mirrorDenisePaymentPlanTab_, seedFromDenisePaymentPlan_, seedNewInvoicesFromFPM_, payment_plan_mirror_disabled flag)?
- [ ] Is the broadened intercompany predicate **PAYEE allowlist + Bebang-prefix OR**, NOT a loose regex that could false-positive?
- [ ] Does the broadened predicate still preserve the negative govt-keyword filter (HDMF/SSS/PHIC/etc.)?
- [ ] Are all 14 affiliate entity names spelled EXACTLY as Denise wrote them in her PDF (Section B free-text)?
- [ ] Does auto-tag 3PL detection trigger BEFORE sourceTag is finalised (so `Denise PP - Manual` wins over `Denise PP - Masterlist`)?
- [ ] Does auto-tag detection use case-insensitive PAYEE contains, with anchors to avoid false matches (e.g., `Suzuyo Whitelands Logistics` matches Suzuyo, but a payee literally named "Suzu Yo Catering" must NOT match)?
- [ ] Does the FPM-SOA-aware dedup recognise `SOURCE='FPM-SOA'` rows as authoritative matches for Denise PP dedup, preventing re-seed?
- [ ] **Investigation Gate:** If Procurement App sheet ID is unverified at end of Phase 1, do sub-phases 4a/4b/4c defer to S257?
- [ ] **Investigation Gate:** If `05 - AP Opening Balance Head Office` file is missing/incomplete at end of Phase 1, does sub-phase 4c defer to S257?
- [ ] Does the source-of-truth redesign FLIP `payment_plan_mirror_disabled` to `true` only AFTER Procurement App is wired and verified producing rows?
- [ ] Does Bridge PII audit cover ALL tabs (including hidden ones) on each of the 5 sheets?
- [ ] Does the PII restriction mechanism (protectedRange on offending tab) leave Bridge as reader on the rest of the sheet?
- [ ] Does the `/finance-ap` team-training doc bump count from "90/90 lock checks" to "96/96"?
- [ ] Does the training doc add Joevic Almajar to the per-role section (he handles Supplier Payments per Denise A1)?
- [ ] **PR-Handoff:** does the closeout phase create a PR and STOP, leaving Sam to merge?
- [ ] **Cloud Scheduler:** does Phase 0.5 PAUSE and Phase 9b.5 RESUME the trigger, with both timestamps logged?

## Phase Budget Contract

| Phase | Description | Estimated units |
|---|---|---:|
| Phase 0 | Boot + baseline + Cloud Scheduler pause + v3.9 backup | 5 |
| Phase 1 | **INVESTIGATION GATE** — locate Procurement App + `05 - AP Opening Balance HO` + read schemas | 6 |
| Phase 2 | v3.10 patch — broaden intercompany predicate + dedup race fix | 8 |
| Phase 3 | One-time migration: affiliate-matching HO rows → Intercompany | 5 |
| Phase 4a | Source redesign — Procurement App SOA seed function (IF Phase 1 OK) | 9 |
| Phase 4b | Source redesign — Denise PP → opening-balance-only (mirror disable runbook) | 5 |
| Phase 4c | Source redesign — `05 - AP Opening Balance HO` wiring (IF Phase 1 OK) | 5 |
| Phase 5 | Auto-tag 3PL bypass suppliers at seed time | 4 |
| Phase 6 | Bridge PII audit on 5 sheets + restrictions if needed | 6 |
| Phase 7 | /finance-ap team-training refresh + Joevic addition + lock count bump | 4 |
| Phase 8 | Dry-run gate + promote v3.10 + resume scheduler + trigger live sync | 7 |
| Phase 9 | Post-deploy verification + SUMMARY + DEFECTS + PR + closeout | 8 |
| **Total** | | **72 units** |

- Hard limit: 80 (within budget; 72 leaves 8 units of headroom for amendments)
- Preferred split threshold: 12 per phase (max here is 9 in Phase 4a — under threshold)
- Phase 4 is split into 4a/4b/4c because the three sub-tasks are independent and the gate at Phase 1 may defer 4a + 4c without affecting 4b
- Single-session executability: 72 units is feasible in one session but the agent should commit after each phase so compaction can recover

## Worktree boot + Anti-Rewind / Concurrent-Run Protection

### Ownership matrix

| Surface | Owner | Notes |
|---|---|---|
| Apps Script project `1pE8wt_z8NA9q__PNbUilJ72UE0_EI3DmurJekkw6mbgtHr8hosnKsNRF` HEAD | S256 | No other sprint touches the script until closeout |
| `scripts/google_apps/s256_ap_view_hourly_sync_v310.gs` (NEW file) | S256 | Save-as from v3.9; don't overwrite v3.9 source |
| AP Master entry tabs (SOA / HO / CAPEX / Payment Plan / Intercompany) | Script-writes + S256 one-time structural changes only | Cloud Scheduler PAUSED at Phase 0.5 |
| AP Master `Intercompany` tab — new affiliate rows | S256 (Phase 3 migration) | append + delete pattern, highest-row-first |
| Procurement App sheet (TBD ID) | Read-only at Phase 1; Phase 4a wires seed | No writes |
| FPM | Read-only (existing seed source) | No writes |
| `05 - AP Opening Balance Head Office` file (TBD path) | Read-only at Phase 4c | No writes |
| `/finance-ap` skill (3 mirrors) | S256 — Phase 7 refresh | Sync to .claude/, .agent/, .agents/ |
| 5 upstream sheets (FPM, Compliance, Bank, Cashflow, PCM) | Read-only at Phase 6 audit; Bridge restriction protectedRange if PII found | No data writes |

### Protected surfaces

These must NOT regress:

- 16 strict-locked tabs on AP Master (all status-sync continues; Intercompany was added in S255)
- Payment Plan tab strict-lock (still sam@ only during mirror phase; if Phase 4b flips mirror, lock policy unchanged)
- Mirror function running hourly (until Phase 4b flips flag — only after Procurement App is verified live)
- Denise PP seed running hourly (until Phase 4b flips it to opening-balance-only)
- FPM-only status sync to entry tabs running hourly
- Tax sync Compliance → entry tabs running hourly
- Banner recompute every cycle (v3.9 `recomputeBanners_`)
- 96/96 lock-check matrix (post-S255)

Verification: each Phase X verify script asserts at least one protected surface continues to function (e.g., status_sync.tabs_seen has 4 tabs, `_sync_log_v3` has new entries this cycle).

### Remote-truth baseline

Capture at Phase 0:
- Origin/production SHA: `git rev-parse origin/production` → `output/s256/baseline_sha.txt`
- Apps Script version: 16 (v3.9) on deployment `AKfycbw-AuqJq6OyMV6DGarGWEruDoez04OETlWFQoeppNjvzoeSOJOomPOZNsVPE9iuV6ZC_Q`
- Apps Script source size: ~95K chars (v3.9)
- AP Master grid sizes + tab list snapshot to `output/s256/baseline_state.json`
- Denise PP grid sizes + 7-day editor list snapshot
- 5 upstream sheet ACLs snapshot (verify Bridge present per S255 closeout grants)

### Pre-touch backup

Phase 0.4 saves a copy of current v3.9 source to `output/s256/script_source_backup_v39.gs` (committed evidence — survives worktree closeout). This is the rollback target.

### Concurrent-run protection (per S255 precedent)

The chosen lock primitive is **Cloud Scheduler pause** (no LockService in source; v3.10 does not add one):
- Phase 0.5 pauses `ap-auto-view-hourly-refresh` via `gcloud scheduler jobs pause`
- All destructive operations (Phase 2 source edits ARE non-destructive, but Phase 3 row migration IS destructive, Phase 4a/4b/4c live-data ops ARE destructive) run without race risk
- Phase 8.5 resumes the trigger AFTER v3.10 is verified working
- Rollback Runbook (below) re-pauses if needed

## Zero-Skip Enforcement

Every task has a MUST_MODIFY or MUST_CONTAIN assertion or a verification script step. Phase gate is a Python script.

**Forbidden agent behaviors:**

- Marking partial work as DONE
- Replacing a task with a simpler version without Sam approval
- "Deferred to S257" without writing the deferral reason in `output/s256/DEFECTS.md` AND obtaining Sam-acknowledged blocker confirmation
- Self-grading via prose instead of filesystem evidence
- Silently retrying deploy on failure — STOP and present error

### Phase completion checklist

After each phase, write `output/s256/phase{N}_checklist.md` with the format:

| Task | Status | Evidence | Skipped? | If skipped, why? |
|---|---|---|---|---|
| 1.1 | DONE | `output/s256/phase1_source_investigation.json` shows `procurement_app_id` non-null | NO | n/a |
| ... | | | | |

Plus per-phase verify script (`verify_phase{N}.py`) that asserts machine-readable evidence — never the agent's prose.

## Status Reconciliation Contract

When status / counts / blockers change, update in the same work unit:

1. `output/s256/SUMMARY.md`
2. `output/s256/closeout_state.json`
3. This plan's YAML `status` field
4. `docs/plans/SPRINT_REGISTRY.md` S256 row

## Signoff Model

- **Mode:** single-owner
- **Approver of record:** Sam Karazi (CEO)
- **Signoff artifact:** `output/s256/closeout_state.json` with `signed_off_by: "sam@bebang.ph"` + ISO timestamp
- **Note:** CFO seat vacant per `memory/finance-team-2026-04-15.md`; Bridge fractional CFO advises but does NOT approve. Denise countersigns operational changes within her sheet (already done via the signed PDF).

## Autonomous Execution Contract

### Completion condition

This sprint is COMPLETE when ALL of:

- [ ] Phases 0–9 all `status=DONE` (or Phase 4a/4c marked DEFERRED with Sam-acknowledged Investigation Gate reason in DEFECTS.md)
- [ ] Cloud Scheduler paused at Phase 0.5 AND resumed at Phase 8.5 (both timestamps logged)
- [ ] `output/s256/v310_dryrun_verify.json` shows `all_assertions_passed: true`
- [ ] `output/s256/v310_deployment.json` shows `versionNumber: 17` (v3.10 promoted)
- [ ] `output/s256/post_deploy_verify.json` shows all 5 assertions PASS
- [ ] v3.10 source has 14-affiliate intercompany predicate (verified via grep for at least 5 of the 14 entity names)
- [ ] v3.10 source has `seedFromProcurementApp_` function OR a DEFERRED note in DEFECTS.md
- [ ] v3.10 source has `payment_plan_mirror_disabled` flag handling (either still `false` or flipped to `true` if Procurement App live)
- [ ] v3.10 source has 3PL bypass auto-tag predicate (matches PAYEE for 3MD/Pinnacle/Royal Cold Storage/Fourkoolitz/Suzuyo)
- [ ] v3.10 source has FPM-SOA-aware dedup (Denise seed `existingIndex` lookup includes FPM-SOA-sourced entries)
- [ ] Affiliate migration log shows N_migrated >= 0 (zero is acceptable — means no affiliate rows currently in HO)
- [ ] Auto-tag log shows historical retag count for any present-day bypass-supplier rows newly classified
- [ ] Bridge PII audit run on 5 sheets; if findings exist, restrictions applied (protectedRange on offending tabs)
- [ ] `/finance-ap` team-training doc updated (3 mirrors, sha256 match) with: S255 deployed entry, S256 in-flight entry, lock count 96/96, Joevic in per-role section
- [ ] PR created on `s256-ap-source-redesign` branch, Sam stops short of merge per PR-Handoff
- [ ] `docs/plans/SPRINT_REGISTRY.md` S256 row → `COMPLETED`
- [ ] This plan's YAML → `status: COMPLETED`, `completed_date: 2026-05-XX`

### Stop-only-for

- Missing credentials / access (e.g., Procurement App sheet ID not findable, file owners not impersonatable)
- Destructive approval (Phase 4b mirror flip — Sam-approved go-live only after Phase 4a Procurement App seed verified producing > 0 rows in dry-run)
- Genuine business-policy decision (e.g., Bridge PII finding requires Sam decision — restrict vs leave)
- Direct conflict with unrelated in-flight changes (someone else patches the script mid-sprint)

### Continue without pause through

- Phase 0 → 1 → 2 → 3 → (5 if 4 deferred, else 4a → 4b → 4c → 5) → 6 → 7 → 8 → 9

If Phase 1 investigation defers 4a/4b/4c, the agent skips those phases and continues straight to Phase 5 (auto-tag) and onward. DEFECTS.md captures the deferral.

### Blocker policy

| Class | Response |
|---|---|
| Programmatic (script error) | Fix and continue |
| Evidence mismatch (Procurement App schema unexpected) | Re-investigate at Phase 1, normalise plan, continue with reduced scope |
| 3× failure | Grounded research (read GAS API docs, traceback files), then continue |
| Business-data/policy (Bridge PII restriction needs Sam approval) | Write finding to DEFECTS.md, propose restriction, pause for Sam |
| Active-run conflict (someone patched script mid-sprint) | Pause, present diff, ask Sam |

### Canonical closeout artifacts

- `output/s256/SUMMARY.md`
- `output/s256/DEFECTS.md`
- `output/s256/S256_SURFACE_OWNERSHIP_MATRIX.csv`
- `output/s256/v310_deployment.json`
- `output/s256/baseline_state.json`
- `output/s256/phase1_source_investigation.json`
- `output/s256/intercompany_affiliate_migration_log.json`
- `output/s256/auto_tag_bypass_log.json`
- `output/s256/dedup_race_fix_log.json`
- `output/s256/source_redesign_log.json` (or `source_redesign_deferred.json` if Phase 1 gate failed)
- `output/s256/bridge_pii_audit.json`
- `output/s256/cloud_scheduler_pause_log.json`
- `output/s256/post_deploy_sync.json`
- `output/s256/post_deploy_verify.json`
- `output/s256/rollback_runbook.md`
- `output/s256/phase0_checklist.md` through `output/s256/phase9_checklist.md`
- `output/s256/closeout_state.json`
- `docs/plans/2026-05-22-sprint-256-ap-source-redesign.md` (this file, YAML updated)
- `docs/plans/SPRINT_REGISTRY.md` (S256 row updated)
- `scripts/google_apps/s256_ap_view_hourly_sync_v310.gs` (the v3.10 script source)
- `.claude/skills/finance-ap/SKILL.md` + references (3 mirrors)

## Phase 0 — Boot + baseline

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 0.1 | Read this plan + 4 related references: (a) S255 closeout `tmp/s255_followup/CLOSEOUT_EXECUTION_2026-05-22.md`, (b) v3.9 source `scripts/google_apps/s255_ap_view_hourly_sync_v39.gs`, (c) `/finance-ap` SKILL.md, (d) Denise's signed PDF | none |
| 0.2 | `git fetch origin --prune` then verify worktree at `F:/Dropbox/Projects/BEI-ERP-s256-ap-source-redesign` is on `s256-ap-source-redesign` branch tracking origin/production | MUST_CONTAIN: HEAD = origin/production SHA at plan write time |
| 0.3 | Record remote-truth baseline (`git rev-parse origin/production` → `output/s256/baseline_sha.txt`) | MUST_CONTAIN: SHA non-empty |
| 0.4 | Backup current Apps Script v3.9 source → `output/s256/script_source_backup_v39.gs` (committed evidence — survives worktree closeout) | MUST_CONTAIN: file size in `[90000, 105000]` bytes |
| 0.5 | **PAUSE Cloud Scheduler trigger** (per Blocker 6 precedent from S255): `gcloud scheduler jobs pause ap-auto-view-hourly-refresh --project=quiet-walker-475722-s2 --location=asia-southeast1`. Log to `output/s256/cloud_scheduler_pause_log.json` with `{paused_at, job_name, original_state, current_state}` | MUST_CONTAIN: `paused: true` in log |
| 0.6 | Snapshot AP Master grid sizes per tab → `output/s256/baseline_state.json` | MUST_CONTAIN: keys for all 19 tabs (post-S255 incl. Intercompany) |
| 0.7 | Snapshot Denise PP sheet grid + 7-day editor list → `output/s256/denise_pp_baseline.json`; verify post-S255 ACL state (Bea/Liezel/Maika removed, Bridge users present) | MUST_CONTAIN: `denise_pp_acl_count >= 16` AND `bridge_user_count >= 1` |
| 0.8 | Snapshot 5 upstream sheet ACLs (FPM, Compliance, Bank Balances, Cashflow, PCM) → `output/s256/upstream_acl_baseline.json`; verify Bridge readers present (S255 closeout grants) | MUST_CONTAIN: each sheet has at least 1 bridge-ph.com entry |
| 0.9 | Verify `/finance-ap` skill present + intact in all 3 mirrors | MUST_CONTAIN: grep "Bridge" returns ≥ 5 hits in each SKILL.md across 3 mirrors |
| 0.10 | Write `output/s256/S256_SURFACE_OWNERSHIP_MATRIX.csv` | MUST_CONTAIN: ≥ 10 rows |
| 0.11 | Write `output/s256/verify_phase0.py` | exit 0 |

**Phase 0 gate:** `python output/s256/verify_phase0.py` exits 0 AND scheduler shows PAUSED.

## Phase 1 — INVESTIGATION GATE — locate Procurement App + `05 - AP Opening Balance HO`

This phase determines whether the source-of-truth redesign sub-phases (4a/4b/4c) ship in S256 or defer to S257. The v3.10 patches (intercompany broadening, auto-tag, dedup race fix) ship regardless.

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 1.1 | **Locate Procurement App sheet:** search Google Drive (via Drive API search impersonating Sam) for files with name containing "Procurement App", "Procurement AppSheet", "BEI Procurement", or "RFP App". Check both `My Drive` and `Shared with me`. Document each candidate (sheet ID, owner, last modified, current tab list). | MUST_CONTAIN in `output/s256/phase1_source_investigation.json`: `procurement_app_candidates: [{sheet_id, name, owner_email, last_modified, tab_list}, ...]` |
| 1.2 | For each Procurement App candidate, read tab structure. Identify which tab contains the supplier-invoice register. Document: row count, header schema (col names + types), data freshness (most recent entry date) | MUST_CONTAIN: `procurement_app_chosen` field with sheet_id, tab_name, schema_mapping (header → AP Master col) OR `procurement_app_chosen: null` + reason |
| 1.3 | **Locate `05 - AP Opening Balance Head Office` file:** Drive API search for files named "05 - AP Opening Balance Head Office", "AP Opening Balance Head Office", "Head Office Opening Balance", etc. Read structure. | MUST_CONTAIN: `ho_opening_balance_chosen` field with file_id, schema OR null + reason |
| 1.4 | **Locate `CAPEX File` for Phase 4c:** Drive API search for the legacy CAPEX archive file (Denise's directive: "for the CAPEX, beginning is the CAPEX File"). The existing seed already reads from `CAPEX` tab on AP Master; the legacy "CAPEX File" may be a separate archive workbook. | MUST_CONTAIN: `capex_legacy_file` field with file_id + reason if found OR null + note that current CAPEX tab on AP Master serves as opening-balance source |
| 1.5 | **DECIDE GATE:** if `procurement_app_chosen != null` AND `ho_opening_balance_chosen != null` → set `proceed_with_source_redesign: true` in JSON; else → set `proceed_with_source_redesign: false` and write Sam-readable summary of what's missing to `output/s256/source_redesign_deferred.md` | MUST_CONTAIN: `proceed_with_source_redesign` boolean |
| 1.6 | Write `output/s256/verify_phase1.py` | exit 0 |

**Phase 1 gate:** `output/s256/phase1_source_investigation.json` has the decision boolean populated. If FALSE, sub-phases 4a/4b/4c are SKIPPED with DEFECTS.md entry; agent proceeds to Phase 2 then jumps directly to Phase 5.

## Phase 2 — v3.10 patches: broaden intercompany + dedup race fix

Build v3.10 source from v3.9 by extending the intercompany predicate and fixing the Denise PP seed dedup.

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 2.1 | Build v3.10 source: copy `scripts/google_apps/s255_ap_view_hourly_sync_v39.gs` → `scripts/google_apps/s256_ap_view_hourly_sync_v310.gs` | MUST_CONTAIN: file exists; size in `[90000, 105000]` |
| 2.2 | **Broaden intercompany predicate** in v3.10 source's `seedNewInvoicesFromFPM_` routing block: change the Bebang-only regex to an allowlist of 14 affiliates PLUS Bebang Enterprise/Kitchen/Shaw. Source code shape: <br>```js<br>const INTERCO_AFFILIATE_PATTERNS = [/^Bebang\s+(Enterprise\|Kitchen\|Shaw)\s+Inc\.?/i, /^B\s*Cubed\s+Ventures\s+Corp/i, /^BB\s+Estancia\s+Food\s+Corp/i, /^BEIFranchise\s+Food\s+OPC/i, /^Day\s+Ones\s+Food\s+and\s+Drink\s+Establishments\s+Corp/i, /^DMD\s+Holdings\s+Inc/i, /^Halo[\s-]*Halo\s+Alabang\s+Town\s+Food\s+Corp/i, /^Halo[\s-]*Halo\s+Terminal\s+Food\s+Corp/i, /^HFFM\s+Solenad\s+Food\s+Services\s+Inc/i, /^JL\s+Trade\s+OPC\s+Perpetual\s+Food\s+Corp/i, /^Red\s+Taldawa\s+Foods\s+OPC/i, /^Resto\s+Tech\s+Inc/i, /^Sweet\s+Harmony\s+Food\s+Corp/i, /^Taj\s+Food\s+Corp/i, /^Tungsten\s+Capital\s+Holdings\s+OPC/i];<br>var isIntercompany = INTERCO_AFFILIATE_PATTERNS.some(rx => rx.test(payee)) && /(transfer (of )?fund\|cash sweep\|intercompany)/i.test(particulars) && !/HDMF\|SSS\|PHIC\|PHILHEALTH\|BIR\|PAG-?IBIG\|CONTRIBUTION\|RENTAL\|FINAL PAY/i.test(particulars);<br>``` | MUST_CONTAIN: at least 5 of the 14 affiliate entity names appear in v3.10 source (grep). MUST_CONTAIN: original Bebang Enterprise/Kitchen/Shaw pattern preserved as first entry. |
| 2.3 | **Fix dedup race** in v3.10's `seedFromDenisePaymentPlan_` function: in the existingIndex lookup loop (currently checks `payeeKey + '|' + invVariant + '|' + amt`), ALSO check whether the matched existing-row's SOURCE is `'FPM-SOA'` or `'Suppliers SOA'`. If yes, the Denise row is a duplicate of an FPM-derived row already in AP Master and MUST be skipped. Add `stats.skipped_existing_fpm_soa++` counter. | MUST_CONTAIN: in v3.10 source: `'FPM-SOA'` and `skipped_existing_fpm_soa` both present |
| 2.4 | Sanity-check: grep v3.10 source for `INTERCO_AFFILIATE_PATTERNS` AND `isIntercompany` AND `skipped_existing_fpm_soa` — all 3 must appear | MUST_CONTAIN: 3 patterns present in source |
| 2.5 | Write `output/s256/verify_phase2.py` | exit 0 |

## Phase 3 — One-time migration of affiliate-matching HO rows

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 3.1 | Read all Head Office tab rows; for each row, evaluate the broadened predicate (PAYEE matches one of the 14 affiliates AND CLASSIFICATION matches transfer-keyword AND NOT govt-keyword). Produce candidate list (sheet_row, payee, classification, amount, source). Write to `output/s256/phase3_affiliate_candidates.json`. | MUST_CONTAIN: candidates_count integer (could be 0) |
| 3.2 | Sam review gate (manual step or auto-proceed): if candidates_count > 10, write a one-liner Chat draft to `output/s256/sam_affiliate_review.md` so Sam can spot-check before mass migration. If candidates_count <= 10, log and proceed. | MUST_CONTAIN: file exists; status either "auto-proceeded" or "draft sent to Sam" |
| 3.3 | Migrate candidates: append rows to Intercompany tab (append at end, in batches of 20), then delete from HO (highest-row-first) | MUST_CONTAIN in `output/s256/intercompany_affiliate_migration_log.json`: `migrated_rows: N` (N ≥ 0) + sample of 5 migrated payees |
| 3.4 | Refresh banners via direct write (mirror S255 P3 pattern — Python parallel recompute) since v3.10 not yet deployed | MUST_CONTAIN in log: post-migration banner totals for HO + Intercompany |
| 3.5 | Write `output/s256/verify_phase3.py` | exit 0 |

## Phase 4a — Source redesign: Procurement App SOA seed (CONDITIONAL on Phase 1 gate)

Only execute if `proceed_with_source_redesign: true` in Phase 1.

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 4a.1 | Add `const PROCUREMENT_APP_ID = '<from Phase 1>'` constant to v3.10 source | MUST_CONTAIN: const in v3.10 |
| 4a.2 | Write `seedFromProcurementApp_(ss, fpmLookup, taxLookup, existingIndex, dryRun)` — mirror of `seedNewInvoicesFromFPM_` but reads from Procurement App. Header schema mapping from Phase 1.2 wired in. SOURCE tag = `'Procurement App'`. Skip rows already in `existingIndex` (FPM + Suppliers SOA + Denise PP + Intercompany — 4 tabs). | MUST_CONTAIN: `function seedFromProcurementApp_` + `'Procurement App'` SOURCE assignment + appendto-Suppliers-SOA |
| 4a.3 | Wire `seedFromProcurementApp_` into `doRefreshAllTabs_v3_` after the FPM seed and BEFORE the Denise PP seed: | MUST_CONTAIN in `doRefreshAllTabs_v3_`: `seedFromProcurementApp_(ss, ...)` call |
| 4a.4 | Add 'Procurement App' SOURCE to the existing 4-tab forEach loop for status sync (line 290 v3.9) — no, actually: SOURCE='Procurement App' rows land on Suppliers SOA, which is already in the 4-tab loop. No second forEach change needed. Verify in v3.10. | MUST_CONTAIN: no new forEach entry; existing 4-tab covers Procurement App-sourced rows |
| 4a.5 | Add `recomputeBanners_` no-op for new SOURCE (banner already iterates ALL rows; SOURCE doesn't affect totals). Verify in dry-run. | MUST_CONTAIN: dry-run output shows Procurement App rows counted in SOA banner total |
| 4a.6 | Write `output/s256/verify_phase4a.py` | exit 0 |

**Skip note (if Phase 1 gate failed):** write `output/s256/phase4a_deferred.md` with reason; Phase 4a artifacts replaced by `deferred_reason` field in `output/s256/source_redesign_log.json`.

## Phase 4b — Source redesign: Denise PP opening-balance-only (CONDITIONAL)

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 4b.1 | Document the cutover: when Procurement App seed produces > 0 new rows for N consecutive cycles (default N=3, ~3 hours), Sam may flip `payment_plan_mirror_disabled = true`. Cutover does NOT auto-trigger — Sam decides. | MUST_CONTAIN: `output/s256/payment_plan_mirror_cutover_v2_runbook.md` exists with the trigger condition + manual steps |
| 4b.2 | In `seedFromDenisePaymentPlan_`, add a flag check: if `denise_pp_seed_disabled = true` (new const), early-exit with stats `{seed_disabled: true}`. Default `denise_pp_seed_disabled = false`. | MUST_CONTAIN: const + early-exit in v3.10 |
| 4b.3 | Document in runbook: after S256 deploy with Procurement App live, AT LEAST 3 cycles of dual-source operation (FPM + Procurement App + Denise PP) MUST run cleanly before considering the Denise PP seed disable. Sam confirms via spot-check. | MUST_CONTAIN: cutover steps + verification criteria |
| 4b.4 | Write `output/s256/verify_phase4b.py` | exit 0 |

## Phase 4c — Source redesign: `05 - AP Opening Balance Head Office` wiring (CONDITIONAL)

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 4c.1 | Add `const HO_OPENING_BALANCE_ID = '<from Phase 1>'` constant | MUST_CONTAIN: const in v3.10 |
| 4c.2 | Implement `seedHoOpeningBalanceOnce_()` — one-shot function that runs only if `Head Office` tab data range row count < threshold (e.g., < 100). Reads `05 - AP Opening Balance Head Office` and appends rows to HO tab with `SOURCE='05 AP Opening Balance HO'`. Subsequent hourly cycles skip via existingIndex dedup. | MUST_CONTAIN: function exists in v3.10 + `SOURCE='05 AP Opening Balance HO'` literal |
| 4c.3 | Add idempotency guard: function checks for existence of `_opening_balance_loaded` flag tab in AP Master; if present, no-op. After first successful load, create the flag tab. | MUST_CONTAIN: flag-tab create logic in v3.10 |
| 4c.4 | Add 'CAPEX File' wiring (Denise's directive: "for the CAPEX, beginning is the CAPEX File"). If Phase 1.4 found a separate CAPEX file → write `seedCapexOpeningBalanceOnce_`. If not → log that current CAPEX tab is treated as opening-balance archive (no new seed needed) | MUST_CONTAIN: either CAPEX one-shot function OR a note in log explaining no-op |
| 4c.5 | Write `output/s256/verify_phase4c.py` | exit 0 |

## Phase 5 — Auto-tag 3PL bypass suppliers at seed time

This phase ships regardless of Phase 1 gate.

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 5.1 | Add `const BYPASS_3PL_PATTERNS = [/3M\s*Dragon\s+Logistics/i, /3MD\s+Logistics/i, /Pinnacle\s+Cold\s+Storage/i, /Royal\s+Cold\s+Storage/i, /Four\s*Coolitz/i, /Suzuyo\s+Whitelands\s+Logistics/i, /Suzuyo/i]` to v3.10 source | MUST_CONTAIN: const in v3.10 with at least 5 of the 7 listed patterns |
| 5.2 | In `seedFromDenisePaymentPlan_` row builder, BEFORE `sourceTag` is finalised, check if PAYEE matches any pattern in `BYPASS_3PL_PATTERNS`. If yes, override `sourceTag = 'Denise PP - Manual'`. This wins over `Denise PP - Masterlist`, `Denise PP - Disputed (Middleby)`, etc. The S255-introduced "Invoice No." prefix detection (manual flag) still runs but takes lower priority — explicit 3PL pattern wins. | MUST_CONTAIN: 3PL pattern check in v3.10 source AND comment explaining precedence |
| 5.3 | Optionally apply same auto-tag in `seedNewInvoicesFromFPM_` for FPM-sourced bypass-supplier rows (so FPM-side 3M Dragon entries also get `Denise PP - Manual` tagging if they appear) — defer this to S257 if it requires more design discussion; default: ONLY apply in Denise seed for now | MUST_CONTAIN: explicit comment in v3.10 about deferral decision (whichever chosen) |
| 5.4 | Backfill audit: re-run the Phase 5/6 detection from S255 closeout against current SOA + HO data. Compare to `tmp/s255_followup/closeout_execution_log.json` op3/op4 counts (3M Dragon 6, Suzuyo 18). If more rows appeared since S255 closeout, write a one-time retag plan to `output/s256/auto_tag_backfill_plan.json`. | MUST_CONTAIN: backfill count summary + delta vs S255 closeout |
| 5.5 | Execute backfill retag if delta > 0 (use batch update on Sheets API; mirror the S255 P5 / closeout pattern) | MUST_CONTAIN in `output/s256/auto_tag_bypass_log.json`: `historical_retagged_count: N` (N ≥ 0) |
| 5.6 | Write `output/s256/verify_phase5.py` | exit 0 |

## Phase 6 — Bridge PII audit on 5 upstream sheets

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 6.1 | For each of the 5 sheets (FPM, Compliance App, Bank Balances LIVE, Cashflow Tracker - CEO, PCM), impersonate the sheet OWNER (Denise / Sam / Mae per `tmp/s255_followup/execute_closeout_ops.py UPSTREAM_SHEETS` list). Enumerate ALL tabs including hidden ones. | MUST_CONTAIN: per-sheet tab inventory in `output/s256/bridge_pii_audit.json` |
| 6.2 | For each tab, scan header row (row 1) for keywords: `salary`, `compensation`, `monthly rate`, `daily rate`, `hourly rate`, `take home`, `net pay`, `gross pay`, `13th month`, `SSS#`, `PhilHealth#`, `HDMF#`, `TIN`, `personal`, `birthday`, `birthdate`, `address`, `phone`, `mobile`, `emergency contact`. Document all matches. | MUST_CONTAIN: per-tab keyword match list |
| 6.3 | For each tab that flagged a keyword, sample 10 random data rows to confirm the column actually contains PII (vs just a column named "address" that happens to be store addresses, etc.) | MUST_CONTAIN: per-flagged-tab `confirmed_pii: true|false` + sample evidence |
| 6.4 | Write findings to `output/s256/bridge_pii_audit.json` with: `flagged_tabs_count`, `confirmed_pii_tabs`, `recommendations` (one of: `restrict`, `move`, `leave`) | MUST_CONTAIN: structured findings |
| 6.5 | **Apply restrictions** (Sam pre-approval via Denise's signed E2: "Bridge should NEVER see Personal Info, Salary details"): for each confirmed-PII tab, add a `protectedRange` (warningOnly=false, editors=owner-only) so Bridge readers cannot see the tab. Use the tab-protect pattern from S255 P2.1. | MUST_CONTAIN in audit log: `restrictions_applied: N`; per-restriction protectedRangeId |
| 6.6 | Write `output/s256/verify_phase6.py` | exit 0 |

## Phase 7 — /finance-ap team-training refresh

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 7.1 | Update `team-training-2026-05-14.md` in `.claude/skills/finance-ap/references/`: <br>(a) "What's NEW since 2026-05-13/14" — add S255 entry (PR #760 merged 2026-05-20, v3.9 deployed, Intercompany tab live, etc.) + S256 in-flight entry<br>(b) "Lock verification" — bump "90 / 90 lock checks pass" → "96 / 96 lock checks pass"; reference path `output/s255/lock_test_post_v1.json`<br>(c) Per-role section: add Joevic Almajar entry (handles Supplier Payments per Denise A1)<br>(d) Update Bridge access section — note Bridge is now reader on AP Master + 5 upstream sheets per Denise E approvals | MUST_MODIFY: training doc updated |
| 7.2 | Sync changes to all 3 mirrors (`.claude/skills/finance-ap/`, `.agent/skills/finance-ap/`, `.agents/skills/finance-ap/`) — use the `pwsh -File scripts/sync_claude_skills_to_codex.ps1 -SkillName "finance-ap"` script | MUST_CONTAIN: 3 mirrors sha256 identical |
| 7.3 | Update `SKILL.md` Bridge section with Phase 6 PII audit outcome (note: "PII tabs restricted via protectedRange on TabX/TabY" or "no PII found, full Bridge view access") | MUST_MODIFY: SKILL.md in 3 mirrors |
| 7.4 | Write `output/s256/verify_phase7.py` | exit 0 |

## Phase 8 — Dry-run gate + promote v3.10 + resume scheduler

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 8.1 | Push v3.10 source to Apps Script HEAD via `projects.updateContent` + `versions.create` (version 17). Mirror S255 P9b.1 pattern. | MUST_CONTAIN: `output/s256/v310_deployment.json` with `versionNumber: 17` (NOT yet promoted to production deployment) |
| 8.2 | Create STAGING deployment pinned to v3.10 via `deployments.create`. Get staging URL. | MUST_CONTAIN: `output/s256/v310_dryrun_deployment.json` with staging deployment ID + URL |
| 8.3 | Invoke `?dryRun=1` against staging URL with web app token; capture response → `output/s256/v310_dryrun.json` | MUST_CONTAIN: HTTP 200 + valid JSON stats |
| 8.4 | Verify dry-run assertions:<br>(a) `dryrun_returned_stats` — stats has `seed`, `status_sync`, `tax_sync`, `duration_ms` keys<br>(b) `dry_run_mode_was_set` — `dry_run: true`<br>(c) `no_seed_errors` — no error fields in seed stats<br>(d) `v310_logic_active` — output contains at least one affiliate entity name OR `Procurement App` OR `BYPASS_3PL_PATTERNS` evidence<br>(e) `status_sync_5_tabs_if_pp_disabled_else_4` — if `payment_plan_mirror_disabled === true`, tabs_seen has 5 entries; else 4<br>If any FAIL: STOP. Delete staging deployment. Do NOT promote. Write reason to DEFECTS.md. | MUST_CONTAIN: `output/s256/v310_dryrun_verify.json` with `all_assertions_passed: true` |
| 8.5 | Promote production deployment to versionNumber=17 via `deployments.update`. Delete staging deployment for cleanup. | MUST_CONTAIN: production deployment ID `AKfycbw-Auq...` confirmed at versionNumber=17 |
| 8.6 | **RESUME Cloud Scheduler trigger** via `gcloud scheduler jobs resume`. Update `cloud_scheduler_pause_log.json` with `resumed_at` timestamp. | MUST_CONTAIN: scheduler state = ENABLED |
| 8.7 | Trigger one immediate live cycle via curl with token (mirror S255 P9b.6) → capture to `output/s256/post_deploy_sync.json` | MUST_CONTAIN: HTTP 200 + valid JSON |

## Phase 9 — Post-deploy verification + closeout

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 9.1 | Post-deploy verify (5 assertions):<br>(A1) banner totals match data sum within ₱100 on all 5 tabs (SOA/HO/CAPEX/Payment Plan/Intercompany)<br>(A2) Intercompany growth this cycle = 0 (existingIndex working)<br>(A3) PP mirror stats present (running unless flag flipped)<br>(A4) status_sync sees 4 or 5 tabs depending on flag state<br>(A5) cycle complete within 240s | MUST_CONTAIN: `output/s256/post_deploy_verify.json` with all 5 PASS |
| 9.2 | Write `output/s256/SUMMARY.md` with: 5-item completion table (intercompany broadening + dedup race fix + source redesign 4a/4b/4c + auto-tag + PII audit), banner totals, scheduler pause duration | MUST_CONTAIN: 5-item table + all banner totals |
| 9.3 | Write `output/s256/DEFECTS.md` with any deferred items (4a/4b/4c if Phase 1 gate failed; PII restrictions awaiting Sam decision; any backfill rows that couldn't be touched) | MUST_CONTAIN: file exists; deferred-count field |
| 9.4 | Write `output/s256/rollback_runbook.md` (mirror S255 P9b.X structure): trigger conditions, exact rollback commands (re-push v3.9 backup → v18, etc.), success criteria | MUST_CONTAIN: 4-section runbook |
| 9.5 | Update plan YAML status: PLANNED → COMPLETED, set `completed_date`, populate `execution_summary` | MUST_MODIFY: this plan file |
| 9.6 | Update SPRINT_REGISTRY.md S256 row status → COMPLETED + PR # | MUST_MODIFY: registry |
| 9.7 | Commit + push: `git add -f docs/plans/2026-05-22-sprint-256-ap-source-redesign.md docs/plans/SPRINT_REGISTRY.md output/s256/ scripts/google_apps/s256_ap_view_hourly_sync_v310.gs .claude/skills/finance-ap/ .agent/skills/finance-ap/ .agents/skills/finance-ap/` | git status clean |
| 9.8 | Create PR via `GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms --base production --head s256-ap-source-redesign --title "S256: AP Master v3.10 + source-of-truth redesign" --body "$(cat output/s256/SUMMARY.md)"` | MUST_CONTAIN: PR URL in `output/s256/pr.json` |
| 9.9 | Worktree closeout: `git status --short` clean, then `git worktree remove F:/Dropbox/Projects/BEI-ERP-s256-ap-source-redesign` (NEVER `--force`) | MUST_CONTAIN: worktree removed cleanly |
| 9.10 | STOP — report PR # to Sam, do NOT merge | Agent terminates |

## Verify Script Assertions

Per S255 precedent, each `verify_phaseN.py` implements machine-checkable assertions. Template per phase:

**verify_phase0.py:** baseline_sha matches; v3.9 backup exists in `[90000, 105000]` bytes; scheduler PAUSED; 19 tabs in baseline; ownership matrix ≥ 10 rows; Bridge present in upstream ACLs.

**verify_phase1.py:** `phase1_source_investigation.json` exists; `proceed_with_source_redesign` field populated (boolean); if `true`, both `procurement_app_chosen` and `ho_opening_balance_chosen` non-null.

**verify_phase2.py:** v3.10 file exists; grep affiliate entity names returns ≥ 5; `INTERCO_AFFILIATE_PATTERNS` const exists; `skipped_existing_fpm_soa` counter referenced.

**verify_phase3.py:** `intercompany_affiliate_migration_log.json` exists; `migrated_rows` ≥ 0; banner totals updated; Intercompany tab data range grew by migrated_rows count.

**verify_phase4a.py:** (skipped if Phase 1 gate FALSE) `PROCUREMENT_APP_ID` const in v3.10; `seedFromProcurementApp_` function exists; wired into `doRefreshAllTabs_v3_`.

**verify_phase4b.py:** (skipped if 4a deferred) `denise_pp_seed_disabled` const exists; early-exit logic present; cutover runbook written.

**verify_phase4c.py:** (skipped if 4a deferred) `HO_OPENING_BALANCE_ID` const + `seedHoOpeningBalanceOnce_` function + idempotency flag-tab logic.

**verify_phase5.py:** `BYPASS_3PL_PATTERNS` const with ≥ 5 patterns; auto-tag override logic in `seedFromDenisePaymentPlan_`; `auto_tag_bypass_log.json` shows backfill delta.

**verify_phase6.py:** `bridge_pii_audit.json` exists; `flagged_tabs_count` populated; restrictions applied where `confirmed_pii: true`.

**verify_phase7.py:** training doc updated with S255 + S256 + 96/96 + Joevic + Bridge access; 3 mirrors sha256 identical; SKILL.md Bridge section updated.

**verify_phase8.py:** v3.10 versionNumber=17 deployed to production; `v310_dryrun_verify.json` all PASS; scheduler RESUMED; `post_deploy_sync.json` HTTP 200.

**verify_phase9.py:** SUMMARY.md + DEFECTS.md present; rollback runbook present; v3.9 backup at `output/s256/script_source_backup_v39.gs` still committed; PR URL in `pr.json`.

## Rollback Runbook (will be written to `output/s256/rollback_runbook.md` at Phase 9.4)

**Trigger conditions** (any one fires):
- Phase 8.4 dry-run verify fails — STOP at gate; don't promote.
- Phase 9.1 post-deploy verify fails — rollback to v3.9.
- `_sync_log_v3` shows error rate > 0 in first 2 cycles after promote.
- Banner shows wrong totals (delta > ₱100 vs data sum).
- Sam reports broken behavior.

**Rollback steps:**
1. Pause Cloud Scheduler.
2. Read backup: `cat output/s256/script_source_backup_v39.gs` (committed at Phase 0.4).
3. Push v3.9 source to live Apps Script via `script.projects.updateContent`.
4. Promote to new version (will become 18 — Apps Script doesn't allow rolling back to older versionNumber).
5. Verify rollback: curl with `?dryRun=1` shows v3.9 behavior (no `INTERCO_AFFILIATE_PATTERNS`, no `BYPASS_3PL_PATTERNS`).
6. Resume scheduler.
7. Log rollback to `output/s256/rollback_log.json`.
8. Mark plan status `ROLLBACK_v3.9`; update registry.
9. Open Chat to Sam with rollback report; do NOT close worktree (Sam decides next steps).

## Failure Response

- **Mode A (script bug):** file in DEFECTS.md, fix code, re-run verify script, re-deploy. Do NOT downgrade assertions.
- **Mode B (plan bug — wrong assertion):** investigate, normalize plan inline per Ground-Truth Lock, continue. Don't bump tolerances silently.
- **Mode C (brittleness — intermittent timeout):** fix the LIBRARY (split sync into smaller batches if Procurement App is huge), not the spec.
- **Mode D (dry-run failure at Phase 8.4):** STOP. Delete staging deployment. Do NOT promote.
- **Mode E (post-deploy verification failure at Phase 9.1):** Follow Rollback Runbook. Do NOT proceed to worktree closeout.
- **Mode F (Phase 1 investigation gate FALSE):** Skip 4a/4b/4c. Write `output/s256/source_redesign_deferred.md` with what's missing. Continue to Phase 5. This is NOT a failure — it's a planned defer.

## Notes / Out-of-scope (explicitly deferred to S257 or later)

- **Frappe migration of AP Master** (Feb 2026 go-live target): replaces Google-Sheets-based AP Master with `tabPurchase Invoice` + custom dashboard. Not in S256.
- **Bypass-supplier auto-tag in FPM seed** (per Phase 5.3 deferral note): could be added in S257 if Sam wants FPM-sourced 3M Dragon rows tagged Manual too.
- **PropertiesService for `payment_plan_mirror_disabled` flag**: still a hardcoded const. Migration to PropertiesService for toggle-without-redeploy is S256+ scope. Sam can use the existing v3.9 cutover runbook (`output/s255/payment_plan_cutover_runbook.md`).
- **Procurement App schema mismatches** (if Phase 1 finds incomplete schema): defer to a dedicated schema-mapping sprint with stakeholder input from Cayla/Luwi/Ian.
- **Other 3PLs / bypass-procurement suppliers Sam may name later**: add to `BYPASS_3PL_PATTERNS` array in v3.11.
- **L3 / Playwright tests**: this sprint has no L3 scenarios — it's an Apps Script + Sheets ops sprint, not a UI feature. Verify scripts (verify_phaseN.py) replace L3.
- **Section A3 deferred 6 BEI writers** (drew, marco, julius kept as-is after Denise A3 confirmed they stay; liezel and maika removed; bea.garcia.intern removed): S255 closeout executed.
- **James Tamaca did not countersign Denise's PDF**: per Sam directive 2026-05-22, James's countersign is NOT required. Denise's authority is sufficient.
