# Employee Transfer Flow

Status: `ready`
Prefix: `TRF`

This flow validates staged transfer approval (Requester -> Area -> HR -> IT), employee master mutation, and ADMS sync reconciliation.

### TRF-001: Requester creates transfer request with warehouse-only target
- **Type:** happy
- **Role:** test.supervisor@bebang.ph
- **Call:** `POST hrms.api.transfer_requests.create_transfer_request`
- **Payload:**
  ```json
  {
    "employee": "<existing_test_employee_id>",
    "effective_date": "2026-02-27",
    "reason": "Transfer flow E2E coverage",
    "store_warehouse": "BRITTANY OFFICE - BEI"
  }
  ```
- **Assert:**
  - Response returns `success == true` and non-empty transfer request `name`.
  - DB: `BEI Transfer Request.current_stage == "Pending Area Approval"`.
  - DB: `to_branch` is auto-derived from `store_warehouse` (no manual `to_branch` required).

### TRF-002: Area Supervisor approves stage
- **Type:** happy
- **Role:** test.area@bebang.ph
- **Call:** `POST hrms.api.transfer_requests.approve_transfer_stage`
- **Payload:**
  ```json
  {
    "transfer_request_name": "<request_name_from_trf_001>",
    "remarks": "Area approved"
  }
  ```
- **Assert:**
  - Response `success == true`.
  - Stage transition: `Pending Area Approval -> Pending HR Approval`.

### TRF-003: HR approves and employee transfer bridge is created
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Call:** `POST hrms.api.transfer_requests.approve_transfer_stage`
- **Payload:**
  ```json
  {
    "transfer_request_name": "<request_name_from_trf_001>",
    "remarks": "HR approved"
  }
  ```
- **Assert:**
  - Response `success == true`.
  - Stage transition: `Pending HR Approval -> Pending IT Approval` (or `HR Approved - Waiting Effective Date` when effective date is in future).
  - `employee_transfer_ref` is set and references a valid `Employee Transfer` record.

### TRF-004: IT dispatches transfer sync commands
- **Type:** happy
- **Role:** Administrator/System Manager
- **Call:** `POST hrms.api.transfer_requests.dispatch_transfer_sync`
- **Payload:**
  ```json
  {
    "transfer_request_name": "<request_name_from_trf_001>",
    "remarks": "IT dispatch for transfer"
  }
  ```
- **Assert:**
  - Response `success == true`.
  - DB: `BEI Transfer Device Command` rows created for target/remove device actions.
  - Stage moves to `Sync In Progress` or `Ready for Sync` based on effective date gate.

### TRF-005: Reconcile ADMS command status
- **Type:** edge
- **Role:** Administrator/System Manager
- **Call:** `POST hrms.api.transfer_requests.reconcile_transfer_sync_status`
- **Payload:**
  ```json
  {
    "transfer_request_name": "<request_name_from_trf_001>"
  }
  ```
- **Assert:**
  - Response includes reconciliation summary (`updated`, `errors`, command status counts).
  - DB command rows move from `PENDING/SENT` to terminal state (`ACKED` or `FAILED`) as available from ADMS.

### TRF-006: Transfer form options exclude non-BEI/3PL warehouses
- **Type:** regression
- **Role:** test.supervisor@bebang.ph
- **Call:** `GET hrms.api.transfer_requests.get_transfer_form_options`
- **Payload:**
  ```json
  {
    "search_text": "",
    "limit": 200
  }
  ```
- **Assert:**
  - Response `warehouses` list is non-empty for BEI stores.
  - Returned warehouses include derived `branch`.
  - Rows containing `3PL`, `3MD`, `3rd party`, or non-`Bebang Enterprise Inc.` company are excluded.

