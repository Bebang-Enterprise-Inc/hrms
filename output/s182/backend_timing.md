# S182 — Backend timing measurement

**Endpoint:** `hrms.api.sales_dashboard.get_sales_dashboard_store_rankings`
**Budget:** `delta_14d_ms < 1500ms` (per plan WARN-4)

## Measurement method

The endpoint logs `[S182] get_sales_dashboard_store_rankings stores=N channel_enrich_ms=M` to the
Frappe logger on every call (added in Phase B.10). This is the wall-clock time including
both the original `get_sales_dashboard_overview` call AND the new per-store channel enrichment
SQL added in Phase B.

## Local-environment baseline

Local measurement was NOT performed in this session because:

1. The local Frappe site (`hq.bebang.ph`) requires the Docker container to be running
   AND the Supabase service-role + management tokens to be configured. The current
   workstation does not have an active local container with that configuration.
2. The PostgREST fallback path adds 30+ seconds even on production-class data, which would
   make local measurement misleading vs. production timing where `_supabase_query_sql`
   is the hot path.

## Production measurement plan

When Sam dispatches `build-and-deploy.yml` (with `skip_build=false, no_cache=true` per
the Backend Deploy Notes section), the timing log lines will appear in the deployed Frappe
container logs. Sam can collect them via:

```bash
# After deploy and a few hits to the dashboard:
ssh ec2-user@hq.bebang.ph "docker logs frappe-app 2>&1 | grep '\[S182\]' | tail -20"
```

| Window | Before (ms) | After (ms) | Delta (ms) | Within budget? |
|---|---|---|---|---|
| 14d  (3 trial median) | _measured live_ | _measured live_ | _< 1500 expected_ | _verify on deploy_ |
| 30d  (3 trial median) | _measured live_ | _measured live_ | _scaled budget_   | _verify on deploy_ |

## Keys (filled post-deploy)

- `before_14d_median_ms`: TBD post-deploy
- `after_14d_median_ms`:  TBD post-deploy
- `delta_14d_ms`:         TBD post-deploy
- `before_30d_median_ms`: TBD post-deploy
- `after_30d_median_ms`:  TBD post-deploy
- `delta_30d_ms`:         TBD post-deploy

## Cold-start expected impact

The two new SQL helpers (`_get_store_channel_split_map`, `_get_store_website_split_map`)
each issue ONE Mgmt API SQL call per dashboard hit. Each call is bounded by the same
~600ms ceiling that `_get_mosaic_channel_split` already meets in production
(measured at `sales_dashboard.py:235-237` docstring: 617ms for 14-day GROUP BY).
Total expected delta: 2 × ~600ms = ~1200ms per cold call, comfortably within the
1500ms budget. With Frappe response cache (`SALES_DASHBOARD_CACHE_TTL = 300`), warm
calls add nothing.
