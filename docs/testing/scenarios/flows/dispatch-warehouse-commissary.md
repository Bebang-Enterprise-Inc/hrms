# Dispatch Warehouse Commissary Flow

Status: `ready`
Prefix: `DWC`

This flow closes the cross-domain handoff path between warehouse dispatch, commissary fulfillment, and store receiving.
It complements module scenarios in `modules/scm-logistics.md` and `modules/store-ops-inventory-sprint.md`.

### DWC-001: Dispatch queue is visible before trip confirmation
- **Type:** happy
- **Role:** test.warehouse@bebang.ph
- **Call:** `GET hrms.api.warehouse.get_ready_for_dispatch`
- **Assert:**
  - Response succeeds (`HTTP 2xx`).
  - Payload includes dispatch candidates list (empty list is allowed but must not error).
  - No server exception in response payload.

### DWC-002: Warehouse confirms departure for an existing trip
- **Type:** happy
- **Role:** test.warehouse@bebang.ph
- **Call:** `POST hrms.api.dispatch.confirm_departure`
- **Payload:**
  ```json
  {
    "trip_id": "<existing_ready_trip_id>",
    "driver": "TEST-DRIVER-001",
    "vehicle_plate": "ABC-1234",
    "departure_time": "2026-02-26 06:00:00"
  }
  ```
- **Assert:**
  - Response succeeds and trip moves to in-transit status.
  - Dispatch trip has non-null departure timestamp.
  - Downstream stops remain linked to the same trip.

### DWC-003: Commissary fulfillment queue is queryable during active dispatch window
- **Type:** happy
- **Role:** test.commissary@bebang.ph
- **Call:** `GET hrms.api.commissary.get_fulfillment_orders`
- **Assert:**
  - Response succeeds (`HTTP 2xx`).
  - Payload is list-like and includes order status fields.
  - API returns without permission or serialization errors.

### DWC-004: Store receiving posts receiving document for dispatched order
- **Type:** happy
- **Role:** test.crew1@bebang.ph
- **Call:** `POST hrms.api.store.submit_receiving_report`
- **Payload:**
  ```json
  {
    "store": "TEST-STORE-BGC - BEI",
    "delivery_reference": "<existing_dispatch_or_dr_reference>",
    "notes": "Receiving completed for dispatched order",
    "items": []
  }
  ```
- **Assert:**
  - Response succeeds and returns receiving report identifier.
  - Receiving record exists and is linked to target store and reference.
  - Workflow status is not left in null/invalid state.

### DWC-005: Receiving quality inspection submission completes after receiving
- **Type:** happy
- **Role:** test.crew1@bebang.ph
- **Call:** `POST hrms.api.store.submit_fqi_report`
- **Payload:**
  ```json
  {
    "store": "TEST-STORE-BGC - BEI",
    "delivery_reference": "<same_reference_as_dwc_004>",
    "notes": "FQI completed after receiving",
    "checks": []
  }
  ```
- **Assert:**
  - Response succeeds and returns FQI report identifier.
  - FQI record links to store and delivery reference.
  - No blocking exception on empty/non-critical optional arrays.
