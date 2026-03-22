# 2026-03-11 Store Inventory Shadow Sync Hardening Follow-Up

## Live issue found during production simulation

The first hardening patch deployed successfully, but a live watchdog simulation exposed two remaining gaps:

1. `store_inventory_shadow_sync.py` wrote `last_run.generated_at` / `updated_at` using plain `datetime.now()` from the container.
2. `erp_sync.watch_store_inventory_shadow_sync_health()` compared those timestamps to `frappe.utils.now_datetime()`.

Because production is interpreted in `Asia/Manila`, while the container-level `datetime.now()` behaved as UTC, the watchdog saw active runs as artificially older than they really were and could enqueue recovery too early.

The same simulation also showed that the runtime heartbeat only moved after an entire store completed. That is too coarse for large workbook exports and extraction steps because a healthy but slow store can look stalled.

## Follow-up fix

- Make `_now_ts()` use `frappe.utils.now_datetime()` when Frappe is available.
- Add stage-level heartbeats during:
  - `starting`
  - `exporting_workbook`
  - `extracting_inventory`
  - `syncing_inventory`
  - `completed_store`
  - final `completed`
- Persist `current_store_code`, `current_store_name`, and `current_stage` into `last_run` for operational debugging.

## Local verification

- `pytest hrms/tests/test_store_inventory_shadow_sync.py -q` -> `6 passed`
- `pytest hrms/tests/test_erp_sync_runtime.py -q` -> `5 passed`
- `pytest hrms/tests/test_erp_sync.py -q` -> `38 passed`
- `ruff check hrms/utils/store_inventory_shadow_sync.py hrms/tests/test_store_inventory_shadow_sync.py hrms/tests/test_erp_sync_runtime.py` -> `All checks passed`
