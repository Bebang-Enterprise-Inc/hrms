# S191 Phase 2.5 — Cache Prefix Bumps

Post-deploy, any cached payload from the pre-S191 logic would return stale Mosaic-only
FoodPanda numbers for up to 300s. Bumping the outer prefixes forces a cache miss on
first request after deploy so users see unified FP immediately.

## Bumped prefixes

| Location | Old prefix | New prefix | Reason |
|---|---|---|---|
| `_sales_dashboard_cache_key` at ~line 2807 (Sales Summary payload) | `summary` | `summary_s191` | wraps `_apply_mosaic_channel_split` output |
| `_sales_dashboard_cache_key` at ~line 2915 (`_build_dashboard_overview_payload`) | `overview` | `overview_s191` | wraps summary + per-day series + comparisons |

## NOT bumped (not FP-touching)

- `freshness_v2` (line 743) — unrelated freshness metadata, no FP data cached here
- `daily_rows` (line 1387) — raw MV row cache; unified FP is sourced from a different table, so even stale rows don't affect unified output
- `weather_rows` (line 1408)
- `discount_rows` (line 1429)
- `fleet_cache_key` (line 3448) — fleet metrics, no FP involvement
- `fp_unified_v2` (inside `_get_unified_foodpanda_totals`) — already fresh for this sprint

## Inner cache key already namespaced

`_get_unified_foodpanda_totals` uses `fp_unified_v2` (versioned in-name) — no bump needed.

## Precedent
S176 DD-21 used `freshness_v2` (line 743) for the same reason — post-deploy bump prevented
stale freshness payloads.
