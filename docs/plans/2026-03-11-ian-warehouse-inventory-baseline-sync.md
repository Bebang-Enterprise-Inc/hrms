# Ian Warehouse Inventory Baseline Sync

Date: 2026-03-11

## Purpose

Prepare Frappe inventory so Ian can start warehouse operations from Frappe with a daily 8:00 AM PHT baseline sync from the active warehouse workbook.

## Active Source

- Workbook: `2026 MARCH BEBANG INVENTORY`
- Spreadsheet ID: `19Hm25vaj9gD8p6z_M6-4CPWvcXaPzAeOFKlUZ298V4s`
- Tab: `SUMMARY 2026`
- Receiver key: `inventory`

## Why This Needs a Transformer

`SUMMARY 2026` is a matrix report, not a row-based table.

The receiver must pivot warehouse columns into canonical inventory rows before syncing to Frappe:

- `3MD` -> `3MD Logistics - Camangyanan - BEI`
- `JENTEC` -> `Jentec Storage Inc. - BEI`
- `RCS` -> `Royal Cold Storage - Taytay - BEI`
- `PINNACLE` -> `Pinnacle Cold Storage - BEI`
- `SHAW` -> `Shaw BLVD - BEI`

Each transformed row is keyed by `inventory_key = <warehouse_code>::<item_code>`.

## Runtime Behavior

- Daily baseline scheduler includes `inventory` at `8:00 AM PHT`
- Manual force sync endpoint:
  - `POST /api/sync/inventory?force=true`
- Receiver sends `inventory` in per-warehouse chunks using `warehouse_source_code`
  so each Frappe request stays below the gateway timeout envelope
- Payload written to Frappe inventory sync:
  - `item_code`
  - `warehouse`
  - `qty`

This produces warehouse-level `Stock Reconciliation` entries in Frappe using the transformed source rows.

## Production Hardening

- Zero-qty rows for item codes missing from Frappe Item master are skipped instead of
  failing the whole inventory baseline.
- This rule is intentionally narrow:
  - missing item + zero qty = skip
  - missing item + non-zero qty = fail
- Batch-tracked items in the Ian warehouse baseline now receive deterministic synthetic
  `INVBASE-*` batch IDs when the source workbook only has aggregate quantities and no
  lot detail.
- This keeps Frappe batch validation satisfied while preserving a clear audit marker
  that these are baseline placeholder batches, not supplier-origin lot numbers.
- When an inventory baseline item has no recoverable valuation source, the baseline sync
  now allows zero valuation rate so quantities can land in Frappe instead of blocking the
  whole warehouse cutover.
- Warehouse chunks that result in no stock ledger movement are treated as successful no-op
  syncs instead of hard failures.
- On 2026-03-11, live reconciliation against `SUMMARY 2026` found only `9` missing
  item codes and all `9` were zero-stock rows, so they are treated as obsolete/no-op
  rows instead of cutover blockers.
- Audit artifact:
  - `F:\\Dropbox\\Projects\\BEI-ERP\\tmp\\inventory_missing_item_audit_2026-03-11.md`

## Verification

Local verification used for this change:

- `python hrms/tests/test_sheets_receiver_config.py`
- `python hrms/tests/test_sheets_receiver_main.py`
- `python hrms/tests/test_sheets_receiver_processor.py`
- `python hrms/tests/test_sheets_receiver_transforms.py`
- `python hrms/tests/test_erp_sync.py`
- `python -m py_compile hrms/services/sheets_receiver/config.py hrms/services/sheets_receiver/main.py hrms/services/sheets_receiver/sheets_client.py hrms/services/sheets_receiver/processor.py hrms/services/sheets_receiver/transforms.py`

Live source parse check on 2026-03-11:

- `163` raw `SUMMARY 2026` rows
- `630` transformed inventory rows across the 5 warehouse buckets
