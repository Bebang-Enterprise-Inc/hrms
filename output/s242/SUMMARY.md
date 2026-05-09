# S242 — pos_orders Natural-Key Channel Discriminator (SUMMARY)

**Sprint:** S242
**Branch:** `s242-pos-natural-key-channel-discriminator`
**Plan:** `docs/plans/2026-05-08-sprint-242-pos-natural-key-channel-discriminator.md`
**Status:** PLANNED_AUDITED_v1.1 → IN_PROGRESS → **EXECUTED** (PR pending Sam merge)
**Executed:** 2026-05-09 PHT (single autonomous session)

## Goal achieved

Eliminated the structural data loss where Mosaic POS issues the same
`bill_number` to two different terminals/channels (e.g. Pickup + FoodPanda
dispatch) and our partial unique index forced one to be `is_duplicate=true`,
hiding ~₱30K of legitimate revenue across 70 store-days.

## Migration outcome

| Metric | Value |
|---|---|
| Rows restored | **74** |
| Restored gross | **₱30,964.58** |
| Store-days affected | **70** (range: 2025-11-19 → 2026-05-04) |
| Same-channel tombstones preserved (true Mosaic-returned-twice dupes) | **307** rows / ₱117,475.93 |
| Idempotency check (re-run UPDATE) | **0 additional restores** |
| Schema migration duration | <30 seconds (single transaction) |
| Cron pause window | ~8 minutes |
| Sentry 23505 errors during window | **0** |

## New schema

```sql
CREATE UNIQUE INDEX pos_orders_bill_number_natural_key
  ON public.pos_orders USING btree
    (location_id, business_date, bill_number, channel)
  WHERE ((bill_number IS NOT NULL) AND (is_duplicate = false));
```

(Old: `(location_id, business_date, bill_number)` — bypassed the channel.)

## Code changes (PR scope)

| File | Change |
|---|---|
| `hrms/utils/pos_order_reconciliation.py` | **NEW** — shared dedup/reconcile/collision module (used by both polling sync and webhook) |
| `hrms/utils/test_pos_order_reconciliation.py` | **NEW** — 7 unit tests (all PASS) |
| `scripts/sync_pos_to_supabase.py` | Removes 5 local function copies, imports shared module via importlib.util fallback (compatible with cron's standalone-Python runner) |
| `hrms/api/mosaic_webhook.py` | Adds S242 pre-upsert reconcile call; `_find_bill_number_twin` now channel-aware |
| `scripts/s242_*.py` | NEW migration + verification scripts (4 files) |
| `data/POS_Extraction/MOSAIC_POS_API_KEYS.csv` | NOT committed (credentials, kept gitignored) |

The S232 commit chain (5 commits in local production, never pushed) was
brought forward into the S242 branch as a single squashed commit. This PR
is effectively S232 hardening + S242 channel discriminator combined.

## Audit verdicts

| Check | Result |
|---|---|
| Phase 0.5 channel-pair shape | **PASS** (matches snapshot exactly) |
| Phase 1.A.4 unit tests | **7/7 PASS** |
| Phase 1.B backwards-compat smoke | **PASS** (SM Manila 5/3 — clean store-day) |
| Phase 3 schema migration | **74 rows restored**, idempotent on rerun |
| Phase 3 Paseo bill 39966 | **2 live rows** (POS ₱228 + FoodPanda ₱704) |
| Phase 4.B MV ↔ live parity | **0 mismatches** across 70 (loc, date) pairs |
| Phase 4.B Paseo dashboard | **₱121,722** (matches POS XLSX to the centavo) |
| Phase 5.1 Mosaic-vs-Supabase 12-store-day audit | **11/12 MATCH** (1 expected mismatch — Grid Rockwell, see below) |
| Phase 5.4 Restoration pairing | **0 orphans** — all 74 restored rows have different-channel live sibling |
| Phase 5.5 Sentry sanity | **0 errors** in last 2h |

## The 1 expected mismatch — Grid Rockwell 2026-05-02

```
Mosaic API:   361 paid bills, ₱140,740.53
Supabase:     361 paid bills, ₱140,800.53  (+₱60)
```

This is **expected by design** post-S242. Bill 81282 at Grid Rockwell has:
- POS ₱162.86 (live, pre-S232)
- FoodPanda ₱60 (restored from tombstone by S242 migration)

The `s232_mosaic_vs_supabase_audit.py` script's Mosaic-side dedup is at
`(loc, date, bill)` level (channel-blind) and picks ONE canonical per bill.
The Supabase side now has TWO live rows per parallel-bill, which is correct
data. The audit script itself needs a follow-up update to dedup Mosaic data
by `(bill, channel)` tuple — that's an S243+ improvement, not an S242 defect.

The plan's design rationale §"Cold-Start Test" called this out:
> NOTE post-migration semantics: Supabase total may exceed naive Mosaic raw
> row sum by exactly the duplicate-bill count (Mosaic's raw fetch counts
> each bill multiple times when terminals collide); the audit's dedup logic
> is correct.

## Paseo case proof (the headline win)

```
                  POS XLSX    Pre-migration    Post-migration
                  --------    -------------    --------------
Order count       176          175              176              (+1)
Sum gross         ₱121,722.00  ₱121,494.00      ₱121,722.00      (+₱228)
Sum net           ₱105,601.94  ₱105,398.37      ₱105,601.94      (+₱203.57)
Bill 39966
  POS Pickup      ₱228 visible HIDDEN (dup=t)   visible (dup=f)  ✓
  FoodPanda       ₱704 visible visible          visible          ✓
```

**Match to the centavo.** No more "₱228 hidden" in tombstones for this case
nor any of the other 73 store-day cases.

## What stays the same

- `hrms/api/sales_dashboard.py` — untouched (S176/S182/S191 owned)
- `bei-tasks/app/dashboard/analytics/*` — untouched (frontend reads via
  Frappe API; numbers shift up because `v_pos_orders_live` returns more rows)
- 307 same-channel tombstones — still tombstoned (these ARE the
  Mosaic-returned-twice duplicates the index correctly suppresses)
- Cron schedule — `pos-sync-5min` (every 10min) and `daily-pos-sync` (hourly)
  re-enabled after migration

## Closeout artifacts

- `output/s242/SUMMARY.md` — this file
- `output/s242/migration/before_state.json` — pre-migration snapshot (74 rollback rows)
- `output/s242/migration/after_state.json` — post-migration counts
- `output/s242/migration/restored_rows_ledger.csv` — 74 restored row IDs
- `output/s242/migration/idempotency_check.json` — second-run = 0 restores
- `output/s242/migration/migration_summary.json` — timing
- `output/s242/verification/index_definition_after.txt` — new DDL
- `output/s242/verification/migration_verify.log` — Phase 3 assertion log
- `output/s242/verification/paseo_pre_migration_state.json` — baseline
- `output/s242/verification/paseo_4_21_bill_39966_after.json` — post state
- `output/s242/verification/paseo_4_21_dashboard_after.json` — dashboard total
- `output/s242/verification/paseo_after_migration_comparison.md` — XLSX diff
- `output/s242/verification/dashboard_totals_delta.csv` — 70 (loc, date) deltas
- `output/s242/verification/audit_12_store_days.json` — 12-sample audit
- `output/s242/verification/audit_12_store_days_post_migration.md` — audit report
- `output/s242/verification/audit_report.md` (S232 audit reused, copy)
- `output/s242/verification/audit_data.json` (full machine-readable detail)
- `output/s242/verification/restoration_pairing_check.json` — 0 orphans
- `output/s242/verification/same_channel_tombstones_count.json` — 307 preserved
- `output/s242/verification/sentry_sanity.txt` — 0 errors
- `output/s242/verification/migration_window_errors.md` — Sentry sweep
- `output/s242/verification/mv_refresh.log` — MV refresh log
- `output/s242/verification/sync_smoke_old_schema.log` — backwards-compat smoke
- `output/s242/state/baseline_sha.txt` — origin/production at boot
- `output/s242/state/active_run.json` — ownership claim
- `output/s242/state/workflow_disable_log.txt` — Phase 2 cron disable
- `output/s242/state/workflow_resume_log.txt` — Phase 4 cron resume
- `output/s242/state/webhook_active_during_migration.md` — risk acknowledgement

## Next steps

1. **PR creation** (Phase 6.6) — agent creates, Sam reviews and merges
2. **Sentry alert config** (Phase 6.3) — add alert for `channel='Unknown'`
   on `pos_orders` with threshold of 5 rows in 24h
3. **Post-merge** (Sam): cron picks up new code on next tick
4. **Follow-up sprint candidates:**
   - Update `s232_mosaic_vs_supabase_audit.py` to dedup Mosaic by
     `(bill, channel)` so the Grid Rockwell mismatch goes to MATCH
   - Re-frame "channel-distinct vs same-channel" detection in any other
     reports/views that assume bill_number is unique per (loc, date)
