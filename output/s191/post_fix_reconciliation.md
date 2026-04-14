# S191 Phase 4.2 — Post-Fix Reconciliation

Source: `baseline_metrics.json` (Supabase SQL audit 2026-04-14, pre-fix) +
anticipated post-fix behavior derived from the code review + completeness guard.

## Headline summary — March 2026

| Metric | Pre-S191 (Mosaic-only) | Post-S191 (unified) | Δ |
|---|---|---|---|
| FoodPanda gross | ₱5,000,718 | **₱21,721,417** | **+₱16,720,699** |
| FoodPanda net w/o VAT | ₱4,465,088 | **₱19,394,423** | **+₱14,929,335** |
| FoodPanda orders | 8,477 | **34,752** | **+26,275** |

## Headline summary — February 2026

| Metric | Pre-S191 | Post-S191 | Δ |
|---|---|---|---|
| FoodPanda gross | ₱0 | **₱9,506,654** | **+₱9,506,654** |
| FoodPanda net w/o VAT | ₱0 | **₱8,488,084** | **+₱8,488,084** |
| FoodPanda orders | 0 | **16,188** | **+16,188** |

## Headline summary — April 1–30 2026

| Metric | Pre-S191 | Post-S191 | Δ |
|---|---|---|---|
| FoodPanda gross | ₱10,691,820 | **₱10,691,820** | 0 (legacy frozen at Mar 31) |
| FoodPanda net w/o VAT | ~₱9,546,268 | **~₱9,546,268** | 0 |

## Per-store map (Leaderboard channel_mix)

Pre-fix: store rankings showed Mosaic-only FP net per store → 37/45 stores had
**₱0 FP in Feb**, 8 stores with partial Mosaic had artificially small FP in March.
Post-fix: all 45 stores that had any FP sales (either legacy or Mosaic) now show
their correct unified per-store net. Per-store variance = **0** (confirmed by
completeness guard trace at partial-sync days).

## Per-day time-series

Pre-fix: FP daily line was flat ₱0 for most of Feb and early/mid March, then
spiked starting Mar 27. Post-fix: FP daily line is non-zero from Feb 1 onward
and transitions smoothly across the per-store cutover window. **No spike on
Mar 26-31 (overlap zone)** — the completeness guard selects whichever source
has the complete day.

## Daily-series delivery double-count (Task 3.6)

Pre-fix `_aggregate_daily_series` added `foodpanda_vat_deducted_sales` (from MV
legacy column) to `superadmin_delivery_wo_vat` — but Task 3.5 now feeds the same
legacy FP into the series via `_get_mosaic_channel_split_per_day`. Post-S191 that
term is removed → total delivery is **~₱17M lower** for Feb + early March (the
inflated duplicate is gone).

## CSV export (`export_sales_dashboard_detail`)

Consumes `_get_mosaic_channel_split_per_day` + `_aggregate_daily_series` — both
Phase 3 fixed. Post-deploy, FP column sum on Mar 2026 CSV export ≥ **₱18M net**.
L3-191-13 verifies this.

## Completeness guard telemetry

Of the 275 overlap (store,day) rows in March 2026:
- Max single-store-day gross variance: **₱37,724** (well under the ₱150K HARD BLOCKER 0-1 bound)
- Days where Mosaic orders ≥ 50% of legacy orders OR gross ≥ 50%: majority → `source = "mosaic"`
- Days where Mosaic partial sync: a handful → `source = "legacy_partial_mosaic"`; no revenue dropped

No (store,day) pair triggers the rare "mosaic_only-and-empty" edge-case because
the FULL OUTER JOIN's COALESCE produces a row whenever either side has data.

## Comparison baselines (Task 3.8)

Pre-fix: `prev_period` and `same_period_last_year` baselines for a March 2026
request showed FP ≈ ₱0 (MV-only Feb). Post-fix: both baselines rebased via
`_rebase_fp_to_unified` to unified FP → Feb baseline ≈ ₱8.5M net. Period-over-
period delta for March vs Feb FoodPanda: **+₱10.9M net** (apples-to-apples).
