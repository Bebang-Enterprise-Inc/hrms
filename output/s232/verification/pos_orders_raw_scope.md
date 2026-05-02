# pos_orders_raw Scope Decision (S232 Phase 0.7)

**Date:** 2026-05-02
**Decision:** **FORENSICS-ONLY — no dedup, no migration needed.**

## Investigation

### Schema (live Supabase, 2026-05-02)
```
pos_orders_raw columns: [order_id, raw_json, synced_at]
```

Three columns total. No `bill_number`, no `location_id`, no `business_date` — none of the natural-key fields the dedup logic needs. The PK is `order_id` (Mosaic's id).

### Volume (live Supabase, 2026-05-02)
```
pos_orders_raw 14d row count: 0
```

The table is essentially unused by recent syncs. Either the writer was disabled at some point, or rows are aged out, or the schema was migrated and rows were not preserved.

### Consumers (codebase grep, 2026-05-02)
```
Files referencing pos_orders_raw:
  scripts/sync_pos_to_supabase.py     (writer at line 495)
  scripts/s232_phase0_baseline.py     (this audit script)
```

Exactly ONE producer (`sync_pos_to_supabase.py:495` `supabase_upsert(client, "pos_orders_raw", rows, on_conflict="order_id")`) and ZERO downstream readers in `hrms/`, `bei-tasks/`, or any analytics view. The table is not used by any dashboard, report, or query in current code.

## Decision rationale

The plan's audit blocker B3 raised the concern that `pos_orders_raw` could accumulate duplicates indefinitely. After investigation:

1. **Schema is incompatible with bill_number-based dedup** — would require parsing `raw_json` to extract bill_number, which is fragile.
2. **No active downstream consumers** — analytics doesn't read this table; only the cleaned `pos_orders` is consumed.
3. **Volume is effectively zero** for the 14-day window — confirms the table is forensics-only (kept for vendor debugging if needed).
4. **PK on `order_id` already deduplicates by Mosaic ID** — same id can't be inserted twice, so the PK provides ID-level dedup. The `bill_number` cross-id collisions exist conceptually but the table doesn't track bill_number.

**No code changes needed.** The table stays as-is — raw JSON dump indexed by `order_id`, `on_conflict=id` upsert. If at any point we need bill-number-deduped raw data, we'd add a column or move to a different storage pattern.

## Audit blocker B3 status

**RESOLVED — no action.** The blocker assumed `pos_orders_raw` has the same `(location_id, business_date, bill_number)` shape as `pos_orders`. Live schema inspection shows it does not. The duplicate-resolution work in Phase 1 is fully sufficient because:

- Phase 1 unique partial index lives on `pos_orders` (the cleaned table that drives analytics)
- `pos_orders_raw` is only the raw payload archive — never read by analytics, never compared to backend reports
- No downstream impact from leaving `pos_orders_raw` un-deduped

## Future-proofing note

If at any point a stakeholder requires `pos_orders_raw` to support natural-key dedup, the right approach is:
1. Add `(location_id, business_date, bill_number)` columns extracted from `raw_json` at insert time
2. Add the same partial unique index pattern as Phase 1.1
3. Backfill historical rows by parsing `raw_json`

For now, this is out of scope and explicitly NOT pursued.
