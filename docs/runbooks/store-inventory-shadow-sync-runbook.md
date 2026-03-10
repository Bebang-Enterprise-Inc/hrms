# Store Inventory Shadow Sync Runbook

## Purpose

Mirror each enabled store's Google Sheet `3. INVENTORY` tab into Frappe every day at `8:00 AM PHT` (`00:00 UTC`) until that store cuts over to Frappe/my.bebang as the stock source of truth.

## Scheduler

- Hook: `hrms.api.erp_sync.enqueue_scheduled_store_inventory_shadow_sync`
- Schedule: `0 0 * * *`
- Runtime job: `hrms.api.erp_sync.run_scheduled_store_inventory_shadow_sync`

## Registry And State

Default registry fixture:
- `hrms/fixtures/store_inventory_shadow_sync/store_inventory_shadow_sync_registry.csv`

Runtime registry copy:
- `sites/<site>/private/files/store_inventory_shadow_sync_registry.csv`

Runtime state file:
- `sites/<site>/private/files/store_inventory_shadow_sync_state.json`

Per-run output directory:
- `sites/<site>/private/files/store_inventory_shadow_sync_runs/YYYY-MM-DD_store_inventory_shadow_sync/`

## Resolution Policy

The bridge resolves quantity in this order:

1. `encode`
2. `total`
3. latest dated `END` value on or before the run date
4. `blank_zero_policy`

`blank_zero_policy` is explicit, not silent:
- it applies only when the row has no positive stock signal at all
- it is necessary so unchanged blank rows do not preserve stale prior balances forever
- formula errors still remain quarantined and are never imported

Rows with `#REF!` or any other formula error land in `store_inventory_exceptions.csv`.

## First-Run Bootstrap

The bridge bootstraps missing master data idempotently before syncing:

- missing store warehouses under `Stores - BEI`
- missing item masters explicitly marked `create_item` in `store_inventory_item_mapping.csv`
- stable synthetic `Batch` records for batch-tracked items mirrored from aggregate sheet totals

Current expected bootstrap scope:
- Warehouses: `NAIA T3`, `SM Sta. Rosa`, `SM Taytay`, `Greenhills Ortigas`
- Items: `FG021`, `FG022`, `RM010-A`

## Shadow Batch Policy

The store inventory sheets do **not** provide real batch-level stock detail. For pre-cutover stores only, the bridge uses one stable synthetic batch per `store_code + item_code` for batch-tracked items so Frappe can maintain correct `Bin.actual_qty`.

Policy:
- pattern: `SHADOW-<STORE_CODE>-<ITEM_CODE>`
- example: `SHADOW-AFT-FG001`
- scope: only `Store Inventory Shadow Sync*` runs
- purpose: temporary aggregate on-hand mirror until the store cuts over to Frappe/my.bebang
- stop condition: once a store moves out of `shadow_sync`, the sheet bridge stops updating that store

This is an operational mirror policy, not a claim that the workbook contains true batch lineage.

## Operator Controls

Edit the runtime registry CSV, not the fixture, to control live behavior.

Relevant columns:
- `sheet_sync_enabled`
- `state`
- `notes`

Allowed active state for the bridge:
- `shadow_sync`

States skipped by the bridge:
- `cutover_ready`
- `frappe_live`
- `sync_disabled`

## Manual Run

Queue from Frappe console:

```python
frappe.call("hrms.api.erp_sync.enqueue_scheduled_store_inventory_shadow_sync", run_date="2026-03-10")
```

Run immediately from Frappe console:

```python
from hrms.api import erp_sync
erp_sync.run_scheduled_store_inventory_shadow_sync(run_date="2026-03-10", force=True)
```

## Verification

After a run, inspect:

1. `summary.json`
2. `summary.md`
3. `store_inventory_payload.csv`
4. `store_inventory_exceptions.csv`
5. `store_inventory_resolution_audit.csv`

Expected healthy outcome:
- `rows_failed = 0` from Frappe sync
- changed stores imported once
- unchanged stores skipped by checksum
- only formula-error rows remain in exceptions

## Recovery

If one store fails:

1. Check `last_error` in the runtime registry CSV
2. Fix the specific warehouse/item/config issue
3. Rerun for that store only:

```python
from hrms.utils import store_inventory_shadow_sync
store_inventory_shadow_sync.run_store_inventory_shadow_sync(
    run_date="2026-03-10",
    force=True,
    store_codes=["AFT"],
)
```

If the registry is corrupted:

1. Back up the runtime CSV
2. Replace it with the fixture copy
3. Restore the needed `state` / `sheet_sync_enabled` edits

