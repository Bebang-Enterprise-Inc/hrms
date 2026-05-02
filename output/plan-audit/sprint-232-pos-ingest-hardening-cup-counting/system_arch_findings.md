# S232 System Architecture & End-to-End Duplicate Resolution Audit

**Plan audited:** `F:\Dropbox\Projects\BEI-ERP\docs\plans\2026-05-02-sprint-232-pos-ingest-hardening-cup-counting.md`
**Question answered:** Will this resolve all our duplicate issues?
**Audit date:** 2026-05-02
**Auditor:** plan-audit (system-arch reviewer)

---

## TL;DR — verdict

The plan **substantially improves** dedup at the primary write path, but it has **5 BLOCKER-class coverage gaps** and **3 HIGH-class issues** that would let duplicates leak back in or leave stale data behind. These gaps are concrete (not theoretical) and are reachable by code that exists today.

**Will it resolve ALL duplicates?** No — not as written. Phase 1 closes the leading hole (~99.95% of new poll dupes) but leaves at least 4 other write paths and at least 1 read path that defeat the dedup either at write time, at view time, or at item-cardinality time.

---

## Severity legend

- **BLOCKER** — closes the loop only on a subset of paths; duplicates can be inserted, presented to users, or leave orphaned children even after Phase 1+5 ship.
- **HIGH** — the dedup works, but the surrounding system is fragile or misleading (operational risk, ordering risk).
- **MEDIUM** — accuracy/maintainability concerns; doesn't break the fix but should be addressed.

---

## BLOCKER 1 — `_upsert_completed_order` direct REST insert path bypasses the dedup helper as currently written

**Severity:** BLOCKER

**Where:** `hrms/api/mosaic_webhook.py:457-492` (`_upsert_completed_order`), and Phase 1 task 1.5b in the plan.

**The gap:** The plan's Phase 1.5b says "wire same dedup into `_upsert_completed_order` (FUTURE-PROOFING)." Sounds fine. But examine how `_upsert_completed_order` actually writes:

```python
r_order = requests.post(
    f"{SUPABASE_URL}/rest/v1/pos_orders",
    headers=headers,
    json=[order_row],
    timeout=15,
)
```

It uses **PostgREST `Prefer: resolution=merge-duplicates`** which deduplicates on the PK (`id`). The plan's Phase 1.1 adds a unique partial index on `(location_id, business_date, bill_number)` — but PostgREST `merge-duplicates` only handles ONE conflict resolution. The current code uses `?on_conflict=` is implied by the PK; if the row passes the PK check (because it has a new `id`) but violates the bill-number unique index, **PostgREST will throw HTTP 409 / 23505 unique_violation** and the entire batch will fail. The webhook `_upsert_completed_order` catches `r_order.raise_for_status()` and returns 500 to Mosaic. Mosaic, per the documented S189 history, **paused webhook delivery for 6 days** the last time we returned non-200s.

The plan acknowledges via 1.5b that the order.completed webhook is currently NOT registered, so this is "future-proofing." But:

1. The plan also doesn't add the explicit `on_conflict` resolution to the unique partial index in the helper. Without it, the second arrival raises 23505, not silently merges.
2. If/when S189 webhooks are re-registered (which is part of the vendor outreach), the FIRST burst-retry will return 500, Mosaic pauses delivery, and the system silently regresses.

**What's missing:**
- The plan must specify the exact PostgREST conflict-resolution strategy when both a PK conflict AND the new bill-number unique index can fire. Phase 1.5b says "do the same: bill_number twin check (→ webhook_duplicates if found)" — i.e., a pre-check via `find_bill_number_twin`. That's correct, but it must run BEFORE the `requests.post`, AND the post must catch the 23505 fallback explicitly, AND return HTTP 200 (with `handled: false, reason: "duplicate_routed_to_webhook_duplicates"`) so Mosaic doesn't pause delivery.

**Why this is a BLOCKER:** even if we never re-register S189 webhooks, the same code path is invoked when Mosaic's roundtrip is attempted (`_handle_order_completed` will call `_upsert_completed_order` after `_fetch_mosaic_order`). And if anyone re-registers without remembering this, the failure mode is "silent webhook pause" not "loud error."

---

## BLOCKER 2 — `pos_orders_raw` is not addressed and its uniqueness key is `order_id` (Mosaic ID), so it WILL accept all duplicates

**Severity:** BLOCKER

**Where:**
- Write site: `scripts/sync_pos_to_supabase.py:485-496` (`store_raw_orders`)
- on_conflict key: `"order_id"` (Mosaic Order ID, the unstable one)
- Plan coverage: **NONE** — the plan never mentions `pos_orders_raw`

**The gap:** The poll script writes a raw audit dump to `pos_orders_raw` with `on_conflict="order_id"`. Since the bug is that **Mosaic re-issues fresh `id` (Order ID) values for the same `bill_number`**, every duplicate cluster lands in `pos_orders_raw` as 6 separate rows (one per re-issued ID). The plan's unique partial index lives on `pos_orders`, not `pos_orders_raw`. The raw table has different keys.

**Concrete consequence:** If anyone backs into analytics from `pos_orders_raw` (e.g., to re-derive a metric, to debug, or to populate a downstream system), they get the inflated count back. The `webhook_duplicates` audit ledger doesn't tell them which raw rows correspond to dropped duplicates.

**What's missing:**
- Either: (a) extend the unique index strategy to `pos_orders_raw` with a JSONB-extracted index `((raw_json->>'bill_number')::int)` plus location_id and business_date, OR
- Decide explicitly that `pos_orders_raw` is "raw audit by Mosaic Order ID" and document this in the plan so analysts know to NEVER aggregate from it.

**Recommended:** add `pos_orders_raw` to Phase 1 explicit scope. At a minimum, add a column `pos_orders_raw.kept_as_canonical BOOLEAN` populated from the dedup helper.

---

## BLOCKER 3 — `pos_order_items` will accumulate 6× line items even after `pos_orders` rejects 5 of 6 duplicates

**Severity:** BLOCKER

**Where:**
- Write site: `scripts/sync_pos_to_supabase.py:541` (`upsert_items_batch`)
- `on_conflict` key: `"order_id,product_id,line_number"` (line 234)
- Plan coverage: Phase 5.1 mentions `pos_orders` only; explicitly says "Does NOT delete any row" with the `is_duplicate=true` flag.

**The gap:** Look at the order in `sync_store_day` (lines 528-543):

```python
order_rows.append(map_order(order))      # <-- one row per Mosaic ID
item_rows.extend(map_order_items(order)) # <-- N rows per Mosaic ID, keyed by order_id

supabase_upsert(client, "pos_orders", order_rows, on_conflict="id")
upsert_items_batch(client, item_rows)    # <-- writes children for the rejected parents too
```

When Phase 1's bill-number check rejects 5 of 6 duplicate orders into `webhook_duplicates`, the **5 rejected orders' items still get inserted into `pos_order_items`** because:
1. Each rejected duplicate has a unique `order_id` (Mosaic ID), so `(order_id, product_id, line_number)` is unique.
2. The plan's helper modifies the `pos_orders` write but doesn't intercept `upsert_items_batch`.
3. Phase 5.1 explicitly preserves all rows: "Does NOT delete any row."

**Concrete consequence:** With the live finding — bill_number 23547 has 6 duplicate orders × ~4 items each ≈ 24 line items. After Phase 1 ships, only 1 order is in `pos_orders`, but 24 items are in `pos_order_items`. Five sets of those items are **orphaned** (foreign key `order_id` points to a row in `webhook_duplicates`, not `pos_orders`).

**Downstream effects:**
- `pos_order_items` JOIN `pos_orders ON o.id = i.order_id` (e.g., `supabase/migrations/20260307_discount_identity_alerts.sql:198`) silently drops the orphans — analytics may shift unpredictably.
- `cups_sold` query in Phase 2 reads through `pos_order_items` joined back; orphans cause undercount or instability.
- The S189 BOM consumption trigger `fn_update_material_consumption_pos` (`supabase/migrations/20260414_s189_realtime_bom_consumption.sql:122-170`) fires on `pos_order_items` INSERT — it `SELECT business_date, location_id INTO v_business_date, v_location_id FROM pos_orders WHERE id = NEW.order_id`. If the orphaned items reference a kept order — wait, they reference the REJECTED order's id. The trigger gets `NULL` from the join, returns NEW without writing consumption. **OK** for new rows. But during Phase 5 backfill, when we set `is_duplicate=true` on the duplicates we kept (because we want to preserve them), the trigger doesn't re-fire on the items — but the items already counted toward consumption when they were originally inserted. **The cups consumption is over-counted by 5×.**

**What's missing:**
- The dedup helper must also tombstone or re-link orphaned children when an order is rejected. Options:
  - Reassign `pos_order_items.order_id` to the kept order — but that violates the unique key `(order_id, product_id, line_number)` if items have same line numbers.
  - Add `pos_order_items.is_duplicate BOOLEAN DEFAULT false` and set true for items whose parent went to `webhook_duplicates`. Filter all reads.
  - Refuse to insert items for rejected orders. Cleanest, but requires change to `sync_store_day` flow.

**Phase 5.1 backfill ALSO doesn't address the historical orphan items.** It only flags `pos_orders`. The 945 historical duplicate clusters have ~3K-4K orphan items.

**Why this is a BLOCKER:** the cups recount in Phase 5.3 (`scripts/s232_recount_cups.py`) depends on filtering items via the `is_duplicate` flag. The plan does not say that the items table gets a parallel flag. Without it, the recount will be wrong.

---

## BLOCKER 4 — Backfill ordering risk: the unique index ships in Phase 1, but historical dupes aren't flagged until Phase 5

**Severity:** BLOCKER (operational)

**Where:** Phase 1.1 vs Phase 5.1 timing.

**The gap:** The unique partial index `pos_orders_bill_number_natural_key` is created in Phase 1.1. As soon as that migration applies, the next 10-min poll runs **and the polling script tries to insert orders for which a duplicate row already exists in production today**. Specifically:

- `supabase_upsert(client, "pos_orders", order_rows, on_conflict="id")` at line 539 uses `on_conflict=id` (PK). It does NOT specify the bill-number unique index.
- When the poll re-pulls today's partial day (`partial` rows are re-synced per line 511), the same bill_number that was successfully written to two different IDs yesterday is in the database TWICE. The poll's UPSERT-on-id touches each row with the same id, fine — but a NEW order with a new `id` for the SAME (location, date, bill_number) violates the unique index and the WHOLE batch fails (PostgREST batches a list of rows; one violation rejects the response).

**Concrete consequence:** The very next poll after Phase 1.1 ships fails because real production data contains 945+ duplicates today. Every poll for ~14 days (the audit's window) keeps failing because the existing dupes block new inserts. The system cannot self-heal until Phase 5.1 backfill runs.

**The plan does not address the migration ordering.** Phase 1 ships before Phase 5. The fix exists later in the plan but in the wrong order.

**What's missing:**
- Phase 1 must include "migration aborts if existing duplicates exist" OR Phase 5 backfill must run BEFORE Phase 1.1 unique index applies. The natural ordering is:
  1. Phase 5.1 backfill flag `is_duplicate=true` on existing dupes (no DDL change).
  2. Phase 1.1 apply unique partial index `WHERE is_duplicate IS NOT TRUE AND bill_number IS NOT NULL` (the partial filter excludes flagged rows so the index can be built without violation).
  3. The dedup helper writes new rows with `is_duplicate=false` and the unique index fires only on un-flagged rows.

**Or** (even cleaner): the partial WHERE clause should be `WHERE is_duplicate IS NOT TRUE AND bill_number IS NOT NULL` — but that requires `is_duplicate` to exist on the table BEFORE the unique index is created. Currently Phase 1.3 adds `is_duplicate`. So the migration order must be: 003 (is_duplicate column) → 5.1 backfill → 001 (unique index with WHERE clause). The plan as written has 001 → 002 → 003 → 5.1, which is broken.

---

## BLOCKER 5 — Multiple analytics views read directly from `pos_orders` and Phase 5.2 only mentions `v_sync_drift_monitor`

**Severity:** BLOCKER (silent over-reporting persists)

**Where:** Phase 5.2 says "`pos_orders` views and rollups (`v_sync_drift_monitor`, any S171/S189 view) get a `WHERE is_duplicate IS NOT TRUE` filter."

**The gap:** Searching `pos_orders` references in views/migrations turned up these read sites that need the filter, NOT all of which are explicitly enumerated in Phase 5.2:

| File | Line | View/Query | Reads `pos_orders`? | Needs `WHERE is_duplicate IS NOT TRUE` |
|------|------|-----------|---------------------|----------------------------------------|
| `supabase/migrations/20260214_store_daily_closing.sql` | 96 | `v_system_daily_totals` | YES (FROM pos_orders) | YES |
| `supabase/migrations/20260215_fix_view_aliases_add_foodpanda.sql` | 117, 129 | `v_system_daily_totals`, `v_all_channel_daily` | YES | YES |
| `supabase/migrations/20260217_fix_views_add_status_filters.sql` | 63, 75, 208 | `v_all_channel_daily`, `v_ops_weekly`, `v_system_daily_totals` | YES | YES |
| `supabase/migrations/20260307_discount_identity_alerts.sql` | 199 | `discount_identity_alerts` view | YES (JOIN) | YES |
| `supabase/migrations/20260315_sales_dashboard_daily_metrics.sql` | 39, 82 | (the dashboard rollup) | YES | YES |
| `supabase/migrations/20260316zzz_..._materialized.sql` | 38, 81 | materialized version of above | YES | YES |
| `supabase/migrations/20260405_exclude_webdelivery_from_pos_views.sql` | 33, 45, 119, 196, 203, 228 | rebuild of `v_system_daily_totals`, `v_all_channel_daily`, `v_ops_weekly` | YES | YES |
| `supabase/migrations/20260414_s189_realtime_bom_consumption.sql` | 131, 383, 396, 410 | trigger function + `v_ingestion_reconciliation`, `v_webhook_coverage`, `v_store_internet_health` | YES (READ + TRIGGER) | YES — and the BOM trigger is the riskiest |
| `hrms/api/sales_dashboard.py` | 898, 1096, 1361, 1499, 2305, 2322 | `v_pos_orders_live` (view, def not in repo — production-only) | YES (via view) | The VIEW must filter, not the caller |

**The plan only commits to `v_sync_drift_monitor` plus "any S171/S189 view".** It does not enumerate `v_system_daily_totals`, `v_all_channel_daily`, `v_ops_weekly`, `discount_identity_alerts`, or — most critically — `v_pos_orders_live` which `sales_dashboard.py` reads from in 6+ places.

**Concrete consequence:** Even after Phase 5.2 ships, the Sales Dashboard, Discount Abuse alerts, Daily Closing, Ops Weekly, Aggregator JV all still read non-filtered `pos_orders`. The user-facing 17K PHP overage at Araneta Gateway (the original symptom) does not go away.

**The L3 scenario at line 462** says "Open Sales Dashboard → Araneta Gateway → 2026-04-20 to 2026-04-26 → Gross sales display reflects post-dedup total". This will fail unless `v_pos_orders_live` is updated.

**What's missing:**
- An explicit enumerated list of every view that reads `pos_orders` and a checklist confirming each gets the filter.
- A new migration to update `v_pos_orders_live` (the view definition is in production, not in this repo — likely lives in an earlier migration we don't have, OR was hand-created).
- Re-running `REFRESH MATERIALIZED VIEW CONCURRENTLY` for the materialized rollups (`sales_dashboard_daily_metrics_materialized`).

---

## HIGH 1 — `bill_number` may be per-terminal at multi-terminal stores; the unique index will over-deduplicate

**Severity:** HIGH

**Where:** Plan acknowledges in section "Pre-Implementation Finding" item 3, but punts to vendor outreach.

**The gap:** The plan acknowledges that `terminal_id` is missing from the API and that "If `bill_number` is sequenced per-terminal rather than per-store, our `(location_id, business_date, bill_number)` natural key would over-deduplicate at multi-terminal stores."

**Quantification:** Looking at `data/POS_Extraction/MOSAIC_POS_API_KEYS.csv` (49-row file = 48 stores), the candidates for multi-terminal operation include:
- SM Megamall (location_id=2338, BEBANG ENTERPRISE INC.)
- SM Mall of Asia (location_id=2219)
- SM North EDSA (location_id=2284)
- Araneta Gateway (location_id=2557)
- Ayala Fairview Terraces (2220)
- Ayala Market Market (2287)

Realistic estimate: BEI mall stores in high-traffic locations have 1-2 terminals. The plan provides no quantitative count. Probably 6-12 of the 48 stores are multi-terminal.

**Concrete consequence:** At a 2-terminal store, if both terminals start the day's bill counter at 1, the (loc, date, bill=1) pair collides between two real customers. The unique index rejects the second customer's order to `webhook_duplicates`. Real revenue is silently dropped.

**The plan is willing to ship this risk** because the audit found no evidence of it in the 14-day Araneta data. But the audit didn't run a multi-terminal probe across SM Megamall.

**What's missing:**
- Phase 0 should add a probe: query `pos_orders` for last 30 days grouped by `(location_id, business_date)`. For each store-day, check if the bill_number sequence has gaps (single-terminal) or interleaving (multi-terminal). Stores with interleaved-low-then-jump-high patterns are likely multi-terminal.
- A defensive fallback: if the unique index rejects an order at a known multi-terminal store, route to `webhook_duplicates` with reason `"multi_terminal_collision_review_required"` and surface in a daily report. Don't blackhole real revenue.
- Possibly: scope the unique partial index to only the stores Phase 0 verified as single-terminal, and use the cluster-window fallback at multi-terminal stores until Mosaic adds `terminal_id`.

---

## HIGH 2 — Race condition across 12 parallel credential workers

**Severity:** HIGH

**Where:** `scripts/sync_pos_to_supabase.py` parallel mode (lines 783-806). The cron runs every 10 min via `.github/workflows/pos-sync-5min.yml` (per S197).

**The gap:** Each credential group can sync independently. The dedup helper `find_bill_number_twin` does a SELECT, then the upsert does an INSERT. Between the SELECT and the INSERT, another worker on a different credential group can write a conflicting row.

**Two relevant scenarios:**
1. **Same store, two pollers:** Not relevant — each store maps to exactly one credential group.
2. **Different stores in different credential groups, sharing a bill_number value** (unlikely if `(location_id, ...)` is the key — bill_number alone collides across stores but the index includes location_id). **Not a problem.**
3. **Within ONE credential group, batched upsert:** A single credential group can serialize ~27 stores. But the upsert is a batch of orders for ONE store-day. If the batch contains 6 orders and 5 are duplicates of an existing row, ALL 6 are rejected by the partial unique index because PostgREST `on_conflict=id` and the bill-number index aren't reconciled.

**Real concern:** the cron runs every 10 min AND the cron has `cancel-in-progress: false` (per S197). Two consecutive cron runs CAN overlap if the first takes >10 min. Both will pull the same store-day overlap window. Both will get the same bill_number across distinct Mosaic IDs (the bug). Both will try to insert.

**What's missing:**
- The unique partial index alone provides safety. But the plan should specify that the dedup helper's SELECT-THEN-INSERT can race, and the resolution path (catching unique-violation 23505 and routing to `webhook_duplicates`) must be present, not just the pre-check.
- The plan's Phase 1.5 says "if the unique partial index throws via PostgREST despite the pre-check (rare race), catch the unique-violation error code and route to `webhook_duplicates`." Good. But this language only appears for `sync_pos_to_supabase.py`, not for `_upsert_completed_order` (1.5b).

---

## HIGH 3 — `webhook_duplicates` table name reused for poll-source dedups (maintainability)

**Severity:** HIGH (as plan-acknowledged); raising to call out the future cost.

**Where:** Plan section "Plan workstream re-targeting" notes "table name kept for continuity even though the source is poll."

**The gap:** Once 99.95% of rows in `webhook_duplicates` come from poll-source rejects, the name lies. Future agents will assume "webhook" is the source and miss poll-rejected rows. The audit story breaks.

**Recommendation:**
- Rename to `pos_duplicates` in this sprint. There's no cost — the table is being created by Phase 1.2 (no historical data to migrate). Or, keep the name and add column `source TEXT NOT NULL DEFAULT 'poll'` filled by the helper.

---

## MEDIUM 1 — `pos_orders.id` column type unverified

**Severity:** MEDIUM

**Where:** Plan Phase 1.2 declares `webhook_duplicates.order_id BIGINT PK, kept_order_id BIGINT`.

**The gap:** The plan does not include the `pos_orders` table CREATE statement (it predates the in-repo migrations — the table was created by S171 or earlier, definition not in the repo). All visible Mosaic Order IDs in the data range (e.g., 51481228 to 51499274) fit comfortably in INTEGER (32-bit max ~2.1B), but BIGINT is correct and matches `webhook_duplicates`. No actual issue if `pos_orders.id` is BIGINT. **Action: verify before Phase 1 ships.**

**Concrete check:** Add to Phase 0.5 (state_before.json) a column-type probe: `SELECT data_type FROM information_schema.columns WHERE table_name = 'pos_orders' AND column_name = 'id'`. If INTEGER, raise — Mosaic IDs growing past 2B in a few years would silently overflow.

---

## MEDIUM 2 — S189 BOM consumption trigger does not respect `is_duplicate`

**Severity:** MEDIUM

**Where:** `supabase/migrations/20260414_s189_realtime_bom_consumption.sql:122-170` (`fn_update_material_consumption_pos`).

**The gap:** The trigger fires on `pos_order_items` INSERT or UPDATE. It does NOT inspect `pos_orders.is_duplicate`. So:
- Going forward: items belonging to rejected duplicate orders (orphaned, see BLOCKER 3) still consume BOM. Material consumption is over-counted by ~5× per duplicate cluster.
- Backfill: Phase 5.1 sets `is_duplicate=true` on duplicate orders but doesn't reverse the BOM consumption that was already counted.

**What's missing:**
- The trigger must read `pos_orders.is_duplicate` (already in scope to add per Phase 1.3) and short-circuit if true.
- Phase 5.3 (cup recount) talks about cups but not BOM material consumption. Add a parallel `s232_recompute_bom_consumption.py` or document explicitly that BOM is materially over-counted historically and acceptable.

---

## MEDIUM 3 — POSTREGREST conflict-resolution semantics are not specified

**Severity:** MEDIUM

**Where:** `supabase_upsert(client, "pos_orders", order_rows, on_conflict="id")` at line 540 uses ONE on_conflict key.

**The gap:** PostgREST's `?on_conflict=id` only handles PK conflicts. The new unique partial index is on `(location_id, business_date, bill_number)`. When the partial index conflict fires, PostgREST returns 23505 unique_violation for the row, NOT a merge. The plan's helper must catch this. Currently `supabase_upsert` (line 174-185) is a thin wrapper that calls `r.raise_for_status()` — no catch. The dedup helper changes need to either:
- Pre-filter (the plan's primary path via `find_bill_number_twin`) — works but is racy.
- Use `Prefer: resolution=ignore-duplicates` — but that drops the row silently with no audit trail.
- Custom error handler around the POST that detects 23505 and routes the offending rows to `webhook_duplicates` while letting the rest of the batch proceed.

**The plan addresses this at high level** ("if the unique partial index throws via PostgREST despite the pre-check (rare race), catch the unique-violation error code and route to `webhook_duplicates`") but doesn't say WHO catches it — `supabase_upsert` itself, or the caller. Production-grade implementation requires per-row error handling because PostgREST's batch upsert returns 1 status code for the whole batch.

---

## Path coverage matrix — every code path that writes to `pos_orders`

| # | Path | Source file | Cron / trigger | Plan covers? | Risk if uncovered |
|--:|------|-------------|----------------|--------------|-------------------|
| 1 | API poll upsert | `scripts/sync_pos_to_supabase.py:539` | `.github/workflows/pos-sync-5min.yml` (5-min) | YES — Phase 1.5 | (primary path) |
| 2 | Webhook order.completed upsert | `hrms/api/mosaic_webhook.py:457` | Mosaic webhook (UNREGISTERED today) | YES — Phase 1.5b | future-proofed |
| 3 | Webhook order.cancelled UPDATE | `hrms/api/mosaic_webhook.py:151-162` | Mosaic webhook (REGISTERED, 12 endpoints) | NOT mentioned | UPDATE not affected by unique INDEX. **OK** for tombstone. **But:** when a cancelled order is later re-fired with new id (audit found this), the new id INSERT path fires the unique index, which sees the OLD (tombstoned) row and rejects. Tombstone survives. **Verified safe.** |
| 4 | `_upsert_completed_order` direct REST | `hrms/api/mosaic_webhook.py:476` (POST to PostgREST) | webhook | YES (via 1.5b) | see BLOCKER 1 |
| 5 | S171 tombstone reconciliation UPDATE | `scripts/verify_mosaic_pos_sync.py:457` | manual / on-demand | NOT mentioned | UPDATE only — does not insert. **Safe.** |
| 6 | S171 phantom tombstone UPDATE | `scripts/s171_full_parity_audit.py:723` | manual | NOT mentioned | UPDATE only. **Safe.** |
| 7 | S169 cleanup test orders UPDATE | `scripts/s169_cleanup_test_orders.py:114` | manual | NOT mentioned | UPDATE only. **Safe.** |
| 8 | `pos_orders_raw` upsert | `scripts/sync_pos_to_supabase.py:495` | 5-min cron (`--store-raw` flag) | NOT mentioned | see BLOCKER 2 |
| 9 | `pos_order_items` upsert (children of dups) | `scripts/sync_pos_to_supabase.py:541` | 5-min cron | NOT mentioned | see BLOCKER 3 |
| 10 | `pos_order_items` upsert (webhook) | `hrms/api/mosaic_webhook.py:486` | webhook | NOT mentioned | same shape as #9 |
| 11 | `pos_order_payments` upsert | `scripts/sync_pos_to_supabase.py:543` | 5-min cron | NOT mentioned | dependent on #9 |

---

## Tombstone path coverage (S169) — re-fire scenario

**Plan coverage:** Implicit only.

**Scenario:** A cancelled order (`cancelled_at` set, `order_status='CANCELLED'`) gets a new top-level Mosaic `id` in a later poll for the same `bill_number`. The webhook handler `_handle_order_cancelled` already wrote a tombstone on the OLD id. The poll script's upsert tries to insert the NEW id.

**With Phase 1's unique index in place:**
- `pos_orders_bill_number_natural_key` (location, date, bill_number) WHERE bill_number IS NOT NULL.
- The OLD tombstoned row has bill_number=N. The NEW row also has bill_number=N. Unique index rejects.
- Helper `find_bill_number_twin` returns the OLD tombstoned row's id as the existing twin.
- New row goes to `webhook_duplicates` with `kept_order_id = <tombstoned id>`.
- Tombstone survives. Cancellation state preserved. **OK.**

**But:** the helper must explicitly preserve tombstoned state when computing twins. If `find_bill_number_twin` ignores the `cancelled_at` filter, a re-fire of a cancelled order succeeds-as-duplicate-of-an-active-row only if a non-cancelled twin exists. Edge case: only ONE row exists, and it's tombstoned → the new row goes to webhook_duplicates → behavior is correct.

**Recommendation:** the plan's L3 scenarios should add: "replay-with-cancellation: poll receives a cancelled (tombstoned) order's bill_number with a NEW id; expect webhook_duplicates entry, kept_order_id = tombstoned_id, and `pos_orders` cancellation state preserved."

---

## Concrete to-do additions for the plan

To resolve the BLOCKERs:

1. **Phase 0.4** — also probe schema:
   - `SELECT data_type FROM information_schema.columns WHERE table_name='pos_orders' AND column_name='id';`
   - Verify multi-terminal stores via `bill_number` interleaving probe over last 30 days.

2. **Phase 1 ordering correction:**
   - 1.3 (add `is_duplicate` column) FIRST.
   - 5.1 (backfill flag duplicates) BEFORE 1.1 (unique index).
   - 1.1 (unique index) with WHERE `is_duplicate IS NOT TRUE AND bill_number IS NOT NULL`.

3. **New Phase 1.8** — extend dedup to children:
   - Add `pos_order_items.is_duplicate BOOLEAN`.
   - Helper rejects items along with parent.
   - All view + analytics joins filter both tables.

4. **New Phase 1.9** — extend to `pos_orders_raw`:
   - Decide policy: extract bill_number from `raw_json` and add unique index OR document `pos_orders_raw` as audit-only-by-Mosaic-id (NO ANALYTICS).

5. **Phase 1.5b explicit error handling:**
   - Catch 23505 from PostgREST. Return 200 with `handled: false, reason: "duplicate_routed"` so Mosaic doesn't pause webhook delivery.

6. **Phase 5.2 enumeration:**
   - Add migration files updating `v_system_daily_totals`, `v_all_channel_daily`, `v_ops_weekly`, `v_pos_orders_live`, `discount_identity_alerts`, `v_ingestion_reconciliation`, `v_webhook_coverage`, `v_store_internet_health`, `sales_dashboard_daily_metrics`, `sales_dashboard_daily_metrics_materialized`.
   - Run `REFRESH MATERIALIZED VIEW CONCURRENTLY sales_dashboard_daily_metrics_materialized` after backfill.

7. **New Phase 5.5** — fix BOM trigger:
   - `fn_update_material_consumption_pos` must read `pos_orders.is_duplicate` and short-circuit.
   - Add `s232_recompute_bom_consumption.py` to backfill consumption corrections.

8. **L3 scenarios additions:**
   - `replay-with-cancellation` — see tombstone scenario above.
   - `multi-terminal-collision` — same loc, same date, two real bill_number=1 from terminals A and B → both must be accepted (only feasible if multi-terminal stores get a separate path; otherwise document as known limitation).
   - `bom-consumption-no-double-count` — assert `daily_material_consumption.total_grams` does not increase when a duplicate is inserted.

---

## Final answer to "will this resolve all our duplicate issues?"

**No — not as written.** The plan addresses the headline duplicate problem on the primary write path (the API poll's `pos_orders` insert), but:

- **5 BLOCKER gaps** prevent end-to-end coverage:
  - Webhook upsert PostgREST conflict semantics aren't specified (BLOCKER 1)
  - `pos_orders_raw` is uncovered (BLOCKER 2)
  - `pos_order_items` orphan creation is uncovered (BLOCKER 3)
  - Migration ordering will fail Phase 1 against existing duplicates (BLOCKER 4)
  - Multiple analytics views still read non-filtered `pos_orders` (BLOCKER 5)

- **3 HIGH risks:**
  - Multi-terminal stores not quantified; risk of silent revenue drops (HIGH 1)
  - Race conditions across parallel cron workers underspecified (HIGH 2)
  - Misnamed `webhook_duplicates` table will confuse future agents (HIGH 3)

- **3 MEDIUM concerns:**
  - `pos_orders.id` column type unverified (MEDIUM 1)
  - S189 BOM consumption trigger ignores `is_duplicate` flag (MEDIUM 2)
  - PostgREST conflict-resolution semantics not documented (MEDIUM 3)

The user-visible symptom (Sales Dashboard showing 17K PHP overage at Araneta Gateway) **will NOT be fixed** until BLOCKER 5 is closed (the views need the filter, not just `pos_orders` getting the flag).

The `cups_sold` recount in Phase 5.3 **will be incorrect** until BLOCKER 3 is closed (orphan items still get counted unless `pos_order_items.is_duplicate` is added).

The very next poll after Phase 1.1 deploys **will throw 23505** until BLOCKER 4 ordering is fixed.

To make the plan resolve all duplicate issues end-to-end, address the 5 BLOCKERs above as patches to the existing phases (no new phase needed — they fold into Phases 1, 5).
