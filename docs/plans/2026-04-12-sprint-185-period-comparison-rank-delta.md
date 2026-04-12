---
sprint_id: S185
sprint_name: "Sales Analytics: Period-over-Period Comparison per Store + Weekly Rank Delta"
branch: s185-period-comparison-rank-delta
repos:
  - bei-tasks (primary — frontend)
  - BEI-ERP (hrms — backend)
branches:
  bei-tasks: s185-period-comparison-rank-delta
  hrms: s185-store-rank-comparison
depends_on: [S182]
status: PLANNED
planned_date: 2026-04-12
amended_date: 2026-04-12
amendment_version: v2
owner: sam@bebang.ph
signoff_authority: single-owner
estimated_units: 28
hard_unit_ceiling: 35
session_scope: single-agent-single-session
plan_file: docs/plans/2026-04-12-sprint-185-period-comparison-rank-delta.md
registry_row: |
  | `S185` | Sprint 185 | `s185-period-comparison-rank-delta` (bei-tasks) + `s185-store-rank-comparison` (hrms) | — | PLANNED 2026-04-12 — Sales Analytics: period-over-period comparison per store + weekly ranking with position delta. |
completed_date: null
execution_summary: null
---

# S185 — Sales Analytics: Period-over-Period Comparison per Store + Weekly Rank Delta

## Executive Summary

Sam (CEO) wants two capabilities on the Sales Analytics dashboard and Store Leaderboard:

1. **Period-over-period comparison per store** — "How is each store doing compared to the same period before?" When viewing any date range (7 days, 10 days, 1 month), show each store's net sales delta vs the equivalent prior period. If viewing Apr 5-11, compare to Mar 29-Apr 4. If viewing a single day, compare to the same day last week.

2. **Weekly rank tracking with position delta** — "Which stores are climbing and which are dropping?" A weekly ranking based on **net sales without VAT** that shows each store's current rank AND how many positions it moved up or down vs the previous week. A store that went from #15 to #8 shows "↑7". A store dropping from #3 to #9 shows "↓6".

### What already exists (S182 baseline, verified 2026-04-12)

| Component | Status | Location |
|-----------|--------|----------|
| `_build_comparisons()` — aggregate period-over-period delta | EXISTS (aggregate only, not per-store) | `sales_dashboard.py:1760-1803` |
| `_shift_range()` — date range shifting helper | EXISTS | `sales_dashboard.py:1756-1757` |
| `_build_store_rankings()` — per-store ranking builder | EXISTS (no comparison, no rank index) | `sales_dashboard.py:2416-2565` |
| `get_sales_dashboard_store_rankings()` endpoint | EXISTS (wraps overview, no comparison param) | `sales_dashboard.py:3082-3120` |
| Store Leaderboard page | EXISTS (sortable table, sparkline, channel mix — NO delta columns) | `bei-tasks/app/dashboard/analytics/sales/stores/page.tsx` (676 lines) |
| Sales Analytics main page | EXISTS (comparison in KPI tiles only — NOT per-store) | `bei-tasks/app/dashboard/analytics/sales/page.tsx` (1820 lines) |
| `SalesDashboardStoreRanking` type | EXISTS (no `rank`, `previous_rank`, `position_change`, `comparison` fields) | `bei-tasks/lib/sales-dashboard.ts:256-275` |

### What needs to be built

- **Backend:** Extend `_build_store_rankings()` to compute per-store comparison (reusing `_query_daily_rows` + `_aggregate_sales` pattern from `_build_comparisons`) AND weekly rank indices with position delta. Add new response fields to each store dict.
- **Frontend (leaderboard):** Add columns for Net Sales Delta (₱ + %), Rank (#N), and Rank Change (↑/↓ badge). Add a "vs. Prior Period" toggle or auto-show when data available.
- **Frontend (main page):** Show per-store comparison inline in the store ranking section on the main Sales Analytics page.

**Total: 28 units, 5 phases.** Single-agent single-session.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

Sam (CEO) said on 2026-04-12: "I want to see the day comparison to the same day a week before. If the selection is for more than 1 day I need to see the comparison in the same range before it. I also want to see that number per store in the leaderboard how the store is performing in comparison to the week before it. Another thing I want is the stores weekly ranking based on net sales without VAT and in leaderboard I want to see how many places the stores moved up or down so we can track if a certain store performance is dropping."

### Why extend existing pages (not a new surface)

The Store Leaderboard page (S182) already has the data infrastructure — per-store net_sales_without_vat, channel mix, sparkline. Adding comparison columns and rank delta is a natural extension. Creating a new "Ranking" page would duplicate data fetching and confuse navigation.

### Period-over-period logic

The existing `_build_comparisons()` function (line 1760) already does this for aggregate data. It calls `_shift_range()` to compute the prior period dates, queries `_query_daily_rows()`, and computes delta + delta_pct. The new work applies this SAME pattern per-store inside `_build_store_rankings()`.

**Key formula:**
- Prior period = shift the ENTIRE date range backward by `span_days = (end_day - start_day).days + 1`
- Example: viewing Apr 5-11 (7 days) → prior period = Mar 29 - Apr 4
- Example: viewing Apr 12 (1 day) → prior period = Apr 5 (same day last week)
- Delta = `current_net - prior_net`
- Delta % = `(delta / prior_net) * 100` if prior_net > 0, else null

### Weekly rank logic

Rank is computed by sorting ALL stores in the user's RBAC scope by `net_sales_without_vat` descending and assigning 1-based indices. The same sort is applied to the prior period's data. Position change = `previous_rank - current_rank` (positive = improved, negative = dropped).

**Why `net_sales_without_vat`?** Sam explicitly said "net sales without VAT." This is the cleanest measure of actual store revenue — no VAT distortion, no discount noise.

### Known limitations

- **Stores with no prior period data** get `rank_change: null` (shown as "—" in UI). This happens for stores that opened within the current period.
- **Rank is relative to RBAC scope.** An Area Supervisor seeing 5 stores gets rank 1-5, not fleet-wide rank. This is intentional (security) but means ranks differ between users.
- **Cache TTL is 300s.** Comparison queries may use up to 5-minute-old data. Acceptable for daily/weekly analytics.

### Source references (verified 2026-04-12)

- **`_build_comparisons()`**: `hrms/api/sales_dashboard.py:1760-1803` — aggregate comparison builder (reuse pattern)
- **`_shift_range()`**: `hrms/api/sales_dashboard.py:1756-1757` — date range shift helper
- **`_build_store_rankings()`**: `hrms/api/sales_dashboard.py:2416-2565` — per-store ranking builder (MODIFY)
- **`get_sales_dashboard_store_rankings()`**: `hrms/api/sales_dashboard.py:3082-3120` — rankings endpoint (MODIFY to accept `include_comparisons`)
- **`_query_daily_rows()`**: `hrms/api/sales_dashboard.py:1384-1402` — daily rows query with 300s cache
- **`_aggregate_sales()`**: used in `_build_comparisons` — aggregates daily rows into totals
- **Store Leaderboard page**: `bei-tasks/app/dashboard/analytics/sales/stores/page.tsx` (676 lines)
- **Store Leaderboard mobile**: `bei-tasks/app/dashboard/analytics/sales/stores/store-leaderboard-mobile.tsx`
- **Sales main page rankings section**: `bei-tasks/app/dashboard/analytics/sales/page.tsx:705-780`
- **`SalesDashboardStoreRanking` type**: `bei-tasks/lib/sales-dashboard.ts:256-275`
- **`fetchStoreRankings()`**: `bei-tasks/lib/api/sales-dashboard.ts` — frontend API helper
- **Sentry context**: already present at `sales_dashboard.py:3094-3098`

---

## Agent Boot Sequence

1. **Read this plan fully.**
2. **Create frontend branch:**
   ```bash
   cd F:/Dropbox/Projects/bei-tasks
   git fetch origin main && git checkout -b s185-period-comparison-rank-delta origin/main
   ```
3. **Create backend branch:**
   ```bash
   cd F:/Dropbox/Projects/BEI-ERP
   git fetch origin production && git checkout -b s185-store-rank-comparison origin/production
   ```
4. **Read the existing `_build_store_rankings()`** (`hrms/api/sales_dashboard.py:2416-2565`).
5. **Read the existing `_build_comparisons()`** (`hrms/api/sales_dashboard.py:1760-1803`) for the reuse pattern.
6. **Read the Store Leaderboard page** (`app/dashboard/analytics/sales/stores/page.tsx`, 676 lines).
7. **Read `SalesDashboardStoreRanking` type** (`lib/sales-dashboard.ts:256-275`).
8. **Read the Sales main page rankings section** (`app/dashboard/analytics/sales/page.tsx:705-780`).
9. **Do not modify any file outside the Surface Ownership Matrix.**

---

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

---

## Requirements Regression Checklist

- [ ] Does the comparison use the SAME span shifted backward? (7-day window → compare to prior 7 days, NOT prior week Mon-Sun)
- [ ] Is per-store comparison computed from `net_sales_without_vat` (NOT gross_sales)?
- [ ] Is the prior period query using `_query_daily_rows` with the shifted dates? (reuse cached daily data pattern)
- [ ] Does weekly rank use `net_sales_without_vat` for sorting? (HARD BLOCKER — Sam's explicit requirement)
- [ ] Is `position_change` computed as `previous_rank - current_rank`? (positive = improvement, negative = drop)
- [ ] Does the rank cover ALL stores in the user's RBAC scope? (not just the filtered/selected stores)
- [ ] Does the leaderboard show rank change with ↑/↓/— badges color-coded green/red/gray?
- [ ] Are stores with no prior period data shown as "—" (not 0 or missing)?
- [ ] Does the comparison auto-populate when data loads? (no extra user click needed)
- [ ] Does the existing leaderboard functionality remain unchanged when comparison data is unavailable?
- [ ] Does every new/modified `@frappe.whitelist()` endpoint call `set_backend_observability_context()`? (Already present — verify only)
- [ ] Is the Leaderboard mobile view also updated with rank + comparison columns?

---

## Surface Ownership Matrix

| Owner | Owned file globs |
|---|---|
| S185 backend | `hrms/api/sales_dashboard.py` — `_build_store_rankings` (lines 2416-2565) + `get_sales_dashboard_store_rankings` (lines 3082-3120) + `_build_dashboard_overview_payload` (ONLY to thread `include_comparisons` param — no logic changes). |
| S185 frontend leaderboard | `app/dashboard/analytics/sales/stores/page.tsx` (extend) |
| S185 frontend leaderboard mobile | `app/dashboard/analytics/sales/stores/store-leaderboard-mobile.tsx` (extend) |
| S185 frontend types | `lib/sales-dashboard.ts` — ONLY `SalesDashboardStoreRanking` interface (extend with optional fields) |
| S185 frontend main page | `app/dashboard/analytics/sales/page.tsx` — ONLY the store ranking section (~lines 705-780, 1513+). Do NOT touch KPI tiles, channel mix, or weather sections. |

**Protected surfaces (do not touch):**
- `hrms/api/sales_dashboard.py` — all other functions (especially `_build_comparisons`). Note: `_build_dashboard_overview_payload` may be touched ONLY to add `include_comparisons` param threading — no logic changes.
- `.github/workflows/*`
- `app/dashboard/analytics/product/**/*` (S183)
- `lib/roles.ts`, `lib/constants.ts`
- `lib/api/sales-dashboard.ts` — do NOT change the `fetchStoreRankings` function signature (add new params only)

---

## Phase Budget Contract

| Phase | Name | Est. Units | Hard Cap |
|---|---|---|---|
| Phase 0 | Branch setup + baseline | 1 | 2 |
| Phase 1 | Backend: per-store comparison + rank delta | 10 | 12 |
| Phase 2 | Frontend: leaderboard rank + comparison columns | 8 | 10 |
| Phase 3 | Frontend: main page per-store comparison + mobile | 5 | 7 |
| Phase 4 | Verification + PRs + closeout | 4 | 5 |
| **Total** | | **28** | **36** |

---

## Phase Table

### Phase 0 — Branch setup + baseline (1 unit)

| # | Task | MUST_MODIFY / Evidence |
|---|---|---|
| 0.1 | Create both branches (see boot sequence) | `git branch --show-current` correct in each repo |
| 0.2 | Record base SHAs in `output/s185/BASELINE.md` | File exists |

### Phase 1 — Backend: per-store comparison + rank delta (10 units)

**Goal:** Extend `_build_store_rankings()` so each store dict includes comparison data and rank position change.

| # | Task | MUST_MODIFY / Evidence |
|---|---|---|
| 1.1 | Read `_build_store_rankings()` (lines 2416-2565). Understand the two-pass architecture: **Pass 1** (lines 2442-2480) accumulates raw MV values per `location_id` via `by_location` loop. **Pass 2** (lines 2496-2564) overrides `net_sales_without_vat` with channel-split-corrected `clean_net`. The return sort at line 2565 uses `gross_sales`. Do NOT use `_aggregate_sales()` — it returns fleet-wide totals, not per-store. | Mental model |
| 1.2 | **Thread `include_comparisons` parameter.** (a) Add `include_comparisons: bool | str | None = None` to `get_sales_dashboard_store_rankings()` (line 3082). Parse using `_include_comparisons = _to_bool_flag(include_comparisons, default=False)` (audit fix B-5 — `_to_bool_flag` at line 2403, NOT raw truthiness). (b) Forward to `get_sales_dashboard_overview(include_comparisons=_include_comparisons, ...)` call at line 3100. (c) `get_sales_dashboard_overview` already accepts `include_comparisons` (line 2983) and passes it to `_build_dashboard_overview_payload`. (d) In `_build_dashboard_overview_payload`, add `include_comparisons` to the `_build_store_rankings()` call. **HARD BLOCKER 1-1:** `_build_dashboard_overview_payload` may ONLY be touched to thread this parameter — no logic changes. | `grep -c "include_comparisons" hrms/api/sales_dashboard.py` ≥ 4; `grep -c "_to_bool_flag" hrms/api/sales_dashboard.py` in rankings function ≥ 1 |
| 1.3 | **Query prior period daily rows.** Inside `_build_store_rankings()`, when `include_comparisons=True`: compute `span_days = (end_day - start_day).days + 1`, `prev_start, prev_end = _shift_range(start_day, end_day, span_days)` (reuse existing `_shift_range` at line 1756). Query: `prev_rows = _query_daily_rows(prev_start, prev_end, [s["location_id"] for s in scope["selected_stores"]])`. Do NOT add a new `_cache_get_or_set` wrapper around the aggregated result — `_query_daily_rows` already caches its raw rows internally (audit fix B-1 — cache key collision risk). Aggregate in-process. | `grep -c "prev_start" hrms/api/sales_dashboard.py` ≥ 1; `grep -c "prev_rows" hrms/api/sales_dashboard.py` ≥ 1 |
| 1.4 | **Aggregate prior period per-store (audit fixes B-1, B-2, B-6).** Build `prev_by_location: dict[int, dict[str, float]]` by iterating `prev_rows`. For each row: `prev_by_location[location_id]["net"] += _to_float(row.get("total_net_sales_without_vat"))` and `prev_by_location[location_id]["gross"] += _to_float(row.get("total_gross_sales"))`. **CRITICAL (B-1):** The column is `total_net_sales_without_vat` — NOT `net_sales - vat_amount` (those columns don't exist, and double-subtracting VAT is a known bug per line 844 comment). **CRITICAL (B-6):** Filter to RBAC scope: `allowed_ids = {s["location_id"] for s in scope["selected_stores"]}; if lid not in allowed_ids: continue`. | `grep -c "prev_by_location" hrms/api/sales_dashboard.py` ≥ 1; `grep -c "total_net_sales_without_vat" hrms/api/sales_dashboard.py` in prev section ≥ 1; `grep -c "allowed_ids" hrms/api/sales_dashboard.py` ≥ 1 |
| 1.5 | **Compute per-store comparison fields (audit fix B-7).** AFTER the channel-split Pass 2 loop (line ~2564), for each store in the final `by_location`, look up `prev_net` from `prev_by_location`. Add: `comparison: { prior_net_sales: float, net_delta: float, net_delta_pct: float|null, prior_gross_sales: float, gross_delta: float, gross_delta_pct: float|null, prior_period: {start: str, end: str}, prior_period_zero: bool }`. `net_delta_pct = round((net_delta / prior_net) * 100, 1) if prior_net > 0 else None`. If no prior data for this store: `comparison: None, is_new_store: True`. | `grep -c "net_delta" hrms/api/sales_dashboard.py` ≥ 2; `grep -c "net_delta_pct" hrms/api/sales_dashboard.py` ≥ 1; `grep -c "is_new_store" hrms/api/sales_dashboard.py` ≥ 1 |
| 1.6 | **Compute current rank (audit fix B-3).** AFTER the channel-split Pass 2 loop (where `net_sales_without_vat` is overridden with `clean_net`), sort all stores by `net_sales_without_vat` descending and assign `rank: int` (1-based). **CRITICAL:** This is a SEPARATE rank-assignment pass, NOT a change to the existing return sort at line 2565. The existing `sorted(..., key=lambda row: row["gross_sales"], ...)` return sort stays as-is for backward compatibility. Rank is ADDED as a field. | `grep -c '"rank"' hrms/api/sales_dashboard.py` ≥ 2 |
| 1.7 | **Compute previous period rank (audit fix B-7).** Build a list of `(location_id, prev_net)` from `prev_by_location`, sort descending, assign `previous_rank: int` (1-based). Stores not in `prev_by_location` get `previous_rank = None`. Guard: `position_change = (previous_rank - rank) if previous_rank is not None else None`. | `grep -c "previous_rank" hrms/api/sales_dashboard.py` ≥ 2 |
| 1.8 | **Add rank + position_change to each store dict.** Add `rank`, `previous_rank`, `position_change`, `is_new_store` (True when `previous_rank is None`). | `grep -c "position_change" hrms/api/sales_dashboard.py` ≥ 2; `grep -c "is_new_store" hrms/api/sales_dashboard.py` ≥ 1 |
| 1.9 | **Add comparison meta to response.** In `get_sales_dashboard_store_rankings()` return dict, add `comparison_meta: { prior_period_start: str, prior_period_end: str, comparison_available: bool, rank_delta_reliable: span_days >= 7 }` (audit fix B-8 — suppress rank delta on short windows). | `grep -c "comparison_meta" hrms/api/sales_dashboard.py` ≥ 1; `grep -c "rank_delta_reliable" hrms/api/sales_dashboard.py` ≥ 1 |
| 1.10 | **Python parse check.** `python -c "import ast; ast.parse(...)"` → OK. | Parse clean |

**HARD BLOCKER 1-1:** Do NOT modify `_build_comparisons()`. `_build_dashboard_overview_payload()` may ONLY be touched to thread the `include_comparisons` parameter to `_build_store_rankings()` — no logic changes. The per-store comparison is computed inside `_build_store_rankings()` using the `by_location` accumulator pattern (direct loop over rows, group by `location_id`). Do NOT call `_aggregate_sales()` — it returns fleet-wide totals.

**HARD BLOCKER 1-2:** Rank MUST be based on `net_sales_without_vat` — NOT `gross_sales`. Sam explicitly said "net sales without VAT."

### Phase 2 — Frontend: leaderboard rank + comparison columns (8 units)

**Goal:** Add Rank, Rank Change, and Prior Period Comparison columns to the Store Leaderboard page.

| # | Task | MUST_MODIFY / Evidence |
|---|---|---|
| 2.1 | **Extend `SalesDashboardStoreRanking` interface** in `lib/sales-dashboard.ts` with optional fields: `rank?: number`, `previous_rank?: number`, `position_change?: number | null`, `comparison?: { prior_net_sales: number, net_delta: number, net_delta_pct: number | null, prior_gross_sales: number, gross_delta: number, gross_delta_pct: number | null, prior_period: { start: string, end: string } } | null`. Also extend `SalesDashboardStoreRankingsResponse` with optional `comparison_meta?: { prior_period_start: string, prior_period_end: string, comparison_available: boolean }`. | `grep -c "position_change" lib/sales-dashboard.ts` ≥ 1; `grep -c "comparison_meta" lib/sales-dashboard.ts` ≥ 1 |
| 2.2 | **Update `fetchStoreRankings()` to pass `include_comparisons=true`.** In `lib/api/sales-dashboard.ts`, add `include_comparisons: "true"` to the query params built for the store-rankings endpoint. | `grep -c "include_comparisons" lib/api/sales-dashboard.ts` ≥ 1 |
| 2.3 | **Replace existing `#` column with API rank (audit fix FE-C3).** The existing `#` column shows row index (`idx + 1`). Replace it with `store.rank` from the API (net sales rank). Label the column header "Rank" (not "#"). When `store.rank` is undefined (comparison not available), fall back to `idx + 1`. | `grep -c "store.rank\|store\.rank" app/dashboard/analytics/sales/stores/page.tsx` ≥ 1 |
| 2.4 | **Add Rank Change badge column (audit fix FE-W7).** After Rank column: show position change with colored badge. `position_change > 0` → green `↑N` badge. `position_change < 0` → red `↓N` badge. `position_change === 0` → gray `—` badge. `null` or `is_new_store` → muted `NEW`. **Suppress badge when `comparison_meta.rank_delta_reliable === false`** (window < 7 days). Add `aria-label` to each badge (e.g., `aria-label="Moved up 3 positions"`). | `grep -c "position_change" app/dashboard/analytics/sales/stores/page.tsx` ≥ 2; `grep -c "aria-label" app/dashboard/analytics/sales/stores/page.tsx` in rank section ≥ 1 |
| 2.5 | **Add Net Sales Delta column.** After existing Net w/o VAT column: show `comparison.net_delta` as `+₱X,XXX (+X.X%)` in green or `-₱X,XXX (-X.X%)` in red. If no comparison: show "—". | `grep -c "net_delta" app/dashboard/analytics/sales/stores/page.tsx` ≥ 1 |
| 2.6 | **Add comparison period indicator.** Below the DateRangePicker or as a subtitle, show: "vs. [prior_period_start] – [prior_period_end]" in muted text when comparison data is available. | `grep -c "prior_period" app/dashboard/analytics/sales/stores/page.tsx` ≥ 1 |
| 2.7 | **Add Rank Change sort key (audit fix FE-C1).** Add `"rank_change"` to the `SortKey` type AND add an explicit `case "rank_change":` in the `keyFn` switch that returns `store.position_change ?? -9999` (nulls sort last). Do NOT rely on the `default` fallback — it silently sorts by `net_sales_without_vat`. | `grep -c "rank_change" app/dashboard/analytics/sales/stores/page.tsx` ≥ 1; `grep -c "case.*rank_change" app/dashboard/analytics/sales/stores/page.tsx` ≥ 1 |
| 2.8 | **Add rank + comparison info to CSV export.** When exporting CSV, include: Rank, Previous Rank, Position Change, Prior Net Sales, Net Delta, Net Delta %. | `grep -c "position_change\|net_delta" app/dashboard/analytics/sales/stores/page.tsx` in CSV section ≥ 1 |

### Phase 3 — Frontend: main page per-store comparison + mobile (5 units)

**Goal:** Show per-store comparison inline in the main Sales Analytics page rankings section, and update the mobile leaderboard view.

| # | Task | MUST_MODIFY / Evidence |
|---|---|---|
| 3.1 | **Update main page Top 8 store leaders section.** In `page.tsx:705-780`, show rank change badge next to each store name in the top-8 list. | `grep -c "position_change" app/dashboard/analytics/sales/page.tsx` ≥ 1 |
| 3.2 | **Update main page full rankings table.** In `page.tsx:1513+`, add Rank and Delta columns to the inline store ranking table (same pattern as Phase 2 leaderboard). | `grep -c "net_delta" app/dashboard/analytics/sales/page.tsx` ≥ 1 |
| 3.3 | **Update `fetchSalesOverview()` to pass `include_comparisons` (audit fix FE-C4).** The main page calls `fetchSalesOverview` (overview endpoint). Since Task 1.2 threads `include_comparisons` through `get_sales_dashboard_overview` → `_build_dashboard_overview_payload` → `_build_store_rankings`, the overview response's `stores` array will contain rank + comparison data. In `lib/api/sales-dashboard.ts`, add `include_comparisons: "true"` to the `fetchSalesOverview` query params. The param already exists on the backend (line 2983). | `grep -c "include_comparisons" lib/api/sales-dashboard.ts` ≥ 2 |
| 3.4 | **Update mobile leaderboard component.** In `store-leaderboard-mobile.tsx`, add rank badge and net delta display to each store card. | `grep -c "position_change\|net_delta" app/dashboard/analytics/sales/stores/store-leaderboard-mobile.tsx` ≥ 1 |
| 3.5 | **Visual polish.** Rank change badge: `↑` green, `↓` red, `—` gray, `NEW` muted. Delta amounts: green for positive, red for negative. Compact layout for mobile. | Badge colors present |

### Phase 4 — Verification + PRs + closeout (4 units)

| # | Task | MUST_MODIFY / Evidence |
|---|---|---|
| 4.1 | **Verification script.** Create `output/s185/verify_s185.py` with filesystem assertions for both repos. Run → PASS. | File exists, exits 0 |
| 4.2 | **Push both branches, create 2 PRs.** hrms → production. bei-tasks → main. `GH_TOKEN=""` prefix. | Both PR numbers recorded |
| 4.3 | **Update plan YAML** to `status: DEPLOYED` + update `SPRINT_REGISTRY.md` with PR numbers. `git add -f docs/plans/`. | Plan + registry updated |
| 4.4 | **Generate L3 handoff prompt.** | Handoff prompt output |

---

## Zero-Skip Enforcement

Every task in the phase table MUST be implemented. The agent is FORBIDDEN from:
- Skipping a task silently
- Marking partial work as "done"
- Replacing a task with a simpler version without user approval
- Saying "deferred to next sprint"
- Implementing happy path only, skipping edge cases
- Combining tasks and dropping features

**Phase Completion Checklist:** After each phase, write `output/s185/phase_N_completion.md` with task-by-task status. If any task is skipped/partial, STOP and notify user.

### Verification Script (MANDATORY)

Create `output/s185/verify_s185.py`. Runs after every phase AND at closeout. PR cannot be created until PASS.

The script checks:
- Phase 1 backend patterns: `include_comparisons`, `prev_start`, `prev_rows`, `prev_by_location`, `net_delta`, `net_delta_pct`, `position_change`, `previous_rank`, `comparison_meta`
- Phase 2-3 frontend patterns: `position_change`, `net_delta`, `↑`, `rank_change`, `prior_period`, `comparison_meta`, `include_comparisons`
- Protected surface check: no workflow files modified
- MUST NOT contain: `ToggleGroup` (not installed), `useMediaQuery` (doesn't exist)

---

## L3 Workflow Scenarios

| ID | User | Action | Expected Outcome | Failure Means |
|---|---|---|---|---|
| L3-185-01 | sam@bebang.ph | Load Store Leaderboard with default 7-day range | Rank column shows #1-#N for each store. Position change badges visible (↑/↓/—). Net Delta column shows ₱ amounts with %. | Rank/comparison not computed |
| L3-185-02 | sam@bebang.ph | Verify rank order matches net sales w/o VAT descending | Store with highest net_sales_without_vat has rank #1 | Rank sorted by wrong field |
| L3-185-03 | sam@bebang.ph | Verify comparison period indicator text | Shows "vs. [date] – [date]" matching the prior period | Date shift wrong |
| L3-185-04 | sam@bebang.ph | Check ≥1 store has positive delta (green ↑) | Green upward badge with position count | No rank changes computed |
| L3-185-05 | sam@bebang.ph | Check net delta display format | Shows "+₱X,XXX (+X.X%)" or "-₱X,XXX (-X.X%)" with correct colors | Delta display broken |
| L3-185-06 | sam@bebang.ph | Change date range to "Last 14 days" | Leaderboard refreshes. Comparison period shifts (14 days prior). Rank may change. | Date range not passed to comparison |
| L3-185-07 | sam@bebang.ph | Change to single-day view (Yesterday) | Comparison shows same day last week. Rank still computed. | Single-day comparison broken |
| L3-185-08 | sam@bebang.ph | Sort by "Rank Change" column | Stores sorted by largest positive change first | Sort key not wired |
| L3-185-09 | sam@bebang.ph | Export CSV with rank + comparison data | CSV includes Rank, Previous Rank, Position Change, Prior Net, Net Delta, Net Delta % | Export missing new columns |
| L3-185-10 | sam@bebang.ph | Check mobile leaderboard view | Rank badge and delta visible on mobile cards | Mobile not updated |
| L3-185-11 | sam@bebang.ph | Verify main Sales Analytics page shows rank badges in top-8 section | Rank change badges next to store names | Main page not updated |
| L3-185-12 | sam@bebang.ph | Load with 30-day date range | Comparison uses 30-day prior period (not calendar month). All stores have comparison data. | Wide-range comparison broken |
| L3-185-13 | sam@bebang.ph | Verify store with no prior data shows "NEW" badge | If any store has `is_new_store: true`, shows muted "NEW" instead of ↑/↓. If none exist, verify null-handling renders "—". | New store handling broken |

---

## Autonomous Execution Contract

- **completion_condition:**
  - All 5 phases marked DONE in `output/s185/phase_N_completion.md`
  - `output/s185/verify_s185.py` exits 0
  - 2 PRs created (hrms + bei-tasks)
  - Plan YAML updated to DEPLOYED, SPRINT_REGISTRY.md updated with PR numbers
- **stop_only_for:**
  - Missing credentials/access
  - Direct conflict on `hrms/api/sales_dashboard.py` with a newer sprint
  - Repeated (3x) technical failure with no progress after grounded research
- **continue_without_pause_through:** `execute → pr_creation → closeout`
- **blocker_policy:**
  - programmatic → fix and continue
  - repeated failure x3 → grounded research, continue
  - business-data/policy → pause
  - verify_s185.py FAIL → fix and re-run immediately
- **signoff_authority:** single-owner (sam@bebang.ph)
- **canonical_closeout_artifacts:**
  - `output/s185/BASELINE.md`
  - `output/s185/phase_0..4_completion.md`
  - `output/s185/verify_s185.py` + `verify_output.txt`
  - `docs/plans/2026-04-12-sprint-185-period-comparison-rank-delta.md`
  - `docs/plans/SPRINT_REGISTRY.md`

---

## Backend Deploy Notes

Phase 1 modifies `get_sales_dashboard_store_rankings` (Python source change). Dispatch `build-and-deploy.yml` with **`skip_build=false, no_cache=true`** (MEMORY lesson #2).

---

## Execution Workflow

- Test Python changes: `/local-frappe`
- Deploy changes: `/deploy-frappe` (Sam handles merge + deploy trigger)
- Full workflow: `/agent-kickoff`
- E2E testing: `/e2e-test` or `/test-full-cycle`

---

## Anti-Rewind Protection

- **remote_truth_baseline:** `output/s185/BASELINE.md` with both SHAs
- **protected_surfaces:** see Surface Ownership Matrix
- **rebase rule:** before pushing, `git fetch origin` and rebase. Re-run `verify_s185.py`. Grep for conflict markers.

---
