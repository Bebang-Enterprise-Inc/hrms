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
