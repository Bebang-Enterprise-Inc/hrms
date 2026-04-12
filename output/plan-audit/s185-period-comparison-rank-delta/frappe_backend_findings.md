# S185 Backend Plan Audit — Frappe/Python Findings
**Sprint:** S185 — Sales Analytics: Period-over-Period Comparison per Store + Weekly Rank Delta
**Auditor:** Subagent / 2026-04-12
**Scope:** READ-ONLY analytics. DM-1 through DM-6 are N/A (no GL entries, no DocType mutations).
**Source files read:** `hrms/api/sales_dashboard.py` (lines 55, 200–420, 590–616, 1384–1515, 1756–1803, 2403–2565, 3060–3121)

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 2 |
| WARNING  | 5 |
| INFO     | 4 |

---

## CRITICAL Findings

### C-1 — Cache key collision: prior-period rows share key with current-period rows under same date range

**Location:** Task 1.3 — `_cache_get_or_set` call for prior period inside `_build_store_rankings()`

**Problem:**
`_query_daily_rows()` already caches its result under the key:
```
sales_dashboard:daily_rows:<sorted_location_ids>:<prev_start>:<prev_end>
```
That is correct and reuse is safe. **However**, the plan proposes that `_build_store_rankings()` will call `_query_daily_rows(prev_start, prev_end, location_ids)` with `_cache_get_or_set` at **300 s TTL** — the same TTL as the current-period call.

The collision risk is subtle but real: `_sales_dashboard_cache_key()` (line 396) includes `include_comparisons` in the **outer endpoint** cache key (the overview wrapper cached at line 2817/2924), but `_query_daily_rows` itself does NOT see `include_comparisons`. Its cache key is purely `(prefix, location_ids, start_day, end_day)`.

This is safe as long as `_build_store_rankings()` calls `_query_daily_rows` directly (sharing the existing cache entry). The risk activates if the plan introduces a **new `_cache_get_or_set` wrapper around the per-store aggregation result** (`prev_by_location`) rather than wrapping only the raw row fetch. If the aggregation is cached separately, a key must be constructed that includes `"per_store_prev"` as a prefix **and** both date bounds — otherwise a second call with the same stores but different date window (e.g., current week vs. prior week both cached at the same time) will return stale per-store data.

**Fix required:**
- Do NOT add a new `_cache_get_or_set` wrapper around `prev_by_location`. Reuse `_query_daily_rows` (which already caches), then aggregate in-process.
- If a separate cache entry for the aggregated result is added, the cache key MUST include both `prev_start` and `prev_end` as distinct components, not just the shifted delta. Use `_sales_dashboard_cache_key("store_prev_agg", location_ids, start_day=prev_start, end_day=prev_end)`.

---

### C-2 — RBAC scope leakage risk: rank assignment must operate on `scope["selected_stores"]` only, not on all rows returned by `_query_daily_rows`

**Location:** Tasks 1.6 and 1.7 — rank current stores / rank prior period stores

**Problem:**
`_query_daily_rows` accepts `location_ids` which is derived from `scope["selected_stores"]` at call time. This is correct. **However**, the plan's Task 1.4 says:
```
prev_by_location[location_id] = {net_sales, gross_sales}
```
This dict is populated by iterating over raw Supabase rows. If any row in the prior-period result set carries a `location_id` not present in `scope["selected_stores"]` (e.g., a store that was accessible in the prior period but has since been removed from the user's RBAC scope, or a data anomaly), that location will silently enter `prev_by_location` and influence rank positions.

`_build_store_rankings()` (line 2441) guards this correctly for the current period via `store_lookup = {store["location_id"]: store for store in scope["selected_stores"]}` — rows with no matching `store_lookup` entry are still accumulated but get a `None` warehouse. The rank list is then sorted, so a ghost `location_id` from a prior period could appear ranked alongside authorized stores.

**Fix required:**
When building `prev_by_location`, filter to only `location_id` values present in `scope["selected_stores"]`:
```python
allowed_ids = {store["location_id"] for store in scope["selected_stores"]}
for row in prev_rows:
    lid = _to_int(row.get("location_id"))
    if lid not in allowed_ids:
        continue
    prev_by_location[lid] = ...
```
This mirrors the `store_lookup` guard that `_build_store_rankings()` already uses for current rows.

---

## WARNING Findings

### W-1 — Division by zero: `net_delta_pct` when `prior_net = 0` is specified as `null`, but channel-reconciled net can be legitimately zero for new stores

**Location:** Task 1.5 — `net_delta_pct = (delta/prior_net)*100 if prior_net > 0 else null`

**Problem:**
The plan correctly guards `prior_net > 0 → null`. However, `net_sales_without_vat` in `_build_store_rankings()` is the **channel-reconciled** value (`clean_net`, line 2516–2517), which is the sum of 7 channel buckets. A store that had zero channel sales in the prior period (e.g., newly opened, or POS offline for entire prior window) produces `clean_net = 0.0` — this is not a missing-data case but a genuine zero-revenue store. The `null` result is correct for that case.

The additional risk is the **current period**: if `current_net = 0` as well (store offline both periods), `net_delta = 0` and `net_delta_pct = null`. The store will rank last in both periods with `position_change = 0`. This is correct behavior but the frontend must be told explicitly: `net_delta_pct: null` means "prior period was zero, no percentage meaningful", not "no data". The plan's `comparison_meta` should include an `is_new_store` flag or a `prior_net_zero: true` discriminator to let the frontend render this correctly.

**Fix required:** Add `"prior_period_zero": prior_net == 0.0` to each per-store comparison payload so the frontend can distinguish "no prior data" from "prior revenue was zero".

---

### W-2 — `include_comparisons` parameter: Frappe `@whitelist()` receives all params as strings; `_to_bool_flag` exists but plan does not call it

**Location:** Task 1.2 — `include_comparisons` param on `get_sales_dashboard_store_rankings()`

**Problem:**
The plan states the parameter type as `bool`, but Frappe's `@frappe.whitelist()` deserializes HTTP POST bodies as strings unless the client sends JSON with `Content-Type: application/json`. The existing codebase already handles this: `_to_bool_flag()` is defined at line 2403 and handles `"true"`, `"1"`, `"false"`, `"0"`, `""`, `None`. **The plan does not mention calling `_to_bool_flag()` on the parameter.** If the raw string `"false"` reaches a truthiness check via `if include_comparisons:`, it evaluates to `True` (non-empty string), triggering a full prior-period query even when the caller explicitly opted out.

**Fix required:**
```python
def get_sales_dashboard_store_rankings(
    ...
    include_comparisons: bool | str | None = None,
) -> dict[str, Any]:
    _include_comparisons = _to_bool_flag(include_comparisons, default=False)
```
Use `_include_comparisons` (the bool) throughout the function body, not the raw parameter.

---

### W-3 — Cache TTL asymmetry: prior-period data cached at same TTL (300 s) as current-period live data

**Location:** Task 1.3 — `_cache_get_or_set` with 300 s TTL

**Problem:**
`SALES_DASHBOARD_CACHE_TTL = 300` (line 55) is the global TTL used for all daily row caches. This is appropriate for the current period (data is live and changes as today's sales come in). Prior-period data (last week, last month) is **immutable** — it will never change. Caching it at 300 s means it will be re-fetched from Supabase every 5 minutes even though the answer is identical each time.

For a 45-store fleet querying a 7-day prior window, the prior period query is the same cost as the current period query (~600 ms based on the 73x speedup comment at line 237). Under normal dashboard usage (multiple users, multiple view refreshes per hour), this wastes 12+ Supabase SQL calls per hour for a result that could be cached for hours.

**Fix required:**
Define a separate constant for immutable historical data:
```python
SALES_DASHBOARD_HISTORY_CACHE_TTL = 3600  # 1 hour; prior-period data is immutable
```
Use `SALES_DASHBOARD_HISTORY_CACHE_TTL` when caching `_query_daily_rows(prev_start, prev_end, ...)` calls where `prev_end < date.today()`.

---

### W-4 — Single-day range edge case: `_shift_range` with `span_days = 1` shifts back exactly 1 day, producing "yesterday vs. today" — semantically correct but rank delta is meaningless

**Location:** Task 1.8 — `position_change = previous_rank - current_rank`

**Problem:**
When `start_date == end_date` (single-day range), `span_days = 1`, so `prev_start = prev_end = start_day - 1`. The prior period is a single day. Ranking 45 stores on one day's revenue produces extremely volatile rank positions — a store that happened to be closed the prior day ranks last regardless of performance trend. The `position_change` value will be large and misleading.

This is not a crash risk, but it is a data quality risk: the frontend will display rank deltas that are meaningless noise for single-day views.

**Fix required:**
In the response's `comparison_meta`, include:
```python
"rank_delta_reliable": span_days >= 7
```
This lets the frontend suppress or dim rank deltas when the window is too short to be meaningful. No logic change required in the backend computation.

---

### W-5 — Stores with no prior-period data receive no `previous_rank`, but the plan does not specify the rank assignment for these stores

**Location:** Task 1.7 — "Rank prior period stores by prior net, assign previous_rank"

**Problem:**
A store that opened after `prev_end` (e.g., a new store opened this week) will have zero rows in the prior period result. `prev_by_location` will have no entry for that `location_id`. When computing `position_change = previous_rank - current_rank`, `previous_rank` is undefined for that store.

Two problematic outcomes depending on implementation:
1. `previous_rank = None` — `None - int` raises `TypeError`.
2. `previous_rank = 0` — `0 - current_rank` is negative, implying the store "fell" in rank, which is wrong.

**Fix required:**
```python
position_change = (previous_rank - current_rank) if previous_rank is not None else None
is_new_store = previous_rank is None
```
Emit `"position_change": null, "is_new_store": true` in the per-store payload for these cases. The frontend can render a "NEW" badge instead of an arrow.

---

## INFO Findings

### I-1 — `_build_comparisons()` uses `gross_sales` for delta; plan correctly uses `net_sales_without_vat` for rank — no conflict, but inconsistency may confuse future maintainers

**Location:** Plan constraint: "Rank MUST use net_sales_without_vat"

**Note:** The existing `_build_comparisons()` (line 1786) computes delta on `gross_sales` only. The S185 per-store comparison is specified to use `net_sales_without_vat`. These are different fields on different code paths and do not conflict. However, the plan does not specify whether the per-store `net_delta` and `net_delta_pct` fields are delta on `net_sales_without_vat` (channel-reconciled, from `_build_store_rankings`) or on the raw MV `net_sales_without_vat`. Since `_build_store_rankings()` overrides `net_sales_without_vat` with `clean_net` (line 2517), the prior-period aggregation in `prev_by_location` should use the same channel-reconciled figure for consistency.

**Recommendation:** Explicitly document in the implementation that prior-period `net_sales_without_vat` for ranking is the `total_net_sales_without_vat` MV column (not the channel-split override, which is only computed for current-period rows via `_get_store_channel_split_map`). If the channel split is not run for the prior period, a comment should explain the intentional asymmetry.

---

### I-2 — `_build_store_rankings()` currently returns a list sorted by `gross_sales` descending (line 2565); plan requires sort by `net_sales_without_vat` descending

**Location:** Line 2565: `return sorted(by_location.values(), key=lambda row: row["gross_sales"], reverse=True)`

**Note:** The plan says rank MUST use `net_sales_without_vat`. The existing sort key is `gross_sales`. This means either:
(a) The plan intends to assign ranks from a secondary sort pass (not reusing the existing list order), or
(b) The existing sort will be changed to `net_sales_without_vat`.

If (b), this is a behavioral change to the existing S182 rankings (stores that previously ranked differently on gross vs. net would reorder). This is not in scope for S185 but the plan is silent on it.

**Recommendation:** Clarify whether S185 adds a second sorted pass for ranking purposes only (leaving the returned list order unchanged for backward compatibility), or whether the sort key at line 2565 is being changed.

---

### I-3 — `_supabase_query_sql` injection note in source comment is correct; prior-period SQL interpolation follows safe pattern if dates use `.isoformat()` and location_ids use `str(int)`

**Location:** Tasks 1.3/1.4 — `_query_daily_rows` internals (line 1390–1400)

**Note:** The existing `_query_daily_rows` uses PostgREST params (not raw SQL), so interpolation is via `f"gte.{start_day.isoformat()}"` — safe because `start_day` is a `date` object. The `location_filter` is `",".join(str(int(i)) for i in sorted(set(location_ids)))` via `_location_scope_key()` — safe because it casts to `int`. No new SQL injection surface is introduced by the plan as long as the prior-period call reuses the existing `_query_daily_rows` function rather than constructing a new raw SQL string.

**No action required unless a new `_supabase_query_sql` call is introduced for prior-period data.**

---

### I-4 — Empty result set: if `scope["selected_stores"]` is empty, `_query_daily_rows` already returns `[]` (line 1385 guard); prior-period aggregation must also short-circuit

**Location:** Task 1.4 — `prev_by_location` aggregation loop

**Note:** `_query_daily_rows` returns `[]` when `location_ids` is empty (line 1385). An empty list fed into the aggregation loop produces an empty `prev_by_location` dict. All stores then receive `previous_rank = None` and `net_delta = None`. This is correct behavior. The `comparison_meta` in the response should set `"comparisons_available": false` in this case so the frontend does not attempt to render rank deltas.

**No code change required** beyond confirming the `comparison_meta` flag is emitted.

---

## Checklist for Implementer

Before committing:

- [ ] C-1: `prev_by_location` built from `_query_daily_rows` result directly (no extra `_cache_get_or_set` wrapper around the aggregated dict, unless key includes both `prev_start` and `prev_end`)
- [ ] C-2: `prev_by_location` loop filters to `allowed_ids = {s["location_id"] for s in scope["selected_stores"]}` before populating
- [ ] W-1: Per-store comparison payload includes `"prior_period_zero": bool` discriminator
- [ ] W-2: `include_comparisons` parameter processed through `_to_bool_flag()` before any conditional check
- [ ] W-3: Prior-period `_query_daily_rows` call uses `SALES_DASHBOARD_HISTORY_CACHE_TTL` (≥ 3600 s), not `SALES_DASHBOARD_CACHE_TTL`
- [ ] W-4: `comparison_meta` includes `"rank_delta_reliable": span_days >= 7`
- [ ] W-5: `position_change = None` and `"is_new_store": true` for stores absent from prior period
- [ ] I-2: Clarify/document whether sort key at line 2565 changes, or a separate rank-pass is used
