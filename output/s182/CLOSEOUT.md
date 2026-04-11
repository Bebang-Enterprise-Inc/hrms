# S182 — Build session closeout

**Status at end of this session:** READY_FOR_REVIEW (build complete; L3 + deploy + closeout pending in fresh session)

## PRs created (Sam: please review and merge)

| Repo | PR # | Branch | URL |
|---|---|---|---|
| hrms | **#540** | `s182-store-rankings-per-channel` | https://github.com/Bebang-Enterprise-Inc/hrms/pull/540 |
| bei-tasks | **#380** | `s182-sales-analytics-store-drilldown` | https://github.com/Bebang-Enterprise-Inc/BEI-Tasks/pull/380 |

## What this session delivered

### Backend (hrms PR #540)
- 2 new SQL helpers (`_get_store_channel_split_map` + `_get_store_website_split_map`) reusing the S176 hotfix #11/#12 Mgmt API + PostgREST fallback pattern
- `_build_store_rankings` signature change + per-row enrichment with channel_mix (7 buckets), reconciled net, pickup_share, daily_series
- DM-7 Sentry context on `get_sales_dashboard_store_rankings` with `module="sales"`
- Inline consistency check that logs reconcile drift via `frappe.log_error` without throwing
- `time` import + `[S182] ... channel_enrich_ms=N` log for B.10 measurement
- Python parses cleanly; rebased onto current `origin/production`

### Frontend (bei-tasks PR #380)
- Main page: 4-col top-8 grid + every store name clickable, sortable ranking table with 3 new columns + inline bar + a11y, breadcrumb, reset pill, useCallback handler
- New `StoreDetailDialog` (1200px × 90vh) using shared `fetchSalesOverview` helper — never client-side filters parent bundle (S176 hotfix #9 prevention)
- New `lib/api/sales-dashboard.ts` shared API wrapper (`fetchSalesOverview` + `fetchStoreRankings`) used by all 4 surfaces
- New `app/dashboard/analytics/sales/_formatters.ts` shared formatter module
- New `/dashboard/analytics/sales/stores` Leaderboard page with per-channel columns (POS / Web non-COD / Web COD / GrabFood / FoodPanda), 14d sparkline, density toggle as Button pair, sticky col, scroll cue, debounced search, CSV export, color-coded perf, mobile fallback
- New `/dashboard/analytics/sales/stores/[locationId]` dynamic route with `Number()` coercion and `get_sales_dashboard_access_context` resolution
- TS interface extension on `SalesDashboardStoreRanking` for the new optional fields
- Clean TypeScript build for all S182 surfaces (pre-existing `tests/e2e/*` errors unrelated)

### Verification
- `output/s182/verify_s182.py` → **VERIFY: PASS**
- All filesystem-level assertions for both repos green
- No protected-surface violations (`.github/workflows/` untouched)

## What is NOT done (scheduled for fresh session)

| Phase | Why deferred |
|---|---|
| 9 — L3 browser scenarios (21 tests) | S092 rule for >40u plans — fresh session has no motivated reasoning about whether the build passes |
| 9.7 — L3 evidence push to hrms branch | Depends on Phase 9 |
| Backend Deploy + post-deploy smoke test | Sam dispatches `build-and-deploy.yml` with `skip_build=false, no_cache=true` after reviewing PR #540 |
| Backend timing measurement (`backend_timing.md` keys) | Live measurement requires production endpoint to be hit post-deploy |
| Viewport proof PNGs (1366×768 + 390×844) | Captured during L3 session |
| Closeout: plan YAML → COMPLETED, registry update | After L3 PASS |

See `output/s182/l3_session_mode.md` for the full handoff prompt.

## Critical reminders for Sam before merging

1. **Backend rebuild is mandatory** — `skip_build=false, no_cache=true` on the workflow dispatch for the hrms PR. A `skip_build=true` deploy will silently ship a stale image and L3-182-13 + L3-182-13a will both fail with `channel_columns = ₱0` and `daily_series = undefined` and zero compile errors.
2. **Merge order:** hrms #540 first (so backend deploy succeeds), then bei-tasks #380 (Vercel auto-deploys; the new Leaderboard page calls the rankings endpoint that now includes channel_mix).
3. **Both PRs are rebased** onto current default branch (S161 silent-revert lesson).

## Files left on disk (this session)

```
output/s182/BASELINE.md
output/s182/CLOSEOUT.md (this file)
output/s182/backend_timing.md
output/s182/l3_session_mode.md
output/s182/mv_column_verification.md
output/s182/phase_B_completion.md
output/s182/verify_output.txt
output/s182/verify_s182.py
```
