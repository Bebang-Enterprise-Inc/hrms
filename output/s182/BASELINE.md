# S182 Baseline

Recorded at Phase 0 — start of execution.

## Branches

| Repo | Branch | Base SHA | Base ref |
|---|---|---|---|
| BEI-ERP (hrms) | `s182-store-rankings-per-channel` | `37744036155f6b2a830d681113a02cc0de83055f` | `origin/production` |
| bei-tasks | `s182-sales-analytics-store-drilldown` | `5270f9baa6cd9e0eb1493a45edd42576ca487005` | `origin/main` |

## Keys
- `hrms_base_sha`: `37744036155f6b2a830d681113a02cc0de83055f`
- `bei_tasks_base_sha`: `5270f9baa6cd9e0eb1493a45edd42576ca487005`

## Source versions at baseline

- `hrms/api/sales_dashboard.py` — 2800+ lines, contains `_build_store_rankings` at line 2238 and `get_sales_dashboard_store_rankings` endpoint at line 2801
- `bei-tasks/lib/sales-dashboard.ts` — contains `SalesDashboardStoreRanking` at line ~246
- `bei-tasks/app/dashboard/analytics/sales/page.tsx` — 1542 lines

## Out-of-scope protected surfaces (do not touch)
- All other functions in `sales_dashboard.py`
- `.github/workflows/*`
- `app/dashboard/store-ops/store-dashboard/**/*`
- `app/dashboard/supervisor-tools/area-dashboard/**/*`
- `app/dashboard/hr/employee-master/**/*`
- `app/dashboard/hr/payroll/compensation-setup/**/*`
- `lib/roles.ts`, `lib/constants.ts`
