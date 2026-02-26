# Test Scenarios Registry

**Purpose:** Pre-written test cases with EXACT data and EXACT assertions. Agents EXECUTE these — they do NOT invent their own.

**Why this exists:** Agents given "test module X" invent happy-path tests with toy data (1x1 pixel PNGs, single status transitions). Real users hit bugs in 20 minutes that agents miss over days.

**Rule:** Every scenario specifies the exact payload, the exact assertion, and the expected result. The agent's job is to run the script, not to be creative.

---

## How Scenarios Work

Each scenario has:
- **ID** — permanent, never reused (e.g., `MAINT-003`)
- **Type** — `happy`, `edge`, `regression`, `rbac`, `adversarial`
- **Steps** — exact API calls with exact payloads
- **Assert** — exact field checks on the response/DB record
- **Origin** — where the test came from (bug report, real user, design spec)

### Data Requirements

| Data Type | WRONG (what agents do) | RIGHT (what we require) |
|-----------|----------------------|------------------------|
| Photo | 1x1 pixel, 114 bytes | 200x200 PNG, 100KB+ |
| Photo format | plain base64 string | `[{"photo": "data:image/png;base64,...", "caption": "test"}]` |
| Text fields | "test" | 50+ chars with special chars: `Broken light (café area) — needs 220V fixture & bulb` |
| Status transitions | Only happy path (Open→Completed) | Every valid transition + invalid ones |
| Multi-role | Single role tests | Full handoff: crew submits → projects assigns → supervisor verifies |

### Photo Test Fixture

All photo tests MUST use a real-sized PNG. Generate one:

```python
import struct, zlib, base64

width, height = 200, 200
raw_data = b''
for y in range(height):
    raw_data += b'\x00'
    for x in range(width):
        raw_data += bytes([x % 256, y % 256, (x+y) % 256])
compressed = zlib.compress(raw_data)
ihdr = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
png = (b'\x89PNG\r\n\x1a\n' +
       struct.pack('>I', 13) + b'IHDR' + ihdr + struct.pack('>I', zlib.crc32(b'IHDR' + ihdr) & 0xffffffff) +
       struct.pack('>I', len(compressed)) + b'IDAT' + compressed + struct.pack('>I', zlib.crc32(b'IDAT' + compressed) & 0xffffffff) +
       struct.pack('>I', 0) + b'IEND' + struct.pack('>I', zlib.crc32(b'IEND') & 0xffffffff))
PHOTO_B64 = base64.b64encode(png).decode()
PHOTO_DATA_URL = f"data:image/png;base64,{PHOTO_B64}"
# Size: ~151KB base64
```

Use `PHOTO_DATA_URL` everywhere a photo field is tested.

---

## Maintenance Module (15 scenarios)

### MAINT-001: Submit Request (Happy Path)
- **Type:** happy
- **Role:** test.crew1@bebang.ph
- **Call:** `POST hrms.api.store.submit_maintenance_request`
- **Payload:**
  ```json
  {
    "store": "TEST-STORE-BGC - BEI",
    "title": "Broken light in café area — needs 220V fixture & bulb replacement",
    "description": "Light flickering since yesterday. Located near the counter. Customers complained about dim lighting during evening shift.",
    "category": "Electrical",
    "priority": "High",
    "equipment_area": "Lights"
  }
  ```
- **Assert:**
  - Response: `ok == true`, `message.name` starts with `MR-`
  - DB verify: `status == "Open"`, `priority == "High"`, `category == "Electrical"`, `reported_by == test.crew1@bebang.ph`

### MAINT-002: Submit Request WITH Photo (Dict Format)
- **Type:** edge
- **Role:** test.crew1@bebang.ph
- **Call:** `POST hrms.api.store.submit_maintenance_request`
- **Payload:**
  ```json
  {
    "store": "TEST-STORE-BGC - BEI",
    "title": "Leaking pipe under sink",
    "description": "Photo attached showing water damage",
    "category": "Plumbing",
    "priority": "Urgent",
    "equipment_area": "Sink/Faucet",
    "photos": "<PHOTO_DATA_URL>"
  }
  ```
- **Assert:**
  - Response: `ok == true`
  - DB verify: photo_count >= 1, photo URL returns HTTP 200

### MAINT-003: Assign Request
- **Type:** happy
- **Role:** test.projects@bebang.ph (Projects Head)
- **Depends on:** MAINT-001 (use its request_id)
- **Call:** `POST hrms.api.projects.assign_maintenance_request`
- **Payload:**
  ```json
  {
    "request_id": "<from MAINT-001>",
    "assigned_to": "test.projects.staff@bebang.ph",
    "scheduled_date": "2026-02-15"
  }
  ```
- **Assert:**
  - DB verify: `status == "Assigned"`, `assigned_to == "test.projects.staff@bebang.ph"`, `scheduled_date == "2026-02-15"`

### MAINT-004: Status Transition — In Progress
- **Type:** happy
- **Role:** test.projects@bebang.ph
- **Depends on:** MAINT-003
- **Call:** `POST hrms.api.projects.update_maintenance_status`
- **Payload:** `{"request_id": "<from MAINT-001>", "status": "In Progress"}`
- **Assert:** DB verify: `status == "In Progress"`

### MAINT-005: Status Transition — Pending Acknowledgement
- **Type:** edge
- **Role:** test.projects@bebang.ph
- **Depends on:** MAINT-004
- **Call:** `POST hrms.api.projects.update_maintenance_status`
- **Payload:** `{"request_id": "<from MAINT-001>", "status": "Pending Acknowledgement", "notes": "Waiting for replacement part from supplier"}`
- **Assert:** DB verify: `status == "Pending Acknowledgement"`

### MAINT-006: Status Transition — Pending Acknowledgement Back to In Progress
- **Type:** edge
- **Role:** test.projects@bebang.ph
- **Depends on:** MAINT-005
- **Call:** `POST hrms.api.projects.update_maintenance_status`
- **Payload:** `{"request_id": "<from MAINT-001>", "status": "In Progress", "notes": "Parts arrived, resuming work"}`
- **Assert:** DB verify: `status == "In Progress"`

### MAINT-007: Record Completion WITH 150KB After Photo (Dict Format)
- **Type:** regression | **Origin:** BUG-1 (2026-02-11, Dan reported AttributeError)
- **Role:** test.projects@bebang.ph
- **Depends on:** MAINT-006 (request must be In Progress)
- **Call:** `POST hrms.api.projects.record_maintenance_completion`
- **Payload:**
  ```json
  {
    "request_id": "<from MAINT-001>",
    "completion_date": "2026-02-11",
    "technician_name": "Test Technician",
    "work_description": "Replaced 220V fixture and LED bulb. Tested for 30 minutes, no flickering.",
    "resolution_status": "Fully Resolved",
    "after_photos": "[{\"photo\": \"<PHOTO_DATA_URL>\", \"caption\": \"After repair — new fixture installed\"}]"
  }
  ```
- **Assert:**
  - Response: `ok == true`
  - DB verify: `status == "Completed"`, `resolved_date` is set
  - Completion record: `after_photos` URL accessible (HTTP 200)

### MAINT-008: Supervisor Verification
- **Type:** happy
- **Role:** test.supervisor@bebang.ph
- **Depends on:** MAINT-007 (request must be Completed)
- **Call:** `POST hrms.api.projects.update_maintenance_status`
- **Payload:** `{"request_id": "<from MAINT-001>", "status": "Verified", "notes": "Supervisor confirmed repair quality OK"}`
- **Assert:** DB verify: `status == "Verified"`

### MAINT-009: Projects Staff Sees Assigned Tasks
- **Type:** happy
- **Role:** test.projects.staff@bebang.ph
- **Call:** `GET hrms.api.projects.get_maintenance_queue?assigned_to_me=1`
- **Assert:**
  - Response: `ok == true`
  - `message.requests` is a list with length > 0
  - At least one request has `assigned_to` matching this user

### MAINT-010: Staff Sees Own Submitted Requests
- **Type:** happy
- **Role:** test.staff@bebang.ph (submit first) then check
- **Step 1:** Submit a request via `hrms.api.store.submit_maintenance_request` with:
  ```json
  {
    "store": "TEST-STORE-BGC - BEI",
    "title": "Staff test request for feed check",
    "description": "Testing that submitted requests appear in my requests list.",
    "category": "Electrical",
    "priority": "Normal",
    "equipment_area": "Lights"
  }
  ```
- **Step 2:** `GET hrms.api.store.get_my_maintenance_requests`
- **Assert:**
  - Response: `message.requests` is a list (NOT a flat list — it's `message.requests`)
  - The submitted request_id appears in the list

### MAINT-011: RBAC — Staff Blocked from Admin Endpoints
- **Type:** rbac
- **Role:** test.staff@bebang.ph (Store OIC — NOT Projects User)
- **Call:** `POST hrms.api.projects.update_maintenance_status`
- **Payload:** `{"request_id": "<any valid MR>", "status": "Assigned"}`
- **Assert:** Response: `ok == false`, HTTP 403

### MAINT-012: RBAC — Crew Blocked from Admin Endpoints
- **Type:** rbac
- **Role:** test.crew1@bebang.ph
- **Call:** `POST hrms.api.projects.assign_maintenance_request`
- **Payload:** `{"request_id": "<any valid MR>", "assigned_to": "test.crew1@bebang.ph"}`
- **Assert:** Response: `ok == false`, HTTP 403

### MAINT-013: Invalid Status Transition Rejected
- **Type:** adversarial
- **Role:** test.projects@bebang.ph
- **Setup:** Create request via `hrms.api.store.submit_maintenance_request` with:
  ```json
  {
    "store": "TEST-STORE-BGC - BEI",
    "title": "Test request for invalid transition",
    "description": "This request will test skipping status transitions.",
    "category": "Plumbing",
    "priority": "Normal",
    "equipment_area": "Sink/Faucet"
  }
  ```
- **Call:** `POST hrms.api.projects.update_maintenance_status`
- **Payload:** `{"request_id": "<new MR>", "status": "Completed"}` (skipping Assigned/In Progress)
- **Assert:** Response: `ok == false` (cannot jump from Open to Completed)

### MAINT-014: Invalid Status Name Rejected
- **Type:** adversarial
- **Role:** test.projects@bebang.ph
- **Call:** `POST hrms.api.projects.update_maintenance_status`
- **Payload:** `{"request_id": "<any MR>", "status": "Pending Parts"}`
- **Assert:** Response: `ok == false` (not a valid status — correct name is "Pending Acknowledgement")

### MAINT-015: Dashboard Stats Return Valid Data
- **Type:** happy
- **Role:** test.projects@bebang.ph
- **Call:** `GET hrms.api.projects.get_maintenance_dashboard_stats`
- **Assert:**
  - Response: `ok == true`
  - Has keys: `total_open`, `total_assigned`, `total_in_progress`
  - All counts are integers >= 0

### MAINT-016: Submit Request with Invalid Store — Expect Validation Error
- **Type:** rbac | **Origin:** Sprint-04 audit B-07
- **Role:** test.crew1@bebang.ph
- **Call:** `POST hrms.api.store.submit_maintenance_request`
- **Payload:**
  ```json
  {
    "store": "NON-EXISTENT-STORE-XYZ - BEI",
    "title": "Testing invalid store rejection",
    "description": "This should fail because the store does not exist in the system.",
    "category": "Electrical",
    "priority": "Normal",
    "equipment_area": "Lights"
  }
  ```
- **Assert:** Response: `ok == false`, error message references invalid store or 403/400 HTTP status. DB: no new `BEI Maintenance Request` record created.

### MAINT-017: Assess Request Without Projects Role — Expect 403
- **Type:** rbac | **Origin:** Sprint-04 audit B-07
- **Role:** test.staff@bebang.ph (Store OIC — no Projects role)
- **Setup:** Use any valid MR name (e.g. from MAINT-001 run)
- **Call:** `POST hrms.api.projects.assess_maintenance_request`
- **Payload:**
  ```json
  {
    "request_id": "<any valid MR>",
    "concern_type": "Wear & Tear",
    "notes": "Unauthorized assessment attempt"
  }
  ```
- **Assert:** Response: `ok == false`, HTTP 403 PermissionError. DB: `concern_type` on the MR remains unchanged.

### MAINT-018: Set Charge with Negative Amount — Expect Validation Error
- **Type:** adversarial | **Origin:** Sprint-04 audit B-07
- **Role:** test.projects@bebang.ph (Projects Head)
- **Setup:** Use any valid MR name
- **Call:** `POST hrms.api.projects.set_maintenance_charge`
- **Payload:**
  ```json
  {
    "request_id": "<any valid MR>",
    "charge_amount": -5000,
    "charging_reason": "Attempting to credit store — should fail"
  }
  ```
- **Assert:** Response: `ok == false`, validation error about negative or invalid charge amount. DB: `charge_amount` on MR remains unchanged (not set to -5000).

### MAINT-019: Acknowledge Charge for Different Store — Expect 403
- **Type:** rbac | **Origin:** Sprint-04 audit B-07 / BLOCKER-10
- **Role:** test.supervisor@bebang.ph (Store Supervisor — bound to TEST-STORE-BGC branch)
- **Setup:** Create an MR for a DIFFERENT store (e.g. TEST-STORE-MM), set `charge_to_store=1` on it
- **Call:** `POST hrms.api.projects.acknowledge_maintenance_charge`
- **Payload:**
  ```json
  {
    "request_id": "<MR for different store>"
  }
  ```
- **Assert:** Response: `ok == false`, HTTP 403. DB: `store_acknowledged` remains `0`. This tests BLOCKER-10 (cross-store charge acknowledgement guard).
- **Note:** This test will FAIL until BLOCKER-10 (store-binding check in `acknowledge_maintenance_charge`) is implemented.

### MAINT-020: Complete Maintenance with Missing Required Fields — Expect Error
- **Type:** adversarial | **Origin:** Sprint-04 audit B-07
- **Role:** test.projects@bebang.ph
- **Setup:** Use a MR in `In Progress` status
- **Call:** `POST hrms.api.projects.record_maintenance_completion`
- **Payload (missing technician_name and work_description):**
  ```json
  {
    "request_id": "<MR in In Progress>",
    "completion_date": "2026-02-20",
    "resolution_status": "Fully Resolved"
  }
  ```
- **Assert:** Response: `ok == false`, validation error referencing missing required fields. DB: no `BEI Maintenance Completion` record created.

### MAINT-021: Double-Submit Same Request — Expect Idempotent or Error
- **Type:** adversarial | **Origin:** Sprint-04 audit B-07
- **Role:** test.projects@bebang.ph
- **Setup:** Use a MR that is already `Completed` (e.g. from MAINT-007)
- **Call:** `POST hrms.api.projects.record_maintenance_completion`
- **Payload:**
  ```json
  {
    "request_id": "<already Completed MR>",
    "completion_date": "2026-02-20",
    "technician_name": "Second Technician",
    "work_description": "Second completion attempt on already closed request.",
    "resolution_status": "Fully Resolved",
    "after_photos": "<PHOTO_DATA_URL>"
  }
  ```
- **Assert:** Either (a) Response `ok == false` with error "already completed" / invalid status transition, OR (b) If idempotent: `ok == true` but DB shows only ONE completion record (no duplicate). Either outcome is acceptable; silent creation of a second completion record is NOT acceptable.

### MAINT-022: SLA Breach Notification Fires After Threshold
- **Type:** edge | **Origin:** Sprint-04 audit B-07 / Gap G-077
- **Role:** System (scheduled job trigger)
- **Setup:**
  1. Create an Urgent MR via `hrms.api.store.submit_maintenance_request`
  2. Manually set `creation` to 5 hours ago: `UPDATE \`tabBEI Maintenance Request\` SET creation = DATE_SUB(NOW(), INTERVAL 5 HOUR) WHERE name = '<MR>'`
  3. Confirm `status` is still `Open`
- **Call:** Trigger directly via bench console: `frappe.get_doc("BEI Maintenance Request", "<MR>")` then `from hrms.api.projects import check_sla_violations; check_sla_violations()`
- **Assert:**
  - No Python exception raised
  - Frappe Chat space (SPACE_NOTIFICATIONS) receives a message containing `SLA BREACH` and the MR name
  - Check Frappe Error Log for any "SLA alert failed" entries — there should be none

### MAINT-023: Orphan Cleanup — Completion Without Valid Request
- **Type:** adversarial | **Origin:** Sprint-04 audit B-07
- **Role:** test.projects@bebang.ph
- **Call:** `POST hrms.api.projects.record_maintenance_completion`
- **Payload:**
  ```json
  {
    "request_id": "MR-DOES-NOT-EXIST-99999",
    "completion_date": "2026-02-20",
    "technician_name": "Ghost Technician",
    "work_description": "Trying to complete a non-existent maintenance request.",
    "resolution_status": "Fully Resolved",
    "after_photos": "<PHOTO_DATA_URL>"
  }
  ```
- **Assert:** Response: `ok == false`, error referencing record not found (404/DoesNotExist). DB: no orphaned `BEI Maintenance Completion` record created.

### MAINT-024: Concurrent Charge Updates on Same Request
- **Type:** adversarial | **Origin:** Sprint-04 audit B-07
- **Role:** Two simultaneous calls as test.projects@bebang.ph
- **Setup:** Use a valid MR in `Assigned` or `In Progress` state
- **Step 1:** Send two near-simultaneous POST requests to `hrms.api.projects.set_maintenance_charge` with different amounts:
  - Request A: `charge_amount = 3000, charging_reason = "Call A"`
  - Request B: `charge_amount = 7000, charging_reason = "Call B"`
- **Assert:**
  - Only ONE charge amount wins (no intermediate state with both amounts)
  - DB: `charge_amount` is either 3000 or 7000 — not null, not a sum, not 0
  - No 500 error returned from either call
  - Frappe error log has no uncaught exceptions from this operation

---

## Store Operations Module (10 scenarios)

### STORE-001: Submit Opening Report
- **Type:** happy
- **Role:** test.crew1@bebang.ph
- **Call:** `POST hrms.api.store.submit_opening_report`
- **Payload:**
  ```json
  {
    "store": "TEST-STORE-BGC - BEI",
    "checklist_items": [
      {"item": "Floor swept and mopped", "status": "Yes"},
      {"item": "Display cases clean", "status": "Yes"},
      {"item": "Cash register balanced", "status": "Yes"},
      {"item": "Handwashing station stocked", "status": "Yes"},
      {"item": "Temperature logs started", "status": "Yes"}
    ],
    "notes": "All checks completed. Morning shift crew: 3 present, 0 absent."
  }
  ```
- **Assert:** Response `message.success == true`, `message.name` starts with `BEI-OPEN-`

### STORE-002: Submit Opening Report WITH Photos
- **Type:** edge
- **Role:** test.crew1@bebang.ph
- **Call:** `POST hrms.api.store.submit_opening_report`
- **Payload:**
  ```json
  {
    "store": "TEST-STORE-BGC - BEI",
    "checklist_items": [
      {"item": "Backup area clean", "status": "Yes"},
      {"item": "Frozen milk stocked", "status": "Yes"}
    ],
    "photo_backup_area": "<PHOTO_DATA_URL>",
    "photo_frozen_milk": "<PHOTO_DATA_URL>",
    "notes": "Opening with photos — backup area and frozen milk area documented."
  }
  ```
- **Assert:** `message.success == true`, record created. (Photo URLs are saved to DB fields but NOT returned in the API response — verify only `success` and `name`.)

### STORE-003: Closing Report — 3-Stage Pipeline
- **Type:** happy
- **Role:** test.crew1@bebang.ph
- **Step 1:** `POST hrms.api.store.get_or_create_closing_report` with `{"store": "TEST-STORE-BGC - BEI"}`
- **Step 2:** `POST hrms.api.store.submit_closing_stage1_cash` with:
  ```json
  {
    "report_name": "<from step 1>",
    "petty_cash_fund": 500,
    "delivery_fund": 200,
    "change_fund": 300,
    "actual_cash_count": 5000,
    "variance_explanation": "Test variance — minor discrepancy from morning changeover."
  }
  ```
- **Step 3:** `POST hrms.api.store.submit_closing_stage2_checklist` with:
  ```json
  {
    "report_name": "<from step 1>",
    "inventory_items": "[{\"item_name\": \"Leche flan\", \"category\": \"Highest Cost\", \"expected_count\": 10, \"actual_count\": 8}]",
    "cashier_signoff": true,
    "production_signoff": true
  }
  ```
- **Step 4:** `POST hrms.api.store.submit_closing_stage3_photos` with:
  ```json
  {
    "report_name": "<from step 1>",
    "x_reading_opening_photo": "<PHOTO_DATA_URL>",
    "x_reading_closing_photo": "<PHOTO_DATA_URL>",
    "z_reading_photo": "<PHOTO_DATA_URL>"
  }
  ```
- **Assert:** Each stage returns `message.success == true`. Stage 4 (photos) saves to DB but photo URLs are NOT returned in the response — verify only `success`. (Photo storage can be verified via separate `get_doc` call if needed.)

### STORE-004: Submit Mid-Shift Check
- **Type:** happy
- **Role:** test.crew1@bebang.ph
- **Call:** `POST hrms.api.store.submit_midshift_check`
- **Payload:**
  ```json
  {
    "store": "TEST-STORE-BGC - BEI",
    "cleanliness_status": "Good",
    "checklist_items": [
      {"item": "Display cases restocked", "status": "Yes"},
      {"item": "Floor area clean", "status": "Yes"}
    ],
    "notes": "Peak hour rush handled. 2 complaints logged about wait time."
  }
  ```
- **Assert:** `message.success == true`, record created with shift auto-detected

### STORE-005: Submit Bank Deposit
- **Type:** happy
- **Role:** test.crew1@bebang.ph
- **Call:** `POST hrms.api.store.submit_bank_deposit`
- **Payload:**
  ```json
  {
    "store": "TEST-STORE-BGC - BEI",
    "deposit_date": "2026-02-12",
    "bank": "BDO",
    "total_amount": 25000,
    "photos": "[\"<PHOTO_DATA_URL>\"]",
    "notes": "Morning deposit — deposit slip attached."
  }
  ```
- **Assert:** `message.success == true`, record created (BEI-DEP-xxxx)

### STORE-006: Upload POS Data
- **Type:** happy
- **Role:** test.crew1@bebang.ph
- **Call:** `POST hrms.api.store.upload_pos_data`
- **Payload:**
  ```json
  {
    "store": "TEST-STORE-BGC - BEI",
    "pos_date": "2026-02-12",
    "pos_system": "Mosaic",
    "discount_report": "<PHOTO_DATA_URL>",
    "transaction_report": "<PHOTO_DATA_URL>",
    "product_mix": "<PHOTO_DATA_URL>",
    "daily_sales_revenue": "<PHOTO_DATA_URL>",
    "sales_summary": "<PHOTO_DATA_URL>"
  }
  ```
- **Assert:** `message.success == true`, record created (BEI-POS-xxxx). POS extraction hook errors are non-blocking (upload succeeds even if extraction fails for image files).

### STORE-007: Crew Submits, Area Supervisor Reviews in Reports Feed
- **Type:** happy (multi-role)
- **Note:** The reports feed uses `custom_area_supervisor` on Warehouse to determine which stores a user supervises. TEST-STORE-BGC has `custom_area_supervisor = test.area@bebang.ph` (Area Supervisor). Use the **area supervisor** account, not store supervisor.
- **Step 1:** test.crew1 submits opening report (STORE-001)
- **Step 2:** test.area@bebang.ph calls `GET hrms.api.supervisor.get_reports_feed`
- **Assert:** `message.reports` is a list with length > 0, at least one item has `report_type == "opening"` and today's date

### STORE-008: RBAC — Warehouse User Cannot Submit Store Reports
- **Type:** rbac
- **Role:** test.warehouse@bebang.ph
- **Call:** `POST hrms.api.store.submit_opening_report`
- **Payload:** `{"store": "TEST-STORE-BGC - BEI", "checklist_items": [{"item": "test", "status": "Yes"}]}`
- **Assert:** Response: `message.success == false` or HTTP 403 (permission error)

### STORE-009: Submit Opening Report with Empty Checklist
- **Type:** adversarial
- **Role:** test.crew1@bebang.ph
- **Call:** `POST hrms.api.store.submit_opening_report`
- **Payload:** `{"store": "TEST-STORE-BGC - BEI"}` (no checklist_items — now optional)
- **Assert:** `message.success == true` (empty checklist is allowed per REQ-007 incomplete submission)

### STORE-010: Submit with Invalid Store Name
- **Type:** adversarial
- **Role:** test.crew1@bebang.ph
- **Call:** `POST hrms.api.store.submit_opening_report`
- **Payload:** `{"store": "FAKE-STORE-999", "checklist_items": [{"item": "test", "status": "Yes"}]}`
- **Assert:** `message.success == false` (store not found, NOT 500)

---

## HR Self-Service Module (8 scenarios + 2 bug regression)

### HR-001: Submit Leave Application
- **Type:** happy
- **Role:** test.crew1@bebang.ph
- **Call:** `POST hrms.api.payroll.submit_leave_application`
- **Payload:**
  ```json
  {
    "leave_type": "Casual Leave",
    "from_date": "2026-03-15",
    "to_date": "2026-03-15",
    "reason": "Personal errand — need to visit SSS office for contribution update"
  }
  ```
- **Assert:** `message.success == true`, `message.name` is a Leave Application ID, `message.status == "Open"`

### HR-002: Submit Coverage Request
- **Type:** happy
- **Role:** test.supervisor@bebang.ph (supervisors request coverage)
- **Call:** `POST hrms.api.coverage.request_coverage`
- **Payload:**
  ```json
  {
    "store": "TEST-STORE-BGC - BEI",
    "coverage_date": "2026-03-15",
    "shift": "Opening",
    "reason": "Sick Leave",
    "absent_employee": "TEST-CREW-001",
    "notes": "Employee called in sick, need coverage for opening shift"
  }
  ```
- **Note:** `reason` is a Select field — valid values: `Sick Leave`, `Emergency`, `Training`, `Vacation`, `Resignation`, `Other`. Use `notes` for free-form description. Valid shift values: `Opening`, `Mid`, `Closing`. `absent_employee` can be Employee ID or employee name.
- **Assert:** `message.success == true`, `message.name` returned

### HR-003: Submit Official Business Checkout
- **Type:** happy
- **Role:** test.crew1@bebang.ph
- **Call:** `POST hrms.api.official_business.checkout`
- **Payload:**
  ```json
  {
    "destination": "SSS BGC Branch — contribution inquiry and payment",
    "purpose": "Government compliance errand (SSS contribution update)",
    "latitude": 14.5547,
    "longitude": 121.0505,
    "accuracy": 15.0,
    "selfie_base64": "<PHOTO_DATA_URL>"
  }
  ```
- **Assert:** Response contains `name` (OB record) and `status == "success"`

### HR-004: Supervisor Approves Leave
- **Type:** happy (multi-role)
- **Depends on:** HR-001
- **Prerequisites:** Employee TEST-CREW-001 must have `leave_approver = test.supervisor@bebang.ph` (CONFIGURED).
- **Step 1:** test.crew1 submits leave via `POST hrms.api.payroll.submit_leave_application` with a FUTURE date not already used (e.g., `from_date`/`to_date` = `2026-04-01`). If duplicate validation triggers, use a different date.
- **Step 2:** test.supervisor calls `GET hrms.api.supervisor.get_pending_approvals`
- **Step 3:** Find the leave in queue (`message.approvals` list), supervisor calls `POST hrms.api.supervisor.approve_item` with the queue item name
- **Assert (CRITICAL):** Leave appears in supervisor's queue AND approval changes the leave status from "Open"

### HR-005: View My Attendance
- **Type:** happy
- **Role:** test.crew1@bebang.ph
- **Call:** `GET hrms.api.payroll.get_my_attendance`
- **Assert:** `message.success == true`, `message.attendance` is a list (may be empty for test account), `message.summary` has keys `present`, `absent`, `on_leave`, `late`

### HR-006: View My Payslips
- **Type:** happy
- **Role:** test.crew1@bebang.ph
- **Call:** `GET hrms.api.payroll.get_my_payslips`
- **Assert:** `message.success == true`, `message.payslips` is a list (may be empty, but no 500)

### HR-007: View My Schedule
- **Type:** happy
- **Role:** test.crew1@bebang.ph
- **Call:** `GET hrms.api.payroll.get_my_schedule`
- **Assert:** `message.success == true`, `message.schedule` is a list (may be empty, but no 500)

### HR-008: RBAC — Projects User Cannot Approve Leaves
- **Type:** rbac
- **Role:** test.projects@bebang.ph
- **Call:** `GET hrms.api.supervisor.get_pending_approvals`
- **Assert:** Returns empty approvals list (Projects user is not an approver, so no items appear)

### BUG-015: Leave Approval — Store Supervisor Permission
- **Type:** regression | **Origin:** BUG-015 (2026-02-12, Store Supervisor PermissionError on BEI Approval Queue)
- **Role:** test.supervisor@bebang.ph
- **Call:** `GET hrms.api.supervisor.get_pending_approvals`
- **Assert:** `message.approvals` is a list (no PermissionError). Supervisor can access the approval queue.

### BUG-017: Employee Payslip Self-Service
- **Type:** regression | **Origin:** BUG-017 (2026-02-12, no self-service payslip endpoint)
- **Role:** test.crew1@bebang.ph
- **Call:** `GET hrms.api.payroll.get_my_payslips`
- **Assert:** `message.success == true`, no PermissionError. Employee can view own payslips.

---

## Expense Module (6 scenarios)

### EXP-001: Submit Expense with Receipt Photo
- **Type:** happy
- **Role:** test.crew1@bebang.ph
- **Call:** `POST hrms.api.expense.submit_expense`
- **Payload:**
  ```json
  {
    "manual_vendor": "Uber Philippines",
    "manual_description": "Uber ride to BGC branch for emergency delivery pickup — receipt #UB20260211",
    "manual_amount": 350.50,
    "manual_date": "2026-02-12",
    "receipt_photo": "<PHOTO_DATA_URL>"
  }
  ```
- **Note:** ALL 5 fields are MANDATORY (manual_vendor, manual_description, manual_amount, manual_date, receipt_photo). There is NO `category` field — classification is done automatically by backend ML.
- **Assert:** `message.success == true`, `message.data.name` is a BEI Expense Request ID

### EXP-002: Submit Expense WITHOUT Photo (Should Fail)
- **Type:** adversarial
- **Role:** test.crew1@bebang.ph
- **Call:** `POST hrms.api.expense.submit_expense`
- **Payload:** `{"manual_vendor": "Mercury Drug", "manual_description": "Parking fee", "manual_amount": 50, "manual_date": "2026-02-12"}`
- **Note:** `receipt_photo` is ALWAYS mandatory — there is NO small amount exemption.
- **Assert:** Response: `ok == false` (validation error: "Receipt photo is required")

### EXP-003: View My Expenses
- **Type:** happy
- **Role:** test.crew1@bebang.ph
- **Call:** `GET hrms.api.expense.get_my_expenses`
- **Assert:** `message.success == true`, `message.data` is a list (may be empty for test account)

### EXP-004: PCF Status Check
- **Type:** happy
- **Role:** test.crew1@bebang.ph
- **Call:** `GET hrms.api.pcf.get_my_pending_expenses`
- **Note:** `get_pcf_dashboard` does NOT exist. Available PCF endpoints: `get_my_pending_expenses`, `get_pcf_status`, `get_store_pending_summary`, `get_pcf_custodians`, `get_batch_history`
- **Assert:** Returns data or empty list (no 500)

### EXP-005: Submit Expense with Zero Amount
- **Type:** adversarial
- **Role:** test.crew1@bebang.ph
- **Call:** `POST hrms.api.expense.submit_expense`
- **Payload:** `{"manual_vendor": "Test", "manual_description": "Zero test", "manual_amount": 0, "manual_date": "2026-02-12", "receipt_photo": "<PHOTO_DATA_URL>"}`
- **Assert:** Should fail validation (not 500) — "Vendor, description, and amount are required" (0 is falsy)

### EXP-006: Submit Expense with Negative Amount
- **Type:** adversarial
- **Role:** test.crew1@bebang.ph
- **Call:** `POST hrms.api.expense.submit_expense`
- **Payload:** `{"manual_vendor": "Test", "manual_description": "Negative test", "manual_amount": -100, "manual_date": "2026-02-12", "receipt_photo": "<PHOTO_DATA_URL>"}`
- **Assert:** Should fail or create record (negative amount passes the `if not manual_amount` check since -100 is truthy — this is an edge case the backend doesn't currently validate)

---

## Communication Module (4 scenarios)

### COMM-001: Send Kudos
- **Type:** happy
- **Role:** test.crew1@bebang.ph
- **Call:** `POST hrms.api.communication.send_kudos`
- **Payload:** `{"to_employee": "TEST-SUPERVISOR-001", "category": "Leadership", "message": "Great leadership during rush hour — team stayed motivated!"}`
- **Assert:** Record created (kudos name returned or success response)

### COMM-002: Submit CEO Complaint
- **Type:** happy
- **Role:** test.crew1@bebang.ph
- **Call:** `POST hrms.api.communication.submit_ceo_complaint`
- **Payload:** `{"category": "Workplace Issue", "subject": "Broken AC in store for 3 days", "description": "Multiple calls to maintenance but no response. Customers complaining about heat."}`
- **Note:** Valid categories: `Workplace Issue`, `Policy Concern`, `Misconduct Report`, `Suggestion`, `Other`
- **Assert:** `message.success == true`, `message.name` returned

### COMM-003: Create Support Ticket
- **Type:** happy
- **Role:** test.crew1@bebang.ph
- **Call:** `POST hrms.api.communication.create_support_ticket`
- **Payload:** `{"category": "IT/Technical", "subject": "Cannot access payslip page", "description": "Getting blank page when clicking Payslip. Started today.", "priority": "Medium"}`
- **Note:** Valid categories: `IT/Technical`, `HR Question`, `Payroll Issue`, `App Bug`, `Feature Request`, `Other`
- **Assert:** `message.success == true`, `message.name` returned

### COMM-004: View Announcements
- **Type:** happy
- **Role:** test.crew1@bebang.ph
- **Call:** `GET hrms.api.communication.get_announcements`
- **Assert:** Returns list (no 500)

---

## Regression Bank

Every bug found by real users or manual testing becomes a permanent test. These NEVER get removed.

| ID | Date | Original Bug | Test |
|----|------|-------------|------|
| REG-001 | 2026-02-11 | BUG-1: after_photos dict crash | MAINT-007 (completion with dict-format photo) |
| REG-002 | 2026-02-11 | BUG-2: "Pending Parts" rejected | MAINT-005 + MAINT-014 |
| REG-003 | 2026-02-10 | Staff can call update_maintenance_status | MAINT-011 |
| REG-004 | 2026-02-08 | Cycle count "Approved" not valid status | (add when inventory scenarios written) |
| REG-005 | 2026-02-12 | BUG-002: Closing report base64 overflow | STORE-003 (3-stage pipeline with 150KB photos) |
| REG-006 | 2026-02-12 | BUG-006: POS upload DataError 1406 | STORE-006 (upload_pos_data with 150KB files) |
| REG-007 | 2026-02-12 | BUG-015: Supervisor PermissionError on approval queue | BUG-015 (in HR section) |
| REG-008 | 2026-02-12 | BUG-017: No self-service payslip endpoint | BUG-017 (in HR section) |
| REG-009 | 2026-02-12 | POS extraction hook blocks upload | STORE-006 (extraction error is non-blocking) |

**Rule:** When a real user finds a bug, add a regression scenario HERE within the same fix commit. The regression bank only grows — it never shrinks.

---

## Finance & Billing

**Module:** Finance & Accounting Automation (v2.1)
**Endpoints:** `apply_franchise_payment`, `generate_acknowledgement_receipt`, `generate_monthly_billing`, `auto_assign_gl_account`
**Test accounts:** test.hr@bebang.ph (Accounts Manager role), test.staff@bebang.ph (Store Staff — no finance perms)

### Happy Path

#### FIN-001: Apply full payment to Sent billing

**Type:** happy | **Origin:** Plan v2.1 Task 3
**Pre-req:** BEI Billing Schedule exists with status="Sent", total_amount=100000

```
POST /api/method/hrms.api.procurement.apply_franchise_payment
Session: test.hr@bebang.ph (Accounts Manager)
Payload: {
  "billing_name": "<billing_name>",
  "amount_paid": 100000,
  "payment_date": "2026-02-12",
  "payment_reference": "BT-2026-001"
}
```

**Assert:**
- Response: `success=True`, `ar_number` starts with "AR-", `new_balance=0`
- DB: `BEI Billing Schedule.<billing_name>.status == "Paid"`
- DB: `BEI Billing Schedule.<billing_name>.amount_paid == 100000`
- DB: `BEI Billing Schedule.<billing_name>.balance_due == 0`
- DB: `BEI Acknowledgement Receipt` exists with `billing_schedule=<billing_name>`

#### FIN-002: Apply partial payment

**Type:** happy | **Origin:** Plan v2.1 Task 3
**Pre-req:** BEI Billing Schedule with status="Sent", total_amount=100000

```
POST /api/method/hrms.api.procurement.apply_franchise_payment
Payload: {
  "billing_name": "<billing_name>",
  "amount_paid": 50000,
  "payment_date": "2026-02-12",
  "payment_reference": "BT-2026-002"
}
```

**Assert:**
- Response: `status="Partially Paid"`, `new_balance=50000`
- DB: `BEI Billing Schedule.<billing_name>.status == "Partially Paid"`
- DB: `BEI Billing Schedule.<billing_name>.amount_paid == 50000`
- DB: `BEI Billing Schedule.<billing_name>.balance_due == 50000`

#### FIN-003: Apply second partial to complete payment

**Type:** happy | **Origin:** Plan v2.1 Task 3
**Pre-req:** BEI Billing Schedule with status="Partially Paid", amount_paid=50000, total_amount=100000

```
POST /api/method/hrms.api.procurement.apply_franchise_payment
Payload: {
  "billing_name": "<billing_name>",
  "amount_paid": 50000,
  "payment_date": "2026-02-13",
  "payment_reference": "BT-2026-003"
}
```

**Assert:**
- Response: `status="Paid"`, `new_balance=0`
- DB: `BEI Billing Schedule.<billing_name>.amount_paid == 100000` (accumulated, not overwritten)
- DB: `BEI Billing Schedule.<billing_name>.status == "Paid"`

#### FIN-004: Generate AR standalone

**Type:** happy | **Origin:** Plan v2.1 Task 2

```
POST /api/method/hrms.api.procurement.generate_acknowledgement_receipt
Session: test.hr@bebang.ph (Accounts Manager)
Payload: { "billing_name": "<billing_name>" }
```

**Assert:**
- Response: `ar_name` starts with "AR-"
- DB: AR doc has `billing_schedule`, `store`, `amount`, `payment_date` populated
- DB: AR doc `status == "Generated"`

#### FIN-005: Generate monthly billing for single store

**Type:** happy | **Origin:** Plan v2.1 Task 4
**Pre-req:** BEI Store Closing Report exists for store with docstatus=1 in the target period

```
POST /api/method/hrms.api.procurement.generate_monthly_billing
Session: test.hr@bebang.ph (Accounts Manager)
Payload: { "billing_period": "2026-02", "store": "<test_store>" }
```

**Assert:**
- Response: `generated=1`, `skipped=0`, `errors=[]`
- DB: `BEI Billing Schedule` created with `billing_period="2026-02"`, `store=<test_store>`, `status="Draft"`
- DB: Fee calculations match store type (check royalty_fee, marketing_fee per billing matrix)

#### FIN-006: Generate monthly billing skips duplicates

**Type:** happy | **Origin:** Plan v2.1 Task 4
**Pre-req:** Run FIN-005 first so billing already exists for the store+period

```
POST /api/method/hrms.api.procurement.generate_monthly_billing
Payload: { "billing_period": "2026-02", "store": "<test_store>" }
```

**Assert:**
- Response: `generated=0`, `skipped=1`
- DB: Only ONE billing exists for the store+period (no duplicate)

#### FIN-007: GL auto-assign for PCF request

**Type:** happy | **Origin:** Plan v2.1 Task 1
**Pre-req:** BEI Payment Request with rfp_type="PCF Replenishment", account_code empty

```
Trigger: Save/validate the BEI Payment Request
```

**Assert:**
- DB: `BEI Payment Request.account_code` contains "1113000" (full Frappe name like "1113000 - Petty Cash Fund - BEI")
- NOT bare "1113000" — must be the full Frappe Account name

### Edge Cases

#### FIN-NEG-001: Overpayment rejected

**Type:** edge | **Origin:** Plan v2.1 Task 3
**Pre-req:** BEI Billing Schedule with status="Sent", total_amount=100000

```
POST /api/method/hrms.api.procurement.apply_franchise_payment
Payload: {
  "billing_name": "<billing_name>",
  "amount_paid": 150000,
  "payment_date": "2026-02-12",
  "payment_reference": "BT-OVER"
}
```

**Assert:**
- Response: HTTP 417 or error containing "would exceed balance due"
- DB: `BEI Billing Schedule.amount_paid` unchanged (still 0)
- DB: `BEI Billing Schedule.status` unchanged (still "Sent")

#### FIN-NEG-002: Payment on Cancelled billing rejected

**Type:** edge | **Origin:** Plan v2.1 Task 3
**Pre-req:** BEI Billing Schedule with status="Cancelled"

```
POST /api/method/hrms.api.procurement.apply_franchise_payment
Payload: {
  "billing_name": "<cancelled_billing>",
  "amount_paid": 10000,
  "payment_date": "2026-02-12",
  "payment_reference": "BT-CANCEL"
}
```

**Assert:**
- Response: Error containing "Cannot apply payment to billing with status"
- DB: No changes to billing document

#### FIN-NEG-003: Duplicate billing generation skipped

**Type:** edge | **Origin:** Plan v2.1 Task 4
**Pre-req:** BEI Billing Schedule already exists for store+period with status != Cancelled

```
POST /api/method/hrms.api.procurement.generate_monthly_billing
Payload: { "billing_period": "2026-02", "store": "<store_with_existing_billing>" }
```

**Assert:**
- Response: `generated=0`, `skipped=1`
- DB: No new BEI Billing Schedule created

#### FIN-NEG-004: Billing for store with no POS data skipped

**Type:** edge | **Origin:** Plan v2.1 Task 4
**Pre-req:** Store exists in BEI Store Type but has NO submitted BEI Store Closing Reports for the period

```
POST /api/method/hrms.api.procurement.generate_monthly_billing
Payload: { "billing_period": "2025-01", "store": "<store_with_no_data>" }
```

**Assert:**
- Response: `generated=0`, `skipped=1`
- Frappe Error Log: Contains "No POS data for" message

#### FIN-NEG-005: GL mapping for unknown rfp_type logs warning

**Type:** edge | **Origin:** Plan v2.1 Task 1
**Pre-req:** BEI Payment Request with rfp_type="Unknown Type"

```
Trigger: Save/validate the BEI Payment Request
```

**Assert:**
- DB: `BEI Payment Request.account_code` is empty (not assigned)
- No crash — validation completes successfully

#### FIN-NEG-006: Chat notification fails during AR generation

**Type:** edge | **Origin:** R2 audit addition
**Pre-req:** Simulate Chat API failure (network error or invalid credentials)

```
POST /api/method/hrms.api.procurement.generate_acknowledgement_receipt
Payload: { "billing_name": "<billing_name>" }
```

**Assert:**
- Response: `ar_name` exists (AR created DESPITE chat failure)
- Frappe Error Log: Contains "AR Chat Notification Error"
- AR document exists in DB with correct fields

### RBAC

#### FIN-RBAC-001: Store Staff CANNOT apply payment

**Type:** rbac | **Origin:** Plan v2.1

```
POST /api/method/hrms.api.procurement.apply_franchise_payment
Session: test.staff@bebang.ph (Store OIC — no Accounts role)
Payload: {
  "billing_name": "<billing_name>",
  "amount_paid": 10000,
  "payment_date": "2026-02-12",
  "payment_reference": "BT-UNAUTH"
}
```

**Assert:**
- Response: PermissionError ("Insufficient permissions")
- DB: No changes to billing document

#### FIN-RBAC-002: Accounts User CAN apply payment

**Type:** rbac | **Origin:** Plan v2.1

```
POST /api/method/hrms.api.procurement.apply_franchise_payment
Session: test.hr@bebang.ph (has Accounts Manager or Accounts User role)
Payload: {
  "billing_name": "<billing_name>",
  "amount_paid": 10000,
  "payment_date": "2026-02-12",
  "payment_reference": "BT-AUTH"
}
```

**Assert:**
- Response: `success=True`
- DB: Payment applied, status updated

---

## Biometric Monitoring Module (14 scenarios)

### BIO-001: Dashboard Summary (Happy Path)
- **Type:** happy
- **Role:** test.hr@bebang.ph (HR Officer)
- **Call:** `GET /api/method/hrms.api.biometric_monitoring.get_dashboard_summary`
- **Payload:** None (GET request)
- **Assert:**
  - Response: `ok == true`
  - Data contains: `total_employees` (int > 0), `punching_employees` (int), `enrollment_pct` (float 0-100), `devices_online` (int), `devices_total` (int), `issues_count` (int >= 0), `days_to_deadline` (int), `last_refreshed` (ISO datetime string)
  - `enrollment_pct == round(punching_employees / total_employees * 100, 1)`
  - `devices_total == 46`

### BIO-002: Device Status List (Happy Path)
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Call:** `GET /api/method/hrms.api.biometric_monitoring.get_device_status`
- **Payload:** None
- **Assert:**
  - Response: `ok == true`, `devices` is array with length == 46
  - Each device has: `sn` (string), `store` (string), `status` (one of: "online", "recent", "offline", "never_connected"), `last_activity` (ISO datetime or null), `total_punches` (int >= 0), `employee_count` (int >= 0)
  - At least 40 devices have `status == "online"` (realistic baseline)

### BIO-003: Not Punching >48h List
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Call:** `GET /api/method/hrms.api.biometric_monitoring.get_not_punching`
- **Payload:** `{"hours": 48}`
- **Assert:**
  - Response: `ok == true`, `employees` is array
  - Each employee has: `employee_id` (string), `employee_name` (string), `bio_id` (string matching `^9\d{6}$`), `store` (string), `last_punch` (ISO datetime or null), `hours_since_punch` (float > 48), `supervisor` (string or null)
  - No employee appears with `hours_since_punch < 48`

### BIO-004: Not Punching Custom Hours Parameter
- **Type:** edge
- **Role:** test.hr@bebang.ph
- **Call:** `GET /api/method/hrms.api.biometric_monitoring.get_not_punching`
- **Payload:** `{"hours": 24}`
- **Assert:**
  - Response: `ok == true`, `employees` is array
  - Every employee in list has `hours_since_punch > 24`
  - Result set is >= the 48h result (more employees appear at lower threshold)

### BIO-005: Wrong Device Detection
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Call:** `GET /api/method/hrms.api.biometric_monitoring.get_wrong_device`
- **Payload:** None
- **Assert:**
  - Response: `ok == true`, `employees` is array
  - Each entry has: `employee_id`, `employee_name`, `bio_id`, `assigned_store`, `punching_store`, `assigned_device_sn`, `punching_device_sn`, `punch_count_wrong_device` (int > 0)
  - `assigned_store != punching_store` for every entry

### BIO-006: Ghost Punchers (Unknown Bio IDs)
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Call:** `GET /api/method/hrms.api.biometric_monitoring.get_ghost_punchers`
- **Payload:** None
- **Assert:**
  - Response: `ok == true`, `unknowns` is array
  - Each entry has: `bio_id` (string), `device_sn` (string), `store` (string), `punch_count` (int > 0), `last_punch` (ISO datetime)
  - No `bio_id` in the list exists in Employee Master (`data/_FINAL/EMPLOYEE_MASTER.csv` `new_attendance_device_id` column)

### BIO-007: Store Leaderboard
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Call:** `GET /api/method/hrms.api.biometric_monitoring.get_store_leaderboard`
- **Payload:** None
- **Assert:**
  - Response: `ok == true`, `stores` is array sorted by `compliance_pct` descending
  - Each store has: `store_name` (string), `total_employees` (int > 0), `punching_employees` (int), `compliance_pct` (float 0-100), `rank` (int)
  - Sum of all `total_employees` across stores == `total_employees` from BIO-001

### BIO-008: Not Enrolled (Never Punched)
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Call:** `GET /api/method/hrms.api.biometric_monitoring.get_not_enrolled`
- **Payload:** None
- **Assert:**
  - Response: `ok == true`, `employees` is array
  - Each entry has: `employee_id`, `employee_name`, `bio_id`, `store`, `designation`, `supervisor`
  - None of these employees appear in `adms_attlog_raw` since Feb 3

### BIO-009: RBAC — Store Staff DENIED Access
- **Type:** rbac
- **Role:** test.staff@bebang.ph (Store OIC — NOT HR/System Manager)
- **Call:** `GET /api/method/hrms.api.biometric_monitoring.get_dashboard_summary`
- **Payload:** None
- **Assert:**
  - Response: HTTP 403 or `frappe.PermissionError`
  - Error message contains "do not have access" or "Insufficient Permissions"
  - No biometric data returned

### BIO-010: RBAC — Crew DENIED Access
- **Type:** rbac
- **Role:** test.crew1@bebang.ph (Crew — lowest role)
- **Call:** `GET /api/method/hrms.api.biometric_monitoring.get_device_status`
- **Payload:** None
- **Assert:**
  - Response: HTTP 403 or `frappe.PermissionError`
  - No device data returned

### BIO-011: Manual Cache Refresh
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Call:** `POST /api/method/hrms.api.biometric_monitoring.refresh_biometric_cache`
- **Payload:** None
- **Assert:**
  - Response: `ok == true`, `refreshed == true`, `duration_seconds` (float > 0)
  - Subsequent `get_dashboard_summary` call returns `last_refreshed` timestamp >= the refresh time
  - Response time < 120s (SSM queries + processing)

### BIO-012: Cache Refresh — Non-Admin DENIED
- **Type:** rbac
- **Role:** test.hr@bebang.ph (HR Officer — can view but NOT refresh)
- **Call:** `POST /api/method/hrms.api.biometric_monitoring.refresh_biometric_cache`
- **Payload:** None
- **Assert:**
  - Response: HTTP 403 or `frappe.PermissionError`
  - Cache NOT refreshed (only System Manager / Administrator can refresh)
- **Note:** If HR Officer should be able to refresh, change this to a happy-path test. Decision point for user.

### BIO-013: SSM Failure Graceful Degradation
- **Type:** edge
- **Role:** test.hr@bebang.ph
- **Precondition:** Cache populated from previous successful refresh
- **Call:** `GET /api/method/hrms.api.biometric_monitoring.get_dashboard_summary`
- **Simulate:** (Cannot directly simulate SSM failure in L3 test — verify at code level)
- **Assert:**
  - When cache exists, dashboard returns stale data with `stale == true` flag
  - `last_refreshed` timestamp is older than 6 hours
  - No error thrown to user — graceful degradation

### BIO-014: Dashboard Response Performance
- **Type:** edge
- **Role:** test.hr@bebang.ph
- **Call:** `GET /api/method/hrms.api.biometric_monitoring.get_dashboard_summary`
- **Assert:**
  - Response time < 2000ms (reads from cache, never hits SSM)
  - Response body size < 50KB (summary data only, not raw punch logs)

---

## Billing Module (17 scenarios)

**Added:** 2026-02-14 | **Origin:** Billing Redesign Plan v1.6 audit (AUDIT-6)

**Context:** BEI has 3 billing streams:
- **Stream A:** Monthly franchise fees (royalty, management, marketing, eCommerce) — triggered monthly, pulls POS data from Supabase
- **Stream B:** Delivery billing (delivery_fee + logistics_fee + goods_value + handling_fee) — triggered on `confirm_delivery()`, real-time per stop
- **Stream C:** Other charges (R&M, PM, payroll, taxes) — monthly, deferred

**Key Business Rules:**
- JV stores: NO royalty, NO management, YES marketing (5%), YES eCommerce (4%)
- Full Franchise: ALL fees, emailed billings, 8% handling markup on delivery
- Managed Franchise: ALL fees, internal only, 8% handling markup on delivery
- eCommerce fee = `website_sales × 4%` (excludes Foodpanda/Grab)
- Delivery rate per store, per cargo type (Dry/Frozen), set in BEI Delivery Rate DocType
- Billing BLOCKED if no active rate for store+cargo_type
- Bidirectional rate approval (Finance ↔ Supply Chain)

**Test Data Requirements:**
- Test stores: TEST-STORE-BGC (Full Franchise), TEST-STORE-MEGAMALL (JV), TEST-STORE-EASTWOOD (Managed Franchise)
- Delivery rates: Dry = ₱1,500 delivery + ₱800 logistics, Frozen = ₱2,500 delivery + ₱1,200 logistics
- Store orders: At least 3 items per order, goods_value = ₱15,000
- Photos: Use `PHOTO_DATA_URL` fixture (150KB+ PNG) for any attachment fields

### BILL-001: Delivery Billing — JV Store (No Markup)
- **Type:** happy
- **Role:** test.staff@bebang.ph (Store OIC or Supply Chain role)
- **Precondition:**
  - BEI Distribution Trip exists with cargo_type="Dry Goods", status="In Transit"
  - BEI Trip Stop exists for TEST-STORE-MEGAMALL (JV store) with store_order containing goods_value=15000
  - Active BEI Delivery Rate for TEST-STORE-MEGAMALL + Dry Goods (delivery_fee=1500, logistics_fee=800)
- **Call:** `POST hrms.api.dispatch.confirm_delivery`
- **Payload:**
  ```json
  {
    "stop_id": "<trip_stop_name>",
    "delivered_by": "TEST-DRIVER-001",
    "photos": "[{\"photo\": \"<PHOTO_DATA_URL>\", \"caption\": \"Delivery confirmation photo\"}]"
  }
  ```
- **Assert:**
  - Response: `ok == true`, `message` contains "Delivery confirmed"
  - DB: `BEI Trip Stop.status == "Delivered"`
  - DB: `BEI Billing Schedule` created with `billing_type == "Delivery"`, `store == "TEST-STORE-MEGAMALL"`
  - DB: `BEI Billing Schedule.delivery_fee == 1500`
  - DB: `BEI Billing Schedule.logistics_fee == 800`
  - DB: `BEI Billing Schedule.goods_value == 15000`
  - DB: `BEI Billing Schedule.handling_fee == 0` (JV stores get NO markup)
  - DB: `BEI Billing Schedule.total_amount == 17300` (1500 + 800 + 15000 + 0)

### BILL-002: Delivery Billing — Full Franchise (8% Markup)
- **Type:** happy
- **Role:** test.staff@bebang.ph
- **Precondition:**
  - BEI Distribution Trip with cargo_type="Dry Goods"
  - BEI Trip Stop for TEST-STORE-BGC (Full Franchise) with goods_value=15000
  - Active BEI Delivery Rate for TEST-STORE-BGC + Dry Goods (delivery_fee=1500, logistics_fee=800)
- **Call:** `POST hrms.api.dispatch.confirm_delivery`
- **Payload:**
  ```json
  {
    "stop_id": "<trip_stop_name>",
    "delivered_by": "TEST-DRIVER-001",
    "photos": "[{\"photo\": \"<PHOTO_DATA_URL>\", \"caption\": \"Delivery confirmation\"}]"
  }
  ```
- **Assert:**
  - DB: `BEI Billing Schedule.delivery_fee == 1500`
  - DB: `BEI Billing Schedule.logistics_fee == 800`
  - DB: `BEI Billing Schedule.goods_value == 15000`
  - DB: `BEI Billing Schedule.handling_fee == 1200` (15000 × 0.08)
  - DB: `BEI Billing Schedule.total_amount == 18500` (1500 + 800 + 15000 + 1200)
  - DB: Billing record has `email_sent == 1` (Full Franchise gets emailed)

### BILL-003: Monthly Billing — JV Store (Marketing + eCommerce Only)
- **Type:** happy
- **Role:** test.hr@bebang.ph (Accounts Manager)
- **Precondition:**
  - BEI Store Type for TEST-STORE-MEGAMALL with `store_type == "Joint Venture"`
  - POS data in Supabase for TEST-STORE-MEGAMALL with `gross_sales = 500000`, `website_sales = 100000`, `online_sales = 150000` (includes Foodpanda/Grab)
- **Call:** `POST hrms.api.procurement.generate_monthly_billing`
- **Payload:**
  ```json
  {
    "billing_period": "2026-02",
    "store": "TEST-STORE-MEGAMALL"
  }
  ```
- **Assert:**
  - Response: `generated == 1`, `skipped == 0`, `errors == []`
  - DB: `BEI Billing Schedule.billing_type == "Monthly Fees"`
  - DB: `BEI Billing Schedule.royalty_fee == 0` (JV stores exempt)
  - DB: `BEI Billing Schedule.management_fee == 0` (JV stores exempt)
  - DB: `BEI Billing Schedule.marketing_fee == 25000` (500000 × 0.05)
  - DB: `BEI Billing Schedule.ecommerce_fee == 4000` (100000 × 0.04, uses website_sales NOT online_sales)
  - DB: `BEI Billing Schedule.total_amount == 29000` (0 + 0 + 25000 + 4000)

### BILL-004: Monthly Billing — Full Franchise (All Fees)
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Precondition:**
  - BEI Store Type for TEST-STORE-BGC with `store_type == "Full Franchise"`
  - POS data: `gross_sales = 1000000`, `website_sales = 200000`
- **Call:** `POST hrms.api.procurement.generate_monthly_billing`
- **Payload:**
  ```json
  {
    "billing_period": "2026-02",
    "store": "TEST-STORE-BGC"
  }
  ```
- **Assert:**
  - DB: `BEI Billing Schedule.royalty_fee == 120000` (1000000 × 0.12)
  - DB: `BEI Billing Schedule.management_fee == 30000` (1000000 × 0.03)
  - DB: `BEI Billing Schedule.marketing_fee == 50000` (1000000 × 0.05)
  - DB: `BEI Billing Schedule.ecommerce_fee == 8000` (200000 × 0.04)
  - DB: `BEI Billing Schedule.total_amount == 208000` (120000 + 30000 + 50000 + 8000)

### BILL-005: Delivery Billing — No Active Rate (Error)
- **Type:** edge
- **Role:** test.staff@bebang.ph
- **Precondition:**
  - BEI Distribution Trip with cargo_type="Frozen Goods"
  - BEI Trip Stop for TEST-STORE-BGC
  - NO active BEI Delivery Rate for TEST-STORE-BGC + Frozen Goods (status is Draft or Expired)
- **Call:** `POST hrms.api.dispatch.confirm_delivery`
- **Payload:**
  ```json
  {
    "stop_id": "<trip_stop_name>",
    "delivered_by": "TEST-DRIVER-001",
    "photos": "[{\"photo\": \"<PHOTO_DATA_URL>\", \"caption\": \"Delivery\"}]"
  }
  ```
- **Assert:**
  - Response: `ok == false`, error message contains "No active delivery rate found"
  - DB: `BEI Trip Stop.status == "In Transit"` (delivery NOT confirmed)
  - DB: NO `BEI Billing Schedule` created for this stop
  - Frappe Error Log: Contains "Delivery rate missing for store + cargo type"

### BILL-006: eCommerce Fee Uses website_sales Only (Edge)
- **Type:** edge | **Origin:** Billing Redesign v1.6 specification clarification
- **Role:** test.hr@bebang.ph
- **Precondition:**
  - POS data: `gross_sales = 300000`, `website_sales = 50000` (website only), `online_sales = 150000` (includes Foodpanda/Grab = 100000 + website 50000)
- **Call:** `POST hrms.api.procurement.generate_monthly_billing`
- **Payload:**
  ```json
  {
    "billing_period": "2026-02",
    "store": "TEST-STORE-BGC"
  }
  ```
- **Assert:**
  - DB: `BEI Billing Schedule.ecommerce_fee == 2000` (50000 × 0.04)
  - DB: eCommerce fee does NOT use `online_sales` (which would be 150000 × 0.04 = 6000 — WRONG)
  - Verify calculation excludes Foodpanda/Grab (100000 should NOT be in ecommerce_fee base)

### BILL-007: eCommerce Fee Formula Regression Test
- **Type:** regression | **Origin:** AUDIT-6 (Plan v1.6 audit found formula typo)
- **Role:** test.hr@bebang.ph
- **Precondition:**
  - POS data: `website_sales = 100000`
- **Call:** `POST hrms.api.procurement.generate_monthly_billing`
- **Payload:**
  ```json
  {
    "billing_period": "2026-02",
    "store": "TEST-STORE-BGC"
  }
  ```
- **Assert:**
  - DB: `BEI Billing Schedule.ecommerce_fee == 4000` (100000 × 0.04, NOT 100000 × 0.05)
  - Verify formula is `website_sales × 0.04` not accidentally using 5% from marketing fee

### BILL-008: Rate Management — Finance Creates, Supply Chain Approves
- **Type:** happy
- **Role:** test.hr@bebang.ph (Finance role)
- **Step 1:** `POST hrms.api.billing.set_delivery_rate`
- **Payload:**
  ```json
  {
    "store": "TEST-STORE-BGC",
    "cargo_type": "Dry Goods",
    "delivery_fee": 1500,
    "logistics_fee": 800,
    "effective_from": "2026-02-15"
  }
  ```
- **Assert Step 1:**
  - Response: `ok == true`, `rate_name` returned
  - DB: `BEI Delivery Rate.status == "Draft"`, `created_by == "test.hr@bebang.ph"`, `approver == null`
- **Step 2:** Finance submits for review: `POST hrms.api.billing.submit_rate_for_review` with `{"rate_id": "<rate_name>"}`
- **Assert Step 2:** DB: `BEI Delivery Rate.status == "Pending Review"`, `submitted_for_review == 1`
- **Step 3:** test.warehouse@bebang.ph (Supply Chain) calls `POST hrms.api.billing.approve_rate` with `{"rate_id": "<rate_name>"}`
- **Assert Step 3:**
  - DB: `BEI Delivery Rate.status == "Active"`
  - DB: `approved_by == "test.warehouse@bebang.ph"`
  - DB: Previous active rate for same store+cargo_type now has `status == "Expired"`

### BILL-009: Rate Management — Supply Chain Creates, Finance Approves
- **Type:** happy
- **Role:** test.warehouse@bebang.ph (Supply Chain role)
- **Step 1:** Create rate via `POST hrms.api.billing.set_delivery_rate`
- **Payload:**
  ```json
  {
    "store": "TEST-STORE-MEGAMALL",
    "cargo_type": "Frozen Goods",
    "delivery_fee": 2500,
    "logistics_fee": 1200,
    "effective_from": "2026-02-20"
  }
  ```
- **Step 2:** Submit for review: `POST hrms.api.billing.submit_rate_for_review`
- **Step 3:** test.hr@bebang.ph (Finance) approves: `POST hrms.api.billing.approve_rate`
- **Assert:**
  - DB: Final status == "Active"
  - DB: `created_by == "test.warehouse@bebang.ph"`, `approved_by == "test.hr@bebang.ph"`
  - Old rate for TEST-STORE-MEGAMALL + Frozen Goods has `status == "Expired"`

### BILL-010: Rate Management — Cannot Approve Own Rate (Edge)
- **Type:** edge
- **Role:** test.hr@bebang.ph
- **Precondition:** test.hr creates a rate, submits for review (status="Pending Review")
- **Call:** `POST hrms.api.billing.approve_rate`
- **Payload:** `{"rate_id": "<rate_name>"}`
- **Assert:**
  - Response: `ok == false`, error contains "Cannot approve your own rate" or "Must be approved by other department"
  - DB: `BEI Delivery Rate.status == "Pending Review"` (unchanged)

### BILL-011: RBAC — Crew Cannot Access Rate Management
- **Type:** rbac
- **Role:** test.crew1@bebang.ph
- **Call:** `GET hrms.api.billing.get_delivery_rates`
- **Assert:**
  - Response: HTTP 403 or `frappe.PermissionError`
  - Error message contains "Insufficient Permissions" or "do not have access"

### BILL-012: SOA Generation — Consolidate Multiple Billings
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Precondition:**
  - TEST-STORE-BGC (Full Franchise) has:
    - 3 delivery billings (from BILL-002) totaling ₱55,500
    - 1 monthly billing (from BILL-004) = ₱208,000
  - All billings in status "Sent" or "Partially Paid"
- **Call:** `POST hrms.api.billing.generate_soa`
- **Payload:**
  ```json
  {
    "store": "TEST-STORE-BGC",
    "billing_period": "2026-02"
  }
  ```
- **Assert:**
  - Response: `ok == true`, `soa_name` returned
  - DB: `BEI Statement of Account.total_billings == 4`
  - DB: `BEI Statement of Account.total_amount == 263500` (55500 + 208000)
  - DB: SOA Child Table contains all 4 billing references
  - DB: SOA has `email_sent == 1` (Full Franchise gets emailed)

### BILL-013: Delivery Billing — Frozen Cargo Uses Frozen Rates
- **Type:** edge
- **Role:** test.staff@bebang.ph
- **Precondition:**
  - BEI Distribution Trip with cargo_type="Frozen Goods"
  - Active BEI Delivery Rate for TEST-STORE-BGC + Frozen Goods (delivery_fee=2500, logistics_fee=1200)
- **Call:** `POST hrms.api.dispatch.confirm_delivery`
- **Payload:**
  ```json
  {
    "stop_id": "<trip_stop_frozen>",
    "delivered_by": "TEST-DRIVER-001",
    "photos": "[{\"photo\": \"<PHOTO_DATA_URL>\", \"caption\": \"Frozen delivery\"}]"
  }
  ```
- **Assert:**
  - DB: `BEI Billing Schedule.delivery_fee == 2500` (NOT 1500 from Dry Goods rate)
  - DB: `BEI Billing Schedule.logistics_fee == 1200` (NOT 800 from Dry Goods rate)
  - Verify rate lookup uses BOTH store AND cargo_type

### BILL-014: Concurrent Delivery Confirmations — No Duplicate Billing
- **Type:** adversarial
- **Role:** test.staff@bebang.ph (simulated concurrent API calls)
- **Precondition:**
  - BEI Distribution Trip with 2 stops for same store (TEST-STORE-BGC)
- **Simulate:** Call `confirm_delivery` for BOTH stops within 500ms (use threading or async)
- **Assert:**
  - DB: EXACTLY 2 `BEI Billing Schedule` records created (one per stop)
  - DB: NO duplicate billings with identical `billing_reference` (stop_id must be unique)
  - Verify atomicity: each stop gets exactly ONE billing, even under race condition

### BILL-015: Monthly Billing — Zero Gross Sales (Edge)
- **Type:** edge
- **Role:** test.hr@bebang.ph
- **Precondition:**
  - POS data: `gross_sales = 0`, `website_sales = 0` (store closed for renovation)
- **Call:** `POST hrms.api.procurement.generate_monthly_billing`
- **Payload:**
  ```json
  {
    "billing_period": "2026-02",
    "store": "TEST-STORE-BGC"
  }
  ```
- **Assert (Option A — No billing created):**
  - Response: `generated == 0`, `skipped == 1`, message contains "No sales data"
  - DB: NO `BEI Billing Schedule` created
- **Assert (Option B — Billing with ₱0 fees):**
  - Response: `generated == 1`
  - DB: `BEI Billing Schedule.total_amount == 0`, all fee fields == 0
  - (Implementation decision: confirm with stakeholder)

### BILL-016: Managed Franchise — Markup Applied, No Email
- **Type:** regression | **Origin:** AUDIT-6 (Managed Franchise business rule)
- **Role:** test.staff@bebang.ph
- **Precondition:**
  - BEI Store Type for TEST-STORE-EASTWOOD with `store_type == "Managed Franchise"`
  - Delivery with goods_value=15000
- **Call:** `POST hrms.api.dispatch.confirm_delivery`
- **Payload:**
  ```json
  {
    "stop_id": "<managed_franchise_stop>",
    "delivered_by": "TEST-DRIVER-001",
    "photos": "[{\"photo\": \"<PHOTO_DATA_URL>\", \"caption\": \"Delivery\"}]"
  }
  ```
- **Assert:**
  - DB: `BEI Billing Schedule.handling_fee == 1200` (8% markup applied)
  - DB: `BEI Billing Schedule.email_sent == 0` (Managed Franchise is internal, no email)
  - DB: `total_amount == 18500` (same as Full Franchise calculation)

### BILL-017: Rate with Future effective_from — Not Used Today
- **Type:** edge
- **Role:** test.staff@bebang.ph
- **Precondition:**
  - BEI Delivery Rate for TEST-STORE-BGC + Dry Goods with `effective_from = "2026-03-01"` (future), `status = "Active"`
  - OLD rate with `effective_from = "2026-01-01"`, `status = "Active"`
- **Call:** `POST hrms.api.dispatch.confirm_delivery` (today is 2026-02-14)
- **Payload:**
  ```json
  {
    "stop_id": "<trip_stop_name>",
    "delivered_by": "TEST-DRIVER-001",
    "photos": "[{\"photo\": \"<PHOTO_DATA_URL>\", \"caption\": \"Delivery\"}]"
  }
  ```
- **Assert:**
  - DB: Billing uses OLD rate (effective_from=2026-01-01), NOT the future rate
  - DB: Rate selection query filters `effective_from <= today()`
  - Verify future rates don't affect current billings

---

## SCM & Logistics Module (14 scenarios)

### SCM-001: Store Places Order with Suggested Qty (No Edits) → Auto-Approve
- **Type:** happy
- **Origin:** Plan Phase 1B (auto-approval for no deviations)
- **Role:** test.staff@bebang.ph (Store OIC)
- **Call:** `POST hrms.api.store_orders.submit_store_order`
- **Payload:**
  ```json
  {
    "store": "TEST-STORE-BGC - BEI",
    "delivery_date": "2026-02-18",
    "items": [
      {
        "item_code": "SKU-001",
        "item_name": "Cooking Oil 1L",
        "suggested_qty": 10,
        "qty": 10
      },
      {
        "item_code": "SKU-002",
        "item_name": "Sugar 1kg",
        "suggested_qty": 5,
        "qty": 5
      },
      {
        "item_code": "SKU-003",
        "item_name": "Rice 25kg",
        "suggested_qty": 8,
        "qty": 8
      }
    ]
  }
  ```
- **Assert:**
  - Response: `ok == true`, `status == "Approved"`
  - DB verify: `status == "Approved"`, all items `deviation_pct == 0`, `approved_by IS NULL` (auto-approved, no manual approval needed)

### SCM-002: Store Increases Qty by 50% → Flags for Area Supervisor Approval
- **Type:** edge
- **Origin:** Plan Phase 1B deviation approval workflow
- **Role:** test.staff@bebang.ph
- **Call:** `POST hrms.api.store_orders.submit_store_order`
- **Payload:**
  ```json
  {
    "store": "TEST-STORE-BGC - BEI",
    "delivery_date": "2026-02-18",
    "items": [
      {
        "item_code": "SKU-001",
        "item_name": "Cooking Oil 1L",
        "suggested_qty": 10,
        "qty": 15
      }
    ]
  }
  ```
- **Assert:**
  - Response: `ok == true`, `status == "Pending Approval"`
  - DB verify: `status == "Pending Approval"`, item `deviation_pct == 50`, `workflow_state == "Area Supervisor Review"`

### SCM-003: Store Orders OOS Item → Blocked with Error Message
- **Type:** edge
- **Origin:** Plan Phase 1B inventory check
- **Role:** test.staff@bebang.ph
- **Precondition:**
  - Item SKU-999 exists in system with `stock_available = 0` in Central Warehouse
- **Call:** `POST hrms.api.store_orders.submit_store_order`
- **Payload:**
  ```json
  {
    "store": "TEST-STORE-BGC - BEI",
    "delivery_date": "2026-02-18",
    "items": [
      {
        "item_code": "SKU-999",
        "item_name": "Out of Stock Item",
        "suggested_qty": 10,
        "qty": 10
      }
    ]
  }
  ```
- **Assert:**
  - Response: `ok == false`, `message` contains "out of stock" or "insufficient stock"
  - DB verify: No order created

### SCM-004: Order Submitted After Cutoff Time → Rejected
- **Type:** edge
- **Origin:** Plan Phase 1B schedule gate
- **Role:** test.staff@bebang.ph
- **Precondition:**
  - Current time is after 12:00 PM cutoff for next-day delivery
- **Call:** `POST hrms.api.store_orders.submit_store_order`
- **Payload:**
  ```json
  {
    "store": "TEST-STORE-BGC - BEI",
    "delivery_date": "2026-02-17",
    "items": [
      {
        "item_code": "SKU-001",
        "item_name": "Cooking Oil 1L",
        "suggested_qty": 10,
        "qty": 10
      }
    ]
  }
  ```
- **Assert:**
  - Response: `ok == false`, `message` contains "cutoff" or "too late"
  - DB verify: No order created

### SCM-005: Emergency Order (Bypass Schedule) → Requires Area Supervisor Approval
- **Type:** edge
- **Origin:** GAP-1 (emergency order exception handling)
- **Role:** test.staff@bebang.ph
- **Precondition:**
  - Today is a non-delivery day for TEST-STORE-BGC
- **Call:** `POST hrms.api.store_orders.submit_store_order`
- **Payload:**
  ```json
  {
    "store": "TEST-STORE-BGC - BEI",
    "delivery_date": "2026-02-17",
    "is_emergency": true,
    "emergency_reason": "Critical shortage of cooking oil due to unexpected weekend rush. Store will run out by tomorrow morning.",
    "items": [
      {
        "item_code": "SKU-001",
        "item_name": "Cooking Oil 1L",
        "suggested_qty": 10,
        "qty": 20
      }
    ]
  }
  ```
- **Assert:**
  - Response: `ok == true`, `status == "Pending Approval"`
  - DB verify: `status == "Pending Approval"`, `is_emergency == 1`, `workflow_state == "Area Supervisor Review"`

### SCM-006: Driver Confirms Departure → ETA Calculated for All Stops
- **Type:** happy
- **Origin:** Plan Phase 1A (route optimization with ETA calculation)
- **Role:** test.warehouse@bebang.ph
- **Precondition:**
  - Delivery Trip exists with 5 stops, status = "Ready for Dispatch"
  - Trip stops: BGC → Makati → Ortigas → Pasig → Quezon City
- **Call:** `POST hrms.api.dispatch.confirm_departure`
- **Payload:**
  ```json
  {
    "trip_id": "<trip_name>",
    "driver": "TEST-DRIVER-001",
    "vehicle_plate": "ABC-1234",
    "departure_time": "2026-02-17 06:00:00"
  }
  ```
- **Assert:**
  - Response: `ok == true`, `status == "In Transit"`
  - DB verify: Each stop has `eta_minutes` calculated (stop_order × 20 min), stop 1 = 20, stop 2 = 40, stop 3 = 60, stop 4 = 80, stop 5 = 100
  - DB verify: Trip `status == "In Transit"`, `actual_departure_time` is set

### SCM-007: Stop N Delivered → Stop N+1 Store Gets GChat Notification
- **Type:** happy
- **Origin:** Plan Phase 1A GChat notification for next stop
- **Role:** test.warehouse@bebang.ph
- **Precondition:**
  - Trip "In Transit" with 5 stops, currently on stop 2
  - Stop 3 is TEST-STORE-MAKATI
- **Call:** `POST hrms.api.dispatch.confirm_delivery`
- **Payload:**
  ```json
  {
    "stop_id": "<trip_stop_2_name>",
    "delivered_by": "TEST-DRIVER-001",
    "photos": "[{\"photo\": \"<PHOTO_DATA_URL>\", \"caption\": \"Delivery to BGC\"}]"
  }
  ```
- **Assert:**
  - Response: `ok == true`
  - DB verify: Stop 2 `status == "Delivered"`, `delivered_at` is set
  - GChat API called for TEST-STORE-MAKATI staff, message contains "1 stop away" or "ETA" or "arriving soon"
  - **Note:** GChat failure MUST NOT block delivery confirmation (try/except, log error)

### SCM-008: Store Closed Exception → Trip Stays "In Transit" Until All Stops Processed
- **Type:** edge
- **Origin:** Plan Phase 1A exception handling (store closed, refused delivery, address issues)
- **Role:** test.warehouse@bebang.ph
- **Precondition:**
  - Trip "In Transit" with 5 stops, currently on stop 3
  - Stop 4 and 5 still pending
- **Call:** `POST hrms.api.dispatch.report_exception`
- **Payload:**
  ```json
  {
    "stop_id": "<trip_stop_3_name>",
    "exception_type": "Store Closed",
    "notes": "Store closed for emergency repairs. Staff confirmed via phone they cannot receive delivery today.",
    "photos": "[{\"photo\": \"<PHOTO_DATA_URL>\", \"caption\": \"Closed store gate\"}]"
  }
  ```
- **Assert:**
  - Response: `ok == true`
  - DB verify: Stop 3 `status == "Store Closed"` or "Exception", `exception_type == "Store Closed"`
  - DB verify: Trip `status == "In Transit"` (NOT "Completed"), stops 4 and 5 still `status == "Pending"`
  - DB verify: Exception logged, photo attached

### SCM-009: Delivery Confirmed → Stock Entry Created (Company-Owned Store)
- **Type:** happy
- **Origin:** BLOCKER-1 resolution (Stock Entry, NOT Sales Invoice for company-owned stores)
- **Role:** test.warehouse@bebang.ph
- **Precondition:**
  - Trip "In Transit" with stop to TEST-STORE-BGC (company-owned)
  - DR has 3 items with quantities
- **Call:** `POST hrms.api.dispatch.confirm_delivery`
- **Payload:**
  ```json
  {
    "stop_id": "<company_owned_stop>",
    "delivered_by": "TEST-DRIVER-001",
    "photos": "[{\"photo\": \"<PHOTO_DATA_URL>\", \"caption\": \"Delivery confirmed\"}]"
  }
  ```
- **Assert:**
  - Response: `ok == true`
  - DB verify: **Stock Entry** (Material Transfer) created, NOT Sales Invoice
  - DB verify: Stock Entry debits "BGC - Warehouse Inventory", credits "Central Warehouse - BEI"
  - DB verify: NO revenue recognition (no GL Entry with Income Account)
  - DB verify: DR `status == "Delivered"`, linked to Stock Entry

### SCM-010: Area Supervisor Approves Deviation → Order Status Changes
- **Type:** happy
- **Origin:** Plan Phase 1B approval workflow
- **Role:** test.area@bebang.ph (Area Supervisor)
- **Precondition:**
  - Store order from SCM-002 exists with `status == "Pending Approval"`, deviation_pct = 50
- **Call:** `POST hrms.api.store_orders.approve_order_deviation`
- **Payload:**
  ```json
  {
    "order_id": "<order_name_from_scm_002>",
    "approval_notes": "Approved due to upcoming long weekend and anticipated demand surge."
  }
  ```
- **Assert:**
  - Response: `ok == true`, `status == "Approved"`
  - DB verify: `status == "Approved"`, `approved_by == "test.area@bebang.ph"`, `approved_at` is set, `approval_notes` saved

### SCM-011: 3PL Billing Comparison → Flags Discrepancies with EWT
- **Type:** happy
- **Origin:** Plan Phase 4B (3PL billing validation) + BLOCKER-2 (EWT calculation)
- **Role:** test.warehouse@bebang.ph
- **Precondition:**
  - 3 delivery trips completed:
    - Trip A: actual delivery value = 5000 PHP
    - Trip B: actual delivery value = 8000 PHP
    - Trip C: actual delivery value = 6000 PHP
- **Call:** `POST hrms.api.dispatch.validate_3pl_billing`
- **Payload:**
  ```json
  {
    "billing_period": "2026-02-01 to 2026-02-15",
    "3pl_invoices": [
      {"trip_id": "TRIP-A", "billed_amount": 5000, "invoice_ref": "3PL-001"},
      {"trip_id": "TRIP-B", "billed_amount": 8500, "invoice_ref": "3PL-002"},
      {"trip_id": "TRIP-C", "billed_amount": 5800, "invoice_ref": "3PL-003"}
    ]
  }
  ```
- **Assert:**
  - Response: `ok == true`, `discrepancies.length == 2` (Trip B overcharged by 500, Trip C undercharged by 200)
  - DB verify: Discrepancy report created with 2 flagged invoices
  - DB verify: EWT 2% calculated on gross billing (total = 19300 PHP, EWT = 386 PHP)
  - DB verify: Form 2307 reference generated for EWT withholding

### SCM-012: Ian Approves Order with Qty Adjustment → DR Auto-Generated
- **Type:** happy
- **Origin:** Plan Phase 1B Ian review queue
- **Role:** test.warehouse@bebang.ph
- **Precondition:**
  - Approved order exists from SCM-001 with 3 items
- **Call:** `POST hrms.api.store_orders.generate_dr`
- **Payload:**
  ```json
  {
    "order_id": "<order_name_from_scm_001>",
    "reviewed_by": "ian@bebang.ph",
    "qty_adjustments": [
      {"item_code": "SKU-001", "adjusted_qty": 9, "reason": "Stock allocation adjustment"}
    ]
  }
  ```
- **Assert:**
  - Response: `ok == true`, `dr_number` starts with "DR-"
  - DB verify: Delivery Receipt created with SKU-001 qty = 9 (adjusted), SKU-002 and SKU-003 unchanged
  - DB verify: Order `status == "Converted to DR"`, `dr_number` saved
  - GChat notification sent to TEST-STORE-BGC staff with DR number and adjusted items

### SCM-013: GR Completed → Low Stock Alert Sent via GChat
- **Type:** happy
- **Origin:** Plan Phase 2A low stock alerts
- **Role:** test.warehouse@bebang.ph
- **Precondition:**
  - Item SKU-001 has reorder level = 20 units in Central Warehouse
  - Current stock = 25 units
- **Call:** `POST hrms.api.warehouse.complete_goods_receipt`
- **Payload:**
  ```json
  {
    "gr_number": "GR-2026-001",
    "items": [
      {
        "item_code": "SKU-001",
        "qty": -10,
        "warehouse": "Central Warehouse - BEI",
        "notes": "Issued to production"
      }
    ]
  }
  ```
- **Assert:**
  - Response: `ok == true`
  - DB verify: Stock balance for SKU-001 = 15 units (below reorder level of 20)
  - GChat alert sent to ian@bebang.ph (or designated SCM manager), message contains:
    - Item name "Cooking Oil 1L"
    - Warehouse "Central Warehouse - BEI"
    - Qty remaining "15 units"
    - Reorder threshold "20 units"

### SCM-014: RBAC — Store OIC Cannot Access Other Store's Orders
- **Type:** rbac
- **Origin:** BLOCKER-5 (store data isolation for RBAC)
- **Role:** test.staff@bebang.ph (Store OIC for TEST-STORE-BGC)
- **Precondition:**
  - Orders exist for TEST-STORE-BGC (2 orders)
  - Orders exist for TEST-STORE-MAKATI (3 orders)
- **Call:** `GET hrms.api.store_orders.get_my_orders`
- **Payload:**
  ```json
  {}
  ```
- **Assert:**
  - Response: `ok == true`, returns ONLY 2 orders for TEST-STORE-BGC
  - Response does NOT include any orders for TEST-STORE-MAKATI
- **Additional Test:** Call `GET hrms.api.store_orders.get_my_orders?store=TEST-STORE-MAKATI`
  - Assert: `ok == false`, permission denied OR empty result (no cross-store access)

### SCM-015 [PENDING-v4.1]: Create Trip from Zone with Selected Stores → Only Selected Stores in Trip
- **Type:** happy
- **Origin:** v4.1 dynamic routing
- **Role:** test.warehouse@bebang.ph (Warehouse Manager role required)
- **Precondition:**
  - BEI Route "Cold Zone North" exists with 5 stores
  - 2 of those stores (Store A, Store C) have approved orders for today
- **Call:** `POST hrms.api.dispatch.create_trip_from_route`
- **Payload:**
  ```json
  {
    "route_name": "Cold Zone North",
    "trip_date": "2026-02-17",
    "selected_stops": [
      {"store": "Store A - BEI", "stop_order": 1},
      {"store": "Store C - BEI", "stop_order": 2}
    ]
  }
  ```
- **Assert:**
  - Response: `ok == true`, trip created with exactly 2 stops
  - DB verify: `stop_order` matches payload order (Store A = 1, Store C = 2)
  - DB verify: Stores B, D, E are excluded from the trip
  - Trip contains ONLY the 2 selected stores

### SCM-016 [PENDING-v4.1]: Create Trip from Zone with No Selected Stops → All Zone Stores Included (Backward Compat)
- **Type:** happy
- **Origin:** v4.1 backward compatibility
- **Role:** test.warehouse@bebang.ph
- **Precondition:**
  - BEI Route "Cold Zone North" exists with 5 stores
- **Call:** `POST hrms.api.dispatch.create_trip_from_route`
- **Payload:**
  ```json
  {
    "route_name": "Cold Zone North",
    "trip_date": "2026-02-17"
  }
  ```
- **Assert:**
  - Response: `ok == true`
  - DB verify: Trip created with ALL 5 stores in original route order
  - Backward compatibility: When `selected_stops` parameter is omitted, all zone stores are included

### SCM-017 [PENDING-v4.1]: Create Trip with Reordered Stops → Stop Order Matches User Sequence
- **Type:** happy
- **Origin:** v4.1 drag-to-reorder
- **Role:** test.warehouse@bebang.ph
- **Call:** `POST hrms.api.dispatch.create_trip_from_route`
- **Payload:**
  ```json
  {
    "route_name": "Cold Zone North",
    "trip_date": "2026-02-17",
    "selected_stops": [
      {"store": "Store C - BEI", "stop_order": 1},
      {"store": "Store B - BEI", "stop_order": 2},
      {"store": "Store A - BEI", "stop_order": 3}
    ]
  }
  ```
- **Assert:**
  - Response: `ok == true`
  - DB verify: `stop_order` matches exactly: Store C = 1, Store B = 2, Store A = 3
  - Stops are created in the exact sequence provided (reverse of original route order)

### SCM-018 [PENDING-v4.1]: Create Trip with Store NOT in Zone → Error
- **Type:** negative
- **Origin:** v4.1 zone validation
- **Role:** test.warehouse@bebang.ph
- **Call:** `POST hrms.api.dispatch.create_trip_from_route`
- **Payload:**
  ```json
  {
    "route_name": "Cold Zone North",
    "trip_date": "2026-02-17",
    "selected_stops": [
      {"store": "FAKE-STORE - BEI", "stop_order": 1}
    ]
  }
  ```
- **Assert:**
  - Response: `ok == false`, error message contains "not in zone" or "not found in route"
  - DB verify: NO trip created
  - Validation prevents creating trips with stores not belonging to the specified route

### SCM-019 [PENDING-v4.1]: Create Trip from Zone with Zero Pending Orders → Trip Created with 0 Items
- **Type:** edge
- **Origin:** v4.1 (drivers sometimes deliver empty runs for returns pickup)
- **Role:** test.warehouse@bebang.ph
- **Precondition:**
  - BEI Route "Cold Zone North" exists
  - Selected stores have NO approved orders (all orders are pending or no orders exist)
- **Call:** `POST hrms.api.dispatch.create_trip_from_route`
- **Payload:**
  ```json
  {
    "route_name": "Cold Zone North",
    "trip_date": "2026-02-17",
    "selected_stops": [
      {"store": "Store A - BEI", "stop_order": 1},
      {"store": "Store B - BEI", "stop_order": 2}
    ]
  }
  ```
- **Assert:**
  - Response: `ok == true`
  - DB verify: Trip created, all stops have `items_count == 0`
  - DB verify: `store_order` field is empty string (no delivery receipts to attach)
  - Edge case: Empty trips are allowed (e.g., for returns pickup)

### SCM-020 [PENDING-v4.1]: RBAC — Crew Cannot Create Trips
- **Type:** rbac
- **Origin:** v4.1 RBAC enforcement
- **Role:** test.crew1@bebang.ph (Crew role, no Warehouse Manager)
- **Call:** `POST hrms.api.dispatch.create_trip_from_route`
- **Payload:**
  ```json
  {
    "route_name": "Cold Zone North",
    "trip_date": "2026-02-17",
    "selected_stops": [
      {"store": "Store A - BEI", "stop_order": 1}
    ]
  }
  ```
- **Assert:**
  - Response: HTTP 403 or `frappe.PermissionError`
  - Error message contains "Insufficient Permissions" or "do not have access"
  - DB verify: NO trip created

### SCM-021 [PENDING-v4.1]: RBAC — Store Staff Cannot Modify Routes
- **Type:** rbac
- **Origin:** v4.1 RBAC enforcement
- **Role:** test.staff@bebang.ph (Store OIC)
- **Call:** `POST hrms.api.dispatch.update_route`
- **Payload:**
  ```json
  {
    "route_name": "Cold Zone North",
    "updates": {
      "route_name": "Hacked Route"
    }
  }
  ```
- **Assert:**
  - Response: HTTP 403 or `frappe.PermissionError`
  - DB verify: Route unchanged (still named "Cold Zone North")

### SCM-022 [PENDING-v4.1]: Trip Created with Driver as Employee Link → driver_name Auto-Fetched
- **Type:** happy
- **Origin:** v4.1 schema fix (driver = Link:Employee)
- **Role:** test.warehouse@bebang.ph
- **Call:** `POST hrms.api.dispatch.create_trip_from_route`
- **Payload:**
  ```json
  {
    "route_name": "Cold Zone North",
    "trip_date": "2026-02-17",
    "driver": "TEST-SUPERVISOR-001",
    "selected_stops": [
      {"store": "Store A - BEI", "stop_order": 1}
    ]
  }
  ```
- **Assert:**
  - Response: `ok == true`
  - DB verify: Trip `driver == "TEST-SUPERVISOR-001"` (Employee ID, not User ID)
  - DB verify: Trip linked to Employee doctype (driver field is Link:Employee)
  - Driver name auto-resolved from Employee Master

### SCM-023 [PENDING-v4.1]: Trip Created with Vehicle as BEI Vehicle Link → vehicle_plate Auto-Resolved
- **Type:** happy
- **Origin:** v4.1 schema fix (vehicle = Link:BEI Vehicle)
- **Role:** test.warehouse@bebang.ph
- **Precondition:**
  - BEI Vehicle "VH-001" exists with `vehicle_plate = "ABC 123"`
- **Call:** `POST hrms.api.dispatch.create_trip_from_route`
- **Payload:**
  ```json
  {
    "route_name": "Cold Zone North",
    "trip_date": "2026-02-17",
    "vehicle": "VH-001",
    "selected_stops": [
      {"store": "Store A - BEI", "stop_order": 1}
    ]
  }
  ```
- **Assert:**
  - Response: `ok == true`
  - DB verify: Trip `vehicle == "VH-001"`
  - DB verify: Trip `vehicle_plate == "ABC 123"` (auto-resolved from BEI Vehicle doctype)

### SCM-024 [PENDING-v4.1]: Zone Stores Show Delivery Window in Trip Wizard → UI Displays Time Hints
- **Type:** happy (L2 - page check)
- **Origin:** v4.1 delivery window fields
- **Role:** test.warehouse@bebang.ph
- **Precondition:**
  - BEI Route Stop for "Store A - BEI" has `delivery_window_start = "06:00"`, `delivery_window_end = "09:00"`
- **Call:** Navigate to `/dashboard/warehouse/trips/create`, select route "Cold Zone North", proceed to Step 3 (store selection)
- **Assert:**
  - UI displays "06:00–09:00" next to Store A in the store pool
  - Delivery window is visible as time hint for scheduling
  - (L2 test: verify DOM contains time range text)

### SCM-025 [PENDING-v4.1]: Select All Stores Then Deselect One → Trip Created Without Deselected Store
- **Type:** edge
- **Origin:** v4.1 store pool interaction
- **Role:** test.warehouse@bebang.ph
- **Precondition:**
  - BEI Route "Cold Zone North" has 5 stores (Store A, B, C, D, E)
- **Call:** `POST hrms.api.dispatch.create_trip_from_route`
- **Payload:**
  ```json
  {
    "route_name": "Cold Zone North",
    "trip_date": "2026-02-17",
    "selected_stops": [
      {"store": "Store A - BEI", "stop_order": 1},
      {"store": "Store B - BEI", "stop_order": 2},
      {"store": "Store C - BEI", "stop_order": 3},
      {"store": "Store E - BEI", "stop_order": 4}
    ]
  }
  ```
- **Assert:**
  - Response: `ok == true`
  - DB verify: Trip created with 4 stops (N-1 stores)
  - DB verify: Store D is NOT in the trip stops
  - Verify selective inclusion: all zone stores except Store D

### SCM-026 [READY]: Regression — cargo_type Billing Lookup
- **Type:** regression
- **Origin:** BUG-v45-1 (cargo_type missing from BEI Delivery Rate lookup, billing schedule always fell back to default rate)
- **Role:** test.warehouse@bebang.ph (Warehouse Manager role required)
- **Precondition:**
  - BEI Delivery Rate exists with `cargo_type = "FC"` and `rate_per_km = 35.00`
  - BEI Route "Cold Zone FC" exists with `cargo_type = "FC"` and at least 2 stops
  - Trip created from "Cold Zone FC", status = "Ready for Dispatch"
- **Call (Step 1):** `POST hrms.api.dispatch.confirm_departure`
- **Payload:**
  ```json
  {
    "trip_id": "<trip_name>",
    "departure_time": "2026-02-18 06:00:00"
  }
  ```
- **Call (Step 2):** `POST hrms.api.dispatch.confirm_delivery`
- **Payload:**
  ```json
  {
    "stop_id": "<first_stop_name>",
    "delivered_by": "TEST-WAREHOUSE-001",
    "photos": "[{\"photo\": \"<PHOTO_DATA_URL>\", \"caption\": \"Delivered to Store A\"}]"
  }
  ```
- **Assert:**
  - Response: `ok == true`
  - DB verify: BEI Billing Schedule created with `cargo_type == "FC"`
  - DB verify: `rate_applied` matches the BEI Delivery Rate for `cargo_type = "FC"` (not the default rate)
  - DB verify: No `KeyError` or fallback to generic rate — billing schedule references correct rate row
  - **Regression guard:** Before fix, `cargo_type` was missing from the rate lookup filter causing all FC trips to bill at wrong rate

### SCM-027 [READY]: Regression — Vehicle Dropdown Renders Plate Numbers
- **Type:** regression
- **Origin:** BUG-v45-2 (get_vehicles() returned dict objects; frontend rendered "[object Object]" in dropdown)
- **Role:** test.warehouse@bebang.ph
- **Precondition:**
  - At least 1 BEI Vehicle record exists with `vehicle_plate = "ABC 123"` and `name = "VH-001"`
- **Call:** `GET hrms.api.dispatch.get_vehicles`
- **Payload:** (no body required — GET endpoint)
- **Assert:**
  - Response is a JSON array (not an array of dicts with nested keys)
  - Each element has at minimum a `"name"` field that is a plain string (e.g., `"VH-001"`)
  - `response[0].name` is a string like `"VH-001"`, NOT `"[object Object]"`
  - `response[0].vehicle_plate` is `"ABC 123"` (string, not nested object)
  - **Regression guard:** Before fix, the endpoint returned raw Frappe document dicts; frontend `v.name` rendered as `[object Object]`. After fix, each item is a flat object with string fields.

### SCM-028 [READY]: Regression — Route Default Driver Inherits to Trip
- **Type:** regression
- **Origin:** BUG-v45-3 (default_driver on BEI Route was a Data field; Link:Employee not enforced so driver_name never populated)
- **Role:** test.warehouse@bebang.ph
- **Precondition:**
  - BEI Route "Cold Zone North" exists with `default_driver = "TEST-SUPERVISOR-001"` (valid Employee ID)
  - Employee TEST-SUPERVISOR-001 exists with `employee_name = "Test Supervisor"`
- **Call:** `POST hrms.api.dispatch.create_trip_from_route`
- **Payload:**
  ```json
  {
    "route_name": "Cold Zone North",
    "trip_date": "2026-02-18",
    "selected_stops": [
      {"store": "Store A - BEI", "stop_order": 1}
    ]
  }
  ```
- **Assert:**
  - Response: `ok == true`
  - DB verify: `trip.driver == "TEST-SUPERVISOR-001"` (inherited from route `default_driver`)
  - DB verify: `trip.driver_name == "Test Supervisor"` (auto-fetched from Employee Master)
  - DB verify: `trip.driver` field is a valid Link to Employee doctype (not a freetext string)
  - **Regression guard:** Before fix, `default_driver` was stored as raw text so `driver_name` was always blank and Frappe link validation failed silently

### SCM-029 [READY]: Regression — 3PL Trip Accepts threepl_driver_name
- **Type:** regression
- **Origin:** BUG-v45-5 (3PL trips had no field for external driver name; trips showed blank driver on billing reports)
- **Role:** test.warehouse@bebang.ph
- **Precondition:**
  - BEI Vehicle "VH-3PL-001" exists with `owner_type = "3PL"` and `vehicle_plate = "XYZ 999"`
- **Call:** `POST hrms.api.dispatch.create_trip_from_route`
- **Payload:**
  ```json
  {
    "route_name": "Cold Zone North",
    "trip_date": "2026-02-18",
    "vehicle": "VH-3PL-001",
    "threepl_driver_name": "Juan Cruz",
    "selected_stops": [
      {"store": "Store A - BEI", "stop_order": 1}
    ]
  }
  ```
- **Assert:**
  - Response: `ok == true`
  - DB verify: `trip.threepl_driver_name == "Juan Cruz"` (external driver name stored correctly)
  - DB verify: `trip.driver` is null or empty string (no Employee Link required for 3PL)
  - DB verify: `trip.vehicle == "VH-3PL-001"`, `trip.vehicle_plate == "XYZ 999"`
  - **Regression guard:** Before fix, submitting a 3PL trip with `threepl_driver_name` caused a field-not-found error; after fix the field exists on BEI Delivery Trip and persists correctly

### SCM-030 [READY]: Regression — ETA Uses Route Stop Estimated Minutes
- **Type:** regression
- **Origin:** BUG-v45-6 (confirm_departure() hardcoded 20 min per stop; actual `estimated_minutes` on BEI Route Stop was ignored)
- **Role:** test.warehouse@bebang.ph
- **Precondition:**
  - BEI Route "ETA Test Route" exists with exactly 4 stops:
    - Stop 1 (Store A): `estimated_minutes = 15`
    - Stop 2 (Store B): `estimated_minutes = 25`
    - Stop 3 (Store C): `estimated_minutes = 20`
    - Stop 4 (Store D): `estimated_minutes = 30`
  - Trip created from "ETA Test Route", status = "Ready for Dispatch"
- **Call (Step 1):** `POST hrms.api.dispatch.confirm_departure`
- **Payload:**
  ```json
  {
    "trip_id": "<trip_name>",
    "departure_time": "2026-02-18 06:00:00"
  }
  ```
- **Call (Step 2):** `GET hrms.api.dispatch.get_route_progress`
- **Payload:**
  ```json
  {
    "trip_id": "<trip_name>"
  }
  ```
- **Assert:**
  - Response: `ok == true` on departure confirmation
  - DB verify (cumulative ETAs from 06:00 departure):
    - Stop 1 ETA = `06:15` (0 + 15 min)
    - Stop 2 ETA = `06:40` (15 + 25 min)
    - Stop 3 ETA = `07:00` (40 + 20 min)
    - Stop 4 ETA = `07:30` (60 + 30 min)
  - `get_route_progress` response contains ETA timestamps matching above values
  - **Regression guard:** Before fix, all stops had ETA = stop_order × 20 min (hardcoded), so Stop 1 = 06:20, Stop 2 = 06:40, Stop 3 = 07:00, Stop 4 = 07:20 — wrong for non-uniform routes

---


## Store Ops + Inventory Sprint Scenarios (21 scenarios)

**Added:** 2026-02-20 | **Origin:** Store Ops + Inventory Sprint — pre-written before execution per E2E_RULES.md Rule 9

**Context:** Covers the Store Order flow (SORDER), POS date mismatch detection (POSDATE), Food Quality Check receiving fields (FQI), Variance Investigation lifecycle (VAR), Cycle Count Reconciliation (CCRECON), GChat notification resilience (GCHAT), RBAC gates (RBAC), and Stage 3 POS auto-link (STAGE3).

**API Base:** `https://hq.bebang.ph/api/method/hrms.api`

**Key Business Rules:**
- Store orders require an Approval Queue entry when submitted — `assigned_approver` must be populated
- Material Request items MUST have `warehouse` set after approval (regression: BLOCKER 1)
- POS upload date mismatch is non-blocking but must set `has_date_mismatch = 1` on the document
- Variance resolution via Write-Off creates a **Submitted** Stock Entry (docstatus=1, NOT Draft)
- Variance resolution via Recount Corrected creates a **Submitted** Stock Reconciliation (docstatus=1)
- GChat failures are always non-blocking — orders and approvals succeed regardless
- Only Verified cycle counts can be reconciled (CCRECON guard)
- Crew role is blocked from all inventory investigation and variance resolution endpoints

---

### SORDER-001: Submit store order via store.submit_order

**Level:** L3
**Type:** happy
**Login:** test.staff@bebang.ph / BeiTest2026!

**Prerequisites:**
- Store "Market Market - BK" exists in Frappe
- Item code "CHICKEN-JOY-2PC" exists with stock available in Central Warehouse
- test.staff@bebang.ph has Store OIC role and is linked to "Market Market - BK"

**Steps:**
1. POST `hrms.api.store.submit_order` with payload:
   ```json
   {
     "store": "Market Market - BK",
     "items": [
       {
         "item_code": "CHICKEN-JOY-2PC",
         "qty": 50,
         "uom": "Nos"
       }
     ],
     "cargo_category": "FC",
     "is_emergency": false
   }
   ```

**Expected Results:**
- [ ] `result.success == true`
- [ ] `result.order` is not null and starts with a recognizable prefix (e.g., "BEI-SO-" or "SO-")
- [ ] DB: `BEI Store Order.<result.order>.status == "Pending Approval"`
- [ ] DB: `BEI Approval Queue` entry exists with `reference_doctype == "BEI Store Order"` and `reference_name == result.order`
- [ ] DB: `BEI Approval Queue.<entry>.assigned_approver` is not null and not empty string

---

### SORDER-002: Area Supervisor approves order — Material Request created with correct warehouse

**Level:** L3
**Type:** happy + regression
**Login:** test.area@bebang.ph / BeiTest2026!
**Origin:** Regression for BLOCKER 1 (warehouse was null on Material Request Item after approval)

**Prerequisites:**
- SORDER-001 completed; use `order_name` from SORDER-001 result
- test.area@bebang.ph has Area Supervisor role and is the assigned_approver for the queue entry

**Steps:**
1. POST `hrms.api.store.approve_order` with payload:
   ```json
   {
     "order_name": "<order_name from SORDER-001>",
     "approved_quantities": [
       {
         "item_code": "CHICKEN-JOY-2PC",
         "qty_approved": 45
       }
     ]
   }
   ```

**Expected Results:**
- [ ] `result.success == true`
- [ ] DB: `BEI Store Order.<order_name>.status == "Approved"`
- [ ] DB: A `Material Request` document was created (discoverable via `frappe.db.get_value("Material Request", {"store_order": order_name}, "name")`)
- [ ] DB: `Material Request Item` for CHICKEN-JOY-2PC has `warehouse` field that is NOT null and NOT empty string
- [ ] DB: `Material Request Item.qty == 45` (approved qty, not the original 50)

---

### SORDER-003: Regression — Material Request warehouse field is never null after order approval

**Level:** L3
**Type:** regression
**Login:** test.area@bebang.ph / BeiTest2026!
**Origin:** BLOCKER 1 — Material Request Item.warehouse was null causing downstream Stock Entry failures

**Prerequisites:**
- A BEI Store Order in "Pending Approval" status (use SORDER-001 or create a fresh one)

**Steps:**
1. POST `hrms.api.store.approve_order` with payload:
   ```json
   {
     "order_name": "<order_name>",
     "approved_quantities": [
       {
         "item_code": "CHICKEN-JOY-2PC",
         "qty_approved": 45
       }
     ]
   }
   ```
2. Fetch the resulting Material Request name via bench console or API
3. Fetch warehouse from DB: `frappe.db.get_value("Material Request Item", {"parent": mr_name}, "warehouse")`

**Expected Results:**
- [ ] `warehouse` is not None
- [ ] `warehouse` is not an empty string `""`
- [ ] `warehouse` resolves to a valid Frappe Warehouse (e.g., "Market Market - BK Warehouse - BEI" or the configured default)
- [ ] **Regression guard:** Before the fix, this value was always `None`, causing all downstream Stock Entries to fail with "Warehouse is mandatory"

---

### POSDATE-001: Upload POS with mismatched date returns date_mismatch flag

**Level:** L3
**Type:** edge
**Login:** test.staff@bebang.ph / BeiTest2026!

**Prerequisites:**
- test.staff@bebang.ph is linked to store "Market Market - BK"
- Use today as `pos_date` and yesterday as the CSV internal date

**Steps:**
1. Prepare a POS CSV where the internal date column contains yesterday's date (e.g., 2026-02-19)
2. POST `hrms.api.store.upload_pos_data` with payload:
   ```json
   {
     "store": "Market Market - BK",
     "pos_date": "2026-02-20",
     "pos_system": "Mosaic",
     "pos_file_content": "<base64-encoded CSV with 2026-02-19 internal date>",
     "discount_report": "<PHOTO_DATA_URL>",
     "transaction_report": "<PHOTO_DATA_URL>",
     "product_mix": "<PHOTO_DATA_URL>",
     "daily_sales_revenue": "<PHOTO_DATA_URL>",
     "sales_summary": "<PHOTO_DATA_URL>"
   }
   ```

**Expected Results:**
- [ ] `result.success == true` (upload is NOT blocked — mismatch is a warning, not an error)
- [ ] `result.date_mismatch == true`
- [ ] `result.warning` or `result.message` contains both dates: the submitted `pos_date` AND the date found inside the CSV
- [ ] DB: BEI POS Upload document is created and persisted (name accessible)

---

### POSDATE-002: has_date_mismatch field is persisted on the POS Upload document

**Level:** L3
**Type:** regression
**Login:** test.staff@bebang.ph / BeiTest2026!
**Origin:** BLOCKER 6 — `has_date_mismatch` field on BEI POS Upload was not being set even when mismatch was detected

**Prerequisites:**
- POSDATE-001 completed; POS Upload document name available

**Steps:**
1. Complete POSDATE-001 to obtain `doc_name`
2. Fetch the field directly: `frappe.db.get_value("BEI POS Upload", doc_name, "has_date_mismatch")`

**Expected Results:**
- [ ] `has_date_mismatch == 1` (integer 1, truthy)
- [ ] Field is persisted on the document after upload (not just returned in the API response)
- [ ] **Regression guard:** Before the fix, this field was always 0 even when dates clearly differed, making audit queries for mismatch uploads impossible

---

### FQI-001: complete_receiving with all 5 quality checks saves all fields

**Level:** L3
**Type:** happy
**Login:** test.staff@bebang.ph / BeiTest2026!

**Prerequisites:**
- A `BEI Store Receiving` document exists in status "Pending Receiving" linked to "Market Market - BK"
- The receiving has at least one item

**Steps:**
1. POST `hrms.api.store.complete_receiving` with payload:
   ```json
   {
     "receiving_name": "<BEI Store Receiving name>",
     "check_temperature": 1,
     "check_packaging": 1,
     "check_quantity": 1,
     "check_expiry": 1,
     "check_food_quality": 1,
     "receiving_notes": "All 5 quality checks passed. Items received in good condition at 06:45 AM."
   }
   ```

**Expected Results:**
- [ ] `result.success == true`
- [ ] DB: `BEI Store Receiving Item.check_temperature == 1`
- [ ] DB: `BEI Store Receiving Item.check_packaging == 1`
- [ ] DB: `BEI Store Receiving Item.check_quantity == 1`
- [ ] DB: `BEI Store Receiving Item.check_expiry == 1`
- [ ] DB: `BEI Store Receiving Item.check_food_quality == 1`
- [ ] DB: `BEI Store Receiving.status == "Received"` (or equivalent completion status)
- [ ] No validation error thrown for any of the 5 fields

---

### FQI-002: complete_receiving with check_food_quality=0 is allowed (not mandatory)

**Level:** L3
**Type:** edge
**Login:** test.staff@bebang.ph / BeiTest2026!

**Prerequisites:**
- A fresh `BEI Store Receiving` in "Pending Receiving" status (separate from FQI-001)

**Steps:**
1. POST `hrms.api.store.complete_receiving` with payload:
   ```json
   {
     "receiving_name": "<BEI Store Receiving name>",
     "check_temperature": 1,
     "check_packaging": 1,
     "check_quantity": 1,
     "check_expiry": 1,
     "check_food_quality": 0,
     "receiving_notes": "4 checks passed. Food quality check not applicable for dry goods."
   }
   ```

**Expected Results:**
- [ ] `result.success == true` (no error — `check_food_quality` is NOT mandatory)
- [ ] DB: `BEI Store Receiving Item.check_food_quality == 0`
- [ ] DB: All other 4 check fields saved correctly as 1
- [ ] DB: `BEI Store Receiving.status` reflects completion (not stuck in "Pending Receiving")

---

### VAR-001: start_variance_investigation transitions Open to Investigating

**Level:** L3
**Type:** happy
**Login:** test.supervisor@bebang.ph / BeiTest2026!

**Prerequisites:**
- A `BEI Stock Variance` document exists with `status == "Open"` for the supervisor's store
- test.supervisor@bebang.ph has Store Supervisor role

**Steps:**
1. POST `hrms.api.inventory.start_variance_investigation` with payload:
   ```json
   {
     "variance_name": "<BEI Stock Variance name>",
     "investigation_notes": "Beginning investigation — counted shelf stock manually, checking delivery records."
   }
   ```

**Expected Results:**
- [ ] `result.success == true`
- [ ] DB: `BEI Stock Variance.<variance_name>.status == "Investigating"`
- [ ] DB: `investigated_by` is set (supervisor user or employee ID)
- [ ] DB: `investigation_started_at` is set (datetime, not null)

---

### VAR-002: resolve_variance Write-Off creates a SUBMITTED Stock Entry

**Level:** L3
**Type:** happy
**Login:** test.supervisor@bebang.ph / BeiTest2026!
**Origin:** Regression prevention — Stock Entry must be docstatus=1, NOT Draft

**Prerequisites:**
- A `BEI Stock Variance` in status "Investigating" (use VAR-001 output or create fresh)
- The variance item has sufficient stock for write-off

**Steps:**
1. POST `hrms.api.inventory.resolve_variance` with payload:
   ```json
   {
     "variance_name": "<BEI Stock Variance name>",
     "resolution_type": "Write-Off",
     "resolution_notes": "Spoilage confirmed during investigation. Items disposed of per food safety protocol. Write-off approved by area supervisor."
   }
   ```

**Expected Results:**
- [ ] `result.success == true`
- [ ] `result.stock_entry` is not null (Stock Entry name returned)
- [ ] DB: `Stock Entry.<result.stock_entry>.docstatus == 1` (Submitted — NOT 0/Draft, NOT 2/Cancelled)
- [ ] DB: `Stock Entry.<result.stock_entry>.stock_entry_type == "Material Issue"` (or equivalent write-off type)
- [ ] DB: `BEI Stock Variance.<variance_name>.status == "Resolved"`
- [ ] DB: `BEI Stock Variance.<variance_name>.resolution_type == "Write-Off"`

---

### VAR-003: resolve_variance Recount Corrected creates a SUBMITTED Stock Reconciliation

**Level:** L3
**Type:** happy
**Login:** test.supervisor@bebang.ph / BeiTest2026!
**Origin:** Regression prevention — Stock Reconciliation must be docstatus=1

**Prerequisites:**
- A `BEI Stock Variance` in status "Investigating"
- The variance item has stock to reconcile

**Steps:**
1. POST `hrms.api.inventory.resolve_variance` with payload:
   ```json
   {
     "variance_name": "<BEI Stock Variance name>",
     "resolution_type": "Recount Corrected",
     "adjustment_qty": 5,
     "resolution_notes": "Recount confirmed actual qty is 5 units higher than system. Initial count was done during rush hour — miscounted. Corrected via stock reconciliation."
   }
   ```

**Expected Results:**
- [ ] `result.success == true`
- [ ] `result.stock_reconciliation` is not null (Stock Reconciliation name returned)
- [ ] DB: `Stock Reconciliation.<result.stock_reconciliation>.docstatus == 1` (Submitted — NOT 0/Draft)
- [ ] DB: Stock Reconciliation items reflect `adjustment_qty` = 5
- [ ] DB: `BEI Stock Variance.<variance_name>.status == "Resolved"`
- [ ] DB: `BEI Stock Variance.<variance_name>.resolution_type == "Recount Corrected"`

---

### VAR-004: resolve_variance from "Open" status (skip Investigating) is allowed

**Level:** L3
**Type:** edge
**Login:** test.supervisor@bebang.ph / BeiTest2026!

**Prerequisites:**
- A `BEI Stock Variance` in status "Open" (NOT "Investigating" — freshly created or reset)

**Steps:**
1. POST `hrms.api.inventory.resolve_variance` with payload:
   ```json
   {
     "variance_name": "<BEI Stock Variance in Open status>",
     "resolution_type": "Write-Off",
     "resolution_notes": "Quick resolution — variance confirmed as spoilage, no extended investigation needed. Resolved directly from Open."
   }
   ```

**Expected Results:**
- [ ] `result.success == true` (code allows resolution from both Open and Investigating)
- [ ] DB: `BEI Stock Variance.status == "Resolved"`
- [ ] DB: Stock Entry or Stock Reconciliation created with `docstatus == 1`
- [ ] No error like "Variance must be in Investigating status to resolve"

---

### VAR-005: RBAC — Crew member CANNOT call start_variance_investigation

**Level:** L3
**Type:** rbac
**Login:** test.crew1@bebang.ph / BeiTest2026!

**Prerequisites:**
- Any `BEI Stock Variance` in "Open" status exists

**Steps:**
1. POST `hrms.api.inventory.start_variance_investigation` with payload:
   ```json
   {
     "variance_name": "<any Open BEI Stock Variance>",
     "investigation_notes": "Crew attempting to start investigation."
   }
   ```

**Expected Results:**
- [ ] Response is HTTP 403 OR Frappe PermissionError
- [ ] Error message contains "Insufficient Permissions", "do not have access", or equivalent
- [ ] DB: `BEI Stock Variance.status` unchanged (still "Open")
- [ ] Crew role is strictly blocked from variance investigation workflow

---

### VAR-006: RBAC — Crew member CANNOT call resolve_variance

**Level:** L3
**Type:** rbac
**Login:** test.crew1@bebang.ph / BeiTest2026!

**Prerequisites:**
- Any `BEI Stock Variance` in "Investigating" or "Open" status exists

**Steps:**
1. POST `hrms.api.inventory.resolve_variance` with payload:
   ```json
   {
     "variance_name": "<any BEI Stock Variance>",
     "resolution_type": "Write-Off",
     "resolution_notes": "Crew attempting to resolve variance."
   }
   ```

**Expected Results:**
- [ ] Response is HTTP 403 OR Frappe PermissionError
- [ ] Error message contains "Insufficient Permissions" or equivalent
- [ ] DB: `BEI Stock Variance.status` unchanged
- [ ] No Stock Entry or Stock Reconciliation created

---

### VAR-007: Variance list loads successfully for Area Supervisor

**Level:** L3
**Type:** happy
**Login:** test.area@bebang.ph / BeiTest2026!

**Prerequisites:**
- At least one `BEI Stock Variance` exists in any status

**Steps:**
1. GET `hrms.api.inventory.get_variances` (no body required)

**Expected Results:**
- [ ] `result.success == true` OR response is a valid list (no PermissionError, no 500)
- [ ] Response contains a list (may be empty if no variances in scope, but must not error)
- [ ] Area Supervisor role is NOT blocked from viewing variances
- [ ] Each item in the list has at minimum: `name`, `status`, and `store` or `warehouse` fields

---

### CCRECON-001: mark_cycle_count_reconciled transitions Verified to Reconciled

**Level:** L3
**Type:** happy
**Login:** test.supervisor@bebang.ph / BeiTest2026!

**Prerequisites:**
- A `BEI Cycle Count` document exists with `status == "Verified"` linked to the supervisor's store
- test.supervisor@bebang.ph has Store Supervisor role

**Steps:**
1. POST `hrms.api.inventory.mark_cycle_count_reconciled` with payload:
   ```json
   {
     "cycle_count_name": "<BEI Cycle Count in Verified status>",
     "reconciliation_notes": "Reconciliation complete. All variances resolved. Stock entries submitted and GL impact confirmed."
   }
   ```

**Expected Results:**
- [ ] `result.success == true`
- [ ] DB: `BEI Cycle Count.<cycle_count_name>.status == "Reconciled"`
- [ ] DB: `reconciled_by` is set (supervisor user or employee)
- [ ] DB: `reconciled_at` is set (datetime, not null)

---

### CCRECON-002: Cannot reconcile a Cycle Count that is not in Verified status

**Level:** L3
**Type:** adversarial
**Login:** test.supervisor@bebang.ph / BeiTest2026!

**Prerequisites:**
- A `BEI Cycle Count` in status "Submitted" (approved/submitted but NOT yet verified — skipping the Verified step)

**Steps:**
1. POST `hrms.api.inventory.mark_cycle_count_reconciled` with payload:
   ```json
   {
     "cycle_count_name": "<BEI Cycle Count in Submitted status>",
     "reconciliation_notes": "Attempting premature reconciliation."
   }
   ```

**Expected Results:**
- [ ] `result.success == false` OR Frappe ValidationError thrown
- [ ] Error message contains "Only Verified cycle counts can be marked as Reconciled" or equivalent guard message
- [ ] DB: `BEI Cycle Count.status` unchanged (still "Submitted")
- [ ] Status guard enforced — cannot skip the Verified step

---

### GCHAT-001: submit_order succeeds even when GChat notification is unavailable

**Level:** L3
**Type:** edge (non-blocking notification)
**Login:** test.staff@bebang.ph / BeiTest2026!

**Prerequisites:**
- "Market Market - BK" store exists
- CHICKEN-JOY-2PC item exists

**Steps:**
1. POST `hrms.api.store.submit_order` with payload:
   ```json
   {
     "store": "Market Market - BK",
     "items": [
       {
         "item_code": "CHICKEN-JOY-2PC",
         "qty": 10,
         "uom": "Nos"
       }
     ],
     "cargo_category": "FC",
     "is_emergency": false
   }
   ```

**Expected Results:**
- [ ] `result.success == true` (order created regardless of GChat state)
- [ ] DB: `BEI Store Order` created with status "Pending Approval"
- [ ] DB: Approval Queue entry created with `assigned_approver` set
- [ ] If GChat notification failed: error is logged in Frappe Error Log but NOT propagated to the API response
- [ ] No `frappe.throw()` triggered by a GChat failure in the submit_order code path

---

### GCHAT-002: approve_order succeeds even when GChat notification is unavailable

**Level:** L3
**Type:** edge (non-blocking notification)
**Login:** test.area@bebang.ph / BeiTest2026!

**Prerequisites:**
- A BEI Store Order in "Pending Approval" status exists (use GCHAT-001 or SORDER-001 output)

**Steps:**
1. POST `hrms.api.store.approve_order` with payload:
   ```json
   {
     "order_name": "<order in Pending Approval>",
     "approved_quantities": [
       {
         "item_code": "CHICKEN-JOY-2PC",
         "qty_approved": 10
       }
     ]
   }
   ```

**Expected Results:**
- [ ] `result.success == true`
- [ ] DB: `BEI Store Order.status == "Approved"`
- [ ] DB: Material Request created with `warehouse` populated (regression guard from SORDER-003)
- [ ] If GChat notification for "order approved" failed: logged in Frappe Error Log, NOT thrown as an exception
- [ ] Approval workflow completes fully even if GChat is unreachable

---

### GCHAT-003: GChat failure does NOT block order submission — code-level verification

**Level:** L3
**Type:** regression
**Login:** test.staff@bebang.ph / BeiTest2026!
**Origin:** Pattern from SCM-007 — GChat must be wrapped in try/except in submit_order

**Prerequisites:**
- Access to source code at `hrms/api/store.py` (or equivalent path)

**Steps:**
1. Open `hrms/api/store.py` and inspect the `submit_order` function:
   - Locate the GChat notification call (look for `google_chat`, `send_message`, or similar)
   - Verify it is wrapped in a `try/except` block
   - Verify the `except` clause calls `frappe.log_error(...)` and does NOT re-raise or call `frappe.throw()`
2. Submit a fresh order via the API (same payload as GCHAT-001)

**Expected Results:**
- [ ] Code review: GChat call is inside `try/except` block
- [ ] Code review: `except` block calls `frappe.log_error(...)` not `raise` or `frappe.throw()`
- [ ] API: `result.success == true` (order created)
- [ ] Frappe Error Log: if GChat was unreachable, an error entry exists with a message like "GChat notification failed" or "submit_order notification error"
- [ ] **Regression guard:** Any future change that moves the GChat call outside try/except will break this test

---

### RBAC-001: Store Crew CANNOT call store.approve_order

**Level:** L3
**Type:** rbac
**Login:** test.crew1@bebang.ph / BeiTest2026!

**Prerequisites:**
- Any `BEI Store Order` in "Pending Approval" status exists

**Steps:**
1. POST `hrms.api.store.approve_order` with payload:
   ```json
   {
     "order_name": "<any Pending Approval order>",
     "approved_quantities": [
       {
         "item_code": "CHICKEN-JOY-2PC",
         "qty_approved": 5
       }
     ]
   }
   ```

**Expected Results:**
- [ ] Response is HTTP 403 OR Frappe PermissionError
- [ ] Error message contains "Insufficient Permissions", "do not have access", or equivalent
- [ ] DB: `BEI Store Order.status` unchanged (still "Pending Approval")
- [ ] Crew role cannot bypass the approval gate

---

### RBAC-002: Area Supervisor CAN call store.approve_order (positive RBAC check)

**Level:** L3
**Type:** rbac (positive assertion)
**Login:** test.area@bebang.ph / BeiTest2026!

**Prerequisites:**
- A `BEI Store Order` in "Pending Approval" status where test.area@bebang.ph is the assigned_approver

**Steps:**
1. POST `hrms.api.store.approve_order` with payload:
   ```json
   {
     "order_name": "<Pending Approval order with area supervisor as approver>",
     "approved_quantities": [
       {
         "item_code": "CHICKEN-JOY-2PC",
         "qty_approved": 45
       }
     ]
   }
   ```

**Expected Results:**
- [ ] HTTP 200 (no permission error)
- [ ] `result.success == true`
- [ ] DB: `BEI Store Order.status == "Approved"`
- [ ] Area Supervisor role has approve_order permission confirmed

---

### STAGE3-001: submit_closing_stage3_photos auto-links today's POS upload

**Level:** L3
**Type:** happy + regression
**Login:** test.staff@bebang.ph / BeiTest2026!
**Origin:** Stage 3 auto-link requirement — closing report must auto-attach today's POS upload without manual input

**Prerequisites:**
- A `BEI POS Upload` exists for today's date AND for "Market Market - BK" (in submitted/complete status)
- A `BEI Store Closing Report` exists in draft or stage-2-complete status for "Market Market - BK" today

**Steps:**
1. POST `hrms.api.store.submit_closing_stage3_photos` with payload:
   ```json
   {
     "report_name": "<BEI Store Closing Report name>",
     "x_reading_opening_photo": "<PHOTO_DATA_URL>",
     "x_reading_closing_photo": "<PHOTO_DATA_URL>",
     "z_reading_photo": "<PHOTO_DATA_URL>"
   }
   ```

**Expected Results:**
- [ ] `result.success == true`
- [ ] DB: `BEI Store Closing Report.<report_name>.pos_upload` is NOT null and NOT empty string
- [ ] DB: `BEI Store Closing Report.<report_name>.pos_upload` equals the name of the POS Upload for today and this store
- [ ] DB: The linked POS Upload has `pos_date` matching today and `store == "Market Market - BK"`
- [ ] Auto-link happens server-side — the caller does NOT need to pass `pos_upload` in the payload
- [ ] If no POS Upload exists for today: `pos_upload` field is left null and no error is thrown (graceful degradation)

---

### VAR-PHOTO-001: Variance Report with Photo Evidence

**Level:** L3
**Type:** edge
**Login:** test.staff@bebang.ph / BeiTest2026!

**Prerequisites:**
- test.staff@bebang.ph is linked to store "Market Market - BK" (Store OIC role)
- Item "CHICKEN-JOY-2PC" exists in Frappe
- Photo fixture: generate `PHOTO_DATA_URL` using the 200x200 PNG generator from the Data Requirements section (~151KB base64). NEVER use a 1x1 pixel PNG.

**Steps:**
1. Generate `PHOTO_DATA_URL` using the photo fixture script in the "Photo Test Fixture" section above.
2. POST `hrms.api.inventory.report_variance` with payload:
   ```json
   {
     "store": "Market Market - BK",
     "item_code": "CHICKEN-JOY-2PC",
     "system_qty": 20,
     "actual_qty": 17,
     "variance_type": "Shortage",
     "explanation": "Counted shelf stock manually — 3 units missing. Checked delivery records and no unrecorded issues. Possible pilferage during morning rush.",
     "photo": "<PHOTO_DATA_URL>"
   }
   ```
3. Capture `result.name` (the BEI Inventory Variance document name).
4. Fetch the document via bench console or Frappe API: `frappe.get_doc("BEI Inventory Variance", result.name)`
5. Fetch the File record: `frappe.db.get_value("File", {"attached_to_name": result.name, "attached_to_doctype": "BEI Inventory Variance"}, ["name", "file_url", "attached_to_doctype"])`
6. Verify the photo URL is accessible: `requests.get("https://hq.bebang.ph" + doc.photo_evidence)` — should return HTTP 200.

**Expected Results:**
- [ ] `result.success == true`
- [ ] `result.name` starts with "BEI-VAR-" or similar variance prefix (not null)
- [ ] DB: `BEI Inventory Variance.<result.name>.photo_evidence` is a `/files/` URL string (NOT a base64 string, NOT null)
- [ ] DB: `BEI Inventory Variance.<result.name>.photo_evidence` does NOT contain `data:image` (base64 prefix must be stripped)
- [ ] DB: Frappe `File` DocType record exists where `attached_to_doctype == "BEI Inventory Variance"` AND `attached_to_name == result.name`
- [ ] File URL returns HTTP 200 when fetched (photo is accessible, not broken link)
- [ ] DB: `BEI Inventory Variance.<result.name>.variance_qty == -3` (17 - 20)
- [ ] DB: `BEI Inventory Variance.<result.name>.variance_type == "Shortage"`
- [ ] **Key assertion:** `photo_evidence` is a server-side `/files/` URL, proving `save_base64_image()` ran correctly and the base64 was NOT stored raw in the DB column

---

### CC-PHOTO-001: Cycle Count with Photo Evidence

**Level:** L3
**Type:** edge
**Login:** test.staff@bebang.ph / BeiTest2026!

**Prerequisites:**
- test.staff@bebang.ph is linked to store "Market Market - BK" (Store OIC role)
- Item "CHICKEN-JOY-2PC" exists with a stock UOM set in Frappe
- A photo file has been uploaded to Frappe via multipart/form-data and a `photo_url` (e.g., `/files/cycle_count_photo.png`) is available OR use the two-step approach described below.
- Photo fixture: generate `PHOTO_DATA_URL` (~151KB base64, 200x200 PNG). NEVER use a 1x1 pixel PNG.

**Two-Step Upload Pattern (required for submit_cycle_count_v2):**
`submit_cycle_count_v2` accepts a `photo_url` parameter (a server-side `/files/` path), NOT raw base64. Upload the photo first:
1. Upload photo file via `POST /api/method/upload_file` (multipart/form-data, `is_private=0`), get `file_url` from response.
2. Pass that `file_url` as `photo_url` in the cycle count payload.

**Steps:**
1. Generate `PHOTO_DATA_URL` using the photo fixture script. Decode from base64 to raw bytes for the file upload.
2. Upload the photo via `POST https://hq.bebang.ph/api/method/upload_file` (multipart/form-data):
   - Field `file`: the PNG bytes, filename `cycle_count_evidence.png`
   - Field `is_private`: `0`
   - Capture `response.message.file_url` (e.g., `/files/cycle_count_evidence.png`)
3. POST `hrms.api.inventory.submit_cycle_count_v2` with payload:
   ```json
   {
     "store": "Market Market - BK",
     "count_date": "2026-02-20",
     "count_type": "Store Monthly",
     "photo_url": "<file_url from step 2>",
     "items": [
       {
         "item_code": "CHICKEN-JOY-2PC",
         "counted_qty_whole": 18,
         "counted_qty_loose": 0.0
       }
     ]
   }
   ```
4. Capture `result.name` (BEI Cycle Count document name).
5. Fetch the document: `frappe.get_doc("BEI Cycle Count", result.name)`
6. Fetch the linked File record: `frappe.db.get_value("File", {"attached_to_name": result.name, "attached_to_doctype": "BEI Cycle Count"}, ["name", "file_url", "attached_to_doctype"])`
7. Verify photo accessibility: `requests.get("https://hq.bebang.ph" + doc.photo_evidence)` — should return HTTP 200.

**Expected Results:**
- [ ] Upload step: `file_url` returned is a `/files/` path (not null, not empty string)
- [ ] `result.name` is a BEI Cycle Count document name (not null)
- [ ] `result.status == "Submitted"`
- [ ] DB: `BEI Cycle Count.<result.name>.photo_evidence` equals the `file_url` from the upload step
- [ ] DB: `BEI Cycle Count.<result.name>.photo_evidence` is a `/files/` URL (NOT null, NOT base64 string)
- [ ] DB: Frappe `File` DocType record exists where `attached_to_doctype == "BEI Cycle Count"` AND `attached_to_name == result.name`
- [ ] DB: The File record's `attached_to_name` was set by the two-step linkage in `submit_cycle_count_v2` (not left as orphan)
- [ ] File URL returns HTTP 200 when fetched (photo is accessible)
- [ ] DB: `BEI Cycle Count.<result.name>.docstatus == 1` (submitted, not draft)
- [ ] **Key assertion:** File DocType `attached_to_name` is populated — the orphan-link step (`frappe.db.set_value("File", ...)`) ran correctly after doc insert

---

## Regression Bank Updates (Store Ops + Inventory Sprint)

| ID | Date | Origin | Test |
|----|------|--------|------|
| REG-010 | 2026-02-20 | BLOCKER 1: Material Request Item.warehouse null after approval | SORDER-002, SORDER-003 |
| REG-011 | 2026-02-20 | BLOCKER 6: has_date_mismatch not persisted on BEI POS Upload | POSDATE-002 |
| REG-012 | 2026-02-20 | VAR resolution creates Draft Stock Entry/Reconciliation (must be Submitted, docstatus=1) | VAR-002, VAR-003 |
| REG-013 | 2026-02-20 | GChat failure propagated as frappe.throw() blocking order submission | GCHAT-003 |
| REG-014 | 2026-02-20 | Stage 3 closing report does not auto-link today's POS upload | STAGE3-001 |
| REG-015 | 2026-02-20 | Variance photo stored as raw base64 in DB column instead of /files/ URL | VAR-PHOTO-001 |
| REG-016 | 2026-02-20 | Cycle count photo File record left as orphan (attached_to_name not set) | CC-PHOTO-001 |


### T-PROC-003: PR -> PO -> GR -> Invoice -> Payment E2E Flow (Happy Path)
**Level:** L4
**Type:** happy
**Login:** Multiple Roles

**Steps:**
1. **Purchase Request (PR)**
   - **Role:** test.requester@bebang.ph (Department Head)
   - **Call:** `POST hrms.api.procurement.create_purchase_request`
   - **Payload:**
     ```json
     {
       "transaction_date": "2026-02-22",
       "required_by": "2026-02-28",
       "material_request_type": "Purchase",
       "items": [
         {
           "item_code": "LAPTOP-001",
           "qty": 5,
           "uom": "Nos",
           "schedule_date": "2026-02-28"
         }
       ]
     }
     ```
   - **Assert:** DB: `Material Request.docstatus == 1`, `status == "Pending"`
2. **Purchase Order (PO)**
   - **Role:** test.purchasing@bebang.ph (Purchasing Manager)
   - **Call:** `POST hrms.api.procurement.create_purchase_order`
   - **Payload:**
     ```json
     {
       "supplier": "Tech Supplies Inc.",
       "material_request": "<Material Request Name>",
       "items": [
         {
           "item_code": "LAPTOP-001",
           "qty": 5,
           "rate": 50000,
           "material_request": "<Material Request Name>",
           "material_request_item": "<Material Request Item Name>"
         }
       ]
     }
     ```
   - **Assert:** DB: `Purchase Order.docstatus == 1`, `status == "To Receive and Bill"`
3. **Goods Receipt (GR)**
   - **Role:** test.warehouse@bebang.ph (Warehouse Manager)
   - **Call:** `POST hrms.api.procurement.create_purchase_receipt`
   - **Payload:**
     ```json
     {
       "supplier": "Tech Supplies Inc.",
       "purchase_order": "<Purchase Order Name>",
       "items": [
         {
           "item_code": "LAPTOP-001",
           "qty": 5,
           "purchase_order": "<Purchase Order Name>",
           "purchase_order_item": "<Purchase Order Item Name>",
           "warehouse": "Central Warehouse - BEI"
         }
       ]
     }
     ```
   - **Assert:** DB: `Purchase Receipt.docstatus == 1`, `status == "To Bill"`
4. **Purchase Invoice (Invoice)**
   - **Role:** test.ap@bebang.ph (Accounts Payable)
   - **Call:** `POST hrms.api.procurement.create_purchase_invoice`
   - **Payload:**
     ```json
     {
       "supplier": "Tech Supplies Inc.",
       "purchase_receipt": "<Purchase Receipt Name>",
       "items": [
         {
           "item_code": "LAPTOP-001",
           "qty": 5,
           "rate": 50000,
           "purchase_receipt": "<Purchase Receipt Name>",
           "pr_detail": "<Purchase Receipt Item Name>"
         }
       ]
     }
     ```
   - **Assert:** DB: `Purchase Invoice.docstatus == 1`, `status == "Unpaid"`
5. **Payment Entry (Payment)**
   - **Role:** test.finance@bebang.ph (Finance Manager)
   - **Call:** `POST hrms.api.procurement.create_payment_entry`
   - **Payload:**
     ```json
     {
       "party_type": "Supplier",
       "party": "Tech Supplies Inc.",
       "payment_type": "Pay",
       "paid_amount": 250000,
       "reference_name": "<Purchase Invoice Name>",
       "reference_doctype": "Purchase Invoice"
     }
     ```
   - **Assert:** DB: `Payment Entry.docstatus == 1`, `Purchase Invoice.status == "Paid"`

### T-PROC-004: 3-Way Match Exception Flow (Invoice Amount Differs from PO/GR)
**Level:** L4
**Type:** edge
**Login:** Multiple Roles

**Steps:**
1. **PO and GR Creation**
   - **Role:** test.purchasing@bebang.ph & test.warehouse@bebang.ph
   - **Action:** Create PO for 10 units of `MOUSE-001` at 500 rate. Create GR for 10 units. (Follow steps 1-3 from T-PROC-003 equivalent).
   - **Assert:** DB: `Purchase Receipt.docstatus == 1`
2. **Purchase Invoice with Discrepancy**
   - **Role:** test.ap@bebang.ph
   - **Call:** `POST hrms.api.procurement.create_purchase_invoice`
   - **Payload:**
     ```json
     {
       "supplier": "Tech Supplies Inc.",
       "purchase_receipt": "<Purchase Receipt Name>",
       "items": [
         {
           "item_code": "MOUSE-001",
           "qty": 10,
           "rate": 600, 
           "purchase_receipt": "<Purchase Receipt Name>",
           "pr_detail": "<Purchase Receipt Item Name>"
         }
       ]
     }
     ```
   - **Assert:** 
     - Response: Validation Error / 3-Way Match Exception triggered.
     - Error Message contains: "Invoice rate (600) exceeds Purchase Order rate (500) beyond allowed tolerance."
     - DB: `Purchase Invoice.docstatus == 0` (Draft) or Not Created.

---

## Sprint 03 Integration Backbone Coverage

Use the dedicated flow scenario file for GAP-specific coverage of Sprint 03:

- `docs/testing/scenarios/flows/sprint-03-integration-backbone.md`

Registered IDs:

- `S03-006` AR Aging sync write/idempotency
- `S03-007` Inventory sync write/idempotency
- `S03-008` COA sync upsert/idempotency
- `S03-009` AP opening + supplier SOA route parity
- `S03-025` Bank account sync upsert/idempotency
- `S03-046` Critical alert dispatch and escalation metadata
- `S03-092` Pre-delivery billing exception enforcement (dual approval)

