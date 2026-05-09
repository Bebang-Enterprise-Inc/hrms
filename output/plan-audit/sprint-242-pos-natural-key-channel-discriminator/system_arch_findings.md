# System Architecture Audit Findings
## Plan: S242 pos_orders natural-key channel discriminator
## Date: 2026-05-08

## Audit scope

The plan amends a Supabase partial unique index on `pos_orders` by adding `channel` to the natural key, restores 74 channel-distinct tombstoned rows by flipping `is_duplicate=false`, and patches the polling sync script's three deduplication/reconciliation functions to key on `(location_id, business_date, bill_number, channel)` instead of `(location_id, business_date, bill_number)`. Auditor reviewed the plan against the live source code in `scripts/sync_pos_to_supabase.py`, `hrms/api/mosaic_webhook.py`, `hrms/api/sales_dashboard.py`, the existing migrations under `supabase/migrations/`, and both cron schedules under `.github/workflows/`.

The plan is conceptually correct but has multiple architectural defects that, left in, will (a) break the dashboard verification step, (b) leave a concurrent-write race window during the migration, (c) leave the webhook ingestion path silently corrupting data after the cutover, and (d) ship a verification gate (Phase 1.6 +/- tolerance) that cannot succeed because the underlying counts move every 10 minutes.

---

### CRITICAL Findings

#### C1: Phase 3 dashboard delta verification is structurally impossible — the MV does NOT filter `is_duplicate`
**Location in plan:** Phase 3.3 ("dashboard_totals_delta.csv .. ~₱30,964.58"), Phase 3.4 (Paseo MV >= ₱121,720), Phase 3.1 (`REFRESH MATERIALIZED VIEW sales_dashboard_daily_store_metrics`), Surface Inventory (`sales_dashboard_daily_store_metrics MV` row), Cold-Start Test ("How to verify the dashboard").

**Problem:** The plan's verification model assumes the MV `sales_dashboard_daily_store_metrics` reads from `v_pos_orders_live` (which filters `is_duplicate=false`). It does not. The actual implementation in `supabase/migrations/20260405_exclude_webdelivery_from_pos_views.sql` lines 154-238 (`refresh_sales_dashboard_daily_store_metrics()`) reads directly from `public.pos_orders` and filters only by `payment_status = 'PAID' AND (channel IS NULL OR channel != 'WebDelivery')`. There is NO `is_duplicate=false` filter and NO `cancelled_at IS NULL` filter.

Concrete consequences:
1. The 74 channel-distinct tombstones (all `payment_status='PAID'`) are **already counted** in the MV today. Restoring them by flipping `is_duplicate=true → false` produces **zero delta** in `sales_dashboard_daily_store_metrics`.
2. Phase 3.3's "Sum of all deltas should equal ~₱30,964.58" is therefore false. The expected delta on this MV is ₱0.00.
3. Phase 3.4's "combined gross >= 121,720" assertion will likely already hold BEFORE the migration (because the tombstone is already counted in the MV's pos_gross_sales). The Paseo case Phase 3 promises to surface is invisible at the MV level.
4. The same is true for `store_daily_closing` MV (line 119-122 of the same migration): reads `pos_orders` directly with no `is_duplicate` filter.
5. The `sales_dashboard_daily_store_metrics` is the headline-totals source for `_apply_mosaic_channel_split`. The dashboard's UNDER-counting of 30K is therefore happening **somewhere else** — specifically, the `_apply_mosaic_channel_split` re-queries `v_pos_orders_live` directly for the channel breakdown (sales_dashboard.py:876, 975, 1096, 1339), so the *channel-split donut* under-counts but the headline `pos_net_sales_without_vat` MV column may already include the 74 tombstones.

**Fix:** Either (a) verify Phase 3.3/3.4 by querying `v_pos_orders_live` directly (which DOES filter `is_duplicate=false`) for the BEFORE/AFTER delta, not the MV, or (b) accept that the MV totals do not change and re-cast Phase 3 to verify the channel-split path (`_get_mosaic_channel_split`) which IS the surface that under-counts. The plan's Cold-Start text ("`v_pos_orders_live` transparently picks up restored rows" — Surface Inventory row) is correct; the `sales_dashboard_daily_store_metrics MV` row "(refresh only)" reasoning is wrong about the source. Phase 1.5 (Paseo bill 39966 directly via SQL on `pos_orders`) is correct and should be the authoritative spot-check. The MV-based verifications need to be replaced with `v_pos_orders_live` SUM queries.

---

#### C2: Phase 3.1 invokes the wrong refresh API
**Location in plan:** Phase 3.1 ("`REFRESH MATERIALIZED VIEW sales_dashboard_daily_store_metrics;` (non-concurrent — view lacks unique index per S232 finding)").

**Problem:** Two errors in one sentence:
1. `sales_dashboard_daily_store_metrics` is **NOT a materialized view** — it was rebuilt as a **regular table** in S210, refreshed by `TRUNCATE + INSERT` inside `public.refresh_sales_dashboard_daily_store_metrics()` (`supabase/migrations/20260405_exclude_webdelivery_from_pos_views.sql:154-238`). `REFRESH MATERIALIZED VIEW sales_dashboard_daily_store_metrics` will fail with `"sales_dashboard_daily_store_metrics" is not a materialized view`. The cron uses `select public.refresh_sales_dashboard_daily_store_metrics();` (see `.github/workflows/daily-pos-sync.yml:142`). The plan must do the same.
2. The reasoning "view lacks unique index per S232 finding" mis-attributes a property to this object. The TABLE has `idx_sales_dashboard_daily_store_metrics_pk` UNIQUE on `(location_id, business_date)` (`supabase/migrations/20260316zzz_sales_dashboard_daily_metrics_materialized.sql:162-163`). And `store_daily_closing` (Phase 3.2) IS a true MATERIALIZED VIEW WITH a unique index `idx_store_daily_closing_pk` on `(location_id, business_date)` — meaning `REFRESH MATERIALIZED VIEW CONCURRENTLY` IS supported there (line 146-147 of the same migration). The plan's claim that concurrent refresh is impossible is wrong for both objects.

**Fix:** Phase 3.1 should be: `select public.refresh_sales_dashboard_daily_store_metrics();`. Phase 3.2 (store_daily_closing) can be `REFRESH MATERIALIZED VIEW CONCURRENTLY public.store_daily_closing;` if you want concurrent semantics, otherwise plain `REFRESH MATERIALIZED VIEW public.store_daily_closing;`.

---

#### C3: Concurrent-write race window during DROP+CREATE INDEX in same transaction
**Location in plan:** Phase 1.1 migration SQL (BEGIN/DROP INDEX/CREATE UNIQUE INDEX/UPDATE/COMMIT).

**Problem:** The plan claims "Migration is fully reversible" and treats DDL as atomic, but does not address concurrent INSERT/UPSERT traffic. While the migration transaction holds `ACCESS EXCLUSIVE` on the index during `DROP INDEX IF EXISTS` and `CREATE UNIQUE INDEX` (non-CONCURRENTLY), the BIG problem is **what happens to rows inserted by concurrent connections after `CREATE UNIQUE INDEX` commits but before the UPDATE flips the 74 tombstones**:

- During the transaction, the new index is in place, but the 74 tombstones still have `is_duplicate=true` (they aren't UPDATEd yet, and even if they were, the partial index excludes them via the `WHERE is_duplicate=false` clause). The migration is internally consistent there.
- What's truly dangerous is what happens BEFORE the migration: between `BEGIN` and `CREATE UNIQUE INDEX`, the OLD partial index is gone (it's `DROP INDEX IF EXISTS`). For the duration of the transaction (~seconds), there is no uniqueness protection. If a concurrent webhook (`hrms/api/mosaic_webhook.py:_upsert_completed_order`) or the 10-minute cron sync (`pos-sync-5min.yml`, runs every 10 min from 10 AM-midnight PHT) ingests an order during that window, two bills with the same `(loc, date, bill, NEW channel)` could both be inserted as `is_duplicate=false`.
- Then when `CREATE UNIQUE INDEX` runs, the index build will FAIL with a unique violation, ROLLING BACK the entire transaction — leaving the OLD index gone too (because DROP committed inside the same TX, so the rollback restores it, but the WHERE clause is the OLD definition).
- Wait — actually rolling back DDL DOES restore the old index in PostgreSQL (DDL is transactional). But the user-visible failure is "migration aborted" with no clear remediation.

The bigger risk: if the concurrent inserts arrive AFTER `CREATE UNIQUE INDEX` succeeds and BEFORE `COMMIT`, those inserts queue on the index lock and proceed once the transaction commits. Their row state is bound by the new index. That's fine. But during DROP→CREATE, the table-level lock for index DDL doesn't block inserts to the table — only to that index. So inserts can land in the table without index protection until `CREATE UNIQUE INDEX` finishes scanning.

- The 10-minute cron is the live concern: `.github/workflows/pos-sync-5min.yml` runs every 10 minutes from 02:00-16:00 UTC (10 AM-midnight PHT). The migration is likely to be run during work hours. The mosaic webhook (`hrms/api/mosaic_webhook.py`) writes via `_upsert_completed_order` (line 457) using `Prefer: resolution=merge-duplicates,return=minimal` — a continuously-active write path.

**Fix:** Add a Phase 0.7 task: **disable both crons before migration** (`gh workflow disable daily-pos-sync.yml` and `pos-sync-5min.yml`), and disable the webhook (rate-limit or temporarily 503 the route via a feature flag) for the migration duration. Re-enable at start of Phase 3. Alternatively, use `CREATE UNIQUE INDEX CONCURRENTLY ... ` to build the new index BEFORE dropping the old one, then drop the old one once the new one is verified — this requires breaking the single-transaction approach but is the standard zero-downtime pattern. The plan's "single transaction" clause is in conflict with the concurrent-traffic reality. Document explicitly in the Failure Response.

---

#### C4: Webhook ingestion path will write `is_duplicate=NULL` rows that violate the new index OR silently lose collisions
**Location in plan:** Surface Inventory ("`hrms/api/sales_dashboard.py` — No change"), Anti-Rewind contract (does not list `hrms/api/mosaic_webhook.py`).

**Problem:** The plan does not touch `hrms/api/mosaic_webhook.py`, but the webhook DOES write to `pos_orders` via `_upsert_completed_order` (line 457-492). Specifically:
- The webhook payload is mapped to a row that includes `channel: _resolve_channel(order)` (line 410). But it does NOT include `is_duplicate` — so the upsert leaves the column at its DB default (likely false / NULL). The PostgREST upsert uses `merge-duplicates` on the PK (`id`).
- When a NEW Pickup-side bill 39966 arrives via webhook AFTER the migration, the webhook writes a row with `channel=POS, is_duplicate=NULL/false`. If the FoodPanda-side bill 39966 row already exists for that `(loc, date, bill, channel=POS)` (i.e., from poll), the new natural-key index `(loc, date, bill, channel) WHERE is_duplicate=false` triggers a 23505 unique violation. The webhook handler will get HTTP 4xx from PostgREST and respond 500 to Mosaic, causing Mosaic to retry/pause delivery (the same failure mode S189 patched on 2026-04-07).
- Worse: when same-channel duplicates arrive via webhook, the webhook does not run `_dedupe_incoming_by_natural_key` at all (it's a single-row path). The index will reject the second one as a duplicate, and the webhook will return 500 — same Mosaic-pause cascade.
- Even worse: if a webhook delivers the dup-bill BEFORE the poll picks it up, the webhook may insert it as `is_duplicate=false`, and then the next poll's `reconcile_existing_ids` (after Phase 2 patch) will look up by `(loc, date, bill, channel)` and remap correctly. But if the dup-bill arrives via webhook on the SAME-channel side (same channel as existing live row), it 23505s and Mosaic retries forever.

**Fix:** Either (a) extend the webhook's `_upsert_completed_order` to run the same canonical-pick logic against any existing same-channel live row (set `is_duplicate=true` on the new row if a canonical sibling already exists), (b) explicitly set `is_duplicate=false` ONLY when no live sibling exists in same channel — requires a pre-fetch, defeats the merge-duplicates simplicity, or (c) switch the webhook upsert to use `Prefer: resolution=merge-duplicates,return=representation` and on 23505 fall back to a server-side script that re-runs the canonical-pick. Minimal fix: add `is_duplicate: false` explicitly to `_map_order_row` so the webhook's intent is clear, and add a try/except around the upsert that on 23505 logs to Sentry and queues for next poll cycle. The Surface Inventory row claiming `hrms/api/mosaic_webhook.py` is untouched is a defect — it MUST be in scope or explicitly out-of-scope with a documented mitigation.

---

#### C5: `reconcile_existing_ids` channel-aware lookup must NOT lose orphan-channel matches
**Location in plan:** Phase 2.2 ("Lookup query must group canonical_rows by channel, then for each channel call PostgREST with `channel=eq.{channel}`").

**Problem:** The new lookup partitions by channel. But Mosaic's `_resolve_channel` returns `"Unknown"` when `service_type_id IS NULL` (line 813-814 of sync script). It returns the actual channel string for known mappings. The existing DB rows that currently exist with `channel=NULL` (zero per plan's claim of 100% populated, but a NULL row CAN sneak in) would not match `channel=eq.Unknown` in PostgREST — PostgREST `eq.` matches on equality, not on `IS NULL`.

Even more importantly: the existing query (line 559-580 of `sync_pos_to_supabase.py`) returns `select=id,bill_number` and stores `existing_by_bill[str(row["bill_number"])] = row["id"]`. The plan's new key `(bill, channel)` requires the SELECT to include `channel`, and the lookup-by-channel filter must also match the row's channel. But there's an implementation subtlety: the partial index covers `(loc, date, bill, channel) WHERE bill IS NOT NULL AND is_duplicate=false`, meaning at most ONE row per (loc, date, bill, channel). The current query `WHERE is_duplicate=eq.false AND bill_number=in.(...)` returns ALL channels for those bills. Iterating per-channel is wasteful — a single query returning `select=id,bill_number,channel` and indexing locally by `(bill, channel)` is simpler AND avoids the `channel=eq.X` URL-encoding edge case (e.g., what about `channel=eq.Unknown` when channel is actually NULL?).

Also: if a SAME bill has TWO live rows (one POS, one FoodPanda) the existing implementation stores `existing_by_bill[bill]=last_seen_id` — a single value, last-write wins. After Phase 2, this MUST become a tuple key, but the plan instructs "for each channel call PostgREST with `channel=eq.{channel}`" — that is N additional round-trips per chunk where N=number of distinct channels in batch. For a typical batch (POS, FoodPanda, GrabFood, Delivery, WebDelivery), that's 5x the lookup latency. PostgREST has no IN tuple support but a single SELECT with both `bill_number=in.(...)` AND no channel filter would return all channels in one call, then locally index by `(bill, channel)`.

**Fix:** Replace the per-channel PostgREST round-trip approach with: single query `select=id,bill_number,channel` filtered by `bill_number=in.(...)`, build `existing_by_bill_channel[(bill, channel)]=id` from response. Faster, simpler, no NULL-channel edge cases. The plan's MUST_CONTAIN regex `"channel": f"eq.{` is fine for compliance but ARCHITECTURALLY suboptimal — the executing agent should be allowed to use the single-query pattern if they document why.

Additionally: handle the NULL-channel case. The plan asserts 100% of rows have non-NULL channel (Design Rationale §"Why `channel`"). Phase 0.4 should re-verify this assertion immediately before the migration, NOT just trust the S232 audit.

---

#### C6: Phase 1.6 anti-regression tolerance band cannot succeed under continuous ingest
**Location in plan:** Phase 1.6 (`same_channel_count_after >= 295 AND <= 320`), Phase 0.5 (`rows_to_restore_within_tolerance`).

**Problem:** The 10-minute cron ingests new rows continuously. Between Phase 0 baseline capture and Phase 1.6 verification, multiple sync cycles may have run. The same-channel tombstone count of 307 (locked 2026-05-08) is a snapshot. By the time Phase 1.6 runs, new same-channel duplicates from the past hours of ingest will increase the count. The +/-5 tolerance band (`>= 295 AND <= 320`) may be tighter than the daily ingest variance.

A 14-hour active window (10 AM-midnight PHT) processes ~25,000 PAID bills/day across 45 stores. Even if only 1% are same-bill duplicates returned twice (which `_dedupe_incoming_by_natural_key` correctly handles), that's 250 NEW same-channel tombstones per day. The growth rate of the same-channel-tombstones counter over 14 hours can far exceed +/-5. Over a single migration window of ~30 min, growth might be ~5-10 — close to the tolerance limit.

The plan's Phase 0.5 has the same problem: "rows_to_restore_within_tolerance" assumes the count is stable, but the SAME query that produces `74 channel-distinct tombstones` will return MORE if any new channel-distinct tombstones have appeared since 2026-05-08 (today). Between 2026-05-08 and execution day, several additional bills MAY have been tombstoned. Whether or not this happens depends on Mosaic's same-bill-different-channel collision rate. The plan does not measure this rate.

**Fix:** Either (a) widen Phase 1.6 tolerance (e.g., +/-50 over 30 min) AND make Phase 0.5 capture a fresh count and use IT as the locked tolerance basis, not the 2026-05-08 number, or (b) disable both crons during migration (per C3 fix) so counts are frozen, OR (c) base Phase 1.6 on the SAME ids captured in `output/s242/migration/before_state.json` rather than a count query — verify each captured tombstone-id still has `is_duplicate=true` (zero-loss assertion), instead of comparing aggregate counts.

---

### WARNING Findings

#### W1: Phase 1.1 SQL UPDATE wraps no `RETURNING` capture into the CSV — capture happens in Phase 1.2 task description
**Location in plan:** Phase 1.1 SQL (Step C with RETURNING) vs Phase 1.2 task ("Captures the RETURNING rows from Step C and writes them to ...restored_rows_ledger.csv").

**Problem:** The `RETURNING` clause in the SQL is inside the transaction. Whether `scripts/s242_migrate.py` actually parses Mgmt API JSON response containing those returned rows depends on implementation. Supabase Mgmt API `/database/query` endpoint typically returns the LAST statement's result set when run via raw SQL. With multiple statements in a single transaction (DROP, CREATE, WITH...UPDATE...RETURNING), the response shape depends on Supabase's parser behavior. If the Mgmt API returns only the FINAL statement's result (the COMMIT, which has no rows), the `RETURNING` rows are LOST.

**Fix:** Phase 1.2 must verify implementation. Either split the migration into two Mgmt API calls (DDL first, then UPDATE...RETURNING in a separate transaction, captured into restored_rows_ledger.csv) — sacrificing single-transaction atomicity but gaining capture reliability — or wrap the UPDATE inside a CTE that the Mgmt API can parse the result of. Add a Phase 1 unit test that confirms the ledger CSV contains 74 rows after run-1 (or whatever count Phase 0.5 captured). Without this, "rollback via restored_rows_ledger.csv" (Failure Response Mode A) cannot be guaranteed.

---

#### W2: Restoration pairing check (Phase 4.4) does not catch the truly-bad outcome
**Location in plan:** Phase 4.4 ("100% of restored rows have a paired live sibling with different channel ... If any restored row is now ORPHAN (no sibling)").

**Problem:** The plan's "orphan" check confirms each restored row has SOME live sibling with a different channel. It does NOT verify that the restored row itself does not now create a NEW conflict with an in-flight ingest. The truly-bad outcome is: between Phase 1's UPDATE and Phase 4.4's verification, the cron sync inserted a row with the same `(loc, date, bill, channel)` as a freshly-restored row. The new partial index would have rejected the insert with 23505 — the cron would have errored and retry-failed. Phase 4.4's pairing check passes, but the cron is broken.

**Fix:** Phase 4.4 should additionally check `output/s242/verification/sync_progress_after.json` for any `status='error'` rows since migration. The cron `set_sync_progress(... status='error')` writes to a `sync_progress` table (see line 640-653). Query it for errors with `synced_at >= migration_start`. If any error references a 23505 or "duplicate key value", that's the failure mode this audit is most worried about.

---

#### W3: The `_resolve_id_collisions` function is not in scope but its semantics shift
**Location in plan:** Surface Inventory (`_canonical_score` "No change ... but now only ranks within the SAME (loc, date, bill, channel) group"), §Phase 2.

**Problem:** `_resolve_id_collisions` (line 291-369 of sync_pos_to_supabase.py) is NOT explicitly in scope for Phase 2. Its purpose is to fix in-batch id collisions (Mosaic returns the same numeric id for two different bills). It runs AFTER `reconcile_existing_ids`. Its `protected_ids` parameter receives the set from `reconcile_existing_ids`. The plan's Surface Inventory says `_canonical_score` semantics shift to "within the SAME `(loc, date, bill, channel)` group" — but `_resolve_id_collisions` groups by `id`, not by natural key. It picks the keeper using `_canonical_score`. That score still works for per-id grouping, BUT: if the same id appears across two natural-key groups (one POS, one FoodPanda), the keeper is whichever has the better `_canonical_score`. The loser gets reassigned a synthetic id. The loser then needs to land at the correct natural-key group — but if two losers end up with the same synthetic id (rare per the existing comment), the salt loop handles it.

The risk: the plan does not analyze how `_resolve_id_collisions` interacts with the new natural-key tuple. If the keeper is in natural-key group A (POS-39966) and the loser is in natural-key group B (FoodPanda-39966) AND both share an id by Mosaic-side chance, after collision resolution they both have different ids and different natural keys. Fine. But if the protected_id comes from group A (because reconcile_existing_ids matched POS-39966 to existing id X) and the in-batch row for FoodPanda-39966 (which has a different natural key) also has id X (Mosaic collision), the keeper is the protected POS one, and the FoodPanda-39966 gets a synthetic. That's correct — the FoodPanda-39966 keeps its natural-key identity but lands as a new row.

**Fix:** Add a Phase 2 task: write a unit test that simulates an in-batch id collision across distinct channels and verifies both end up in DB as `is_duplicate=false` post-sync. The Phase 2.5 Paseo smoke covers the Paseo case but does not exercise this specific failure mode.

---

#### W4: `pos_order_items` and `pos_order_payments` FK refer to `pos_orders.id` — orphan-row risk on rollback
**Location in plan:** Failure Response Mode A ("ROLL BACK by re-running migration with the inverse update (use `restored_rows_ledger.csv` as the rollback list)").

**Problem:** When restoration is rolled back, the 74 rows revert to `is_duplicate=true`. Their `pos_order_items` and `pos_order_payments` children are unchanged. Joins to `v_pos_orders_live` filter them out (because `is_duplicate=true` is excluded). Fine for dashboard. But the BOM consumption trigger (`fn_record_bom_consumption_on_paid` from `supabase/migrations/20260414_s189_realtime_bom_consumption.sql`) fires on `pos_order_items` UPDATE and reads `pos_orders` to get `business_date, location_id`. If the parent is `is_duplicate=true`, the trigger still fires (no `is_duplicate` filter). This means after restoration AND rollback, BOM consumption events may have already been recorded for the 74 restored rows. Rolling back `is_duplicate` does NOT reverse the BOM consumption.

**Fix:** Document this in Failure Response Mode A: "Rollback flips `is_duplicate` only; any BOM consumption deltas already recorded for the 74 rows are NOT reverted. If BOM consumption is wrong, run `fn_reverse_consumption_on_cancel` equivalent for each restored id before rollback." Better: confirm whether BOM consumption fires on `is_duplicate=false→true` UPDATE OR only on cancellation (the current trigger fires on `cancelled_at IS NOT NULL AND OLD.cancelled_at IS NULL` — line 273 — so flip-flopping `is_duplicate` does NOT reverse consumption automatically). Clarify in plan.

---

#### W5: Phase 0.5 5% drift gate may halt agent on a 0-drift normal-case
**Location in plan:** Phase 0.5 ("Verify before_state.json shows `rows_to_restore` within 5% of 74 (locked count). If not, STOP").

**Problem:** 5% of 74 = 3.7, rounded to 3 or 4. If today's run captures 78 rows (4 new channel-distinct tombstones since 2026-05-08), that's 5.4% drift → STOP. Yet the migration WOULD work fine — flipping 78 rows is no different from flipping 74. The locked-count gate is overly tight for a count that is monotonically increasing.

**Fix:** Change the gate to a one-sided check: STOP only if `rows_to_restore < 74 * 0.95` (count went DOWN by >5%, meaning rows already-restored, suggesting a partial earlier run) OR `rows_to_restore > 74 * 2.0` (count doubled, meaning something massively shifted). Otherwise proceed with the captured count.

---

#### W6: The existing `reconcile_existing_ids` SELECT does NOT include `channel` — Phase 2 must update SELECT clause
**Location in plan:** Phase 2.2 (does not explicitly mention SELECT clause change).

**Problem:** Current line 565-566 of sync_pos_to_supabase.py:
```python
"select": "id,bill_number",
```
The new tuple key requires `channel` in SELECT. The plan's MUST_CONTAIN regex `"channel": f"eq.{` covers the filter side but NOT the SELECT side. An agent might add the filter but forget to add `channel` to the SELECT, in which case the response rows have no channel field and the local indexing fails silently.

**Fix:** Add MUST_CONTAIN to Phase 2.2: `select.*id,bill_number,channel` OR explicit task instruction: "update the `select` parameter to `id,bill_number,channel`."

---

### INFO Findings

#### I1: Plan claim "scheduled cron 00:00 PHT" mismatches the actual schedules
**Location in plan:** Audit checklist item "No race condition between migration and the daily 00:00 PHT cron sync" (this finding only flagged because it's in the audit checklist — not in the plan body).

**Problem:** No production cron at 00:00 PHT. Actual schedules:
- `daily-pos-sync.yml`: hourly 02:00-16:00 UTC = 10:00-00:00 PHT (15 runs/day)
- `pos-sync-5min.yml`: every 10 min, 02:00-16:00 UTC = 10:00-00:00 PHT (~84 runs/day)
- `daily-pos-sync.yml` nightly verification at 16:30 UTC = 00:30 PHT

Plan's Failure Response and Anti-Rewind contracts should reference these actual schedules.

**Fix:** Update plan's Failure Response to mention the 10-minute cadence (`pos-sync-5min.yml`) explicitly. Reference C3 fix (disable both workflows for the migration window).

---

#### I2: `protected_ids` accumulator (Phase 2.3) — wording is confusing but semantically OK
**Location in plan:** Phase 2.3 ("when a remap happens, add the existing_id keyed by `(bill, channel)` not just `bill`").

**Problem:** `protected_ids` is a `set` of ids — there is no key, just a flat set. The plan's wording "keyed by `(bill, channel)` not just `bill`" suggests changing the key, but `protected_ids` is value-only (just ids). What the plan likely MEANS is: ensure the existing_id PULLED FROM `existing_by_bill_channel[(bill, channel)]` is added to `protected_ids` (as a flat set). That's already correct in the existing code (line 595: `stats["protected_ids"].add(existing_id)`). The "keyed by tuple" phrasing in 2.3 is wrong.

**Fix:** Reword Phase 2.3 to: "Verify `protected_ids.add(existing_id)` is reached for every (bill, channel) tuple that found a match. The set itself remains a flat set of ids."

---

#### I3: Phase 2.5 smoke does not validate the negative case
**Location in plan:** Phase 2.5 (smoke runs Paseo dual-channel day, asserts both rows live).

**Problem:** The smoke asserts the PASS case (no remap regression on dual-channel bill 39966). It does NOT assert that a SAME-CHANNEL duplicate is still correctly tombstoned. Without this, a regression that flipped same-channel dedup logic would slip through. Phase 2.7/2.8 add SM Manila clean-day, but again no negative case.

**Fix:** Add Phase 2.9: smoke against a known same-channel-tombstone day (any of the 158 store-days from the locked count). Assert the same-channel tombstone ids are still `is_duplicate=true` after re-sync. Sample 1-2 ids from `output/s232/audit_data.json` if they have same-channel duplicates, otherwise add a Phase 0.4.b task to identify a candidate.

---

#### I4: Phase 4.4 query semantics under-specified
**Location in plan:** Phase 4.4 ("for each `id` in `restored_rows_ledger.csv`, confirm `(loc, date, bill)` has another `is_duplicate=false` row with a different channel").

**Problem:** "another row" — does it mean any other row, or exactly one? The new partial index allows multiple rows (one per channel) per (loc, date, bill). After restoration, a Paseo bill 39966 has 2 live rows (POS + FoodPanda). For each of these, the "other" is well-defined. But could there be 3 channels? `_resolve_channel` returns 5 distinct channels (POS, FoodPanda, GrabFood, WebDelivery, Delivery, Unknown). It IS theoretically possible for a bill to be on 3+ channels.

**Fix:** Reword Phase 4.4: "For each `id` in `restored_rows_ledger.csv`, confirm AT LEAST ONE other live (`is_duplicate=false`) row exists for the same `(loc, date, bill)` with a DIFFERENT channel." The current plan wording is OK but could be misread.

---

#### I5: ON CONFLICT clause in upserts — verify natural-key path doesn't break
**Location in plan:** Surface Inventory (no mention of `on_conflict=` parameter).

**Problem:** `supabase_upsert(client, "pos_orders", batch, on_conflict=??)` — the existing code uses `on_conflict=id` (PK) for pos_orders upsert. The new partial unique index is a SECONDARY constraint. PostgREST with `on_conflict=id` resolves on PK only. If a batch contains two rows with same `(loc, date, bill, channel)` but different ids (a Mosaic edge case), the PK-based ON CONFLICT inserts both, then the partial unique index rejects one. The dedup function is supposed to prevent this — and IS, because `_dedupe_incoming_by_natural_key` after Phase 2.1 will collapse same-channel duplicates. So this works.

**Fix:** No fix needed; document in plan body that `on_conflict=id` is correct because dedup handles the natural-key uniqueness pre-upsert. Adds clarity for cold-start agents.

---

#### I6: Verifier exits 0 != work was done correctly
**Location in plan:** Phase verifier table ("Phase 1 ... idempotency 0 second-run rows").

**Problem:** Phase 1.4 idempotency check re-runs the migration and asserts second-run restored count = 0. But the verifier could trivially exit 0 if the SQL has `DROP INDEX IF EXISTS` (no-ops on rerun) and the WHERE clause finds no `is_duplicate=true` siblings (because they were all flipped). What it does NOT check: that the index DEFINITION on second run matches what we want. If Step B's CREATE INDEX was somehow swapped with the OLD column list and we re-ran, the new run would try to CREATE the index but it's already created with the WRONG definition — `CREATE UNIQUE INDEX` (not IF NOT EXISTS) would fail. The plan uses bare `CREATE UNIQUE INDEX` (line 310-313) — no `IF NOT EXISTS`. So idempotency requires the second run to handle the "already exists" case.

**Fix:** Either (a) change Step B to `CREATE UNIQUE INDEX IF NOT EXISTS pos_orders_bill_number_natural_key ...`, or (b) add a Step A2: `DROP INDEX IF EXISTS` is the only DROP, then check if recreation is needed (idempotency-friendly). Recommend (a). The plan's idempotency claim is currently broken: re-running fails on `CREATE UNIQUE INDEX` due to existing index.

---

### Summary

- CRITICAL: 6 (C1: MV verification structurally impossible; C2: wrong refresh API; C3: concurrent-write race window; C4: webhook breaks post-cutover; C5: lookup partitioning logic flawed; C6: tolerance-band gate cannot succeed)
- WARNING: 6 (W1: RETURNING capture risk; W2: pairing check misses real failure mode; W3: collision resolver coverage; W4: BOM consumption rollback; W5: 5% drift over-tight; W6: SELECT clause not in MUST_CONTAIN)
- INFO: 6 (I1: cron schedule misstatement; I2: protected_ids wording; I3: missing negative smoke case; I4: pairing check ambiguity; I5: on_conflict clarity; I6: idempotency requires IF NOT EXISTS)

### Top blockers (must-fix before execution)

1. **C1+C2** — fix Phase 3 verification: query `v_pos_orders_live` for the delta, not the MV; call the function `refresh_sales_dashboard_daily_store_metrics()` not raw REFRESH SQL.
2. **C3** — disable both crons + webhook for migration window OR switch to CONCURRENT index build pattern.
3. **C4** — add webhook handling change OR explicitly mitigate (e.g., temporarily fail-open on 23505 from webhook + queue retry on poll cycle); webhook MUST be in scope.
4. **C5** — collapse per-channel PostgREST round-trips into single SELECT + local indexing; handle NULL channel.
5. **C6** — disable crons (resolves C3 too), and base Phase 1.6 verification on captured ids not aggregate counts.
6. **I6** — add `IF NOT EXISTS` to CREATE UNIQUE INDEX so idempotency claim holds.

### Cross-system consistency checklist verdict

- [x] Migration SQL is in a single transaction — yes
- [x] Migration is idempotent — NO (C6 wrt CREATE UNIQUE INDEX without IF NOT EXISTS)
- [ ] No concurrent-write window — NO (C3)
- [ ] WHERE clause of new index matches sync script's lookup — partially (C5: lookup design suboptimal)
- [ ] reconcile_existing_ids correctly partitions by channel — needs SELECT clause fix (W6)
- [x] _dedupe_incoming_by_natural_key change preserves canonical-pick — yes (the plan's grouping change is correct; same-channel dedup still works)
- [x] _resolve_id_collisions still works — yes (W3 documents minor coverage gap)
- [ ] No race vs webhook ingestion — NO (C4)
- [ ] No race vs daily 00:00 PHT cron — N/A (cron is HOURLY and 10-minute, not 00:00; see I1, also covered by C3)
- [x] Restoration doesn't violate new partial unique index — by-construction yes (different-channel siblings only)
- [ ] MV refresh order correct — Phase 3.1/3.2 are wrong about the API call AND wrong about source data (C1, C2)
- [x] v_pos_orders_live transparently picks up restored rows — yes (no view definition change needed; standard view)
- [x] _apply_mosaic_channel_split logic still works — yes (queries `v_pos_orders_live` directly; restored rows now visible)
- [x] FK pos_order_items.order_id → pos_orders.id stays valid — yes (FK doesn't depend on is_duplicate; W4 documents BOM consumption side-effect)
- [x] Anti-Rewind contract owns vs protects correctly — partially (C4: missing webhook in owned-or-out-of-scope inventory)
- [ ] Failure Response Mode A rollback feasible via ledger — partially (W1: ledger capture from RETURNING is fragile; W4: BOM consumption side-effects not handled)

### Edge case: NEW bill 39966 entry on next sync after migration

This was the audit-prompt-specified scenario. Trace:
1. Mosaic returns bill 39966 with two orders: id=NEW1 (channel=POS, amount=300), id=NEW2 (channel=FoodPanda, amount=900) — both are NEW rows that don't exist in DB yet.
2. `_dedupe_incoming_by_natural_key` (Phase 2.1 patched): groups by `(loc, date, bill, channel)` → 2 distinct keys → no dedup needed. Both rows pass through with `is_duplicate=false` (set explicitly by the function when has_dupes is false).
3. `reconcile_existing_ids` (Phase 2.2 patched): looks up `(loc, date, bill, channel)` in DB. If existing `(loc, date, bill=39966, channel=POS)` row exists with id=OLD_POS, it remaps NEW1.id → OLD_POS (preserves stable id, replaces children). Same for FoodPanda. Both now upsert correctly under PK on_conflict.
4. If neither exists yet (first sync of this dual-channel bill): both NEW1 and NEW2 are inserted as `is_duplicate=false`. The new partial unique index permits this because `(loc, date, bill, channel)` is distinct.
5. If previously-tombstoned 4/21 Paseo case: by Phase 1, both rows were flipped to `is_duplicate=false` and have stable ids OLD1 and OLD2. Mosaic re-sync brings ids NEW1, NEW2. Reconcile remaps: NEW1.id → OLD_POS; NEW2.id → OLD_FoodPanda. Children re-replaced. No duplicates created.

VERDICT: Phase 2 patch handles the new-bill-39966-after-migration scenario correctly, ASSUMING C5 single-query approach OR per-channel round-trips both find both existing rows. The original per-channel approach in C5 would also work but with extra latency and the NULL-channel edge case unresolved.

What FAILS without Phase 2 patch (regression test): if Phase 1 is applied but Phase 2 is delayed/forgotten, the next sync would lookup `(loc, date, bill)` only, find OLD_POS or OLD_FoodPanda (whichever comes back last from the SELECT), and remap BOTH NEW1 and NEW2 to the SAME existing id. The collision resolver would catch this via `_resolve_id_collisions`, reassign one to a synthetic id, and BOTH would upsert. But the upsert would fail on the partial unique index `(loc, date, bill, channel)` because one row at PK=synthetic with channel=POS would still exist as `is_duplicate=false` AND the original POS-39966 row is still at OLD_POS as `is_duplicate=false` — same `(loc, date, bill, channel)`. 23505. Sync errors. So Phase 1 WITHOUT Phase 2 = broken.

Phase 1 and Phase 2 must be deployed together. Plan's Phase ordering is correct (1 then 2 in the same execution). But the inter-phase atomicity is not guaranteed if Phase 1 succeeds and Phase 2's smoke fails — the migration is half-done, the schema is changed, the sync script is OLD. The next cron tick (~10 min) will error on every dual-channel store-day. Plan's Failure Response Mode B says "the migration is independent — it can stay applied while Phase 2 iterates." That's WRONG: the cron will be broken until Phase 2 ships.

**CRITICAL addendum to Failure Response:** if Phase 2 fails, REVERT Phase 1 by restoring the OLD index definition (drop new, re-create old) AND re-tombstone the 74 restored rows (use `restored_rows_ledger.csv`). Do NOT leave Phase 1 active without Phase 2 — the cron will fire-and-fail on every dual-channel bill encountered.
