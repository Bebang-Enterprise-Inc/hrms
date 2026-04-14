# S191 Phase 0.5 — FoodPanda Call Sites Audit (pre-fix)

File: `hrms/api/sales_dashboard.py`

## Baseline counts (pre-S191)
- `foodpanda_vat_deducted_sales` references: **6** (`grep -c "foodpanda_vat_deducted_sales" hrms/api/sales_dashboard.py` = 6; lines 92, 1493, 1498, 2061, 2655 + docstring mention at ~928). Phase 3.6 removes the line 2061 occurrence → expected post-fix count = **5**.
- `set_backend_observability_context` calls: **5** (Sentry baseline)
- `grabfood` references: count pre-S191 captured for anti-regression check (verify_s191.py asserts exact match)

## Call sites enumerated

| # | Line | Function | Role | Phase-fix |
|---|---|---|---|---|
| A | 82–92 | module-level column whitelist | lists `foodpanda_orders`, `foodpanda_subtotal`, `foodpanda_vat_deducted_sales` fetched from MV | none — keep list for MV fetch |
| B | 760–774 | `_query_daily_rows` column selection | selects `foodpanda_orders` from MV | none — drives downstream reads |
| C | 825–907 | `_get_mosaic_channel_split` | Mosaic-only headline FP bucket | Phase 2.1: `_apply_mosaic_channel_split` overrides fp_bucket from unified helper |
| D | 910–1027 | `_apply_mosaic_channel_split` | consumer — line 948 `fp_bucket = split.pop("foodpanda"...)`, lines 960-965 write summary fields | Phase 2.1 — REPLACE with unified |
| E | 1049–1122 | `_get_store_channel_split_map` | per-store Mosaic channel mix (net_wo_vat floats) | Phase 3.2 — override `result[lid]["foodpanda"]` with unified net sum |
| F | 1453–1515 | `_aggregate_sales` | sums `foodpanda_subtotal` / `foodpanda_vat_deducted_sales` from MV | Phase 3.8 — `_rebase_fp_to_unified` rewrites these post-aggregation |
| G | 1760–1803 | `_build_comparisons` | baseline prev_period / last_year via `_aggregate_sales` | Phase 3.8 — call `_rebase_fp_to_unified` on each baseline |
| H | 1962–2021 | `_get_mosaic_channel_split_per_day` | Mosaic-only per-day channel mix (net_wo_vat floats) | Phase 3.5 — override foodpanda day float with unified per-day net |
| I | 2024–2102 | `_aggregate_daily_series` | line 2061 adds `foodpanda_vat_deducted_sales` → double-count once H is fixed | Phase 3.6 — REMOVE the `+ foodpanda_vat_deducted_sales` term |
| J | 2484 | store_rankings builder | calls `_get_store_channel_split_map` | fixed transitively by E |
| K | 2644–2657 | `_sales_row_metrics` | per-row MV-based delivery (uses `foodpanda_vat_deducted_sales`) | Phase 3.7 — thread unified-FP-by-(loc,date) map through caller |
| L | 2846, 2940 | `_apply_mosaic_channel_split` invocations | auto-picks up Phase 2.1 fix | fixed transitively by D |
| M | 2963, 3261 | `_get_mosaic_channel_split_per_day` invocations (dashboard + export) | auto-picks up Phase 3.5 fix | fixed transitively by H |
| N | 2359–2360 | summary read for Channel Mix donut | read-only | no change |
| O | 1299 | deprecated `_FOODPANDA_MOSAIC_START` freshness warning text | documentation only | Phase 2.4 — mark constant deprecated |

## HARD BLOCKER 0-3 verdict
All call sites above are covered by Phase 2 or Phase 3 tasks. No orphan sites. Cross-refs verified manually 2026-04-14.

## Grep baseline snapshot (captured 2026-04-14 on branch s191-foodpanda-unified-source pre-fix)
```
$ grep -c "foodpanda_vat_deducted_sales" hrms/api/sales_dashboard.py
6
$ grep -c "fp_bucket = split.pop" hrms/api/sales_dashboard.py
1
$ grep -c "_get_unified_foodpanda_totals" hrms/api/sales_dashboard.py
0
$ grep -c "set_backend_observability_context" hrms/api/sales_dashboard.py
5
```
