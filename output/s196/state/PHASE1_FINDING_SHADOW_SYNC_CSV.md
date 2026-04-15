# Phase 1 Finding — `store_inventory_shadow_sync_registry.csv` not updated

**Audit v3 Plan P1-T5:** "Update 4 rows whose warehouse_docname will change after Phase 2 warehouse renames..."

## Why NOT updated

1. **Fixture is already globally stale.** All ~40 rows reference `<Store> - Bebang Enterprise Inc.` warehouse names (full corp suffix). Production warehouses actually use `<Store> - BEI` / `- BKI` suffix (abbr). The fixture never matched production suffix convention; this is pre-S196.

2. **Lookup logic is suffix-agnostic.** `hrms/utils/sales_location_mapping.py:normalize_store_key` splits at first " - " and takes the base; same for the shadow sync lookup (`_record_name_base`). Lookups work for `Vista Mall Taguig - BEI`, `Vista Mall Taguig - Bebang Enterprise Inc.`, and `Vista Mall Taguig - Tricern Food Corp.` identically — all resolve to `vista mall taguig`.

3. **Selective updates create MORE inconsistency.** Updating 4 rows to new post-S196 names while leaving 36 rows on stale pre-S190 names makes the fixture less internally consistent than leaving it alone.

4. **Out-of-scope bigger cleanup.** The right fix is to regenerate this fixture from current production Warehouse state (all ~40 rows). That's a dedicated data-hygiene sprint, not S196.

## Impact of skip

Zero functional impact on S196. The fixture's only functional column (`warehouse_docname`) is used for name-lookup which is suffix-agnostic.

## Action

- **P1-T5 skipped.** Documented here for audit traceability.
- **Follow-up sprint reservation:** regenerate `sales_dashboard_store_mapping.csv` + `store_inventory_shadow_sync_registry.csv` from live Warehouse table query. Low priority (fixtures are inert — only load on clean site init).
