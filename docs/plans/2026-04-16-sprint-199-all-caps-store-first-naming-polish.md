---
sprint: S199
display: Sprint 199 — ALL CAPS Store-First Company Naming Polish + Analytics CSV Removal
branch: s199-all-caps-store-first-naming-polish
repo: hrms
status: GO
created: 2026-04-16
depends_on:
  - S196 (Store-First Naming + Data Migration — COMPLETED)
  - S191 (FP completeness guard — DEPLOYED)
completed_date:
backend_pr:
execution_summary:
registry_row: |
  | `S199` | Sprint 199 | `s199-all-caps-store-first-naming-polish` (hrms) | TBD | PLANNED 2026-04-16 |
---

# Sprint 199 — ALL CAPS Store-First Company Naming Polish + Analytics CSV Removal

## TL;DR

S196 established the `<Store> - <Corp>` naming convention but left it half-done: 16 Companies got store-first names in mixed case, 28 stayed as corp-only ALL CAPS names, and the Analytics dashboard still reads a stale CSV fixture instead of `Company.mosaic_location_id`. This sprint finishes the job:

1. **Rename ALL 44 store Companies** to uniform `<STORE NAME> - <CORP NAME>` in ALL CAPS
2. **Fix 7 naming defects** (typos, double spaces, abbreviations, inconsistent Robinsons/Robinson)
3. **Rewire Analytics** from CSV fixture to `Company.mosaic_location_id` (Frappe-native, auto-discovers new stores)
4. **Delete the CSV fixture** that keeps breaking on every rename

CEO directive (2026-04-16): "Let's have everything in ALL CAPS so the invoices have all caps too."

## Design Rationale (For Cold-Start Agents)

**Why ALL CAPS:** Frappe `Company.name` is the docname that prints on Sales Invoices, Purchase Orders, and BIR documents. ALL CAPS matches SEC/BIR registration format and avoids mixed-case inconsistency between `BEBANG SMOA INC.` (BIR-registered) and `SM Megamall - Bebang Enterprise Inc.` (S196 rename). One format, everywhere.

**Why store-first:** CEO directive (2026-04-15): "operators don't know the fucking corp names." The store name is what ops/finance teams recognize. Corp name is secondary context for legal/accounting.

**Why this sprint exists:** S196 renamed 12 S188 children (corp-first → store-first) and 3 new Companies, but the ~30 single-operator corps (`BEBANG SMOA INC.`, `TASTECARTEL CORP.`, etc.) were not renamed because they didn't have the `<Corp> - <Store>` pattern to flip. S196 also used mixed case instead of ALL CAPS. The result: 16 Title Case + 28 ALL CAPS + 0 abbreviations resolved = inconsistent mess.

**Why rewire Analytics:** `_filter_sales_warehouses` reads `sales_dashboard_store_mapping.csv` to find `location_id` for each warehouse. This CSV breaks on every Warehouse/Company rename (S188 broke 9 stores, S196 broke the same 9 differently). `Company.mosaic_location_id` already exists with 45 of 50 orderable Companies populated. Rewiring to Frappe ORM eliminates the CSV dependency entirely. New stores auto-appear when BD sets `mosaic_location_id` on the Company — no code deploy needed.

**Known limitations:**
- `frappe.rename_doc("Company", old, new)` cascades to Link fields but NOT to denormalized `SLE.company` / `GL Entry.company`. However, this sprint is rename-only (no re-points), so SLE/GL rows already have the correct Company from S196. The rename cascades the docname through Link fields.
- `Company.abbr` is preserved across renames (verified in S196 Step I). Must re-verify after this sprint.
- 5 Companies have no `mosaic_location_id` (no Mosaic POS terminal): BB ESTANCIA FOOD CORP., BEIFRANCHISE FOOD OPC, PERPETUAL FOOD CORP., FREEZE DELIGHT INC., Bebang Kitchen Inc. These are excluded from Analytics by design — they're either non-POS stores or commissary.
- 4 entities are not stores and stay as-is: BEBANG FRANCHISE CORP., JV, Managed Franchise, LEGACY77 FOOD CORP.

## Naming Defects Identified (7)

| # | Current | Issue | Corrected |
|---|---------|-------|-----------|
| D1 | `SM  Manila` (Mosaic) / `SM Manila - Bebang Enterprise Inc.` | Double space in Mosaic store name | `SM MANILA` |
| D2 | `Robisons Galleria South` (Mosaic + Warehouse) | Missing 'n' — should be `Robinsons` | `ROBINSONS GALLERIA SOUTH` |
| D3 | `Robinson Imus` / `Robinson General Trias` (Mosaic) | Missing 's' — should be `Robinsons` | `ROBINSONS IMUS` / `ROBINSONS GENERAL TRIAS` |
| D4 | `SM SJDM` (Mosaic) | Abbreviation — CEO wants full name | `SM SAN JOSE DEL MONTE` |
| D5 | `Ayala UPTC` (Mosaic) | Abbreviation — CEO wants full name | `AYALA UP TOWN CENTER` |
| D6 | `The Grid - Rockwell` (Mosaic) | Dash creates 3-segment name when combined with corp | `THE GRID ROCKWELL` (flattened) |
| D7 | `Ayala Evo` (Mosaic) vs `Ayala Evo City` (Company) | Store name mismatch — Company has "City", Mosaic doesn't | Use `AYALA EVO CITY` (longer = more specific) |

**Abbreviations that stay abbreviated (per Sam):** PITX, NAIA T3, EDSA, BGC.

## Complete Rename Map (45 Companies)

All targets are `<STORE NAME> - <CORP NAME>` in ALL CAPS. Sorted by Mosaic location_id.
Corp suffix uses the FULL legal entity name (e.g. `TUNGSTEN CAPITAL HOLDINGS OPC`, not shortened `TUNGSTEN CAPITAL`).

| LID | Current Company Name | Target Company Name |
|-----|---------------------|---------------------|
| 2177 | BEBANG PASEO INC. | MEGAWORLD PASEO CENTER - BEBANG PASEO INC. |
| 2179 | BEBANG PITX INC. | MEGAWIDE PITX - BEBANG PITX INC. |
| 2184 | BEBANG SMEO INC. | SM EAST ORTIGAS - BEBANG SMEO INC. |
| 2216 | BEBANG VENICE GRAND CANAL INC. | MEGAWORLD VENICE GRAND CANAL - BEBANG VENICE GRAND CANAL INC. |
| 2217 | BEBANG BF HOMES INC. | BF HOMES - BEBANG BF HOMES INC. |
| 2218 | BEBANG GRAND CENTRAL INC. | SM GRAND CENTRAL - BEBANG GRAND CENTRAL INC. |
| 2219 | BEBANG SMOA INC. | SM MALL OF ASIA - BEBANG SMOA INC. |
| 2220 | BEBANG FT INC. | AYALA MALLS FAIRVIEW TERRACES - BEBANG FT INC. |
| 2222 | BEBANG FESTIVAL INC. | FESTIVAL MALL ALABANG - BEBANG FESTIVAL INC. |
| 2250 | TASTECARTEL CORP. | THE GRID ROCKWELL - TASTECARTEL CORP. |
| 2281 | DLS Dessert Craft Inc. | EVER COMMONWEALTH - DLS DESSERT CRAFT INC. |
| 2284 | BEBANG NORTH EDSA INC. | SM NORTH EDSA - BEBANG NORTH EDSA INC. |
| 2287 | BEBANG MARKET MARKET INC. | AYALA MARKET MARKET - BEBANG MARKET MARKET INC. |
| 2311 | BEBANG LCT INC. | LUCKY CHINATOWN - BEBANG LCT INC. |
| 2317 | BEBANG SM MARIKINA INC. | SM MARIKINA - BEBANG SM MARIKINA INC. |
| 2319 | BEBANG STARMALL ALABANG INC. | THE TERMINAL - BEBANG STARMALL ALABANG INC. |
| 2338 | SM Megamall - Bebang Enterprise Inc. | SM MEGAMALL - BEBANG ENTERPRISE INC. |
| 2339 | SM Manila - Bebang Enterprise Inc. | SM MANILA - BEBANG ENTERPRISE INC. |
| 2340 | SM Southmall - Bebang Enterprise Inc. | SM SOUTHMALL - BEBANG ENTERPRISE INC. |
| 2341 | BEBANG SMV INC. | SM VALENZUELA - BEBANG SMV INC. |
| 2342 | Robinsons Antipolo - Bebang Enterprise Inc. | ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC. |
| 2408 | Robinsons Imus - Bebang Mega Inc. | ROBINSONS IMUS - BEBANG MEGA INC. |
| 2411 | SM Tanza - Bebang Mega Inc. | SM TANZA - BEBANG MEGA INC. |
| 2412 | BEBANG SM BICUTAN INC. | SM BICUTAN - BEBANG SM BICUTAN INC. |
| 2413 | BEBANG MARILAO INC. | SM MARILAO - BEBANG MARILAO INC. |
| 2425 | BEBANG UP TOWN CENTER INC. | AYALA UP TOWN CENTER - BEBANG UP TOWN CENTER INC. |
| 2426 | Ayala Evo City - Bebang Mega Inc. | AYALA EVO CITY - BEBANG MEGA INC. |
| 2428 | Ayala Vermosa - Bebang Mega Inc. | AYALA VERMOSA - BEBANG MEGA INC. |
| 2430 | Robinsons Gen Trias - Bebang Mega Inc. | ROBINSONS GENERAL TRIAS - BEBANG MEGA INC. |
| 2464 | SM Caloocan - TAJ Food Corp. | SM CALOOCAN - TAJ FOOD CORP. |
| 2478 | BEBANG SMM INC. | SM PULILAN - BEBANG SMM INC. |
| 2481 | SM San Jose Del Monte - JL TRADE OPC | SM SAN JOSE DEL MONTE - JL TRADE OPC |
| 2482 | SM Sangandaan - Tungsten Capital | SM SANGANDAAN - TUNGSTEN CAPITAL HOLDINGS OPC |
| 2515 | Robinsons Galleria South - Tungsten Capital | ROBINSONS GALLERIA SOUTH - TUNGSTEN CAPITAL HOLDINGS OPC |
| 2526 | B CUBED VENTURES CORP. | CTTM TOMAS MORATO - B CUBED VENTURES CORP. |
| 2547 | HFFM SOLENAD FOOD SERVICES INC. | AYALA SOLENAD - HFFM SOLENAD FOOD SERVICES INC. |
| 2548 | DMD HOLDINGS INC. | UP TOWN MALL BGC - DMD HOLDINGS INC. |
| 2556 | TRICERN FOOD CORP. | VISTA MALL TAGUIG - TRICERN FOOD CORP. |
| 2557 | Gateway Mall - Tungsten Capital | ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC |
| 2558 | Sta Lucia - Bebang SM Marikina Inc. | STA. LUCIA EAST GRAND MALL - BEBANG SM MARIKINA INC. |
| 2646 | RED TALDAWA FOODS OPC | SM CLARK - RED TALDAWA FOODS OPC |
| 2766 | DVerde Calamba - TAJ Food Corp. | D'VERDE CALAMBA - TAJ FOOD CORP. |
| 2774 | SWEET HARMONY FOOD CORP. | SM STA. ROSA - SWEET HARMONY FOOD CORP. |
| 2812 | DAY ONES FOOD AND DRINK ESTABLISHMENTS CORP. | SM TAYTAY - DAY ONES FOOD AND DRINK ESTABLISHMENTS CORP. |
| 9001 | HALO-HALO TERMINAL FOOD CORP. | NAIA T3 - HALO-HALO TERMINAL FOOD CORP. |

**Not renamed (non-store / no POS):**
- Bebang Kitchen Inc. (Commissary)
- BEBANG FRANCHISE CORP. (Franchisor)
- BB ESTANCIA FOOD CORP. (no Mosaic ID — needs ops to confirm store name)
- BEIFRANCHISE FOOD OPC (no Mosaic ID — needs ops to confirm store name)
- PERPETUAL FOOD CORP. (no Mosaic ID — needs ops to confirm)
- FREEZE DELIGHT INC. (Temporarily Closed, no Mosaic ID)
- JV, Managed Franchise, LEGACY77 FOOD CORP. (archived/non-store)

## Requirements Regression Checklist

- [ ] Are ALL store Company names in ALL CAPS format? No mixed case.
- [ ] Does every store Company follow `<STORE NAME> - <CORP NAME>` pattern?
- [ ] Is `SM SAN JOSE DEL MONTE` spelled out (not SJDM)?
- [ ] Is `AYALA UP TOWN CENTER` spelled out (not UPTC)?
- [ ] Is `THE GRID ROCKWELL` flattened (no dash between Grid and Rockwell)?
- [ ] Is `ROBINSONS` spelled correctly everywhere (not Robisons or Robinson)?
- [ ] Is `SM MANILA` single-spaced (not `SM  MANILA`)?
- [ ] Does `_filter_sales_warehouses` read `Company.mosaic_location_id` NOT the CSV?
- [ ] Is `sales_dashboard_store_mapping.csv` deleted from the repo?
- [ ] Does `_filter_sales_warehouses` log unmapped warehouses via `frappe.log_error()`?
- [ ] Are Company abbreviations (abbr) preserved after rename (CR-2 invariance)?
- [ ] Does `_normalize_store_name_for_route` handle ALL CAPS warehouse names?
- [ ] **HARD BLOCKER:** Non-store entities (Bebang Kitchen Inc., BEBANG FRANCHISE CORP., JV, Managed Franchise) are NOT renamed.

## Phase Budget Contract

| Phase | Units | Description |
|-------|-------|-------------|
| Phase 1 | 9 | Code changes: rewire Analytics + update normalizer + fix dispatch.py + fix Robisons typo + update all hardcoded maps + update tests |
| Phase 2 | 9 | SSM data migration: 45 Company renames + warehouse renames + cache clear |
| Phase 3 | 4 | Verification + fixture cleanup + data_seed CSVs |
| Phase 4 | 2 | Commit + PR + closeout |
| **Total** | **24** | Well within 80-unit ceiling |

## Phase 1 — Code Changes (9 units)

| Task | Description | MUST_MODIFY |
|------|-------------|-------------|
| P1-T1 | Rewire `hrms/utils/sales_location_mapping.py`: replace CSV reader with `Company.mosaic_location_id` query. Keep same return shape `dict[str, dict]`. | `hrms/utils/sales_location_mapping.py` |
| P1-T2 | Add `frappe.log_error()` to `_filter_sales_warehouses` on unmapped warehouse drop. **HARD BLOCKER:** Do NOT silence drops — log every miss to Sentry. | `hrms/api/sales_dashboard.py` |
| P1-T3 | Update `_normalize_store_name_for_route` regex to handle ALL CAPS warehouse names (e.g., strip `" - BEBANG ENTERPRISE INC."` as well as `" - Bebang Enterprise Inc."`). Make the regex case-insensitive. | `hrms/api/store.py` |
| P1-T4 | Update `_STORE_TO_CHILD` map in `company_master.py` — all 15 values must be ALL CAPS to match new Company names. Also update `_BRIDGE` dict (line ~1009) to use ALL CAPS + fix "Robisons" typo. | `hrms/api/company_master.py` |
| P1-T5 | Update `_STORE_OVERRIDES` and `_COMPANY_TO_SA_STORE` maps in `company_master.py` — all keys/values must use the new ALL CAPS Company names. | `hrms/api/company_master.py` |
| P1-T6 | **(CR-2)** Update `_strip_legacy_company_suffix()` in `dispatch.py:2164-2218` — hardcoded suffixes `" - BEBANG ENTERPRISE INC."` and `" - Bebang Enterprise Inc."` must handle ALL CAPS. Make suffix stripping case-insensitive or add ALL CAPS variants. | `hrms/api/dispatch.py` |
| P1-T7 | **(CR-3/CR-4/CR-5)** Fix "Robisons" typo in ALL hardcoded references: `erp_sync.py:104-106,372` and `store_order_demand_snapshot.py:816` — update to `ROBINSONS GALLERIA SOUTH` (ALL CAPS + typo fix). | `hrms/api/erp_sync.py`, `hrms/utils/store_order_demand_snapshot.py` |
| P1-T8 | **(W-7)** Update test files with ALL CAPS Company names: `test_s196_orderable_companies.py`, `test_s196_get_weekly_schedule.py`, `test_s055_shift_swap_metadata.py`, `test_returns_consistency_s10.py`, `test_s37_warehouse_role_gated_writes.py`. | `hrms/tests/test_s196_*.py`, `hrms/tests/test_s055_*.py`, etc. |
| P1-T9 | **(W-2)** Update E2E test constants in `bei-tasks/tests/e2e/specs/s190-store-company-integration.spec.ts` — SM_TANZA, SM_MEGAMALL, GRID_ROCKWELL, AYALA_EVO Company names to ALL CAPS. | `bei-tasks/tests/e2e/specs/s190-store-company-integration.spec.ts` |

## Phase 2 — SSM Data Migration (9 units)

| Task | Description |
|------|-------------|
| P2-T1 | Write `scripts/s199_company_rename_allcaps.py` with 45 `frappe.rename_doc("Company", old, new)` calls. Each in `frappe.db.savepoint()`. CONFIRM=yes gate + --dry-run. |
| P2-T2 | Dry-run via SSM — verify all 44 renames plan correctly, no collisions. |
| P2-T3 | Live run via SSM — execute all 44 renames. |
| P2-T4 | Post-rename: rename corresponding leaf warehouses from `<old suffix> - <old corp>` to match new Company names. Use `frappe.rename_doc("Warehouse", old, new, force=True)`. |
| P2-T5 | Abbr invariance check (S196 CR-2 pattern) — verify no abbr changed or collided. |
| P2-T6 | Verify `_normalize_store_name_for_route` still resolves all warehouses to correct routes (test against `_CENTRAL_WAREHOUSE_ROUTE_MAP`). |
| P2-T7 | **(W-1)** Clear LRU cache post-rename: `frappe.cache.clear_value("sales_location_mapping")`. The `@lru_cache(maxsize=1)` on `load_sales_location_mapping()` and `load_sales_location_mapping_by_id()` caches stale Company names until process restart. |

**HARD BLOCKER (P2-T1):** The warehouse `Robisons Galleria South - Tungsten Capital` has a typo in the current docname (missing 'n'). The rename must fix this: `ROBINSONS GALLERIA SOUTH - TUNGSTEN CAPITAL`. This is a warehouse rename, not just a Company rename.

**HARD BLOCKER (P2-T4):** Warehouse renames cascade to `tabStock Ledger Entry.warehouse` and `tabBin.warehouse` via Link fields. BUT `tabGL Entry` references warehouse as Data field in some contexts. After rename, verify GL Entry warehouse references are updated via `frappe.rename_doc` cascade.

## Phase 3 — Verification + Cleanup (4 units)

| Task | Description |
|------|-------------|
| P3-T1 | Delete `hrms/fixtures/sales_dashboard_store_mapping.csv` from repo. |
| P3-T2 | Update `hrms/fixtures/store_inventory_shadow_sync/store_inventory_shadow_sync_registry.csv` — `warehouse_docname` column must match new ALL CAPS warehouse names. |
| P3-T3 | **(W-3)** Update data_seed CSVs if present: `hrms/data_seed/bank_accounts_*.csv`, `hrms/data_seed/company_register_*.csv` — Company names must match new ALL CAPS names. |
| P3-T4 | Run full verification: orderable Companies count (expect 50), orderable warehouses count (expect 50), Analytics store count via `_resolve_allowed_store_scope` (expect ≥45), zero mixed-case Company names among stores. |

## Phase 4 — Tests + Closeout (2 units)

| Task | Description |
|------|-------------|
| P4-T1 | Update `hrms/tests/test_s196_orderable_companies.py` — any hardcoded Company names must use ALL CAPS. Update `hrms/tests/test_s196_get_weekly_schedule.py` similarly. |
| P4-T2 | Commit, push, create PR to production. Update plan YAML + SPRINT_REGISTRY.md. |

## Autonomous Execution Contract

- **completion_condition:** All 45 Companies renamed to ALL CAPS store-first pattern. Analytics reads `Company.mosaic_location_id` (not CSV). CSV deleted. Abbr invariance verified. dispatch.py / erp_sync.py / snapshot.py hardcoded refs updated. E2E test constants updated. PR created. Plan YAML + SPRINT_REGISTRY.md updated.
- **stop_only_for:** Missing credentials/access. Destructive action requiring Sam approval. Business-policy decision on the 5 unknown stores (BB ESTANCIA, BEIFRANCHISE, PERPETUAL, FREEZE DELIGHT — skip them, don't stop).
- **continue_without_pause_through:** All phases. Do not stop for progress reports.
- **signoff_authority:** single-owner (Sam)

## Zero-Skip Enforcement

Every task MUST be implemented. If a task cannot be completed, STOP and ask the user. No silent skips, no partial implementations marked as done, no "deferred to next sprint."

## Rollback Contract

All 44 renames are reversible via inverse `frappe.rename_doc(new, old)`. The executing agent must write `scripts/s199_rollback.py` with the inverse map before executing the live run.

## Agent Boot Sequence

1. Read this plan fully.
2. `git fetch origin production && git checkout -b s199-all-caps-store-first-naming-polish origin/production`
3. Read `hrms/utils/sales_location_mapping.py` (the file being rewired).
4. Read `hrms/api/sales_dashboard.py:500-520` (the `_filter_sales_warehouses` function).
5. Read `hrms/api/store.py:1503-1534` (the `_normalize_store_name_for_route` function).
6. Read `hrms/api/company_master.py` — find `_STORE_TO_CHILD`, `_STORE_OVERRIDES`, `_COMPANY_TO_SA_STORE` maps.
7. Read `hrms/api/dispatch.py:2164-2218` (`_strip_legacy_company_suffix` — CR-2).
8. Read `hrms/api/erp_sync.py:104-106,372` (Robisons typo — CR-4).
9. Start Phase 1.

## Audit v1 Amendments — 2026-04-16

3-agent audit (hardcoded-names + analytics-connections + rename-map-completeness). 5 CRITICAL + 7 WARNING. All applied to authoritative phase tables above.

### CRITICAL (5) — all resolved

| # | Finding | Resolution |
|---|---------|------------|
| CR-1 | DAY ONES FOOD AND DRINK ESTABLISHMENTS CORP. (SM Taytay, LID 2812) missing from rename map | Added as entry #45. Map now 45 entries. |
| CR-2 | `_strip_legacy_company_suffix()` in dispatch.py:2164 hardcodes Company suffixes — breaks after ALL CAPS | New task P1-T6: make suffix stripping case-insensitive |
| CR-3 | `_BRIDGE` dict in company_master.py:1009 has "Robisons" typo mapping | Folded into P1-T4 |
| CR-4 | erp_sync.py:104-106,372 has "Robisons" typo hardcoded | New task P1-T7 |
| CR-5 | store_order_demand_snapshot.py:816 has "Robisons" typo | Folded into P1-T7 |

### WARNING (7) — all resolved

| # | Finding | Resolution |
|---|---------|------------|
| W-1 | LRU cache clear needed post-rename | New task P2-T7 |
| W-2 | E2E test constants in bei-tasks hardcode Company names | New task P1-T9 |
| W-3 | data_seed CSVs have Company names | New task P3-T3 |
| W-4 | CTTM abbreviation | Sam decision: keep as CTTM TOMAS MORATO (building brand name) |
| W-5 | TUNGSTEN CAPITAL vs full legal name | Sam decision: use full legal name TUNGSTEN CAPITAL HOLDINGS OPC. 3 entries updated. |
| W-6 | SM San Pablo (LID 2912) no Company entity | Noted as Company creation backlog item, not S199 scope |
| W-7 | Additional test files need Company name updates | Folded into P1-T8 |

### SAFE systems (confirmed no break from rename)

- **Analytics pipeline:** Uses Company.mosaic_location_id + Warehouse.company Link field — Frappe cascade covers it
- **Delivery schedule:** Filters by entity_category/operational_status, not Company name strings
- **Ordering:** _CENTRAL_WAREHOUSE_ROUTE_MAP uses store display names with `.upper()` normalization
- **Billing:** All SI fields are Link type — cascade covers it
- **_normalize_store_name_for_route():** Already uses `.upper()` on input — handles ALL CAPS natively
