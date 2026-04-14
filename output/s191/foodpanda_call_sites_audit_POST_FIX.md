# S191 Phase 3.10 — FoodPanda Call Sites Audit (POST-FIX)

Cross-reference of pre-fix Task 0.5 inventory to resolution after Phase 2-3.

| # | Line (pre-fix) | Site | Resolution |
|---|---|---|---|
| A | 82–92 | module-level column whitelist | unchanged — still needed to fetch MV columns including `foodpanda_subtotal` and `foodpanda_vat_deducted_sales` for `_aggregate_sales` and `_sales_row_metrics` |
| B | 760–774 | `_query_daily_rows` column selection | unchanged |
| C | 825–907 | `_get_mosaic_channel_split` | **unchanged**; `_apply_mosaic_channel_split` now overrides its `foodpanda` bucket (Task 2.1) |
| D | 910–1027 | `_apply_mosaic_channel_split` | **Phase 2.1 complete** — `fp_bucket = fp_unified`; `split.pop("foodpanda", None)` present; fp_bucket reflects unified gross/net/orders |
| E | 1049–1122 | `_get_store_channel_split_map` | **Phase 3.2 complete** — SQL + PostgREST paths unified via `else` branch; shared post-amble overrides `out[lid]["foodpanda"]` with unified net sum |
| F | 1453–1515 | `_aggregate_sales` | **unchanged by design** — still sums MV columns (used as "raw" aggregation); `_rebase_fp_to_unified` (Task 3.8) rewrites FP fields after aggregation for comparison baselines |
| G | 1760–1803 | `_build_comparisons` | **Phase 3.8 complete** — `_rebase_fp_to_unified` called on both `prev` and `last_year` baselines immediately after `_aggregate_sales` |
| H | 1962–2021 | `_get_mosaic_channel_split_per_day` | **Phase 3.5 complete** — SQL + PostgREST paths unified via `else` branch; shared post-amble overrides `per_day[day]["foodpanda"]` with unified net aggregated across stores; zero-fill for days with no unified data |
| I | 2024–2102 | `_aggregate_daily_series` | **Phase 3.6 complete** — removed `+ _to_float(row.get("foodpanda_vat_deducted_sales"))` from the `superadmin_delivery_wo_vat` sum. Now the per-day FP comes from the fixed H helper, avoiding double-count |
| J | 2484 | store_rankings builder call site | fixed transitively by E |
| K | 2644–2657 | `_sales_row_metrics` | **Phase 3.7 complete** — new optional `fp_unified_by_loc_day` parameter; caller `_build_weather_effects` precomputes `fp_unified_window` once and passes it into both history and current iterations |
| L | 2846, 2940 | `_apply_mosaic_channel_split` invocations | fixed transitively by D |
| M | 2963, 3261 | `_get_mosaic_channel_split_per_day` invocations (dashboard + CSV export) | fixed transitively by H — no inline FP SQL in `export_sales_dashboard_detail`, so the CSV export picks up unified FP automatically |
| N | 2359–2360 | summary read for Channel Mix donut | unchanged — read-only, receives unified via summary fields written by D |
| O | 1299 | deprecated `_FOODPANDA_MOSAIC_START` freshness warning text | **Phase 2.4 complete** — constant marked DEPRECATED; retained only for the freshness warning text |

## Task 3.9 — `export_sales_dashboard_detail` verification

- Reads `_get_mosaic_channel_split_per_day` and passes to `_aggregate_daily_series`.
- Both are Phase 3.5/3.6 fixed.
- **No inline FP SQL** in the endpoint body.
- Verdict: **Export automatically picks up unified FP after deploy. L3-191-13 covers this.**

## Grep posture (post-fix)

```
foodpanda_vat_deducted_sales                  : 5   (baseline 6, −1 by Task 3.6) ✓
fp_bucket = split.pop                         : 0   (baseline 1, 0 expected)     ✓
fp_bucket = fp_unified                        : 1                                ✓
_get_unified_foodpanda_totals                 : 13  (≥ 4 required)               ✓
_get_unified_foodpanda_totals_aggregate       : 3   (≥ 2 required)               ✓
_rebase_fp_to_unified                         : 3   (1 def + 2 calls)            ✓
legacy_partial_mosaic                         : 4                                ✓
fp_unified_v2                                 : 1   (cache prefix)               ✓
overview_s191                                 : 1   (outer cache bump)           ✓
summary_s191                                  : 1   (outer cache bump)           ✓
ilike.delivered                               : 3   (PostgREST fallback)         ✓
set_backend_observability_context             : 5   (unchanged)                  ✓
grabfood                                      : 28  (unchanged — anti-regress)   ✓
```
