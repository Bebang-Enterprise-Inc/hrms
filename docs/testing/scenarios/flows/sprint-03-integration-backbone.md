# Sprint 03 Integration Backbone Flow

Target gaps: `GAP-006`, `GAP-007`, `GAP-008`, `GAP-009`, `GAP-025`, `GAP-046`, `GAP-092`

Evidence target:
- `output/l4/runs/sprint-03-integration-backbone/<run-id>/`

---

### S03-006: AR Aging Sync Writes Idempotently
**Level:** L4  
**Type:** edge + idempotency  
**Call:** `POST hrms.api.erp_sync.sync_ar_aging`

**Steps:**
1. Send payload with one known invoice row and fixed checksum.
2. Replay the same payload/checksum.

**Expected Results:**
- Invoice outstanding fields are updated on first run.
- Replay does not create duplicates or drift values.
- Sync token field remains stable for same payload/checksum.

---

### S03-007: Inventory Sync Creates One Reconciliation Per Warehouse
**Level:** L4  
**Type:** happy + dedupe  
**Call:** `POST hrms.api.erp_sync.sync_inventory`

**Steps:**
1. Send mixed item rows for one warehouse with repeated item codes.
2. Replay with same checksum.

**Expected Results:**
- One submitted `Stock Reconciliation` per warehouse sync ref.
- Duplicate replay maps to existing reconciliation (rows count as updated, no extra doc).

---

### S03-008: COA Sync Upsert + Replay Safety
**Level:** L4  
**Type:** happy + idempotency  
**Call:** `POST hrms.api.erp_sync.sync_coa`

**Steps:**
1. Send one new account row and one existing account row.
2. Replay with same checksum.

**Expected Results:**
- New account created with correct parent/root/report type.
- Existing account updated on first run.
- Replay produces no duplicate account records.

---

### S03-009: AP Opening Sync + Supplier SOA Route
**Level:** L4  
**Type:** happy + route parity  
**Calls:** `POST hrms.api.erp_sync.sync_ap_opening`, `POST hrms.api.erp_sync.sync_supplier_soa`

**Steps:**
1. Send one AP opening row via `sync_ap_opening`.
2. Send same row via `sync_supplier_soa`.

**Expected Results:**
- Purchase Invoice is created/updated once per supplier+invoice+company.
- `sync_supplier_soa` behaves as route alias and does not 404.

---

### S03-025: Bank Directory Sync Upsert + Replay Safety
**Level:** L4  
**Type:** happy + idempotency  
**Call:** `POST hrms.api.erp_sync.sync_bank_accounts`

**Steps:**
1. Send one new account and one update for existing account number.
2. Replay with same checksum.

**Expected Results:**
- Bank account records are created/updated correctly.
- Replay does not duplicate `Bank Account` docs.

---

### S03-046: Critical Sheets Alert Dispatch
**Level:** L4  
**Type:** negative + observability  
**Path:** sheets receiver processor/file processor

**Steps:**
1. Trigger a change-tracker critical alert (`MASS EDIT` / `DELETION`) during sync.
2. Trigger file processing failure in POS queue.

**Expected Results:**
- Real-time GChat alert is sent with severity + escalation metadata (`L1-OPS`, owners, runbook link).
- Notification record is logged in `notifications` table.
- Failures are not silently delayed to daily summary.

---

### S03-092: Pre-Delivery Billing Exception Enforcement
**Level:** L4  
**Type:** policy + approval gate  
**Calls:** `POST hrms.api.dispatch.request_pre_delivery_billing_exception`, `POST hrms.api.dispatch.create_pre_delivery_billing`

**Steps:**
1. Attempt `create_pre_delivery_billing` without approved exception.
2. Create exception request for trip stop (CPO+CFO tier).
3. Approve exception through procurement approval flow.
4. Retry `create_pre_delivery_billing` with approved exception.

**Expected Results:**
- Step 1 is blocked with policy error.
- Step 4 succeeds and writes billing with exception trace fields (`exception_cpo_*`, `exception_cfo_*`).

