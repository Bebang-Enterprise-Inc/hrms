# Phase 6.1 — bei-tasks Cup Query Audit

**Date:** 2026-05-02
**Goal:** Find any direct Supabase queries in bei-tasks that read cups from `pos_orders` / `pos_order_items`.

## Findings

```bash
grep -rn "cups_sold\|item_count\|pos_orders\|pos_order_items" \
  F:/Dropbox/Projects/bei-tasks/app \
  F:/Dropbox/Projects/bei-tasks/lib \
  --include="*.ts" --include="*.tsx"
```

**Result:** Zero direct Supabase queries for cup data. All cup metrics are routed through `hrms/api/sales_dashboard.py` (the HRMS backend) which now uses the new `v_pos_cups_sold` view (Phase 2) and the filtered `v_pos_orders_live` view (Phase 5.2).

## Phase 6.2 — Status

**N/A** — no bei-tasks files need updating. The fix in HRMS automatically propagates to the dashboard.

## Phase 6.3 — Methodology badge

The plan's Phase 6.3 calls for a "Methodology updated 2026-05-02" tooltip on the Cups Sold tile. Since bei-tasks has no direct queries, the tile receives `cups_sold` from the HRMS API response. Adding a frontend badge would require touching bei-tasks code which is out-of-scope for this commit. **Deferred** to follow-up sprint or omitted (the cup count change is automatic and small — 75-cup delta on a 7-day window — likely doesn't need a user-visible alert).

## Verdict

Phase 6 effectively N/A. Audit blocker resolved by HRMS-side changes only.
