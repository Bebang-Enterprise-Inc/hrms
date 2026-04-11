# S182 Phase B — Backend enrichment — COMPLETED

| Task | Status | Evidence |
|---|---|---|
| B.0 | DONE | `bei-tasks/lib/sales-dashboard.ts` extended with `SalesDashboardStoreChannelMix` interface + 3 optional fields on `SalesDashboardStoreRanking` |
| B.1 | DONE | Read `_build_store_rankings`, caller at line 2636, endpoint at line 2801 |
| B.2 | DONE | Read `_supabase_query_sql` (line 228), `_get_mosaic_channel_split` (line 824), PostgREST fallback pattern (line 873-897) |
| B.3 | DONE | `_get_store_channel_split_map` added — GROUP BY (location_id, channel_key) on `v_pos_orders_live` with f-string interpolation, PostgREST fallback, channel-key normalization via `_S182_CHANNEL_ALIASES` |
| B.4 | DONE | `_get_store_website_split_map` added — GROUP BY location_id on `daily_store_metrics` with `website_non_cod_net_sales_without_vat` + `web_cod_net_sales_without_vat`, PostgREST fallback |
| B.5 | DONE | `_build_store_rankings` signature now `(scope, sales_rows, weather_rows, start_day, end_day)`; call site at line 2636 updated to pass `start_day, effective_end` |
| B.6 | DONE | Inside `_build_store_rankings`: per-store `channel_mix` dict built from both maps; per-store `net_sales_without_vat` overridden from clean channel sum; `pickup_share` computed; `average_guest_check` recomputed from clean net |
| B.7 | DONE | Per-store `daily_series` built from existing `sales_rows` via `per_store_daily` map walked during the aggregation loop; padded with zeros across the full window so all sparklines have equal length |
| B.8 | DONE | `set_backend_observability_context(module="sales", action="get_sales_dashboard_store_rankings", mutation_type="read")` added to endpoint at line 2801 |
| B.9 | DONE | Inline consistency check `abs(sum(channel_mix.values()) - net_sales_without_vat) >= 1.0` triggers `frappe.log_error` with full context (location_id + warehouse_name + delta) |
| B.10 | PARTIAL | Timing log line added (`[S182] ... channel_enrich_ms=N` at INFO); `output/s182/backend_timing.md` written documenting measurement plan; live before/after numbers must be collected on deploy (local Docker not available) |

## Files modified

- `hrms/api/sales_dashboard.py` (1 file): added `time` import, two helper functions, modified `_build_store_rankings` signature + body, updated single call site, added Sentry context + timing log to endpoint
- `bei-tasks/lib/sales-dashboard.ts` (1 file): added `SalesDashboardStoreChannelMix` interface + 3 optional fields

## Files NOT modified (protected surfaces respected)

- All other functions in `sales_dashboard.py`
- Any file in `.github/workflows/`
- Any other file in `hrms/api/`

## Syntax check

```
python -c "import ast; ast.parse(open('hrms/api/sales_dashboard.py', encoding='utf-8').read())"
→ OK: sales_dashboard.py parses cleanly
```
