# Phase 3 — Timestamp Usage Audit (S232)

**Date:** 2026-05-02
**Goal:** Confirm every dashboard query reads PHT-aligned `business_date` (and PHT-aligned `billed_at` already converted at ingest time), NEVER raw UTC `Billed At`/`Paid At` from a webhook payload.

## Findings

### Source layer — pos_orders timestamp columns

The Mosaic webhook payload contains `billed_at` and `paid_at` in **UTC** (e.g., `2026-04-20T03:07:05.000000Z`). The ingester at `hrms/api/mosaic_webhook.py:_map_order_row` and `scripts/sync_pos_to_supabase.py:map_order` writes these columns to Supabase `pos_orders.billed_at` and `pos_orders.paid_at`.

**The `business_date` column is set by Mosaic per their own PHT business-day cutoff** — verified by inspecting raw API responses. Sample: an order with `billed_at = 2026-04-20T03:07:05Z` (UTC) has `business_date = 2026-04-20` (PHT date — correct because 03:07 UTC = 11:07 AM PHT on the same date).

### Risk class

A dashboard query that filters on `billed_at >= '2026-04-20T00:00:00'` (UTC midnight) would actually return data from PHT 2026-04-20 8:00 AM through 2026-04-21 7:59 AM — the wrong day window. The safe filter is `business_date = '2026-04-20'`.

### Audit results — `hrms/api/sales_dashboard.py`

```
grep -nE "(billed_at|paid_at|business_date)" hrms/api/sales_dashboard.py
```

| Query | Filter | Status |
|-------|--------|--------|
| All daily-window queries | `business_date >= start_day, business_date <= end_day` | ✅ PHT-aligned |
| `paid_at` references | only used for chronological sort within a day, not for day boundaries | ✅ Safe |
| `billed_at` references | only used for chronological sort, not day boundaries | ✅ Safe |

Conclusion: `sales_dashboard.py` correctly uses `business_date` for all day-boundary filters. No code change needed.

### Audit results — `hrms/api/discount_abuse.py` + `hrms/api/marketing_giveaways.py`

Same pattern: filters on `business_date` (PHT). Phase 5.5 patched these files to add `is_duplicate=is.false` filter, but did NOT need to change timestamp filters.

### Frontend (bei-tasks)

Phase 6 audit confirms bei-tasks does NOT query Supabase directly — all data comes through HRMS API. So the timestamp risk is fully encapsulated in the HRMS layer audited above.

### Webhook receiver

`hrms/api/mosaic_webhook.py:_map_order_row` writes the raw UTC `billed_at` / `paid_at` from the Mosaic payload directly to Supabase. **This is correct** — the columns are documented as UTC, and downstream consumers use `business_date` for filtering. The S232 sprint adds `webhook_received_at` as a separate PHT-aligned column for the cluster-window dedup fallback.

## Verdict

**No timestamp standardization changes needed.** The codebase already uses `business_date` correctly for all day-window filters. Phase 3 closes as a verified-clean audit.

## Audit blocker status

- C3 from the audit (cancellation tombstone L3) — separate scenario in Phase 7 L3 handoff
- Phase 3 Phase 5 documentation contract — this file IS the deliverable
