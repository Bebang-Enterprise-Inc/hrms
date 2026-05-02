# pos_orders Dedup Filter Rule (S232)

Applies when: writing or modifying any code that READs from Supabase `pos_orders`, `pos_order_items`, or `pos_order_payments`.

## The rule

**Every direct PostgREST read of `pos_orders` / `pos_order_items` / `pos_order_payments` MUST include the `is_duplicate=is.false` filter.** Reads that go through the canonical views (`v_pos_orders_live`, `v_pos_cups_sold`, etc.) are already filtered — those are safe.

The exceptions:
- Freshness / `MAX(business_date)` / `MAX(synced_at)` queries used only for "Last synced HH:MM" display — flagged dupes don't change the max, and the small skew is invisible.
- Reads from the `pos_duplicates` audit table (which is the dedup audit log itself).
- Tombstone-handling code (S169 cancellation path) that operates on individual `id` lookups.

## Why

S232 (2026-05-02) shipped a bill-number-based dedup that flags duplicate `pos_orders` rows with `is_duplicate = true`. The unique partial index `pos_orders_bill_number_natural_key` prevents new dupes from landing. But analytics that read `pos_orders` directly (not through `v_pos_orders_live`) silently double-count the 2,462 historical flagged dupes (and any new ones routed to `pos_duplicates`). That defeats the whole sprint.

S232 audit blocker B1 caught two such direct readers (`hrms/api/discount_abuse.py:1175`, `hrms/api/marketing_giveaways.py:1009`). The S232-followup hardening pass (this rule's source) caught five more (`sales_dashboard.py` cup-by-channel, `store_order_demand_snapshot.py`, `build_demand_snapshots.py`, `detect_anomalies.py`, `s189_backfill_consumption.py`). Without this rule, the next agent that adds an analytics endpoint will re-introduce the bug.

## How to comply

### PostgREST read (Python)
```python
# WRONG — silently includes flagged dupes
rows = _supabase_get_all("pos_orders", [
    ("business_date", f"gte.{start}"),
    ("payment_status", "eq.PAID"),
])

# RIGHT — explicit filter
rows = _supabase_get_all("pos_orders", [
    ("business_date", f"gte.{start}"),
    ("payment_status", "eq.PAID"),
    ("is_duplicate", "is.false"),  # S232: exclude flagged dupes
])
```

### Direct SQL
```sql
-- WRONG
SELECT SUM(gross_sales) FROM pos_orders WHERE business_date = ...

-- RIGHT
SELECT SUM(gross_sales) FROM pos_orders
WHERE business_date = ...
  AND COALESCE(is_duplicate, false) = false
```

### Embedded JOIN (PostgREST `select=...!inner(...)`)
```python
# When the embedded resource is pos_orders, filter both sides
("order.is_duplicate", "is.false")  # exclude flagged parents
("is_duplicate", "is.false")         # exclude flagged child rows (pos_order_items only)
```

### New view
```sql
-- WRONG
CREATE VIEW v_my_metric AS SELECT ... FROM pos_orders WHERE ...;

-- RIGHT — either filter explicitly or build on top of v_pos_orders_live
CREATE VIEW v_my_metric AS
  SELECT ... FROM pos_orders
  WHERE ...
    AND COALESCE(is_duplicate, false) = false;
-- OR
CREATE VIEW v_my_metric AS SELECT ... FROM v_pos_orders_live WHERE ...;
```

## Code to grep before commit

If you modified any analytics, scripts, or API code, run:
```bash
git diff --name-only origin/production | xargs grep -lE 'pos_orders|pos_order_items|pos_order_payments' | \
  xargs grep -L 'is_duplicate'
```

If the output is non-empty AND those files contain new direct reads (not view reads), add the filter.

## Reference

- Sprint S232: `docs/plans/2026-05-02-sprint-232-pos-ingest-hardening-cup-counting.md`
- S232 hardening branch: `s232-hardening-followup`
- Forensic audit: `docs/audits/2026-05-02_pos_vs_analytics_forensic_audit.md`
