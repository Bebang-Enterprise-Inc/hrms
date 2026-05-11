---
sprint: S245
title: Sales Analytics — Daily/Weekly/Monthly Granularity Toggle
filename: 2026-05-11-sprint-245-analytics-sales-granularity-toggle.md
branch: s245-analytics-sales-granularity-toggle
repo: bei-tasks
pr_base: main
status: PR_OPEN
version: 1.1
frontend_pr: 465
pr_url: https://github.com/Bebang-Enterprise-Inc/BEI-Tasks/pull/465
pr_opened_date: 2026-05-11
audit_log:
  - 2026-05-11 v1.0 PLANNED initial draft via /write-plan-bei-erp
  - 2026-05-11 v1.1 PLANNED_AUDITED — 8 domain auditors + code-verifier + adversarial fact-checker. 6 CRITICAL + 3 PARTIAL WARNINGs + 3 quality WARNINGs verified against source code. NG-1 and NG-2 discarded as false positives. Amendments applied inline.
  - 2026-05-11 v1.1+ cold-start sweep — pinned remaining 3 "implementer's choice" guess points: Phase 2.6 (`day_of_week` + `weather_description`), Phase 3.1 (active button `bg-teal-700`), Phase 4.3 (`minTickGap` conditional values). Plan is now fully cold-start ready.
  - 2026-05-11 PR_OPEN — executed all 8 phases via /execute-plan-bei-erp. 28/28 vitest pass, 8/8 L3 Playwright pass, npm run build green. PR #465 opened on bei-tasks main. Awaiting Sam's merge.
created: 2026-05-11
owner: CEO (single-owner)
canonical_scope: none
canonical_scope_rationale: |
  Pure frontend polish on bei-tasks Sales Analytics page. Adds client-side
  aggregation + UI toggle. Does NOT touch tabCompany, tabWarehouse, tabCustomer,
  tabSupplier, Sales Invoices, Purchase Orders, Material Requests, Stock
  Entries, Journal Entries, Payment Entries, GL Entries, or any canonical
  resolver function (resolve_store_buyer_entity, etc.). Reads only existing
  `/api/analytics/sales/overview` daily rows already produced by the backend;
  no Frappe whitelist endpoint signature changes, no Supabase schema changes.
evidence_committed:
  - output/s245/SUMMARY.md
  - output/s245/verification/before_after_screenshots/*.png
  - output/s245/verification/aggregation_unit_tests.log
  - output/s245/verification/url_state_persistence.json
  - output/s245/verification/l3_playwright_results.json
evidence_transient:
  - tmp/s245/dev_server_*.log
  - tmp/s245/playwright_trace_*.zip
  - tmp/s245/build_*.log
  - tmp/s245/console_capture_*.txt
related_sprints:
  - S176  # DateRangePicker (modern dual-calendar)
  - S182  # Sales Dashboard structure (formatters extraction, dialog, leaderboard)
  - S185  # include_comparisons + per-store rank
  - S191  # Mosaic channel split per day in _aggregate_daily_series
depends_on:
  - none (existing /api/analytics/sales/overview is already live)
---

# Sprint 245 — Sales Analytics Daily/Weekly/Monthly Granularity Toggle

## Audit Amendments (v1.1) — 2026-05-11

### Audit Methodology

8 parallel domain auditors + code-verifier + adversarial fact-checker:

| Domain | CRITICAL raw | WARN raw | Final verdict |
|---|---:|---:|---|
| Frontend | 3 | 7 | 3 CONFIRMED |
| Deployment & QA | 3 | 5 | 3 CONFIRMED |
| System Architecture | 1 | 2 | 1 CONFIRMED (PARTIAL — narrowed) |
| Design Review | 4 | 6 | 2 CONFIRMED, 2 demoted to WARN |
| Cold Start | 5 | 6 | 5 CONFIRMED |
| Zero Skip | 0 | 4 | 0 |
| Dependency Tracking | 2 | 3 | 2 CONFIRMED (+ 33 deps VERIFIED-OK) |
| Team Orchestration | 0 | 5 | 0 |
| Code-verifier | — | — | Converged 9 CRITICAL → 6 SUPPORTED + 3 PARTIAL after fact-check |
| Adversarial fact-checker | — | — | 6 SUPPORTED + 3 PARTIAL + 2 NOT_FOUND (false positives discarded) |

Findings files: `output/plan-audit/sprint-245-analytics-sales-granularity-toggle/{frontend,deployment_qa,system_arch,design_review,cold_start,zero_skip,dependency_tracking,team_orchestration}_findings.md` + `code_verification.md` + `blockers_for_verification.md` + `fact_check_verification.md` + `verified_blockers.md`.

### Verified Blockers (6 CRITICAL + 3 PARTIAL WARNINGs + 3 quality WARNINGs)

**🔴 CRITICAL (6) — must resolve before /execute-plan-bei-erp**

| ID | Title | Phases | Source evidence |
|---|---|---|---|
| **B1** | `npm run test` script does NOT exist in `bei-tasks/package.json`. Plan instructs running `npm run test -- _aggregation.test.ts` which will fail at the shell. Vitest 4.0.15 IS installed; correct invocation is `npx vitest run <path>`. Plan also references a phantom "Phase 2 deviation note" that doesn't exist. | Phase 2.8, Phase 4.8, "Execution Workflow" | `package.json` lines 5-11: only 5 scripts (dev, build, start, lint, audit:erpnext-notify) |
| **B2** | Wrong fixture name AND wrong test email in all 8 L3 scenarios. Plan: `loggedInAsAreaSupervisor` + `test.areasup@bebang.ph`. Actual: `loggedInAreaSupervisor` (no "As") + `test.area@bebang.ph` (no "sup"). TS compile error or login failure. | Phase 6.1, all 8 L3 rows, Test Data Seeding paragraph | `tests/e2e/fixtures/auth.ts:105`; `tests/e2e/helpers.ts:14` |
| **B3** | Toggle placement instruction is internally contradictory. Plan says "card header (around line 1199-1213)" but `</CardHeader>` is at line 1201 and the badge row is in `<CardContent>` at lines 1203-1213. | Phase 3.3 | `page.tsx:1188-1213` |
| **B6** | `<details>` vs shadcn `Collapsible` ambiguity. Plan says "or shadcn Collapsible if primitive imported" but MUST_CONTAIN asserts `<details` literal. shadcn Collapsible IS installed (`@radix-ui/react-collapsible@^1.1.11` + `components/ui/collapsible.tsx`, used in HR dialog) — agent picking the better choice gets false-negative MUST_CONTAIN failure. | Phase 4.6 | `components/ui/collapsible.tsx` exists |
| **B7** | DateRangePicker requires explicit `Apply` click — L3 scenarios miss it. `applyPreset` only calls `setDraft()`; `handleApply` (Apply button onClick) fires `onFromChange`/`onToChange`. Playwright tests clicking a preset and immediately asserting state will fail. | L3 scenarios L3-2/3/4/7, Phase 5.2 | `date-range-picker.tsx:174-183` |
| **B9** | ISO week format token wrong. Plan: `format(date, "yyyy-'W'WW")`. With `date-fns@^4.1.0`, dates in late December that belong to ISO Week 1 of the next year produce wrong bucket keys (e.g., 2025-12-29 → `"2025-W01"` ≠ correct `"2026-W01"`). The plan adds "Last Year" preset which guarantees this scenario. Correct: `RRRR-'W'II`. | Phase 2.2, Phase 2.7 (new unit test) | date-fns v4 token semantics; "Last Year" preset span |

**🟡 WARNINGs (3 PARTIAL — real risk, narrower than original claim)**

| ID | Title | Phases | Mechanism |
|---|---|---|---|
| **B4** | `SalesWeatherTick` reads `is_weekend`/`is_holiday`/`rain_severity` on bucket rows. Booleans are inherited from `SalesDashboardDailyRow` (won't be `undefined` per TS types), but `aggregateRows` must explicitly SET them on bucket rows from count fields or the tick indicators silently misbehave on multi-day buckets. | Phase 2.5/2.6, Phase 4.2 | `page.tsx:190-207` |
| **B5** | `useMemo<SalesWeatherChartRow[]>` type annotation is semantically wrong post-refactor (bucket rows are not `SalesWeatherChartRow`). TypeScript's excess-property check does NOT apply to spread/map results, so this compiles — but the annotation should be updated for accuracy. | Phase 4.1 | `page.tsx:684` |
| **B8** | Precipitation aggregation: SUM is wrong for intensity metrics. Backend (`sales_dashboard.py:2459-2470`) stores all 4 precipitation fields as per-day store averages (`sum / coverage_count`). SUM is defensible for `total_precipitation` and `precipitation_hours` (cumulative). SUM is wrong for `average_max_hourly_precipitation` and `max_hourly_precipitation` (peak — should be MAX). | Phase 2.5 | `hrms/api/sales_dashboard.py:2459-2470` |

**🟢 Quality WARNINGs (NCV — code-verifier non-convergent)**

| ID | Title | Phases |
|---|---|---|
| **NCV-4** | CardTitles "Daily Net Sales vs Weather Drivers" (line 1192) and "Daily Signals" (line 1787) hard-code "Daily". Plan addresses CardDescription dynamic text but not CardTitles. | Phase 4.5 or 4.7 |
| **NCV-6** | useRef vs useState ambiguity for override flag. Plan says "implementer's choice". Pin `useRef<boolean>(false)` — `useState` flip triggers re-render that re-fires the auto-default useEffect before state settles. | Phase 1.5 |
| **NCV-7** | Phase 4.7 cites CardDescription string `"Daily net sales over the selected window with weather and calendar context."` — that string does NOT appear in page.tsx. Actual line 1199 text: `"Net sales, temperature, and precipitation layered across the selected window for faster pattern reading."` | Phase 4.7 |

### ❌ False Positives Discarded

- **NG-1** "This Year" preset future end-date: `react-day-picker@^9.12.0` Calendar component is rendered without `toDate`/`disabled` props → future dates ARE selectable. No crash.
- **NG-2** Phase 4.1 memo-collapse: Phase 4.5 MUST_CONTAIN `bucketRows.map` (not just `bucketRows`) is tight enough — collapse-to-comment scenario cannot satisfy both phases.
- **STALE** `endOfYear` import (plan uses raw `new Date(...)`), `day_count` field conflict (no conflict), Playwright testDir recursive discovery.

### Amendments Applied (inline) to Phases

All v1.1 fixes below are surgical edits to the operative phase tables — NOT amendment-only notes. Each phase change is marked **AMENDED v1.1**.

### GO / NO-GO Gate (updated)

**Status: PLANNED_AUDITED_v1.1 — GO for autonomous execution after pre-flight checks below pass.**

**Pre-flight checks (all must be ✓ before any code change):**
- [ ] **AUDIT-1**: Phase 2.8 + Phase 4.8 + "Execution Workflow" use `npx vitest run <path>` (NOT `npm run test`)
- [ ] **AUDIT-2**: All 8 L3 scenario rows + Phase 6.1 + Test Data Seeding paragraph use `loggedInAreaSupervisor` (no "As") + `test.area@bebang.ph` (no "sup")
- [ ] **AUDIT-3**: Phase 3.3 specifies insertion in `<CardContent>` at line 1203 (badge row), NOT in `<CardHeader>`
- [ ] **AUDIT-4**: Phase 4.6 pins shadcn `Collapsible`; MUST_CONTAIN is `CollapsibleTrigger` AND `CollapsibleContent` (NOT `<details`)
- [ ] **AUDIT-5**: L3 scenarios L3-2/3/4/7 + Phase 5.2 include the explicit "click Apply button" step after preset selection
- [ ] **AUDIT-6**: Phase 2.2 uses `format(..., "RRRR-'W'II")`; Phase 2.7 adds a unit test asserting `bucketKey('2025-12-29', 'weekly') === '2026-W01'`
- [ ] **AUDIT-7**: Phase 2.5 specifies per-field aggregation: SUM for `total_precipitation` + `precipitation_hours`; MAX for `average_max_hourly_precipitation` + `max_hourly_precipitation`
- [ ] **AUDIT-8**: Phase 2.5 sets `is_weekend = (weekend_count > 0)`, `is_holiday = (holiday_count > 0)`, `is_rainy = (sum rainy > 0)`, `rain_severity = highest-severity day` on bucket rows
- [ ] **AUDIT-9**: Phase 4.1 type annotation: `useMemo<Array<SalesDashboardBucketRow & { label: string; tickLabel: string }>>`
- [ ] **AUDIT-10**: Phase 1.5 pins `useRef<boolean>(false)` for override flag
- [ ] **AUDIT-11**: Phase 4.7 quotes the actual CardDescription string from line 1199
- [ ] **AUDIT-12**: Phase 4.5 (or 4.7) updates BOTH CardTitles dynamically
- [ ] **AUDIT-13** (W-02/W-03 pinned): Phase 2.6 PINS `day_of_week` (bucket-start `format(parseISO, "EEEE")` for weekly, `"Mixed"` for monthly) and `weather_description` (`` `Mixed (${day_count} days)` `` for buckets, passthrough for daily) — no "implementer's choice" wording remains
- [ ] **AUDIT-14** (design-review W-02 pinned): Phase 3.1 PINS `bg-teal-700` (matching chart line color `#0f766e`) instead of `bg-slate-900` (no dashboard precedent)
- [ ] **AUDIT-15** (W-04 pinned): Phase 4.3 PINS `minTickGap={granularity === "daily" ? 14 : granularity === "weekly" ? 80 : 40}` — no rotation, no "e.g. 28"

### Final Cold-Start Verdict (after v1.1 amendments)

**Cold-start ready: YES.** All 5 cold-start CRITICAL guess points (C-01 to C-05) and all 6 cold-start WARNINGs (W-01 to W-06) are now pinned with explicit values. The plan can be executed by an agent with zero conversation context.

---

## Goal (one sentence)

Add a `Daily | Weekly | Monthly` segmented control to the Sales Analytics page so a year of data is readable as 12 monthly bars instead of 365 daily ones, while preserving every existing weather, holiday, and per-store drill-down behavior.

## Problem statement (cold-start ready)

### What the user sees today

Open `/dashboard/analytics/sales`, pick "Last 30 days" (or "Year to Date"), and the **Sales × Weather** chart renders one point per day. For 30 days it's busy but readable. For 90+ days it's a wall of pixels. For Year to Date (132 days as of 2026-05-11) it's unreadable — labels overlap, the curve flattens visually, the temperature line becomes noise.

The **daily detail table** below the chart renders one row per business date (1810-1851 in `app/dashboard/analytics/sales/page.tsx`). For 30+ days the user must scroll through dozens of rows to find a specific date. For a year there are 365+ rows — no usable summary view.

### What the user wants

Two specific behaviors:

1. **Date range ≥ 1 month → show weekly aggregation by default.**
   Bars/lines represent ISO-week buckets (Mon-Sun). Roughly 4-26 points instead of 30-180.
2. **Year selection → show monthly aggregation by default.**
   Bars/lines represent calendar-month buckets. 1-12 points for a 1-12 month span.

User must be able to **override** the default (e.g. force daily while looking at a 60-day range to drill into a specific spike, or force weekly on a 14-day range for parity with a weekly board pack).

### Why this matters operationally

- BEI leadership reviews use Year-to-Date and prior-year ranges; daily 365-point charts produce no insight at that span.
- The Sales × Weather chart needs to remain useful at weekly/monthly grain — temperature anomalies and rain effects DO matter at week level, just averaged.
- The per-day weather and calendar signals (Weekend, Holiday, Disruptive rain badges) should aggregate visibly into per-week / per-month counts so the bucket still tells the story (e.g., "Week 18 contained 1 holiday + 2 disruptive rain days").

### What is in scope

- Frontend-only change in `bei-tasks` repo.
- Aggregation of `dailyRows` (already returned by `/api/analytics/sales/overview`) into weekly/monthly buckets in client memory (in a new helper module `app/dashboard/analytics/sales/_aggregation.ts`).
- New segmented control in the Sales × Weather card header (3 toggle buttons).
- URL state persistence (`granularity=daily|weekly|monthly`).
- Auto-default selection based on the active date range span.
- Two new DateRangePicker presets: `This Year` and `Last Year` (so year-selection is a one-click action).
- Daily-detail table at the bottom of the page mirrors the same granularity (with a separate `Show daily breakdown` toggle to keep the per-day drill-down available).
- Driver Snapshot tile aggregates similarly (weather summaries reflect the bucket span, not just a single day).

### What is NOT in scope

- No backend changes to `hrms/api/sales_dashboard.py`. The existing `_aggregate_daily_series()` continues returning daily rows; the client aggregates.
- No new Frappe `@frappe.whitelist()` endpoints.
- No Supabase schema or materialized view changes.
- No changes to the `StoreDetailDialog` (`store-detail-dialog.tsx`) or the per-store leaderboard page (`/dashboard/analytics/sales/stores`). Those follow up in a separate sprint if user wants them.
- No changes to the Sales Analytics access-context, channel-mix, weather-context, store-rankings, or product-mix endpoints.
- No new Sentry instrumentation (this PR touches no whitelisted endpoints; existing Next.js auto-instrumentation continues).
- No backend granularity API (e.g. `?granularity=monthly`). Reserved for a v2 follow-up if 365-row payload size becomes a concern.

## Design Rationale (For Cold-Start Agents)

### Why this exists

S176 (DateRangePicker dual-calendar) gave operators a clean way to pick big ranges. S182 (formatters + dialog + leaderboard) made daily numbers consistent across surfaces. S185/S191 fixed channel-split accuracy. None of these addressed **what to render** when the daily series has 30-365 points. The result is that operators with a Year-to-Date pick get a chart they can't actually read.

This sprint closes that gap with the smallest possible surface change — purely client-side aggregation behind a segmented control. The backend already returns the data we need; the chart just needs to be told "bucket it by week" or "bucket it by month."

### Why frontend-only aggregation (not backend)

Considered: add `?granularity=daily|weekly|monthly` to `/api/analytics/sales/overview` and have Frappe `_aggregate_daily_series()` group by `DATE_TRUNC('week'|'month', business_date)`. **Rejected for v1.**

Trade-offs:

| Approach | Pro | Con |
|---|---|---|
| **Frontend-only (chosen)** | No backend deploy; instant toggle (no re-fetch); 365 daily rows is ~200KB JSON, trivial; weather/calendar context already loaded; shared logic with daily-detail table | Larger initial payload for year-span requests; aggregation runs in browser |
| Backend granularity | Smaller payload (12 monthly rows vs 365 daily); SQL is the canonical aggregation source | Two code paths (daily vs week/month); changes existing endpoint signature; toggle requires re-fetch; weather context needs separate aggregation logic on backend; ships slower (deploy coordination) |

For BEI's data volume (≤50 stores × ≤365 days = ~18K row max before client filter), client aggregation is fast (<10ms). The Recharts `<ComposedChart>` handles 12-26 points trivially. Re-rendering on toggle is instant. Backend granularity stays as a follow-up if a future analytics view needs to scan >2 years or roll up 100+ stores.

### Why ISO-weeks (Mon-Sun), not Sun-Sat

Two valid options for "weekly":

| Option | Pro | Con |
|---|---|---|
| **ISO week (Mon-Sun, week starts Monday) — CHOSEN** | Matches Philippine business convention; aligns with payroll cutoff which is also Mon-based; `date-fns` `getISOWeek()` is the standard | None |
| Sun-Sat (US default) | Aligns with US calendar widgets | Doesn't match BEI's payroll/scheduling cadence |

The `DateRangePicker`'s existing `react-day-picker` widget defaults to Sun-Sat for visual calendar display, but the **bucketing** for aggregation is independent of the picker visual. We use `date-fns`'s `startOfISOWeek()` and `endOfISOWeek()` for bucketing.

### Why "monthly" = calendar month (not 30-day rolling)

Calendar month aligns with BIR reporting periods, payroll cycles, and the BEI leadership monthly review cadence. Rolling 30-day windows would confuse comparisons with finance reports. Bucket = `format(date, 'yyyy-MM')`.

### Why auto-default to weekly at 30 days (not 14 or 60)

Tested thresholds against operator readability:

| Range span | Daily points | Weekly buckets | Monthly buckets | Recommended default |
|---|---:|---:|---:|---|
| 1-13 days | 1-13 | 1-3 | 1 | **Daily** (weekly/monthly hide low-info bars) |
| 14-29 days | 14-29 | 3-5 | 1-2 | **Daily** (still readable; weekly available but not default) |
| 30-89 days | 30-89 | 5-13 | 2-4 | **Weekly** (daily too dense, weekly is the sweet spot) |
| 90-179 days | 90-179 | 13-26 | 4-7 | **Weekly** (monthly available, weekly still rich) |
| 180+ days | 180+ | 26+ | 7+ | **Monthly** (weekly approaching density limit; monthly is cleaner) |
| Exactly 1 calendar year | ~365 | 52 | 12 | **Monthly** |

Cutoffs:

- `< 30 days` → Daily default
- `30 to 179 days` → Weekly default
- `>= 180 days` → Monthly default

User can always override.

### Why a 3-button segmented control (not Select dropdown or Tabs)

Three options. Segmented control gives the user a one-glance view of the current state and one click to switch. Existing component primitive: shadcn `Tabs` works but visually reads "tab-like" (suggests separate content panels). A custom segmented control built with three `Button` elements styled as a connected group is cleaner. We model on the existing `storeFilterOpen` toggle pattern (line ~400 in page.tsx) but as a 3-way.

### Why also add "This Year" and "Last Year" presets

User's request "select a year" implies a one-click year-pick. Current presets stop at "Year to Date" (which is partial-year, not full-year). Adding `This Year` (Jan 1 of current year → today) and `Last Year` (Jan 1 → Dec 31 of last year) handles the "I want monthly view of 2026 / 2025" intent without forcing the user to manually pick Jan 1 and Dec 31 from the calendar.

### Why keep the daily detail table — and how it aggregates

The daily-detail table (lines 1810-1851 in `page.tsx`) is the per-day drill-down. Removing it for weekly/monthly views would lose drill-down. Two valid approaches:

| Approach | Pro | Con |
|---|---|---|
| **Aggregate the table to match the toggle, with a `Show daily breakdown` collapsible — CHOSEN** | Consistent with the chart; user can expand to see daily within any bucket | Slightly more layout complexity |
| Always render daily table regardless of toggle | Drill-down always one scroll away | 365 rows below a 12-bar chart is dissonant |

The aggregated table mirrors the chart's bucket. Each row shows:
- Bucket label (`Week 18 (Apr 28 – May 4)` or `May 2026`)
- Net sales w/o VAT (sum over bucket)
- Transactions (sum)
- Cups (sum)
- App max temp (avg)
- Temp vs 28D (avg)
- Rain (sum mm)
- Pickup share (computed from summed pickup/delivery)
- Signals (counts: "3 weekends, 1 holiday, 2 disruptive-rain days")

Below the aggregated table, a collapsible `▸ Show daily breakdown` exposes the original per-day table when the user wants the drill-down. Default collapsed when granularity != daily.

### Why URL state persistence

URL `granularity=weekly` lets the user share a link that opens the chart in the same view. Matches existing `start_date`, `end_date`, `stores`, `store_selection_mode` pattern (line 449-472).

### Why no backend changes

The existing API returns ALL daily rows for the selected range. The new aggregation function reads `bundle.weather.daily`, groups by ISO week or calendar month, and produces the same row shape with bucket labels. The chart's existing rendering, tooltip, dot-coloring, and legend continue to work unchanged (they just receive 12 or 26 rows instead of 365). The driver snapshot computes its weather/calendar averages from the same source. No type changes to `SalesDashboardDailyRow`.

### Source references

- Sales Analytics page: `bei-tasks/app/dashboard/analytics/sales/page.tsx` (1885 lines)
  - Chart at lines 1222-1315
  - Daily detail table at lines 1779-1856
  - Driver snapshot at lines 1328 onwards
  - URL state useEffect at lines 449-472
- DateRangePicker: `bei-tasks/components/reports/date-range-picker.tsx` (presets at line 87-145)
- Frontend API caller: `bei-tasks/lib/api/sales-dashboard.ts` (fetchSalesOverview line 50)
- Type defs: `bei-tasks/lib/sales-dashboard.ts` (SalesDashboardDailyRow line 156-200)
- Next.js API route forwarder: `bei-tasks/app/api/analytics/sales/[endpoint]/route.ts`
- Backend (UNTOUCHED, read-only reference): `hrms/api/sales_dashboard.py` `_aggregate_daily_series()` at line 2359-2540ish
- Existing `discount-abuse` `period_granularity` field type pattern: `bei-tasks/hooks/use-discount-abuse.ts:367` (`"day" | "month" | "range"`) — semantically similar but a tag, not a true aggregation toggle

## Requirements Regression Checklist

Before any code change, the executing agent must confirm each yes/no:

- [ ] Is the granularity state a 3-value enum (`"daily" | "weekly" | "monthly"`)? Not a boolean. Not a Select with 4+ options.
- [ ] Are auto-default thresholds set to: `<30d → daily`, `30-179d → weekly`, `>=180d → monthly`?
- [ ] Is the URL parameter named `granularity` and persisted via the existing `router.replace` block at lines 449-472?
- [ ] Does the URL param round-trip cleanly: open `?granularity=monthly` → state initializes to monthly → toggle to weekly → URL updates to `granularity=weekly`?
- [ ] Does the segmented control allow the user to override the auto-default at any range size? (i.e. user can pick Weekly on a 14-day range or Daily on a 365-day range — UI should NOT hide options, only choose defaults.)
- [ ] Are weekly buckets ISO-week (Mon-Sun, `date-fns` `startOfISOWeek`)? Not Sun-Sat.
- [ ] Are monthly buckets calendar month (`format(date, 'yyyy-MM')`)? Not 30-day rolling.
- [ ] Does the chart's `chartRows` `useMemo` depend on `[dailyRows, granularity]`?
- [ ] Does the daily-detail table aggregate to match the toggle when granularity != daily? (Not "stays daily regardless.")
- [ ] Is the `Show daily breakdown` collapsible present and default-collapsed when granularity != daily?
- [ ] Do `This Year` and `Last Year` presets appear in the DateRangePicker `PRESETS` array AFTER `Year to Date`?
- [ ] Does selecting `This Year` or `Last Year` auto-default granularity to monthly?
- [ ] Are weather aggregations: avg for temperature fields, sum for precipitation, counts for signals (is_weekend, is_holiday, disruptive_rain_store_count)?
- [ ] Are bucket labels human-readable: weekly = `Week 18 (Apr 28 – May 4)`, monthly = `May 2026`?
- [ ] Does the existing Sales × Weather chart's tooltip continue to render correctly with the new aggregated data?
- [ ] Is there ZERO change to `hrms/api/sales_dashboard.py`?
- [ ] Is there ZERO change to the Next.js API route handler at `app/api/analytics/sales/[endpoint]/route.ts`?
- [ ] Is the canonical structure verifier untouched? (canonical_scope: none — should be a no-op anyway.)
- [ ] Does the build pass `npm run build` in `bei-tasks` with zero new TypeScript errors?
- [ ] Does `npm run lint` pass with zero new warnings?

## Duplication Audit

Files searched for prior work in this domain:

| Search | Result | Classification |
|---|---|---|
| `grep -rn "granularity\|aggregate.*period\|weekly\|monthly" bei-tasks/app/dashboard/analytics/sales/` | No granularity toggle on Sales Analytics; existing `dailyRows` rendering only | **[BUILD]** new aggregation module + UI control |
| `grep -rn "period_granularity\|granularity" bei-tasks/hooks/` | `hooks/use-discount-abuse.ts:367` uses `period_granularity: "day" \| "month" \| "range"` as a TAG (server-supplied), not a true client aggregation toggle | **[BUILD]** different concern; do not reuse |
| `grep -rn "ToggleGroup\|SegmentedControl" bei-tasks/components/ui/` | Not installed. shadcn `Tabs` exists, `Select` exists. | **[BUILD]** new minimal segmented control with three `<Button>` elements styled as a group — do not pull a new shadcn primitive for a 3-button surface |
| `grep -n "This Year\|Last Year" bei-tasks/components/reports/date-range-picker.tsx` | Not present. Has `Year to Date` only. | **[EXTEND]** add two new presets to existing PRESETS array |
| `grep -rn "startOfISOWeek\|getISOWeek" bei-tasks/` | Not used. `date-fns` is in deps. | **[BUILD]** import from `date-fns` |
| `grep -rn "/dashboard/analytics/sales" bei-tasks/app/` | One page (`sales/page.tsx`), one dialog (`store-detail-dialog.tsx`), one stores subroute (`sales/stores/`) | StoreDetailDialog + leaderboard are **OUT OF SCOPE** for v1 |

No EXTEND/SKIP candidates beyond the two presets. Everything else is [BUILD].

## Surface Inventory (what changes, owned by this sprint)

| Surface | Change | Owner |
|---|---|---|
| `bei-tasks/app/dashboard/analytics/sales/page.tsx` | Add granularity state + URL param + chart/table/snapshot data wiring + segmented control component placement | This sprint (exclusive) |
| `bei-tasks/app/dashboard/analytics/sales/_aggregation.ts` | **NEW** — pure aggregation helpers: `bucketKey`, `bucketLabel`, `aggregateRows(dailyRows, granularity)` returning the same SalesDashboardDailyRow shape per bucket | This sprint (exclusive) |
| `bei-tasks/app/dashboard/analytics/sales/_aggregation.test.ts` | **NEW** — unit tests covering daily passthrough, weekly grouping, monthly grouping, weather averaging, signal counts, empty input | This sprint (exclusive) |
| `bei-tasks/components/reports/date-range-picker.tsx` | Add `This Year` and `Last Year` presets to PRESETS array. NO change to props API. | This sprint (exclusive) |
| `bei-tasks/components/analytics/granularity-toggle.tsx` | **NEW** — small 3-button segmented control component (controlled `<button>` group, no external dependency) | This sprint (exclusive) |
| `bei-tasks/lib/sales-dashboard.ts` | Add `SalesGranularity` type (`"daily" \| "weekly" \| "monthly"`) and `SalesDashboardBucketRow` type (extends SalesDashboardDailyRow with `bucket_label`, `bucket_start_date`, `bucket_end_date`, `day_count`, `weekend_count`, `holiday_count`, `disruptive_rain_day_count`) | This sprint (exclusive) |

## What stays untouched (protected surfaces)

- `hrms/api/sales_dashboard.py` — backend logic. NO TOUCH.
- `bei-tasks/app/api/analytics/sales/[endpoint]/route.ts` — Next.js API forwarder. NO TOUCH.
- `bei-tasks/app/dashboard/analytics/sales/store-detail-dialog.tsx` — store detail modal. NO TOUCH (still renders daily; future sprint can extend).
- `bei-tasks/app/dashboard/analytics/sales/stores/` — leaderboard subroute. NO TOUCH.
- `bei-tasks/app/dashboard/analytics/sales/_formatters.ts` — formatters extracted in S182. READ-ONLY consumer.
- `bei-tasks/lib/api/sales-dashboard.ts` — fetch wrapper. NO TOUCH.
- All other `bei-tasks/app/dashboard/analytics/*` (area, finance, manpower, operations, product, store). NO TOUCH.
- Sentry instrumentation contracts — no new whitelisted endpoints touched, so no Sentry tasks.

## Anti-Rewind / Concurrent-Run Protection Contract

```yaml
ownership_matrix:
  rule: one owner per file-glob family; no overlap with adjacent sprints
  exclusive_files:
    - bei-tasks/app/dashboard/analytics/sales/page.tsx
    - bei-tasks/app/dashboard/analytics/sales/_aggregation.ts          # NEW
    - bei-tasks/app/dashboard/analytics/sales/_aggregation.test.ts     # NEW
    - bei-tasks/components/reports/date-range-picker.tsx
    - bei-tasks/components/analytics/granularity-toggle.tsx            # NEW
    - bei-tasks/lib/sales-dashboard.ts                                  # types only

protected_surfaces:
  - hrms/api/sales_dashboard.py                                         # backend
  - bei-tasks/app/api/analytics/sales/[endpoint]/route.ts               # API forwarder
  - bei-tasks/app/dashboard/analytics/sales/store-detail-dialog.tsx
  - bei-tasks/app/dashboard/analytics/sales/stores/                     # leaderboard
  - bei-tasks/app/dashboard/analytics/sales/_formatters.ts
  - bei-tasks/lib/api/sales-dashboard.ts
  - bei-tasks/components/ui/                                            # shadcn primitives — do not add new ones
  - All other bei-tasks/app/dashboard/analytics/* routes

remote_truth_baseline:
  repo: bei-tasks
  release_branch: main
  release_head_sha_at_plan_authoring: <captured by Phase 0>
  live_evidence_basis:
    - production deploy of bei-tasks main as of 2026-05-11 PHT
    - PR #737 (S242) already merged to hrms production; backend daily series unchanged

active_run_coordination:
  artifact: output/s245/state/active_run.json
  rule: claim on Phase 0 boot, release on closeout

pretouch_backup:
  not_applicable: |
    No destructive operations. Pure frontend code changes; git history is the
    backup. Aggregation is read-only over the API response.

supersession_map:
  rule: |
    This sprint introduces a NEW UI capability. It does not supersede any
    existing route, endpoint, or evidence. The daily detail table remains
    available via the `Show daily breakdown` collapsible.

touch_preservation:
  rule: |
    No cleanup work involved. No files deleted. Closeout removes only the
    disposable worktree per the worktree-isolation rule.
```

## Phase Budget Contract

| Phase | Description | Estimated work units |
|---|---|---:|
| Phase 0 | Worktree boot + baseline screenshots + commit-state probe | 3 |
| Phase 1 | Types + URL state + auto-default logic | 8 |
| Phase 2 | Aggregation module + unit tests | 12 |
| Phase 3 | Segmented control component + integration in chart card | 8 |
| Phase 4 | Wire chart + driver snapshot + daily-detail table to granularity | 10 |
| Phase 5 | Add `This Year` + `Last Year` presets + auto-granularity on preset click | 4 |
| Phase 6 | L3 Playwright verification + visual regression screenshots | 8 |
| Phase 7 | Closeout (PR + registry + plan status + worktree removal) | 4 |
| **Total** | | **57** |

Hard ceiling per S089: 80 units. Within budget. No phase exceeds 12.

## Ground-Truth Lock

```yaml
evidence_sources:
  - bei-tasks/app/dashboard/analytics/sales/page.tsx               -> baseline UI + render paths
  - bei-tasks/components/reports/date-range-picker.tsx             -> current preset list (8 entries)
  - bei-tasks/lib/sales-dashboard.ts                               -> SalesDashboardDailyRow shape (lines 156-200)
  - bei-tasks/app/api/analytics/sales/[endpoint]/route.ts          -> API forwarder (no granularity param today)
  - hrms/api/sales_dashboard.py:_aggregate_daily_series (line 2359) -> backend continues returning daily rows
  - production deploy: my.bebang.ph live as of 2026-05-11           -> baseline interactive evidence

count_method:
  metric: dailyRows length for known ranges
  basis: |
    For a single-store, single-channel query:
    - "Last 7 days" -> 7 daily rows
    - "Last 30 days" -> 30 daily rows
    - "Year to Date" (2026-01-01 to 2026-05-11) -> 131 daily rows
    - "Last Year" (2025-01-01 to 2025-12-31) -> 365 daily rows
    Verified by opening /dashboard/analytics/sales and counting points in
    the rendered chart for each preset before Phase 0 begins.

authoritative_sections:
  - "## Problem statement", "## Phase 1...7" are authoritative for execution.
  - Audit history (if any) is traceability only.

unresolved_value_policy:
  - No unresolved values. All file paths verified to exist by Phase 0 read.
```

## Worktree Boot (Phase 0)

```bash
# Reserved branch from frontmatter
BR=s245-analytics-sales-granularity-toggle
WT=F:/Dropbox/Projects/bei-tasks-${BR##*/}

# Spawn isolated worktree off origin/main (bei-tasks default branch)
cd F:/Dropbox/Projects/bei-tasks && git fetch origin --prune
git worktree add "$WT" -B "$BR" origin/main
cd "$WT"

# Capture baseline SHA for Anti-Rewind contract
git rev-parse origin/main > output/s245/state/baseline_sha.txt
mkdir -p output/s245/verification/before_after_screenshots
mkdir -p output/s245/state tmp/s245
```

## Phase 0 — Boot + baseline capture (3 units)

| Task | Description | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 0.1 | Read this plan fully. Read `bei-tasks/app/dashboard/analytics/sales/page.tsx` (full file; especially lines 1-150 imports/types, 380-475 state+URL, 583-690 dailyRows + chartRows, 1130-1315 chart card, 1779-1856 daily-detail table). Read `bei-tasks/components/reports/date-range-picker.tsx` fully. Read `bei-tasks/lib/sales-dashboard.ts` lines 115-200. | n/a (read only) |
| 0.2 | Spawn the worktree per "Worktree Boot" above. CWD must change to `$WT`. Verify `git status` shows clean and HEAD is `origin/main`. | MUST_MODIFY: `output/s245/state/baseline_sha.txt` |
| 0.3 | Run `npm install` in the worktree to populate `node_modules`. Then `npm run lint` and `npm run build` to confirm a clean baseline. If baseline build fails, STOP — branch is not clean off main. | MUST_MODIFY: `tmp/s245/build_baseline.log` (capture full output). MUST_CONTAIN: "Compiled successfully" OR "build completed" (depending on Next.js version output) |
| 0.4 | Open the production Sales Analytics page via the local dev server (`npm run dev` in background) and capture 4 baseline screenshots: Last 7 days, Last 30 days, Year to Date (or Last 90 days if YTD is too short on test data), Custom 6-month range. Save to `output/s245/verification/before_after_screenshots/before_*.png`. (If local dev cannot reach Frappe API, capture from production my.bebang.ph instead — note the source in the filename.) | MUST_MODIFY: 4 PNG files under `output/s245/verification/before_after_screenshots/` |
| 0.5 | Write `output/s245/state/active_run.json` claiming ownership. | MUST_MODIFY: `output/s245/state/active_run.json` |

## Phase 1 — Types + URL state + auto-default logic (8 units)

| Task | Description | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 1.1 | In `bei-tasks/lib/sales-dashboard.ts`, add `export type SalesGranularity = "daily" \| "weekly" \| "monthly";` near the other top-level types. Add `export interface SalesDashboardBucketRow extends SalesDashboardDailyRow { bucket_key: string; bucket_label: string; bucket_start_date: string; bucket_end_date: string; day_count: number; weekend_count: number; holiday_count: number; disruptive_rain_day_count: number; }` | MUST_MODIFY: `bei-tasks/lib/sales-dashboard.ts`. MUST_CONTAIN: `export type SalesGranularity` AND `export interface SalesDashboardBucketRow` |
| 1.2 | In `bei-tasks/app/dashboard/analytics/sales/page.tsx`, add `function autoDefaultGranularity(startDate: string, endDate: string): SalesGranularity` near `defaultRange()` (around line 116). Returns `"daily"` if span < 30 days, `"weekly"` if 30-179 days, `"monthly"` if >=180 days. Span computation uses `(endDate - startDate)` in days, inclusive. | MUST_CONTAIN in `page.tsx`: `function autoDefaultGranularity` AND constant thresholds `30` AND `180` |
| 1.3 | Add a `parseGranularity(value: string \| null, fallback: SalesGranularity): SalesGranularity` helper that validates `?granularity=` URL param. Invalid values fall back to fallback. | MUST_CONTAIN in `page.tsx`: `function parseGranularity` |
| 1.4 | In the `SalesDashboardPage()` component (around line 386), add `const [granularity, setGranularity] = useState<SalesGranularity>(...)` initialized via `parseGranularity(searchParams.get("granularity"), autoDefaultGranularity(startDate, endDate))`. | MUST_CONTAIN: `const [granularity, setGranularity] = useState<SalesGranularity>` |
| 1.5 | **AMENDED v1.1 (NCV-6):** Add a `useEffect` that re-computes auto-default whenever `startDate` or `endDate` changes — BUT only if the URL did NOT specify a granularity AND the user has not manually overridden. **HARD BLOCKER (NCV-6):** Track override state via `const granularityOverrideRef = useRef<boolean>(false)`. Do NOT use `useState` for this flag — `useState` flip triggers a re-render that re-fires this useEffect before state settles, causing a transient granularity reset. The ref flips `true` inside the segmented control's `onChange` handler. | MUST_CONTAIN: `useRef<boolean>(false)` AND a `useEffect` with `[startDate, endDate` in deps AND a check that respects manual override |
| 1.6 | Extend the existing URL-state `useEffect` (line 449-472) to also set/delete the `granularity` URL param. Rule: if granularity equals the auto-default for the current range, DELETE the param (clean URL); if it differs, SET it. | MUST_CONTAIN in the URL-state useEffect block: `params.set("granularity"` AND `params.delete("granularity"` |
| 1.7 | Build + lint to confirm no TS errors. Capture output to `tmp/s245/build_phase1.log`. | MUST_MODIFY: `tmp/s245/build_phase1.log`. MUST_CONTAIN: zero `error TS` lines |

## Phase 2 — Aggregation module + unit tests (12 units)

| Task | Description | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 2.1 | Create `bei-tasks/app/dashboard/analytics/sales/_aggregation.ts`. Pure module, no React imports. Imports: `date-fns` (`startOfISOWeek`, `endOfISOWeek`, `getISOWeek`, `format`, `parseISO`, `differenceInCalendarDays`). | MUST_MODIFY: `bei-tasks/app/dashboard/analytics/sales/_aggregation.ts`. MUST_CONTAIN: `from "date-fns"` AND `startOfISOWeek` AND `format` |
| 2.2 | **AMENDED v1.1 (B9):** Export `function bucketKey(businessDate: string, granularity: SalesGranularity): string`. Daily → returns the date unchanged (`yyyy-MM-dd`). Weekly → returns `format(startOfISOWeek(parseISO(businessDate)), "RRRR-'W'II")` — **HARD BLOCKER: use `RRRR` (ISO week-year) and `II` (zero-padded ISO week), NOT `yyyy` (calendar year) or `WW`.** With `date-fns@^4.1.0`, calendar-year tokens produce wrong bucket keys at year boundaries: 2025-12-29 (Monday) is ISO Week 2026-W01 but `format(date, "yyyy-'W'WW")` returns `"2025-W01"`. The plan's "Last Year" preset (Jan 1 → Dec 31) guarantees this scenario will arise. Monthly → returns `format(parseISO(businessDate), "yyyy-MM")` (calendar year + month is correct for monthly). | MUST_CONTAIN: `export function bucketKey` AND `"RRRR-'W'II"` AND `startOfISOWeek` |
| 2.3 | Export `function bucketLabel(bucketKey: string, granularity: SalesGranularity): string`. Daily → `formatDayLabel` (reuse existing formatter). Weekly → `Week WW (MMM d – MMM d)` using `startOfISOWeek`/`endOfISOWeek`. Monthly → `MMM yyyy`. | MUST_CONTAIN: `export function bucketLabel` |
| 2.4 | Export `function bucketRange(bucketKey: string, granularity: SalesGranularity): { start: Date; end: Date }`. | MUST_CONTAIN: `export function bucketRange` |
| 2.5 | **AMENDED v1.1 (B4, B8):** Export `function aggregateRows(rows: SalesDashboardDailyRow[], granularity: SalesGranularity): SalesDashboardBucketRow[]`. Implementation:<br><br>If `granularity === "daily"`: return rows mapped to BucketRow shape (each row IS its own bucket: `day_count=1`, `weekend_count = is_weekend ? 1 : 0`, `holiday_count = is_holiday ? 1 : 0`, `disruptive_rain_day_count = rain_severity === "disruptive_rain" ? 1 : 0`). Preserve the original boolean fields unchanged.<br><br>If `granularity === "weekly"|"monthly"`: group rows by `bucketKey`, then per field:<br>- **SUM**: `gross_sales`, `net_sales_with_vat`, `net_sales_without_vat`, `pickup_sales_without_vat`, `delivery_sales_without_vat`, `cups_sold`, `transactions`, `total_precipitation`, `precipitation_hours` (cumulative metrics)<br>- **AVG (skip null)**: `avg_temperature`, `max_temperature`, `min_temperature`, `apparent_temperature_max`, `avg_wind_speed`, `max_wind_speed`, `temperature_anomaly_vs_28d`<br>- **HARD BLOCKER (B8) — MAX (not SUM)**: `average_max_hourly_precipitation`, `max_hourly_precipitation` — these are peak-intensity metrics; summing per-day store-averaged peaks across a week is semantically wrong. Backend (`hrms/api/sales_dashboard.py:2459-2470`) already stores these as per-day store averages.<br>- **COUNT**: `day_count` = rows in bucket, `weekend_count` = sum of `is_weekend`, `holiday_count` = sum of `is_holiday`, `disruptive_rain_day_count` = count of rows where `rain_severity === "disruptive_rain"`.<br>- **HARD BLOCKER (B4) — boolean compatibility for `SalesWeatherTick`**: set `is_weekend = (weekend_count > 0)`, `is_holiday = (holiday_count > 0)`, `is_rainy = rows.some(r => r.is_rainy)`, `rain_severity` = highest-severity day's value using priority `disruptive_rain` > `wet` > `passing_showers` > else. This keeps `page.tsx:190-207` `SalesWeatherTick` rendering indicators correctly without modification.<br>- **RECOMPUTE**: `average_guest_check = gross_sales / transactions if transactions > 0 else 0`; `cups_per_transaction = cups_sold / transactions if transactions > 0 else 0`. | MUST_CONTAIN: `export function aggregateRows` AND `weekend_count` AND `disruptive_rain_day_count` AND `Math.max` (for the MAX aggregation) AND `is_weekend: weekend_count > 0` AND `rain_severity` (verifies the severity propagation logic exists) |
| 2.6 | **AMENDED v1.1 (W-02, W-03):** Critical edge cases in aggregateRows: (a) empty input returns empty array. (b) `null`/`undefined` weather fields are skipped from the avg (don't poison with NaN). (c) **PINNED**: `day_of_week` for weekly buckets = the bucket's start date's day name via `format(parseISO(bucket_start_date), "EEEE")` → `"Monday"`. For monthly buckets = `"Mixed"`. (d) See Phase 2.5 amendment — `is_weekend`/`is_holiday`/`is_rainy` are set via the compat shim (`weekend_count > 0`, `holiday_count > 0`, `rows.some(r => r.is_rainy)`). (e) **PINNED**: `weather_description` for buckets = `` `Mixed (${day_count} days)` `` for weekly/monthly. Simple template; do NOT compute mode/most-frequent (over-engineering). For daily granularity, pass through the input row's `weather_description` unchanged. (f) `holiday_name` becomes a `;`-joined list of any holidays in the bucket (empty string if none — NOT `null`). | MUST_CONTAIN: handling for null/undefined weather values AND `format(parseISO` (for day_of_week) AND `Mixed (${` (for weather_description) |
| 2.7 | **AMENDED v1.1 (B9):** Create `bei-tasks/app/dashboard/analytics/sales/_aggregation.test.ts` with Vitest (Vitest 4.0.15 is already installed in `bei-tasks/package.json` line 92; `vitest.config.ts` exists). Cover: (a) daily passthrough preserves all 7 input rows → 7 BucketRows. (b) 14 daily rows → 2 or 3 weekly buckets depending on which weekday rows start. (c) 30 daily rows → 1-2 monthly buckets. (d) empty input → empty output for all 3 granularities. (e) `gross_sales` sum equals sum of input `gross_sales` (no double-count). (f) `avg_temperature` ignores null entries. (g) `weekend_count` equals number of input rows where `is_weekend=true`. (h) **HARD BLOCKER (B9) — ISO week year boundary**: `bucketKey('2025-12-29', 'weekly') === '2026-W01'` (NOT `'2025-W01'`). (i) Peak-intensity metrics: feed 7 rows with `max_hourly_precipitation = [1,2,3,4,5,6,7]`; bucket's `max_hourly_precipitation === 7` (MAX, not SUM=28). (j) Boolean compatibility: 7 rows with `is_weekend = [F,F,F,F,F,T,T]`, bucket's `is_weekend === true` AND `weekend_count === 2`. | MUST_MODIFY: `bei-tasks/app/dashboard/analytics/sales/_aggregation.test.ts`. MUST_CONTAIN: `describe(` AND `aggregateRows` AND `'2026-W01'` AND `max_hourly_precipitation` AND at least 10 `it(` / `test(` blocks |
| 2.8 | **AMENDED v1.1 (B1):** Run the new tests: `npx vitest run app/dashboard/analytics/sales/_aggregation.test.ts`. **HARD BLOCKER (B1)**: do NOT use `npm run test` — `bei-tasks/package.json` has no `test` script (only `dev`, `build`, `start`, `lint`, `audit:erpnext-notify`). Do NOT use `npx vitest run` without a path argument — there are 3 pre-existing failing tests in other modules (`tests/unit/api/pcf-normalizers.test.ts`, `tests/unit/hr/s026-l05-hr-routing.test.ts`, `tests/unit/navigation/navigation-personas.test.ts`) that will produce false-positive blockers. Scope strictly to the new test file. All tests must PASS. Capture to `tmp/s245/aggregation_tests.log`. | MUST_MODIFY: `tmp/s245/aggregation_tests.log`. MUST_CONTAIN: `npx vitest run` AND zero failing tests in the output |

## Phase 3 — Segmented control component + integration in chart card (8 units)

| Task | Description | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 3.1 | **AMENDED v1.1 (design-review W-02):** Create `bei-tasks/components/analytics/granularity-toggle.tsx`. Component: `GranularityToggle({ value, onChange, disabledOptions = [] }: { value: SalesGranularity; onChange: (g: SalesGranularity) => void; disabledOptions?: SalesGranularity[]; })`. Renders three connected `<button type="button">` elements styled with shadcn-like classes (border, background swaps for active state, rounded-l on first, rounded-r on last, no rounded middle). **PINNED** active button color: `bg-teal-700 text-white hover:bg-teal-800` — matches the existing chart `net_sales_without_vat` line color (`#0f766e` = `teal-700` per Tailwind palette) used in `page.tsx:1217`. Idle button: `bg-white text-slate-700 hover:bg-slate-50`. Borders: `border border-slate-200`. Disabled buttons: `opacity-50 cursor-not-allowed`. Do NOT use `bg-slate-900` — has no precedent in the dashboard palette. | MUST_MODIFY: `bei-tasks/components/analytics/granularity-toggle.tsx`. MUST_CONTAIN: `value: SalesGranularity` AND three button labels: `Daily` AND `Weekly` AND `Monthly` AND `bg-teal-700` |
| 3.2 | The component must NOT disable any option based on range size by default. The PARENT decides what (if anything) is disabled. (This keeps the component pure and lets the parent enforce policy.) | MUST_CONTAIN: prop `disabledOptions` is optional with default `[]` |
| 3.3 | **AMENDED v1.1 (B3):** In `page.tsx`, import the new component. **HARD BLOCKER (B3)**: the Weekend/Holiday/Disruptive-rain badge row is in `<CardContent>` at lines 1203-1213, NOT in `<CardHeader>` (which closes at line 1201). Insert the GranularityToggle as the LAST child of the badge `<div>` at line 1203. Change the badge `<div>` from `<div className="flex flex-wrap gap-2">` (line 1203) to `<div className="flex flex-wrap items-center gap-2 justify-between">` so badges stay left-aligned and the toggle floats right. Do NOT insert in `<CardHeader>`. | MUST_CONTAIN in `page.tsx`: `<GranularityToggle` AND `value={granularity}` AND `onChange={` AND `justify-between` (the modified flex class on the badge row) |
| 3.4 | When the user clicks the toggle, immediately set `userOverrodeGranularity = true` so the range-change auto-default does not re-clobber the user's pick. | MUST_CONTAIN: an `onChange` wrapper that sets the override flag |
| 3.5 | Add a small textual hint near the toggle: when the current granularity is the auto-default for the range, show muted text `Auto`; when overridden, show `Override` with a small "Reset to auto" button. | MUST_CONTAIN: `Auto` AND `Reset to auto` |
| 3.6 | Build + lint. Capture to `tmp/s245/build_phase3.log`. | MUST_MODIFY: `tmp/s245/build_phase3.log`. MUST_CONTAIN: zero `error TS` lines |

## Phase 4 — Wire chart + driver snapshot + daily-detail table (10 units)

| Task | Description | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 4.1 | **AMENDED v1.1 (B5):** In `page.tsx`, replace the `chartRows` `useMemo` (line 684-692) so it depends on `[dailyRows, granularity]`. Logic:<br><br>```typescript<br>const bucketRows = useMemo(<br>  () => aggregateRows(dailyRows, granularity),<br>  [dailyRows, granularity]<br>);<br>const chartRows = useMemo<Array<SalesDashboardBucketRow & { label: string; tickLabel: string }>>(<br>  () => bucketRows.map(row => ({<br>    ...row,<br>    label: row.bucket_label,<br>    tickLabel: row.bucket_label,<br>    business_date: row.bucket_start_date,<br>  })),<br>  [bucketRows]<br>);<br>```<br><br>**HARD BLOCKER (B5)**: update the `useMemo` type annotation from `useMemo<SalesWeatherChartRow[]>` to `useMemo<Array<SalesDashboardBucketRow & { label: string; tickLabel: string }>>` (the local interface `SalesWeatherChartRow` at line 95-98 no longer accurately describes the bucket-row shape). | MUST_CONTAIN in `page.tsx`: `const bucketRows = useMemo` AND `aggregateRows(dailyRows, granularity)` AND `SalesDashboardBucketRow & { label: string; tickLabel: string }` |
| 4.2 | **AMENDED v1.1 (B4):** Update the chart's per-row dot color logic (line 1298-1313) to respect bucket-level signal counts: if a bucket has any holiday → amber dot; any disruptive_rain → teal; any weekend day → sky-blue; else default. Daily granularity preserves the existing 1-day-per-dot semantics. **NOTE on `SalesWeatherTick` (B4)**: that component (lines 190-207) reads `row?.is_weekend`, `row?.is_holiday`, `row?.rain_severity === "disruptive_rain"`. Phase 2.5's bucket-row compatibility shim (`is_weekend = weekend_count > 0`, `is_holiday = holiday_count > 0`, `rain_severity = highest-severity day`) keeps `SalesWeatherTick` working WITHOUT modification — so this phase does NOT need to touch `SalesWeatherTick`. Verify Phase 2.5 implements the compat shim before relying on this. | MUST_CONTAIN: `row.holiday_count > 0` OR `row.disruptive_rain_day_count > 0` OR `row.weekend_count > 0` |
| 4.3 | **AMENDED v1.1 (W-04):** Update the chart's `XAxis` (line 1224-1231) to handle longer labels (`Week 18 (Apr 28 – May 4)` ≈ 22 chars at weekly, `May 2026` ≈ 8 chars at monthly) without overlap. **PINNED** conditional values: `minTickGap={granularity === "daily" ? 14 : granularity === "weekly" ? 80 : 40}`. Do NOT rotate (the existing `<SalesWeatherTick>` custom component would need a re-write — out of scope). Do NOT increase to just `28` (cold-start auditor confirmed insufficient — 26-char labels need ~120px gap; 80 with `SalesWeatherTick`'s ~70px wide rendering gets clean separation at all weekly densities up to 26 buckets in a 1200px chart). | MUST_CONTAIN: `granularity === "daily" ? 14` AND `minTickGap` |
| 4.4 | The Driver Snapshot tile (line 1328 onwards) currently reads from `bundle.weather.analysis.groups/effects`. Those server-supplied analytics are per-day aggregates by the backend. The snapshot itself is range-level (already aggregated by the backend over the full range). NO change needed unless the snapshot displays per-day numbers — verify by reading lines 1328-1400 and confirm it's range-aggregated. If any per-day rendering exists, replace with the bucket count from `bucketRows`. | MUST_CONTAIN if any rendering change occurs: a reference to `bucketRows` near the driver snapshot |
| 4.5 | The daily-detail table (line 1779-1856) currently renders one row per `day` in `dailyRows`. Replace with one row per bucket: render `bucketRows` instead. Column changes: "Date" becomes "Period" (renders `bucket_label`); "Weekend"/"Holiday"/"Rain"/"Showers"/"Temp state" badges become COUNT badges (`2 weekends`, `1 holiday`, `3 disruptive-rain days`) only when count > 0 for that bucket. Tabular monetary columns (Net, Txns, Cups, App Max, Temp vs 28D, Rain) use the bucket aggregates. | MUST_CONTAIN: `bucketRows.map` AND `bucket_label` referenced in the table |
| 4.6 | **AMENDED v1.1 (B6):** Below the aggregated table, add a shadcn `Collapsible` (NOT native `<details>`). `bei-tasks/components/ui/collapsible.tsx` is already installed (uses `@radix-ui/react-collapsible@^1.1.11`) and used in `employee-detail-dialog.tsx`. Import: `import { Collapsible, CollapsibleTrigger, CollapsibleContent } from "@/components/ui/collapsible";`<br><br>Structure:<br>```tsx<br>const [showDailyBreakdown, setShowDailyBreakdown] = useState(granularity === "daily");<br>useEffect(() => setShowDailyBreakdown(granularity === "daily"), [granularity]);<br><br><Collapsible open={showDailyBreakdown} onOpenChange={setShowDailyBreakdown}><br>  <CollapsibleTrigger className="...">Show daily breakdown</CollapsibleTrigger><br>  <CollapsibleContent><br>    {/* original per-day table loop from lines 1810-1851, sourced from dailyRows */}<br>  </CollapsibleContent><br></Collapsible><br>```<br><br>When granularity is `daily`, the collapsible is OPEN and the bucket table above IS the daily table (do not duplicate; render the daily breakdown only when granularity != daily). When granularity is weekly/monthly, the collapsible is closed by default and exposes the per-day breakdown re-derived from `dailyRows`, not `bucketRows`. **HARD BLOCKER (B6)**: do NOT use native `<details>` — visually inconsistent with the rest of the BEI dashboard and breaks Tailwind styling. | MUST_CONTAIN: `<CollapsibleTrigger` AND `<CollapsibleContent` AND `Show daily breakdown` |
| 4.7 | **AMENDED v1.1 (NCV-4, NCV-7):** Update three text surfaces to reflect the current granularity:<br><br>1. **CardDescription at line 1198** (NCV-7 — actual current text). Find: `"Net sales, temperature, and precipitation layered across the selected window for faster pattern reading."` Replace with: `` `${granularity === "daily" ? "Daily" : granularity === "weekly" ? "Weekly" : "Monthly"} net sales, temperature, and precipitation layered across the selected window for faster pattern reading.` ``<br><br>2. **Chart CardTitle at line 1192** (NCV-4). Find: `"Daily Net Sales vs Weather Drivers"`. Replace with: `` `${granularity === "daily" ? "Daily" : granularity === "weekly" ? "Weekly" : "Monthly"} Net Sales vs Weather Drivers` ``<br><br>3. **Driver Snapshot / Signals CardTitle at line 1787** (NCV-4). Find: `"Daily Signals"`. Replace with: `` `${granularity === "daily" ? "Daily" : granularity === "weekly" ? "Weekly" : "Monthly"} Signals` `` | MUST_CONTAIN: 3 occurrences of `granularity === "daily" ? ` (or a single helper like `granularityLabel(granularity)` used 3 times) — verifying all three text surfaces are dynamic. ALSO the literal string `"Net sales, temperature, and precipitation layered"` must remain reachable (the prefix of the description, embedded in a template literal). |
| 4.8 | **AMENDED v1.1 (B1):** Build + lint + run unit tests. Use `npm run build`, `npm run lint`, and `npx vitest run app/dashboard/analytics/sales/_aggregation.test.ts` (NOT `npm run test` — see Phase 2.8 amendment). Capture to `tmp/s245/build_phase4.log`. | MUST_MODIFY: `tmp/s245/build_phase4.log`. MUST_CONTAIN: zero `error TS` lines AND test summary shows zero failures AND `npx vitest run` |

## Phase 5 — Year presets + auto-granularity on preset click (4 units)

| Task | Description | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 5.1 | In `components/reports/date-range-picker.tsx`, add two new entries to the `PRESETS` array AFTER `Year to Date` (current entry at line 138-144): `{ label: 'This Year', range: () => { const t = startOfDay(new Date()); return { from: startOfYear(t), to: new Date(t.getFullYear(), 11, 31) }; } }` and `{ label: 'Last Year', range: () => { const t = startOfDay(new Date()); const lastYr = t.getFullYear() - 1; return { from: new Date(lastYr, 0, 1), to: new Date(lastYr, 11, 31) }; } }`. | MUST_MODIFY: `bei-tasks/components/reports/date-range-picker.tsx`. MUST_CONTAIN: `'This Year'` AND `'Last Year'` AND `getFullYear() - 1` |
| 5.2 | **AMENDED v1.1 (B7):** The DateRangePicker's API is unchanged. **HARD BLOCKER (B7)**: `applyPreset` (line 174-177) ONLY calls `setDraft({ from, to })` — `onFromChange`/`onToChange` only fire when the user clicks the `Apply` button (line 259 → `handleApply`). Verification: pick "This Year" preset (sidebar button click) → click `Apply` button in popover → date range updates → granularity auto-defaults to monthly. Any automated test or manual probe that asserts granularity change immediately after the preset click WITHOUT clicking Apply will see stale state. | n/a (verification step; the Apply-click pattern is enforced in Phase 6.1 spec) |
| 5.3 | Build + lint. | MUST_MODIFY: `tmp/s245/build_phase5.log` |

## Phase 6 — L3 Playwright verification + visual regression (8 units)

This sprint produces operator-facing UI changes. L3 verification is mandatory.

| Task | Description | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 6.1 | **AMENDED v1.1 (B2, B7):** Write `bei-tasks/tests/e2e/specs/s245-granularity-toggle.spec.ts`. **HARD BLOCKER (B2)**: use the existing `loggedInAreaSupervisor` fixture (NO "As" prefix — verified at `tests/e2e/fixtures/auth.ts:105`). The fixture imports `USERS.area` → `test.area@bebang.ph` (NOT `test.areasup@bebang.ph` — that account does NOT exist). **HARD BLOCKER (B7)**: every L3 scenario that clicks a DateRangePicker preset must follow with `await page.getByRole('button', { name: 'Apply' }).click();` before asserting granularity or date state — `applyPreset` only updates draft state; `handleApply` (Apply button) fires the actual date callbacks. Cover the L3 scenarios table below. | MUST_MODIFY: `bei-tasks/tests/e2e/specs/s245-granularity-toggle.spec.ts`. MUST_CONTAIN: `loggedInAreaSupervisor` (NO "As") AND `Apply` (the Apply-button click pattern) AND each scenario from the table below as a separate `test(...)` block |
| 6.2 | Add `data-testid` attributes to the new component: `data-testid="granularity-toggle-daily"`, `data-testid="granularity-toggle-weekly"`, `data-testid="granularity-toggle-monthly"`, `data-testid="granularity-toggle-reset"`. Add `data-testid="bucket-row-${row.bucket_key}"` to each row in the aggregated table. | MUST_CONTAIN in `granularity-toggle.tsx`: `data-testid="granularity-toggle-daily"`. MUST_CONTAIN in `page.tsx`: `data-testid={`bucket-row-` |
| 6.3 | Run `npx playwright test specs/s245-granularity-toggle.spec.ts` against the local dev server (`npm run dev` background). All scenarios must PASS. Capture trace on failure to `tmp/s245/playwright_trace_*.zip`. Save final pass evidence to `output/s245/verification/l3_playwright_results.json`. | MUST_MODIFY: `output/s245/verification/l3_playwright_results.json`. MUST_CONTAIN: `"passed": <count >= 7>` AND `"failed": 0` |
| 6.4 | Capture AFTER screenshots for the same 4 ranges as Phase 0.4: Last 7 days (daily auto), Last 30 days (weekly auto), Year to Date (monthly auto), Last Year (monthly auto). Save to `output/s245/verification/before_after_screenshots/after_*.png`. | MUST_MODIFY: 4 PNG files |
| 6.5 | URL state round-trip test: open page with `?granularity=monthly&start_date=2026-01-01&end_date=2026-03-31` → state initializes to monthly. Click `Weekly` button → URL updates to `?granularity=weekly&...`. Click `Reset to auto` → URL removes `granularity` param (the auto-default for 90-day range is weekly so the explicit param is redundant). Document round-trip evidence in `output/s245/verification/url_state_persistence.json`. | MUST_MODIFY: `output/s245/verification/url_state_persistence.json`. MUST_CONTAIN: at least 3 transitions with `before_url` and `after_url` recorded |

## L3 Workflow Scenarios

**v1.1 AMENDMENT (B2, B7)**: Every row uses `test.area@bebang.ph` (NOT `test.areasup@...`). Every action that picks a DateRangePicker preset must be followed by clicking the `Apply` button before asserting state — `applyPreset` only stages draft; `handleApply` fires the date callbacks.

| # | User | Action | Expected outcome | Failure means |
|---|---|---|---|---|
| L3-1 | test.area@bebang.ph | Navigate to `/dashboard/analytics/sales`. Open the date picker, click "Last 7 days" preset, click `Apply`. | Granularity toggle shows `Daily` active (auto). Chart renders 7 points. Daily-detail table renders 7 rows. URL has no `granularity` param. | Auto-default logic broken at <30 days |
| L3-2 | test.area@bebang.ph | Open the date picker, click "Last 30 days" preset, click `Apply`. | Granularity toggle shows `Weekly` active (auto). Chart renders 4-5 weekly bars. Aggregated table renders 4-5 rows with `Week N (...)` labels. shadcn `Collapsible` `Show daily breakdown` trigger visible and collapsed. URL has no `granularity` param. | Auto-default not snapping to weekly at 30 days |
| L3-3 | test.area@bebang.ph | Open the date picker, click "Year to Date" preset, click `Apply`. | Granularity toggle shows `Weekly` active (~131 days falls in 30-179 range, so weekly). Chart renders 18-19 weekly bars. | YTD did not auto-snap to weekly |
| L3-4 | test.area@bebang.ph | Open the date picker, click "Last Year" preset (NEW), click `Apply`. | Granularity toggle shows `Monthly` active. Chart renders 12 monthly bars labeled `Jan 2025` to `Dec 2025`. Aggregated table renders 12 rows. | Auto-default not snapping to monthly at full-year span; or `Last Year` preset missing |
| L3-5 | test.area@bebang.ph | With "Last 7 days" active (after click `Apply`), click `Monthly` button on the granularity toggle. | Toggle changes to `Monthly`. Chart renders 1 bar (May 2026). `Override` indicator visible with `Reset to auto` button. URL updates to include `granularity=monthly`. | Manual override not respected, or URL not persisting |
| L3-6 | test.area@bebang.ph | Click `Reset to auto`. | Granularity reverts to `Daily` (auto for 7-day range). URL removes `granularity` param. `Auto` indicator visible. | Reset-to-auto broken |
| L3-7 | test.area@bebang.ph | With `Monthly` active on "This Year" preset (after clicking the preset AND `Apply`), open browser DevTools, copy URL, open new tab, paste URL. | Page initializes with the same granularity (monthly). Chart renders 12 monthly bars (or fewer if mid-year — `Jan 2026` through current month). | URL state round-trip broken |
| L3-8 | test.area@bebang.ph | With "Last 30 days" active (weekly auto, after `Apply`), click the `Show daily breakdown` `CollapsibleTrigger`. | shadcn `Collapsible` expands showing the 30 per-day rows. Aggregated table still visible above. | Collapsible broken or duplicating data wrong |

## Failure Response

This is a frontend UI sprint. Failure modes follow the discipline doc taxonomy:

- **Mode A (app bug):** if a scenario reveals a bug in existing code unrelated to this sprint (e.g. chart tooltip broken at a specific data shape), file a `[BUG]` ticket, do not touch the test or the granularity logic, re-run after fix. Continue with the rest of L3.
- **Mode B (test bug):** if the test fails because the assertion is wrong or the selector is wrong, fix the test (or the new data-testid attribute) — do not paper over with `waitForTimeout`. If the fix is generally useful (e.g. a Page Object for the segmented control), extract it to `bei-tasks/tests/e2e/pages/sales-analytics.page.ts` as a closeout task.
- **Mode C (brittleness/flakiness):** if a scenario is flaky, fix the LIBRARY — add a deterministic wait (e.g. wait for the chart's `[data-chart-ready=true]` attribute) rather than `waitForTimeout`. If ≥3 library fixes happen during execution, emit `output/s245/LIBRARY_IMPROVEMENTS.md`.

## Test Data Seeding Contract

**This sprint does NOT seed test data.** The Sales Analytics page reads existing production sales data (via the already-deployed `/api/analytics/sales/overview` endpoint). The L3 scenarios use whatever data is currently in production for the selected ranges.

**AMENDED v1.1 (B2):** The test account is `test.area@bebang.ph` (NOT `test.areasup@bebang.ph` — that account does not exist anywhere in the codebase or `memory/testing-accounts.md`). It already has Area Supervisor role with Sales Dashboard module access (verified via `tests/e2e/helpers.ts:14` and `tests/e2e/fixtures/auth.ts:105`).

If for any reason the agent considers seeding test data, STOP and ask user — the L3 scenarios are read-only against production analytics.

## Phase 7 — Closeout (4 units)

| Task | Description | MUST_MODIFY / MUST_CONTAIN |
|---|---|---|
| 7.1 | Write `output/s245/SUMMARY.md` with: scope, before/after screenshots referenced, total LOC changed, file list, L3 verdict, list of UX decisions made (override flag behavior, ISO-week vs Sun-Sat, etc.). | MUST_MODIFY: `output/s245/SUMMARY.md` |
| 7.2 | Update plan YAML: `status: PLANNED` → `IN_PROGRESS` → `COMPLETED` with `completed_date: 2026-05-XX`, `execution_summary`. Use `git add -f docs/plans/2026-05-11-sprint-245-analytics-sales-granularity-toggle.md` because docs/plans/ is gitignored. | MUST_MODIFY: this plan file. MUST_CONTAIN: `status: COMPLETED` |
| 7.3 | Update `docs/plans/SPRINT_REGISTRY.md` S245 row to COMPLETED + PR link. `git add -f docs/plans/SPRINT_REGISTRY.md`. | MUST_MODIFY: registry. MUST_CONTAIN: `S245` row with `COMPLETED` |
| 7.4 | Append a row to `data/04_Project_Management/Import_Log/PROGRESS.md` summarizing S245. | MUST_MODIFY: PROGRESS.md. MUST_CONTAIN: `S245` row with timestamp |
| 7.5 | Commit all changes with specific paths: `git add bei-tasks/app/dashboard/analytics/sales/page.tsx bei-tasks/app/dashboard/analytics/sales/_aggregation.ts bei-tasks/app/dashboard/analytics/sales/_aggregation.test.ts bei-tasks/components/reports/date-range-picker.tsx bei-tasks/components/analytics/granularity-toggle.tsx bei-tasks/lib/sales-dashboard.ts bei-tasks/tests/e2e/specs/s245-granularity-toggle.spec.ts`. Then `git add -f` for plan + registry + PROGRESS + output/s245/. Commit with descriptive message referencing S245. | MUST_CONTAIN in commit log: `S245` AND `granularity` |
| 7.6 | Push branch: `git push -u origin s245-analytics-sales-granularity-toggle`. Create PR via `GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/BEI-Tasks --base main --head s245-analytics-sales-granularity-toggle --title "S245: Sales Analytics daily/weekly/monthly granularity toggle"`. PR body: link to plan, before/after screenshot URLs, L3 verdict, scope summary. | MUST_MODIFY: PR created. MUST_CONTAIN PR body: `S245`, `granularity`, `weekly`, `monthly`, `12 monthly bars`, `L3` |
| 7.7 | Update plan + registry with PR number; commit; push. | MUST_CONTAIN: PR number in plan YAML + registry row |
| 7.8 | Worktree cleanup: `cd F:/Dropbox/Projects/bei-tasks && git worktree remove F:/Dropbox/Projects/bei-tasks-s245-analytics-sales-granularity-toggle`. Worktree must exit clean (git status --short returns nothing). If dirty, commit scratch artifacts to a follow-up branch — never `--force`. | MUST_CONTAIN: `git worktree list` no longer shows the s245 worktree |
| 7.9 | Release `output/s245/state/active_run.json` ownership claim (`released_at` set). | MUST_MODIFY: `output/s245/state/active_run.json` |

## Execution Workflow

- Local dev: `cd F:/Dropbox/Projects/bei-tasks-s245-analytics-sales-granularity-toggle && npm run dev` (background)
- Build: `npm run build`
- Lint: `npm run lint`
- Tests: `npx vitest run app/dashboard/analytics/sales/_aggregation.test.ts` — for `_aggregation.test.ts`. **DO NOT** use `npm run test` (script does not exist in `bei-tasks/package.json` — verified). **DO NOT** use `npx vitest run` without a path argument (3 pre-existing failing tests in other modules will produce false-positive blockers).
- E2E: `npx playwright test specs/s245-granularity-toggle.spec.ts` — see `playwright-bei-erp` skill if tooling questions
- Deploy: NONE for this sprint. PR merge to `main` triggers Vercel auto-deploy. Builder creates PR; **user (Sam) merges**.
- Full workflow: standard `/execute-plan-bei-erp` (read plan → execute phases → PR).

## Execution Authority

This sprint is intended for autonomous end-to-end execution. Do not stop for progress-only updates. Pause only for items in `stop_only_for` (see Autonomous Execution Contract).

## Autonomous Execution Contract

```yaml
completion_condition:
  - all 8 phases green per their MUST_MODIFY / MUST_CONTAIN assertions
  - output/s245/SUMMARY.md exists and contains the verdict
  - PR is created (Sam merges separately)
  - plan YAML is COMPLETED with completed_date
  - SPRINT_REGISTRY.md row is COMPLETED with PR link
  - worktree is removed cleanly

stop_only_for:
  - npm install fails on a fresh worktree
  - npm run build fails on baseline (Phase 0.3)
  - aggregation_tests fail in Phase 2.8 (logic bug — fix it, do not skip)
  - production Frappe API returns 500 for the local dev session (env issue, not code)
  - Playwright cannot launch (see `playwright-bei-erp` skill — 99% of "Playwright is broken" claims are wrong invocation)
  - any L3 scenario fails after 3 retry attempts (after applying Mode B fixes)
  - any DM-1..DM-6 violation surfaces (should NOT — this plan touches no money/GL)

continue_without_pause_through:
  - phase 0 -> phase 1 -> phase 2 -> phase 3 -> phase 4 -> phase 5 -> phase 6 -> phase 7
  - aggregation tests -> chart wiring -> table wiring -> presets -> L3 -> closeout
  - PR creation -> registry update

blocker_policy:
  - programmatic (TS errors, lint errors, test failures) -> fix and continue
  - flakiness/timing in Playwright -> fix the LIBRARY (data-testid, deterministic wait), not the spec
  - chart rendering glitch with longer labels -> adjust XAxis tickFormatter or minTickGap; do not remove the label
  - merge conflict on bei-tasks/main -> rebase the branch, re-run build + lint, push

signoff_authority: single-owner (Sam, CEO)

canonical_closeout_artifacts:
  - output/s245/SUMMARY.md
  - output/s245/verification/before_after_screenshots/before_*.png (4 files)
  - output/s245/verification/before_after_screenshots/after_*.png (4 files)
  - output/s245/verification/aggregation_unit_tests.log
  - output/s245/verification/l3_playwright_results.json
  - output/s245/verification/url_state_persistence.json
  - docs/plans/2026-05-11-sprint-245-analytics-sales-granularity-toggle.md (status COMPLETED)
  - docs/plans/SPRINT_REGISTRY.md (S245 row COMPLETED)
  - data/04_Project_Management/Import_Log/PROGRESS.md (S245 row appended)
```

## Status Reconciliation Contract

When phase completes or counts change, update IN THE SAME WORK UNIT:

1. Phase status in this plan body (mark phase done with timestamp)
2. `output/s245/SUMMARY.md` running summary
3. Plan YAML `status` if transitioning (PLANNED → IN_PROGRESS → COMPLETED)
4. `SPRINT_REGISTRY.md` row when status changes
5. Authoritative counts in this plan body if drift was confirmed and accepted

## Signoff Model

- **Mode:** single-owner
- **Approver of record:** Sam (CEO)
- **Signoff artifact:** PR merge by Sam (per BEI deployment workflow — agents create PRs, user merges)
- **Final readiness basis:** `output/s245/SUMMARY.md` + 8/8 L3 scenarios passing + before/after screenshots showing the same data at higher readability

## Sprint Closeout Contract

- Plan YAML `status: PLANNED` → `COMPLETED` with `completed_date` and `execution_summary` (Phase 7.2)
- `SPRINT_REGISTRY.md` row updated to COMPLETED with PR link (Phase 7.3)
- Both files committed with `git add -f` (gitignored paths) and pushed (Phase 7.5-7.7)
- Worktree removed cleanly (Phase 7.8)
- A plan still showing `PLANNED` after the PR merges is a documentation defect.

## Zero-Skip Enforcement

Every task in Phases 0-7 MUST be implemented. If a task cannot be completed:

1. The agent STOPS at the failed task
2. The agent writes `output/s245/state/blocker_<phase>.<task>.md` describing what failed and why
3. The agent surfaces the blocker to the user
4. The agent does NOT mark the task done
5. The agent does NOT advance to the next phase

**Forbidden:**

- Marking a task done if its MUST_MODIFY file does not appear in `git diff --name-only origin/main..HEAD`
- Marking a task done if its MUST_CONTAIN string does not appear in the file via `grep`
- Combining tasks
- Skipping the unit tests (Phase 2.7-2.8) because "the logic is obviously right"
- Skipping L3 (Phase 6) because "I tested it manually"
- Substituting prose evidence for filesystem evidence
- Implementing "happy path only" — empty input, null weather fields, single-day buckets must all be tested

### Phase verification script

Every phase has a machine-checkable verifier. Write the verifier BEFORE starting the phase and run it AFTER:

```bash
# scripts/s245_phase_verifier.sh (in worktree)
# Usage: bash scripts/s245_phase_verifier.sh <phase_number>
# Checks:
#  - every MUST_MODIFY file appears in `git diff --name-only origin/main..HEAD`
#  - every MUST_CONTAIN string appears in its target file via grep
#  - npm run build passes
#  - npm run lint passes
#  - aggregation unit tests pass (after Phase 2)
#  - playwright passes (after Phase 6)
# Exits non-zero with a list of failures if anything is missing.
```

| Phase | Pass criteria |
|---|---|
| 0 | baseline_sha.txt exists; 4 before screenshots saved; baseline build green |
| 1 | `SalesGranularity` type exists; `granularity` URL param round-trips |
| 2 | `_aggregation.ts` + `_aggregation.test.ts` exist; ALL unit tests pass (>=7 cases) |
| 3 | `granularity-toggle.tsx` exists; renders in chart card; 3 buttons clickable |
| 4 | `chartRows` depends on `[dailyRows, granularity]`; daily-detail table aggregates; collapsible exists |
| 5 | `This Year` + `Last Year` present in PRESETS; year selection auto-defaults to monthly |
| 6 | 8/8 L3 scenarios pass; after screenshots saved; URL persistence JSON exists |
| 7 | plan YAML COMPLETED; registry row COMPLETED; PR exists; worktree removed |

If any phase verifier exits non-zero, the agent fixes the failure or stops per Failure Response.

## Cold-Start Test (self-check)

> "If an agent with zero context reads only this document, can it make every implementation choice?"

Yes. Specifically:

| Decision point | Where the agent finds the answer |
|---|---|
| What repo and branch | YAML frontmatter (`repo: bei-tasks`, `branch: s245-analytics-sales-granularity-toggle`, `pr_base: main`) |
| Which files to modify vs create | Surface Inventory table |
| Type definitions for granularity | Phase 1.1 (`SalesGranularity`, `SalesDashboardBucketRow`) |
| Auto-default thresholds | Design Rationale §"Why auto-default..." + Phase 1.2 (`<30 → daily`, `30-179 → weekly`, `>=180 → monthly`) |
| ISO-week vs Sun-Sat | Design Rationale §"Why ISO-weeks" + Phase 2.2 (`startOfISOWeek`) |
| Monthly = calendar month | Design Rationale §"Why monthly = calendar month" + Phase 2.2 (`yyyy-MM`) |
| Where to place the toggle UI | Phase 3.3 — right-aligned in chart card header next to badges |
| How to handle override flag | Phase 1.5 + 3.4 (track override; range change does not auto-clobber) |
| URL state pattern to follow | Phase 1.6 — extends existing useEffect at page.tsx:449-472 |
| How aggregation handles null weather | Phase 2.6 (`null`/`undefined` skipped from averages) |
| Bucket label format | Phase 2.3 — `Week WW (MMM d – MMM d)` weekly, `MMM yyyy` monthly |
| What the daily-detail table does | Phase 4.5-4.6 (aggregates to match toggle; collapsible exposes daily) |
| New presets | Phase 5.1 (`This Year`, `Last Year`) |
| L3 scenarios | L3 Workflow Scenarios table (8 scenarios) |
| Test account | **AMENDED v1.1 (B2):** `test.area@bebang.ph` (NOT `test.areasup@...`) — verified at `tests/e2e/helpers.ts:14` and `tests/e2e/fixtures/auth.ts:105` |
| Closeout sequence | Phase 7 task table |
| When to stop | Autonomous Execution Contract `stop_only_for` |

No unresolved values. No `[UNVERIFIED — requires resolution]` items.

## Agent Boot Sequence

1. Read this plan fully (every phase, every HARD BLOCKER).
2. Spawn worktree:
   ```bash
   cd F:/Dropbox/Projects/bei-tasks && git fetch origin --prune
   git worktree add F:/Dropbox/Projects/bei-tasks-s245-analytics-sales-granularity-toggle -B s245-analytics-sales-granularity-toggle origin/main
   cd F:/Dropbox/Projects/bei-tasks-s245-analytics-sales-granularity-toggle
   ```
3. Read `docs/plans/SPRINT_REGISTRY.md` row for S245 (verifies branch reservation).
4. **AMENDED v1.1 (B2):** Read `memory/testing-accounts.md` for the `test.area@bebang.ph` credentials needed in Phase 6 (NOT `test.areasup@...` — that account does NOT exist).
5. Confirm baseline build is green (Phase 0.3).
6. Begin Phase 0 → Phase 7 in order.
