# Store Inventory Cutover Toggle

## Purpose

Stop the daily Google Sheet mirror for a store the moment that store begins using Frappe/my.bebang as the live inventory source.

## File To Edit

Runtime registry:
- `sites/<site>/private/files/store_inventory_shadow_sync_registry.csv`

Do not edit the fixture unless you are changing the default seed for future environments.

## State Meanings

- `shadow_sync`
  The store still uses the Google Sheet as the operational stock source. Daily `8:00 AM PHT` sync remains active.

- `cutover_ready`
  The store is preparing to cut over. The bridge skips it.

- `frappe_live`
  The store is now live on Frappe/my.bebang inventory workflows. The bridge skips it.

- `sync_disabled`
  Force-disabled. The bridge skips it.

## Cutover Procedure

1. Confirm the store is ready to use Frappe/my.bebang for stock updates and counts.
2. Open `store_inventory_shadow_sync_registry.csv`.
3. Find the row for the target `store_code`.
4. Set:
   - `state=frappe_live`
   - keep `sheet_sync_enabled=true` or set it to `false`; either way the bridge will skip non-`shadow_sync` rows
5. Save the file.
6. Trigger one manual shadow-sync run and confirm the store is skipped.

## Verification

Run:

```python
from hrms.api import erp_sync
erp_sync.run_scheduled_store_inventory_shadow_sync(run_date="2026-03-10", force=True)
```

Then confirm:
- the store does not appear in imported-store results
- the store's existing Frappe balances remain unchanged

## Rollback

If the cutover is reverted:

1. Change `state` back to `shadow_sync`
2. Set `sheet_sync_enabled=true`
3. Rerun the bridge manually for that store

## Non-Negotiable Rule

Never leave a live Frappe store in `shadow_sync`. If you do, the next morning sheet run can overwrite the ERP-maintained position.

