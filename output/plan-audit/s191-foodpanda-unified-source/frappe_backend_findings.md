# S191 Backend Audit Findings — FoodPanda Unified Source
**Audited:** 2026-04-12
**Plan file:** `docs/plans/2026-04-14-sprint-191-foodpanda-unified-source.md`
**Source file:** `hrms/api/sales_dashboard.py`
**MV file:** `supabase/migrations/20260316zzz_sales_dashboard_daily_metrics_materialized.sql`
**Auditor scope:** SQL correctness, cache coherence, PostgREST fallback, cache staleness, per-day edge cases, VAT formula, parameter threading, double-call risk, boundary overlap.

---

## Summary

| Severity | Count |
|---|---|
| CRITICAL | 3 |
| WARNING | 5 |
| INFO | 4 |

---

## CRITICAL Findings

### C-1: COALESCE treats Mosaic `gross = 0` as "no data" — zero-sales days invisible

**Location:** Plan design rationale SQL (lines 95–97 of plan), Phase 1 task 1.1

**Issue:** The FULL OUTER JOIN result uses:
```sql
COALESCE(m.gross, l.gross) AS gross,
COALESCE(m.net,   l.net)   AS net,
COALESCE(m.orders, l.orders) AS orders,
CASE WHEN m.gross IS NOT NULL THEN 'mosaic' ELSE 'legacy_sheet' END AS source
```

`COALESCE` falls through to the legacy value when `m.gross IS NULL`. But `m.gross` is `SUM(gross_sales)` — if a Mosaic-tracked store had **zero FoodPanda sales that day** (no rows match the `WHERE` filter), the CTE produces **no row at all** for that `(location_id, business_date)`. That is fine — the FULL OUTER JOIN will then have `m.*` all NULL and legacy wins, which is correct.

**However**, the problem is the reverse edge case: if a Mosaic store had exactly **one cancelled PAID order reversed to ₱0.00 gross**, `SUM(gross_sales) = 0` (not NULL), so `COALESCE(0, legacy_gross)` returns `0` and **drops the legacy data**. More concretely: `SUM(gross_sales) = 0.00` is a number, not NULL. The plan says "Mosaic wins on overlap" — but Mosaic winning with ₱0 when the real (legacy) gross is ₱500K is data loss, not a feature.

**Actual risk:** Low for most days (a zero-gross Mosaic FP row is rare), but possible in edge scenarios around the cutover week where early-onboarded stores had incomplete Mosaic data. It should be explicitly documented, and the plan's SQL should clarify the behavior.

**Recommended fix:** The plan should document this edge case explicitly, and the agent should add a comment in the helper:
```sql
-- NOTE: COALESCE treats Mosaic gross=0 as "Mosaic wins with zero sales".
-- This is intentional: once a store is on Mosaic, even a zero-sales day
-- is authoritative. Legacy data for that (store, day) is suppressed.
-- If this is undesired, replace with: CASE WHEN m.gross IS NOT NULL THEN m.gross ELSE l.gross END
-- (which has identical semantics to COALESCE, so the current behavior is correct-by-definition
-- but the intent should be documented).
```
Actually: `COALESCE(m.gross, l.gross)` and the explicit `CASE WHEN m.gross IS NOT NULL` are **semantically identical**. The real concern is whether ₱0 Mosaic should suppress non-zero legacy. The plan does not address this. Flag for CEO awareness before execution.

---

### C-2: `_aggregate_daily_series` still adds `foodpanda_vat_deducted_sales` from MV — double-count NOT eliminated for per-day series

**Location:** `hrms/api/sales_dashboard.py:2061`, `2652–2655`

**Issue:** `_aggregate_daily_series` at line 2058–2061 adds:
```python
bucket["superadmin_delivery_wo_vat"] += (
    _to_float(row.get("website_non_cod_net_sales_without_vat"))
    + _to_float(row.get("web_cod_net_sales_without_vat"))
    + _to_float(row.get("foodpanda_vat_deducted_sales"))  # legacy sheet, usually 0
)
```

The comment says `# legacy sheet, usually 0` — but for Feb and pre-cutover March dates, `foodpanda_vat_deducted_sales` is NOT zero (it holds the full legacy FP net from the MV). After S191 fixes `_get_mosaic_channel_split_per_day`, the per-day `split["foodpanda"]` in the `mosaic_split_per_day` dict will now include the unified (legacy + Mosaic) FoodPanda net. But `superadmin_delivery_wo_vat` also still adds `foodpanda_vat_deducted_sales` from the MV (lines 2058–2062). Then line 2084–2085:
```python
bucket["delivery_sales_without_vat"] = mosaic_delivery_wo_vat + bucket["superadmin_delivery_wo_vat"]
```
where `mosaic_delivery_wo_vat` includes the new unified FP net from `split["foodpanda"]`. This means:

**For pre-cutover Mar days:** `delivery_sales_without_vat` = `(legacy FP net via unified split)` + `(legacy FP net from MV via superadmin_delivery_wo_vat)` = **double-count**.

**The plan does not fix this.** Phase 3 only fixes `_get_mosaic_channel_split_per_day` to return the unified FP figure — but does not touch `_aggregate_daily_series` to remove the `foodpanda_vat_deducted_sales` addend.

**Severity:** CRITICAL — the per-day delivery totals and `net_sales_without_vat` in the time-series chart will be inflated for all pre-cutover dates (Feb 1 – Mar ~26). This affects L3-191-07 and L3-191-08 directly.

**Recommended fix:** The plan must add a task to update `_aggregate_daily_series` line ~2061: remove `_to_float(row.get("foodpanda_vat_deducted_sales"))` from `superadmin_delivery_wo_vat`. After S191, the FoodPanda contribution to delivery comes exclusively through `mosaic_split_per_day["foodpanda"]` (unified). The MV `foodpanda_vat_deducted_sales` addend must be zeroed out or removed.

Same issue at line 2652–2655 in the per-store row builder — adds `foodpanda_vat_deducted_sales` to `delivery_sales_without_vat`. That function is not in S191's scope (Surface Ownership Matrix), but it will also double-count if called for pre-cutover dates. Mark as out-of-scope but document.

---

### C-3: PostgREST fallback for legacy `foodpanda_orders` uses paginated row fetch — field `business_date` may not exist in `v_pos_orders_live` PostgREST params, but the legacy table fetch needs `order_status` not `payment_status`

**Location:** Plan Phase 1, task 1.2

**Issue:** The plan says the PostgREST fallback does two separate fetches: Mosaic (`v_pos_orders_live`) and legacy (`foodpanda_orders`). The Mosaic fetch mirrors the existing pattern at line 880–887. The legacy fetch must filter `lower(order_status) = 'delivered'` — but PostgREST does not support `LOWER()` function calls in filter params natively. The existing pattern uses `eq.PAID` for `payment_status` — a direct equality match. For `foodpanda_orders`, the correct PostgREST filter would be `("order_status", "ilike.delivered")` (case-insensitive LIKE), not `("lower(order_status)", "eq.delivered")`.

**If the agent writes** `("order_status", "eq.delivered")` it will miss rows where `order_status = 'Delivered'` (capital D) — the legacy data uses mixed case (confirmed by the SQL in MV: `WHERE lower(order_status) = 'delivered'`).

**The plan does not specify the exact PostgREST filter syntax for the legacy fallback.** This is a gap that the agent will likely get wrong.

**Recommended fix:** The plan should specify: use `("order_status", "ilike.delivered")` for the PostgREST legacy fetch, NOT `eq.delivered`. Add explicit note to task 1.2.

---

## WARNING Findings

### W-1: VAT formula `SUM(subtotal / 1.12)` vs `SUM(subtotal) / 1.12` — confirmed correct but plan claim needs precision

**Location:** Plan line 128, MV `supabase/migrations/20260316zzz_sales_dashboard_daily_metrics_materialized.sql:70`

**Verified:** The MV definition at line 70 is:
```sql
coalesce(sum(subtotal / 1.12), 0)::numeric(14,2) as foodpanda_vat_deducted_sales
```

This is `SUM(subtotal / 1.12)` — division happens **per row before aggregation**, NOT `SUM(subtotal) / 1.12` (aggregation first, then divide). The plan's proposed SQL in the FULL OUTER JOIN CTE uses:
```sql
SUM(subtotal / 1.12) net
```
This matches the MV exactly. **Good — no discrepancy.**

**However:** `SUM(subtotal / 1.12)` vs `SUM(subtotal) / 1.12` are algebraically equivalent (`SUM(x/c) = SUM(x)/c` for constant `c`). The rounding difference only arises if intermediate `numeric(14,2)` truncation is applied per-row (as in the MV's `::numeric(14,2)` cast). The MV casts the **final SUM** to `numeric(14,2)`, not each row. In Postgres, `subtotal / 1.12` returns `numeric` with high precision (no per-row truncation) and the outer cast rounds the aggregate. The plan's CTE does the same — no per-row cast. So both produce identical results.

**Status:** Correct. No change needed. But the plan's claim "matches the MV formula" is accurate and confirmed.

---

### W-2: Cache key `"fp_unified"` does NOT invalidate the **overview-level** cached payload that was built from the old Mosaic-only `fp_bucket`

**Location:** Plan Phase 1, HARD BLOCKER 1-1; `hrms/api/sales_dashboard.py:396–405`

**Issue:** `_sales_dashboard_cache_key("fp_unified", ...)` creates a NEW key for the new helper. This correctly bypasses any old `"foodpanda"` or `"mosaic_split"` prefixed keys. **However**, the higher-level overview response (e.g., `get_sales_dashboard_overview`) is likely itself cached under its own key (e.g., `"sales_dashboard:overview:..."` or similar). If that outer cache entry was built before S191 deploy and has a 300s TTL, it still contains the old Mosaic-only `foodpanda_sales` values in its payload — even though the inner helper now returns the correct unified figure.

**Risk:** Up to 300s post-deploy (the TTL), the overview endpoint returns stale ₱4.4M FoodPanda. The inner `"fp_unified"` key is properly invalidated, but the outer overview cache isn't.

**The plan acknowledges** "cache key prefix change to `fp_unified` ensures old bucket is bypassed post-deploy" (BLOCKER 1-1) — but this only covers the helper's own cache, not the consumer endpoint's cache.

**Recommended fix:** Add a task to Phase 2 or Phase 0 closeout: on deploy, flush the `sales_dashboard:*` Redis key namespace (or wait 300s). Alternatively, use a deploy-time cache bust by incrementing a version suffix in the overview cache key. At minimum, add a Phase 4 task note: "Wait ≥5 minutes post-deploy before running L3 verification to allow cache TTL to expire."

---

### W-3: `_get_store_channel_split_map` return type mismatch — plan says `{gross, net_wo_vat, orders}` but existing function returns only `{net_wo_vat}` per channel

**Location:** `hrms/api/sales_dashboard.py:1067–1122`, Plan Phase 3, task 3.2

**Issue:** The existing `_get_store_channel_split_map` SQL (line 1067–1078) selects only `SUM(net_sales)::numeric(14,2) AS net_wo_vat` — no `gross`, no `orders` count. The existing per-store bucket shape from this function is `{pos: float, foodpanda: float, ...}` (a single float per channel, not a sub-dict).

The plan task 3.2 says: "call `_get_unified_foodpanda_totals(...)`, sum all `business_date` entries per store to get `{gross, net_wo_vat, orders}`, then **override** `result[location_id]["foodpanda"]` with this aggregated bucket."

But the existing `result[location_id]["foodpanda"]` is a **float** (just `net_wo_vat`), not a dict with `gross/net_wo_vat/orders` keys. If the agent replaces a float with a dict, it will break every consumer that reads `store_split["foodpanda"]` expecting a float.

**Recommended fix:** Before implementing task 3.2, the agent must check how `_get_store_channel_split_map`'s result is consumed (what keys are read from `result[location_id]["foodpanda"]`). The plan assumes both functions return the same `{gross, net_wo_vat, orders}` shape — verify against the consumer at call sites. The S182 implementation explicitly confirms the per-store result is a single float per channel key (line 1117: `bucket[canon_key] += _round_half_up(_to_float(row.get("net_wo_vat")))`). The plan needs to align the shape, or the agent will break the leaderboard.

---

### W-4: `_apply_mosaic_channel_split` double-calls `_get_mosaic_channel_split` AND (after S191) `_get_unified_foodpanda_totals_aggregate` — two SQL round-trips for what could be one

**Location:** Plan Phase 2, task 2.1; `hrms/api/sales_dashboard.py:946`

**Issue:** After S191, `_apply_mosaic_channel_split` will:
1. Call `_get_mosaic_channel_split(...)` → 1 SQL to `v_pos_orders_live` (returns all channels including FoodPanda from Mosaic)
2. Call `_get_unified_foodpanda_totals_aggregate(...)` → 1 SQL FULL OUTER JOIN (`v_pos_orders_live` + `foodpanda_orders`)

`v_pos_orders_live` is queried **twice** (once for all channels, once inside the FULL OUTER JOIN for FP only). The Mosaic FP rows from step 1 are then discarded (`split.pop("foodpanda", ...)` result is overwritten by `fp_unified`). This is a wasted DB round-trip.

**Severity:** Functional correctness is fine (the cache at 300s TTL means this only matters on cache-miss). Not a blocking issue, but worth noting. For a 14-day window this was previously 617ms (one SQL). Adding a second SQL for the FULL OUTER JOIN adds ~300–800ms on cache miss. Acceptable given 300s TTL, but document the trade-off.

---

### W-5: Plan's `_get_unified_foodpanda_totals` return type is `dict[int, dict[str, dict]]` (store → date → bucket) but `_get_mosaic_channel_split_per_day` needs `dict[str, dict]` (date → bucket) — aggregation logic is agent-implemented, not specified

**Location:** Plan Phase 3, tasks 3.4–3.5

**Issue:** The plan says `_get_unified_foodpanda_totals` returns `location_id → business_date_isoformat → {gross, net_wo_vat, orders, source}`. For Phase 3 task 3.5, the agent must aggregate across all stores per day: iterate all location_ids, sum `gross/net_wo_vat/orders` per `date_iso`. This is straightforward but the plan does not write the aggregation code — it says "Aggregate across all stores per day: `fp_by_day: dict[date_iso, {gross, net_wo_vat, orders}]`" without showing the loop.

The risk is the agent using a naïve `dict.update()` (last-store wins) instead of a proper additive loop. This is a gap in the plan's specification for task 3.5 that could produce wrong per-day totals if the agent implements it incorrectly.

**Recommended fix:** The plan should include a pseudocode snippet for the date aggregation loop in task 3.5, similar to how the SQL is explicitly provided in Phase 1.

---

## INFO Findings

### I-1: MV `foodpanda_vat_deducted_sales` formula confirmed — `SUM(subtotal / 1.12)` per row, not `SUM(subtotal) / 1.12`

**Location:** `supabase/migrations/20260316zzz_sales_dashboard_daily_metrics_materialized.sql:70`

The MV computes: `coalesce(sum(subtotal / 1.12), 0)::numeric(14,2)`. Division is per-row, cast is on the aggregate. The plan's SQL matches this. No rounding discrepancy exists because Postgres applies no intermediate truncation on `numeric / 1.12` (returns high-precision numeric). **Confirmed correct.**

---

### I-2: Cache key signature for `_sales_dashboard_cache_key` — verified compatible

**Location:** `hrms/api/sales_dashboard.py:396–405`

The `_sales_dashboard_cache_key` signature is:
```python
def _sales_dashboard_cache_key(
    prefix: str,
    location_ids: list[int],
    start_day: date | None = None,
    end_day: date | None = None,
    view_mode: str | None = None,
    channel: str | None = None,
    include_comparisons: bool | None = None,
    ranking_mode: str | None = None,
) -> str:
```

The plan's proposed call `_sales_dashboard_cache_key("fp_unified", location_ids, start_day=start_day, end_day=end_day)` is **compatible** — uses the first 4 parameters only, all optional extras default to `None` and are excluded from the key. Cache key will be: `"sales_dashboard:fp_unified:<loc_csv>:<start>:<end>"`. Correct.

---

### I-3: Boundary overlap (Mar 26) behavior — confirmed correct and intended

**Location:** Plan Design Rationale, "Why Mosaic wins on overlap"

For a store that went live on Mosaic Mar 27, the (store, Mar 26) row: legacy has data, Mosaic has no rows → FULL OUTER JOIN returns `m.*` all NULL → `COALESCE(m.gross, l.gross)` = legacy gross. Correct — legacy data is preserved for pre-cutover days. For stores that went live earlier (e.g., Mar 22), (store, Mar 26): Mosaic has data, legacy also has data → Mosaic wins. **This is the intended behavior per CEO directive.** No code issue — confirming design is sound.

---

### I-4: `_FOODPANDA_MOSAIC_START` constant at line 31 is still referenced at line 1296 freshness warning

**Location:** `hrms/api/sales_dashboard.py:1296–1301`

The freshness warning reads: `if start_day < _FOODPANDA_MOSAIC_START:` and emits a message about the source split. After S191, this warning text will be slightly misleading (it says "split at 2026-03-27" but the real split is per-store). The plan task 2.4 addresses the constant's deprecation comment but does NOT update the warning message text at line 1296–1301. The plan should add a task to update the warning string to reflect the per-store cutover reality (e.g., "FoodPanda source changed per store during the week of 2026-03-21 to 2026-03-27; pre-cutover dates use the legacy Google Sheet, post-cutover uses Mosaic.").

---

## Audit Checklist Response (from Plan's Regression Checklist)

| Check | Verdict |
|---|---|
| FULL OUTER JOIN at (location_id, business_date) grain | Plan SQL is correct; no issue |
| Mosaic wins on overlap | COALESCE logic correct; C-1 edge case (Mosaic gross=0) needs documentation |
| Legacy-only days preserved | Correct in SQL |
| Mosaic-only days preserved | Correct in SQL |
| Legacy net = `subtotal / 1.12` | Confirmed matches MV (I-1) |
| `LOWER(order_status) = 'delivered'` filter | SQL correct; PostgREST fallback has gap (C-3) |
| `payment_status = 'PAID'` filter | Correct |
| Result shape `{gross, net_wo_vat, orders}` | Shape mismatch in `_get_store_channel_split_map` consumer (W-3) |
| GrabFood untouched | Plan hard-blocks this correctly |
| All three functions updated | Phase 3 covers all three |
| Cache key invalidates old bucket | Helper cache correct; outer overview cache not invalidated (W-2) |
| Verification baseline ≥ ₱20M | Defined in Phase 4 |
| Sentry instrumentation unchanged | Verified — no new `@frappe.whitelist()` endpoints |
| `_FOODPANDA_MOSAIC_START` retained | Yes, at line 31 + deprecation comment task 2.4 |

---

## Recommended Pre-Execution Plan Amendments

1. **[CRITICAL/C-2]** Add Phase 3 task 3.6 (renumber existing 3.6→3.7, 3.7→3.8): Remove `_to_float(row.get("foodpanda_vat_deducted_sales"))` from `superadmin_delivery_wo_vat` accumulator in `_aggregate_daily_series` (line ~2061). This is the most important fix missing from the plan.

2. **[CRITICAL/C-3]** Update Phase 1 task 1.2: specify PostgREST filter for legacy table as `("order_status", "ilike.delivered")`, not `eq.delivered`.

3. **[CRITICAL/C-1]** Add documentation note: when Mosaic `SUM(gross_sales) = 0.00` for a (store, day), COALESCE drops legacy data. Decision: is this intended? If yes, document. If no, no code change needed (behavior is already correct-by-definition).

4. **[WARNING/W-3]** Add Phase 3 pre-task: read every call site of `_get_store_channel_split_map` and confirm whether the `["foodpanda"]` value is consumed as a float or as a dict. Align the override to match the existing shape.

5. **[WARNING/W-2]** Add Phase 4 task: post-deploy, wait ≥5 min before L3 (or explicitly flush `sales_dashboard:*` Redis keys via `frappe.cache().delete_keys("sales_dashboard:*")`).

6. **[INFO/I-4]** Add task 2.4b: update warning string at `sales_dashboard.py:1297–1301` to reflect per-store cutover (not a global 2026-03-27 date).
