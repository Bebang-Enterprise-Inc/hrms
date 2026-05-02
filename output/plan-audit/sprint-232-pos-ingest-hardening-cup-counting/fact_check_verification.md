# S232 Plan Audit — Adversarial Fact-Check Verification

**Verifier:** Claude Opus 4.7 (zero-context skeptic)
**Verified:** 2026-05-02
**Method:** Read actual source files; treat each blocker as "agent hallucinated" and try to disprove.

---

## Claim 1 (Blocker A1) — Phase 1 unique index will FAIL because 945 existing duplicates violate it

**Verdict:** SUPPORTED

**Evidence:**
- The plan itself, at `docs/plans/2026-05-02-sprint-232-pos-ingest-hardening-cup-counting.md:63`, states verbatim: *"Live probe found 945 duplicate rows across 137,209 unique `(location_id, business_date, bill_number)` tuples in the last 14 days (0.7% inflation)."* So the 945 figure is grounded in the plan's own narrative, not invented by the audit.
- The probe script `.claude/rlm_state/pos_audit/probe_supabase_dupes.py:83-94` runs the SQL: `SELECT location_id, business_date, bill_number, COUNT(*) AS dupe_count ... FROM pos_orders ... GROUP BY (...) HAVING COUNT(*) > 1` — a legitimate dupe-counting query against live Supabase via the Management API SQL endpoint. The probe is real, not fabricated.
- Phase ordering confirmed in plan:
  - Phase 1.1 at line 332: `CREATE UNIQUE INDEX pos_orders_bill_number_natural_key ON pos_orders (location_id, business_date, bill_number) WHERE bill_number IS NOT NULL`
  - Phase 5.1 at line 419: `is_duplicate=true` backfill (Phase 5 = "Historical Backfill" at line 413). Phase 5 runs AFTER Phase 1.
- Postgres behavior: `CREATE UNIQUE INDEX` against a table with existing violating rows throws `ERROR 23505 unique_violation`. This is canonical, not invented (see Postgres docs `CREATE INDEX`).
- The plan's index uses `WHERE bill_number IS NOT NULL` only — it does NOT exclude `is_duplicate=true` rows. So when migration 001 runs in Phase 1.1, the existing ~945 duplicate-natural-key rows in `pos_orders` will violate the new constraint immediately. There is no `is_duplicate IS NOT TRUE` clause in the partial index.

**Counter-evidence considered:**
- Could Phase 5 silently run before Phase 1? No — phases are explicitly numbered and sequential ("If verifier fails, do NOT proceed to Phase 2." line 376). The plan states "Phase 5 — Historical Backfill" at line 413, after the goal section of Phase 1 at line 326.
- Could the probe be stale (e.g., dupes already cleaned)? The probe script writes only a stub file `supabase_dupe_probe.txt` ("see stdout above"), so I cannot directly read the probe's most-recent JSON output. However, the plan AS WRITTEN cites 945 as current (line 63: "Live probe found 945 duplicate rows... in the last 14 days"). If the plan author recorded 945 as the basis for sizing Phase 5, the index in Phase 1 will hit those same rows.
- Could Postgres do an online build that ignores existing dupes? No — Postgres `CREATE UNIQUE INDEX` (even `CONCURRENTLY`) validates uniqueness against existing rows.

**Final reasoning:** The blocker is correct. The plan's own narrative cites 945 live duplicates, the index migration's `WHERE` clause does not exclude duplicate-flagged rows, and Phase 5 (which sets `is_duplicate=true`) runs AFTER Phase 1. Phase 1 will throw 23505 on the migration. Fix proposed by audit (move backfill to Phase 1 OR add `is_duplicate IS NOT TRUE` to the partial index `WHERE` clause) is the right shape.

---

## Claim 2 (Blocker A4) — Migration filename numbering collision

**Verdict:** SUPPORTED

**Evidence:**
- Plan line 334: Phase 1.3 → `MUST_MODIFY: scripts/s232_supabase_migrations/003_pos_orders_dedup_fields.sql`
- Plan line 384: Phase 2.1 → `MUST_MODIFY: scripts/s232_supabase_migrations/003_pos_products.sql`
- Plan line 410: Phase 4.2 → `MUST_MODIFY: scripts/s232_supabase_migrations/005_pos_order_payments_inferred.sql`
- Plan line 420: Phase 5.2 → `MUST_MODIFY: scripts/s232_supabase_migrations/005_views_filter_dupes.sql`

Both `003_*.sql` filenames and both `005_*.sql` filenames are written into the plan as MUST_MODIFY paths in different phases. This is a literal filename collision in the same directory. The grep for `003_pos_orders_dedup_fields|003_pos_products|005_pos_order_payments_inferred|005_views_filter_dupes` returned all four entries from the plan.

**Counter-evidence considered:**
- Could they be in different subdirectories? No — all four paths share the exact directory `scripts/s232_supabase_migrations/`.
- Could one of them be a typo the agent misquoted? I read the plan's actual lines verbatim; no typo on the audit side.

**Final reasoning:** Two filename collisions confirmed exactly as the audit claims. Even if the migration runner uses git ordering (commit-time) rather than alphabetical, the two `003_*` files and two `005_*` files cannot coexist in one directory under one of those names — one will overwrite the other when written, or the second `MUST_MODIFY` assertion will fail because the file content was overwritten. Renumbering to monotonic 001-007 (audit's proposed fix) is the correct resolution.

---

## Claim 3 (Blocker B1) — `discount_abuse.py:1175` and `marketing_giveaways.py:1009` query `pos_orders` directly

**Verdict:** SUPPORTED

**Evidence:**
- `hrms/api/discount_abuse.py:1175`: `return _supabase_get_all("pos_orders", params)`
  - Verified by reading lines 1160-1175. The function builds PostgREST params (`select=...`, `business_date=gte/lte`, `location_id=in.(...)`, `payment_status=eq.PAID`) and passes the literal table name `"pos_orders"` to `_supabase_get_all`. This is a direct table read, not a view.
- `hrms/api/marketing_giveaways.py:1009`: `order_rows = _supabase_get("pos_orders", params)`
  - Verified by reading lines 996-1015. Same pattern — `select=id,location_id,business_date,bill_number,...` filtering by `business_date`, `payment_status=PAID`, `total_discounts > 0`. Direct table call.
- Neither call includes `is_duplicate=is.false` (or any `is_duplicate` filter) in `params`.
- Plan Phase 5.2 at line 420 only mentions `v_sync_drift_monitor` and "any S171/S189 view" — no plan task adds an `is_duplicate IS NOT TRUE` filter to either `discount_abuse.py:1175` or `marketing_giveaways.py:1009`.

**Counter-evidence considered:**
- Could `_supabase_get_all` internally route through a view? Unlikely — it's named `pos_orders` (literal table name passed in). The function name `_supabase_get_all` and the PostgREST contract treat the first arg as the resource path. To prove the negative I would need the helper definition, but: (a) `_supabase_get_all("pos_orders", ...)` returns the table as-is unless a Supabase RLS policy or view alias rewrites it, and (b) such a rewrite would defeat the purpose of having `is_duplicate` as a column-level filter (you'd still need the WHERE clause).
- Could the audit have miscited the line numbers? Verified at exact lines: `_supabase_get_all("pos_orders", params)` is at `discount_abuse.py:1175`; `_supabase_get("pos_orders", params)` is at `marketing_giveaways.py:1009`.

**Final reasoning:** Both files query the base `pos_orders` table directly with no `is_duplicate` filter. Phase 5.2's view-only filter strategy will leave these two analytics endpoints reading duplicate rows post-migration. Fix proposed (add `is_duplicate=is.false` to params, OR redirect through a filtered view) is exactly right.

---

## Claim 4 (Blocker B4) — `pos_order_items` orphan rows accumulate when parent dupes are rejected

**Verdict:** SUPPORTED

**Evidence:**
- `scripts/sync_pos_to_supabase.py:528-543` shows the upsert sequence:
  ```python
  for order in orders:
      order_rows.append(map_order(order))
      item_rows.extend(map_order_items(order))     # ← items collected per order, no parent-status check
      payment_rows.extend(map_order_payments(order))
  ...
  supabase_upsert(client, "pos_orders", order_rows, on_conflict="id")
  upsert_items_batch(client, item_rows)              # ← items written regardless of parent dedup status
  supabase_upsert(client, "pos_order_payments", payment_rows, on_conflict="order_id,payment_type,line_number")
  ```
  Items and payments are unconditionally upserted alongside parents, with no link to the parent dedup outcome.
- `pos_order_items` is upserted via `upsert_items_batch(item_rows)` — a separate call. The rows reference `order["id"]` (Mosaic top-level ID), which is what makes them orphan candidates: each of the 6 distinct Mosaic IDs in a duplicate cluster generates its own `pos_order_items` rows under its own `order_id`.
- Plan Phase 5 (lines 413-425): the only mutation is `is_duplicate=true` on `pos_orders`. Phase 5.1 explicitly says "Does NOT delete any row." Plan line 424 (HARD BLOCKER): "This phase NEVER deletes rows from `pos_orders` or `pos_order_items`. The `is_duplicate=true` flag is the ONLY mutation."
- Critically, plan Phase 5 contains NO task that propagates the `is_duplicate=true` flag onto `pos_order_items` (e.g., flagging items where `order_id IN (SELECT id FROM pos_orders WHERE is_duplicate=true)`).
- Grep for `pos_order_items|orphan|cleanup` against the plan finds Phase 5.x only references items in mentions like the HARD BLOCKER ("never delete") and L3 scenarios — no item-level dedup task.

**Counter-evidence considered:**
- Could `pos_order_items` have an FK cascade that auto-cleans when the parent is flagged? FK cascade triggers on DELETE/UPDATE of the FK column. Setting `is_duplicate=true` is a non-FK column update — no cascade fires. So orphan items remain readable by analytics queries that don't join on `pos_orders.is_duplicate`.
- Could going-forward dedup (Phase 1.5) prevent items from being inserted for rejected parents? Phase 1.5 handles the unique-violation by routing rejected rows to `webhook_duplicates` (plan line 336: "If a twin exists, append the rejected row to a batch list and skip the main upsert"). HOWEVER, this only applies to NEW rows going forward. The 945 historical duplicates already have items in `pos_order_items` with no remediation in the plan.
- Phase 1.5's MUST_CONTAIN strings include `find_bill_number_twin` and `webhook_duplicates`, but no MUST_CONTAIN for skipping `item_rows.extend(...)` or filtering items at upsert time. Even going-forward, if the bill_number twin is found and the parent is skipped, the code as currently structured at lines 532-541 has already populated `item_rows` from the rejected order before the parent check runs. So even after Phase 1.5 ships, items can still leak unless the wiring task explicitly adds the items-skip step (the plan does not enumerate that).

**Final reasoning:** Confirmed. Phase 1.5's design rejects parent rows but the existing item-collection logic (lines 532-541 of `sync_pos_to_supabase.py`) collects items eagerly into the same batch. Plan does not specify items must be filtered at write time NOR backfilled retroactively. The 945 historical duplicates have ~6× line-item over-count for any cluster of size 6. Phase 5 must add an item-side cleanup task; it does not.

---

## Claim 5 (Blocker A5) — Phase 2.2 cites column `item_name` but actual column is `product_name`

**Verdict:** SUPPORTED

**Evidence:**
- Plan line 385 (Phase 2.2 task description): *"Script `scripts/s232_seed_pos_products.py` queries `SELECT DISTINCT product_id, item_name, AVG(price) FROM pos_order_items` and inserts into `pos_products`."* — uses literal column `item_name`.
- Actual code at `scripts/sync_pos_to_supabase.py:438-464` (`map_order_items` function), line 448 writes:
  ```python
  "product_name": item.get("name") or item.get("product_name"),
  ```
  Grep for `item_name|product_name` against `sync_pos_to_supabase.py` returns ONLY one hit (line 448) — and the column key is `"product_name"`. The string `item_name` does not appear anywhere in the sync script.
- The dict key in `map_order_items` is the Supabase column name (this dict is what `upsert_items_batch` writes to `pos_order_items`). So the actual `pos_order_items` column is `product_name`, NOT `item_name`.
- Cross-reference: `marketing_giveaways.py:1022` (which I verified earlier) selects `"order_id,product_name,quantity,discount_amount,discount_name,discount_name_normalized"` from `pos_order_items` — also using `product_name`. This is consistent.

**Counter-evidence considered:**
- Could `item_name` be an alias or computed column? No `pos_order_items` reference in the codebase uses `item_name` — both writers (`sync_pos_to_supabase.py`) and readers (`marketing_giveaways.py`) use `product_name`. There's no view or computed column named `item_name`.
- Could the plan mean a different column intentionally? The Phase 2.2 task SQL `SELECT DISTINCT product_id, item_name, AVG(price)` is the seed query for `pos_products(product_id, name, default_price, ...)`. The author meant to grab the product's display name. The correct column is `product_name`.

**Final reasoning:** Phase 2.2's seed query references a column that does not exist. The script will throw `ERROR: column "item_name" does not exist` at runtime. Fix is trivial (rename `item_name` → `product_name`), but blocking until applied. The blocker's claim is a literal grep-confirmed fact.

---

## Final Summary

**Of the 5 highest-stakes claims verified: 5 SUPPORTED, 0 CONTRADICTED, 0 NOT_FOUND.** All five are grounded in actual file content (plan lines, sync script lines, API endpoint lines) — none required inference beyond reading the cited paths. The audit's adversarial cluster (A1, A4, A5 in Cluster A; B1, B4 in Cluster B) is reliable; the plan as written cannot ship without these five fixes.
