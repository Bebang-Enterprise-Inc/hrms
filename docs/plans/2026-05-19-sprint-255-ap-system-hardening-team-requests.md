---
sprint_id: S255
title: AP System Hardening — fix all audit findings + integrate Angela/Bethina/Avis team requests
status: PLANNED_AUDITED_v1.1
plan_version: 1.1
created_date: 2026-05-19
last_amended_date: 2026-05-20
completed_date: null
canonical_scope: none
canonical_scope_rationale: |
  Google Apps Script patch + Google Sheets schema work + Denise PP sheet ACL
  cleanup + /finance-ap skill updates. No Frappe `tabCompany`, `tabWarehouse`,
  `tabCustomer`, or `tabSupplier` mutations. No `hrms/api/*` files touched.
  Supplier names in AP Master are PAYEE strings on Google Sheets, not Frappe
  master records.

audit_status: |
  Audited 2026-05-19 → 9 CRITICAL + 8 WARNING blockers identified.
  Amended 2026-05-20 (v1.1) → all 17 blockers resolved (specs preserved).
  Audit artifacts: output/plan-audit/s255-ap-system-hardening/verified_blockers.md
audit_reference: output/plan-audit/s255-ap-system-hardening/verified_blockers.md

branch_name: s255-ap-system-hardening-team-requests
worktree: F:/Dropbox/Projects/BEI-ERP-s255-ap-system-hardening-team-requests
repos_touched:
  - hrms (only for: `scripts/google_apps/s248_ap_view_hourly_sync_v38.gs` → v3.9 patch; `.claude/skills/finance-ap/*` skill updates; this plan + `SPRINT_REGISTRY.md`)

depends_on:
  - S248 PR #751 MERGED 2026-05-14 (Phase 0-3 — Denise PP seed live; Apps Script v3.7 + v3.8 deployed)
  - S248 PR #752 MERGED 2026-05-14T07:22:16Z (commit `d1ab45c9`) — Payment Plan tab live + mirror running hourly
  - Apps Script project `1pE8wt_z8NA9q__PNbUilJ72UE0_EI3DmurJekkw6mbgtHr8hosnKsNRF`, deployment `AKfycbw-AuqJq6OyMV6DGarGWEruDoez04OETlWFQoeppNjvzoeSOJOomPOZNsVPE9iuV6ZC_Q`, web app token `bei-ap-sync-2026-04`, current version 15 (v3.8, source = 85,734 bytes on `origin/production` commit `d25f035a4`)

evidence_committed:
  - output/s255/SUMMARY.md
  - output/s255/DEFECTS.md
  - output/s255/S255_SURFACE_OWNERSHIP_MATRIX.csv
  - output/s255/baseline_state.json
  - output/s255/script_source_backup_v38.gs        # v1.1: MOVED from tmp/ to survive worktree closeout (Blocker 7)
  - output/s255/v39_dryrun.json                    # v1.1: NEW — dry-run output before promote (Blocker 9)
  - output/s255/v39_deployment.json
  - output/s255/post_change_state.json
  - output/s255/post_deploy_sync.json
  - output/s255/intercompany_ambiguous.json        # v1.1: NEW — ambiguous edge cases for Sam review (Warning 5)
  - output/s255/intercompany_routing_log.json
  - output/s255/dedup_cleanup_log.json
  - output/s255/3m_dragon_reclassification_log.json
  - output/s255/sam_acl_approval.draft.json        # v1.1: NEW — agent-written draft (Blocker 8)
  - output/s255/sam_acl_approval.json              # v1.1: Sam-finalized version (Blocker 8)
  - output/s255/acl_change_log.json
  - output/s255/bridge_access_audit.json
  - output/s255/dd_package_checklist.md
  - output/s255/cloud_scheduler_pause_log.json     # v1.1: NEW — proof scheduler was paused (Blocker 6)
  - output/s255/rollback_runbook.md                # v1.1: NEW — explicit rollback procedure (Blocker 7)
  - output/s255/phase{0..9}_checklist.md
  - output/s255/verify_phase{0..9}.py
  - output/s255/closeout_state.json

evidence_transient:
  - tmp/s255/dry_run_*.json
  - tmp/s255/probe_*.json
  - tmp/s255/denise_sheet_snapshot_pre.csv
  - tmp/s255/traceback_*.txt

execution_summary: null
---

# Sprint S255 — AP System Hardening + Team Recommendations

## 🟥 AMENDMENT BLOCK — v1.1 (2026-05-20)

**Status:** PLANNED_AUDITED_v1.1 — all 9 CRITICAL + 8 WARNING audit blockers resolved.

**The 11 backlog items (specs) are UNCHANGED.** All amendments are implementation-detail refinements: tighter routing predicate, safer rename strategy, explicit handoff mechanics, dry-run gate, lock primitive, rollback runbook.

**Resolution summary (cross-reference: `output/plan-audit/s255-ap-system-hardening/verified_blockers.md`):**

| # | Blocker | Resolution location |
|---|---|---|
| C1 | Intercompany filter misroutes 18 govt-remittance rows | Phase 2.2 + 2.3 — tighter predicate |
| C2 | Phase 1.7 creates duplicate GOODS/SERVICES header on PP tab | Phase 1.7 — rename target changed to BILLED ENTITY for PP col 15 |
| C3 | CLASSIFICATION holds entity-routing values (mixed semantics) | Phase 1.6 — declared as DISPLAY-HEADER-ONLY rename; team-training note |
| C4 | Rename affects 8+ code sites, not just buildGrid | Phase 1.6 — explicit code-site enumeration |
| C5 | Intercompany missing from existingIndex (line 428) | Phase 2.5 — explicit existingIndex extension |
| C6 | No concurrent-run lock; hourly cycle races destructive ops | Phase 0.X + Phase 9.X — Cloud Scheduler pause/resume |
| C7 | Rollback runbook missing; backup in tmp/ deleted by closeout | Phase 0.4 — backup to output/; new `## Rollback Runbook` section |
| C8 | Phase 8 pause handoff mechanics undefined | Phase 8.2/8.3 — sam_acl_approval.json schema + handoff |
| C9 | No dry-run gate between build and live deploy | Phase 9.5b/c/d/e — deploy-to-staging-URL dry-run |
| W1 | Dedup invKey not specified | Phase 4.1 — uses `invNoVariants_()` |
| W2 | Header-rename / script-deploy ordering window | Phase 1.6 note — safety guard during window |
| W3 | Phase 9 unit count wrong (13 vs 15; total 64 vs 62) | Phase Budget table — corrected |
| W4 | PP tab has 2 STATUS columns; Phase 6 doesn't specify which | Phase 6.1/6.2 — col I (mapped) specified |
| W5 | "5 ambiguous edge cases" undefined | Phase 2.3 — criteria + `intercompany_ambiguous.json` |
| W6 | verify_phaseN.py assertions not specified | new `## Verify Script Assertions` section |
| W7 | Size estimate 7% low (~80K vs actual 85,734) | Phase 0.4 + 9.5 — `[86000, 110000]` range |
| W8 | depends_on PR #752 ambiguous | YAML line — MERGED 2026-05-14T07:22:16Z |

---

## TL;DR for cold-start agents

Consolidates 11 backlog items from three sources:
1. **Avis Chat message 2026-05-18 16:52 PHT** relaying Ms. Angela + Bethina concerns
2. **2026-05-19 investigation** of who edited Denise's sheet (`tmp/finance_ap_audit/audit_2026-05-13/avis_complaint_investigation_2026-05-19.json`)
3. **Earlier audits** (S248 Phase 0-3 wrap-up notes; the 2026-05-13 4-way reconciliation findings)

Plus formalizes the **Bridge fractional CFO / DD auditor engagement** in the `/finance-ap` skill (Bridge writes from `accountant.outsource@bridge-ph.com` — AUTHORIZED, already updated in the skill 2026-05-19).

After this sprint:
- AP Master entry tabs have clean 19/19/20 grids (no phantom columns); Angela's "Remarks" column gracefully migrated; `CLASSIFICATION` renamed to `GOODS/SERVICES`
- FPM seed no longer routes Bebang Kitchen/Shaw/Enterprise intercompany transfers to Head Office (35 misrouted rows fixed)
- Angela's 2 staging tabs (Scheduled for Online Transfer / Scheduled for Release Check) live in AP Master as native views, not parallel in Denise's sheet
- 14 duplicate rows on Suppliers SOA cleaned
- Banner refresh works (no more stale ₱81.66M while sheet has ₱314.7M)
- 3M Dragon manual-invoice flow documented; 12 stranded "Invoice No.5172" rows routed properly
- Denise PP sheet ACL: Roberose downgraded to commenter; Joevic confirmed; Bridge kept; outside accountants without explicit Sam approval blocked
- Status sync wired to Payment Plan tab — Denise can switch over to AP Master Payment Plan whenever she's ready (currently strict-locked mirror; this sprint adds the cutover path)

## Context Sources (Ground-Truth Lock)

### Evidence sources

| Source | What it proves | Path / ID |
|---|---|---|
| Avis Chat message | Angela + Bethina raised issues 2026-05-18 16:52 PHT | Pasted in S255 originating user message; reproduced in `output/s255/SUMMARY.md` |
| AP Master grid drift snapshot | Phantom cols 21-22 on entry tabs; `Remarks` col 20 on Suppliers SOA with 1 entry "received: 5/16/2026" at row 355 | `tmp/finance_ap_audit/audit_2026-05-13/grid_state_2026-05-19.json` |
| 7-day editor activity on Denise PP sheet | 6 distinct editors incl. Bridge contractor; Angela 12 revs heaviest | `tmp/finance_ap_audit/audit_2026-05-13/denise_sheet_revisions_7day.json` |
| Bethina's "Commissary in HO" finding | 35 rows in Head Office tagged Bebang Kitchen / Shaw fund transfers from FPM seed | `tmp/finance_ap_audit/audit_2026-05-13/avis_complaint_investigation_2026-05-19.json` |
| Angela's 2 new tabs on Denise PP | `Scheduled for Online Transfer - Due` (91 rows), `Scheduled for Release Check - Due` (72 rows) — useful Finance staging views | Direct read from `13cyYaPLmjL0TPaeqyYd2esjJNYj-5qJCDS8OZLdhURU` |
| Duplicate audit | 14 (payee, invKey, amount) duplicate pairs on Suppliers SOA (some from Denise PP seed × FPM seed overlap, others true dupes) | Same as above; section CHECK 1 |
| Bridge engagement | CEO confirmed 2026-05-19 PHT: `bridge-ph.com` is fractional CFO + DD auditor — `accountant.outsource@bridge-ph.com` AUTHORIZED | `.claude/skills/finance-ap/SKILL.md` Bridge section (added 2026-05-19) |
| Banner staleness (RF-7) | `buildGrid()` only invoked by legacy `doRefreshAllTabs_`; v3 hourly cycle never refreshes banner. Banner shows ₱49.82M+₱24.71M+₱7.16M=₱81.66M while actual sum (incl. FPM-seeded rows) ≈ ₱314.7M | `tmp/finance_ap_audit/audit_2026-05-13/DENISE_VS_INFRA_FINDINGS.md` |
| Lock verification | 90/90 strict-lock checks PASS as of 2026-05-14 (6 writers × 15 locked tabs) | `tmp/finance_ap_audit/audit_2026-05-13/impersonate_lock_test_results.json` |
| Bridge skill section | `accountant.outsource@bridge-ph.com` writes to Denise PP — AUTHORIZED | `.claude/skills/finance-ap/SKILL.md` (recently added) |

### Count method

Reproducible probes the executing agent must run at Phase 0 and Phase 9 to confirm pre-state and post-state. Same script can be used in both phases (paths differ).

```python
# Pre-state baseline (Phase 0 step 6)
python tmp/finance_ap_audit/audit_2026-05-13/pull_full_acl.py
# Saves: tmp/finance_ap_audit/audit_2026-05-13/acl_snapshot_2026-05-14.json
# Verify the snapshot includes Bridge user
```

```python
# Grid state (Phase 0 step 7 — copy from prior probe; verify entry tab cols match expected)
# Expected before this sprint: SOA cols=22 (incl. phantom + Remarks), HO cols=22 (incl. phantom), CAPEX cols=22 (incl. phantom)
# Expected after this sprint: SOA cols=19, HO cols=19, CAPEX cols=20
```

### Authoritative sections

Phases 0–9 below are authoritative for execution. Amendments must update phase bodies in the same edit.

### Unresolved-value policy

Operator-facing unknowns become `[UNVERIFIED — requires resolution]`. There is currently 1 unverified item: **Joevic Almajar's role** (he edited Denise PP twice on Mon May 18 but is not in any /finance-ap roster). Phase 8 step 8.3 verifies with Denise/James before any ACL change.

## Worktree boot

Spawn at `F:/Dropbox/Projects/BEI-ERP-s255-ap-system-hardening-team-requests` from `origin/production`. Closeout removes it.

## Design Rationale (for cold-start agents)

### Why this exists

Avis relayed Angela + Bethina concerns 2026-05-18. The investigation 2026-05-19 found:
- Multiple schema drifts on Denise PP sheet (Angela added Remarks/Tag/Reason columns, removed DESCRIPTION on Middleby/FD tabs)
- 1 Remarks column added on AP Master Suppliers SOA (row 355: "received: 5/16/2026")
- Phantom empty columns 21-22 on SOA/HO/CAPEX (someone tried adding, reverted, grid stayed expanded)
- 35 commissary/intercompany rows misrouted to Head Office by FPM seed (Bethina's complaint)
- 14 real duplicates on Suppliers SOA (Denise PP seed × FPM seed overlap)
- 2 new "Scheduled for ..." tabs Angela built in Denise PP — useful staging views not in AP Master

All of these are real, fixable, and align with making AP Master the single source of truth.

Plus the Bridge engagement (2026-05-14) means the outside contractor `accountant.outsource@bridge-ph.com` is AUTHORIZED, not a security hole. The /finance-ap skill is updated.

### Why this architecture

**Alternatives considered:**

| Option | Why rejected |
|---|---|
| Add Angela's columns directly to the AP Master entry tabs (SOA, HO, CAPEX) | Breaks the 19/20-column schema the script depends on. Would require rewriting `buildGrid()`, the seed functions, and 14 summary-tab formulas. |
| Keep Angela working in Denise PP and never formalize | Already failing — she's building parallel tabs (Scheduled for Online/Check) and adding columns the script can't see. The mirror only goes one direction (Denise → AP Master). |
| Migrate AP Master Suppliers SOA / Head Office / CAPEX to the 30-column Payment Plan schema | Too big — would invalidate every existing row + script invariant. Better to keep entry tabs lean and put Angela's extras in Payment Plan tab (already 30 cols). |
| **CHOSEN:** Formalize Payment Plan tab as the rich-schema home (already 30 cols + Angela's missing-from-EnTry-tabs fields like TIN, Address, Terms, etc.). Add Angela's 2 staging views as new Payment Plan filtered tabs (or filter views in the Payment Plan tab). Drop Remarks column from Suppliers SOA. | Aligns with S248 cutover plan: Denise (when ready) switches into Payment Plan tab where Angela's requested fields ALREADY exist. No schema break on entry tabs. |

### Key trade-off decisions

| Decision | Choice | Reason |
|---|---|---|
| What to do with Angela's "Remarks" col 20 on Suppliers SOA | Migrate the 1 cell "received: 5/16/2026" to INVOICE DATE if blank on that row, then delete col 20 | Preserves the data point; restores entry tab to 19 cols |
| Phantom cols 21-22 cleanup | Resize grid back to 19/19/20 via `batchUpdate.updateSheetProperties` | Removes phantom space, no data lost (all empty) |
| Bebang intercompany routing | Add filter to FPM seed: skip rows where category contains "Intercompany" OR payee starts with "Bebang " | Removes 35 misrouted rows from Head Office without losing the data (it's still in FPM) |
| 14 duplicate rows on Suppliers SOA | Identify pairs via (payee, invKey, amount); delete the "Denise PP"-sourced one if a "Suppliers SOA" or "FPM" one exists for the same triple | Keeps the legacy/script-managed source as authoritative |
| Banner refresh (RF-7) | Add `recomputeBanners_(ss)` function called at end of `doRefreshAllTabs_v3_` — recompute totals on the fly from current data | Eliminates stale banner without rerunning the expensive legacy `doRefreshAllTabs_` rebuild |
| Angela's "Scheduled for ..." staging tabs | Recreate as Sheets-native filtered views on the AP Master Payment Plan tab (no copy of data — just filter on STATUS) | One source of truth; her workflow preserved |
| 3M Dragon manual invoices ("Invoice No.5172" pattern, 12 rows) | Tag the SOURCE column as `Denise PP - Manual` (new sub-tag) when invoice text contains "Invoice No." prefix; track separately in the bridge audit trail | Lets Bridge see they're outside procurement without forcing a procurement-onboarding sprint |
| Joevic Almajar's access | Phase 8: ask Denise/James (Joevic likely on James's F&A team); pause access decision pending response | Don't revoke a legitimate new team member without confirmation |
| Bridge access scope | Keep Bridge reader/commenter on FPM + Compliance + Bank Balances; writer only on Denise PP and a new `Bridge_DD` reference tab in AP Master | Bridge needs read-everything for DD; write-anywhere is excessive |
| Status sync to Payment Plan tab | Wire `syncStatusFieldsFromFPM_` to also write to PP tab when `payment_plan_mirror_disabled` flag is set (Sam toggles when Denise switches) | Enables clean cutover later; mirror stays the default for now |

### Known limitations and mitigations

| Limitation | Mitigation |
|---|---|
| Can't see per-cell history on native Google Sheets via API | Sam reviews Drive UI version history if forensic detail needed; this sprint only changes current state |
| Apps Script execution time limit (~6 min per HTTP-triggered run) | Phase 7 banner-refresh adds ~10 sec; total cycle still under limit |
| Angela might revert Remarks col after we delete it | Schema-change tasks are recorded; team-training doc reinforces "don't add columns to entry tabs" |
| If Bridge requests additional access mid-sprint | Sam approves separately; not in S255 scope |

### Source references

- `.claude/skills/finance-ap/SKILL.md` — operational skill (Bridge section added 2026-05-19)
- `.claude/skills/finance-ap/references/team-training-2026-05-14.md` — per-role training (Bridge mention added)
- `tmp/finance_ap_audit/live_script/Code.gs` — current v3.8 Apps Script live source
- `scripts/google_apps/s248_ap_view_hourly_sync_v38.gs` — repo source mirroring live v3.8
- `tmp/finance_ap_audit/audit_2026-05-13/*` — all investigation artifacts

## Requirements Regression Checklist (v1.1)

Verify these BEFORE writing code. Each is a yes/no assertion the executing agent checks.

- [ ] Is `/finance-ap` skill's Bridge section present in all 3 mirrors (`.claude/skills/`, `.agent/skills/`, `.agents/skills/`)? (already done 2026-05-19, verify before patching script)
- [ ] Does v3.9 patch keep all v3.7 + v3.8 functions intact (no regression on Denise seed or Payment Plan mirror)?
- [ ] **v1.1 — Is the intercompany-routing filter the TIGHT predicate?** PAYEE regex `/^Bebang\s+(Enterprise|Kitchen|Shaw)\s+Inc\.?/i` AND CLASSIFICATION `/(transfer|cash sweep|intercompany)/i` AND NOT `/HDMF|SSS|PHIC|PHILHEALTH|BIR|PAG-?IBIG|CONTRIBUTION|RENTAL|FINAL PAY/i` (NOT the loose v1.0 predicate)
- [ ] Is the new `Intercompany` tab strict-locked to sam@bebang.ph only (like the 15 existing locked tabs)?
- [ ] **v1.1 — Is Intercompany added to existingIndex (v3.8 line 428 tab array extended from 3 → 4)?**
- [ ] Does `recomputeBanners_(ss)` compute totals from the current tab data (not legacy snapshot)?
- [ ] Does `recomputeBanners_` write to row 4 (banner totals) AND optionally row 10 (aging breakdown) — not touching other rows?
- [ ] Does the Suppliers SOA grid get resized 22→19 via `batchUpdate.updateSheetProperties` (not via deletion of cells)?
- [ ] **v1.1 — Does the dupe cleanup use `invNoVariants_()` normalization (NOT simple uppercase)?**
- [ ] Does the dupe cleanup keep the legacy/FPM row and delete the Denise PP duplicate (not the other way around)?
- [ ] Does the migration of Angela's Remarks cell preserve the data ("received: 5/16/2026") in INVOICE DATE as a Date type (not string) before col 20 is deleted?
- [ ] Are Angela's 2 staging tabs recreated as **filtered views** on Payment Plan tab **col I (position 9, mapped STATUS — NOT col AB raw)** with no data duplication?
- [ ] Does the Joevic access decision wait for Denise/James confirmation (no unilateral change)?
- [ ] Does the 3M Dragon "MANUAL" SOURCE class roll out without breaking the existing Denise PP seed?
- [ ] Are Roberose's writer-on-Denise-PP role downgrade actions taken only AFTER Sam approves via `sam_acl_approval.json` (Phase 8 explicit gate)?
- [ ] **v1.1 — Is the CLASSIFICATION rename DISPLAY-ONLY** (header strings at lines 70, 1035, plus `hi('CLASSIFICATION')` at 506, 668) with internal `classification` field key preserved everywhere else?
- [ ] **v1.1 — Is Cloud Scheduler PAUSED before destructive Phase 1/2/4 operations and RESUMED after Phase 9b.7 verification?**
- [ ] **v1.1 — Does Phase 9b have a dry-run gate (separate deployment + `?dryRun=1` + assertion check) BEFORE promoting to v16?**
- [ ] **v1.1 — Is the v3.8 backup at `output/s255/script_source_backup_v38.gs` (committed evidence, not `tmp/`)?**
- [ ] Does Phase 9b closeout verify all 11 backlog items have a green check or a specific deferred-to-S256 reason?

## Phase Budget Contract (v1.1 — corrected)

| Phase | Description | Estimated units |
|---|---|---:|
| Phase 0 | Worktree boot + baseline + Cloud Scheduler pause | 5 |
| Phase 1 | Schema cleanup — drop phantom cols, migrate Remarks, rename CLASSIFICATION (display-only) | 8 |
| Phase 2 | FPM seed intercompany routing fix + new Intercompany tab + existingIndex extension | 7 |
| Phase 3 | Banner refresh (`recomputeBanners_`) | 5 |
| Phase 4 | Dedup cleanup on Suppliers SOA (uses `invNoVariants_`) | 5 |
| Phase 5 | 3M Dragon manual-invoice SOURCE class + reclassify the 12 stranded rows | 4 |
| Phase 6 | Angela's 2 staging tabs → Filter views on Payment Plan tab (col I) | 6 |
| Phase 7 | Status sync wiring to Payment Plan tab (gated, off by default) | 8 |
| Phase 8 | Denise PP sheet ACL audit + handoff mechanics + Roberose/Joevic decisions | 5 |
| Phase 9a | Bridge DD readiness + skill updates + script build | 7 |
| Phase 9b | Dry-run gate + promote-to-v16 + post-deploy verification + closeout | 10 |
| **Total** | | **70 units** |

- Hard limit: 80 (within budget)
- Phase 9 SPLIT into 9a (build) + 9b (deploy + closeout) — was contingent in v1.0, now firm.
- Single-session executability: 70 units is borderline. If context exhausts after Phase 7, the natural break is to commit + push state, exit, resume with `/execute-plan-bei-erp S255` (next agent picks up at Phase 8).

## Anti-Rewind / Concurrent-Run Protection

### Ownership matrix

| Surface | Owner | Notes |
|---|---|---|
| Apps Script project `1pE8wt_z8NA9q__PNbUilJ72UE0_EI3DmurJekkw6mbgtHr8hosnKsNRF` HEAD | S255 | No other sprint pushes here until closeout |
| `scripts/google_apps/s248_ap_view_hourly_sync_v38.gs` → new v39 file | S255 | Save as `scripts/google_apps/s255_ap_view_hourly_sync_v39.gs` (don't overwrite v38) |
| AP Master entry tabs SOA / HO / CAPEX | Script-writes + S255 one-time structural changes (Phase 1) | Resize grid + rename CLASSIFICATION; no row-level edits |
| AP Master Payment Plan tab | Script-mirror; S255 adds 2 filter views (Phase 6); status-sync wired in Phase 7 | |
| AP Master new `Intercompany` tab | S255 creates in Phase 2 | strict-locked to sam@ only |
| FPM + Compliance + PCM + Bank Balances | NO S255 writes | Read-only context |
| Denise PP sheet | NO S255 writes to row data; ACL changes in Phase 8 (with Sam approval) | |
| `/finance-ap` skill | S255 already added Bridge section 2026-05-19 | Other amendments in Phase 9 |

### Protected surfaces

These must NOT regress:

- 15 strict-locked tabs on AP Master (status-sync continues)
- Payment Plan tab strict-lock (still sam@ only during mirror phase)
- Mirror function running hourly
- Denise PP seed running hourly
- Status sync FPM → entry tabs running hourly
- Tax sync Compliance → entry tabs running hourly

Verification: each Phase X verify script asserts at least one of these continues to function (e.g., row count grows, log entries continue, `nochange + updates > 0`).

### Remote-truth baseline

Capture at Phase 0 step 5:
- Origin/production SHA: `git rev-parse origin/production` → `output/s255/baseline_sha.txt`
- Apps Script version: 15 (v3.8) on deployment `AKfycbw-AuqJq6OyMV6DGarGWEruDoez04OETlWFQoeppNjvzoeSOJOomPOZNsVPE9iuV6ZC_Q`
- Apps Script source size: ~80,000 chars (v3.8)
- AP Master grid sizes per tab (snapshot to `output/s255/baseline_state.json`)
- Denise PP grid sizes per tab + revision count

### Pre-touch backup (v1.1)

Phase 0 step 4 saves a copy of current v3.8 source to `output/s255/script_source_backup_v38.gs` (committed evidence — survives worktree closeout per Blocker 7) BEFORE any push.

### Concurrent-run protection (v1.1 — resolves Blocker 6)

The chosen lock primitive is **Cloud Scheduler pause** (option (a) from the audit fix list):
- Phase 0.5 pauses the hourly trigger via `gcloud scheduler jobs pause`
- All destructive operations (Phase 1.2/1.3/1.4/1.5 grid mutations, Phase 2.3 row migration, Phase 4.2 dedup delete) run without race risk
- Phase 9b.5 resumes the trigger AFTER v3.9 is verified working
- Rollback Runbook re-pauses if needed

PropertiesService and LockService were NOT chosen — they would require deploying v3.9 first to add the lock primitives, but the destructive Phase 1 operations precede deploy. Pausing the scheduler externally addresses the race without requiring code changes.

## Zero-Skip Enforcement

Every task has a MUST_MODIFY or MUST_CONTAIN assertion or a verification script step. Phase gate is a Python script.

**Forbidden agent behaviors:**

- Marking partial work as DONE
- Replacing a task with a simpler version without Sam approval
- "Deferred to S256" without writing the deferral reason in `output/s255/DEFECTS.md`
- Self-grading via prose instead of filesystem evidence
- Silently retrying deploy on failure — STOP and present error

### Phase completion checklist

After each phase, write `output/s255/phase{N}_checklist.md` with the format:

| Task | Status | Evidence | Skipped? | If skipped, why? |
|---|---|---|---|---|
| 1.1 | DONE | `git diff scripts/google_apps/s255_ap_view_hourly_sync_v39.gs` shows `function recomputeBanners_` | NO | n/a |
| ... | | | | |

## Status Reconciliation Contract

When status / counts / blockers change, update in the same work unit:

1. `output/s255/SUMMARY.md`
2. `output/s255/closeout_state.json`
3. This plan's YAML `status` field
4. `docs/plans/SPRINT_REGISTRY.md` S255 row

## Signoff Model

- **Mode:** single-owner
- **Approver of record:** Sam Karazi (CEO)
- **Signoff artifact:** `output/s255/closeout_state.json` with `signed_off_by: "sam@bebang.ph"` + ISO timestamp
- **Note:** CFO seat vacant; **Bridge fractional CFO advises but does NOT approve** unless Sam delegates explicitly per-sprint

## Autonomous Execution Contract

### Completion condition

This sprint is COMPLETE when ALL of:

- [ ] Phases 0, 1, 2, 3, 4, 5, 6, 7, 8, 9a, 9b all `status=DONE`
- [ ] Cloud Scheduler paused at Phase 0.5 AND resumed at Phase 9b.5 (both timestamps logged)
- [ ] `output/s255/v39_dryrun_verify.json` shows `all_assertions_passed: true` (dry-run gate cleared)
- [ ] `output/s255/v39_deployment.json` shows `versionNumber: 16`
- [ ] `output/s255/post_deploy_verify.json` shows all 5 assertions PASS
- [ ] AP Master Suppliers SOA grid back to 19 cols (no phantom)
- [ ] AP Master Head Office grid 19 cols, CAPEX 20 cols
- [ ] AP Master `CLASSIFICATION` display-header renamed to `GOODS/SERVICES` on SOA/HO/CAPEX (internal field key `classification` UNCHANGED)
- [ ] Payment Plan tab col 15 renamed to `BILLED ENTITY` (col 23 `GOODS/SERVICES` unchanged — no duplicate header)
- [ ] New `Intercompany` tab exists on AP Master, strict-locked, in extended existingIndex
- [ ] At least 15 misrouted Bebang Kitchen/Shaw/Enterprise rows reclassified to Intercompany tab (v1.1 — refined from "30 of 35" after fact-check); ambiguous rows logged
- [ ] Banner row 4 on each entry tab reflects ALL row data (recomputeBanners_ active)
- [ ] 12+ duplicate rows on Suppliers SOA removed using `invNoVariants_()` normalization (Denise PP-sourced dupes deleted; legacy/FPM-sourced kept)
- [ ] `Denise PP - Manual` SOURCE class introduced; ≥ 10 of the 12 "Invoice No." rows reclassified
- [ ] 2 filter views created on Payment Plan tab targeting **col I (mapped STATUS)** as Sheets-native filter views
- [ ] Status sync to Payment Plan tab wired but DISABLED by default (controlled by `payment_plan_mirror_disabled` flag)
- [ ] Denise PP sheet ACL: per-decision actions executed per `sam_acl_approval.json`, OR `phase8_deferred_to_s256.json` present
- [ ] Bridge DD readiness section in `output/s255/SUMMARY.md` lists access state for FPM/Compliance/Bank/Cashflow/PCM
- [ ] `output/s255/script_source_backup_v38.gs` still committed (survives worktree closeout)
- [ ] PR created (s255-ap-system-hardening-team-requests branch), Sam stops short of merge per PR-Handoff
- [ ] `docs/plans/SPRINT_REGISTRY.md` S255 row → `COMPLETED`
- [ ] This plan's YAML → `status: COMPLETED`, `completed_date: 2026-05-XX`

### Stop-only-for

- Missing credentials/access
- Destructive approval (Roberose downgrade, Joevic decision — wait for Sam)
- Genuine business-policy decision (e.g., Bridge requests extra write access — escalate)
- Direct conflict with unrelated in-flight changes

### Continue without pause through

- Phase 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 sequentially

If a phase has a dependency on Sam approval (Phase 8 — Roberose/Joevic), the agent pauses ONLY at that gate, completes other phases first if possible.

### Blocker policy

| Class | Response |
|---|---|
| Programmatic (script error) | Fix and continue |
| Evidence mismatch (Denise PP schema changed since plan written) | Re-snapshot, normalize plan, continue |
| 3× failure | Grounded research (read GAS API docs, traceback files), then continue |
| Business-data/policy (Joevic identity) | Pause Phase 8 only; complete other phases |
| Active-run conflict (someone patched script mid-sprint) | Pause, present diff, ask Sam |

### Canonical closeout artifacts

- `output/s255/SUMMARY.md`
- `output/s255/DEFECTS.md`
- `output/s255/S255_SURFACE_OWNERSHIP_MATRIX.csv`
- `output/s255/v39_deployment.json`
- `output/s255/baseline_state.json`
- `output/s255/post_change_state.json`
- `output/s255/intercompany_routing_log.json`
- `output/s255/dedup_cleanup_log.json`
- `output/s255/3m_dragon_reclassification_log.json`
- `output/s255/acl_change_log.json`
- `output/s255/phase0_checklist.md` through `output/s255/phase9_checklist.md`
- `output/s255/closeout_state.json`
- `docs/plans/2026-05-19-sprint-255-ap-system-hardening-team-requests.md` (this file, YAML updated)
- `docs/plans/SPRINT_REGISTRY.md` (S255 row updated)
- `scripts/google_apps/s255_ap_view_hourly_sync_v39.gs` (the v3.9 script source)
- `.claude/skills/finance-ap/SKILL.md` (any final amendments — Bridge section already in)

## Phase 0 — Boot + baseline (v1.1 — adds scheduler pause + committed backup)

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 0.1 | Read this plan (v1.1) + audit blockers + 4 related references (finance-ap SKILL.md, team-training-2026-05-14.md, S248 plan, S248 PR #751 + #752 SUMMARYs) | none |
| 0.2 | `git fetch origin --prune` then spawn worktree at `F:/Dropbox/Projects/BEI-ERP-s255-ap-system-hardening-team-requests` from `origin/production` | MUST_CONTAIN: worktree dir exists; HEAD = origin/production SHA |
| 0.3 | Record remote-truth baseline (`git rev-parse origin/production` → `output/s255/baseline_sha.txt`) | MUST_CONTAIN: SHA non-empty |
| 0.4 | Backup current Apps Script v3.8 source → `output/s255/script_source_backup_v38.gs` (committed evidence — survives worktree closeout per Blocker 7) | MUST_CONTAIN: file size in `[85000, 95000]` bytes |
| 0.5 | **NEW v1.1 — PAUSE Cloud Scheduler trigger** (per Blocker 6): use `gcloud scheduler jobs pause projects/quiet-walker-475722-s2/locations/asia-southeast1/jobs/<job-name>` (find via `gcloud scheduler jobs list --filter="name:bei-ap"`). Log to `output/s255/cloud_scheduler_pause_log.json` with `{paused_at, job_name, original_state}` | MUST_CONTAIN: `paused: true` in log |
| 0.6 | Snapshot AP Master grid sizes per tab → `output/s255/baseline_state.json` | MUST_CONTAIN: keys for all 18 tabs |
| 0.7 | Snapshot Denise PP sheet grid + 7-day editor list → `output/s255/denise_pp_baseline.json` | MUST_CONTAIN: `bridge_user_present: true` |
| 0.8 | Write `output/s255/S255_SURFACE_OWNERSHIP_MATRIX.csv` | MUST_CONTAIN: ≥ 10 rows |
| 0.9 | Verify Bridge section in `/finance-ap` SKILL.md present in all 3 mirrors | grep "Bridge" returns ≥ 5 hits across 3 SKILL.md files |
| 0.10 | Write `output/s255/verify_phase0.py` with assertions from `## Verify Script Assertions` section below | exit 0 |

**Phase 0 gate:** `python output/s255/verify_phase0.py` exits 0 AND `cloud_scheduler_pause_log.json` shows `paused: true`.

## Phase 1 — Schema cleanup on entry tabs (v1.1 — display-only rename, PP rename retargeted)

**v1.1 RENAME SAFETY NOTE (resolves Blockers 2, 3, 4):**
- The CLASSIFICATION column currently holds entity-routing values (HEAD OFFICE, BEBANG KITCHEN INC, PROJECT COST, plus free-text descriptions). The rename to GOODS/SERVICES is **DISPLAY-HEADER-ONLY**. The internal field key `classification` and `r.classification` references throughout the script REMAIN UNCHANGED.
- This is a 2-site rename (header definitions only): v3.8 lines **70** + **1035** change from `'CLASSIFICATION'` to `'GOODS/SERVICES'`. Line **506** and **668** `hi('CLASSIFICATION')` lookups must also update to `hi('GOODS/SERVICES')` to stay consistent.
- **Window-safety (Warning 2):** Cloud Scheduler is PAUSED at Phase 0.5, so no hourly cycle runs during the rename window. The v2-mode path (`?mode=v2`) is the only thing that would overwrite the header back to CLASSIFICATION — agent must NOT trigger that mode during execution.
- Team-training amendment in Phase 5.3 must say: "GOODS/SERVICES column carries the SAME data as the previous CLASSIFICATION column — billing routing labels in transition. Do not start typing goods names yet — the field still routes."

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 1.1 | Read Suppliers SOA col 20 row 355 (`Remarks` data: "received: 5/16/2026"). If the row's INVOICE DATE col is blank, parse `2026-05-16` as a Date object (not string) and write to INVOICE DATE | MUST_MODIFY: AP Master Suppliers SOA row 355 INVOICE DATE only if blank; cell type = Date not String |
| 1.2 | Delete column 20 (`Remarks`) from Suppliers SOA via `batchUpdate.deleteDimension(dimension=COLUMNS, startIndex=19, endIndex=20)` | MUST_CONTAIN in `output/s255/phase1_log.json`: `suppliers_soa_cols_before: 22, after: 21` |
| 1.3 | Resize Suppliers SOA grid 21 → 19 cols via `batchUpdate.updateSheetProperties` (after the Remarks deletion the remaining cols 20-21 are phantom; resize to 19) | MUST_CONTAIN: grid columnCount = 19 |
| 1.4 | Resize Head Office grid 22 → 19 cols (phantom 20-22 are empty) | MUST_CONTAIN: grid columnCount = 19 |
| 1.5 | Resize CAPEX grid 22 → 20 cols (col 20 = STORE is legit; cols 21-22 are phantom) | MUST_CONTAIN: grid columnCount = 20 |
| 1.6 | **v1.1 — DISPLAY-ONLY rename** `CLASSIFICATION` → `GOODS/SERVICES` in header row 17 (SOA, HO) and row 19 (CAPEX). In `s255_ap_view_hourly_sync_v39.gs`: update string literal at **lines 70 + 1035** only; update `hi('CLASSIFICATION')` → `hi('GOODS/SERVICES')` at **lines 506 + 668**. KEEP internal lowercase `classification` field key everywhere else (COL_IDX, HUMAN_OWNED_COLS, r.classification reads — all unchanged). | MUST_MODIFY: 3 header cells + 4 script source lines. MUST_CONTAIN: grep `r\.classification` in v3.9 source returns >= 10 hits (proving internal key preserved) |
| 1.7 | **v1.1 — Payment Plan rename retargeted** (Blocker 2 — col 23 already named GOODS/SERVICES). Rename Payment Plan tab col 15 from `CLASSIFICATION` to `BILLED ENTITY` (descriptive of actual current data — entity labels). This avoids duplicate header on the tab; col 23 (GOODS/SERVICES — Denise's true goods column) stays as-is. | MUST_MODIFY: Payment Plan header row 3 col 15 = `BILLED ENTITY`; col 23 unchanged |
| 1.8 | Verify no row data is shifted (just header renames) | MUST_CONTAIN: row 18 col 15 still has the original value pre-rename (e.g., "BEBANG ENTERPRISE INC") |

Phase 1 verify script reads grid sizes + header values + asserts.

## Phase 2 — FPM seed intercompany routing fix (v1.1 — tighter predicate, count refined, existingIndex extended)

**v1.1 PREDICATE CORRECTION (resolves Blocker 1):** Fact-check found the original predicate `payee.toUpperCase().startsWith('BEBANG ')` would misroute 18 government-remittance rows (`PAYEE='Bebang Enterprise Inc.'` + CLASSIFICATION contains `SSS/HDMF/PHIC Contribution`). The `category.includes('Intercompany Transfer')` clause never fires because CATEGORY is always the derived bucket label "Head Office". Tightened predicate below.

**v1.1 EXISTING INDEX EXTENSION (resolves Blocker 5):** Adding Intercompany tab without updating the seed's `existingIndex` (line 428 of v3.8) causes unbounded row duplication. Task 2.5 now updates both the mirror-skip list AND existingIndex.

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 2.1 | Create new `Intercompany` tab on AP Master with 19-col schema MATCHING the Suppliers SOA schema (cols 1-19, no STORE). Strict-lock to sam@bebang.ph only. | MUST_CONTAIN: new tab present with `protectedRangeId`; grid columnCount = 19 |
| 2.2 | **v1.1 — Tighter predicate.** In v3.9 script, modify FPM seed routing in `seedNewInvoicesFromFPM_`: route to `Intercompany` tab when ALL: (a) PAYEE matches `/^Bebang\s+(Enterprise\|Kitchen\|Shaw)\s+Inc\.?/i`, (b) CLASSIFICATION matches `/(transfer (of )?fund\|cash sweep\|intercompany)/i`, AND (c) CLASSIFICATION does NOT match `/HDMF\|SSS\|PHIC\|PHILHEALTH\|BIR\|PAG-?IBIG\|CONTRIBUTION\|RENTAL\|FINAL PAY/i`. | MUST_CONTAIN in v3.9 source: regex literals for all 3 predicates AND target tab variable assignment to 'Intercompany' |
| 2.3 | **v1.1 — One-time migration uses same predicate.** Find rows on Head Office tab matching (2.2)'s predicate. Expected count: **~18-25 rows** (down from "35" estimate in v1.0 — fact-check confirmed 18 strict-match + 7-12 fund-transfer rows). MOVE them to Intercompany tab (append + delete from HO). Log AMBIGUOUS rows (matches PAYEE pattern but fails predicates 2.2.b or 2.2.c) to `output/s255/intercompany_ambiguous.json` for Sam review. | MUST_CONTAIN in `output/s255/intercompany_routing_log.json`: `migrated_rows: 15+`. MUST_CONTAIN: `ambiguous_rows` array (criteria: "matches PAYEE but not CLASSIFICATION transfer-keyword OR matches govt-keyword") |
| 2.4 | Banner: Intercompany has NO banner (not in legacy origin set). Banner code path for HO/SOA/CAPEX unchanged. | MUST_CONTAIN: banner code path unchanged for Intercompany |
| 2.5 | **v1.1 — Dual update.** In v3.9 source: (a) add `'Intercompany'` to mirror dedup set so PP tab doesn't pull these; (b) update **line 428** from `['Suppliers SOA', 'Head Office', 'CAPEX'].forEach(...)` to `['Suppliers SOA', 'Head Office', 'CAPEX', 'Intercompany'].forEach(...)` — extends `existingIndex` to recognize Intercompany rows for dedup, preventing unbounded re-append (Blocker 5). | MUST_CONTAIN in v3.9 source: `'Intercompany'` appears in BOTH the mirror-skip list AND the existingIndex tab array at line 428 |
| 2.6 | **v1.1 — Smoke test post-migration:** Trigger 1 hourly cycle via `?fn=refreshAllTabs&dryRun=1` and verify FPM→Intercompany row count growth = 0 (proves existingIndex extension works) | MUST_CONTAIN in `output/s255/phase2_smoke.json`: `intercompany_rows_appended_in_dryrun: 0` |

Phase 2 verify: post-migration row counts (HO ≈ baseline - migrated; Intercompany >= 15); existingIndex extended; ambiguous list captured.

## Phase 3 — Banner refresh (RF-7 fix)

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 3.1 | Add `recomputeBanners_(ss)` function in v3.9 script. For each entry tab (SOA / HO / CAPEX) and Payment Plan, read all data rows, compute: total outstanding (sum of OUTSTANDING col), unique payees count, total items count. Write to row 4 cols B/C/E. | MUST_CONTAIN in v3.9 source: `function recomputeBanners_` AND `range row 4` write |
| 3.2 | Wire `recomputeBanners_(ss)` call at end of `doRefreshAllTabs_v3_` (after seed, before logging the cycle complete) | MUST_CONTAIN in `doRefreshAllTabs_v3_`: `recomputeBanners_(ss)` call |
| 3.3 | Add aging breakdown computation (Not Yet Due / 0-30 / 31-60 / etc.) to banner row 10 | MUST_CONTAIN in v3.9 source: aging breakdown logic |
| 3.4 | After deploy, the FIRST hourly cycle's banner should equal actual sheet totals (not legacy ₱49.82M but full ₱84.16M+ for SOA) | MUST_CONTAIN in `output/s255/banner_verification.json`: SOA banner = sum of outstanding from data |

Phase 3 verify: read banner B4 + compute total from data + assert equality (±₱1 tolerance for FP rounding).

## Phase 4 — Dedup cleanup (v1.1 — invKey normalization specified)

**v1.1 NORMALIZATION (resolves Warning 1):** Dedup audit must use the SAME `invNoVariants_()` function the seed uses (v3.8 line 952), not simple uppercase. Otherwise dupes pass the audit's simple match but fail the seed's variants match → re-seeded next hourly cycle.

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 4.1 | Re-run dedup audit on Suppliers SOA: for each row, compute the normalized key tuple `(payeeKey, invVariant, amt)` using **`invNoVariants_()` from v3.8 line 952** (multi-variant; same fn the seed uses). For each key tuple appearing more than once across rows, identify SOURCE strings. | MUST_CONTAIN in `output/s255/dedup_cleanup_log.json`: `normalization_fn: "invNoVariants_"`, `dupe_groups: [...]`, `total_dupes: N` |
| 4.2 | For each dupe pair/group: delete the Denise PP-sourced row(s); keep the legacy/FPM/Suppliers SOA-sourced one. Use highest-row-first deletion to preserve indices. Cloud Scheduler IS PAUSED (Phase 0.5) so no row-index race. | MUST_CONTAIN: log of deleted row IDs (sheet rowId, not 1-based) |
| 4.3 | Verify post-delete: 0 dupes remain (re-run audit with same normalization fn) | MUST_CONTAIN: `dupes_after: 0` |
| 4.4 | Also dedupe Payment Plan tab if any cross-tab dupes from Denise PP sources (same `invNoVariants_` normalization) | MUST_CONTAIN: PP tab `dupes_after: 0` |

## Phase 5 — 3M Dragon manual-invoice handling

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 5.1 | In v3.9 script's Denise seed function (`seedFromDenisePaymentPlan_`), detect rows where Invoice No starts with "Invoice No." (literal prefix indicating manual entry). Reclassify SOURCE to `Denise PP - Manual` instead of `Denise PP` for these. | MUST_CONTAIN in v3.9 source: `'Denise PP - Manual'` AND `startsWith('INVOICE NO')` (or equivalent) |
| 5.2 | One-time backfill: find the 12 existing rows in AP Master Suppliers SOA / HO with SOURCE='Denise PP' AND Invoice No starting with "Invoice No." — update their SOURCE column to `Denise PP - Manual` | MUST_CONTAIN in `output/s255/3m_dragon_reclassification_log.json`: `rows_reclassified >= 10` |
| 5.3 | Add this SOURCE class to the team-training doc (under "How edits flow" section) | MUST_MODIFY: `.claude/skills/finance-ap/references/team-training-2026-05-14.md` |

## Phase 6 — Angela's staging tabs → Filter views on Payment Plan (v1.1 — col I specified)

**v1.1 COLUMN SPECIFICATION (resolves Warning 4):** Payment Plan tab has TWO STATUS columns:
- **Col I (position 9):** STATUS — mapped to AP-vocab via `mapDeniseToApStatus_` (v3.8 lines 1623-1638). Values: `FOR ONLINE PAYMENT`, `CHECK READY`, `CHECK RELEASED`, etc.
- **Col AB (position 28):** DENISE STATUS — raw Denise-vocab (`Schedule for Online Payment`, `Paid`, etc.)

Filter views MUST target col I (mapped AP-vocab), not col AB (raw).

**Pre-filter sanity check (Task 6.0):** Read 50 rows from Payment Plan col I and verify `mapDeniseToApStatus_` is producing the expected AP-vocab values. If col I shows raw Denise vocab (e.g., "Schedule for Online Payment" leaking through), the mapping function is broken — pause and report to Sam (don't deploy filter views on broken mapping).

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 6.0 | Sanity-check Payment Plan col I value distribution (50-row sample) — confirm AP-vocab present | MUST_CONTAIN in `output/s255/payment_plan_col_i_sample.json`: at least one of `FOR ONLINE PAYMENT`, `CHECK READY`, `CHECK RELEASED` |
| 6.1 | Create Sheets filter view `Scheduled for Online Transfer - Due` on Payment Plan tab: filter where **col I (position 9, STATUS)** = `FOR ONLINE PAYMENT` | MUST_CONTAIN in batchUpdate.addFilterView call: `columnIndex: 8` (0-indexed col I); textCriteria value `FOR ONLINE PAYMENT` |
| 6.2 | Create filter view `Scheduled for Release Check - Due` on PP tab: filter where **col I (position 9)** IN (`CHECK READY`, `CHECK RELEASED`) | MUST_CONTAIN: filter view created with col I criteria |
| 6.3 | Document filter views in team training (which column they filter, what they show) | MUST_MODIFY: training doc |
| 6.4 | Chat Denise + Angela draft (don't auto-send): "your staging tabs are now native filter views on Payment Plan tab; you can switch whenever ready" | MUST_CONTAIN: `output/s255/angela_denise_chat_draft.md` |

## Phase 7 — Status sync wiring to Payment Plan tab

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 7.1 | Add `payment_plan_mirror_disabled` flag constant in v3.9 source (default `false` — keep mirror running for now) | MUST_CONTAIN: `const payment_plan_mirror_disabled = false;` |
| 7.2 | Modify `mirrorDenisePaymentPlanTab_`: if `payment_plan_mirror_disabled` is true, skip the wipe+rebuild | MUST_CONTAIN: `if (payment_plan_mirror_disabled) return ...` early-exit |
| 7.3 | Add 'Payment Plan' as a 4th entry tab in `syncStatusFieldsFromFPM_` — but gated by `payment_plan_mirror_disabled === true` (only sync FROM FPM when mirror is disabled) | MUST_CONTAIN: `if (payment_plan_mirror_disabled) { ... syncStatus for PP tab }` |
| 7.4 | Document the cutover procedure: when Denise says "switch", Sam toggles flag to `true`, mirror stops, status sync starts | MUST_CONTAIN: `output/s255/payment_plan_cutover_runbook.md` |

## Phase 8 — Denise PP sheet ACL audit (v1.1 — explicit handoff mechanics)

**v1.1 HANDOFF MECHANICS (resolves Blocker 8):**

The agent **drafts** decisions, sends Chat to Sam, **EXITS** Phase 8 (creates checkpoint). Sam reviews the draft, edits to final, renames file. Next agent invocation resumes from Phase 8.4.

**`sam_acl_approval.json` schema** (per-decision fields — single boolean was too lossy):
```json
{
  "approved_at": "2026-05-XX...",
  "approved_by": "sam@bebang.ph",
  "roberose": "downgrade_to_commenter" | "keep_writer" | "remove",
  "joevic": "confirm_writer" | "downgrade_to_commenter" | "remove" | "defer",
  "bridge": "keep_writer" | "downgrade_to_commenter",
  "notes": "free-text"
}
```

**Interlock with Phase 9 (also addresses Blocker 8):** Phase 9b deploy can proceed when **either** Phase 8 is DONE **OR** Sam writes `output/s255/phase8_deferred_to_s256.json` with explicit signoff. Phase 9b cannot proceed with Phase 8 in limbo.

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 8.1 | Snapshot current Denise PP ACL (impersonate denise@) | MUST_CONTAIN: 17 entries before changes |
| 8.2 | **v1.1 — Draft + Chat handoff.** Write `output/s255/sam_acl_approval.draft.json` with agent's proposed decisions (default: `roberose: downgrade_to_commenter`, `joevic: defer`, `bridge: keep_writer`). Write `output/s255/joevic_inquiry_draft.md` (Chat message to Denise/James asking about Joevic). Send via `/chat` skill (Chat draft, NOT auto-send). Agent EXITS Phase 8, creates checkpoint via `git commit -am "S255 Phase 8 awaiting Sam approval"`, reports state to Sam, terminates. | MUST_CONTAIN both `.draft.json` and `joevic_inquiry_draft.md`; agent process exits after commit |
| 8.3 | **Sam-side action (NOT agent work):** Sam reviews `.draft.json`, edits to final values, renames to `sam_acl_approval.json`. Next agent invocation (`/execute-plan-bei-erp S255`) detects file present, resumes from Phase 8.4. | MUST_CONTAIN: `sam_acl_approval.json` with `approved_at` non-null and per-decision fields populated |
| 8.4 | Execute approved changes via `drive.permissions().update` (per-decision actions: downgrade = update role; remove = delete permission; keep = no-op). Skip any decision = `defer` (logs to DEFECTS.md instead). | MUST_CONTAIN: `output/s255/acl_change_log.json` with per-decision action + result |
| 8.5 | Update `/finance-ap` skill permissions reference (sync to all 3 mirrors) | MUST_MODIFY: `.claude/skills/finance-ap/references/permissions.md` + `.agent/` + `.agents/` mirrors |

## Phase 9a — Bridge DD readiness + skill updates + script build (v1.1)

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 9a.1 | Audit Bridge access across ecosystem sheets: list sheets where `accountant.outsource@bridge-ph.com` is granted; flag missing access if any | MUST_CONTAIN: `output/s255/bridge_access_audit.json` |
| 9a.2 | Draft DD-package readiness checklist (which AP artifacts Bridge can pull as-is, which need exports) | MUST_CONTAIN: `output/s255/dd_package_checklist.md` |
| 9a.3 | Update `/finance-ap` skill with the DD-readiness section + Bridge access matrix | MUST_MODIFY: `.claude/skills/finance-ap/SKILL.md` |
| 9a.4 | Sync skill to all 3 mirrors (`.claude/`, `.agent/`, `.agents/`) via `pwsh -File scripts/sync_claude_skills_to_codex.ps1 -SkillName "finance-ap"` | MUST_CONTAIN: 3 SKILL.md files identical sha256 |
| 9a.5 | Build v3.9 source → `scripts/google_apps/s255_ap_view_hourly_sync_v39.gs` (includes: recomputeBanners_, tightened Intercompany routing, extended existingIndex, manual-SOURCE class, status-sync wiring, display-only CLASSIFICATION rename) | MUST_CONTAIN: file size in `[86000, 110000]` bytes (v1.1 — tightened from ~80K loose threshold); contains all new functions |
| 9a.6 | Re-run lock test suite (`tmp/finance_ap_audit/audit_2026-05-13/impersonate_lock_test_v2.py`) against the new 16-tab matrix (added Intercompany tab) | MUST_CONTAIN: 96/96 PASS (6 writers × 16 locked tabs) in `output/s255/lock_test_post_v1.json` |
| 9a.7 | Write `output/s255/verify_phase9a.py` | exit 0 |

**Phase 9a gate:** verify_phase9a.py exits 0; build successful; locks intact.

## Phase 9b — Dry-run gate + promote + post-deploy verification + closeout (v1.1)

**v1.1 DRY-RUN GATE (resolves Blocker 9):** Insert dry-run between build and promote-to-v16 to catch bugs before live execution.

| # | Task | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 9b.1 | **v1.1 — Push v3.9 as a NEW DEPLOYMENT** (separate deployment ID, NOT v16 yet). Use `script.projects.deployments.create` with description `"S255 dry-run gate"`. Capture deployment URL into `output/s255/v39_dryrun_deployment.json`. | MUST_CONTAIN: new deployment URL ≠ production deployment URL |
| 9b.2 | **v1.1 — Invoke `?dryRun=1` against new deployment.** Capture full output into `output/s255/v39_dryrun.json`. | MUST_CONTAIN: dry-run output includes recomputeBanners_ trace, Intercompany routing predicate hits, existingIndex size, all phase deliverables |
| 9b.3 | **v1.1 — Verify dry-run output.** Assert: (a) Intercompany routing matches 0 govt-remittance rows, (b) existingIndex includes 4 tabs (3 + Intercompany), (c) banner totals match data sum (±₱1), (d) no errors in log. If ANY assertion fails: STOP, report to Sam, delete dry-run deployment, do NOT promote. | MUST_CONTAIN: `output/s255/v39_dryrun_verify.json` with `all_assertions_passed: true` |
| 9b.4 | **Promote dry-run deployment to v16** (production). Use `script.projects.deployments.update` on production deployment ID. Old v3.8 deployment becomes v15 (archived but still exists for rollback). | MUST_CONTAIN: `output/s255/v39_deployment.json` with `versionNumber: 16` |
| 9b.5 | **v1.1 — RESUME Cloud Scheduler trigger** (per Blocker 6 — paused at Phase 0.5): `gcloud scheduler jobs resume <job-name>`. Log to `output/s255/cloud_scheduler_pause_log.json` with `resumed_at`. | MUST_CONTAIN: `resumed: true` in log |
| 9b.6 | Trigger live sync immediately (don't wait for next xx:12 PHT cycle): `curl '<web_app_url>?key=bei-ap-sync-2026-04&fn=refreshAllTabs'` | MUST_CONTAIN: HTTP 200 + `output/s255/post_deploy_sync.json` |
| 9b.7 | Post-deploy verification (within 5 min of 9b.6): (a) banner totals match, (b) Intercompany row count stable (no growth), (c) PP mirror still works, (d) status sync still runs, (e) sync_log_v3 has new entries | MUST_CONTAIN: `output/s255/post_deploy_verify.json` with all 5 assertions PASS |
| 9b.8 | Write `output/s255/SUMMARY.md` (11-item completion table) | MUST_CONTAIN: each of 11 backlog items marked DONE or DEFERRED with explanation |
| 9b.9 | Write `output/s255/DEFECTS.md` (empty list if clean) | MUST_CONTAIN: file exists |
| 9b.10 | Commit + push: `git add -f docs/plans/2026-05-19-sprint-255-ap-system-hardening-team-requests.md docs/plans/SPRINT_REGISTRY.md output/s255/ scripts/google_apps/s255_ap_view_hourly_sync_v39.gs .claude/skills/finance-ap/ .agent/skills/finance-ap/ .agents/skills/finance-ap/` (named files only — no broad add) | git status clean |
| 9b.11 | Create PR via `GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms --base production --head s255-ap-system-hardening-team-requests` (rebased onto latest origin/production first) | MUST_CONTAIN: PR URL in `output/s255/pr.json` |
| 9b.12 | Update plan YAML `status: COMPLETED` + `completed_date: 2026-05-XX` + populate `execution_summary` | MUST_MODIFY: plan file |
| 9b.13 | Update SPRINT_REGISTRY.md S255 row status → COMPLETED + PR # | MUST_MODIFY: registry |
| 9b.14 | **v1.1 — Worktree closeout GATED.** Only proceed if Phase 9b.7 verification all PASS. If any FAIL: keep worktree, follow rollback runbook below. Then: `git status --short` clean, then `git worktree remove F:/Dropbox/Projects/BEI-ERP-s255-ap-system-hardening-team-requests` (without `--force`). | MUST_CONTAIN: worktree removed cleanly; backup at `output/s255/script_source_backup_v38.gs` REMAINS committed (survives closeout per Blocker 7) |
| 9b.15 | STOP — report PR # to Sam, do NOT merge | Agent terminates |

## Failure Response

- **Mode A (script bug):** file in DEFECTS.md, fix code, re-run verify script, re-deploy. Do NOT downgrade assertions.
- **Mode B (plan bug — wrong assertion):** investigate, normalize plan inline per Ground-Truth Lock, continue. Don't bump tolerances silently. **v1.1:** any inline normalization must be appended to the v1.1 amendment block above with date stamp + rationale (don't silently edit phase tasks).
- **Mode C (brittleness — intermittent timeout):** fix the LIBRARY (split sync into smaller batches), not the spec. If ≥3 library-level fixes happen, emit `output/s255/LIBRARY_IMPROVEMENTS.md`.
- **Mode D (v1.1 — dry-run failure at Phase 9b.3):** STOP. Delete the dry-run deployment via `script.projects.deployments.delete`. Do NOT promote. Report to Sam with the dry-run output. Production stays on v3.8.
- **Mode E (v1.1 — post-deploy verification failure at Phase 9b.7):** Follow Rollback Runbook below. Do NOT proceed to worktree closeout.

## Rollback Runbook (v1.1 — new section, resolves Blocker 7)

**Trigger conditions** (any one fires rollback):
- Phase 9b.7 verification: banner totals mismatch ≥ ₱100 (FP tolerance is ₱1)
- Intercompany row count grows by >0 per dry-run (Phase 2.6) or per hourly cycle post-deploy
- PP mirror produces 0 rows post-deploy when v3.8 produced >400
- `_sync_log_v3` shows error rate > 0 in first 2 cycles
- Status sync stops writing
- Sam reports broken sheet behavior

**Rollback steps** (run from worktree, scheduler paused):
1. Pause Cloud Scheduler again (if 9b.5 had resumed it): `gcloud scheduler jobs pause <job-name>`
2. Read backup: `cat output/s255/script_source_backup_v38.gs` (committed at Phase 0.4 — survives worktree closeout)
3. Push v3.8 source to live Apps Script via `script.projects.updateContent` with the backup as the Code.gs file
4. Promote to new version (will become v17): `script.projects.deployments.update` on production deployment ID with `versionNumber: 17` (rolling forward to a known-good v3.8 state — Apps Script doesn't allow rolling back to older versionNumber)
5. Verify rollback: `curl '<web_app_url>?key=bei-ap-sync-2026-04&fn=refreshAllTabs&dryRun=1'` shows v3.8 behavior
6. Resume scheduler: `gcloud scheduler jobs resume <job-name>`
7. Log rollback to `output/s255/rollback_log.json` with `{rolled_back_at, reason, from_version: 16, to_version: 17}`
8. Mark plan status `ROLLBACK_v3.8` in YAML; update registry
9. Open Chat to Sam with rollback report; do NOT close worktree (Sam decides next steps)

**Success criteria:**
- v3.8 logic running again (banner totals match pre-v3.9 baseline)
- Hourly cycle continues without errors
- Sam acknowledges rollback in Chat

## Verify Script Assertions (v1.1 — new section, resolves Warning 6)

Each `verify_phaseN.py` must implement the following assertions. Agent writes these as Python scripts in Phase 0.10, 1.x, 2.x, etc.

**verify_phase0.py:**
- `output/s255/baseline_sha.txt` exists and matches `git rev-parse origin/production`
- `output/s255/script_source_backup_v38.gs` exists, size in `[85000, 95000]` bytes
- `output/s255/cloud_scheduler_pause_log.json` shows `paused: true`
- `output/s255/baseline_state.json` has keys for 18 tabs
- `output/s255/S255_SURFACE_OWNERSHIP_MATRIX.csv` has ≥ 10 data rows
- 3 SKILL.md mirrors have "Bridge" section (≥ 5 grep hits each)

**verify_phase1.py:**
- AP Master Suppliers SOA grid columnCount = 19
- AP Master Head Office grid columnCount = 19
- AP Master CAPEX grid columnCount = 20
- Suppliers SOA row 17 col 15 header value = `GOODS/SERVICES` (display rename)
- Suppliers SOA row 355 INVOICE DATE column is a Date type (not string)
- Suppliers SOA row 18 col 15 value preserved (pre-rename — proves data not shifted)
- Payment Plan row 3 col 15 header = `BILLED ENTITY` (NOT `GOODS/SERVICES` — that's col 23)
- Payment Plan row 3 col 23 header = `GOODS/SERVICES` (unchanged)

**verify_phase2.py:**
- AP Master `Intercompany` tab exists with `protectedRangeId`
- Intercompany grid columnCount = 19
- `output/s255/intercompany_routing_log.json` shows `migrated_rows >= 15`
- `output/s255/intercompany_ambiguous.json` exists (may be empty array)
- v3.9 source line corresponding to existingIndex includes `'Intercompany'` (grep `existingIndex.*Intercompany`)
- v3.9 source contains all 3 predicate regexes (PAYEE, transfer-keyword, govt-keyword-excluder)
- `output/s255/phase2_smoke.json` shows `intercompany_rows_appended_in_dryrun: 0`

**verify_phase3.py:**
- v3.9 source contains `function recomputeBanners_`
- v3.9 source `doRefreshAllTabs_v3_` contains `recomputeBanners_(ss)` call
- Banner SOA row 4 totals match data sum (±₱1)
- Banner HO row 4 totals match data sum (±₱1)
- Banner CAPEX row 4 totals match data sum (±₱1)
- Aging breakdown computed (row 10 has aging values, not stale)

**verify_phase4.py:**
- `output/s255/dedup_cleanup_log.json` shows `normalization_fn: "invNoVariants_"`
- `dupes_after: 0` on Suppliers SOA
- `dupes_after: 0` on Payment Plan tab
- Deleted rows are Denise-PP-sourced (not legacy/FPM)

**verify_phase5.py:**
- v3.9 source contains `'Denise PP - Manual'` SOURCE class
- `output/s255/3m_dragon_reclassification_log.json` shows `rows_reclassified >= 10`
- Team-training doc references the new SOURCE class

**verify_phase6.py:**
- `output/s255/payment_plan_col_i_sample.json` shows AP-vocab values present in col I
- 2 filter views created on Payment Plan tab via batchUpdate.addFilterView
- Filter view 1 targets col I (columnIndex: 8) with `FOR ONLINE PAYMENT`
- Filter view 2 targets col I with `CHECK READY` OR `CHECK RELEASED`

**verify_phase7.py:**
- v3.9 source contains `const payment_plan_mirror_disabled = false`
- v3.9 source `mirrorDenisePaymentPlanTab_` has early-exit when flag = true
- v3.9 source `syncStatusFieldsFromFPM_` handles PP tab when flag = true
- `output/s255/payment_plan_cutover_runbook.md` exists

**verify_phase8.py:**
- `sam_acl_approval.json` exists with per-decision fields populated
- `acl_change_log.json` shows actions performed for each non-defer decision
- `/finance-ap` skill permissions reference updated in all 3 mirrors

**verify_phase9a.py:**
- `bridge_access_audit.json` exists with sheet-by-sheet access matrix
- `dd_package_checklist.md` exists with ≥ 5 checklist items
- 3 SKILL.md mirrors identical sha256
- v3.9 source file size in `[86000, 110000]` bytes
- Lock test result: 96/96 PASS

**verify_phase9b.py:**
- `v39_dryrun.json` exists with no errors
- `v39_dryrun_verify.json` shows `all_assertions_passed: true`
- `v39_deployment.json` shows `versionNumber: 16`
- `cloud_scheduler_pause_log.json` shows both `paused_at` AND `resumed_at` populated
- `post_deploy_sync.json` shows HTTP 200
- `post_deploy_verify.json` shows all 5 assertions PASS
- `SUMMARY.md` has 11-item completion table
- `output/s255/script_source_backup_v38.gs` still present (committed evidence — confirms rollback survival)
- Plan YAML status updated, registry updated
- PR URL in `pr.json`

## Notes / Out-of-scope (deferred to future sprints)

- **Frappe migration of AP Master**: when full ERP cuts over (Feb 2026 go-live target), AP Master gets replaced by `tabPurchase Invoice` + custom AP dashboard. Not in S255.
- **3M Dragon procurement onboarding**: forcing 3M Dragon to submit invoices via Compliance AppSheet is a process change requiring SCM + supplier outreach. Not in S255 (we just classify the manual rows differently).
- **Bridge expanded write access**: Sam may want to give Bridge writer on more sheets for DD edits. Decide ad-hoc, not in S255.
- **Angela's request for "formula/automated computation"**: she mentioned wanting a column with automated math. Defer until we know the exact formula she needs.
- **Denise's actual cutover from her standalone sheet to Payment Plan tab**: S255 wires the path; Denise herself triggers when ready (no sprint for the cutover — Sam manually toggles flag).
