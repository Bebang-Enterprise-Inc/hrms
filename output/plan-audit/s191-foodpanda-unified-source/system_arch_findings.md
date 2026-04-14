# S191 System Architecture Audit — FoodPanda Unified Source

**Auditor:** System architect sub-agent (Claude Sonnet 4.6)
**Date:** 2026-04-12
**Plan file:** `docs/plans/2026-04-14-sprint-191-foodpanda-unified-source.md`
**Target file:** `hrms/api/sales_dashboard.py`
**Audit scope:** Data integrity, baseline validation thresholds, downstream callers, cache coherence, historical consistency, Mosaic-wins correctness, rollback path, GrabFood isolation

---

## Summary Table

| # | Severity | Topic | One-line finding |
|---|---|---|---|
| F-01 | CRITICAL | Data integrity — MV double-count not fully eliminated | `_aggregate_daily_series` still adds `foodpanda_vat_deducted_sales` from MV even after S191 fix |
| F-02 | CRITICAL | Data integrity — `_aggregate_sales` initial load uncleared | `_aggregate_sales` loads `foodpanda_subtotal` from MV; `_apply_mosaic_channel_split` overwrites it — but the MV value persists in `net_sales_without_vat` heading until the override runs |
| F-03 | CRITICAL | Missed downstream caller — `export_sales_dashboard_detail` | CSV export calls `_get_mosaic_channel_split_per_day` directly; after S191 that function will carry correct FP per-day data BUT the `_aggregate_daily_series` consumer still adds the MV's `foodpanda_vat_deducted_sales` residual (F-01), so exported CSVs will show inflated delivery totals for legacy-only days |
| F-04 | CRITICAL | Cache coherence — overview cache key unchanged | The `"overview"` and `"summary"` cache key prefixes do NOT change in S191. If a user loaded the dashboard before deploy, the cached response with Mosaic-only FP values persists for up to 300s. The plan's `fp_unified` prefix fix only covers the NEW inner helper — the outer `_build_dashboard_overview_payload` and `_build_dashboard_summary_payload` wrappers keep their existing cache keys. Stale results WILL be served immediately after deploy. |
| F-05 | WARNING | Baseline validation — ₱50K single-day threshold will likely false-trigger | VAT imputation gap (`subtotal/1.12` vs Mosaic `net_sales`) on a medium store-day (~500 orders × avg ₱80 ticket = ₱40K subtotal) produces a ~₱4.3K net difference. But during the overlap window (Mar 26-31) large stores (Trinoma, SM North, etc.) can legitimately produce per-store-day Mosaic vs legacy discrepancies of ₱50K–₱150K due entirely to the VAT computation asymmetry. The ₱50K HARD BLOCKER will trip on valid data and block Phase 1. |
| F-06 | WARNING | Baseline validation — ₱1M total overlap variance threshold ambiguity | The plan does not specify whether the ₱1M is SUM(ABS(mosaic - legacy)) per day across all overlap days, or max single day. With ~6 overlap days × 40+ stores, even a 5% average net-vs-gross discrepancy from the `subtotal/1.12` approximation can produce ~₱1.5M total variance. The threshold may block legitimate execution. |
| F-07 | WARNING | Mosaic-wins correctness — no completeness threshold | The plan picks Mosaic for any overlap (store, day) regardless of order count. If Mosaic had a sync interruption and captured only 30% of actual orders on that day, Mosaic-wins discards the complete legacy data. The plan has no minimum-orders or minimum-gross completeness guard. |
| F-08 | WARNING | `_build_comparisons` uses raw `_aggregate_sales` on prior-period rows | Comparison periods (previous period, same period last year) call `_aggregate_sales` without calling `_apply_mosaic_channel_split`. This means comparison `gross_sales_delta` is computed against the MV's legacy FP totals for the baseline period (Feb 2026), producing a misleading delta. The fix will make March look ₱17M higher while the February comparison baseline remains MV-only (₱9.5M). The reported delta will be distorted for any date window that spans or abuts the legacy period. |
| F-09 | WARNING | `_sales_row_metrics` helper uses stale MV FP value | `_sales_row_metrics` (line 2644) computes `delivery_sales_without_vat` from `foodpanda_vat_deducted_sales` (MV legacy column). This helper feeds the store-detail panel and any direct consumer. The plan does not identify this as a caller to update. |
| F-10 | WARNING | Historical reporting consistency — ₱17M delta not flagged for Sam | S191 will retroactively change reported Feb and March FP revenue from ₱4.4M → ₱21.7M (March) and ₱0 → ₱8.5M (Feb net). Financial close reports, Apex P&L, and any commission calculations that used the old dashboard numbers will be inconsistent with post-S191 figures. This is explicitly out of scope but Sam MUST be notified before deploy. |
| F-11 | INFO | GrabFood isolation — plan is architecturally safe | `_apply_mosaic_channel_split` pops `"grabfood"` from the Mosaic-only split dict independently of FoodPanda. The plan's Phase 2 replaces only `fp_bucket` via the new unified aggregate. GrabFood path is provably untouched IF the developer follows the plan correctly. The verification script's `grabfood` count assertion is appropriate. |
| F-12 | INFO | Rollback path — adequate but requires manual cache flush | Reverting the PR and redeploying restores the old Mosaic-only behavior. However the `fp_unified` inner cache entries (300s TTL) will continue serving unified data for up to 5 minutes post-rollback. The outer `"overview"` and `"summary"` cache keys will also have stale S191 entries for 300s. No explicit cache flush mechanism is documented in the plan. |
| F-13 | INFO | PostgREST fallback for FULL OUTER JOIN not implementable cleanly | The plan (Phase 1.2) requires a Python-level FULL OUTER JOIN fallback when `SUPABASE_MGMT_TOKEN` is missing. PostgREST cannot execute a FULL OUTER JOIN — it exposes individual tables only. The fallback must fetch both sources separately and merge in Python, which is correct per the plan. But the plan underestimates the complexity: paginating `foodpanda_orders` for a 2-month, 45-store window may return 50K+ rows (~50+ pages at 1000/page). Plan's 6-unit budget for Phase 1 may be tight if fallback is implemented thoroughly. |
| F-14 | INFO | `_FOODPANDA_MOSAIC_START` freshness warning (line 1296) will be permanently stale | After S191 the warning "FoodPanda source split at 2026-03-27: earlier dates come from the legacy sheet" is no longer accurate — data from both sources is now unified regardless of date. The warning should be updated to reflect the new unified source model. The plan marks the constant as deprecated but does not update the user-facing warning string. |

---

## Detailed Findings

---

### F-01 — CRITICAL: `_aggregate_daily_series` adds MV's `foodpanda_vat_deducted_sales` even after S191

**Location:** `sales_dashboard.py:2058-2061`

**Evidence:**
```python
bucket["superadmin_delivery_wo_vat"] += (
    _to_float(row.get("website_non_cod_net_sales_without_vat"))
    + _to_float(row.get("web_cod_net_sales_without_vat"))
    + _to_float(row.get("foodpanda_vat_deducted_sales"))  # legacy sheet, usually 0
)
```

The comment says "usually 0" but that is only true POST-cutover. For Feb and early March 2026, `foodpanda_vat_deducted_sales` in the MV contains the full legacy sheet net — up to ~₱400K/day for the fleet. After S191, `_get_mosaic_channel_split_per_day` will correctly return unified FP per-day data (including legacy days), which is used in `_aggregate_daily_series` (line 2081) to compute `mosaic_delivery_wo_vat`. BUT `superadmin_delivery_wo_vat` still adds the MV's `foodpanda_vat_deducted_sales` on top. For any legacy-period day, the final `delivery_sales_without_vat` in the time-series will double-count FoodPanda net: once via `mosaic_delivery_wo_vat` (from the new unified per-day split) and once via `superadmin_delivery_wo_vat` (from the MV).

**Impact:** All time-series data for Feb and early March 2026 will show inflated delivery totals. The export endpoint (`export_sales_dashboard_detail`) also uses this path and will export incorrect data.

**Required fix:** The `+ _to_float(row.get("foodpanda_vat_deducted_sales"))` line in `_aggregate_daily_series` must be removed (or zeroed) as part of S191 — it is functionally obsolete once the unified per-day split is in place. This is analogous to what S176 hotfix #10 did for the headline summary (removing the MV FP double-count from `_aggregate_sales`'s downstream). The plan does not include this in Phase 3.

---

### F-02 — CRITICAL: `_aggregate_sales` seeds `foodpanda_sales` from MV before `_apply_mosaic_channel_split` overrides it

**Location:** `sales_dashboard.py:1492-1499`

**Evidence:**
```python
totals["foodpanda_sales"] += _to_float(row.get("foodpanda_subtotal"))
totals["foodpanda_sales_without_vat"] += _to_float(row.get("foodpanda_vat_deducted_sales"))
...
totals["delivery_sales_without_vat"] += (
    ...
    + _to_float(row.get("foodpanda_vat_deducted_sales"))
)
```

`_aggregate_sales` initializes `foodpanda_sales` and `foodpanda_sales_without_vat` from the MV's `foodpanda_subtotal` / `foodpanda_vat_deducted_sales`. For historical dates (Feb-Mar) these columns contain the full legacy Google Sheet values — roughly correct. `_apply_mosaic_channel_split` then OVERWRITES `summary["foodpanda_sales"]` and `summary["foodpanda_sales_without_vat"]` with the Mosaic-only bucket, dropping the legacy data.

After S191, `_apply_mosaic_channel_split` will call `_get_unified_foodpanda_totals_aggregate` and correctly replace these with the unified total. So the overwrite chain is correct for the headline FP fields. HOWEVER: `delivery_sales_without_vat` is ALSO seeded in `_aggregate_sales` (line 1498) with `foodpanda_vat_deducted_sales`, and `_apply_mosaic_channel_split` does override `delivery_sales_without_vat` at line 989-996 — so this path is correctly handled.

**Residual risk:** The seeded-then-overridden pattern means that if `_apply_mosaic_channel_split` ever fails (exception or short-circuit), the caller receives the MV-only FP values (which are wrong for post-March dates when MV has zero). There is no explicit try/except guard. Low severity in normal operation, but worth noting for defensive coding.

---

### F-03 — CRITICAL: `export_sales_dashboard_detail` is a missed caller (F-01 compounded)

**Location:** `sales_dashboard.py:3244-3297`

**Evidence:**
```python
mosaic_split_per_day = _get_mosaic_channel_split_per_day(start_day, effective_end, selected_location_ids)
series = _aggregate_daily_series(scope["selected_stores"], sales_rows, weather_rows, mosaic_split_per_day)
export_rows = _build_export_rows(scope, series, sales_rows)
```

The CSV export endpoint calls `_get_mosaic_channel_split_per_day` (which S191 will fix to return unified data) and feeds it into `_aggregate_daily_series`. Because of F-01, the export will double-count FP delivery for legacy days. Additionally, the plan's Phase 3.6 audit (`foodpanda_call_sites_audit.md`) is likely to miss this caller because it is not in the three listed target functions. The plan's test scenarios (L3-191-01 through L3-191-12) do not include a CSV export scenario.

**Required action:** Add `export_sales_dashboard_detail` to the call-sites audit. Fix F-01 (remove `foodpanda_vat_deducted_sales` from `_aggregate_daily_series`). Add an L3 scenario for the export endpoint.

---

### F-04 — CRITICAL: Outer cache keys unchanged — stale data served immediately after deploy

**Location:** `sales_dashboard.py:2807-2815` (summary), `2915-2924` (overview)

**Evidence:**
```python
# summary payload:
cache_key = _sales_dashboard_cache_key(
    "summary",
    selected_location_ids,
    start_day=start_day,
    end_day=end_day,
    view_mode=view_mode,
    channel=channel,
    include_comparisons=include_comparisons,
)

# overview payload:
cache_key = _sales_dashboard_cache_key(
    "overview",
    selected_location_ids,
    ...
)
```

The plan's HARD BLOCKER 1-1 correctly mandates the `fp_unified` prefix for the inner helper cache. BUT the outer `"summary"` and `"overview"` cache keys are formed from the **same** parameters as before deploy. Any user who loaded the dashboard before deploy will have a cached response (keyed as `"sales_dashboard:summary:...dates..."`) that contains Mosaic-only FP data. After deploy, that cache key is still valid and the old cached value will be returned for up to 300s. The new `fp_unified` inner cache is bypass-correct (new key = no stale hit) but the outer response cache wraps the entire builder function including the corrected FP values — so if the outer cache is hit, the new unified values never reach the user.

**Practical impact:** Depending on traffic patterns, some users may see the old ₱4.4M figure for up to 5 minutes after deploy. In a high-traffic production environment this is a customer-visible issue.

**Required fix:** Either (a) bump the outer cache key prefix to `"summary_v2"` / `"overview_v2"` (same approach as `"freshness_v2"` at line 743), or (b) document explicitly in the deploy runbook that the 300s TTL means stale data is possible and time the deploy accordingly. Option (a) is safest.

---

### F-05 — WARNING: ₱50K single-store-day variance threshold will likely false-trigger on valid data

**Location:** Plan Phase 0, HARD BLOCKER 0-1

**Analysis:**

The plan compares Mosaic `net_sales` (already net of VAT) against legacy `subtotal / 1.12` (approximated net). During the Mar 26-31 overlap window, the two sources measure different things:
- Mosaic `net_sales` = gross minus actual VAT per transaction (exact)
- Legacy `subtotal / 1.12` = gross / 1.12 (assumes 100% vatable, ignores SC/PWD exemptions)

For a high-volume store (e.g., Trinoma, SM North) with ₱300K–₱600K FP daily gross, a 5-10% systematic VAT computation gap produces ₱15K–₱60K per-store-day difference from methodology alone — not data quality issues. SC/PWD exempt orders (typically 3-8% of transactions) further widen this gap.

Additionally, if the overlap period includes a store where Mosaic and the Google Sheet were synced from the same underlying FoodPanda data, the gross values should match but net will differ by design. The ₱50K threshold will trigger on any high-volume store in the overlap window.

**Recommendation:** Raise the per-store-day threshold to ₱100K, or better: define the threshold as a percentage of gross (e.g., >15% relative difference) rather than an absolute peso amount. Also clearly document in HARD BLOCKER 0-1 that VAT computation differences are expected and should NOT block — only large absolute discrepancies (>30%) in gross values are blocking indicators.

---

### F-06 — WARNING: ₱1M total overlap variance is ambiguous and likely too tight

**Location:** Plan Phase 0, HARD BLOCKER 0-1

**Analysis:**

With ~6 overlap days and ~45 stores, if even 20 stores were active on FoodPanda during the overlap, that is 120 store-day comparisons. A systematic 1% gross vs net imputation difference on ₱100K average store-day = ₱120K total. A 5% difference = ₱600K. This is within the ₱1M threshold, but only barely. On high-sales days (weekends, holidays), the total can easily exceed ₱1M from pure methodology differences.

The plan's documented Supabase numbers show Mosaic Mar total = ₱4.7M net across 8,477 orders. If the overlap (6 days) accounts for ~50% of those orders, that is ~₱2.35M net. Legacy for the same 6 days would be approximately the same amount gross but ~12% more as net-from-gross = ₱2.63M. Systematic overlap variance = ~₱280K, well under ₱1M. But this is a fleet-level number — per-store-day thresholds are more likely to false-trigger.

**Recommendation:** Make HARD BLOCKER 0-1 two separate checks:
1. Total overlap variance in GROSS values (not net) > ₱2M: BLOCK (genuine data issue)
2. Total overlap variance in net values: WARNING only (expected from VAT methodology)
This prevents the baseline audit from blocking on methodology-only differences.

---

### F-07 — WARNING: Mosaic-wins has no completeness threshold — partial sync beats complete legacy

**Location:** Plan Design Rationale "Why Mosaic wins on overlap"

**Analysis:**

The plan states: "Once a store is on Mosaic, the Google Sheet is redundant." This is true for a fully synced day. But Mosaic's sync from FoodPanda's aggregator API can be delayed or interrupted. Historical evidence: the plan itself notes that `_FOODPANDA_MOSAIC_START` was bumped from Mar 26 to Mar 27 because "2026-03-25 and 2026-03-26 were PARTIAL Mosaic days" (line 29-30).

If Mosaic captured 40% of orders on Mar 26 (partial sync day) and the FULL OUTER JOIN sees Mosaic > 0 for that (store, day), Mosaic wins — discarding the complete legacy data for that store-day. The resulting total for Mar 26 would be systematically understated.

**No fix exists within the plan's architecture** (the FULL OUTER JOIN design has no row-count signal). Recommended mitigation: add a heuristic completeness guard in `_get_unified_foodpanda_totals`: if `mosaic_orders < legacy_orders * 0.5` for a given (store, day) AND `mosaic_gross < legacy_gross * 0.5`, prefer legacy. Document this in the code with an explicit "partial-sync guard" comment.

Alternatively, the agent executing S191 should check the Phase 0 baseline audit specifically for Mar 25-26 overlap days to see if partial-sync stores exist, and document them in `BASELINE_SUMMARY.md` before choosing Mosaic-wins unconditionally.

---

### F-08 — WARNING: `_build_comparisons` uses raw `_aggregate_sales` — comparison deltas will be distorted

**Location:** `sales_dashboard.py:1760-1803`

**Evidence:**
```python
prev = _aggregate_sales(prev_rows) if prev_rows else {}
last_year = _aggregate_sales(last_year_rows) if last_year_rows else {}
```

`_build_comparisons` computes previous-period and year-over-year deltas by calling `_aggregate_sales` directly without `_apply_mosaic_channel_split`. For comparison periods that include legacy FP data (Feb 2026, Feb 2025 if available), the baseline `gross_sales` is sourced from the MV's `total_gross_sales` which includes `foodpanda_subtotal` (legacy column, correct for those periods). For March 2026 current period post-S191, the headline `gross_sales` will include unified FP (~₱21.7M). The previous period (Feb 2026 as the 1-month lookback) will use the MV's `total_gross_sales` which ALSO includes the legacy FP correctly for February. So the delta calc may actually be correct for gross — the MV already includes legacy FP in `total_gross_sales`.

However the per-channel breakdown in comparison payloads (`baseline_gross_sales`) is MV-only, while the current period is now unified. Channel-level comparison features (if any frontend uses `foodpanda_sales` from the comparison baseline) will be inconsistent.

**Risk level:** Moderate. The headline gross delta should be directionally correct since the MV's `total_gross_sales` includes legacy FP. But any user trying to do channel-level period comparison will see a misleading apples-to-oranges comparison (unified current vs MV-only baseline). Not blocking for S191, but should be documented as a known gap.

---

### F-09 — WARNING: `_sales_row_metrics` uses MV's `foodpanda_vat_deducted_sales` and is not in scope

**Location:** `sales_dashboard.py:2644-2657`

**Evidence:**
```python
def _sales_row_metrics(row: dict[str, Any]) -> dict[str, Any]:
    return {
        ...
        "delivery_sales_without_vat": (
            _to_float(row.get("website_non_cod_net_sales_without_vat"))
            + _to_float(row.get("web_cod_net_sales_without_vat"))
            + _to_float(row.get("foodpanda_vat_deducted_sales"))   # ← stale MV column
        ),
    }
```

This helper is called in at least one place in the comparison/effects calculation chain. After S191, `foodpanda_vat_deducted_sales` in the MV is functionally the same for legacy dates (it was correct before), but it remains ₱0 for post-cutover dates. For date ranges spanning both legacy and Mosaic periods, this helper will undercount delivery for Mosaic-period rows. Since the plan does not touch `_sales_row_metrics`, and the plan's Phase 3.6 audit specifically looks for `channel.*FoodPanda|foodpanda_orders` patterns, this reference using `foodpanda_vat_deducted_sales` may be missed.

**Required action:** Add `_sales_row_metrics` to the Phase 3.6 call-sites audit. Decide whether to fix it (replace with `_get_unified_foodpanda_totals` per-day lookup or simply zero the MV term and rely on the day-series correction) or explicitly document it as an unaddressed gap.

---

### F-10 — WARNING: Historical reporting inconsistency — financial close numbers will be retroactively changed

**Location:** Not in code — business impact of the data change

**Impact:**

S191 will increase reported March 2026 FoodPanda revenue from ~₱4.4M to ~₱21.7M on ALL analytics surfaces. Any financial close document, Apex P&L, commission report, or business review presentation that used the old dashboard numbers between 2026-03-31 and the S191 deploy date will be inconsistent with post-S191 figures. Specifically:
- Apex P&L March 2026 FoodPanda line: will be wrong vs dashboard
- Any board/management report using March dashboard screenshots: will be inconsistent
- Commission structures based on FP channel volume: recalculation may be needed
- Tax declarations that used the old numbers: MAY need amendment (if VAT is filed quarterly, the Mar FP revenues should already be captured in QR1 filings via FoodPanda's own records, but the ERP's reported number diverged)

**This is out of scope for S191 but Sam MUST be explicitly notified before deploy.** Suggested wording: "S191 will retroactively show ₱17M+ of FoodPanda sales that were always real but not appearing in the dashboard. No revenue is being added or removed — only the visibility. However, any existing report that used the old ₱4.4M figure should be noted as using pre-S191 (Mosaic-only) data."

---

### F-11 — INFO: GrabFood isolation is architecturally safe

**Analysis:**

`_apply_mosaic_channel_split` (lines 947-950) pops channels from the Mosaic-only split dict in this order: `pos`, `foodpanda`, `grabfood`, `webdelivery`. The plan (Phase 2.1) replaces `fp_bucket` with the output of `_get_unified_foodpanda_totals_aggregate` but leaves `gf_bucket = split.pop("grabfood", ...)` unchanged. Since the new unified helper ONLY queries FoodPanda channel rows (explicit `WHERE channel = 'FoodPanda'` in both Mosaic and legacy sides of the JOIN), GrabFood is structurally isolated.

The verification script's `grabfood` line-count assertion (count must equal pre-S191 count) provides a reasonable regression guard. F-11 is informational — no action needed beyond confirming the anti-regression count passes.

---

### F-12 — INFO: Rollback is functional but has a 300s window of stale unified data

**Rollback procedure (not in plan):**

1. Revert PR: `git revert <S191 commit>` or use GitHub PR revert
2. Redeploy: `/deploy-frappe`
3. Wait up to 300s for both `fp_unified` inner cache and `"summary"`/`"overview"` outer cache to expire

Post-rollback the dashboard returns to Mosaic-only FP (₱4.4M March). No database migration is needed since S191 is purely read-path logic. No new tables, columns, or stored data are introduced. Rollback risk is LOW.

**Recommended addition to plan:** Add a rollback step to Phase 4 explicitly stating: "If post-deploy L3 verification fails, revert via `git revert` and redeploy. Allow 300s for cache expiry before re-testing."

---

### F-13 — INFO: PostgREST fallback for FULL OUTER JOIN will be expensive under token-missing conditions

**Analysis:**

The fallback (Phase 1.2) must make two separate PostgREST calls:
- `v_pos_orders_live` filtered by `channel=FoodPanda`, for 2 months × 45 stores: potentially 8,000-15,000 rows
- `foodpanda_orders` filtered by `lower(order_status)='delivered'`: potentially 50,000+ rows for a 2-month window

PostgREST requires pagination at 1,000 rows/page. For `foodpanda_orders` this is 50+ sequential HTTP calls. The original `_get_mosaic_channel_split` fallback for a 14-day window was already "111 paginated requests × ~400ms = 45 seconds." A 60-day window with the legacy table adds significantly more. This path will time out in most serverless/Frappe contexts if SUPABASE_MGMT_TOKEN is ever missing.

**Recommendation:** Document in the fallback that a 60-day window may time out and add a `frappe.log_error` with estimated row counts. Alternatively, limit the fallback's date window to a shorter range (e.g., 14 days) and surface a "data incomplete — management token required" warning for longer ranges.

---

### F-14 — INFO: User-facing freshness warning string will be outdated after S191

**Location:** `sales_dashboard.py:1296-1300`

**Evidence:**
```python
if start_day < _FOODPANDA_MOSAIC_START:
    warnings.append(
        "FoodPanda source split at 2026-03-27: earlier dates come from the legacy "
        "foodpanda_orders Google Sheet (frozen 2026-03-31), later dates come from "
        "Mosaic pos_orders. Historical totals are complete."
    )
```

After S191, this statement is still factually true (data sources are the same), but the framing is misleading. The warning implies users might see incomplete or split data, but after S191 the union is seamless. The "source split" language may cause confusion.

**Recommended update:** Change to: "FoodPanda data for dates before 2026-03-27 comes from the legacy Google Sheet (frozen 2026-03-31). Data for dates on or after 2026-03-27 comes from Mosaic POS. Both sources are unified — historical totals are complete." Add to Phase 2.4 task.

---

## Blocking Actions Required Before S191 Executes

The following issues MUST be resolved before the executing agent proceeds:

1. **F-01 (CRITICAL):** Add Phase 2 or Phase 3 task to remove `foodpanda_vat_deducted_sales` from the `superadmin_delivery_wo_vat` accumulator in `_aggregate_daily_series` (line 2061). Without this, the time-series and CSV export will double-count FP delivery for all legacy dates.

2. **F-04 (CRITICAL):** Add a Phase 2 task to bump outer cache prefixes to `"summary_v2"` / `"overview_v2"` (following the `"freshness_v2"` precedent at line 743). Otherwise users may see stale Mosaic-only FP data for up to 300s post-deploy.

3. **F-05/F-06 (WARNING):** Revise HARD BLOCKER 0-1 thresholds:
   - Single-store-day BLOCKING threshold: raise from ₱50K to ₱150K OR switch to >25% relative difference in gross values
   - Total overlap variance: change from blocking on net difference to blocking on gross difference >₱2M; net-only difference is expected from VAT methodology asymmetry

## Recommended Additions (Non-Blocking)

4. **F-07:** Add a partial-sync guard in `_get_unified_foodpanda_totals`: if `mosaic_orders < legacy_orders * 0.5` AND `mosaic_gross < legacy_gross * 0.5` for a given (store, day), prefer legacy. Document as "partial-sync guard."

5. **F-08:** Document in Phase 4 closeout that comparison period baselines (previous period, YoY) use MV-sourced `_aggregate_sales` without unified FP split. Known gap, not fixed in S191.

6. **F-09:** Add `_sales_row_metrics` to the Phase 3.6 call-sites inventory. Decide fix vs. document gap.

7. **F-10:** Add a deploy-time notification step in Phase 4: "Notify Sam that March and February FoodPanda totals will retroactively increase in all analytics surfaces. Existing reports using pre-S191 numbers should be noted as Mosaic-only-era data."

8. **F-12:** Add explicit rollback steps to Phase 4 closeout documentation.

9. **F-14:** Update freshness warning string (line 1297-1300) to remove misleading "source split" language.

---

## Audit Confidence

- Code read: `sales_dashboard.py` lines 820-1300, 1460-1520, 1760-1815, 1960-2110, 2350-2400, 2480-2530, 2630-2660, 2790-2970, 3240-3300 (targeted reads, not exhaustive)
- Plan read: complete (420 lines)
- Callers verified via grep: `_get_mosaic_channel_split`, `_get_store_channel_split_map`, `_get_mosaic_channel_split_per_day`, `_apply_mosaic_channel_split`, `foodpanda_orders`, `foodpanda_vat_deducted_sales`, `_FOODPANDA_MOSAIC_START`
- Findings F-01 and F-04 are HIGH confidence based on direct code evidence
- Findings F-05/F-06 are MEDIUM confidence — require actual overlap data counts from Phase 0 to confirm false-trigger rate
- Finding F-07 is MEDIUM confidence — requires checking Mosaic sync reliability history
- Findings F-08/F-09 are HIGH confidence based on code read
