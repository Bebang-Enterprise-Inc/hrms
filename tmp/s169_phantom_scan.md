# S169 T0.3 — Phantom Scan Report

**Date:** 2026-04-07
**Branch:** s169-mosaic-order-lifecycle-tombstone-webhook
**Source:** Supabase prod `csnniykjrychgajfrgua`, table `pos_orders`
**Query window:** `business_date >= '2026-01-01'`

## Definition of "phantom group"

Distinct rows in `pos_orders` sharing the same
`(location_id, business_date, bill_number, original_gross_sales, billed_at)`
tuple with `COUNT(*) > 1`. Each such group represents at least one duplicate
ingestion of the same Mosaic bill — the canonical phantom-void footprint S169
is designed to detect.

## Result

| Metric | Value |
|---|---|
| Total phantom groups since 2026-01-01 | **535** |
| Plan threshold (HARD BLOCKER) | > 50 |
| Status | **HARD BLOCKER TRIGGERED (10.7x threshold)** |

## Distribution by business_date (top 30)

| business_date | groups |
|---|---|
| 2026-04-07 | 77 |
| 2026-04-06 | 20 |
| 2026-04-05 | 65 |
| 2026-04-04 | 41 |
| 2026-04-03 | 20 |
| 2026-04-02 | 87 |
| 2026-04-01 | 25 |
| 2026-03-31 | 14 |
| 2026-03-30 | 16 |
| 2026-03-29 | 13 |
| 2026-03-28 | 14 |
| 2026-03-27 | 14 |
| 2026-03-26 | 10 |
| 2026-03-23 | 3 |
| 2026-03-22 | 3 |
| 2026-03-21 | 2 |
| 2026-03-20 | 4 |
| 2026-03-18 | 2 |
| 2026-03-17 | 1 |
| 2026-03-16 | 1 |
| 2026-03-15 | 1 |
| 2026-03-13 | 3 |
| 2026-03-12 | 13 |
| 2026-03-10 | 3 |
| 2026-03-09 | 3 |
| 2026-03-08 | 2 |
| 2026-03-07 | 2 |
| 2026-03-06 | 1 |
| 2026-03-05 | 4 |
| 2026-03-04 | 2 |

## Pattern observation

- Background phantom rate prior to 2026-03-26: roughly 1–4 groups per business
  day — consistent with the original "single known incident" model.
- **Inflection point on 2026-03-26**, then a clear regime shift to 10–87
  groups/day from 2026-03-27 onward.
- Last 7 business days alone account for **335 groups (62.6% of total)**.
- The scan covers all 47 stores; multiple `location_id`s appear in the sample
  (e.g., 2216, 2219, 2222), so this is not isolated to one location.

## Sample (top 20 most recent)

See `tmp/_phantom_sample.json` for raw rows.

```
location_id | business_date | bill_number | gross   | billed_at           | cnt
2216        | 2026-04-07    | 45017       |   714.00| 2026-04-07 04:08:23 | 2
2216        | 2026-04-07    | 45083       |   714.00| 2026-04-07 06:32:24 | 2
2216        | 2026-04-07    | 45085       |  1428.00| 2026-04-07 06:33:42 | 2
2216        | 2026-04-07    | 45087       |   952.00| 2026-04-07 06:39:56 | 2
2216        | 2026-04-07    | 45102       |  1358.00| 2026-04-07 07:08:14 | 2
2216        | 2026-04-07    | 45106       |  1666.00| 2026-04-07 07:12:59 | 2
... (15 more in sample file)
```

## STOP NOTICE — HARD BLOCKER per Plan T0.3

> Plan rule: "**HARD BLOCKER:** If the scan reveals >50 phantom groups (10x the
> single known incident), STOP and present a scope-expansion decision to Sam — a
> massive phantom population might indicate a different root cause than
> void-and-retry."

**Action required from Sam:** scope decision before Phase 1 begins.

**Working hypothesis from the date distribution:**
The 2026-03-26 inflection point and the steady ~30–80 groups/day cadence since
then strongly suggest a **systemic ingestion duplication** (e.g., overlapping
sync windows, retry-on-timeout without idempotency, or a recently introduced
double-trigger), **not** the original "POS user voids and retries with same
bill number" theory. The void-and-retry root cause should produce sporadic,
not daily-bulk, duplicates.

**Decision options to present:**

1. **Stay with current S169 scope** (lifecycle + tombstone + webhook) and
   accept that the underlying duplication source is broader. S169 will still
   correctly tombstone the duplicates as they appear via webhook, but the
   underlying ingestion-side bug will keep generating fresh duplicates.

2. **Pause S169, open S170-investigation** to root-cause the 2026-03-26
   ingestion regime change first (`scripts/sync_pos_to_supabase.py` recent
   diffs, sync schedule, retry semantics), then resume S169 with a clean
   baseline.

3. **Expand S169 scope** to include both (a) the lifecycle/tombstone webhook
   and (b) the ingestion-side dedupe fix — likely an idempotent upsert key on
   `(location_id, mosaic_order_id)` instead of natural key tuples.

**Recommendation:** Option 2 (pause + investigate). The 535-group population
makes it impossible to write a clean Phase 4 verification (`backfill_count`
will be unbounded), and a tombstone webhook on top of an ingestion bug will
mask the real defect.

**Phase 0 cannot proceed past T0.3 without Sam's decision.** T0.4–T0.7
artifacts are still produced for context, but no Phase 1 work should begin.
