---
**Last Scanned:** 2026-02-23 | **Previous Scan:** 2026-02-17
**Commit:** 7b998877f | **Health Score:** 100% LIVE (all stubs from Feb 17 resolved)
---

# Department Feature Matrix: Commissary

## Summary

- Frontend pages: 11 (`/commissary`, `/production`, `/inventory`, `/fulfillment`, `/transfer`, `/raw-materials`, `/work-orders`, `/quality`, `/wastage`, `/wastage-trends`, `/expiring`)
- Backend endpoints: 48 total, 48 LIVE, 0 STUB
- DocTypes: BEI FQI Report, BEI QC Form, BEI QC Reading, BEI Production, BEI Pick List, BOM (standard), Work Order (standard), Stock Entry (standard), Material Request (standard), Quality Inspection (standard), BEI External Hub, BEI Hub Item
- Health Score: 100% LIVE

### Key Changes vs Feb 17

| Item | Feb 17 | Feb 23 |
|------|--------|--------|
| commissary_quality.py | STUB (placeholder) | LIVE — 15 real endpoints |
| commissary_bom.py | ON HOLD | LIVE — 4 BOM CRUD endpoints |
| commissary_requisition.py | ON HOLD | LIVE — 10 endpoints + Work Order integration |
| picking.py | GAP (not built) | LIVE — 5 endpoints, BEI Pick List |
| wastage-trends page | NOT BUILT | LIVE — 4 group-by dimensions |
| G-046 inter-company invoices | PLANNED | LIVE — async BKI→BEI SI+PI |

## Feature Matrix

| Feature | Frontend Page | FE Status | Backend API | BE Status | Notes |
|---------|--------------|-----------|-------------|-----------|-------|
| KPI Dashboard | `/commissary` | LIVE | `get_commissary_dashboard` | LIVE | Shift indicator, productivity gauge, DI summary |
| Production Items List | `/production` | LIVE | `get_production_items` | LIVE | |
| Submit Production Output | `/production` | LIVE | `submit_production_output` | LIVE | Falls back to Material Receipt if no BOM |
| BOM Create/Update/Detail | Internal (work-orders) | LIVE | `create_bom`, `update_bom`, `get_bom_detail` | LIVE | **GAP-066: no dedicated /commissary/bom page** |
| Production Feasibility | `/work-orders` | LIVE | `check_production_feasibility` | LIVE | Returns shortfall + max producible qty |
| Work Order CRUD | `/work-orders` | LIVE | `create_work_order`, `start_work_order`, `complete_work_order` | LIVE | |
| Inventory Levels | `/inventory` | LIVE | `get_inventory_levels` | LIVE | Per-product thresholds (PRODUCT_THRESHOLDS dict) |
| Days Inventory (DI) | `/commissary` (widget) | LIVE | `get_days_inventory` | LIVE | 7-day rolling avg; 6 status levels |
| Weekly Summary (MANCOM) | Internal | LIVE | `get_weekly_summary` | LIVE | WoW comparison |
| Fulfill Store Order | `/fulfillment` | LIVE | `fulfill_store_order` | LIVE | Triggers G-046 async on SE submit |
| G-046 Inter-Company Invoice | Internal (async) | LIVE | `_create_intercompany_invoices_async` | LIVE | BKI→BEI SI+PI; 2.75% JV markup + 8% franchise markup. **GAP-046: failures silently logged** |
| Create RM Requisition | `/raw-materials` | LIVE | `create_rm_requisition` | LIVE | Saved as Draft for SCM approval |
| Approve Requisition | Internal (SCM) | LIVE | `approve_requisition` | LIVE | **GAP-045: no FE for SCM manager** |
| FQI Summary | `/quality` | LIVE | `get_fqi_summary` | LIVE | |
| Create Quality Inspection | `/quality` | LIVE | `create_quality_inspection` | LIVE | Auto-scrap on rejection |
| Log Wastage | `/wastage` | LIVE | `log_wastage` | LIVE | 6 reason codes; calculates PHP value |
| Wastage Trends | `/wastage-trends` | LIVE | `get_wastage_trends` | LIVE | NEW: 4 group-by dims (reason/item/shift/daily) |
| QC Form Submit | `/quality` (QC tab) | LIVE | `submit_qc_form`, `get_qc_forms`, `get_qc_form_detail` | LIVE | **GAP-044: QC Form tab not wired in frontend** |
| FEFO Picking List | `/expiring` | LIVE | `get_fefo_picking_list` | LIVE | |
| Hub Transfer | `/transfer` | LIVE | `create_hub_transfer` | LIVE | Idempotency check; 4 hubs |
| Picking (shared with Warehouse) | `/warehouse/picking` | LIVE | `generate_pick_list`, `update_pick_item`, `complete_picking`, `confirm_loaded` | LIVE | |

## DocType Relationships

| DocType | Link Fields | Child Tables | Submittable? |
|---------|-------------|-------------|--------------|
| BEI FQI Report | store→Warehouse, item_code→Item | — | No |
| BEI QC Form | checked_by→User, verified_by→User | BEI QC Reading | No |
| BEI Pick List | trip→BEI Distribution Trip, warehouse→Warehouse | Items | No |
| BOM (standard) | item→Item, company→Company | BOM Item | Yes |
| Work Order (standard) | production_item→Item, bom_no→BOM | — | Yes |
| Stock Entry (standard) | from_warehouse→Warehouse, to_warehouse→Warehouse | Stock Entry Detail | Yes |
| Material Request (standard) | company→Company, set_warehouse→Warehouse | Material Request Item | Yes |

## Gaps Found

| ID | Feature | Blocker Type | Severity | Notes |
|----|---------|-------------|----------|-------|
| GAP-044 | QC Form tab not wired in quality frontend | Frontend | Medium | Forms submitted only via API |
| GAP-045 | Requisition approval UI for SCM manager | Frontend | Medium | SCM manager cannot approve from app |
| GAP-046 | G-046 failures silently logged | Bug | High | Inter-company invoices can go uncreated silently |
| GAP-066 | BOM management: no dedicated UI | Frontend | Medium | Commissary supervisor cannot browse all BOMs |
| GAP-067 | get_vehicles vehicle dropdown always text input | Bug | Medium | Same format mismatch as GAP-029 |

## Improvements

| Feature | Current State | Suggested Improvement | Priority |
|---------|--------------|----------------------|----------|
| PRODUCT_THRESHOLDS dict | Hardcoded FG item code prefixes in commissary.py | Move to BEI Settings or custom Item fields | HIGH |
| Work Order safety stock | target_stock=100 hardcoded | Use per-product DI target | HIGH |
| G-046 failure notification | log_error only | Add GChat notification to commissary space on failure | MEDIUM |
| QC Form UI | Backend built, no frontend | Add QC Forms tab to /quality page | MEDIUM |
| Requisition approval UI | SCM manager has no UI | Add /warehouse/approve-requisition page | MEDIUM |
