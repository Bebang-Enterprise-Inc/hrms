---
**Last Scanned:** 2026-02-23 | **Previous Scan:** 2026-02-17
**Commit:** 7b998877f | **Health Score:** 100% LIVE
---

# Department Feature Matrix: Warehouse & Logistics

## Summary

- Frontend pages: 20 (expanded from 9 in Feb 17 audit)
- Backend endpoints: 34 LIVE (warehouse.py + dispatch.py), 0 STUB
- DocTypes: BEI Distribution Trip, BEI Trip Stop, BEI Route, BEI Route Stop, BEI Vehicle, BEI Warehouse Department Mapping, BEI External Hub, BEI Hub Item, BEI Pick List, BEI Billing Schedule, BEI Delivery Rate, BEI Store Order, BEI Store Order Item
- Health Score: 100% LIVE

### Key Changes vs Feb 17

| Item | Feb 17 | Feb 23 |
|------|--------|--------|
| Routes management | PLANNED | LIVE — full CRUD |
| Trip creation from route | PLANNED | LIVE |
| Trip Wizard (3-step) | PLANNED | LIVE (partial — Step 3 broken GAP-003) |
| Delivery notifications | PLANNED | LIVE — real GChat "1 stop away" |
| Driver scheduling | NOT BUILT | LIVE — get_available_drivers, assign_driver |
| Billing on delivery | NOT BUILT | LIVE — async _create_delivery_billing |
| Picking workflow | GAP | LIVE — picking.py + BEI Pick List |
| My Delivery (store view) | PLANNED | LIVE |

## Feature Matrix

| Feature | Frontend Page | FE Status | Backend API | BE Status | Notes |
|---------|--------------|-----------|-------------|-----------|-------|
| Warehouse Dashboard | `/warehouse` | LIVE | `get_warehouse_dashboard` | LIVE | |
| Pending Purchase Orders | `/receive` | LIVE | `get_pending_purchase_orders` | LIVE | |
| Create Purchase Receipt | `/receive/[po_name]` | LIVE | `create_purchase_receipt` | LIVE | Partial receipt supported |
| Pending Material Requests | `/approve` | LIVE | `get_pending_material_requests` | LIVE | |
| Approve/Reject MR | `/approve/[mr_name]` | LIVE | `approve_material_request`, `reject_material_request` | LIVE | Row lock prevents double-approval |
| Ready for Dispatch | `/dispatch` | LIVE | `get_ready_for_dispatch` | LIVE | |
| Create Stock Transfer | `/dispatch` | LIVE | `create_stock_transfer` | LIVE | Requires approved MR |
| Picking: Generate Pick List | `/picking` | LIVE | `generate_pick_list` | LIVE | Idempotency guard |
| Picking: Update Item | `/picking` | LIVE | `update_pick_item` | LIVE | |
| Picking: Complete Picking | `/picking` | LIVE | `complete_picking` | LIVE | Validates all items picked |
| Picking: Confirm Loaded | `/picking` | LIVE | `confirm_loaded` | LIVE | One Stock Entry per stop submitted |
| Get Trips | `/dispatch`, `/trips` | LIVE | `get_trips`, `get_trip_detail` | LIVE | |
| Confirm Departure | `/dispatch` | LIVE | `confirm_departure` | LIVE | Sets status=In Transit |
| Confirm Delivery | `/dispatch/[id]` | LIVE | `confirm_delivery` | LIVE | Sends "1 stop away" GChat; async billing |
| Get Routes | `/routes`, `/trips/create` | LIVE | `get_routes`, `get_route_detail` | LIVE | |
| Route CRUD | `/routes` | LIVE | `create_route`, `update_route`, `delete_route`, `duplicate_route`, `reorder_stops` | LIVE | Soft delete (active=0) |
| Create Trip from Route | `/routes`, `/trips/create` | LIVE | `create_trip_from_route` | LIVE | Duplicate trip guard; links approved store orders |
| Trip Creation Wizard | `/trips/create` | LIVE (partial) | `create_trip_from_route` + `get_routes` + `get_vehicles` | LIVE (partial) | **Step 3 broken: preview_trip_stops missing (GAP-003); vehicle dropdown broken (GAP-029)** |
| Get Vehicles | Wizard Step 2 | LIVE | `get_vehicles` | LIVE | **GAP-029: response format mismatch** |
| Available Drivers | `/drivers` | LIVE | `get_available_drivers`, `assign_driver`, `get_driver_schedule` | LIVE | |
| Driver List | Wizard Step 2 | LIVE | `get_driver_list` | LIVE | **GAP-064: not wired in wizard; free-text only** |
| My Delivery (store view) | `/my-delivery` | LIVE | `get_my_delivery` | LIVE | ETA window calc; items preview |
| Delivery Billing (async) | Internal | LIVE | `_create_delivery_billing` | LIVE | Feature-flagged via BEI Settings |

## DocType Relationships

| DocType | Link Fields | Child Tables | Submittable? |
|---------|-------------|-------------|--------------|
| BEI Distribution Trip | route_name→BEI Route, driver→Employee, vehicle→BEI Vehicle | BEI Trip Stop | No |
| BEI Route | source_warehouse→Warehouse, default_vehicle→BEI Vehicle, default_driver→Employee | BEI Route Stop | No |
| BEI Vehicle | — | — | No |
| BEI Pick List | trip→BEI Distribution Trip, warehouse→Warehouse, picked_by→User | Items (item_code, qty_ordered, qty_picked, picked) | No |
| BEI Billing Schedule | store→BEI Store Type, trip_reference→BEI Distribution Trip | — | No |
| BEI Store Order | store→Warehouse, trip→BEI Distribution Trip | BEI Store Order Item | Yes |

## Gaps Found

| ID | Feature | Blocker Type | Severity | Notes |
|----|---------|-------------|----------|-------|
| GAP-003 | preview_trip_stops missing | Bug | Critical | Trip Wizard Step 3 always broken |
| GAP-029 | get_vehicles response format mismatch | Bug | High | Vehicle dropdown always falls back to free-text |
| GAP-064 | Driver selector: free-text only | Integration | Medium | No validation against Employee master |
| GAP-065 | Billing pages: unknown backend | Unclear | Medium | /billing and /billing/3pl-reconciliation may be placeholders |
| GAP-080 | _build_trip_doc does not copy estimated_minutes | Bug | Low | ETA always 20 min/stop default |
| GAP-092 | Delivery billing auto-creation not hooked to Trip submit | Design | High | Billings must be created manually |

## Improvements

| Feature | Current State | Suggested Improvement | Priority |
|---------|--------------|----------------------|----------|
| preview_trip_stops | Missing entirely | Add get_trip_stops_preview(route_name, date) to dispatch.py | HIGH |
| get_vehicles response | Returns dict; wizard expects flat array | Fix wizard to read data.message.vehicles OR change response | MEDIUM |
| Driver selector in wizard | Free-text input | Add combobox calling get_driver_list/get_available_drivers | MEDIUM |
| _build_trip_doc stop data | Does not copy estimated_minutes | Copy from BEI Route Stop to BEI Trip Stop at creation | MEDIUM |
