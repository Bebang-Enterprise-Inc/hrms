# S169 T0.4 — View Dependency Audit & Rewrite Order

**Date:** 2026-04-07
**Source:** Supabase prod `csnniykjrychgajfrgua`, `pg_matviews`/`pg_views`/`pg_depend`

## Object inventory

**Plan expected:** 12 objects (6 MVs + 6 regular views)
**Actual:** 12 objects matching `definition ILIKE '%pos_orders%'` — but
`pg_depend` reveals a **13th object** that depends on the inventory transitively.

### The 12 direct `pos_orders` references

| # | Kind | Schema.Name |
|---|---|---|
| 1 | MV | public.discount_summary |
| 2 | MV | public.daily_revenue |
| 3 | MV | public.store_daily_closing |
| 4 | MV | public.sales_dashboard_daily_store_metrics |
| 5 | MV | public.payment_reconciliation |
| 6 | MV | public.store_daily_baselines |
| 7 | VIEW | public.v_all_channel_daily |
| 8 | VIEW | public.v_ops_weekly |
| 9 | VIEW | public.v_system_daily_totals |
| 10 | VIEW | public.v_orders |
| 11 | VIEW | public.v_monthly_store_summary |
| 12 | VIEW | public.v_discount_identity_order_usage |

### 13th object (transitive — DISCREPANCY vs plan)

| # | Kind | Schema.Name | Depends on |
|---|---|---|---|
| 13 | VIEW | public.v_discount_identity_rolling_30d_usage | public.v_discount_identity_order_usage |

This view does **not** mention `pos_orders` directly so it was missed by the
plan's `definition ILIKE '%pos_orders%'` filter, but it depends on
`v_discount_identity_order_usage` which does. Any DROP/REPLACE of the 12 must
be sequenced so that #13 is dropped first and recreated last.

**Plan compliance note (T0.4 hard blocker rule):** "If the audit reveals a
13th object (not in the current list of 12), STOP — update the plan's
hard-coded '12 objects' inventory everywhere (Phase Budget, Requirements
Regression, verify_s169.py, this task list) in the same edit, then resume."
This update is **gated behind the T0.3 phantom-scan STOP** above and should be
done as part of the same scope discussion.

## Dependency edges (from pg_depend / pg_rewrite)

All edges live in `public` schema. **No cross-schema or external-database
consumers were detected.** (Supabase `bei-tasks` reads via PostgREST against
these same views — that's a logical consumer, but not a `pg_depend` edge.)

```
pos_orders (table, base)
├── daily_revenue                            (MV)
├── discount_summary                         (MV)  also <- pos_order_items
├── payment_reconciliation                   (MV)
├── sales_dashboard_daily_store_metrics      (MV)  also <- pos_order_items
├── store_daily_baselines                    (MV)
├── store_daily_closing                      (MV)
│   └── v_system_daily_totals                (VIEW)   <-- view-on-MV
├── v_all_channel_daily                      (VIEW)
│   └── v_ops_weekly                         (VIEW)   <-- view-on-view
├── v_discount_identity_order_usage          (VIEW)  also <- pos_order_items
│   └── v_discount_identity_rolling_30d_usage (VIEW) <-- 13TH OBJECT
├── v_monthly_store_summary                  (VIEW)
└── v_orders                                 (VIEW)
```

### Critical dependency chains (must be respected)

1. `v_discount_identity_rolling_30d_usage` -> `v_discount_identity_order_usage` (view-on-view)
2. `v_ops_weekly` -> `v_all_channel_daily` (view-on-view)
3. `v_system_daily_totals` -> `store_daily_closing` (**view-on-MV** — fragile, view will break if MV is dropped without CASCADE)

**No MV depends on another MV.** (`store_daily_closing` is consumed by a view,
not by another MV.) This simplifies REFRESH ordering — all 6 MVs can be
refreshed in parallel after a Phase 1 schema migration.

## Topological rewrite order

### DROP order (leaf-first, for `DROP VIEW`/`DROP MATERIALIZED VIEW`)

1. `v_discount_identity_rolling_30d_usage` (VIEW, leaf — depends on #2)
2. `v_discount_identity_order_usage` (VIEW)
3. `v_ops_weekly` (VIEW, depends on #4)
4. `v_all_channel_daily` (VIEW)
5. `v_system_daily_totals` (VIEW, depends on #6)
6. `store_daily_closing` (MV)
7. `v_orders` (VIEW)
8. `v_monthly_store_summary` (VIEW)
9. `daily_revenue` (MV)
10. `discount_summary` (MV)
11. `payment_reconciliation` (MV)
12. `sales_dashboard_daily_store_metrics` (MV)
13. `store_daily_baselines` (MV)

### CREATE order (root-first — reverse of DROP)

1. `store_daily_baselines` (MV)
2. `sales_dashboard_daily_store_metrics` (MV)
3. `payment_reconciliation` (MV)
4. `discount_summary` (MV)
5. `daily_revenue` (MV)
6. `v_monthly_store_summary` (VIEW)
7. `v_orders` (VIEW)
8. `store_daily_closing` (MV)
9. `v_system_daily_totals` (VIEW) — depends on store_daily_closing
10. `v_all_channel_daily` (VIEW)
11. `v_ops_weekly` (VIEW) — depends on v_all_channel_daily
12. `v_discount_identity_order_usage` (VIEW)
13. `v_discount_identity_rolling_30d_usage` (VIEW) — depends on v_discount_identity_order_usage

### Recommendation

For Phase 2 column additions (e.g., `is_voided`, `cancelled_at`,
`mosaic_order_id`), use `DROP MATERIALIZED VIEW ... CASCADE` semantics inside
a single transaction is **not safe** for MVs (CASCADE will silently take views
9 and 11 with it). Prefer the explicit DROP-CREATE script in the order above
inside one transaction with `BEGIN; ... COMMIT;`.

## Definitions captured

- `tmp/s169_view_definitions_before.sql` (12 verbatim definitions)
- `output/l3/s169/view_definitions_before.sql` (mirror copy)

Note: the 13th view (`v_discount_identity_rolling_30d_usage`) was NOT captured
in the SQL snapshot because it does not directly reference `pos_orders`. A
follow-up T0.4b must capture its definition before any DROP/CREATE work
begins, or it will be lost.
