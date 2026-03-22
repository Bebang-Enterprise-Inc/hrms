# Store Inventory Shadow Sync Runbook

## Purpose

Mirror each enabled store's Google Sheet `3. INVENTORY` tab into Frappe every day at `7:00 AM PHT` (`23:00 UTC` previous day) until that store cuts over to Frappe/my.bebang as the stock source of truth.

## Scheduler

- Hook: `hrms.api.erp_sync.enqueue_scheduled_store_inventory_shadow_sync`
- Schedule: `0 23 * * *`
- Runtime job: `hrms.api.erp_sync.run_scheduled_store_inventory_shadow_sync`
- Morning health report schedule: `15 0 * * *`
- Morning health report writer: `hrms.api.erp_sync.scheduled_generate_morning_sync_health_report`

## Morning Health Report

Use the morning report to confirm, before `9:00 AM PHT`, whether all critical sync lanes are ready:

- store inventory shadow sync
- Ian warehouse inventory baseline
- AP / procurement baselines

API entry point:

- `hrms.api.erp_sync.get_morning_sync_health_report`

Artifact paths:

- `sites/<site>/private/files/morning_sync_health_reports/YYYY-MM-DD_morning_sync_health_report.json`
- `sites/<site>/private/files/morning_sync_health_reports/YYYY-MM-DD_morning_sync_health_report.md`

Status meaning:

- `green`: every area completed before `9:00 AM PHT` with no failed-row exceptions
- `yellow`: every area completed before `9:00 AM PHT`, but at least one area completed with exceptions
- `red`: at least one area missed the deadline or the receiver summary could not be fetched

## Registry And State

Default registry fixture:
- `hrms/fixtures/store_inventory_shadow_sync/store_inventory_shadow_sync_registry.csv`

Runtime registry copy:
- `sites/<site>/private/files/store_inventory_shadow_sync_registry.csv`

Runtime state file:
- `sites/<site>/private/files/store_inventory_shadow_sync_state.json`

Per-run output directory:
- `sites/<site>/private/files/store_inventory_shadow_sync_runs/YYYY-MM-DD_store_inventory_shadow_sync/`

## Resumability

The bridge checkpoints progress after each processed store.

What gets checkpointed:
- runtime registry CSV
- runtime state JSON
- `summary.json`
- `summary.md`

Operational effect:
- if a deploy or worker restart interrupts the batch, already completed stores keep their updated checksum and success markers
- the next rerun skips unchanged completed stores instead of starting the whole day from zero
- workbook exports are written to `.xlsx.part` first and only promoted to `.xlsx` after a successful download, so a killed download does not leave a fake finished workbook

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

## Shadow Valuation Policy

The store sheets do not carry reliable valuation data. For each imported row, the bridge tries valuation in this order:

1. explicit payload `valuation_rate`
2. existing `Bin.valuation_rate` for the same store warehouse
3. latest positive `Stock Ledger Entry` valuation for the same store warehouse
4. any positive `Bin` / `Stock Ledger Entry` valuation for the same item elsewhere in Frappe
5. `Item.valuation_rate`
6. `Item.last_purchase_rate`

If none of those produce a positive rate and the row is part of the pre-cutover shadow sync, the bridge sets `allow_zero_valuation_rate = 1` so the operational qty can still mirror into Frappe.

This zero-rate fallback is temporary and operational. It keeps `Bin.actual_qty` correct for ordering, but it is not a substitute for real stock valuation policy.

## Operator Controls

Edit the runtime registry CSV, not the fixture, to control live behavior.

Relevant columns:
- `sheet_sync_enabled`
- `state`
- `notes`

Company binding:
- each `Stock Reconciliation` posts under the target warehouse's owning company, not the global default company

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
- `summary.json.status = completed`

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

If the job is interrupted mid-batch by deploy or worker restart:

1. Confirm the last `summary.json` shows `status = in_progress` or stale counters
2. Rerun the same run date with `force=True`
3. Expect already checkpointed stores to skip by checksum and the batch to continue from the remaining stores

