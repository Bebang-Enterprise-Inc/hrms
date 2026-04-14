# S191 Phase 3 — Completion Report

| Task | Status | Evidence |
|---|---|---|
| 3.1 Read per-store return shape | ✅ | Mental model — float-per-channel, NOT nested dict |
| 3.2 Wire `_get_store_channel_split_map` | ✅ | Refactored `try/except/else` so both SQL + PostgREST paths share the unified FP override. `foodpanda` key reflects unified net. |
| 3.3 Only `foodpanda` overridden per store | ✅ | `git diff` confirms no touch to pos/grabfood/webdelivery/other_mosaic |
| 3.4 Read per-day return shape | ✅ | float-per-channel per day |
| 3.5 Wire `_get_mosaic_channel_split_per_day` | ✅ | Shared else-branch post-amble overrides `per_day[day]["foodpanda"]`; zero-fill for days without unified data; preserves float shape |
| 3.6 Remove `foodpanda_vat_deducted_sales` double-count | ✅ | `grep -c foodpanda_vat_deducted_sales` = 5 (was 6 baseline). Superadmin-delivery sum no longer includes legacy FP |
| 3.7 Fix `_sales_row_metrics` | ✅ | Optional `fp_unified_by_loc_day` param; `_build_weather_effects` precomputes `fp_unified_window` once and threads into both loops |
| 3.8 `_build_comparisons` + `_rebase_fp_to_unified` | ✅ | New helper added; both `prev` and `last_year` baselines rebased to unified FP before delta computation |
| 3.9 Verify `export_sales_dashboard_detail` | ✅ | No inline FP SQL; transitively fixed via 3.5 + 3.6 |
| 3.10 Caller inventory post-fix | ✅ | `output/s191/foodpanda_call_sites_audit_POST_FIX.md` — all 15 sites accounted for |
| 3.11 Python AST parse | ✅ | PARSE OK |

## Anti-regression guards
- `grabfood` count = **28** (unchanged from pre-S191 baseline) ✓
- `set_backend_observability_context` count = **5** (unchanged) ✓
- No changes to GrabFood, WebDelivery, POS, website channels — only `foodpanda` key/field rewritten ✓

## Key call-count summary
```
_get_unified_foodpanda_totals           : 13 (≥ 4 required)
_get_unified_foodpanda_totals_aggregate : 3  (≥ 2 required — def + 2 callers)
_rebase_fp_to_unified                   : 3  (1 def + 2 calls)
foodpanda_vat_deducted_sales            : 5  (baseline 6 − 1 = 5 ✓)
fp_bucket = split.pop                   : 0  ✓
fp_bucket = fp_unified                  : 1  ✓
overview_s191 / summary_s191            : 1 each
legacy_partial_mosaic (completeness)    : 4
ilike.delivered (PostgREST fallback)    : 3
```
