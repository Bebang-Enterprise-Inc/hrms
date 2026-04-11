# S182 — MV column verification for `daily_store_metrics`

**Source of truth:** existing constants in `hrms/api/sales_dashboard.py` and active code sites that read these columns.

## Method

Rather than hitting live Supabase Mgmt API (which requires `SUPABASE_MGMT_TOKEN` that may not be available in local dev), verified by grep of existing code sites that already read per-store website columns from the `daily_store_metrics` MV.

## Verified column names

| Channel | MV column name | Evidence |
|---|---|---|
| Website non-COD (net w/o VAT) | `website_non_cod_net_sales_without_vat` | `sales_dashboard.py:93` (DAILY_METRIC_SELECT), `sales_dashboard.py:1310,1318,1881,2296` (active read sites) |
| Website COD (net w/o VAT) | `web_cod_net_sales_without_vat` | `sales_dashboard.py:89` (DAILY_METRIC_SELECT), `sales_dashboard.py:1313,1319,1882,2297` (active read sites) |

## Decision

Phase B.4 helper `_get_store_website_split_map` will query:

```sql
SELECT
  location_id,
  SUM(website_non_cod_net_sales_without_vat)::numeric(14,2) AS web_non_cod,
  SUM(web_cod_net_sales_without_vat)::numeric(14,2) AS web_cod
FROM public.daily_store_metrics
WHERE business_date >= '{start_day}'
  AND business_date <= '{end_day}'
  AND location_id IN ({loc_csv})
GROUP BY location_id
```

## Mosaic channels (from v_pos_orders_live)

Channel keys verified at `sales_dashboard.py:849` docstring: `pos`, `foodpanda`, `grabfood`, `webdelivery`. Anything else bucketed as `other_mosaic`.

Phase B.3 helper `_get_store_channel_split_map` will query `v_pos_orders_live` with
`GROUP BY location_id, LOWER(COALESCE(channel, 'unknown'))` using the S176 hotfix #12 f-string
pattern at `sales_dashboard.py:857-870`.
