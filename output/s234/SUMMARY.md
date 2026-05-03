# S234 — COMPLETED (2026-05-03)

**Sprint:** S234 — Ordering Schedule Defaults Defense + Smoke Test Repoint + Data Foundation
**PR:** [#716](https://github.com/Bebang-Enterprise-Inc/hrms/pull/716) (merged `29a1b5857`)
**Closeout PR:** chore/s234-closeout (this branch)
**Plan:** `docs/plans/2026-05-03-sprint-234-ordering-schedule-defaults-and-data.md`

## Outcome

20+ consecutive `/merge-bei-erp` cycles had been smoke-failing on
`validate_order_schedule&store=Estancia` returning `next_cold_delivery=null`
+ `next_dry_delivery=null`. Lane A fixed the synthesis; Lane B repointed the
smoke to a store with real cadence data so the canary actually canaries.
Lane C built the import surface so logistics can populate cadence without
engineering follow-up.

## What shipped

| Lane | Artifact | Status |
|---|---|---|
| **A. Code fix** | `327e9b11f` — `hrms/api/store.py:_get_next_deliveries` defaults dict synthesizes `str(add_days(today, 2))` / `str(add_days(today, 3))`; `cold_interval` / `dry_interval` deliberately omitted (REC-ENGINE-DRIFT defense from v2 audit) | ✅ merged |
| **B. Smoke repoint** | Local-only edit to `.claude/skills/merge-bei-erp/SKILL.md`, mirrored to `.agent/.agents`. Repoints smoke probe from Estancia (no entries) to `ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC` (real cadence) | ✅ local (gitignored by design) |
| **C. Data foundation** | `cfe967ae5` — `scripts/s234_seed_delivery_schedule.py` (savepoint+dry-run-default), `scripts/s234_publish_next_week_cron.py` (DISABLED_BY_DEFAULT), `data/operational/delivery_cadence_template.csv`, `docs/operations/delivery-schedule-runbook.md`, `output/s234/verification/doctype_schema.json` | ✅ merged |

## Phase D post-deploy validation (all PASS)

### D-T1 — 3-cycle ARANETA smoke
```
cycle 1: PASS cold=2026-05-04 dry=2026-05-04 schedule_source=fallback_last_week
cycle 2: PASS cold=2026-05-04 dry=2026-05-04 schedule_source=fallback_last_week
cycle 3: PASS cold=2026-05-04 dry=2026-05-04 schedule_source=fallback_last_week
```
Evidence: `output/l3/s234/smoke_3_cycle_log.txt`

### D-T2 — Estancia post-deploy probe (Lane A canary)
```json
{
  "next_cold_delivery": "2026-05-05",
  "next_dry_delivery": "2026-05-06",
  "days_to_cold": 2,
  "days_to_dry": 3,
  "schedule_source": "default"
}
```
ISO dates returned (was `null` before deploy). Evidence: `output/l3/s234/api_probe_estancia_after.json`

### D-T2 — ARANETA post-deploy probe
```json
{
  "next_cold_delivery": "2026-05-04",
  "next_dry_delivery": "2026-05-04",
  "schedule_source": "fallback_last_week"
}
```
Real schedule data preserved (Lane A only modifies the defaults branch). Evidence: `output/l3/s234/api_probe_araneta_after.json`

### D-T2.5 — 49-store state_after probe
```
{
  "by_schedule_source": {
    "fallback_last_week": 2,   // ARANETA + AYALA UP TOWN CENTER
    "default": 47              // synthesized via Lane A add_days
  },
  "stores_with_null_dates": []
}
```
**0 stores with null dates.** All 49 stores return ISO dates post-deploy.
Evidence: `output/s234/verification/state_after.json`

### D-T2.6 — state_verification.json
Read-only attestation: 0 production writes, 0 mutations, deploy SHA
recorded. Evidence: `output/l3/s234/state_verification.json`

### D-T3 — Canonical postcheck
```
[RESULT] ALL CANONICAL — no action required
Stores checked: 49
Violations: 0
```
Parity with preflight. Lane A defaults-dict change introduced 0 new
violations. Evidence: `output/s234/verification/canonical_postcheck.log`

## Behavioral impact (verified post-deploy)

- **47 default-stores**: `next_cold_delivery` `null` → `<today + 2 days>` (e.g., 2026-05-05). `next_dry_delivery` `null` → `<today + 3 days>` (2026-05-06). `schedule_source="default"` preserved.
- **2 schedule-published stores** (ARANETA, AYALA UP TOWN CENTER): UNCHANGED — still served from the entries branch.
- **Recommendation engine**: `coverage_window_days` math UNCHANGED (the v2 `MUST_NOT_CONTAIN` guard prevented the 2.3-3.5× `suggested_qty` inflation that v1 would have caused).
- **Smoke probe**: now actually canaries the schedule pipeline. A null return means the publish pipeline genuinely broke (vs the previous Estancia probe which always returned null because that store has no entries).

## Risk & rollback

- ✅ Inventory regression averted — v2 audit caught the `cold_interval=7`/`dry_interval=7` regression candidate and dropped it. Production behavior unchanged.
- ✅ Canonical drift averted — 0 new violations in postcheck.
- ✅ Schedule pipeline canary live — Lane B repoint targets a store with real cadence.
- Rollback: `git revert 327e9b11f cfe967ae5` + redeploy. No data restore needed (read-only sprint).

## Future work (deferred)

- **Logistics cadence handoff**: logistics fills `data/operational/delivery_cadence_<YYYY-MM-DD>.csv`, engineer dry-runs the seeder, then `--no-dry-run` writes (DM-2 savepoint protected).
- **Cron live-launch**: `scripts/s234_publish_next_week_cron.py` is DISABLED_BY_DEFAULT. Activation requires (1) logistics signoff on stable cadence for all 47 default-stores, (2) Sam approval, (3) wiring into `hrms/hooks.py` `scheduler_events.weekly`. Tracked as a follow-up sprint.

## Files

- Plan: `docs/plans/2026-05-03-sprint-234-ordering-schedule-defaults-and-data.md`
- Audit: `output/plan-audit/sprint-234-ordering-schedule-defaults-and-data/AUDIT_REPORT.md`
- PR body: `output/s234/PR_BODY.md`
- Pre-fix probe: `output/s234/verification/state_before.json`
- Post-deploy 49-store probe: `output/s234/verification/state_after.json`
- Smoke proof (live): `output/s234/verification/smoke_repoint_proof.txt`
- Canonical postcheck: `output/s234/verification/canonical_postcheck.log`
- DocType schema: `output/s234/verification/doctype_schema.json`
- 3-cycle smoke log: `output/l3/s234/smoke_3_cycle_log.txt`
- Estancia post-deploy: `output/l3/s234/api_probe_estancia_after.json`
- ARANETA post-deploy: `output/l3/s234/api_probe_araneta_after.json`
- State verification: `output/l3/s234/state_verification.json`
- Runbook: `docs/operations/delivery-schedule-runbook.md`
- Seeder: `scripts/s234_seed_delivery_schedule.py`
- Cron skeleton: `scripts/s234_publish_next_week_cron.py`
