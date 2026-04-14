---
sprint_id: S191
sprint_name: "FoodPanda Unified Source — Per-Store Rolling Cutover Fix"
branch: s191-foodpanda-unified-source
repos:
  - BEI-ERP (hrms — backend only)
branches:
  hrms: s191-foodpanda-unified-source
depends_on: [S176]
status: PLANNED
planned_date: 2026-04-14
amended_date: 2026-04-14
amendment_version: v2
owner: sam@bebang.ph
signoff_authority: single-owner
estimated_units: 42
hard_unit_ceiling: 55
session_scope: single-agent-single-session
plan_file: docs/plans/2026-04-14-sprint-191-foodpanda-unified-source.md
registry_row: |
  | `S191` | Sprint 191 | `s191-foodpanda-unified-source` (hrms) | — | PLANNED 2026-04-14 — FoodPanda Unified Source: fix missing ₱17M+ March FP sales. |
completed_date: null
execution_summary: null
---

# S191 — FoodPanda Unified Source (Per-Store Rolling Cutover Fix)

## Amendment Log

**v2 (2026-04-14):** Applied 12 audit-driven amendments across 3 domain audits (backend, architecture, cold-start). No scope removed. All improvements strengthen correctness, regression safety, and rollback posture. Unit budget raised 28 → 42 to reflect 5 new tasks (0.4 dedup, 0.5 caller inventory, 2.5 outer cache bump, 3.6 daily-series double-count fix, 3.7 sales_row_metrics fix, 3.8 _build_comparisons fix, 3.9 export_sales_dashboard_detail verify, 4.3 rollback runbook, 4.4 sam pre-deploy notice) — each was a HIDDEN gap that would have caused corrupt success.

| ID | Fix | Location |
|---|---|---|
| B-1 | Remove `foodpanda_vat_deducted_sales` add-back in `_aggregate_daily_series` → stops daily-series ₱17M double-count | Task 3.6 |
| B-2 | Preserve `float`-per-channel return shape in `_get_store_channel_split_map` + `_get_mosaic_channel_split_per_day` → prevents leaderboard dict-vs-float corruption | Tasks 3.2, 3.5 |
| B-3 | Replace `fp_bucket = split.pop("foodpanda"` (not just add new line) → prevents silent revert | Task 2.1 |
| B-4 | Verify `export_sales_dashboard_detail` picks up unified FP + L3-191-13 | Task 3.9 |
| B-5 | Bump outer cache prefix `overview` → `overview_s191` → invalidates pre-deploy cached payloads | Task 2.5 |
| B-6 | `order_id` dedup check in Phase 0 + `DISTINCT ON (order_id)` if dupes found | Tasks 0.4, 1.1 |
| B-7 | L3 thresholds labeled NET (₱18M) not gross (₱20M) | L3-191-01/05 |
| B-8 | PostgREST fallback uses `ilike.delivered` (not `eq.delivered`) + refuses > 45-day ranges | Task 1.2 |
| B-9 | Variance thresholds on GROSS not net; ₱2M total / ₱150K single-day (raised) | Task 0.3, HARD BLOCKER 0-1 |
| B-10 | Fix `_sales_row_metrics` to use unified FP | Task 3.7 + L3-191-15 |
| B-11 | Fix `_build_comparisons` to use unified FP for baselines | Task 3.8 + L3-191-14 |
| B-12 | Completeness guard: Mosaic-wins only when ≥ 50% of legacy rows/gross | Task 1.1 |

**v1 (2026-04-14):** Initial plan.

## Executive Summary

Sam (CEO) reported on 2026-04-14 that March FoodPanda sales in the Analytics dashboard show **₱4,465,227** (Mosaic-only) instead of the actual **~₱21.7M** (legacy Google Sheet + Mosaic combined). Investigation confirmed the `foodpanda_orders` Google Sheet table still has 50,525 delivered orders for Feb 1 – Mar 31 (~₱31.2M total), but the S176 `_apply_mosaic_channel_split` logic **overwrites** the legacy FoodPanda totals with Mosaic-only data, dropping ~₱17M of pre-cutover legacy sales from every Analytics surface.

**Additional complication (CEO clarification 2026-04-14):** The FoodPanda cutover from Google Sheet to Mosaic POS API **happened per store over ~1 week** in late March, not on a single global date. The current `_FOODPANDA_MOSAIC_START = 2026-03-27` constant is fundamentally wrong — each store has its own cutover moment.

**Fix:** Replace the global-date cutover with a **per-(location_id, business_date) FULL OUTER JOIN** of the two sources. Mosaic wins when both have data for a given store-day (authoritative post-cutover). Legacy Google Sheet fills any store-day without Mosaic data. Zero loss, zero double-count, regardless of when each store transitioned.

**Scope:** Backend-only (no frontend changes, no new API endpoints, no schema changes). Three existing functions in `hrms/api/sales_dashboard.py` get updated:
1. `_get_mosaic_channel_split()` (line 825) — headline Channel Mix donut
2. `_get_store_channel_split_map()` (line 1049) — per-store channel mix on Leaderboard / Store Detail
3. `_get_mosaic_channel_split_per_day()` (line 1962) — daily time-series chart

**Out of scope:** GrabFood (CEO confirmed BEI was not selling on GrabFood pre-April; post-April rollout is still incomplete). Do NOT touch GrabFood logic in this sprint.

**Total: 28 units, 5 phases.** Single-agent single-session, backend-only.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

Two CEO directives on 2026-04-14:

1. "Our FoodPanda sales for March were 20m+ not 4.4 million" — Analytics dashboard is under-reporting by ~₱17M
2. "Not all stores were transitioned from the manual sheet to POS in the same date, it happened over 1 week. so how to make sure nothing is missing or lost?" — rejects any global-date cutover fix

Verified numbers from Supabase (2026-04-14 audit):

| Period | Legacy `foodpanda_orders` (Google Sheet) | Mosaic `pos_orders` WHERE channel=FoodPanda |
|---|---|---|
| Feb 2026 | 16,188 orders / ₱9.5M subtotal | 0 |
| Mar 2026 | 34,337 orders / ₱21.7M subtotal | 8,477 orders / ₱4.7M net |
| Apr 2026 | 0 (frozen Mar 31) | 16,583 orders / ₱9.5M net |
| **Total** | **50,525 orders / ₱31.2M** | 25,060 orders / ₱14.2M |

Dashboard currently shows Mosaic-only for March → ₱4.4M instead of ₱21.7M. For Feb it shows ₱0 because `_apply_mosaic_channel_split` zeroes out legacy too.

### Why per-(store, day) FULL OUTER JOIN (not a global cutover date)

The CEO explicitly rejected any global cutover date because the FoodPanda-to-Mosaic transition happened per store over ~1 week. A global date either:
- Drops late-transitioning stores' legacy data (if cutover is too early)
- Double-counts early-transitioning stores' Mosaic data (if cutover is too late)

A per-store cutover date would work but requires tracking the transition date per store — fragile and manually maintained.

**The union-at-cell-grain approach eliminates the problem:**
```sql
WITH fp_mosaic AS (
    SELECT location_id, business_date, SUM(gross_sales) gross, SUM(net_sales) net, COUNT(*) orders
    FROM v_pos_orders_live
    WHERE channel = 'FoodPanda' AND payment_status = 'PAID'
      AND business_date BETWEEN $start AND $end
      AND location_id IN ($locations)
    GROUP BY 1, 2
),
fp_legacy AS (
    SELECT location_id, business_date, SUM(subtotal) gross, SUM(subtotal / 1.12) net, COUNT(*) orders
    FROM foodpanda_orders
    WHERE LOWER(order_status) = 'delivered'
      AND business_date BETWEEN $start AND $end
      AND location_id IN ($locations)
    GROUP BY 1, 2
)
SELECT
    COALESCE(m.location_id, l.location_id) AS location_id,
    COALESCE(m.business_date, l.business_date) AS business_date,
    COALESCE(m.gross, l.gross) AS gross,  -- Mosaic wins when both exist
    COALESCE(m.net, l.net) AS net,
    COALESCE(m.orders, l.orders) AS orders,
    CASE WHEN m.gross IS NOT NULL THEN 'mosaic' ELSE 'legacy_sheet' END AS source
FROM fp_mosaic m
FULL OUTER JOIN fp_legacy l
    ON m.location_id = l.location_id AND m.business_date = l.business_date
```

**Result per (store, day):**

| Mosaic has data | Legacy has data | Result | Source |
|---|---|---|---|
| Yes | No | Mosaic | Post-cutover for this store |
| No | Yes | Legacy | Pre-cutover for this store |
| Yes | Yes | Mosaic | Overlap period — Mosaic is authoritative |
| No | No | — | Store had no FP sales that day (skip row) |

No loss. No double-count. Works for any transition pattern.

### Why Mosaic wins on overlap

Two reasons:
1. **Mosaic is the authoritative post-cutover source** — once a store is on Mosaic, the Google Sheet is redundant (may be stale or incomplete). If both sources have data for the same (store, day), Mosaic is the newer reality.
2. **S176 hotfix #10 established this precedent** — the current code already prefers Mosaic on overlap dates (2026-03-26 to 2026-03-31) to avoid double-count. This sprint extends that preference to the per-store level.

### Why the gross/net computation differs between sources

| Source | Gross | Net (without VAT) |
|---|---|---|
| Mosaic `v_pos_orders_live` | `gross_sales` column (already computed) | `net_sales` column (already net of VAT) |
| Legacy `foodpanda_orders` | `subtotal` column | `subtotal / 1.12` (derived — FoodPanda doesn't expose VAT separately) |

This asymmetry is a known limitation of the legacy Google Sheet schema. Use `subtotal / 1.12` for net to match the existing MV logic (`sales_dashboard_daily_store_metrics.foodpanda_vat_deducted_sales` uses this formula — see MV definition line confirmed 2026-04-14).

### Known limitations

- **Legacy sheet is frozen at 2026-03-31** — after that date, only Mosaic has data. The JOIN handles this naturally (legacy side returns no rows for April+).
- **FoodPanda VAT imputation** — legacy net is `subtotal / 1.12`. If a FoodPanda order was VAT-exempt (e.g., senior discount), this formula slightly overstates VAT. Acceptable: the legacy sheet never tracked VAT exemptions individually; this is the baseline we're preserving.
- **Store closure days** — if a store had zero FP sales on a day, no row appears in either source. The FULL OUTER JOIN correctly produces no result for that (store, day) pair. Time-series aggregation must handle missing days via existing `COALESCE(fp.gross, 0)` patterns in the MV-consuming code.
- **GrabFood is out of scope** — do NOT apply this pattern to GrabFood. Per CEO: "ignore Grabfood because we were not selling on Grabfood pre april and we're not fully on Grab Food in all our stores yet." The existing Mosaic-only GrabFood logic stays unchanged.

### Source references (verified 2026-04-14)

- **Bug location:** `hrms/api/sales_dashboard.py:960-961` — `_apply_mosaic_channel_split` overwrites `summary["foodpanda_sales"]` with `fp_bucket` (Mosaic-only)
- **Current Mosaic-only helper:** `hrms/api/sales_dashboard.py:825-907` — `_get_mosaic_channel_split` queries `v_pos_orders_live` only
- **Per-store variant (also broken):** `hrms/api/sales_dashboard.py:1049` — `_get_store_channel_split_map`
- **Per-day variant (also broken):** `hrms/api/sales_dashboard.py:1962` — `_get_mosaic_channel_split_per_day`
- **Legacy table schema:** `foodpanda_orders` columns = `order_id`, `fp_restaurant_code`, `location_id` (int), `delivery_type`, `payment_type`, `payment_method`, `is_pro_order`, `order_status` (use `LOWER(order_status) = 'delivered'` filter), `order_received_at`, `accepted_at`, `delivered_at`, `cancelled_at`, `subtotal` (numeric — use this for gross), `packaging_charges`, `tax_charge`, `business_date` (date)
- **Mosaic table schema:** `v_pos_orders_live` columns = `location_id`, `business_date`, `channel` (text — filter `= 'FoodPanda'`), `payment_status` (filter `= 'PAID'`), `gross_sales`, `net_sales` (already net of VAT per CRITICAL comment at line 844), `vat_amount`
- **MV reference:** `sales_dashboard_daily_store_metrics` view definition confirms `foodpanda_subtotal` comes from legacy and uses `subtotal / 1.12` for net
- **Cutover constant to REMOVE/DEPRECATE:** `_FOODPANDA_MOSAIC_START = date(2026, 3, 27)` at `sales_dashboard.py:31`. Keep the constant in code but mark it as `# DEPRECATED S191: per-(store,day) JOIN replaces global date. Constant retained for the freshness warning at line 1296.`
- **SQL execution helper:** `_supabase_query_sql(sql: str)` at `sales_dashboard.py:229` — Mgmt API, single round-trip, handles the FULL OUTER JOIN in one call
- **PostgREST fallback pattern:** `_supabase_get_all(resource, params, page_size)` — used when `SupabaseMgmtTokenMissing`; see `_get_mosaic_channel_split` line 874-898 for the pattern
- **Cache pattern:** `_cache_get_or_set(cache_key, builder, 300)` with `_sales_dashboard_cache_key(prefix, location_ids, start_day=..., end_day=...)` — existing 300s TTL

---

## Agent Boot Sequence

1. **Read this plan fully.**
2. **Create backend branch:**
   ```bash
   cd F:/Dropbox/Projects/BEI-ERP
   git fetch origin production && git checkout -b s191-foodpanda-unified-source origin/production
   ```
3. **Read the bug site:** `hrms/api/sales_dashboard.py:825-1030` (existing `_get_mosaic_channel_split` + `_apply_mosaic_channel_split`).
4. **Read the two other variants:** `_get_store_channel_split_map` (line 1049+) and `_get_mosaic_channel_split_per_day` (line 1962+).
5. **Read the S176 hotfix comment block** at `_apply_mosaic_channel_split` (lines 916-945) to understand why the overwrite exists.
6. **Do not touch GrabFood logic.** CEO directive — GrabFood stays Mosaic-only.
7. **Do not modify frontend code.** Backend-only sprint.

---

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

---

## Requirements Regression Checklist

- [ ] Does the FoodPanda source logic use a FULL OUTER JOIN of `v_pos_orders_live` (Mosaic) and `foodpanda_orders` (legacy) at the (`location_id`, `business_date`) grain?
- [ ] When both Mosaic and legacy have data for the same (store, day), does Mosaic win? (HARD BLOCKER — CEO preference)
- [ ] When only legacy has data for a (store, day), is it preserved and included in totals?
- [ ] When only Mosaic has data for a (store, day), is it preserved and included in totals?
- [ ] Is the legacy net computed as `subtotal / 1.12` (matching existing MV logic)?
- [ ] Does the filter exclude non-delivered legacy orders: `LOWER(order_status) = 'delivered'`?
- [ ] Does the filter exclude unpaid Mosaic orders: `payment_status = 'PAID'`?
- [ ] Does the FoodPanda bucket in the result dict have the same shape as other buckets (`{"gross": float, "net_wo_vat": float, "orders": int}`)?
- [ ] Is GrabFood logic completely untouched? (HARD BLOCKER — CEO directive)
- [ ] Are all three functions updated consistently (`_get_mosaic_channel_split`, `_get_store_channel_split_map`, `_get_mosaic_channel_split_per_day`)?
- [ ] Does the cache key distinguish the new unified FP totals from the old Mosaic-only totals so post-deploy cache is invalidated?
- [ ] Does the verification baseline script confirm March 2026 FoodPanda ≥ ₱20M after the fix?
- [ ] Does every new/modified `@frappe.whitelist()` endpoint call `set_backend_observability_context()`? (Already present — verify only)
- [ ] Is the `_FOODPANDA_MOSAIC_START` constant still referenced by the freshness warning at line 1296? (Keep but mark deprecated)

**[AMENDED v2 — audit-driven checks; all 12 amendments surfaced here]:**

- [ ] **(B-1)** Was `+ _to_float(row.get("foodpanda_vat_deducted_sales"))` REMOVED from `_aggregate_daily_series` at line ~2061? `grep -c "foodpanda_vat_deducted_sales"` count is LOWER than pre-S191 baseline by exactly 1?
- [ ] **(B-2)** Do `_get_store_channel_split_map` and `_get_mosaic_channel_split_per_day` PRESERVE the `float`-per-channel return shape (NOT nested dict)? Consumer at line ~2502 still receives float?
- [ ] **(B-3)** Was `fp_bucket = split.pop("foodpanda"` pattern DELETED from `_apply_mosaic_channel_split`? Replaced with `split.pop("foodpanda", None)` on one line + `fp_bucket = fp_unified` on the next?
- [ ] **(B-4)** Is `export_sales_dashboard_detail` (line ~3261) verified to use unified FP via the fixed `_get_mosaic_channel_split_per_day` / `_aggregate_daily_series`? L3-191-13 added?
- [ ] **(B-5)** Was the outer cache key prefix bumped from `"overview"` to `"overview_s191"` in `_build_dashboard_overview_payload`? Any other FP-touching cache prefixes also bumped?
- [ ] **(B-6)** Did Task 0.4 dedup check run? If dupes found, does the legacy CTE use `DISTINCT ON (order_id)`?
- [ ] **(B-7)** Are L3 thresholds correctly labeled as NET (≥ ₱18M net, not ₱20M gross)? Phase 2.6 smoke test uses ≥ ₱18M?
- [ ] **(B-8)** Does the PostgREST fallback use `ilike.delivered` (case-insensitive) NOT `eq.delivered`? Does it refuse date ranges > 45 days without Mgmt token?
- [ ] **(B-9)** Phase 0 variance thresholds measure GROSS (not net), and are raised to ₱2M total / ₱150K single-store-day?
- [ ] **(B-10)** Was `_sales_row_metrics` (line ~2644) updated to use `_get_unified_foodpanda_totals`?
- [ ] **(B-11)** Was `_build_comparisons` (line ~1760) updated to override `prev["foodpanda_sales"]` / `prev["foodpanda_sales_without_vat"]` with unified values? AND recompute prev totals?
- [ ] **(B-12)** Does `_get_unified_foodpanda_totals` include the completeness guard (`mosaic wins only when mosaic_orders >= 0.5 * legacy_orders OR mosaic_gross >= 0.5 * legacy_gross`)? Emits `source = 'legacy_partial_mosaic'` for the partial-sync case?

---

## Surface Ownership Matrix

| Owner | Owned file globs |
|---|---|
| S191 backend | `hrms/api/sales_dashboard.py` — ONLY these functions: `_get_mosaic_channel_split` (lines 825-907), `_get_store_channel_split_map` (line 1049+), `_get_mosaic_channel_split_per_day` (line 1962+). May touch `_apply_mosaic_channel_split` (lines 910-1027) ONLY if the JOIN is implemented as a new helper function returning the same `fp_bucket` shape. |

**Protected surfaces (do not touch):**
- `hrms/api/sales_dashboard.py` — all other functions (S176 channel split infrastructure, S182 store rankings, S183 product analytics, S185 comparison logic, S187 leaderboard)
- `.github/workflows/*`
- `bei-tasks/**/*` — no frontend changes
- `lib/roles.ts` — no RBAC changes
- GrabFood logic everywhere — do not touch (CEO directive)
- WebDelivery logic — do not touch (out of scope)
- POS (pickup) logic — do not touch (already correct)

---

## Phase Budget Contract

| Phase | Name | Est. Units | Hard Cap |
|---|---|---|---|
| Phase 0 | Branch setup + baseline audit + dedup check + duplicate caller inventory | 5 | 7 |
| Phase 1 | Unified helper `_get_unified_foodpanda_totals` (with completeness guard + dedup) | 8 | 10 |
| Phase 2 | Wire into `_get_mosaic_channel_split` + fix `_apply_mosaic_channel_split` + bump outer cache prefix | 7 | 9 |
| Phase 3 | Wire into `_get_store_channel_split_map` + `_get_mosaic_channel_split_per_day` + FIX `_aggregate_daily_series` double-count + fix `_sales_row_metrics` + fix `_build_comparisons` + fix `export_sales_dashboard_detail` | 14 | 18 |
| Phase 4 | Verification + data audit + PR + closeout + rollback runbook | 8 | 11 |
| **Total** | | **42** | **55** |

---

## Phase Table

### Phase 0 — Branch setup + baseline audit (3 units)

**Goal:** Establish the ground-truth baseline for March 2026 FoodPanda so we can verify the fix. If Mosaic + legacy don't reconcile reasonably, we have a data quality issue to investigate BEFORE changing code.

| # | Task | MUST_MODIFY / Evidence |
|---|---|---|
| 0.1 | Create branch (see boot sequence) | `git branch --show-current` = `s191-foodpanda-unified-source` |
| 0.2 | Record base SHA in `output/s191/BASELINE.md` | File exists |
| 0.3 | **Run baseline audit SQL.** Query Supabase via `_supabase_query_sql` (or direct boto3 SSM if running locally): for each (location_id, business_date) in Feb-April 2026, compute legacy FP gross, Mosaic FP gross, overlap flag, and per-store first-Mosaic-day / last-legacy-day. Write results to `output/s191/baseline_audit.csv`. Also write a summary `output/s191/BASELINE_SUMMARY.md` with: total stores, total overlap-days, total GROSS variance (sum of abs(mosaic_gross - legacy_gross) on overlap days), total NET variance (same for net — expected to be higher due to `subtotal/1.12` approximation), per-store transition pattern. **HARD BLOCKER 0-1 (AMENDED v2):** Measure variance on GROSS only (not net) — legacy net is `subtotal/1.12` which systematically differs from Mosaic's exact VAT by up to 8%. If total GROSS overlap variance > ₱2M OR any single-store single-day GROSS variance > ₱150K (raised from ₱50K to account for high-volume stores like Trinoma/SM North), STOP and surface to user. If NET variance is 5-10% higher than GROSS variance, that's the VAT methodology gap — document it, proceed. | `output/s191/baseline_audit.csv` exists with ≥100 rows; `output/s191/BASELINE_SUMMARY.md` has 8 metrics (6 original + gross-vs-net variance split) |
| 0.4 | **[AMENDED v2 — audit fix B-6] Dedup check on `foodpanda_orders.order_id`.** Query: `SELECT order_id, COUNT(*) AS dupes FROM public.foodpanda_orders WHERE LOWER(order_status) = 'delivered' AND business_date BETWEEN '2026-02-01' AND '2026-03-31' GROUP BY order_id HAVING COUNT(*) > 1 LIMIT 100`. Write result count + sample to `output/s191/baseline_dedup_check.md`. **HARD BLOCKER 0-2:** If >10 duplicate `order_id` rows found, the FULL OUTER JOIN's legacy CTE MUST use `SELECT DISTINCT ON (order_id) ... ORDER BY order_id, synced_at DESC` subquery before the SUM aggregation. This prevents phantom revenue. If 0 duplicates: proceed with straight SUM, document the check result. | `output/s191/baseline_dedup_check.md` exists; if dupes found, Phase 1.1 SQL includes `DISTINCT ON (order_id)` |
| 0.5 | **[AMENDED v2 — audit fix B-4/B-10] Caller inventory.** `grep -n "foodpanda_vat_deducted_sales\|foodpanda_subtotal\|_get_mosaic_channel_split\|_get_mosaic_channel_split_per_day\|_get_store_channel_split_map" hrms/api/sales_dashboard.py` and write every call site to `output/s191/foodpanda_call_sites_audit.md`. Explicitly enumerate: `_aggregate_daily_series` (line ~2061), `_sales_row_metrics` (line ~2644), `_build_comparisons` (via `_aggregate_sales`), `export_sales_dashboard_detail` (line ~3261), `_apply_mosaic_channel_split` (line 910), `_build_dashboard_overview_payload`. **HARD BLOCKER 0-3:** If the inventory finds a call site NOT covered in Phase 2 or Phase 3 tasks, STOP and add it to scope. This caller inventory is the freeze-list — every site must be addressed. | `output/s191/foodpanda_call_sites_audit.md` exists with ≥6 call sites enumerated; cross-referenced to Phase 2/3 tasks |

**HARD BLOCKER 0-1 (AMENDED v2):** Do not proceed to Phase 1 until the baseline audit confirms: (a) total March FoodPanda GROSS is ≥ ₱20M when unioned (legacy ₱21.7M gross + Mosaic ₱4.7M with overlap dedup → expected ~₱21.7M unified), (b) GROSS overlap variance is reasonable (<₱2M total across all stores, <₱150K single-store-day), (c) dedup check in Task 0.4 shows either zero dupes OR the SQL has been amended with `DISTINCT ON (order_id)`, (d) caller inventory in Task 0.5 matches the Phase 2/3 scope exactly. If ANY fails, surface to user with the numbers and stop.

### Phase 1 — Unified helper `_get_unified_foodpanda_totals` (6 units)

**Goal:** Build a single reusable helper that returns unified FoodPanda totals per (store, day). All three consumer functions will call this.

| # | Task | MUST_MODIFY / Evidence |
|---|---|---|
| 1.1 | **Create `_get_unified_foodpanda_totals(start_day, end_day, location_ids)`** in `hrms/api/sales_dashboard.py` — place it immediately after `_get_mosaic_channel_split` (around line 908). Returns `dict[int, dict[str, dict]]` keyed by `location_id` → `business_date_isoformat` → `{"gross": float, "net_wo_vat": float, "orders": int, "source": str}`. **[AMENDED v2 — audit fix B-2]** The return shape is NESTED DICT by design — but it is for INTERNAL use by the helpers that consume it. The consumers (`_get_store_channel_split_map`, `_get_mosaic_channel_split_per_day`) must CONVERT to their existing float-per-channel shape before exposing to callers. See Phase 3 tasks for the conversion rules. Uses the FULL OUTER JOIN SQL from the Design Rationale section. **[AMENDED v2 — audit fix B-6]** If Task 0.4 found `order_id` dupes, the legacy CTE must use `SELECT DISTINCT ON (order_id) ... FROM public.foodpanda_orders WHERE ... ORDER BY order_id, synced_at DESC` wrapped in a subquery before the SUM. **[AMENDED v2 — audit fix B-12]** Add per-(store,day) completeness guard: if both Mosaic and legacy have rows for the same (store, day), pick Mosaic ONLY WHEN `mosaic_orders >= legacy_orders * 0.5 OR mosaic_gross >= legacy_gross * 0.5`. Otherwise, prefer legacy (interpret as Mosaic had a partial sync). Emit `source = 'mosaic'`, `'legacy'`, or `'legacy_partial_mosaic'` accordingly. Wrapped in `_cache_get_or_set` with 300s TTL and cache key `_sales_dashboard_cache_key("fp_unified_v2", location_ids, start_day=start_day, end_day=end_day)`. **HARD BLOCKER 1-1:** The cache key prefix MUST be `"fp_unified_v2"` (not `"foodpanda"` or `"fp_unified"`) to invalidate both the old Mosaic-only cache AND any pre-completeness-guard cache post-deploy. | `grep -c "_get_unified_foodpanda_totals" hrms/api/sales_dashboard.py` ≥ 1; `grep -c "FULL OUTER JOIN" hrms/api/sales_dashboard.py` ≥ 1; `grep -c "fp_unified_v2" hrms/api/sales_dashboard.py` ≥ 1; `grep -c "legacy_partial_mosaic" hrms/api/sales_dashboard.py` ≥ 1 |
| 1.2 | **[AMENDED v2 — audit fix B-8] Add PostgREST fallback inside `_get_unified_foodpanda_totals` with explicit implementation.** On `SupabaseMgmtTokenMissing`: (a) Mosaic fetch via `_supabase_get_all("v_pos_orders_live", params=[("select", "location_id,business_date,gross_sales,net_sales"), ("channel", "eq.FoodPanda"), ("payment_status", "eq.PAID"), ("business_date", f"gte.{start_day.isoformat()}"), ("business_date", f"lte.{end_day.isoformat()}"), ("location_id", f"in.({_location_scope_key(location_ids)})")], page_size=5000)`. (b) Legacy fetch via `_supabase_get_all("foodpanda_orders", params=[("select", "order_id,location_id,business_date,subtotal,synced_at"), ("order_status", "ilike.delivered")` — **IMPORTANT: PostgREST does NOT support `LOWER()` in filters. Use `ilike.delivered` (case-insensitive) NOT `eq.delivered` — legacy data has mixed case**`, ("business_date", f"gte.{start_day.isoformat()}"), ("business_date", f"lte.{end_day.isoformat()}"), ("location_id", f"in.({_location_scope_key(location_ids)})")], page_size=5000)`. (c) Python merge implementing FULL OUTER JOIN semantics with Mosaic-wins-on-overlap + completeness guard (same logic as SQL). (d) Python dedup if Task 0.4 flagged dupes: keep row with latest `synced_at` per `order_id`. Log `frappe.log_error("Sales Dashboard perf degraded: SUPABASE_MGMT_TOKEN missing; FP unified fallback", "Sales Dashboard perf fallback")`. **HARD BLOCKER 1-2:** For 60+ day windows (e.g., Feb 1 – Apr 14), the PostgREST fallback may exceed 10s. Add a sentinel check: `if (end_day - start_day).days > 45 and not MGMT_TOKEN: raise RuntimeError("FP unified: Mgmt API required for ranges > 45 days")`. | `grep -c "SupabaseMgmtTokenMissing" hrms/api/sales_dashboard.py` in FP section ≥ 1; `grep -c "ilike.delivered" hrms/api/sales_dashboard.py` ≥ 1 |
| 1.3 | **Add `_get_unified_foodpanda_totals_aggregate(start_day, end_day, location_ids)`** — sibling helper returning a single aggregated bucket `{"gross": float, "net_wo_vat": float, "orders": int}` summed across all stores and days. This is what `_apply_mosaic_channel_split` needs for the headline. Implemented as a trivial wrapper over `_get_unified_foodpanda_totals`. | `grep -c "_get_unified_foodpanda_totals_aggregate" hrms/api/sales_dashboard.py` ≥ 1 |
| 1.4 | **Python parse check.** `python -c "import ast; ast.parse(open('hrms/api/sales_dashboard.py').read())"` → PARSE OK. | Parse clean |

**HARD BLOCKER 1-1:** Cache key prefix change is non-negotiable. Using `"fp_unified"` (not `"foodpanda"` or `"mosaic_split"`) ensures any cached bucket from the old Mosaic-only logic is bypassed post-deploy. Without this, users hit stale cached results for up to 300s after deploy and the fix appears to not work.

**HARD BLOCKER 1-2:** Do NOT touch GrabFood logic. `_get_mosaic_channel_split` will continue to return the correct Mosaic-only GrabFood bucket. Only the FoodPanda bucket is overridden by `_get_unified_foodpanda_totals_aggregate`. (Source: CEO directive 2026-04-14 — "ignore Grabfood")

### Phase 2 — Wire into `_get_mosaic_channel_split` + fix `_apply_mosaic_channel_split` (6 units)

**Goal:** The headline Channel Mix donut on the main Sales Analytics page now shows correct March FoodPanda (~₱21.7M not ₱4.4M).

| # | Task | MUST_MODIFY / Evidence |
|---|---|---|
| 2.1 | **Modify `_apply_mosaic_channel_split`** (line 910+): after the line `split = _get_mosaic_channel_split(start_day, end_day, location_ids)`, add: `fp_unified = _get_unified_foodpanda_totals_aggregate(start_day, end_day, location_ids)`. Then **REPLACE** the existing line `fp_bucket = split.pop("foodpanda", {"gross": 0.0, "net_wo_vat": 0.0, "orders": 0})` at line 948 with: `split.pop("foodpanda", None)  # discard Mosaic-only FP — now using unified source` on one line, then `fp_bucket = fp_unified` on the next line. The `split.pop("foodpanda", None)` call is MANDATORY — it removes the Mosaic FP from `split` so the "other" rollup at line 952-954 doesn't accidentally include it. **[AMENDED v2 — audit fix B-3] HARD BLOCKER 2-2:** The verification script MUST assert that `fp_bucket = split.pop("foodpanda"` pattern is GONE (replaced with `split.pop("foodpanda", None)` + `fp_bucket = fp_unified`). If the agent leaves the old `fp_bucket = split.pop(...)` line AND adds the new `fp_bucket = fp_unified` after it, the old assignment is overwritten but the READER would be confused — worse, if the new line comes FIRST, the old assignment silently reverts the fix. The verify script checks: `grep -c "fp_bucket = split.pop" hrms/api/sales_dashboard.py` MUST be 0 AND `grep -c "fp_bucket = fp_unified" hrms/api/sales_dashboard.py` MUST be 1. | `grep -c "_get_unified_foodpanda_totals_aggregate" hrms/api/sales_dashboard.py` in `_apply_mosaic_channel_split` section ≥ 1; `grep -c "fp_bucket = split.pop" hrms/api/sales_dashboard.py` == 0; `grep -c "fp_bucket = fp_unified" hrms/api/sales_dashboard.py` ≥ 1 |
| 2.2 | **Keep GrabFood bucket untouched.** Line 949: `gf_bucket = split.pop("grabfood", ...)` stays as-is. Do NOT introduce any unified GrabFood logic. **HARD BLOCKER 2-1:** If the diff shows any change to `gf_bucket`, `grabfood_sales`, `grabfood_orders`, or `grabfood_avg_ticket`, revert it immediately. (Source: CEO directive 2026-04-14) | `git diff hrms/api/sales_dashboard.py \| grep -c "grabfood"` in diff = 0 for code changes (comments OK) |
| 2.3 | **Keep `summary["foodpanda_orders"]` aligned with `fp_bucket["orders"]`.** Line 962 already does `summary["foodpanda_orders"] = fp_bucket["orders"]`. After task 2.1, `fp_bucket["orders"]` now reflects unified count. Verify no other code assumes `foodpanda_orders` is Mosaic-only. | `grep -n "foodpanda_orders" hrms/api/sales_dashboard.py` reviewed; no stale assumption |
| 2.4 | **Update the deprecation comment on `_FOODPANDA_MOSAIC_START`.** At line 31, change the comment to: `# S191 2026-04-14: DEPRECATED as cutover date. Per-(store,day) FULL OUTER JOIN in _get_unified_foodpanda_totals replaces global date. Constant retained ONLY for the freshness warning at line ~1296 that tells users about the historical source split.` | `grep -c "DEPRECATED" hrms/api/sales_dashboard.py` near line 31 ≥ 1 |
| 2.5 | **[AMENDED v2 — audit fix B-5] Bump outer cache key prefixes to force invalidation post-deploy.** In `_build_dashboard_overview_payload` (~line 2839), change the cache key prefix from `"overview"` to `"overview_s191"`. Similarly find any other outer cache key prefixes that wrap the summary/channel-split result (search `_sales_dashboard_cache_key\("(overview\|summary\|channel_mix\|rankings\|export)` in sales_dashboard.py). For EACH outer prefix that wraps FP-related data, append `_s191`. This ensures users do NOT see stale pre-fix cached results for up to 300s after deploy. Precedent: S176 DD-21 used `"freshness_v2"` for exactly this reason at line ~743. List all changed prefixes in `output/s191/cache_prefix_changes.md`. | `grep -c "overview_s191" hrms/api/sales_dashboard.py` ≥ 1; `output/s191/cache_prefix_changes.md` lists all prefix bumps |
| 2.6 | **Python parse + smoke test locally.** Start `/local-frappe`, call `get_sales_dashboard_overview` with `start_date=2026-03-01, end_date=2026-03-31`, inspect `response["summary"]["foodpanda_sales_without_vat"]`. **[AMENDED v2 — audit fix B-7] MUST be ≥ ₱18M (net, not gross). Note: the dashboard displays `foodpanda_sales_without_vat` which is the NET (VAT-deducted) amount. Legacy March gross was ₱21.7M; net ≈ `21.7M / 1.12` = ₱19.4M. With the completeness guard possibly picking legacy over partial Mosaic for some overlap days, the final net lands ~₱18-19.4M.** Also inspect `response["summary"]["foodpanda_orders"]` — MUST be ≥ 30,000 (legacy had 34,337). Write result to `output/s191/phase2_local_smoke.json`. | `output/s191/phase2_local_smoke.json` exists; foodpanda_sales_without_vat ≥ 18000000; foodpanda_orders ≥ 30000 |

### Phase 3 — Wire into `_get_store_channel_split_map` + `_get_mosaic_channel_split_per_day` (7 units)

**Goal:** Per-store Channel Mix on Store Leaderboard + Store Detail Dialog shows correct FP totals. Daily time-series chart shows correct FP totals.

| # | Task | MUST_MODIFY / Evidence |
|---|---|---|
| 3.1 | **Read `_get_store_channel_split_map`** (line 1049+) to understand the per-store return shape: `dict[location_id, dict[channel_key, {"gross", "net_wo_vat", "orders"}]]`. | Mental model |
| 3.2 | **[AMENDED v2 — audit fix B-2] Read `_get_store_channel_split_map` return shape CAREFULLY** (lines ~1109-1122). Current shape is `dict[int, dict[str, float]]` — each channel key maps to a single `float` (gross), NOT a nested `{gross, net_wo_vat, orders}` dict. The consumer at line 2502 does `float(mosaic.get("foodpanda", 0.0))` — putting a dict there silently corrupts the FP number in the leaderboard channel_mix. **Modify the function** to preserve the existing float-per-channel shape: after the Mosaic-only SQL, call `fp_unified_by_store = _get_unified_foodpanda_totals(start_day, end_day, location_ids)`. For each `location_id`, sum all its business_date entries to get `total_gross` (single float). Then **override** `result[location_id]["foodpanda"]` with `total_gross` (keeping the float shape). Stores not in `fp_unified_by_store` get `0.0`. If the caller needs `net_wo_vat` or `orders`, create a PARALLEL per-store map (e.g., `_get_unified_foodpanda_per_store_full`) returning the nested dict — but do NOT change the existing function's return type. | `grep -c "_get_unified_foodpanda_totals" hrms/api/sales_dashboard.py` ≥ 2; verify shape by reading `_get_store_channel_split_map` return statement and confirming `float` type preserved |
| 3.3 | **Do NOT override POS, GrabFood, WebDelivery, or other_mosaic per-store buckets.** These stay Mosaic-only. **HARD BLOCKER 3-1:** Only `result[location_id]["foodpanda"]` is overridden. | Diff reviewed: only foodpanda key overridden |
| 3.4 | **Read `_get_mosaic_channel_split_per_day`** (line 1962+) to understand the daily return shape. **[AMENDED v2 — audit fix B-2]** Per audit finding: the return is `dict[date_iso, dict[channel_key, float]]` (float, NOT nested dict). Same care as Task 3.2. | Mental model |
| 3.5 | **[AMENDED v2 — audit fix B-2] Modify `_get_mosaic_channel_split_per_day`** preserving the existing float-per-channel return shape. After the Mosaic-only SQL, call `fp_unified = _get_unified_foodpanda_totals(start_day, end_day, location_ids)`. Aggregate across all stores per day: `fp_by_day: dict[date_iso, float]` where the float is gross sum. For each day in the return dict, **override** `result[date_iso]["foodpanda"]` with `fp_by_day.get(date_iso, 0.0)` (float, not dict). | `grep -c "_get_unified_foodpanda_totals" hrms/api/sales_dashboard.py` ≥ 3 |
| 3.6 | **[AMENDED v2 — audit fix B-1 / F-01] CRITICAL: Fix `_aggregate_daily_series` double-count at line ~2061.** After Phase 3.5 fixes `_get_mosaic_channel_split_per_day` to return UNIFIED FP data (including pre-cutover legacy), the existing code at line 2061 — `superadmin_delivery_wo_vat += _to_float(row.get("foodpanda_vat_deducted_sales"))` — adds the MV's legacy FP on TOP of the already-included unified FP. Result: Feb/March delivery totals DOUBLE-COUNTED by ~₱17M. **REMOVE the `+ _to_float(row.get("foodpanda_vat_deducted_sales"))` term** from the `superadmin_delivery_wo_vat` accumulator at line 2061. Replace with a comment: `# S191: legacy foodpanda_vat_deducted_sales no longer added here — unified FP totals from _get_mosaic_channel_split_per_day already include legacy.` | `grep -c "foodpanda_vat_deducted_sales" hrms/api/sales_dashboard.py` count REDUCES by 1 vs baseline; comment `S191.*unified FP totals` present near line 2061 |
| 3.7 | **[AMENDED v2 — audit fix B-10 / F-09] Fix `_sales_row_metrics` at line ~2644.** This helper uses `foodpanda_vat_deducted_sales` from MV rows. Since `_sales_row_metrics` feeds store-detail delivery panels via the MV (not via `_get_unified_foodpanda_totals`), leaving it unchanged creates inconsistency with the unified Channel Mix. **Modify `_sales_row_metrics`** to call `_get_unified_foodpanda_totals` for the (location_id, business_date) of its input row and override `foodpanda_vat_deducted_sales` with the unified `net_wo_vat` (or 0 if no unified data). If per-row calls are too expensive, cache the unified map at the caller level and pass it in. Document the chosen approach in the function docstring. | `grep -c "_get_unified_foodpanda_totals" hrms/api/sales_dashboard.py` ≥ 4 (Task 3.2, 3.5, 3.7 + helpers) |
| 3.8 | **[AMENDED v2 — audit fix B-11 / F-08] Fix `_build_comparisons` to use unified FP for baseline periods.** Currently calls `_aggregate_sales(prev_rows)` on MV-only rows (no unified FP). Result: current-period FP shows unified ~₱21.7M March, while comparison baseline (Feb) shows MV-only FP → apples-to-oranges delta. **Modify `_build_comparisons`** (line ~1760): after the `_aggregate_sales(prev_rows)` call, call `prev_fp_unified = _get_unified_foodpanda_totals_aggregate(prev_start, prev_end, location_ids)`. **Override** `prev["foodpanda_sales"]` with `prev_fp_unified["gross"]` and `prev["foodpanda_sales_without_vat"]` with `prev_fp_unified["net_wo_vat"]`. Also recompute `prev["total_gross_sales"]` and `prev["total_net_sales_without_vat"]` to reflect the corrected FP (subtract the old MV FP, add unified FP). Do same for `last_year` baseline. | `grep -c "_get_unified_foodpanda_totals_aggregate" hrms/api/sales_dashboard.py` ≥ 2 (Phase 2.1 + Task 3.8) |
| 3.9 | **[AMENDED v2 — audit fix B-4 / F-03] Fix `export_sales_dashboard_detail` CSV export at line ~3261.** This endpoint calls `_get_mosaic_channel_split_per_day` and `_aggregate_daily_series`. After Tasks 3.5 + 3.6, the export automatically picks up unified FP with no double-count. **Verify** by reading the endpoint body: confirm no inline FP aggregation that bypasses the fixed helpers. If inline FP SQL exists (unlikely but possible), refactor to use `_get_unified_foodpanda_totals`. Add an L3 scenario (L3-191-13 below) that downloads the CSV for March and asserts the FoodPanda column sum is ≥ ₱18M. | Endpoint body read; no inline FP SQL; L3-191-13 added to the L3 table |
| 3.10 | **Verify no other FoodPanda aggregation path exists.** `grep -n "channel.*FoodPanda\|foodpanda_orders\|foodpanda_vat_deducted_sales\|foodpanda_subtotal" hrms/api/sales_dashboard.py` — every hit must either be: (a) the new unified helper, (b) a DELIBERATELY preserved MV reference for audit/freshness purposes, or (c) the deprecated `_FOODPANDA_MOSAIC_START` warning text. No stale Mosaic-only FP queries allowed. Cross-reference against `output/s191/foodpanda_call_sites_audit.md` from Task 0.5. Append `output/s191/foodpanda_call_sites_audit_POST_FIX.md` showing every call site's resolution. | `output/s191/foodpanda_call_sites_audit_POST_FIX.md` exists; every call site from Task 0.5 is accounted for |
| 3.11 | **Python parse check.** `ast.parse` → OK. | Parse clean |

**HARD BLOCKER 3-1:** Only the `foodpanda` key is overridden in all three functions. POS/GrabFood/WebDelivery/other_mosaic/web_non_cod/web_cod all stay exactly as before. If the diff shows changes to any non-FoodPanda channel key, revert.

### Phase 4 — Verification + data audit + PR + closeout (6 units)

| # | Task | MUST_MODIFY / Evidence |
|---|---|---|
| 4.1 | **[AMENDED v2 — all audit fixes] Verification script.** Create `output/s191/verify_s191.py` with grep + AST assertions for ALL Phase 1-3 patterns, including: (a) `fp_bucket = split.pop` count == 0 (Task 2.1), (b) `fp_bucket = fp_unified` count == 1, (c) `fp_unified_v2` cache prefix (Task 1.1), (d) `overview_s191` outer cache prefix (Task 2.5), (e) `ilike.delivered` for PostgREST fallback (Task 1.2), (f) `legacy_partial_mosaic` completeness guard marker (Task 1.1), (g) `_get_unified_foodpanda_totals` called ≥ 4 times (Tasks 3.2, 3.5, 3.7 + helpers), (h) `_get_unified_foodpanda_totals_aggregate` called ≥ 2 times (Phase 2.1 + Task 3.8), (i) `foodpanda_vat_deducted_sales` count REDUCED by 1 vs baseline (Task 3.6 removed one call site), (j) Sentry `set_backend_observability_context` count UNCHANGED at 5 (pre-S191 baseline — amended from original "≥ 4"), (k) GrabFood anti-regression: `grep -c grabfood hrms/api/sales_dashboard.py` MUST EQUAL 28 (pre-S191 count — audit confirmed exact number). Also include a post-deploy data probe (commented example) showing how to hit the staged endpoint and confirm March FP ≥ ₱18M NET. Run → PASS. | File exists, exits 0; all 11 assertion categories encoded |
| 4.2 | **Re-run baseline audit SQL post-fix (local):** confirm March FP unified ≈ legacy (₱21.7M GROSS) on pre-cutover days + Mosaic (₱4.7M) on post-cutover days, with no double-count in the overlap window. Also confirm `_aggregate_daily_series` total delivery for Feb/March is NOT inflated by ₱17M (Task 3.6 fix verified). Write `output/s191/post_fix_reconciliation.md` comparing pre-fix vs post-fix numbers across: headline summary, per-store map, per-day series, daily series delivery total, CSV export. | Reconciliation file exists with 5-way before/after comparison |
| 4.3 | **[AMENDED v2 — audit fix F-12] Write rollback runbook.** `output/s191/ROLLBACK_RUNBOOK.md` documents: (a) `GH_TOKEN="" gh pr merge --undo` or revert commit + redeploy steps, (b) cache invalidation: even on rollback, the new `overview_s191` / `fp_unified_v2` cache keys will naturally expire in 300s and new writes use old `overview` prefix again, (c) no schema changes to undo, (d) success criterion: March FP back to ₱4.4M (Mosaic-only pre-S191 value) within 5 min of rollback deploy. | `output/s191/ROLLBACK_RUNBOOK.md` exists with 4 named sections |
| 4.4 | **[AMENDED v2 — audit fix F-10] Pre-deploy notification to Sam.** Write `output/s191/SAM_PRE_DEPLOY_NOTICE.md` explicitly stating: "After S191 deploys, Feb 2026 FP goes from ₱0 → ~₱8.5M net, March FP goes from ₱4.4M → ~₱19.4M net. Downstream reports (Apex P&L, board decks, commission calcs) that used the old numbers will show new numbers. This is visibility restoration, not revenue fabrication. If any scheduled report needs the old number, pull it from `output/s191/post_fix_reconciliation.md` before the deploy day." Surface to Sam in the PR description. | `output/s191/SAM_PRE_DEPLOY_NOTICE.md` exists; linked in PR description |
| 4.5 | **Push branch, create PR.** hrms → production. `GH_TOKEN=""` prefix. PR title: `fix(S191): unified FoodPanda source — recover ₱17M+ pre-cutover March sales`. PR body includes links to baseline_audit, post_fix_reconciliation, rollback_runbook, sam_pre_deploy_notice. | PR number recorded |
| 4.6 | **Update plan YAML** to `status: DEPLOYED` + update `SPRINT_REGISTRY.md` with PR number. `git add -f docs/plans/`. | Plan + registry updated |
| 4.7 | **Generate L3 handoff prompt** with the specific assertions listed below (L3 Workflow Scenarios table now has 13 scenarios including CSV export). L3 runs in a fresh session after deploy. Explicitly note: **wait ≥ 5 minutes after deploy before running L3** to allow any pre-deploy cached responses to expire (audit fix W-2). | Handoff prompt output with ≥5 min wait note |
| 4.8 | **Verify Sentry instrumentation on existing endpoints is still present AND unchanged in count.** **[AMENDED v2 — audit fix W-3]** `grep -c "set_backend_observability_context" hrms/api/sales_dashboard.py` MUST EQUAL 5 (pre-S191 baseline — amended from original "≥ 4"). No new instrumentation required since no new `@frappe.whitelist()` endpoints are introduced. If count changes, Sentry context was accidentally added/removed — revert. | `grep -c "set_backend_observability_context" hrms/api/sales_dashboard.py` == 5 |

---

## Zero-Skip Enforcement

Every task in the phase table MUST be implemented. The agent is FORBIDDEN from:
- Skipping a task silently
- Marking partial work as "done"
- Replacing a task with a simpler version without user approval
- Saying "deferred to next sprint"
- Implementing happy path only, skipping edge cases (e.g., stores with only legacy data, stores with only Mosaic data, stores with both — all three cases must be tested)
- Combining tasks and dropping features
- **Touching GrabFood logic** (CEO directive — GrabFood is explicitly out of scope)
- **Introducing frontend changes** (backend-only sprint)

**Phase Completion Checklist:** After each phase, write `output/s191/phase_N_completion.md` with task-by-task status. If any task is skipped/partial, STOP and notify user.

### Verification Script (MANDATORY)

Create `output/s191/verify_s191.py`. Runs after every phase AND at closeout. PR cannot be created until PASS.

The script checks:
- Phase 1 patterns: `_get_unified_foodpanda_totals`, `_get_unified_foodpanda_totals_aggregate`, `FULL OUTER JOIN`, `fp_unified`, cache key prefix `fp_unified`, fallback path for `SupabaseMgmtTokenMissing`
- Phase 2 patterns: `_get_unified_foodpanda_totals_aggregate` called in `_apply_mosaic_channel_split`; `DEPRECATED` comment on `_FOODPANDA_MOSAIC_START`
- Phase 3 patterns: `_get_unified_foodpanda_totals` called in BOTH `_get_store_channel_split_map` AND `_get_mosaic_channel_split_per_day`
- Anti-regression: `grep -c "grabfood" hrms/api/sales_dashboard.py` unchanged (count must equal pre-S191 count)
- Protected surfaces: no workflow files modified, no frontend files modified
- Python AST parses cleanly

---

## L3 Workflow Scenarios

| ID | User | Action | Expected Outcome | Failure Means |
|---|---|---|---|---|
| L3-191-01 | sam@bebang.ph | Load Sales Analytics with date range 2026-03-01 to 2026-03-31 | Channel Mix donut shows FoodPanda ≥ **₱18M net** (dashboard shows net_without_vat; legacy gross ₱21.7M ÷ 1.12 ≈ ₱19.4M; completeness-guard edge cases → floor at ₱18M). NOT ₱4.4M (pre-fix). | Unified source not wired to headline |
| L3-191-02 | sam@bebang.ph | Same 1-month range, check FoodPanda order count | Orders shown ≥ 30,000 (legacy had 34,337; completeness guard may exclude a few cutover days) | Orders field not using unified |
| L3-191-03 | sam@bebang.ph | Load Sales Analytics with date range 2026-02-01 to 2026-02-28 | Channel Mix donut shows FoodPanda ≥ **₱8M net** (legacy gross ₱9.5M ÷ 1.12 ≈ ₱8.5M net) | Feb legacy data dropped |
| L3-191-04 | sam@bebang.ph | Load Sales Analytics with date range 2026-04-01 to 2026-04-12 | FoodPanda matches Mosaic-only (~₱9.5M net), NO double-count (Apr legacy is frozen ₱0) | Post-cutover double-count regression |
| L3-191-05 | sam@bebang.ph | Load Store Leaderboard, 2026-03-01 to 2026-03-31 | Per-store FoodPanda column sum across all stores ≥ **₱18M net** | Per-store helper not wired |
| L3-191-06 | sam@bebang.ph | Open any store's detail dialog, 2026-03-01 to 2026-03-31 | FoodPanda sales on the dialog match the leaderboard cell for that store (consistency check — no dict-vs-float shape regression) | Per-store inconsistency / return-shape corruption |
| L3-191-07 | sam@bebang.ph | Daily time-series chart, 2026-03-01 to 2026-03-31 | FoodPanda daily line is non-zero for dates before Mar 27 (pre-cutover days). **Total delivery line is NOT inflated by ₱17M vs pre-fix** (Task 3.6 double-count fix verified) | Per-day helper not wired OR daily-series double-count |
| L3-191-08 | sam@bebang.ph | Daily time-series chart, 2026-03-25 to 2026-03-31 (overlap zone) | No FoodPanda spike indicating double-count — daily values reasonable (~₱500K-₱1.5M/day) | Mosaic-preferred overlap logic broken OR completeness guard inverted |
| L3-191-09 | sam@bebang.ph | Check GrabFood Channel Mix bucket for 2026-03-01 to 2026-03-31 | Still ₱0 (unchanged from before — CEO said leave GrabFood alone) | GrabFood regression (should NOT have changed) |
| L3-191-10 | sam@bebang.ph | Check Pickup (POS) Channel Mix bucket, any date range | Unchanged from pre-S191 values | POS regression |
| L3-191-11 | sam@bebang.ph | Product Analytics page, 2026-03-01 to 2026-03-31 | Products fetched OK (this sprint does not touch product analytics; regression check only) | Unintended coupling broken |
| L3-191-12 | sam@bebang.ph | Sales Analytics with 2026-03-25 to 2026-04-05 (spans overlap + both sides) | Total FoodPanda ≥ ₱8M net, daily series smooth across cutover — no cliff, no spike | Union logic broken at overlap |
| **L3-191-13** | **sam@bebang.ph** | **[AMENDED v2 — audit fix B-4] Click "Export CSV" on Store Leaderboard, 2026-03-01 to 2026-03-31** | **Downloaded CSV's FoodPanda column sum across all rows ≥ ₱18M net. NOT ₱4.4M.** | **`export_sales_dashboard_detail` not wired to unified FP** |
| **L3-191-14** | **sam@bebang.ph** | **[AMENDED v2 — audit fix B-11] Sales Analytics with 2026-03-01 to 2026-03-31 — check comparison panel (vs prior period / vs last year)** | **Comparison baseline uses unified FP. Feb baseline shows ~₱8M FP (not ₱0). Period-over-period delta is consistent apples-to-apples.** | **`_build_comparisons` not using unified FP — apples-to-oranges** |
| **L3-191-15** | **sam@bebang.ph** | **[AMENDED v2 — audit fix B-10] Open any store's detail dialog (uses `_sales_row_metrics`) for 2026-02-15** | **FoodPanda delivery number on the per-day panel matches the unified FP for that (store, day). Not 0, not MV-only.** | **`_sales_row_metrics` not using unified FP** |

**[AMENDED v2 — audit fix W-2] POST-DEPLOY WAIT NOTE:** L3 MUST begin at least 5 minutes after the deploy completes. Outer cache keys were bumped (Task 2.5) but any in-flight cached responses from BEFORE the deploy can still serve until their 300s TTL expires. Running L3 immediately post-deploy can surface false FAILs from stale cache.

**Evidence files required before closeout (per S092 rule):**
- `output/l3/s191/form_submissions.json` (empty array — no form submissions in this sprint, all page loads)
- `output/l3/s191/api_mutations.json` (empty array — read-only)
- `output/l3/s191/state_verification.json` (contains the 12 scenarios above with pass/fail + the actual ₱ amounts read from API responses)
- `output/l3/s191/screenshots/` (one screenshot per scenario showing the actual dashboard state)

---

## Autonomous Execution Contract

- **completion_condition:**
  - All 5 phases marked DONE in `output/s191/phase_N_completion.md`
  - `output/s191/verify_s191.py` exits 0
  - `output/s191/BASELINE_SUMMARY.md` shows overlap variance within acceptable bounds (HARD BLOCKER 0-1)
  - `output/s191/post_fix_reconciliation.md` confirms March FP ≥ ₱20M post-fix
  - 1 PR created (hrms only — no frontend, no bei-tasks PR)
  - Plan YAML updated to DEPLOYED, SPRINT_REGISTRY.md updated with PR number
- **stop_only_for:**
  - Missing credentials/access
  - HARD BLOCKER 0-1 triggered (overlap variance > ₱1M or single-store single-day variance > ₱50K) — surface to user
  - Direct conflict on `sales_dashboard.py` with a newer sprint
  - Repeated (3x) technical failure with no progress after grounded research
  - Baseline audit reveals that March FP unified total is < ₱15M OR > ₱35M — data integrity issue, surface to user before shipping
- **continue_without_pause_through:** `execute → pr_creation → closeout`
- **blocker_policy:**
  - programmatic → fix and continue
  - repeated failure x3 → grounded research, continue
  - business-data/policy → pause
  - verify_s191.py FAIL → fix and re-run immediately
- **signoff_authority:** single-owner (sam@bebang.ph)
- **canonical_closeout_artifacts:**
  - `output/s191/BASELINE.md` — base SHA
  - `output/s191/BASELINE_SUMMARY.md` — pre-fix audit summary (8 metrics incl. gross-vs-net variance split)
  - `output/s191/baseline_audit.csv` — per-(store,day) source audit
  - `output/s191/baseline_dedup_check.md` — **[v2]** `order_id` dedup result (Task 0.4)
  - `output/s191/foodpanda_call_sites_audit.md` — **[v2]** Task 0.5 pre-fix caller inventory
  - `output/s191/foodpanda_call_sites_audit_POST_FIX.md` — **[v2]** Task 3.10 post-fix caller resolution
  - `output/s191/cache_prefix_changes.md` — **[v2]** Task 2.5 outer cache bumps
  - `output/s191/phase_0..4_completion.md`
  - `output/s191/phase2_local_smoke.json` — Phase 2.6 local test (net ≥ ₱18M, orders ≥ 30K)
  - `output/s191/post_fix_reconciliation.md` — 5-way before/after numbers (summary, per-store, per-day, daily-series delivery, CSV export)
  - `output/s191/ROLLBACK_RUNBOOK.md` — **[v2]** Task 4.3 rollback plan
  - `output/s191/SAM_PRE_DEPLOY_NOTICE.md` — **[v2]** Task 4.4 downstream impact notice
  - `output/s191/verify_s191.py` + `verify_output.txt`
  - `docs/plans/2026-04-14-sprint-191-foodpanda-unified-source.md`
  - `docs/plans/SPRINT_REGISTRY.md`

---

## Ground-Truth Lock

- **evidence_sources:**
  - `hrms/api/sales_dashboard.py:825-907` — proves `_get_mosaic_channel_split` is Mosaic-only (no legacy JOIN)
  - `hrms/api/sales_dashboard.py:948, 960-962` — proves `_apply_mosaic_channel_split` overwrites `summary["foodpanda_sales"]` with Mosaic-only bucket
  - `hrms/api/sales_dashboard.py:31` — `_FOODPANDA_MOSAIC_START = date(2026, 3, 27)` — the broken global cutover
  - Supabase `foodpanda_orders` schema audit 2026-04-14 — columns confirmed via `information_schema.columns` query
  - Supabase baseline numbers 2026-04-14: legacy Feb=16,188 orders/₱9.5M, legacy Mar=34,337 orders/₱21.7M, Mosaic Mar=8,477 orders/₱4.7M, Mosaic Apr=16,583 orders/₱9.5M
  - `sales_dashboard_daily_store_metrics` view definition proves `foodpanda_subtotal` uses legacy `foodpanda_orders` and computes net as `subtotal/1.12`
- **count_method:**
  - metric: monthly FoodPanda gross sales
  - basis: per-(location_id, business_date) FULL OUTER JOIN with Mosaic-wins-on-overlap
  - method: `_supabase_query_sql` with the SQL block in Design Rationale; PostgREST fallback with same semantics in Python
- **authoritative_sections:** Sections "Executive Summary" through "Autonomous Execution Contract" are authoritative for execution. The Design Rationale section is authoritative for intent. Any amendment must update authoritative sections in the same edit.
- **normalization_required:** yes
- **unresolved_value_policy:** any operator-facing unknown must be labeled `[UNVERIFIED — requires resolution]`, never guessed

---

## Execution Workflow

- Test Python changes locally: `/local-frappe`
- Deploy: `/deploy-frappe` (Sam handles merge + deploy trigger — builder creates PR and stops)
- E2E testing: `/l3-v2-bei-erp` in a fresh session after deploy
- Full workflow: `/agent-kickoff`

---

## Anti-Rewind Protection

- **remote_truth_baseline:** `output/s191/BASELINE.md` with backend SHA
- **protected_surfaces:** see Surface Ownership Matrix — all non-FoodPanda channel logic, all frontend code, all other backend functions
- **rebase rule:** before pushing, `git fetch origin production && git rebase origin/production`. Re-run `verify_s191.py`. Grep for conflict markers.
- **supersession:** this sprint supersedes the S176 `_FOODPANDA_MOSAIC_START` global-date logic for all analytics aggregations. The constant is retained for the freshness warning only.
