# Sprint S138 — Warehouse Routing & Data Reset

```yaml
sprint_id: S138
display: Sprint 138
slug: warehouse-routing-data-integrity
branch: s138-warehouse-routing-data-integrity
status: PLANNED
planned_date: 2026-03-27
completed_date: null
depends_on: [S136, S134, S135]
total_units: 30
backend_pr: null
frontend_pr: null
l3_result: null
execution_summary: null
```

**Registry Lock Evidence:**
```
| S138 | Sprint 138 | s138-warehouse-routing-data-integrity | — | PLANNED — Warehouse routing data integrity | docs/plans/2026-03-27-sprint-138-warehouse-routing-data-integrity.md |
```

**Goal:** Full data reset of test/demo transactional data, rename 47 warehouses from wrong `- Bebang Enterprise Inc.` suffix to `- BEI`, clean and reseed BEI Route mappings, fix low stock API to query real 3PL warehouses. Leave the system clean for live go-live data loading.

**Depends on:** S136 (route map merged via hrms#381), S134 (PO ship_to default), S135 (low stock API)

**Impact:**
- All test procurement, inventory, and store ordering data deleted — clean slate
- 47 warehouses renamed to correct `- BEI` suffix — no more agent confusion
- BEI Route seeded with proper store-to-3PL mappings
- Low stock API queries real 3PL warehouses where stock actually lives
- System ready for live data loading

**CRITICAL PREREQUISITE:** Full Frappe backup created and stored in Dropbox BEFORE any destructive operations.

---

## Autonomous Execution Contract

```yaml
completion_condition: |
  - Full backup created and verified in Dropbox
  - All test transactional data deleted (POs, PRs, GRs, invoices, stock entries, etc.)
  - 47 warehouses renamed from "- Bebang Enterprise Inc." to "- BEI"
  - TEST-* warehouses deleted
  - BEI Route cleaned and reseeded (47 stores x 3 cargo types)
  - Low stock API uses real 3PL warehouses
  - Plan YAML status updated to COMPLETED
  - SPRINT_REGISTRY.md updated with final status
stop_only_for:
  - missing_access: credentials/session not available
  - destructive_approval: deleting production data (backup must be confirmed first)
  - business_policy: unclear which data to keep vs delete
  - direct_overwrite: conflicting active work on same files
signoff_authority: single-owner (Sam)
deploy_handoff: PR creation -> share PR# -> STOP (user merges)
```

---

## Ownership Matrix

| File/Surface | Owner | Protected? |
|---|---|---|
| `hrms/api/procurement.py` (get_low_stock_items + ship_to) | S138 | Shared -- modify only low stock function and ship_to default |
| `scripts/s138_data_reset.py` (new) | S138 | No -- new cleanup script |
| Frappe data (bench console) | S138 | Destructive -- backup required first |

**Protected surfaces (DO NOT TOUCH):**
- Store ordering (S136 -- `hrms/api/store.py`, `hrms/utils/supply_chain_contracts.py`)
- CEO approval flow (S132)
- Quick Receive / Auto-Invoice dialog (S134)
- Stock Alerts widget / dashboard (S135 frontend)
- Employee data (666 employees -- HR data, DO NOT DELETE)
- Real Items (472 non-test items -- keep all)
- Real Suppliers (144 non-test BEI suppliers -- keep all)
- BEI Settings, Vehicles, Store Types (config data)

---

## Phase 0: Backup (2 units) -- MUST COMPLETE BEFORE ANY DELETION

| Task | Type | Description | Units |
|------|------|-------------|-------|
| 0.1 | BACKUP | **Create full Frappe backup.** Run `bench backup --with-files` via SSM on production. Download the backup tarball. Verify it contains: database SQL dump, uploaded files, site config. | 1 |
| 0.2 | BACKUP | **Upload to Dropbox.** Create folder `Full ERP Backup - 2026-03-27` in Dropbox. Upload the backup tarball. Create `README.md` inside explaining: "Pre-S138 data reset backup. Contains all test/demo transactional data that will be deleted. Created before warehouse rename + data cleanup sprint." Confirm upload and share the Dropbox path. | 1 |

**HARD BLOCKER:** Phase A CANNOT start until Phase 0 backup is confirmed uploaded and verified.

## Phase A: Delete Test/Demo Transactional Data (10 units)

All operations via `bench console` through SSM. Each delete batch must be previewed (count + sample) before executing.

| Task | Type | Description | Units |
|------|------|-------------|-------|
| A1 | DATA | **Delete ALL BEI procurement transactions.** In order (child records first): BEI Invoice Items, BEI Invoices (59), BEI Payment Requests (44), BEI GR Items, BEI Goods Receipts (1,051), BEI PO Items, BEI Purchase Orders (802), BEI PR Items, BEI Purchase Requisitions (544). | 2 |
| A2 | DATA | **Delete ALL inventory transactions.** Cancel all submitted Stock Entries first, then delete: Stock Entries (346), which cascades Stock Ledger Entries (23,413). Rebuild Bins after. | 2 |
| A3 | DATA | **Delete ALL store operations transactions.** BEI Store Order Items + BEI Store Orders (220), BEI Distribution Trips (207), BEI Warehouse Receiving Items + BEI Warehouse Receiving (15), BEI Store Receiving Items + BEI Store Receiving (10), BEI Cycle Count Items + BEI Cycle Counts (62). | 2 |
| A4 | DATA | **Delete Frappe native procurement transactions.** Cancel submitted docs first. Purchase Invoices (1,849), Purchase Receipts (112), Purchase Orders (155), Material Requests (115), Sales Invoices (136), Journal Entries (22), Payment Entries (7). GL Entries (3,225) cascade from above. | 2 |
| A5 | DATA | **Delete test Items and Suppliers.** Delete 27 test Items (E2E*, TEST*, CYCLE* prefixes) and 10 test Item Groups. Delete 35 test BEI Suppliers (L3-*, Test*) and 15 test native Suppliers. Keep all real items (472) and real suppliers (144 BEI + 339 native). | 1 |
| A6 | VERIFY | **Post-delete verification.** Confirm: 0 BEI POs, 0 BEI GRs, 0 Stock Entries, 0 SLEs, 0 GL Entries. Confirm real Items count ~472, real BEI Suppliers ~144. Confirm Employees untouched (666). Write verification to `tmp/s138_post_delete_verification.json`. | 1 |

## Phase B: Warehouse Rename + Route Reset (10 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| B1 | DATA | **Rename 47 warehouses.** Use `frappe.rename_doc("Warehouse", old_name, new_name)` which cascades to all linked records (Bins, SLEs, Stock Entries, etc.). Rename `{Store} - Bebang Enterprise Inc.` to `{Store} - BEI` for all 47 warehouses. **HARD BLOCKER:** After Phase A deletes, there should be minimal linked records to cascade. Verify Bin count is near-zero before renaming. Run one rename first as a test, verify no errors, then batch the rest. | 4 |
| B2 | DATA | **Delete TEST-* warehouses.** Delete: TEST-COMMISSARY - BEI, TEST-STORE-BGC - BEI, TEST-STORE-MAKATI - BEI. These have test Bin records that should be gone after Phase A. | 0.5 |
| B3 | DATA | **Delete ALL BEI Route records (219).** Clean slate -- no need to preserve any (all are test/probe data). | 0.5 |
| B4 | DATA | **Seed proper BEI Route records.** Create 141 BEI Route records (47 stores x 3 cargo types: FC, DRY, FM) using the S136 hardcoded route map. Source warehouses NOW use the renamed `- BEI` suffix: `3MD Logistics - BEI` (~40 stores), `Pinnacle Cold Storage Solutions - BEI` (~30 stores), `Jentec Storage Inc. - BEI` (Shaw only). Each route gets a BEI Route Stop child with the store warehouse. | 3 |
| B5 | VERIFY | **Post-rename verification.** Confirm: 0 warehouses with `- Bebang Enterprise Inc.` suffix. 47 warehouses with `- BEI` suffix (was 5, now 52). BEI Route count = 141 active. Each store has FC+DRY+FM. All source_warehouse values are valid Warehouse names. | 2 |

## Phase C: Fix APIs + Deploy + Closeout (8 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| C1 | EXTEND | **Fix `get_low_stock_items()`.** Remove "Stores - BEI" hardcode. New default: aggregate across all distinct `source_warehouse` from active BEI Routes. Add optional `store` param that resolves via route map. Keep `warehouse` param for direct queries. Sentry instrumentation. | 3 |
| C2 | EXTEND | **Fix PO ship_to default.** Change from "Stores - BEI" to route-map-based: if PO has store context, resolve via BEI Route. Fallback to first active 3PL warehouse (3MD). "Stores - BEI" is no longer the default since it's been renamed and is now just one of 52 `- BEI` warehouses. | 1 |
| C3 | EXTEND | **Update frontend low-stock route.** Add `store` query parameter support to `/dashboard/low-stock` API route. | 0.5 |
| C4 | DEPLOY | Create PR for hrms targeting production. Share PR number. Update SPRINT_REGISTRY.md. | 0.5 |
| C5 | L3 | Generate L3 handoff prompt. | 0.5 |
| C6 | CLOSEOUT | Update plan YAML status. Update SPRINT_REGISTRY.md. `git add -f` evidence. | 2.5 |

---

## L3 Workflow Scenarios

| # | Type | User | Action | Expected Outcome | Failure Means |
|---|------|------|--------|-------------------|---------------|
| L3-1 | happy | sam@bebang.ph | Count warehouses with `- Bebang Enterprise Inc.` suffix | 0 warehouses. All renamed to `- BEI`. | Rename incomplete |
| L3-2 | happy | sam@bebang.ph | Count active BEI Route records | 141 active. 47 stores x 3 cargo types. Source warehouses = 3MD/Pinnacle/Jentec (now with `- BEI` suffix). | Route seeding wrong |
| L3-3 | happy | sam@bebang.ph | GET low-stock with no params | Returns items from 3PL warehouses. `warehouse` field shows `- BEI` suffix names. Count > 0 with real stock data. | API still hardcoded |
| L3-4 | happy | sam@bebang.ph | Count BEI POs, GRs, Stock Entries | All 0. Clean slate. | Delete incomplete |
| L3-5 | happy | sam@bebang.ph | Count Employees | 666 (unchanged). | HR data accidentally deleted |
| L3-6 | happy | sam@bebang.ph | Count real Items (not E2E/TEST/CYCLE) | ~472 items. Test items gone. | Wrong items deleted |
| L3-7 | adversarial | sam@bebang.ph | GET low-stock with `warehouse=Stores - BEI` | Returns items from Stores - BEI only (may be empty). No crash. Backward compatible. | Signature broken |

---

## Design Rationale (For Cold-Start Agents)

1. **Why full data reset.** All current transactional data (802 POs, 1051 GRs, 346 Stock Entries, 23K SLEs, 3K GL Entries) is test/demo data created during sprint development. The system will be reset before go-live. Deleting now prevents future agents from being confused by test data and wrong warehouse names. Sam confirmed: "all the stores and POS on the system and inventory for now is for testing."

2. **Why rename warehouses.** 47 warehouses use the long suffix `- Bebang Enterprise Inc.` while the correct ERPNext convention is `- BEI` (matching the company abbreviation). Two naming conventions cause agent confusion (S136 spent hours debugging because warehouse names didn't match). Renaming now, when transactional data is deleted, is the safest time -- minimal cascading records.

3. **Why delete ALL BEI Routes.** All 219 records are test data from S026/S027/S037/Codex sprints. Not a single production route exists. Clean slate + proper seeding is cleaner than selective cleanup.

4. **Why Phase 0 backup is mandatory.** Even though this is test data, a full backup protects against accidental deletion of real config (Items, Suppliers, Employees, Settings). The backup goes to Dropbox for off-system durability.

5. **Store-to-3PL mapping source.** Same Central Warehouse Excel data already hardcoded in S136's `store.py:1251-1322`. 3MD serves ~40 stores, Pinnacle ~30, Jentec 1. After warehouse rename, these become `3MD Logistics - BEI`, `Pinnacle Cold Storage Solutions - BEI`, `Jentec Storage Inc. - BEI`.

---

## Requirements Regression Checklist

- [ ] Is a full Frappe backup created and uploaded to Dropbox BEFORE any deletion?
- [ ] Are ALL test POs, GRs, Invoices, Stock Entries, PRs deleted (zero remaining)?
- [ ] Are ALL Frappe native procurement transactions deleted?
- [ ] Are GL Entries and SLEs at zero after cascading deletes?
- [ ] Are Employees (666) untouched after the reset?
- [ ] Are real Items (~472) preserved and only test items (27) deleted?
- [ ] Are real Suppliers (~144 BEI + ~339 native) preserved?
- [ ] Are 47 warehouses renamed from `- Bebang Enterprise Inc.` to `- BEI`?
- [ ] Are TEST-* warehouses deleted?
- [ ] Are ALL BEI Route records deleted and 141 new ones seeded?
- [ ] Does `get_low_stock_items()` aggregate across 3PL warehouses by default?
- [ ] Does PO ship_to use route map when store context exists?
- [ ] Does every modified `@frappe.whitelist()` call `set_backend_observability_context()`?
- [ ] Does the plan NOT touch `hrms/api/store.py` or `hrms/utils/supply_chain_contracts.py`?

---

## Evidence Sources

| Source | What It Proves |
|--------|----------------|
| `tmp/s138_full_data_audit.md` | Full data audit with counts (2026-03-27) |
| `tmp/warehouse-routing-investigation.md` | Warehouse architecture investigation |
| `hrms/api/store.py:1251-1322` | Hardcoded route map (source for BEI Route seeding) |
| `docs/erp/WAREHOUSE_TREE_2025-12-31.csv` | Canonical warehouse structure |
| Dropbox: `Full ERP Backup - 2026-03-27/` | Pre-reset backup |

---

## Agent Boot Sequence
1. Read this plan fully.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s138-warehouse-routing-data-integrity origin/production`.
3. Read `tmp/s138_full_data_audit.md` for exact record counts.
4. Read `tmp/warehouse-routing-investigation.md` for warehouse architecture.
5. **PHASE 0 FIRST:** Create backup and upload to Dropbox before ANY deletion.
6. Confirm S136 (hrms#381) is merged before starting.

## Execution Authority
This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.
**EXCEPTION:** Phase 0 backup must be confirmed before Phase A begins.

---

## Revision History

- **v1 (2026-03-27):** Initial plan. 18 units, routing fixes only.
- **v2 (2026-03-27):** Expanded to full data reset. 30 units. Added: delete all test transactional data, rename 47 warehouses, delete test items/suppliers. Sam confirmed all current data is test data that will be reset before go-live. Added mandatory Phase 0 backup to Dropbox.
