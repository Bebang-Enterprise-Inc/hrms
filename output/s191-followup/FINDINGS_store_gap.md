# Analytics Store-Gap Investigation — 2026-04-15

Triggered by Sam's observation and Dave's report:
> Frappe Analytics only counts 36 stores vs 48 total stores
> Superadmin POS orders only counts 44 stores vs 48 stores
> Top 5 SM stores (Sta. Rosa, Marikina, North EDSA, SJDM, Taytay) — FoodPanda orders not translating

This is **NOT an S191 regression.** It's a pre-existing data-plumbing gap that S191's FP recovery made more visible.

## Numbers — verified against live Supabase + Frappe + Analytics API (2026-04-15)

| Source | Count | Note |
|---|---|---|
| Bebang Halo-Halo operational universe | **48** | Sam / Dave's claim — operational store count |
| `v_pos_orders_live` distinct location_id (last 60 days, PAID) | **44** | Matches Dave's "Superadmin POS 44" |
| `v_pos_orders_live` w/ channel=FoodPanda | **43** | |
| `foodpanda_orders` legacy table (last 90 days, delivered) | **45** | |
| `sales_dashboard_daily_store_metrics` MV (last 60 days) | **45** | Best ground-truth we have in Supabase |
| Union of all Supabase sources | **45** | 3 stores not in any Supabase table — likely new-opening pipeline gap |
| Frappe **Analytics scope** (`get_sales_dashboard_overview`) | **36 unique** (37 rows, one duplicate location_id 2548) | Matches Dave's "Analytics 36" |

**The analytics shows 36 unique stores.** That's a **gap of 9 stores** vs the 45 that have data in Supabase, and a gap of **12 stores** vs the 48 operational count (9 missing from Analytics + 3 that aren't in any data source yet).

## The 9 stores with data but missing from Analytics

| location_id | Store name (from MV) | Frappe Warehouse record found? | Why Analytics drops it |
|---|---|---|---|
| 2177 | Megaworld Paseo Center | not named `Megaworld Paseo Center` in Frappe | mapping miss |
| 2338 | SM Megamall | `Bebang Enterprise Inc. - SM Megamall` | mapping CSV expects `SM Megamall` |
| 2339 | SM Manila | `Bebang Enterprise Inc. - SM Manila` | mapping CSV expects `SM Manila` |
| 2340 | SM Southmall | `Bebang Enterprise Inc. - SM Southmall` | mapping CSV expects `SM Southmall` |
| 2342 | Robinsons Antipolo | `Bebang Enterprise Inc. - Robinsons Antipolo` | mapping CSV expects `Robinsons Antipolo` |
| 2408 | Robinson Imus | `Bebang Mega Inc. - Robinsons Imus` (inferred; also `Stores - BMI-RI`) | mapping CSV expects `Robinson Imus` |
| 2430 | Robinson General Trias | `Bebang Mega Inc. - Robinsons Gen Trias` | mapping CSV expects `Robinson General Trias` |
| 2558 | Sta. Lucia East Grand Mall | `Bebang SM Marikina Inc. - Sta Lucia` (inferred) | mapping CSV expects `Sta. Lucia East Grand Mall` |
| 9001 | NAIA Terminal 3 | `NAIA T3` | mapping CSV expects `NAIA Terminal 3`, Frappe has `NAIA T3` |

## Root cause

The Analytics scope is built by `_resolve_allowed_store_scope` → `_filter_sales_warehouses` → `lookup_location_id(warehouse_name, warehouse_record_name)` (see `hrms/api/sales_dashboard.py:501-515` and `hrms/utils/sales_location_mapping.py:57`).

`lookup_location_id` reads `hrms/fixtures/sales_dashboard_store_mapping.csv` (46 mapped rows). If **neither** the `warehouse_name` **nor** the `warehouse_record_name` (minus company suffix) matches the mapping CSV exactly, the warehouse is **silently dropped** from scope.

**S188 per-store company restructure (2026-04-13, merged #562) renamed Warehouse records to the `<Company> - <Store>` pattern** but the mapping CSV still contains only the old short names (`SM Megamall`, `SM Manila`, `Robinson Imus`, etc.). So the lookup fails for the 9 new-named stores and they disappear from Analytics.

The 3 stores "missing from all data sources" are most likely brand-new store openings (post-March) whose sales pipeline (Mosaic POS upload or legacy FP export) hasn't landed data yet, or stores that are physically open but have been paused operationally. Those are an **ops-pipeline problem**, not an Analytics code problem.

## Top 5 SM stores FP variance (Dave's item 3.2)

SM Sta. Rosa (2774), SM Marikina (2317), SM North EDSA (2284), SM SJDM (2481), SM Taytay (2812) — **all 5 are IN the Analytics scope already** (confirmed from the 37-store scope dump). So this is not a "store missing" problem for those 5.

The variance Dave describes ("majority is due to Foodpanda orders not being counted, does not translate to pickup sales") is an S191-adjacent issue about **Mosaic FP data completeness** at those stores. With S191's completeness guard, partial-sync Mosaic days fall back to legacy; but if BOTH sources are incomplete for a given day, the displayed FP is understated. Separate probe needed (see Followup #2 below).

## What to do (proposed)

### Fix #1 (required, fast) — update `hrms/fixtures/sales_dashboard_store_mapping.csv`

Add the following 9 rows so `lookup_location_id` matches the S188-renamed Frappe Warehouse records:

```
warehouse_name,warehouse_record_name,company,location_id
Bebang Enterprise Inc. - SM Megamall,Bebang Enterprise Inc. - SM Megamall - BEI-SMG,Bebang Enterprise Inc. - SM Megamall,2338
Bebang Enterprise Inc. - SM Manila,Bebang Enterprise Inc. - SM Manila - BEI-SMM,Bebang Enterprise Inc. - SM Manila,2339
Bebang Enterprise Inc. - SM Southmall,Bebang Enterprise Inc. - SM Southmall - BEI-SMS,Bebang Enterprise Inc. - SM Southmall,2340
Bebang Enterprise Inc. - Robinsons Antipolo,Bebang Enterprise Inc. - Robinsons Antipolo - BEI-RPA,Bebang Enterprise Inc. - Robinsons Antipolo,2342
Bebang Mega Inc. - Robinsons Imus,Bebang Mega Inc. - Robinsons Imus - BMI-RI,Bebang Mega Inc. - Robinsons Imus,2408
Bebang Mega Inc. - Robinsons Gen Trias,Bebang Mega Inc. - Robinsons Gen Trias - BMI-RGT,Bebang Mega Inc. - Robinsons Gen Trias,2430
Bebang SM Marikina Inc. - Sta Lucia,Bebang SM Marikina Inc. - Sta Lucia - BSMM-SL,Bebang SM Marikina Inc. - Sta Lucia,2558
NAIA T3,NAIA T3 - BEI,HALO-HALO TERMINAL FOOD CORP.,9001
```

(Plus whatever Frappe Warehouse record exists for Megaworld Paseo Center, location_id 2177 — needs one more lookup.)

Deploy path: commit to `hrms/fixtures/sales_dashboard_store_mapping.csv`, push, PR, Sam merges + deploys. No Python changes, no DocType changes, no SQL migration. `load_sales_location_mapping` is `@lru_cache(maxsize=1)` so the worker needs to restart (standard Frappe deploy handles this).

### Fix #2 (recommended) — make the lookup log misses instead of silently dropping

`_filter_sales_warehouses` silently drops warehouses with no location_id. This class of bug cost us weeks of wrong dashboards. Change the filter to:
- On miss: call `frappe.log_error(f"Sales scope drop: {warehouse_name} ({record_name}) — add to sales_dashboard_store_mapping.csv", "Sales scope unmapped warehouse")` — which feeds Sentry via DM-7.
- Next time a warehouse is renamed, Sam sees a Sentry alert instead of months of quiet data loss.

### Fix #3 (ops, outside Analytics) — investigate the 3 stores with zero data

Compare the operational 48-store list against the 45 with data. The 3 missing are likely:
- New openings whose Mosaic / FP pipeline isn't wired
- Or suspended/paused stores still counted by ops

Needs operational input from Sam/Dave to confirm which stores and why.

### Followup #2 — investigate the 5 SM stores FP variance

Separate probe. Compare per-day, per-source FP totals for location_ids 2774, 2317, 2284, 2481, 2812 and identify which days / source is incomplete vs validated ops numbers.

## Evidence files
- `output/s191-followup/store_gap_investigation.py` — investigation script (reproducible)
- `output/s191-followup/store_gap_output.txt` — run log
- `output/s191-followup/mv_stores.txt` — 45 MV stores with names
- `output/s191-followup/frappe_warehouses.txt` — all Frappe Warehouse leaf rows
- `output/s191-followup/analytics_scope.txt` — 37 stores currently returned by Analytics
- `output/s191-followup/store_gap_result.json` — machine-readable set diffs
