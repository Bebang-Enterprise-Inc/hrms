# S190 Phase 5 Verification — CSV Retirement

**Date:** 2026-04-14
**Canonical data source:** `F:\Downloads\bei_company_register (2).xlsx`

## Result: 100% Coverage (53/53 stores billable via Company-first only)

All store warehouses now resolve to the correct buyer entity Company via `Warehouse.company` — no CSV lookup needed.

## What was done (production data)

### 1. Warehouse re-pointing (37 warehouses)
Pointed each of 49 store warehouses to its correct buyer entity Frappe Company per workbook Sheet 3 (Store-Entity Mapping). 37 re-pointed from parent `Bebang Enterprise Inc.` to specific legal entities.

Examples:
- `SM Tanza - BEI` → `BEBANG MEGA INC.` (was: Bebang Enterprise Inc.)
- `Ayala Evo - BEI` → `BEBANG MEGA INC.`
- `SM Bicutan - BEI` → `BEBANG SM BICUTAN INC.`
- `SJDM - BEI` → `LEGACY77 FOOD CORP.`
- `The Grid - Rockwell - BEI` → `TASTECARTEL CORP.`

### 2. Corrective fixups (7 warehouses)
- `SM Marikina - BEI` → `BEBANG SM MARIKINA INC.` (was mis-matched to Sta Lucia child)
- `Sta. Lucia East Grand Mall - BEI` → `Bebang SM Marikina Inc. - Sta Lucia`
- `Ayala Malls Fairview Terraces - BEI` → `BEBANG FT INC.` (FTE = FT alias)
- `NAIA T3 - BEI` → `HALO-HALO TERMINAL FOOD CORP.`
- `Greenhills Ortigas - BEI` → `BEIFRANCHISE FOOD OPC`
- `SM Sta. Rosa - BEI` → `SWEET HARMONY FOOD CORP.`
- `SM Taytay - BEI` → `DAY ONES FOOD AND DRINK ESTABLISHMENTS CORP.`

### 3. Customer records (7 new + TIN backfill)
Created Customer records for 7 Companies that didn't have matching Customers:
- Bebang SM Marikina Inc. - Sta Lucia, DLS Dessert Craft Inc., LEGACY77 FOOD CORP.
- RED TALDAWA FOODS OPC, SWEET HARMONY FOOD CORP., TAJ FOOD CORP., TASTECARTEL CORP.

All with tax_id from Company.tax_id.

## Code changes

- `hrms/utils/supply_chain_contracts.py`:
  - `load_store_buyer_entity_register()` → raises NotImplementedError
  - `resolve_store_buyer_entity()` → Company-first only, no CSV fallback
- `hrms/fixtures/store_buyer_entity_register/store_buyer_entity_register.csv` → DELETED
- `hrms/tests/test_s37_store_buyer_entity_register_loader.py` → DELETED

## Live Verification Sample

```
SM Tanza - BEI
  → Warehouse.company = BEBANG MEGA INC.
  → Customer = BEBANG MEGA INC.
  → TIN = 010-885-436-00000
  ✅ Billable

SM Megamall - BEI
  → Warehouse.company = Bebang Enterprise Inc. - SM Megamall (S188 child)
  → Customer = Bebang Enterprise Inc. - SM Megamall
  → TIN = 647-243-690-00000
  ✅ Billable

SJDM - BEI
  → Warehouse.company = LEGACY77 FOOD CORP.
  → Customer = LEGACY77 FOOD CORP.
  → TIN = 691-654-007-00000
  ✅ Billable

The Grid - Rockwell - BEI
  → Warehouse.company = TASTECARTEL CORP.
  → Customer = TASTECARTEL CORP.
  → TIN = 672-270-879-00000
  ✅ Billable
```

## Summary

| Metric | Pre-P5 | Post-P5 |
|--------|--------|---------|
| Billable via Company-first only | 4 (8%) | **53 (100%)** |
| CSV fallback needed | 49 (92%) | 0 |
| CSV files on disk | 2 | 0 |
| `resolve_store_buyer_entity` source paths | 2 (Company + CSV) | 1 (Company) |

The S037 CSV register is retired. Company Master is the only source of truth.
