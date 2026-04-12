---
sprint_id: S183
sprint_name: Per-Store Product Analytics with Trend Detection + Keep/Drop Signal
branch: s183-product-analytics-per-store
repos:
  - bei-tasks (primary — frontend)
  - BEI-ERP (hrms — backend)
branches:
  bei-tasks: s183-product-analytics-per-store
  hrms: s183-product-mix-trend
depends_on: [S179]
status: DEPLOYED
planned_date: 2026-04-12
amended_date: 2026-04-12
amendment_version: v3
owner: sam@bebang.ph
signoff_authority: single-owner
estimated_units: 27
hard_unit_ceiling: 35
session_scope: single-agent-single-session
plan_file: docs/plans/2026-04-12-sprint-183-product-analytics-per-store.md
registry_row: |
  | `S183` | Sprint 183 | `s183-product-analytics-per-store` (bei-tasks) + `s183-product-mix-trend` (hrms) | — | DEPLOYED 2026-04-12 — Per-Store Product Analytics with trend detection + keep/drop signal. |
completed_date: null
execution_summary: null
backend_pr: "https://github.com/Bebang-Enterprise-Inc/hrms/pull/549"
frontend_pr: "https://github.com/Bebang-Enterprise-Inc/BEI-Tasks/pull/383"
---

# S183 — Per-Store Product Analytics with Trend Detection + Keep/Drop Signal

## Executive Summary

The Product Analytics page (`/dashboard/analytics/product`, shipped in S179) shows a global top-50 product table aggregated across ALL stores. Sam needs three capabilities it doesn't have:

1. **Per-store view** — "what does Ayala Market Market sell?" — filter the product table to a single store and see its unique product mix
2. **Trend detection** — "is Halo-Halo Standard trending up or down at this location?" — 14-day daily sparkline per product plus explicit week-over-week delta
3. **Keep/drop signal** — "which products are not worth keeping at this store?" — an automated three-tier recommendation with fleet rank, velocity, contribution %, and trend direction

**v2 enhancements (2026-04-12):** adds per-product drill-down row (click a product → see its velocity at every store that sells it), week-over-week delta column, fleet rank position, assortment gap analysis tile, and default signal sort (Drop Candidates first). Zero deferred requirements.

The data already exists at the right grain: `product_channel_daily_mix` MV has rows at `(business_date, location_id, channel, product_name)`. The existing endpoint `get_product_mix_analytics` already accepts a `stores` filter. The work is:
- **Backend:** enhance the endpoint to return `daily_series`, `velocity`, `contribution_pct`, `trend_slope`, `trend_label`, `fleet_rank`, `fleet_total_stores`, `wow_delta_pct`, and `assortment_gap` per product when scoped to a single store
- **Frontend:** add a store selector, render trend/signal columns, per-product drill-down expandable rows, and an assortment gap tile

**Total: 25 units, 5 phases.** Single-agent single-session.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

Sam (CEO) said on 2026-04-12: "I want to be able to see per store product tab and be able to see if certain products are trending in particular locations, I also need to be able to determine if certain products are not worth keeping."

The current page (S179) aggregates globally — it answers "what sells across the fleet?" but not "what sells HERE?" or "should we keep selling THIS here?" Those are store-manager and ops-team questions that require per-store granularity and trend signals.

### Why extend the existing page (not a new surface)

1. The page already has DateRangePicker, channel tabs, sort, and CSV export. Duplicating for a new route wastes code and confuses users.
2. Adding a store selector is a natural filter axis — the same pattern used on Sales Analytics.
3. When NO store is selected, the page shows the global view (S179 behavior preserved). When a store IS selected, it shows per-store view with trend columns. Clean progressive disclosure.

### Keep/drop signal logic (v2 — enhanced)

The signal classifies each product at a specific store into three tiers:

| Signal | Color | Criteria | Meaning |
|---|---|---|---|
| **Strong** | Green (`emerald`) | Fleet rank in top 50% for this product AND trend slope ≥ 0 | Product is selling well here and stable/growing |
| **Watch** | Amber | Fleet rank in bottom 50% OR trend slope < 0 (but not both bottom-quartile AND declining) | One warning sign — investigate before cutting |
| **Drop Candidate** | Red (`rose`) | Fleet rank in bottom quartile AND trend slope < 0 AND contribution < 1% | Low rank, declining, negligible contribution — candidate for removal |

v2 improves the signal by replacing "fleet median velocity" with **fleet rank position**. "You're #38 of 45 stores for this product" is far more actionable than "you're below median."

**Definitions:**
- **Velocity** = `total_quantity / window_days` (avg daily cups at THIS store)
- **Fleet rank** = this store's rank (1 = highest velocity) among all stores in the user's scope that sell this product. Requires a fleet-wide aggregation query (Phase 1.3).
- **Contribution %** = `product_net_sales / store_total_net_sales * 100`
- **Trend slope** = simple linear regression slope of daily quantity over the window (positive = growing, negative = declining). Computed in Python (no numpy).
- **WoW delta %** = `(this_week_qty - last_week_qty) / last_week_qty * 100`. Requires the window to span at least 8 days. `null` if insufficient data.

### Per-product drill-down (v2 addition)

When the user clicks a product name in per-store mode, the row expands to show a mini-table: **all stores that sell this product** with their velocity, rank, and trend. This lets Sam compare "Halo-Halo Standard at Ayala vs at SM North" and decide per-location.

The drill-down data comes from the SAME fleet-wide query used for fleet_rank (Phase 1.3) — no extra API call. The fleet data is already in the response payload.

### Assortment gap analysis (v2 addition)

When viewing a single store, a KPI tile shows: **"X products sold at other stores but not here."** Clicking it filters the table to show those missing products with their fleet-wide velocity, helping the ops team decide what to ADD (not just what to cut).

Data source: compare this store's product set against the fleet's product set from the same fleet-wide query.

### Known limitations

- **Short windows produce noisy trends.** A 3-day window can show a "declining" slope just from rain. The UI shows the sparkline so the operator can visually assess.
- **WoW delta requires ≥8 day window.** Shorter windows show "—" instead of a misleading percentage.
- **Fleet rank uses the user's allowed scope**, not all system stores. This is intentional (security) but means different users may see different ranks.
- **Contribution % uses net sales from the MV** which has the known FoodPanda double-count for Mar 26-31 (S176 hotfix #10). Relative metric — inflation cancels across products.
- **Assortment gap does NOT imply "should add"** — some products are location-specific (airport, BGC). The gap is informational.

### Source references (verified 2026-04-12)

- **Existing Product Analytics page:** `F:/Dropbox/Projects/bei-tasks/app/dashboard/analytics/product/page.tsx` (402 lines)
- **Existing backend endpoint:** `F:/Dropbox/Projects/BEI-ERP/hrms/api/sales_dashboard.py:3213-3359` (`get_product_mix_analytics`)
- **MV grain:** `(business_date, location_id, channel, product_name)` — columns: `total_quantity, total_gross_sales, total_net_sales, avg_unit_price, min_unit_price, max_unit_price, order_count`
- **MV resource name:** `product_channel_daily_mix` (PostgREST resource in Supabase)
- **Access context endpoint:** `/api/analytics/sales/access-context` → `hrms.api.sales_dashboard.get_sales_dashboard_access_context`
- **Store picker pattern:** `app/dashboard/analytics/sales/page.tsx:863-911` (Popover + Command)
- **Endpoint route registration:** `app/api/analytics/sales/[endpoint]/route.ts:21` — `"product-mix"` key already mapped
- **Shadcn available:** Badge, Popover, Command, CommandInput, CommandList, CommandItem, Skeleton, Alert, Table, Card, Button, DateRangePicker, Collapsible (verify — may need install)
- **Sentry context already present:** `sales_dashboard.py:3227-3230` — `set_backend_observability_context(module="sales", action="get_product_mix_analytics", mutation_type="read")`
- **BOM API exists at:** `hrms/api/commissary_bom.py` (429 lines) — NOT in scope for S183 but confirmed available for future integration

---

## Agent Boot Sequence

1. **Read this plan fully.**
2. **Create frontend branch:**
   ```bash
   cd F:/Dropbox/Projects/bei-tasks
   git fetch origin main && git checkout -b s183-product-analytics-per-store origin/main
   ```
3. **Create backend branch:**
   ```bash
   cd F:/Dropbox/Projects/BEI-ERP
   git fetch origin production && git checkout -b s183-product-mix-trend origin/production
   ```
4. **Read the existing Product Analytics page** (`app/dashboard/analytics/product/page.tsx`, 402 lines).
5. **Read the existing backend endpoint** (`hrms/api/sales_dashboard.py:3213-3359`).
6. **Read the Sales Analytics store picker** (`app/dashboard/analytics/sales/page.tsx:863-911`) for the Popover+Command pattern.
7. **Verify `Collapsible` shadcn component** — `ls F:/Dropbox/Projects/bei-tasks/components/ui/ | grep collapsible`. If missing, use a simple `useState` toggle instead (do NOT install new shadcn components).
8. **Do not modify any file outside the Surface Ownership Matrix.**

---

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

---

## Requirements Regression Checklist

- [ ] When NO store is selected, does the page show the SAME global view as S179? (backward compatible — HARD BLOCKER)
- [ ] When a store IS selected, does the API pass `stores=["<warehouse_code>"]` to `get_product_mix_analytics`?
- [ ] Does the table show Velocity, Contribution %, WoW Delta, Trend sparkline, Fleet Rank, and Signal badge ONLY when a store is selected?
- [ ] Is the fleet rank computed from the user's ALLOWED scope only? (HARD BLOCKER — security)
- [ ] Does the Signal badge use the correct three-tier logic: Strong (green) / Watch (amber) / Drop Candidate (red)?
- [ ] Does the keep/drop signal use fleet RANK (not just median) as the primary signal?
- [ ] Does clicking a product name expand to show per-store velocity comparison?
- [ ] Does the drill-down show fleet rank + velocity + trend for every store that sells the product?
- [ ] Does the "Assortment Gap" tile show how many products are sold elsewhere but not at this store?
- [ ] Does clicking the assortment gap tile filter the table to show those missing products?
- [ ] Does `trend_slope` handle single-day windows gracefully (slope = 0, not NaN)?
- [ ] Does WoW delta show "—" when the window is < 8 days?
- [ ] Is `daily_series` padded with zeros for days with no sales (sparkline length = window_days)?
- [ ] Does the CSV export include velocity, contribution %, WoW delta, fleet rank, and signal columns?
- [ ] Does the page preserve channel tab + date range + sort state when switching stores?
- [ ] Does every new/modified @frappe.whitelist() endpoint call set_backend_observability_context()? (Already present — verify only)
- [ ] Default sort in per-store mode: Drop Candidates first, then Watch, then Strong?

---

## Surface Ownership Matrix

| Owner | Owned file globs |
|---|---|
| S183 frontend | `app/dashboard/analytics/product/page.tsx` (extend) |
| S183 backend | `hrms/api/sales_dashboard.py` — ONLY `get_product_mix_analytics` function (lines 3213-3359). Do NOT touch other functions. |

**Protected surfaces (do not touch):**
- `hrms/api/sales_dashboard.py` — all other functions
- `.github/workflows/*`
- `app/dashboard/analytics/sales/**/*` (S182)
- `lib/roles.ts`, `lib/constants.ts`

---

## Phase Budget Contract

| Phase | Name | Est. Units | Hard Cap |
|---|---|---|---|
| Phase 0 | Branch setup + baseline | 1 | 2 |
| Phase 1 | Backend: daily_series + fleet rank + WoW + trend + signal + assortment gap | 8 | 10 |
| Phase 2 | Frontend: store picker + per-store table + sparkline + signal badges + fleet rank | 8 | 12 |
| Phase 3 | Frontend: per-product drill-down + assortment gap tile + default signal sort | 5 | 8 |
| Phase 4 | CSV export with all columns + verification + PRs + closeout | 3 | 5 |
| **Total** | | **25** | **37** |

---

## Phase Table

### Phase 0 — Branch setup + baseline (1 unit)

| # | Task | MUST_MODIFY / Evidence |
|---|---|---|
| 0.1 | Create both branches (see boot sequence) | `git branch --show-current` correct in each repo |
| 0.2 | Record base SHAs in `output/s183/BASELINE.md` | File exists |

### Phase 1 — Backend: daily_series + fleet data + trend metrics (8 units)

**Goal:** Enhance `get_product_mix_analytics` so the response includes per-product trend and signal fields when scoped to a single store. Add a fleet-wide comparison query for rank and assortment gap.

| # | Task | MUST_MODIFY / Evidence |
|---|---|---|
| 1.1 | Read `get_product_mix_analytics` (lines 3213-3359). Understand aggregation loop. | Mental model |
| 1.2 | **Add daily_series per product.** During the aggregation loop, also collect `per_product_daily[pname][date_str] += quantity`. After aggregation, for each product build `daily_series = [qty_for_day_1, ...]` sorted by date, padded with zeros. Compute `window_days = (end_day - start_day).days + 1`. | `grep -c "daily_series" hrms/api/sales_dashboard.py` ≥ 2 |
| 1.3 | **Fleet-wide comparison query.** When `len(selected_location_ids) == 1` (single-store mode), derive the fleet scope and run a fleet query. **Step A — explicit variable assignment (audit fix B-2):** add this exact code BEFORE the fleet query: `# S183: fleet scope = ALL allowed stores (for rank + assortment gap). selected_location_ids is already scoped to the ONE selected store. These are DIFFERENT sets — do NOT use selected_location_ids for fleet.` then `allowed_location_ids = [s["location_id"] for s in scope["stores"]]`. `scope["stores"]` = all RBAC-allowed stores (set by `_resolve_allowed_store_scope` at line 586). `scope["selected_stores"]` = the filtered single store (set by `_selected_scope` at line 615). **Step B — fleet query via Mgmt API SQL (audit fix B-1):** use `_supabase_query_sql` (NOT `_supabase_get_all`) to avoid 45-158 sequential PostgREST round-trips. SQL: `f"SELECT location_id, product_name, SUM(total_quantity)::int AS qty FROM public.product_channel_daily_mix WHERE business_date >= '{start_day.isoformat()}' AND business_date <= '{end_day.isoformat()}' AND location_id IN ({loc_csv}) GROUP BY location_id, product_name"` where `loc_csv = ",".join(str(int(i)) for i in sorted(set(allowed_location_ids)))`. Wrap in `_cache_get_or_set` with 60s TTL and cache key `_sales_dashboard_cache_key("fleet_product_mix", allowed_location_ids, start_day=start_day, end_day=end_day)`. On `SupabaseMgmtTokenMissing`, fall back to `_supabase_get_all("product_channel_daily_mix", fleet_params, page_size=5000)`. **Step C — aggregate:** build `fleet_product_map: dict[str, dict[int, int]]` = `{ product_name: { location_id: total_quantity } }`. Also build `fleet_store_lookup: dict[int, str]` mapping `location_id → warehouse_name` from `scope["stores"]` for the drill-down display names. **HARD BLOCKER 1-2:** Must use `allowed_location_ids` from `scope["stores"]`, NOT `selected_location_ids`. If you find yourself writing `selected_location_ids` in the fleet query, STOP — that produces fleet_rank = "1 of 1" for every product. | `grep -c "fleet_product_map" hrms/api/sales_dashboard.py` ≥ 2; `grep -c "allowed_location_ids" hrms/api/sales_dashboard.py` ≥ 2; `grep -c "_supabase_query_sql" hrms/api/sales_dashboard.py` in fleet query section ≥ 1 |
| 1.4 | **Compute fleet_rank per product.** From `fleet_product_map`, for each product, rank all stores by quantity descending. This store's rank = its position in that list. `fleet_total_stores` = number of stores that sell this product. | `grep -c "fleet_rank" hrms/api/sales_dashboard.py` ≥ 2 |
| 1.5 | **Compute WoW delta.** Split `daily_series` into two halves: `last_week` (first half) and `this_week` (second half). `wow_delta_pct = ((this_week_sum - last_week_sum) / last_week_sum) * 100` if `last_week_sum > 0` and window ≥ 8 days. `null` otherwise. | `grep -c "wow_delta" hrms/api/sales_dashboard.py` ≥ 2 |
| 1.6 | **Compute trend_slope via simple linear regression (audit fix B-3).** For each product with `daily_series`, compute slope. **Explicit implementation:** `x_vals = list(range(len(daily_series)))`, `x_mean = sum(x_vals) / len(x_vals)`, `y_mean = sum(daily_series) / len(daily_series)`, `numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, daily_series))`, `denominator = sum((x - x_mean) ** 2 for x in x_vals)`, `slope = round(numerator / denominator, 4) if denominator > 0 else 0.0`. **The `if denominator > 0 else 0.0` guard is MANDATORY** — without it, stores with only 1 day of data in the window produce `ZeroDivisionError` that crashes the entire endpoint. Also guard `len(daily_series) == 0` → `slope = 0.0`. | `grep -c "trend_slope" hrms/api/sales_dashboard.py` ≥ 2; `grep -c "denominator > 0" hrms/api/sales_dashboard.py` ≥ 1 |
| 1.7 | **Compute velocity, contribution_pct, trend_label.** `velocity = total_quantity / window_days`. `contribution_pct = total_net_sales / store_total_net * 100`. `trend_label` per the three-tier logic using fleet_rank (not median). | `grep -c "contribution_pct" hrms/api/sales_dashboard.py` ≥ 1; `grep -c "trend_label" hrms/api/sales_dashboard.py` ≥ 1; `grep -c "drop_candidate" hrms/api/sales_dashboard.py` ≥ 1 |
| 1.8 | **Compute assortment_gap.** Products in `fleet_product_map` that are NOT in this store's product set. Return as `meta.assortment_gap_count: int` and `meta.assortment_gap_products: list[{product_name, fleet_velocity, fleet_stores_count}]`. | `grep -c "assortment_gap" hrms/api/sales_dashboard.py` ≥ 2 |
| 1.9 | **Add fleet drill-down data to response.** Each product dict gains `per_store_breakdown: list[{location_id, warehouse_name, velocity, rank, trend_slope}]` — sourced from `fleet_product_map`. Only populated in single-store mode. Capped at top 20 stores per product to limit payload. | `grep -c "per_store_breakdown" hrms/api/sales_dashboard.py` ≥ 2 |
| 1.10 | **Add meta fields + fix store_coverage (audit fix B-9).** `meta.is_single_store: bool`, `meta.store_name: str|null`, `meta.store_total_net: float|null`. **Also fix existing `store_coverage` field:** the current code at line 3310 does `total_stores = len(selected_location_ids) if selected_location_ids else 44` — in single-store mode this produces `"1/1"` for every product (meaningless). Fix: when `is_single_store`, override `total_stores = len(allowed_location_ids)` so `store_coverage` shows e.g., `"1/45"` (product sold at 1 of 45 stores in scope). | `grep -c "is_single_store" hrms/api/sales_dashboard.py` ≥ 1; `grep -c "allowed_location_ids" hrms/api/sales_dashboard.py` in store_coverage section ≥ 1 |
| 1.11 | **Python parse check.** `python -c "import ast; ast.parse(...)"` → OK. | Parse clean |

**HARD BLOCKER 1-1:** Do NOT modify any other function in `sales_dashboard.py`. Scope is `get_product_mix_analytics` ONLY.

**HARD BLOCKER 1-2:** Fleet comparison query MUST use the user's full `scope["stores"]` (all allowed stores), NOT `selected_location_ids` (the filtered single store). Using the filtered scope would make fleet_rank always "1 of 1" — useless. But this also means fleet data is scoped to the user's RBAC — they cannot infer competitor data.

### Phase 2 — Frontend: store picker + per-store table + sparkline + signal badges (8 units)

**Goal:** Add a store selector to the Product Analytics page. When a store is selected, show the per-store product table with Velocity, Fleet Rank, WoW Delta, Contribution %, Trend sparkline, and Signal badge columns.

**Component split guidance (audit fix B-6):** The existing `page.tsx` is 422 lines. After Phase 2 + 3, it will grow to ~720 lines. If the file exceeds 600 lines after Phase 2, extract the per-store table + columns + drill-down into `app/dashboard/analytics/product/_per-store-products.tsx` as a `PerStoreProductTable` component. The main `page.tsx` keeps the global view, store picker, KPI tiles, and state management. The per-store component receives data via props.

| # | Task | MUST_MODIFY / Evidence |
|---|---|---|
| 2.1 | **Fetch access context on mount.** Call `/api/analytics/sales/access-context` to get `allowed_stores`. Add state: `accessStores: SalesDashboardStoreScope[]`. | `grep -c "access-context" app/dashboard/analytics/product/page.tsx` ≥ 1 |
| 2.2 | **Add store selector (audit fix B-5).** Popover + Command pattern from Sales Analytics. State: `selectedStore: SalesDashboardStoreScope | null` (the full scope object, NOT just a string). Place next to the DateRangePicker. When selected, pass `stores=[selectedStore.warehouse]` to the API params — **use `.warehouse` (the string code), NOT `.location_id`** (the backend `_parse_stores_param` expects warehouse codes as strings). When cleared, revert to global view. Add "Viewing: [Store Name] · Clear" reset badge. Import `SalesDashboardStoreScope` from `@/lib/sales-dashboard`. | `grep -c "selectedStore" app/dashboard/analytics/product/page.tsx` ≥ 2; `grep -c "Clear" app/dashboard/analytics/product/page.tsx` ≥ 1; `grep -c "selectedStore.warehouse" app/dashboard/analytics/product/page.tsx` ≥ 1 |
| 2.3 | **Extend ProductRow interface** with optional fields: `daily_series?: number[]`, `velocity?: number`, `contribution_pct?: number`, `trend_slope?: number`, `trend_label?: string | null`, `fleet_rank?: number`, `fleet_total_stores?: number`, `wow_delta_pct?: number | null`, `per_store_breakdown?: Array<{location_id: number, warehouse_name: string, velocity: number, rank: number, trend_slope: number}>`. Extend `ProductMixMeta` with `is_single_store?: boolean`, `store_name?: string | null`, `assortment_gap_count?: number`, `assortment_gap_products?: Array<{product_name: string, fleet_velocity: number, fleet_stores_count: number}>`. | `grep -c "daily_series" page.tsx` ≥ 1; `grep -c "fleet_rank" page.tsx` ≥ 1; `grep -c "wow_delta" page.tsx` ≥ 1 |
| 2.4 | **Add Sparkline component.** Inline SVG polyline at 80×20px (same pattern as S182). Renders `product.daily_series`. Only shown when `meta.is_single_store`. | `grep -c "polyline" page.tsx` ≥ 1 |
| 2.5 | **Add Signal badge column.** Render `trend_label` as color-coded Badge: `strong` → `bg-emerald-500`, `watch` → `bg-amber-500`, `drop_candidate` → `bg-rose-500`. Only when `meta.is_single_store`. | `grep -c "drop_candidate\|Drop Candidate" page.tsx` ≥ 1; `grep -c "bg-emerald" page.tsx` ≥ 1; `grep -c "bg-rose" page.tsx` ≥ 1 |
| 2.6 | **Add Velocity, Fleet Rank, WoW Delta, Contribution % columns.** Only shown when `meta.is_single_store`. Velocity: `X.X cups/day`. Fleet Rank: `#N of M`. WoW: `+X.X%` or `-X.X%` (green/red) or `—`. Contribution: `X.X%`. | `grep -c "cups/day" page.tsx` ≥ 1; `grep -c "fleet_rank\|Fleet Rank" page.tsx` ≥ 1; `grep -c "contribution" page.tsx` ≥ 1 |
| 2.7 | **Default sort in per-store mode (audit fix B-4).** Add state: `sortMode: "signal" | "column"` (default `"column"`). When `meta.is_single_store` AND `sortMode` has not been overridden by the user, set `sortMode = "signal"`. **Signal sort order:** tier priority (drop_candidate=0, watch=1, strong=2) ascending, then velocity ascending within tier — Drop Candidates at top. **State machine:** (a) When store is first selected, set `sortMode = "signal"`. (b) When user clicks ANY column header, switch `sortMode = "column"` and apply normal sort by that column. (c) When store changes (different store selected), reset `sortMode = "signal"`. (d) When store is cleared (back to global), reset `sortMode = "column"` and restore normal sort by `total_quantity` descending. The existing `SortKey` type is NOT extended — signal sort is a parallel mode that bypasses `sortBy`/`sortAsc`. | `grep -c "sortMode" app/dashboard/analytics/product/page.tsx` ≥ 2; `grep -c "drop_candidate\|signal" page.tsx` ≥ 1 |
| 2.8 | **Update KPI tiles for single-store mode.** Replace "Store Coverage" tile with "Signal Summary" tile: `X Strong · Y Watch · Z Drop`. Add "Assortment Gap" tile: `X products not sold here`. | `grep -c "Signal Summary\|signal-summary" page.tsx` ≥ 1; `grep -c "Assortment Gap\|assortment.gap\|not sold here" page.tsx` ≥ 1 |

### Phase 3 — Frontend: per-product drill-down + assortment gap table (5 units)

**Goal:** Clicking a product name in per-store mode expands an inline row showing how that product performs at every store in the user's scope. Clicking the Assortment Gap tile shows products sold elsewhere but not here.

| # | Task | MUST_MODIFY / Evidence |
|---|---|---|
| 3.1 | **Expandable product row.** When `meta.is_single_store`, clicking a product name toggles a sub-row showing `per_store_breakdown` as a mini-table: Store Name, Velocity (cups/day), Rank, Trend Slope (+/-). Sorted by velocity descending. Highlight the current store's row. Use simple `useState<string | null>(expandedProduct)` toggle — clicking the same product collapses it. | `grep -c "expandedProduct\|per_store_breakdown" page.tsx` ≥ 2 |
| 3.2 | **Assortment gap view.** When the "Assortment Gap" tile is clicked, toggle state `showGapProducts: boolean`. When true, the table shows `meta.assortment_gap_products` instead of the regular products: Product Name, Fleet Velocity, Fleet Stores Count. Badge: "Not sold here." A "Back to store products" button toggles back. | `grep -c "showGapProducts\|assortment_gap_products\|Not sold here" page.tsx` ≥ 2 |
| 3.3 | **Visual polish.** Expand/collapse animation via CSS `transition-all`. Highlight current store row in drill-down with `bg-primary/5 font-semibold`. Fleet rank badge: `#1-10 → emerald, #11-30 → slate, #31+ → rose`. | `grep -c "transition-all" page.tsx` ≥ 1 |

### Phase 4 — CSV export + verification + PRs + closeout (3 units)

| # | Task | MUST_MODIFY / Evidence |
|---|---|---|
| 4.1 | **Extend CSV export.** In single-store mode, add columns: Velocity, Contribution %, WoW Delta %, Fleet Rank, Fleet Stores, Trend Slope, Signal, Daily Series (pipe-separated). | `grep -c "velocity\|contribution\|fleet_rank" page.tsx` in downloadCsv |
| 4.2 | **Verification script.** Create `output/s183/verify_s183.py` with filesystem assertions for both repos. Run → PASS. | File exists, exits 0 |
| 4.3 | **Push both branches, create 2 PRs.** hrms → production. bei-tasks → main. `GH_TOKEN=""` prefix. | Both PR numbers recorded |
| 4.4 | **Update plan YAML** to `status: DEPLOYED` + update `SPRINT_REGISTRY.md` with PR numbers. `git add -f docs/plans/`. | Plan + registry updated |

---

## Zero-Skip Enforcement

Every task in the phase table MUST be implemented. The agent is FORBIDDEN from:
- Skipping a task silently
- Marking partial work as "done"
- Replacing a task with a simpler version without user approval
- Saying "deferred to next sprint"
- Implementing happy path only, skipping edge cases
- Combining tasks and dropping features

**Phase Completion Checklist:** After each phase, write `output/s183/phase_N_completion.md` with task-by-task status. If any task is skipped/partial, STOP and notify user. **This STOP overrides `continue_without_pause_through` — a phase with ANY skipped/partial task is NOT complete (audit fix B-8).**

**PR Description Gate (audit fix B-7):** Both PRs MUST include in the description: (a) `verify_s183.py` output (paste the PASS line), (b) phase completion status for all 5 phases, (c) L3 evidence file paths (if applicable). PRs with missing gate items will be rejected.

### Verification Script (MANDATORY)

Create `output/s183/verify_s183.py`. Runs after every phase AND at closeout. PR cannot be created until PASS.

The script checks:
- Phase 1 backend patterns in `hrms/api/sales_dashboard.py`: `daily_series`, `fleet_rank`, `fleet_product_map`, `allowed_location_ids` (B-2), `trend_slope`, `trend_label`, `contribution_pct`, `wow_delta`, `assortment_gap`, `per_store_breakdown`, `is_single_store`, `drop_candidate`, `denominator > 0` (B-3), `_supabase_query_sql` in fleet query (B-1), `_cache_get_or_set` for fleet (B-1)
- Phase 2-3 frontend patterns in `app/dashboard/analytics/product/page.tsx` (or `_per-store-products.tsx` if split): `selectedStore`, `selectedStore.warehouse` (B-5), `sortMode` (B-4), `polyline`, `bg-emerald`, `bg-rose`, `cups/day`, `fleet_rank`, `wow_delta`, `contribution`, `Signal Summary`, `assortment`, `expandedProduct`, `per_store_breakdown`, `Not sold here`, `showGapProducts`
- Protected surface check: no workflow files modified
- MUST NOT contain: `ToggleGroup` (not installed), `useMediaQuery` (doesn't exist)

---

## L3 Workflow Scenarios

| ID | User | Action | Expected Outcome | Failure Means |
|---|---|---|---|---|
| L3-183-01 | sam@bebang.ph | Load `/dashboard/analytics/product` with no store selected | Global top-50 products, no Velocity/Trend/Signal columns visible | Backward compat broken |
| L3-183-02 | sam@bebang.ph | Select "Ayala Market Market" from store picker | Table re-fetches with per-store products. Velocity, Contribution %, WoW Delta, Fleet Rank, Sparkline, Signal columns all visible. | Per-store mode broken |
| L3-183-03 | sam@bebang.ph | Verify ≥1 product has "Strong" badge (green) | Green badge on a top-ranked, stable/growing product | Signal logic broken |
| L3-183-04 | sam@bebang.ph | Verify ≥1 product has "Drop Candidate" badge (red) | Red badge on a bottom-quartile, declining, low-contribution product | Signal logic broken |
| L3-183-05 | sam@bebang.ph | Verify default sort shows Drop Candidates first | Red badges at top of table | Default sort broken |
| L3-183-06 | sam@bebang.ph | Click product name → drill-down expands | Sub-row shows mini-table with all stores' velocity/rank/trend for that product. Current store highlighted. | Drill-down broken |
| L3-183-07 | sam@bebang.ph | Click "Assortment Gap" tile | Table switches to show products not sold at this store, with fleet velocity/stores count | Gap analysis broken |
| L3-183-08 | sam@bebang.ph | Click "Back to store products" after viewing gap | Original per-store product table restores | Toggle broken |
| L3-183-09 | sam@bebang.ph | Click "Clear" to reset store selection | Reverts to global view, trend/signal columns disappear | Reset broken |
| L3-183-10 | sam@bebang.ph | Switch channel tab "FoodPanda" while store selected | Table updates with channel-filtered products, signals recalculated | Channel filter broken |
| L3-183-11 | sam@bebang.ph | Click CSV Export while store selected | CSV includes Velocity, Contribution %, WoW, Fleet Rank, Signal columns | Export broken |
| L3-183-12 | sam@bebang.ph | Change date range to 7-day window while store selected | Table + sparklines + signals update. WoW delta shows "—" (window too short). | Date range broken |

---

## Autonomous Execution Contract

- **completion_condition:**
  - All 5 phases marked DONE in `output/s183/phase_N_completion.md`
  - `output/s183/verify_s183.py` exits 0
  - 2 PRs created (hrms + bei-tasks)
  - Plan YAML updated to DEPLOYED, SPRINT_REGISTRY.md updated with PR numbers
- **stop_only_for:**
  - Missing credentials/access
  - Direct conflict on `hrms/api/sales_dashboard.py` with a newer sprint
  - Repeated (3x) technical failure with no progress after grounded research
- **continue_without_pause_through:** `execute → pr_creation → closeout` (applies to COMPLETED phases only — a phase with ANY skipped/partial task triggers the Zero-Skip STOP override per audit fix B-8)
- **blocker_policy:**
  - programmatic → fix and continue
  - repeated failure x3 → grounded research, continue
  - business-data/policy → pause
  - governor REJECT → read PR comments, push fix to same branch
  - verify_s183.py FAIL → fix and re-run immediately
- **signoff_authority:** single-owner (sam@bebang.ph)
- **canonical_closeout_artifacts:**
  - `output/s183/BASELINE.md`
  - `output/s183/phase_0..4_completion.md`
  - `output/s183/verify_s183.py` + `verify_output.txt`
  - `docs/plans/2026-04-12-sprint-183-product-analytics-per-store.md`
  - `docs/plans/SPRINT_REGISTRY.md`

---

## Backend Deploy Notes

Phase 1 modifies `get_product_mix_analytics` (Python source change). Dispatch `build-and-deploy.yml` with **`skip_build=false, no_cache=true`** (MEMORY lesson #2).

---

## Execution Workflow

- Test Python changes: `/local-frappe`
- Deploy changes: `/deploy-frappe` (Sam handles merge + deploy trigger)
- Full workflow: `/agent-kickoff`
- E2E testing: `/e2e-test` or `/test-full-cycle`

---

## Anti-Rewind Protection

- **remote_truth_baseline:** `output/s183/BASELINE.md` with both SHAs
- **protected_surfaces:** see Surface Ownership Matrix
- **rebase rule:** before pushing, `git fetch origin` and rebase. Re-run `verify_s183.py`. Grep for conflict markers.

---

## Signoff Model

- **mode:** single-owner
- **approver_of_record:** sam@bebang.ph
- **signoff_artifact:** PR review comments on both PRs

---

## Amendment History

| Date | Version | Author | Change |
|---|---|---|---|
| 2026-04-12 | v1 | sam@bebang.ph + Claude | Initial plan. 18 units, 4 phases. |
| 2026-04-12 | v2 | sam@bebang.ph + Claude | Sam directive: "make the feature better without deferring any of my requirements." Added: per-product drill-down (click product → see velocity at every store), week-over-week delta column, fleet rank position (replaces median-based signal — "you're #38 of 45" is more actionable), assortment gap tile + view ("X products sold elsewhere but not here"), default signal sort (Drop Candidates first). Replaced median-based keep/drop logic with rank-based. Added Phase 3 (drill-down + gap). Total: 25 units, 5 phases. Zero features deferred — every Sam requirement is in-scope. |
| 2026-04-12 | v3 | sam@bebang.ph + Claude | `/audit-plan-bei-erp` run against v2. 3 domain agents + 1 code verifier surfaced 3 CRITICAL + 6 WARNING across backend, frontend, and deployment domains. v3 resolves ALL 9 in-place — **zero features removed, zero scope reductions**. Fixes: (B-1) fleet query switched from `_supabase_get_all` PostgREST pagination to `_supabase_query_sql` Mgmt API SQL GROUP BY for single round-trip + `_cache_get_or_set` 60s TTL. (B-2) Explicit `allowed_location_ids = [s["location_id"] for s in scope["stores"]]` code snippet with inline comment in Phase 1.3 — prevents cold-start agent from using `selected_location_ids` for fleet (producing useless "1 of 1" rank). (B-3) Explicit `if denominator > 0 else 0.0` zero-guard for linear regression slope — prevents `ZeroDivisionError` on single-day stores. (B-4) Sort state machine defined: `sortMode: "signal" | "column"` with transition rules (store select → signal, column click → column, store change → reset signal, clear → column). (B-5) Store picker explicitly passes `selectedStore.warehouse` (string code), stores full `SalesDashboardStoreScope` object. (B-6) Component split guidance: extract `_per-store-products.tsx` if page exceeds 600 lines after Phase 2. (B-7) PR description gate added to Zero-Skip section. (B-8) `continue_without_pause_through` disambiguated — Zero-Skip STOP overrides continue clause for incomplete phases. (B-9) `store_coverage` total_stores overridden from `allowed_location_ids` length in single-store mode (was hardcoded to `len(selected_location_ids)` = 1). Total: 27 units (+2 from audit fixes), 5 phases. All features preserved. |
