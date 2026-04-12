# S185 Plan Audit — Cold-Start Findings
**Plan:** `docs/plans/2026-04-12-sprint-185-period-comparison-rank-delta.md`
**Audited:** 2026-04-12
**Auditor:** Sub-agent (cold-start readiness + zero-skip enforcement)

---

## Summary Scorecard

| Category | Status | Blockers |
|---|---|---|
| Cold-Start Readiness | PARTIAL | 4 CRITICAL, 2 WARNING |
| Zero-Skip Enforcement | PASS | 0 |
| Machine-Verifiable Phase Gates | PASS | 0 |
| Requirements Regression Checklist | PASS | 0 |
| L3 Scenarios | PARTIAL | 1 WARNING |

---

## CRITICAL FINDINGS

### CRITICAL-1: `_aggregate_sales` Is NOT Used for Per-Store Aggregation — Wrong Pattern

**Audit question:** Task 1.1 says "understand the `_query_daily_rows` + `_aggregate_sales` pattern" for per-store aggregation. Task 1.4 says "reuse `_aggregate_sales` pattern" and specifies `prev_net = sum of (net_sales - vat_amount)` per store.

**Finding from source:**
`_aggregate_sales()` (`sales_dashboard.py:1453`) aggregates ALL rows into a SINGLE fleet-wide dict. It does NOT split by `location_id`. Its signature is:
```python
def _aggregate_sales(rows: list[dict[str, Any]]) -> dict[str, Any]:
```
It returns one flat dict (`gross_sales`, `net_sales_without_vat`, etc.) — not keyed by store.

**The actual per-store aggregation** (what the plan needs) is NOT done via `_aggregate_sales`. `_build_store_rankings()` does its own direct loop over `sales_rows`, grouping by `location_id` into `by_location: dict[int, dict]`.

**Impact:**
- If an agent follows "reuse `_aggregate_sales` pattern" literally, it will call `_aggregate_sales(prev_rows)` and get a fleet-wide total — not a per-store breakdown. The per-store comparison will be silently wrong (every store gets the fleet total as its "prior net").
- The correct pattern is to walk `prev_rows` in a loop, grouping by `location_id`, summing `total_net_sales_without_vat` per store — matching the existing `by_location` accumulator already in `_build_store_rankings`.

**Verdict:** BLOCKER. The plan must replace "reuse `_aggregate_sales` pattern" with the explicit loop pattern.

---

### CRITICAL-2: Task 1.4 Formula `net_sales - vat_amount` Is Wrong — No Such Column

**Audit question:** Task 1.4 says: `prev_net = sum of (net_sales - vat_amount)` from prior rows.

**Finding from source:**
The Supabase view columns selected via `DAILY_METRIC_SELECT` (`sales_dashboard.py:73-102`) include:
- `total_net_sales_without_vat` — this IS net sales without VAT
- `total_gross_sales` — gross sales
- NO column named `net_sales`
- NO column named `vat_amount`

The existing `_build_store_rankings` accumulates per-store net using:
```python
store_row["net_sales_without_vat"] += _to_float(row.get("total_net_sales_without_vat"))
```

The comparison data must use the SAME column: `total_net_sales_without_vat`. The formula `(net_sales - vat_amount)` is a fabricated formula — neither column exists in the daily rows data.

**Additionally:** The comment block at `sales_dashboard.py:844` explicitly warns:
> "CRITICAL: v_pos_orders_live.net_sales is ALREADY net of VAT (gross - vat). Do NOT subtract vat_amount again — that's a double-subtraction bug."

Even if `vat_amount` existed, double-subtracting VAT would be a known bug.

**Verdict:** BLOCKER. Task 1.4 must be corrected to:
> `prev_net = sum of total_net_sales_without_vat per location_id from prev_rows`

---

### CRITICAL-3: `net_sales_without_vat` in Rankings Is Overridden AFTER the Accumulator — Task 1.6 Ranking Field Is Available But Derived From Channel Split, Not Daily Rows

**Audit question:** Task 1.6 says "rank by `net_sales_without_vat` descending." Is this field available when ranking is computed?

**Finding from source:**
`_build_store_rankings()` has TWO passes:
1. **Pass 1** (lines 2442-2480): Accumulates `net_sales_without_vat` from `total_net_sales_without_vat` in daily rows via the `by_location` loop.
2. **Pass 2** (lines 2496-2564): Overrides each store's `net_sales_without_vat` with `clean_net = round(sum(channel_mix.values()), 2)` — the channel-split-corrected value that removes the FoodPanda double-count.

The final return (line 2565) sorts by `gross_sales` (not `net_sales_without_vat`):
```python
return sorted(by_location.values(), key=lambda row: row["gross_sales"], reverse=True)
```

**Impact on S185:**
- `net_sales_without_vat` IS available for ranking, but only after Pass 2 (channel split enrichment).
- The plan's rank assignment (Task 1.6) must happen AFTER the channel split loop, not inline during accumulation.
- The final sort (line 2565) currently uses `gross_sales` — this MUST be changed to use `net_sales_without_vat` for Sam's requirement. The plan does not explicitly say to change the existing sort line.
- The plan also does not warn that the overridden `net_sales_without_vat` (from channel sum) is the correct value to rank on, not the raw MV value from Pass 1.

**Verdict:** BLOCKER. The plan must explicitly state:
1. Rank assignment happens after the channel-split enrichment loop (Pass 2), not before.
2. The existing `return sorted(..., key=lambda row: row["gross_sales"], ...)` at line 2565 must be changed to sort by `net_sales_without_vat`. Without this instruction, an agent will sort the return value by the wrong field.

---

### CRITICAL-4: `get_sales_dashboard_store_rankings` Wraps `get_sales_dashboard_overview` — Adding `include_comparisons` to Rankings Endpoint Only Won't Work

**Audit question:** Task 1.2 says to add `include_comparisons` to `get_sales_dashboard_store_rankings()` at line 3082. Task 3.3 says "Since `get_sales_dashboard_store_rankings` wraps `get_sales_dashboard_overview`, the frontend fetch for rankings already gets comparison data if the rankings endpoint accepts and forwards the param."

**Finding from source:**
`get_sales_dashboard_store_rankings()` (lines 3082-3120) calls `get_sales_dashboard_overview()` and returns `overview["stores"]`. `_build_store_rankings()` is called from inside `_build_dashboard_overview_payload()` (line 2917), NOT from `get_sales_dashboard_store_rankings()` directly.

`get_sales_dashboard_overview()` already has `include_comparisons` in its signature (line 2983):
```python
def get_sales_dashboard_overview(
    ...
    include_comparisons: bool | str | int | None = None,
) -> dict[str, Any]:
```

This means:
1. `include_comparisons` already exists on the overview endpoint — the plan says to add it to `get_sales_dashboard_overview`, but it's ALREADY THERE.
2. To have `get_sales_dashboard_store_rankings` pass it through, the agent needs to add `include_comparisons` param to `get_sales_dashboard_store_rankings` AND forward it to the `get_sales_dashboard_overview(...)` call.
3. `_build_store_rankings()` is called deep inside `_build_dashboard_overview_payload()` — the plan says to add `include_comparisons` parameter to `_build_store_rankings()` itself, but the call chain goes: `get_rankings` → `get_overview` → `_build_dashboard_overview_payload` → `_build_store_rankings`. The plan does NOT describe the middle of this chain.

**The plan's instruction "add `include_comparisons` to `get_sales_dashboard_store_rankings()`" is correct but INCOMPLETE.** It omits the required change to `_build_dashboard_overview_payload()` to accept and forward `include_comparisons` to `_build_store_rankings()`. Without modifying `_build_dashboard_overview_payload`, the parameter never reaches `_build_store_rankings`.

**However,** the Surface Ownership Matrix says: "do NOT touch `_build_dashboard_overview_payload`." This is a direct contradiction — the agent must touch `_build_dashboard_overview_payload` to thread the parameter through, but is forbidden from doing so.

**Verdict:** BLOCKER. The plan has an architectural gap and a contradictory ownership constraint. Options:
- Either allow modification of `_build_dashboard_overview_payload` (relax the ownership constraint)
- Or document that `get_sales_dashboard_store_rankings` should NOT use the overview wrapper for comparison — it should call `_build_store_rankings` directly with its own data.

---

## WARNING FINDINGS

### WARNING-1: `_aggregate_sales` Return Columns Not Documented for Per-Store Use Case

**Audit question:** "Is `_aggregate_sales` function documented enough? The plan says 'reuse `_aggregate_sales` pattern' but doesn't show what columns it returns."

**Finding:** `_aggregate_sales()` returns: `gross_sales`, `net_sales_with_vat`, `net_sales_without_vat`, `cups_sold`, `transactions`, `pickup_sales`, `website_sales`, `website_sales_without_vat`, `website_cod_orders`, `website_cod_sales_with_vat`, `website_cod_sales_without_vat`, `foodpanda_sales`, `foodpanda_sales_without_vat`, `pickup_sales_without_vat`, `delivery_sales_without_vat`, `grabfood_sales`, `grabfood_sales_without_vat`, `grabfood_orders`, `grabfood_avg_ticket`, `average_daily_sales`, `average_guest_check`, `cups_per_transaction`, `day_count`.

**Status:** Moot — given CRITICAL-1 establishes the agent should NOT call `_aggregate_sales` for per-store aggregation. But worth flagging in case the plan is corrected to keep `_aggregate_sales` for the prior-period fleet-total reference.

---

### WARNING-2: L3 Scenarios Lack Evidence File Contract and Null-Comparison Store Scenario

**Audit questions:** Are L3 scenarios concrete? Do they cover edge cases? Is there an L3 evidence file contract?

**Findings:**

1. **No L3 evidence file contract.** The plan does not specify where L3 test output is written (e.g., `output/s185/l3_evidence.json`). This is a gap — without it, "L3 PASS" is agent self-report, not filesystem-verified.

2. **Missing null-comparison scenario.** The plan mentions "stores that opened within the current period get `rank_change: null`" in Known Limitations, but no L3 scenario tests this. L3-185-04 only checks for a store with positive delta. A new store (null comparison) rendering as "NEW" rather than crashing is a critical edge case that should be tested.

3. **L3-185-02 is observer-only, not action-driven.** "Verify rank order matches net sales w/o VAT descending" requires querying the API response directly. The scenario doesn't specify HOW to verify this (e.g., check that the rendered #1 store matches the store with the highest `net_sales_without_vat` in the payload). A Playwright scenario needs a concrete DOM assertion or API intercept.

4. **L3-185-07 (single-day):** Concrete enough — correct.

5. **30-day range (L3-185-12):** Correct and meaningful.

---

## INFO FINDINGS

### INFO-1: `_build_comparisons` Uses `gross_sales` for Delta, Not `net_sales_without_vat`

The existing `_build_comparisons()` (lines 1781-1793) computes delta using `gross_sales`:
```python
base_sales = _to_float(baseline.get("gross_sales"))
current_sales = _to_float(current.get("gross_sales"))
```

S185's per-store comparison is supposed to use `net_sales_without_vat` (Sam's explicit requirement). The plan correctly diverges from `_build_comparisons` here, but an agent following "reuse `_build_comparisons` pattern" blindly could copy the `gross_sales` delta logic. The plan's Task 1.5 output dict includes both `net_delta` and `gross_delta` — this is safe. But it should explicitly note the divergence from `_build_comparisons`.

---

### INFO-2: `_shift_range` Signature Confirmed Correct

Plan says: `_shift_range(start_day, end_day, span_days)` at line 1756. Source confirms:
```python
def _shift_range(start_day: date, end_day: date, delta_days: int) -> tuple[date, date]:
    return start_day - timedelta(days=delta_days), end_day - timedelta(days=delta_days)
```
Signature matches. Plan's usage is correct.

---

### INFO-3: `_query_daily_rows` Cache Key Pattern Is Already Used — No Custom Wrapper Needed

Task 1.3 says to wrap the prior-period query in `_cache_get_or_set` with a custom cache key. However, `_query_daily_rows()` already calls `_cache_get_or_set` internally (line 1387-1402). Calling `_query_daily_rows(prev_start, prev_end, location_ids)` directly is sufficient — no external cache wrapper is needed. The plan's Task 1.3 instruction to add an outer `_cache_get_or_set` is redundant and could result in double-caching. LOW risk but should be removed from the task.

---

### INFO-4: `SalesDashboardStoreRankingsResponse` Type Not Shown in Plan

Task 2.1 says to extend `SalesDashboardStoreRankingsResponse` with `comparison_meta`. This type is referenced in the plan but not confirmed to exist. The file `lib/sales-dashboard.ts` was not fully audited here, but the type likely exists as a wrapper around `SalesDashboardStoreRanking[]`. Not a blocker — the boot sequence tells the agent to read the type file.

---

## Zero-Skip Enforcement — PASS

The plan has a complete Zero-Skip Enforcement section (lines 259-278):
- Forbidden behaviors listed: 6 specific prohibitions
- Phase Completion Checklist defined: `output/s185/phase_N_completion.md` after each phase
- PR gate: "PR cannot be created until PASS"
- Verification script: `output/s185/verify_s185.py` — filesystem checks (grep patterns), not agent self-report
- Protected surface check included in script

No gaps.

---

## Machine-Verifiable Phase Gates — PASS

All tasks in Phases 1-3 have grep-checkable MUST_MODIFY assertions. Examples:
- `grep -c "include_comparisons" hrms/api/sales_dashboard.py` >= 2
- `grep -c "prev_by_location" hrms/api/sales_dashboard.py` >= 1
- `grep -c "position_change" app/dashboard/analytics/sales/stores/page.tsx` >= 2

All assertions are concrete grep counts, not prose. Phase 4 has filesystem existence checks. The verification script is mandatory before PR creation.

No gaps.

---

## Requirements Regression Checklist — PASS

12-item checklist with yes/no checks. All items are meaningful:
- Formula correctness (SAME span, not calendar week)
- Field used for rank sort (net_sales_without_vat)
- Position change direction convention (+/-)
- RBAC scope coverage
- UI requirements (badge colors, "—" for null)
- Sentry observability
- Mobile coverage

HARD BLOCKERs are present inline (1-1 and 1-2 in Phase 1).

No gaps.

---

## Required Plan Corrections

### Must Fix Before Execution (BLOCKERS)

**[BLOCKER-1] Fix CRITICAL-1:** Replace Task 1.4's "reuse `_aggregate_sales` pattern" with the explicit per-store accumulator pattern:
```python
prev_by_location: dict[int, dict] = {}
for row in prev_rows:
    lid = _to_int(row.get("location_id"))
    bucket = prev_by_location.setdefault(lid, {"net": 0.0, "gross": 0.0})
    bucket["net"] += _to_float(row.get("total_net_sales_without_vat"))
    bucket["gross"] += _to_float(row.get("total_gross_sales"))
```

**[BLOCKER-2] Fix CRITICAL-2:** Replace `prev_net = sum of (net_sales - vat_amount)` in Task 1.4 with `sum of total_net_sales_without_vat per location_id from prev_rows`. Remove any reference to `vat_amount` column.

**[BLOCKER-3] Fix CRITICAL-3:** Add explicit instructions in Task 1.6:
- "Rank assignment happens AFTER the channel-split enrichment loop (Pass 2), not before. The `net_sales_without_vat` used for ranking is the channel-corrected value set by `clean_net = round(sum(channel_mix.values()), 2)` in Pass 2."
- "Modify the existing `return sorted(by_location.values(), key=lambda row: row['gross_sales'], reverse=True)` at line 2565 to sort by `net_sales_without_vat` instead of `gross_sales`."

**[BLOCKER-4] Fix CRITICAL-4:** Resolve the architectural gap around `_build_dashboard_overview_payload`:
- Either: relax the Surface Ownership Matrix to allow modification of `_build_dashboard_overview_payload` to thread `include_comparisons` → `_build_store_rankings`
- Or: change the implementation strategy so `get_sales_dashboard_store_rankings` calls `_build_store_rankings` directly (not via the overview wrapper) when `include_comparisons=True`
- Document the full call chain: `get_rankings` → `get_overview` → `_build_dashboard_overview_payload` → `_build_store_rankings`

### Should Fix (Warnings)

**[WARNING-1]** Add L3 evidence file contract: specify that L3 results are written to `output/s185/l3_evidence.json` with fields verified per scenario.

**[WARNING-2]** Add L3 scenario for null-comparison store (new store, no prior data). Expected: renders "NEW" badge, no crash, comparison shows "—".

**[WARNING-3]** Fix Task 1.3 — remove redundant outer `_cache_get_or_set` wrapper instruction. `_query_daily_rows()` already handles caching internally.

---

## Verified Correct Elements

- `_shift_range()` line reference (1756) and signature: confirmed correct
- `_query_daily_rows()` line reference (1384) and signature: confirmed correct
- `_build_store_rankings()` line reference (2416-2565): confirmed correct
- `_build_comparisons()` line reference (1760-1803): confirmed correct
- `get_sales_dashboard_store_rankings()` line reference (3082-3120): confirmed correct
- `SalesDashboardStoreRanking` type line reference (256-275): confirmed correct
- `fetchStoreRankings()` location in `lib/api/sales-dashboard.ts`: confirmed correct
- Sentry context already present at line 3094-3098: confirmed correct
- Zero-skip enforcement section: complete and correct
- Phase gates: grep-checkable, filesystem-verified
- Requirements regression checklist: meaningful and complete
- L3-185-07 (single-day comparison), L3-185-12 (30-day): concrete and correct
- Cache TTL 300s reference: confirmed (`SALES_DASHBOARD_CACHE_TTL` used in `_query_daily_rows`)
- `net_sales_with_vat` accumulates `total_gross_sales` (line 1482) — this is an existing quirk in `_aggregate_sales`, not introduced by S185
