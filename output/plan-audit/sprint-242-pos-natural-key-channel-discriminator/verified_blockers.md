# S242 Plan Audit — Verified Blockers

**Audit date:** 2026-05-08
**Plan:** `docs/plans/2026-05-08-sprint-242-pos-natural-key-channel-discriminator.md`
**Canonical Gate:** SKIPPED (canonical_scope=none, verified — pure Supabase pos_orders schema; no Frappe master data, no GL touches)

## Audit summary

| Auditor | Status | Findings (raw) | Verified blockers |
|---|---|---|---|
| System Architecture | COMPLETED | 6 CRITICAL, 6 WARNING, 6 INFO | 4 confirmed CRITICAL, 1 STALE, 1 partial |
| Deployment & QA | TIMED OUT | partial output captured webhook concern | 1 confirmed CRITICAL (webhook) |
| Team Orchestration | COMPLETED | 0 CRITICAL, 2 WARNING, 3 INFO | All warnings retained as polish items |
| Cold-Start | COMPLETED | 0 CRITICAL, 2 WARNING | Both retained |
| Zero-Skip | TIMED OUT | no findings written | Self-audit: plan has MUST_MODIFY/MUST_CONTAIN per task ✓ |
| **Code verifier (lead-driven)** | COMPLETED | direct SQL + file grep | C1 system-arch STALE, C3/C4 confirmed |

## CRITICAL blockers (must fix before GO)

### B1 — `mosaic_webhook.py` is an undeclared independent writer to `pos_orders`
**Source:** system-arch C4 + deployment-qa partial output + lead direct verification (`grep` on `hrms/api/mosaic_webhook.py`)
**Evidence:**
- `hrms/api/mosaic_webhook.py:380` defines `_resolve_channel` (same as polling sync)
- Line 410: `"channel": _resolve_channel(order)` — sets channel on incoming row
- Line 477: `f"{SUPABASE_URL}/rest/v1/pos_orders"` — direct PostgREST upsert
- Webhook does NOT call `reconcile_existing_ids`, `_dedupe_incoming_by_natural_key`, or `_resolve_id_collisions`
- Webhook upsert uses `merge-duplicates` on PRIMARY KEY `id` only

**Why it's a blocker:** After the partial unique index is extended to include `channel`, any webhook delivery whose `(loc, date, bill, channel)` matches an existing live row (with a different `id` from Mosaic) will fail with 23505 — the EXACT bug S232 fixed for the polling sync. The plan only updates the polling sync; it doesn't address the webhook.

**Fix required:** Phase 2 must extend the sync logic to `hrms/api/mosaic_webhook.py` as well. Either:
- (a) Refactor the dedup/reconcile/collision functions into a shared module that both `scripts/sync_pos_to_supabase.py` AND `hrms/api/mosaic_webhook.py` import, OR
- (b) Inline the reconcile + collision logic into the webhook's upsert path
- (c) Add a Sentry alert that surfaces 23505 webhook failures + a manual reconciliation script for the affected orders

**Severity:** CRITICAL — without this, every dual-channel order that arrives via webhook in the same minute as a poll sync will be silently dropped.

### B2 — Migration timing ignores 5-min + 10-min crons + always-on webhook
**Source:** system-arch C3 + lead direct verification (`.github/workflows/`)
**Evidence:**
- `pos-sync-5min.yml`: cron `*/10 2-16 * * *` (every 10 minutes, 10 AM–midnight PHT)
- `daily-pos-sync.yml`: nightly catch-up
- `daily-anomaly-report.yml`, `hourly-consumption-to-frappe.yml`, `s189-webhook-health.yml`, `s189-webhook-registration-reconciler.yml` — additional pos_orders readers
- `mosaic_webhook.py` — always-active writer

**Why it's a blocker:** The plan assumes "no deploy required, sync auto-uses on next cron tonight." In reality:
- The 10-minute cron may run DURING the migration's transaction window. If it lands BEFORE the index is recreated, it inserts with the OLD index (succeeds). If it lands AFTER, it tries the NEW index (succeeds). But if it's MID-transaction, it locks-out other writers (BEGIN takes ACCESS EXCLUSIVE on the index).
- More critically: **the OLD sync code is in production until Phase 2's sync code is committed AND the GitHub Actions runner picks it up on the next cron tick**. Between schema migration and sync code deployment, the 5-min cron runs the OLD sync code against the NEW schema → may fail or silently skip rows.

**Fix required:**
1. Sequence the work: deploy the sync code update FIRST (PR + merge), then migrate the schema. NOT the order in the current plan.
2. OR: pause both crons (`workflow_dispatch` disable) for the migration window (~15 minutes total: backup + DDL + restore + smoke).
3. OR: write a "migration window blocker" that disables the 5-min and 10-min cron concurrency keys before Phase 1, re-enables after Phase 4 verifies green.

**Severity:** CRITICAL — schema-without-code OR code-without-schema both produce silent data loss during the gap.

### B3 — Restoration tolerance bands cannot survive continuous ingestion
**Source:** system-arch C6 + lead reasoning
**Evidence:**
- Plan §"count_method" locks `rows_to_restore = 74` from a 2026-05-08 snapshot
- Plan §"Phase 0.5" requires drift < 5% (so 70-78 rows acceptable)
- 5-minute cron runs continuously; new tombstones could be created between `before_state.json` and the migration RUN

**Why it's a blocker:** Between Phase 0 baseline capture and Phase 1 migration execution, the cron may write new same-channel tombstones (which should NOT be restored) or new channel-distinct tombstones (which SHOULD be restored — but they're not in the locked count). A 5% tolerance accepts ±4 rows; a 60-minute Phase 0+1 window during peak hours easily produces >4 new tombstones across 47 stores.

**Fix required:**
- Tighten the migration to use a SINGLE locked SQL transaction that re-computes `to_restore` from the live state at execution time. The Phase 1 SQL already does this with the CTE — the issue is that Phase 0's "drift check" against a stale snapshot is meaningless.
- Replace Phase 0.5's "rows_to_restore_within_tolerance" check with a SHAPE check: are the channel pairs (POS↔FoodPanda, POS↔GrabFood, etc.) the same shape as the locked snapshot? Drift in count is fine; drift in channel-pair distribution is suspicious.
- Document that the restored count in `restored_rows_ledger.csv` is the AUTHORITATIVE count, not the Phase 0 snapshot.

**Severity:** CRITICAL — if not fixed, the agent may STOP at Phase 0.5 due to natural drift even though the migration would be perfectly safe.

### B4 — Phase 4 dashboard delta verification is structurally fragile
**Source:** system-arch C2 + lead direct verification
**Evidence:**
- Lead direct query confirms `sales_dashboard_daily_store_metrics` reads `v_pos_orders_live` (which DOES filter `is_duplicate=false`) — system-arch C1 is **STALE** ✓
- Plan §"Phase 3.3" requires `total_delta_gross >= 30000 AND <= 32000`
- Continuous ingest between BEFORE snapshot and AFTER MV refresh adds new sales that ALSO contribute to the delta

**Why it's a blocker:** During the migration window, the cron may sync new bills for today (2026-05-08) that bump the dashboard total beyond the expected ~₱30,964 restoration. The verifier could falsely fail when nothing's wrong, OR falsely pass when something IS wrong (if some restored rows fail to flip).

**Fix required:**
- Compute delta per (location_id, business_date) BEFORE and AFTER, restricted to dates ≤ 2026-05-07 (closed business dates only — exclude today since today is partial and changing).
- Sum those deltas. Expected total: sum of `gross_sales` from `restored_rows_ledger.csv`. Tolerance: ±₱1.
- This approach is not affected by any new same-day ingestion.

**Severity:** CRITICAL — verification logic must be precise, otherwise green/red status is meaningless.

## WARNING blockers (should fix before GO)

### W1 — `CREATE UNIQUE INDEX` lacks `IF NOT EXISTS`
**Source:** system-arch I6
**Evidence:** Phase 1.1 SQL: `CREATE UNIQUE INDEX pos_orders_bill_number_natural_key ON ...`
**Fix:** `CREATE UNIQUE INDEX IF NOT EXISTS pos_orders_bill_number_natural_key ON ...`. Plan §"idempotency check" assumes second run is a no-op, but the second `CREATE` would fail without `IF NOT EXISTS`.

### W2 — Plan cites `freshness/reintegration gate` that doesn't exist as a section
**Source:** team-orchestration W2
**Fix:** Either add a Freshness/Reintegration section under Anti-Rewind (define what "rebase before merge" means for this PR) or remove the citation in §Failure Response Mode B.

### W3 — Phase 4.1 writes to S232's namespace (`output/s232/audit_report.md`)
**Source:** team-orchestration I3
**Fix:** Phase 4.1 should write to `output/s242/verification/audit_12_store_days_post_migration.md` (s242 namespace). The S232 report should remain a historical artifact.

### W4 — Cold-Start cited line range `255-540` cuts off mid-function
**Source:** cold-start W1
**Evidence:** lead grep — `reconcile_existing_ids` defined at line 490, ends ~line 614. Plan range cuts at 540.
**Fix:** Update Phase 0 task 0.1 to reference lines 255-650.

### W5 — Status state token inconsistency
**Source:** team-orchestration W1
**Evidence:** Plan YAML uses `PLANNED`. §"Sprint Closeout Contract" says `GO → COMPLETED`. §"Phase 5.1" says `status: GO → COMPLETED`. Should harmonize.
**Fix:** Use `PLANNED → IN_PROGRESS → COMPLETED` consistently. Drop `GO` references.

### W6 — Webhook channel coverage assertion
**Source:** lead verification
**Evidence:** `pos_orders` has 409 'Unknown' channel rows since 2025-11-01 (out of 1.2M, 0.034%). Restoration set has 0 'Unknown' rows. But future webhook deliveries for legacy service_channel_ids could produce 'Unknown' canonicals.
**Fix:** Add a closeout monitoring task: Sentry alert when a new `pos_orders` row arrives with `channel='Unknown'`. Currently silent.

## INFO / polish

### I1 — Add PROGRESS.md append in closeout (BEI convention)
**Source:** team-orchestration I2
**Fix:** Phase 5 should also append a row to `data/04_Project_Management/Import_Log/PROGRESS.md`.

### I2 — Over-broad `git add -f` instruction
**Source:** team-orchestration I1
**Fix:** Phase 5.3 should specify exact paths (`docs/plans/2026-05-08-...`, `docs/plans/SPRINT_REGISTRY.md`) rather than blanket `-f`.

### I3 — Phase 4.1 audit may MATCH at higher Supabase totals than Mosaic raw counts
**Source:** cold-start W2
**Fix:** Add note: "post-migration MATCH semantics — Supabase total may be HIGHER than naively-counted Mosaic raw rows by exactly the duplicate-bill count, because Mosaic's raw fetch counts each bill multiple times when terminals collide. The audit script's dedup logic is correct."

## STALE / NOT BLOCKERS (downgraded)

### S1 — system-arch C1 (MV bypasses v_pos_orders_live)
**Status:** STALE — directly verified by lead.
**Evidence:** `pg_get_viewdef('sales_dashboard_daily_store_metrics')` shows the MV's `pos_sales` CTE reads `FROM v_pos_orders_live WHERE payment_status = 'PAID'`. Direct query: MV reports ₱117,799.03 for Paseo 4/21, exactly matching `v_pos_orders_live` (which filters `is_duplicate=false`). The premise of the plan stands.

### S2 — system-arch C5 (NULL channel breaks lookup)
**Status:** STALE for restoration set, partial concern remains.
**Evidence:** Of the 74 rows to restore, 0 have `channel='Unknown'` or NULL. All restorations are between defined channels. The 409 'Unknown' rows in production are unaffected by this migration. Webhook may produce 'Unknown' in future — covered by W6.

## GO/NO-GO Recommendation

**Status: NO-GO until B1, B2, B3, B4 are addressed.**

These four blockers are all about **operational safety during the migration window**:
- B1: silent webhook failures
- B2: schema/code deployment ordering
- B3: tolerance bands vs continuous ingest
- B4: verification math vs continuous ingest

The CORE design (extend natural key with channel, restore channel-distinct tombstones) is **sound**. The plan's premise is correct (system-arch C1 was stale). The schema migration SQL is correct. The sync script changes are correct.

The plan needs amendments to:
1. Add `mosaic_webhook.py` to Phase 2 scope (with its own MUST_MODIFY assertions)
2. Define cron coordination — either pause crons during migration window OR sequence sync-code-first then schema
3. Replace Phase 0.5 stale-snapshot drift check with shape-based check
4. Replace Phase 3.3 absolute delta check with per-(loc, date) delta sum against `restored_rows_ledger.csv`
5. Add `IF NOT EXISTS` to `CREATE UNIQUE INDEX`
6. Reroute Phase 4.1 output to s242 namespace
7. Tighten line ranges in Phase 0.1
8. Harmonize status tokens (PLANNED → IN_PROGRESS → COMPLETED)
9. Add Sentry alert for `channel='Unknown'` arrivals
10. Add PROGRESS.md append + specific git add paths

**Estimated amendment effort: ~2-3 hours.** Once amended → GO for autonomous execution.

**Confidence after fact-check:** 0.85 — high confidence in the architecture, blocked on operational hardening.
