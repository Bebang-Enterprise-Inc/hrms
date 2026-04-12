# S185 Frontend Architecture Audit
**Audited:** 2026-04-12
**Plan:** `docs/plans/2026-04-12-sprint-185-period-comparison-rank-delta.md`
**Auditor:** Architecture review agent

---

## CRITICAL Findings

### CRITICAL-1: SortKey type mismatch — `rank_change` added to leaderboard but not main page; `default` arm swallows it silently

**File:** `app/dashboard/analytics/sales/stores/page.tsx` (leaderboard) + `app/dashboard/analytics/sales/page.tsx` (main page)

The plan (Phase 2.7) adds `"rank_change"` to the `SortKey` union in the leaderboard page (`stores/page.tsx`, lines 54-69). The leaderboard's `keyFn` switch statement currently has a `default` arm that returns `r.net_sales_without_vat`. If `"rank_change"` is added to the type but the `switch` case is not explicitly handled, TypeScript will compile without error (the `default` arm covers it), but sorting by rank change will silently sort by net sales instead — a **corrupt success**. The agent evidence check (`grep -c "rank_change" ...` ≥ 1) will pass because the type declaration counts, but the logic will be wrong.

**Required fix:** Add an explicit `case "rank_change": return r.position_change ?? 0;` to the `keyFn` switch in both `stores/page.tsx` AND — if `rank_change` is also to be sortable in the main page — to the inline `keyFn` in `page.tsx:720-737`. The main page's `sortKey` state type (line 410) does NOT include `rank_change` and will need a separate decision.

**Risk:** Silent wrong-sort; passes grep evidence gate; never caught unless explicitly tested.

---

### CRITICAL-2: `fetchStoreRankings` always sends `include_comparisons=true` — no opt-out path, doubles backend cost on every load

**File:** `lib/api/sales-dashboard.ts` + `app/dashboard/analytics/sales/stores/page.tsx`

Phase 2.2 directs the agent to hardcode `include_comparisons: "true"` into `buildSalesDashboardQuery` or directly into the `fetchStoreRankings` call. The current `fetchStoreRankings` is also called from the main analytics page via the overview bundle. Looking at `page.tsx:716-741`, the main page uses `bundle?.rankings.stores` from the overview endpoint (`fetchSalesOverview`), NOT the dedicated rankings endpoint — so doubling the comparison cost there depends on Phase 3.3's handling.

More critically, the leaderboard page at `stores/page.tsx:205` calls `fetchStoreRankings` directly. Making this always request comparisons means every page load — including date-range changes and refreshes — runs a second DB query (prior period daily rows across all user-scoped stores) on the backend. For a 14-day default range on 45+ stores, this is approximately 2x the SQL row volume per request, with no ability to defer until the user explicitly asks for comparison.

**Risk rated CRITICAL because:** the backend `_query_daily_rows` uses a 300s cache (`_cache_get_or_set`), but cache is keyed by date range — the prior period dates are different from the current dates, so the cache CANNOT be shared between current and prior period queries. Every unique date-range change fires two cold queries.

**Required decision before execution:** Should `include_comparisons` be a toggle the user can enable (default off, saves backend cost), or always-on with a loading indicator? The plan assumes always-on with no user choice — this needs explicit sign-off given backend cost implications.

---

### CRITICAL-3: `rank` vs `index + 1` collision — leaderboard currently uses row index for `#` column; adding API `rank` creates two different numbers for sorted views

**File:** `app/dashboard/analytics/sales/stores/page.tsx:568`

Currently the `#` column renders `{index + 1}` (the sorted position in the current view). Phase 2.3 adds a new "Rank" column showing `store.rank` from the API (which is fixed rank computed on the full RBAC scope by net sales descending for the queried period).

After the change there will be TWO rank numbers visible:
- Column `#` = position in the current sorted/filtered view (e.g., if user sorts by Txns ascending, `#1` = lowest txns store)
- Column `Rank` = API-computed net sales rank

When the user searches/filters (reducing rows to a subset), `#1` will be the first match but `Rank` will show the true fleet-wide rank. This is useful but **must be labeled clearly**. The plan does not specify label disambiguation. If the agent uses the same heading label for both, users will be confused.

**Required fix:** Plan must specify: rename existing `#` column to "View #" or "Pos." and label the API rank column "Fleet Rank" or "Net Rank". Or drop the index column entirely (risky — it also anchors the sticky positioning). Needs explicit plan clarification before execution.

---

### CRITICAL-4: Main page `sortKey` type does not include `rank_change` — adding rank/delta columns to the inline table without extending the type causes TypeScript error or phantom sort behavior

**File:** `app/dashboard/analytics/sales/page.tsx:409-411`

The main page `sortKey` state is typed as:
```
"net" | "gross" | "txns" | "cups" | "agc" | "pickup_pct" | "disruptive"
```

Phase 3.2 adds Rank and Delta columns to the inline ranking table in the main page. If the agent adds a clickable sort header for these columns but does not extend the `sortKey` union, TypeScript will error. If the agent extends the union BUT does not add a corresponding `case` to the `keyFn` at `page.tsx:720-737`, sorting will silently fall through to the `default` (net) arm.

The `toggleSort` callback at `page.tsx:757` uses `typeof sortKey` — extending the union type will automatically propagate to `toggleSort`, but the `switch` body is the failure point.

**Required fix:** The plan should explicitly list: (a) extend `sortKey` union in `page.tsx`, (b) add `case "rank_change"` and `case "rank"` to the `keyFn`, (c) verify `sort.key === "rank_change"` is handled in `ariaSort` equivalent.

---

## WARNING Findings

### WARNING-1: Component line count will breach maintainability threshold — leaderboard page will exceed ~750 lines

**File:** `app/dashboard/analytics/sales/stores/page.tsx` (currently 676 lines)

The plan adds:
- `rank_change` to `SortKey` type (+1 line)
- Rank column `<TableHead>` and `<TableCell>` per store row (+~8 lines each = ~16 lines)
- Rank Change column with badge (+~20 lines for head + cell)
- Net Delta column (+~20 lines)
- Comparison period indicator (+~5 lines)
- CSV export: 6 new columns in header array + 6 new values in row (+~15 lines)

Conservative estimate: **+80-100 lines**, pushing the file to **756-776 lines**.

The `toCsv` function (currently lines 117-168, ~52 lines) will grow to ~70+ lines on its own. The table header section (currently lines 454-548, ~95 lines) will grow to ~140 lines.

**Recommendation:** Extract `toCsv` to a standalone utility file (`stores/leaderboard-csv.ts`) and extract the table header columns into a `<LeaderboardTableHeader>` subcomponent. This is not a blocker but the plan should note it as a refactor gate at 800 lines.

---

### WARNING-2: Mobile view — plan says "add rank badge and net delta display to each store card" but does not specify layout

**File:** `app/dashboard/analytics/sales/stores/store-leaderboard-mobile.tsx`

The current mobile card structure (lines 86-104) has a fixed two-zone header: `[tone dot + store name]` left, `[net sales + pickup %]` right. The 2-column `grid grid-cols-2 gap-2` section (lines 116-130) already has 10 stats.

Adding rank + net delta creates a conflict:
1. Where does the rank badge go? In the name line (cramped), or as a new row above the card header?
2. Where does net delta go? In the right header zone (displacing pickup %)? Or as an 11th/12th stat in the grid (now 12 cells = 6 rows at 2-col — too tall on small screens)?
3. The current `#index + 1` reference at line 94 (`#{index + 1} · {store.warehouse_name}`) should be replaced with `#{store.rank ?? index + 1}` — but if rank is null (comparison unavailable), the fallback must be correct.

**The plan (Phase 3.4) says only:** "add rank badge and net delta display to each store card." This is insufficient specification. Without a layout decision, the agent will make an arbitrary choice that may be visually wrong.

**Required before execution:** Specify: (a) rank replaces `#{index + 1}` in the name line, (b) position change badge appears after rank in the name line (e.g. `#3 ↑2 · Store Name`), (c) net delta appears in the right header zone replacing or appending pickup %, or (d) net delta goes into the grid as two new stat cells.

---

### WARNING-3: Optional field defaults — `comparison?.net_delta` and `store.rank` used in JSX without null coalescing guard will render `undefined` as literal text in some React versions

**File:** `lib/sales-dashboard.ts:256-275` (type), `app/dashboard/analytics/sales/stores/page.tsx` (rendering)

All new fields on `SalesDashboardStoreRanking` are optional (`rank?: number`, `position_change?: number | null`, `comparison?: {...} | null`). The plan's verification greps (e.g. `grep -c "position_change"`) check that the field is referenced but do NOT verify that null/undefined guards are present.

Current pattern for optional fields in the existing code uses `?? 0` or `!= null` guards (e.g. `store.pickup_share != null ? formatPercent(...) : "—"`). The plan must enforce the same pattern for:
- `store.rank ?? (index + 1)` (fallback to row index if rank not returned)
- `store.position_change != null ? renderBadge(...) : <span>—</span>`
- `store.comparison != null ? formatMoney(store.comparison.net_delta) : "—"`
- `store.comparison?.net_delta_pct != null ? formatPercent(...) : "—"`

If the agent omits guards and renders `{store.rank}` on a row where rank is undefined (e.g., when `include_comparisons` is false but the endpoint was called without it), React renders nothing — which is subtle but wrong.

---

### WARNING-4: CSV export function `toCsv` uses hardcoded column array — adding 6 new columns is a correctness risk if column order in header and row do not stay in sync

**File:** `app/dashboard/analytics/sales/stores/page.tsx:117-168`

The current `toCsv` function builds a `header` array (line 118-135) and then a row builder that uses positional correspondence (the nth value must match the nth header). Adding 6 new columns (rank, previous_rank, position_change, prior_net_sales, net_delta, net_delta_pct) means the agent must insert these in BOTH the header array AND the row builder at matching positions.

The current pattern has 16 columns. After the change: 22 columns. This is error-prone if the agent inserts in different positions (e.g., adds rank to front of header but appends net_delta at end of row). The verification grep only checks that `"position_change"` appears somewhere in the CSV section — it does not verify alignment.

**Recommendation:** The plan should specify exact column order OR suggest refactoring `toCsv` to use a column-definition array:
```ts
const COLUMNS = [
  { header: "rank", value: (row, i) => row.rank ?? i + 1 },
  ...
]
```
This makes alignment impossible to break.

---

### WARNING-5: `performanceTone` function is duplicated between `page.tsx` and `store-leaderboard-mobile.tsx` — a third copy added in S185 would be a maintenance problem

**File:** `app/dashboard/analytics/sales/stores/page.tsx:87-93` and `store-leaderboard-mobile.tsx:20-26`

Both files define identical `performanceTone` and `toneClass` functions. The plan does not touch this. However, if S185 adds a similar "delta tone" color function (green/red for positive/negative delta), the agent will likely define it locally in both files — creating a third and fourth copy.

**Recommendation:** The plan should direct the agent to extract shared tone/color helpers to `../_formatters.ts` (which already exists for this purpose) rather than re-defining in each file.

---

### WARNING-6: `position_change` sort direction semantics are unintuitive — sorting "rank_change" descending shows stores that DROPPED most, not stores that improved most

**File:** `app/dashboard/analytics/sales/stores/page.tsx` (sort logic)

The plan (Phase 1.8) defines `position_change = previous_rank - current_rank`. A store going from rank #15 to rank #3 has `position_change = 15 - 3 = +12` (positive = improvement). This is correct directionally.

However, the sort default in the leaderboard is `dir: "desc"`. When the agent adds `case "rank_change": return r.position_change ?? 0` to `keyFn` with `dir: -1` for descending, sorting descending by `rank_change` will show the largest positive changes (biggest improvers) first. This is the CORRECT user expectation for "sort by rank change."

BUT: the plan (Phase 2.7) says "Allow sorting by rank change (largest improvements first)" and the `toggleSort` logic resets to `"desc"` on first click of a new column (line 300: `return { key, dir: "desc" }`). So the default on first click WOULD show improvers first. This is correct.

The warning: the plan does not explicitly state that the initial sort direction for `rank_change` should be `"desc"` (to show improvers first). The `toggleSort` mechanism handles this via the reset-to-desc behavior, but the plan evidence greps do not verify it. **If a future agent reads the code and "cleans up" the toggleSort to preserve direction on column switch, this breaks the UX.**

**Recommendation:** Add a note to Phase 2.7 that `rank_change` sorts default-descending = "best movers at top."

---

### WARNING-7: Aria labels for ↑/↓ badges are not specified — plan does not mention `aria-label` for colored direction badges

**File:** Phase 2.4, 3.5 of plan

The plan specifies that position_change badges should be colored (green ↑N, red ↓N, gray —, muted NEW) but does not specify accessibility. The ↑/↓ characters are Unicode arrows — screen readers may announce these as "upward arrow" or simply "up", which lacks context.

The existing codebase uses `aria-hidden` for decorative icons and `aria-label` on interactive elements (e.g. `aria-label="Performance above average"` on the tone dot at `page.tsx:575`). The rank change badge is informational, not decorative.

**Required:** Each badge must have `aria-label` such as:
- `aria-label="Rank improved by 7 positions"` for `↑7`
- `aria-label="Rank dropped by 3 positions"` for `↓3`
- `aria-label="Rank unchanged"` for `—`
- `aria-label="New to ranking"` for `NEW`

The plan's verification script should grep for these `aria-label` patterns, not just `↑`.

---

### WARNING-8: `SalesDashboardStoreRankingsResponse` already used by main page `page.tsx` — adding `comparison_meta` as optional field to the response type is safe, but the main page fetches via `fetchSalesOverview` (overview bundle), NOT `fetchStoreRankings`

**File:** `lib/sales-dashboard.ts:303-316`, `app/dashboard/analytics/sales/page.tsx`

The plan (Phase 2.1) extends `SalesDashboardStoreRankingsResponse` with optional `comparison_meta`. This is the type returned by `fetchStoreRankings`. The main page (`page.tsx`) does NOT call `fetchStoreRankings` — it calls `fetchSalesOverview` which returns `SalesDashboardOverviewResponse`. The store ranking data on the main page comes from `bundle.rankings` which is typed as the overview's embedded `SalesDashboardStoreRankingsResponse`.

If the backend returns `comparison_meta` inside the rankings sub-object of the overview response AND the agent only adds `comparison_meta` to `SalesDashboardStoreRankingsResponse` (not to `SalesDashboardOverviewResponse.rankings`), the main page will not see `comparison_meta` in TypeScript — even if the data is there at runtime.

**However,** Phase 3.3 says: "the frontend fetch for rankings already gets comparison data if the rankings endpoint accepts and forwards the param." This is unclear — the main page uses `fetchSalesOverview`, not `fetchStoreRankings`. The `get_sales_dashboard_overview` backend endpoint is NOT the rankings endpoint. Unless Phase 3.3 adds `include_comparisons` to the overview call as well (which violates the surface ownership matrix — "Do NOT add this parameter to `get_sales_dashboard_overview`"), the main page will NOT have comparison data from the overview bundle.

**This is a design gap in the plan.** The main page (Phases 3.1-3.2) showing per-store comparison requires EITHER:
1. A second call to `fetchStoreRankings` on the main page (adding a fetch), OR
2. Extending `get_sales_dashboard_overview` to also accept and forward `include_comparisons` (violates HARD BLOCKER 1-1), OR
3. The main page comparison is omitted (contradicts Phase 3.1/3.2 requirements)

**Required resolution before execution:** The plan is internally contradictory on this point. Must decide: does the main page rankings section call `fetchStoreRankings` separately (with comparisons), or does it show comparison from the overview bundle (requiring overview to support `include_comparisons`)?

---

## INFO Findings

### INFO-1: `buildSalesDashboardQuery` in `lib/sales-dashboard.ts` does not currently have an `include_comparisons` parameter

**File:** `lib/sales-dashboard.ts:363-374`

The existing `SalesDashboardFilters` interface (line 355-361) and `buildSalesDashboardQuery` function (line 363-374) do not include `include_comparisons`. The plan says "do NOT change the `fetchStoreRankings` function signature (add new params only)" which is correct, but the query builder also needs updating. The agent should add `includeComparisons?: boolean` to `SalesDashboardFilters` and `if (filters.includeComparisons) params.set("include_comparisons", "true")` to `buildSalesDashboardQuery`. This is a straightforward addition but the plan does not explicitly list it as a task — only mentions it in passing under Phase 2.2.

---

### INFO-2: `channel_mix` field uses `website_non_cod` key in the interface but `web_non_cod` as the sort key — this inconsistency already exists (S182) and will be perpetuated

**File:** `lib/sales-dashboard.ts:246-254` vs `stores/page.tsx:258`

`SalesDashboardStoreChannelMix` uses `website_non_cod` and `website_cod`. The `SortKey` type uses `web_non_cod` and `web_cod`. The `keyFn` correctly maps `web_non_cod` → `mix?.website_non_cod`. No new issue introduced by S185, but any future sort keys added (e.g. for a `grabfood_delta` sort) should follow the established pattern of mapping abbreviated sort keys to full interface field names.

---

### INFO-3: The plan evidence check for Phase 2.4 uses `grep -c "↑"` which will count ALL occurrences of the up-arrow character — including existing sort indicator arrows in table headers

**File:** Plan Phase 2.4 evidence specification

The existing leaderboard page already uses `↑` and `↓` as sort direction indicators in every column header (e.g. line 466: `{sort.dir === "desc" ? "↓" : "↑"}`). The grep count for `↑` will be ≥ 1 regardless of whether the rank change badge was implemented. This evidence gate is unreliable.

**Recommendation:** Replace with `grep -c "position_change > 0"` or `grep -c "PositionChangeBadge\|rank_change_badge"` for a more precise verification.

---

### INFO-4: The `NEW` badge for stores with null `position_change` requires a definition: does null mean "new store in fleet" or "comparison period had no data for this store"?

**File:** Plan Phase 2.4, Phase 1.8

The plan says "stores with no prior period data get `rank_change: null`" and the UI shows "NEW". But there are two distinct cases:
1. Store was not in the prior period because it opened after the prior period started → "NEW" is appropriate
2. Store was in the prior period but had zero sales (e.g., temporarily closed) → "NEW" is misleading; "—" or "No data" would be more accurate

The backend (Phase 1.8) computes `position_change = null` for both cases. The plan does not differentiate.

**Recommendation:** Add a `comparison_available: boolean` field per-store (separate from fleet-level `comparison_meta.comparison_available`) so the frontend can distinguish "no prior data = new store" from "computation error."

---

### INFO-5: The leaderboard page `min-w-[1600px]` table constraint will need updating — 3 new columns push minimum table width further

**File:** `app/dashboard/analytics/sales/stores/page.tsx:453`

The current table has `min-w-[1600px]` and 16 columns. Adding Rank (narrow, ~60px), Rank Change badge (~90px), and Net Delta (~140px) adds approximately 290px, suggesting `min-w-[1900px]` may be needed. The scroll cue gradient (line 636) and the existing `overflow-x-auto` wrapper handle this correctly — just a sizing note. No code change needed beyond updating the Tailwind class.

---

### INFO-6: `comparison_meta` shape in the type (Phase 2.1) does not include `span_days` — useful for the "vs. prior period" indicator subtitle

**File:** `lib/sales-dashboard.ts` (proposed extension)

The plan's proposed `comparison_meta` shape is `{ prior_period_start, prior_period_end, comparison_available }`. The frontend subtitle (Phase 2.6) shows "vs. [prior_period_start] – [prior_period_end]" — this is sufficient. But adding `span_days` would allow the UI to show "vs. prior 7 days" which is more intuitive for users who didn't consciously select a 7-day range (they may have used the date picker). This is a UX enhancement suggestion, not a blocker.

---

## Summary Table

| ID | Severity | Component | Issue |
|----|----------|-----------|-------|
| CRITICAL-1 | CRITICAL | `stores/page.tsx` sort logic | `rank_change` case missing from `keyFn` switch — silent wrong-sort |
| CRITICAL-2 | CRITICAL | `lib/api/sales-dashboard.ts` | Always-on `include_comparisons` doubles backend cost with no opt-out |
| CRITICAL-3 | CRITICAL | `stores/page.tsx` `#` column | `index + 1` vs API `rank` collision — two different numbers visible, ambiguous labels |
| CRITICAL-4 | CRITICAL | `page.tsx` sort type | Main page `sortKey` union not extended — TypeScript error or silent wrong-sort |
| WARNING-1 | WARNING | `stores/page.tsx` | Line count ~756-776 after S185 — extract `toCsv` and table header |
| WARNING-2 | WARNING | `store-leaderboard-mobile.tsx` | Mobile layout for rank + delta not specified in plan |
| WARNING-3 | WARNING | Interface + render | Optional field null guards not mandated — `undefined` renders as blank |
| WARNING-4 | WARNING | `toCsv` function | Hardcoded column array — header/row alignment risk with 6 new columns |
| WARNING-5 | WARNING | Both files | `performanceTone`/`toneClass` duplication will grow with delta tone helpers |
| WARNING-6 | WARNING | Sort UX | `rank_change` default sort direction semantics not documented in plan |
| WARNING-7 | WARNING | Accessibility | ↑/↓ badges lack `aria-label` spec — screen readers announce raw arrows |
| WARNING-8 | CRITICAL | Main page + API | Design gap: main page cannot get comparison data from overview bundle without violating HARD BLOCKER 1-1 |
| INFO-1 | INFO | `buildSalesDashboardQuery` | `include_comparisons` filter param not in `SalesDashboardFilters` type — missing task |
| INFO-2 | INFO | Sort key naming | `web_non_cod` vs `website_non_cod` inconsistency pre-existing, perpetuated |
| INFO-3 | INFO | Verify script | `grep -c "↑"` evidence gate is unreliable — matches existing sort arrows |
| INFO-4 | INFO | `position_change: null` | "NEW" badge meaning ambiguous for closed vs genuinely new stores |
| INFO-5 | INFO | Table width | `min-w-[1600px]` needs update to ~`min-w-[1900px]` |
| INFO-6 | INFO | `comparison_meta` shape | `span_days` missing from meta — useful for "vs. prior N days" subtitle |

---

## Blocker Resolution Required Before Execution

The following items MUST be resolved in the plan before an agent starts execution:

1. **WARNING-8 / design gap:** How does the main page (Phase 3.1-3.2) get per-store comparison data? The overview endpoint is restricted from receiving `include_comparisons`. Options: (a) main page calls `fetchStoreRankings` separately, (b) extend overview endpoint (violates HARD BLOCKER 1-1), (c) scrap Phase 3.1-3.2 for this sprint.

2. **CRITICAL-3 / column label spec:** Provide explicit label names for the existing `#` column vs the new API `rank` column to prevent user confusion.

3. **WARNING-2 / mobile layout spec:** Specify exactly where rank and net delta render in the mobile card layout before giving the agent discretion to place them arbitrarily.

4. **CRITICAL-2 / performance decision:** Decide: always-on comparisons (document accepted backend cost), or user toggle (add toggle UI to plan scope).
