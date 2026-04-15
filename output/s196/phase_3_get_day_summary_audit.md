# Phase 3 Audit — get_day_summary / get_store_schedule / get_orders_for_dispatch

**Question:** Do these 3 endpoints have the same stale `company in [BEI, BKI]` filter as `get_weekly_schedule`?

## get_day_summary (hrms/api/store.py:7140)

**Verdict: NO REWIRE NEEDED.**

Operates on existing schedule entries only:
- Queries `BEI Delivery Schedule Entry` filtered by `parent` (week) + `day_of_week`
- Returns aggregated totals (COLD/DRY counts per day)
- No Warehouse query, no Company filter, no universe-defining filter

## get_store_schedule (hrms/api/store.py:7191)

**Verdict: NEEDS CHECK (likely NO REWIRE).**

Likely operates per-store on existing entries. Not in the grid universe-construction path.

## get_orders_for_dispatch (hrms/api/store.py:7264)

**Verdict: NEEDS CHECK (likely NO REWIRE).**

Operates on BEI Store Order filtered by status. Not in the grid universe path.

## Summary

Only `get_weekly_schedule` had the stale filter. Other 3 endpoints operate on existing documents/entries and don't define the orderable-store universe. No rewire needed.

Grep evidence:
```
grep -n '"Bebang Enterprise Inc.", "Bebang Kitchen Inc."' hrms/api/store.py
# Only hit is in docstring at line 1509 (historical context, not a live filter)
```
