# Sprint 31 Store Inventory Import and 8AM Shadow Sync Plan

- canonical_sprint_id: `S031`
- display_name: `Sprint 31`
- status: `In Progress`
- owner: `Control Cell`
- date_pht: `2026-03-10`
- policy_ref: `docs/plans/SPRINT_NUMBERING_POLICY.md`
- previous_sprint_ref: `docs/plans/2026-03-09-sprint-30-analytics-agent-10x-report.md`
- scope_ref_1: `docs/plans/2026-03-09-sprint-21-stockout-control-command.md`
- scope_ref_2: `docs/plans/2026-03-09-sprint-27-full-surface-e2e-l1-l4-operational-certification.md`
- required_skill_workflows:
  - `execute-plan-bei-erp`
  - `feature-branch-bei-erp`
  - `inventory-control-bei-erp`
  - `frappe-expert-bei-erp`
  - `deploy-frappe-bei-erp`

## Scope Window

Tuesday, 2026-03-10 cutover prep + temporary bridge until each store fully cuts over from sheets to Frappe

## Objective

Create a controlled store-inventory bridge that:

1. Imports the extracted `3. INVENTORY` current balances into Frappe as store opening stock.
2. Keeps store inventory mirrored from Google Sheets every morning at **7:00 AM PHT** until cutover is complete.
3. Preserves the full workbook history for analytics without polluting Frappe's live stock ledger with synthetic historical transactions.
4. Stops sheet-driven updates per store the moment that store starts using Frappe/my.bebang.ph as the stock source of truth.
5. Tracks the linked reordering dependency: store order prefills must become sales-driven, and current FoodPanda workbook data only supports consolidated sales until an item-level FoodPanda pipeline exists.

## Evidence Snapshot

- Full workbook extraction already exists and was re-verified from source:
  - `46` store workbooks downloaded
  - `46/46` include `3. INVENTORY`
  - normalized extraction output:
    - `4,738` current inventory rows
    - `1,743,582` daily long-format rows
    - `100.0%` verification pass on sampled store-level source checks
- Current extraction artifacts already available:
  - `data/Big_Data_Refinery/_run_artifacts/2026-03-09_store_inventory_extraction/inventory_items_current.csv`
  - `data/Big_Data_Refinery/_run_artifacts/2026-03-09_store_inventory_extraction/inventory_daily_long.csv`
  - `data/Big_Data_Refinery/_run_artifacts/2026-03-09_store_inventory_extraction/inventory_store_summary.csv`
- Live store ordering reads stock from Frappe `Bin.actual_qty`, not from the Google Sheets:
  - `hrms/api/store.py` `get_orderable_items`
- Live inventory import path already exists and writes `Stock Reconciliation` documents:
  - `hrms/api/erp_sync.py` `sync_inventory`
- Idempotency test already exists for the inventory sync path:
  - `hrms/tests/test_erp_sync.py` `test_sync_inventory_is_idempotent_by_sync_reference`
- Sheets Receiver already provides a production scheduler, checksum tracking, retries, and webhook/watch management:
  - `hrms/services/sheets_receiver/`
- Existing scheduler currently runs fallback sheet sync every `6` hours, not at `7:00 AM PHT`:
  - `hrms/services/sheets_receiver/main.py`
- Existing in-app stock count / daily stock update path already exists for post-cutover operation:
  - `hrms/api/inventory.py` `daily_stock_update`
- Current store ordering contract already supports sales-driven recommendation fields:
  - `forecast_demand`
  - `recommended_qty`
  - `suggested_qty`
  - `available_to_promise`
  - `risk_rank`
  - source: `hrms/hr/doctype/bei_store_order_item/bei_store_order_item.json`
- Current ordering engine is still heuristic and does **not** read Supabase sales directly:
  - `hrms/api/store.py` `_estimate_projected_sales_and_bom`
  - `hrms/api/store.py` `get_orderable_items`
- Current FoodPanda workbook (`1F9Zqn_5r42iLSWkHZqGaFr-a6-zXj5eOg52DJ3Oac78`) already has a valid **order-header** flow:
  - raw: `FP SUMMARY`
  - clean: `FP_CLEAN`
  - rejects: `FP_REJECTS`
  - daily fact: `SALES_FACT_DAILY_FINAL`
- Current FoodPanda workbook does **not** yet have an item-level pipeline, so FoodPanda can support:
  - consolidated sales
  - order counts
  - store/day revenue
  - P&L revenue packaging
  - but **not** exact item-level demand or BOM-driven reorder prefills
- Current extraction is not yet Frappe-ready:
  - only `1,471` rows have `total`
  - `2,145` rows have `encode`
  - only `2,214` rows have any current-balance field populated
  - `2,524` rows have no current-balance field populated
  - `5` rows contain `#REF!`
  - `3` stores have zero populated current-balance rows in the current snapshot: `NAIA`, `ROBIM`, `UPTC`
- Live baseline verification before bridge import showed sampled and then full existing store warehouses had `0` nonzero `Bin.actual_qty` rows, so a controlled `blank_zero_policy` can be used for rows with no positive stock signal to avoid preserving stale prior balances during the daily mirror.

## Source-of-Truth Rules

1. **Pre-cutover store rule:** until a store is explicitly cut over, its sheet remains the operational source of truth and Frappe is a mirrored copy.
2. **Frappe operational rule:** only the **current on-hand state** is imported into Frappe for store operations. Do not backfill the entire workbook history into Frappe stock ledgers.
3. **Analytics rule:** preserve the whole workbook plus normalized history in the data refinery for reporting, reconciliation, and migration audit.
4. **Post-cutover rule:** once a store starts using my.bebang/Frappe for stock updates and counts, stop sheet-based reconciliation for that store to prevent overwriting live ERP activity.
5. **No silent drops:** any unmapped item, invalid quantity, blank current balance, or formula error must land in an exception report, not disappear during import.
6. **Shadow batch rule for pre-cutover stores:** when a store sheet only exposes aggregate qty for a batch-tracked item, the bridge may maintain a stable synthetic shadow batch per `store_code + item_code` solely to keep `Bin.actual_qty` correct until cutover.
7. **Shadow valuation rule for pre-cutover stores:** when a row carries positive qty but Frappe has no positive valuation signal for that item anywhere, the bridge may submit the row with `allow_zero_valuation_rate = 1` so operational quantities can mirror without inventing a fake cost.
8. **Interruption tolerance rule:** the shadow sync must checkpoint registry/state/summary after each processed store and use temp-file workbook exports so a production deploy or worker restart can be resumed without redoing already completed stores.

## Staleness Note

Some older docs still describe `erp_sync.sync_inventory` as a log-only stub. The live code and tests now show a real `Stock Reconciliation` write path. This plan follows the live codebase, not the stale audit note.

## Duplication Audit

| Workstream | Existing Asset | Classification | Plan Decision |
|---|---|---|---|
| Store workbook downloads | `data/_tools/download_store_workbooks_by_id.py` | `[EXTEND]` | Reuse for deterministic workbook export when shadow sync needs a fresh pull |
| Store workbook extraction | `data/_tools/extract_store_inventory_from_workbooks.py` | `[EXTEND]` | Reuse as the canonical `3. INVENTORY` normalizer |
| Inventory import into Frappe | `hrms/api/erp_sync.py` `sync_inventory` | `[EXTEND]` | Reuse as the Frappe-side write path |
| Inventory import idempotency proof | `hrms/tests/test_erp_sync.py` | `[EXTEND]` | Extend tests rather than creating a second import path |
| Sheets scheduling/checksums/retries | `hrms/services/sheets_receiver/` | `[EXTEND]` | Reuse scheduler + state patterns instead of building a new daemon |
| Store ordering stock consumption | `hrms/api/store.py` `get_orderable_items` | `[EXTEND]` | Verify imported balances against this existing read path |
| Store ordering recommendation contract | `hrms/hr/doctype/bei_store_order_item/bei_store_order_item.json` + my.bebang ordering hooks/routes | `[EXTEND]` | Reuse the existing recommendation payload contract instead of redesigning the UI |
| Post-cutover store counting | `hrms/api/inventory.py` `daily_stock_update` | `[EXTEND]` | Use this as the handoff destination after sheet sync is disabled |
| FoodPanda order-header sales pipeline | workbook tabs `FP SUMMARY` -> `FP_CLEAN` -> `FP_REJECTS` -> `SALES_FACT_DAILY_FINAL`; `scripts/sync_foodpanda_to_supabase.py` | `[EXTEND]` | Keep this as the consolidated-sales and P&L revenue path |
| Current snapshot -> Frappe payload transform | no dedicated transformer found | `[BUILD]` | Build a bridge script that outputs `item_code, warehouse, qty` rows |
| Per-store cutover switch | no explicit cutover registry found | `[BUILD]` | Build an operator-visible cutover config to disable sheet sync store-by-store |
| Morning 7AM inventory job | no store-workbook-specific 7AM job found | `[BUILD]` | Build a new scheduled runner on top of existing service patterns |
| Sales-driven store demand snapshot | no store-item demand snapshot feeding `get_orderable_items` found | `[BUILD]` | Build a compact Frappe-side demand snapshot fed by Supabase sales + stock |
| FoodPanda item-level workbook pipeline | no `FP_ITEMS_*` / `SALES_FACT_ITEM_DAILY` flow found | `[BUILD]` | Add a dedicated FoodPanda item pipeline so the channel can participate in future item-level reorder forecasts |
| New frontend admin UI for sync control | none required for first delivery | `[SKIP]` | Keep control in config/runbook first; add UI only if operator friction appears |

## In Scope

- Importing the extracted store `3. INVENTORY` current balances into Frappe store warehouses
- Building the transformation and exception pipeline needed before calling `sync_inventory`
- Adding a **7:00 AM PHT** automated shadow sync for store workbooks
- Per-store sync enable/disable and cutover state
- Verification against `Bin.actual_qty` and store ordering availability
- Preserving workbook history for analytics
- Operator runbook for morning sync, exceptions, retry, and cutover disablement

## Out Of Scope

- Importing the full workbook history into Frappe stock ledger as synthetic historical transactions
- Replacing my.bebang cycle count / daily stock update flows
- Building a new frontend admin console for sync control in the first release
- Intraday continuous sync; this plan is for a daily morning bridge
- Reworking warehouse procurement, dispatch, or valuation logic unrelated to the bridge

## Linked Reordering Dependency

This plan remains primarily an inventory bridge plan, but store reordering depends on it and must not be forgotten.

Required downstream direction:

1. Store ordering recommendations should move from the current heuristic model to a sales-driven demand snapshot.
2. POS and website already have line-item demand sources in Supabase.
3. FoodPanda must participate through the item-level workbook flow, not just consolidated sales:
   - `FP_ITEMS_RAW`
   - `FP_ITEMS_MAPPING`
   - `FP_ITEMS_CLEAN`
   - `FP_ITEMS_REJECTS`
   - `SALES_FACT_ITEM_DAILY`
4. Historical `FP SUMMARY` data must be backfilled into `FP_ITEMS_RAW` first using existing `Order Items` / flavor-count signals so the pipeline is tested on past data before ops relies on future manual item processing.
5. The sales-driven demand snapshot must use an explicit product policy registry plus a component-recipe registry for Tikim, add-ons, and direct stock items; no silent alias-only fallback is acceptable for production ordering.
6. Products that are intentionally not warehouse-replenished must land in an explicit excluded-product audit, not disappear from the demand build.

Reference notes:

- `tmp/2026-03-09_sales_demand_pipeline_for_store_ordering.md`
- `tmp/2026-03-09_foodpanda_sheet_schema_audit.md`

## Execution Workflow

- Test Python changes: `/local-frappe`
- Deploy changes: `/deploy-frappe`
- Full workflow: `/agent-kickoff`
- E2E/testing: `/e2e-test` or targeted API + DB verification

## Phase Plan

### Phase 1: Freeze Inputs and Build Mapping Inventory

**Goal:** Turn the verified extraction into a deterministic import source with no implicit assumptions.

Inputs:

- `data/Big_Data_Refinery/_run_artifacts/2026-03-09_store_inventory_extraction/inventory_items_current.csv`
- `data/Big_Data_Refinery/_run_artifacts/2026-03-09_store_inventory_extraction/inventory_daily_long.csv`
- `data/Big_Data_Refinery/_run_artifacts/2025-12-26/store_registry/store_registry.csv`
- live Frappe `Item` and `Warehouse` masters

Deliverables:

- `data/_CLEANROOM/2026-03-09-store-inventory-bridge/README.md`
- `data/_CLEANROOM/2026-03-09-store-inventory-bridge/provenance.md`
- `data/_CLEANROOM/2026-03-09-store-inventory-bridge/store_inventory_store_warehouse_mapping.csv`
- `data/_CLEANROOM/2026-03-09-store-inventory-bridge/store_inventory_item_mapping.csv`
- `data/_CLEANROOM/2026-03-09-store-inventory-bridge/store_inventory_current_resolution.csv`
- `data/_CLEANROOM/2026-03-09-store-inventory-bridge/store_inventory_exceptions.csv`

Required logic:

1. Map every `store_code` to the exact Frappe warehouse name used by store ordering.
2. Map every sheet inventory code / description / UOM combination to a Frappe `item_code`.
3. Resolve current quantity using deterministic precedence:
   - `encode` if numeric
   - else `total` if numeric
   - else derive from `whole + loose` only when a trusted conversion rule exists
   - else fallback to the most recent `inventory_daily_long.end` value on or before the run date
   - else send to exceptions
4. Hard-fail formula errors like `#REF!` into the exception report.
5. Produce explicit classification for every extracted row:
   - `ready_to_import`
   - `blank_current_qty`
   - `needs_conversion_rule`
   - `item_unmapped`
   - `warehouse_unmapped`
   - `formula_error`
   - `skip_non_stock_or_zero_policy`

Exit gate:

- `100%` warehouse mapping
- `100%` row classification
- no implicit qty derivation without a written rule

### Phase 2: Build Frappe-Ready Import Payloads

**Goal:** Convert the resolved current state into grouped, idempotent stock-reconciliation inputs.

Deliverables:

- `data/_CLEANROOM/2026-03-09-store-inventory-bridge/store_inventory_frappe_payload.csv`
- `data/_CLEANROOM/2026-03-09-store-inventory-bridge/store_inventory_payload_by_store.json`
- `data/_CLEANROOM/2026-03-09-store-inventory-bridge/import_summary.md`
- new transformer script under `data/_tools/`

Required logic:

1. Output canonical fields:
   - `store_code`
   - `warehouse`
   - `item_code`
   - `qty`
   - `qty_source`
   - `inventory_date`
   - `source_workbook`
   - `source_row`
2. Group payloads by target warehouse because `sync_inventory` dedupes per checksum + warehouse.
3. Generate deterministic payload checksums so reruns with unchanged data do not create duplicate `Stock Reconciliation` docs.
4. Preserve a machine-readable import manifest for audit and rollback.
5. For batch-tracked items without source batch detail, use an explicit stable shadow batch identifier rather than silently dropping the row.

Exit gate:

- payload rows are valid against live `Item` and `Warehouse`
- exception rows are separated from import rows
- rerunning the same payload is provably idempotent

### Phase 3: Dry Run and Opening Balance Import

**Goal:** Load store opening balances into Frappe without guessing and verify that store-ordering stock reads reflect the result.

Deliverables:

- import runner script under `data/_tools/`
- `data/_CLEANROOM/2026-03-09-store-inventory-bridge/import_run_manifest.json`
- `data/_CLEANROOM/2026-03-09-store-inventory-bridge/import_verification.csv`
- `data/_CLEANROOM/2026-03-09-store-inventory-bridge/import_exceptions_after_write.csv`

Execution sequence:

1. Dry-run import for a small sample set first:
   - one store with rich current balances
   - one store with blank-current fallback behavior
2. Verify after write:
   - `Stock Reconciliation` created as expected
   - `Bin.actual_qty` matches payload
   - `hrms.api.store.get_orderable_items` shows the expected `available_stock` for sampled items
   - batch-tracked items reconcile through the documented shadow-batch policy rather than failing on missing serial/batch bundles
3. Run full-store import only after sample verification passes.

Exit gate:

- sample stores pass API + DB verification
- full import produces one deterministic reconciliation path per store payload
- no unresolved exception rows are silently imported

### Phase 4: 8:00 AM PHT Shadow Sync Automation

**Goal:** Keep sheets mirrored into Frappe every morning until each store cuts over.

Design choice:

- Reuse the **deployment/scheduling/checksum patterns** from `hrms/services/sheets_receiver`
- Do **not** try to treat the store workbooks as a simple `A:Z` tab sync
- The automated job should still use the proven workbook export + `3. INVENTORY` extraction path

Deliverables:

- new scheduled runner under `hrms/services/sheets_receiver/` or `data/_tools/`
- operator config file:
  - `data/Big_Data_Refinery/_config/store_inventory_shadow_sync_registry.csv`
- runtime sync state in the Sheets Receiver SQLite DB or equivalent runtime store
- `docs/runbooks/store-inventory-shadow-sync-runbook.md`

Required behavior:

1. Run every day at **08:00 PHT**.
   - If service host runs in UTC, schedule at **00:00 UTC**.
2. Read the store registry and only process stores where `sheet_sync_enabled = true`.
3. Export fresh workbooks only for enabled stores.
4. Re-extract `3. INVENTORY`.
5. Rebuild the resolved Frappe payload.
6. Compare payload checksum by store/warehouse with the last successful checksum.
7. Skip unchanged stores.
8. Import only changed stores through `sync_inventory`.
9. Save:
   - `last_checksum`
   - `last_success_at`
   - `last_error`
   - imported store count
   - skipped unchanged count
10. Emit an operator-visible run report after each 8AM cycle.

Exit gate:

- unchanged reruns create no duplicate reconciliations
- changed-store-only processing works deterministically
- 8AM schedule runs without manual intervention

### Phase 5: Cutover Switch and Handoff to In-App Counting

**Goal:** Prevent the bridge from overwriting live Frappe activity after a store starts using ERP stock updates.

Deliverables:

- per-store cutover registry
- `docs/runbooks/store-inventory-cutover-toggle.md`
- verification checklist for disabling sheet sync per store

Required behavior:

1. Add explicit store states, at minimum:
   - `shadow_sync`
   - `cutover_ready`
   - `frappe_live`
   - `sync_disabled`
2. Only stores in `shadow_sync` continue receiving the 8AM sheet import.
3. When a store moves to `frappe_live`, daily sheet import must stop for that store.
4. Post-cutover stock maintenance must use:
   - my.bebang daily stock update
   - cycle count / variance workflows
   - standard Frappe stock reconciliation processes

Exit gate:

- a cutover store is never overwritten by a later sheet sync
- operator can disable or re-enable a store without code edits

## Data Rules and Exception Policy

### Quantity Resolution Policy

- Preferred operational quantity = the most explicit current quantity available in the current snapshot.
- Accept future-dated historical columns for analytics only, not for operational fallback.
- Historical fallback must use the most recent dated `END` value on or before the run date.

### Zero / Blank Policy

- Blank current values are not silently treated as zero.
- For this bridge, `blank_zero_policy` is an explicit named rule and only applies when a row has:
  - no numeric `encode`
  - no numeric `total`
  - no valid dated `END` fallback on or before the run date
  - no formula error
  - no usable `WHOLE/LOOSE` conversion signal
- This rule is necessary so a later daily sync does not preserve stale nonzero balances forever when the sheet row carries no stock signal at all.

### Exception Policy

Rows go to exceptions when:

- no Frappe item mapping exists
- quantity is blank and no valid fallback exists
- formula error exists
- whole/loose conversion is ambiguous
- warehouse mapping is missing

Exceptions must be visible in a single operator report before any full-store import run is called complete.

## Verification Strategy

### Import Verification

For sampled stores and then the full batch:

1. Compare payload qty vs resulting `Bin.actual_qty`
2. Call `hrms.api.store.get_orderable_items` and verify `available_stock`
3. Confirm duplicate rerun of the same payload does not create extra `Stock Reconciliation` documents

### Scheduler Verification

1. Force-run the 8AM job manually
2. Re-run immediately with unchanged input
3. Confirm:
   - changed stores import once
   - unchanged stores skip cleanly
   - logs record both outcomes

### Cutover Verification

1. Mark one sample store `frappe_live`
2. Trigger the morning sync
3. Confirm that store is skipped even if the sheet changed

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Blank current-balance fields in many rows | incomplete or misleading opening stock | explicit resolution policy + exception file |
| `#REF!` formula errors in source | bad qty import | quarantine to exception report |
| Ambiguous whole/loose conversions | wrong on-hand qty | require explicit conversion rule or historical fallback |
| Stale docs claiming inventory sync is stubbed | plan confusion and duplicated work | plan anchors on live code + tests |
| Morning schedule timezone drift | job runs at wrong local time | set explicit `00:00 UTC = 08:00 PHT` schedule |
| Post-cutover overwrite from sheet sync | corrupt live ERP stock | per-store cutover switch required before launch |

## Acceptance Criteria

This plan is complete only when:

1. The extracted `3. INVENTORY` current snapshot is transformed into a verified Frappe payload with explicit exception handling.
2. Store opening balances can be imported into Frappe and verified through `Bin.actual_qty` and store ordering stock reads.
3. A daily **8:00 AM PHT** automated shadow sync exists for non-cutover stores.
4. The sync is idempotent and skips unchanged stores.
5. A per-store cutover switch prevents post-cutover sheet overwrites.
6. The whole workbook history remains available in analytics, separate from Frappe's transactional stock ledger.

## First Execution Targets

1. Build the cleanroom mapping + exception package from the existing extraction.
2. Implement the current-snapshot-to-Frappe transformer.
3. Prove import on sample stores, then full batch.
4. Extend the scheduler for the 8AM shadow-sync run.
5. Add the store-level cutover registry before enabling the daily job in production.
