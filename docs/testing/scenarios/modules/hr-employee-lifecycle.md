# HR Employee Lifecycle Module

<!-- Generated for S166 from docs/plans/2026-04-06-sprint-166-l3-employee-lifecycle-scenarios.md -->
<!-- 137 scenarios across 36 prefixes covering the full 19-stage employee lifecycle. -->
<!-- Chain convention: most scenarios chain off EMP-CREATE-001 (base test employee). EMP-CREATE-002 produces a second test employee. EMP-CREATE-010 produces a third (transfer destination). -->

## EMP-CREATE — New employee creation (S164 surface)

### EMP-CREATE-001: Create employee with mandatory fields only
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Call:** UI `/dashboard/hr/employee-master` → click "Add New Employee"
- **Payload:**
  ```json
  {
    "first_name": "<filipino-first>",
    "last_name": "<filipino-last>",
    "date_of_birth": "<past-date>",
    "gender": "<from-frappe-gender>",
    "branch": "<real-bei-branch-with-mapped-device>",
    "company": "Bebang Enterprise Inc"
  }
  ```
- **Assert:**
  - Toast: `Employee BEI-EMP-2026-XXXXX created. Bio ID 90XXXXX enrolled on device UDP...`
  - Evidence captures the real device SN from the toast
  - Row appears at top of Employee Master table after refetch
  - This is the BASE test employee for downstream scenarios

### EMP-CREATE-002: Create employee with all optional fields filled
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Call:** UI `/dashboard/hr/employee-master` → "Add New Employee"
- **Payload:**
  ```json
  {
    "first_name": "<filipino>",
    "middle_name": "<middle>",
    "last_name": "<last>",
    "date_of_birth": "<past>",
    "gender": "<gender>",
    "branch": "<branch>",
    "company": "Bebang Enterprise Inc",
    "designation": "<role>",
    "department": "<dept>",
    "date_of_joining": "<today>",
    "employment_type": "Probitionary",
    "personal_email": "<email>",
    "cell_number": "09171234567",
    "tin_number": "123-456-789-000",
    "sss_number": "12-3456789-0",
    "philhealth_number": "<num>",
    "pagibig_number": "<num>"
  }
  ```
- **Assert:**
  - Submit succeeds
  - Re-open employee via EmployeeDetailDialog: every field round-trips identically
  - This is the SECOND base test employee used by multi-employee scenarios

### EMP-CREATE-003: Default date_of_joining to today when blank
- **Type:** edge
- **Role:** test.hr@bebang.ph
- **Call:** UI Add New Employee with `date_of_joining` blank
- **Payload:** Same as EMP-CREATE-001 but no `date_of_joining`
- **Assert:** Employee created with `date_of_joining == today()`

### EMP-CREATE-004: Branch with no mapped biometric device
- **Type:** edge
- **Role:** test.hr@bebang.ph
- **Call:** UI Add New Employee with branch NOT in `DEVICE_TO_STORE`
- **Payload:** Standard mandatory fields, but `branch = <branch-without-device>`
- **Assert:**
  - Toast shows `No biometric device mapped to {branch} — enroll manually`
  - Employee still created
  - Captured API response: `adms_enrollment.reason == "NO_DEVICE_FOR_BRANCH"`

### EMP-CREATE-005: Upload TIN and SSS proof attachments at creation
- **Type:** edge
- **Role:** test.hr@bebang.ph
- **Call:** UI Add New Employee with file uploads
- **Payload:** Mandatory fields + attach real 150KB PDF (TIN) + 150KB JPG (SSS); leave PhilHealth/Pag-IBIG blank
- **Assert:**
  - 2 files uploaded to the new employee
  - Server fields `custom_tin_proof_url` and `custom_sss_proof_url` populated

### EMP-CREATE-006: Reject DOB in the future
- **Type:** adversarial
- **Role:** test.hr@bebang.ph
- **Call:** UI Add New Employee
- **Payload:** Mandatory fields with `date_of_birth = "2030-01-01"`
- **Assert:**
  - Dialog stays open
  - Backend returns 417 / ValidationError `date_of_birth must be in the past`
  - No employee created

### EMP-CREATE-007: Reject unknown gender value
- **Type:** adversarial
- **Role:** test.hr@bebang.ph
- **Call:** UI Add New Employee (force-select if needed)
- **Payload:** Mandatory fields with `gender = "NotAGender"`
- **Assert:**
  - Backend returns `Unknown gender: NotAGender`
  - No employee created

### EMP-CREATE-008: Crew cannot see "Add New Employee" button
- **Type:** rbac-ui
- **Role:** test.crew1@bebang.ph
- **Call:** GET `/dashboard/hr/employee-master`
- **Payload:** N/A
- **Assert:**
  - Either page returns Access Restricted OR loads without "Add New Employee" button visible in header
  - Capture screenshot as evidence

### EMP-CREATE-009: Crew blocked from create_employee_direct API
- **Type:** rbac-api
- **Role:** test.crew1@bebang.ph
- **Call:** `POST /api/frappe/api/method/hrms.api.employee_create.create_employee_direct`
- **Payload:** Valid create payload identical to EMP-CREATE-001
- **Assert:**
  - HTTP 403 / PermissionError
  - No employee created
  - Closes the visibility-only RBAC gap

### EMP-CREATE-010: Bio ID sequence must be exactly +1
- **Type:** regression
- **Role:** test.hr@bebang.ph
- **Call:** Two consecutive UI Add New Employee submissions
- **Payload:** Standard mandatory fields × 2 (third base test employee = transfer destination)
- **Assert:**
  - Second Bio ID == first Bio ID + 1
  - Guards against the 2026-02-26 L3 pollution pattern
  - This second employee is the TRANSFER DESTINATION test subject

## EMP-EDIT-PERSONAL — S160 personal section

### EMP-EDIT-PERSONAL-001: Add middle_name to existing employee
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog → Personal section → save
- **Payload:** `{"middle_name": "Dela Cruz"}`
- **Assert:** Persistence verified via subsequent GET AND via hard page reload

### EMP-EDIT-PERSONAL-002: Correct first_name typo
- **Type:** edge
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog Personal section
- **Payload:** `{"first_name": "<corrected>"}`
- **Assert:** `employee_name` recomputed downstream

### EMP-EDIT-PERSONAL-003: Correct date_of_birth
- **Type:** edge
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog Personal section
- **Payload:** `{"date_of_birth": "<corrected-past-date>"}`
- **Assert:** Save succeeds, value persisted

### EMP-EDIT-PERSONAL-004: Reject DOB change to future date
- **Type:** adversarial
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog Personal section
- **Payload:** `{"date_of_birth": "2031-01-01"}`
- **Assert:** Rejected, prior value remains

### EMP-EDIT-PERSONAL-005: Change gender via Frappe Gender DocType select
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog Personal section
- **Payload:** `{"gender": "<other-frappe-gender>"}`
- **Assert:** Change persisted; verify Gender values came from Frappe Gender DocType, not a hardcoded tuple

### EMP-EDIT-PERSONAL-006: Cancel discards unsaved changes
- **Type:** regression
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog Personal section → make a change → click Cancel
- **Payload:** Any change
- **Assert:** Re-open dialog and verify the change was NOT persisted

## EMP-EDIT-CONTACT — S160 contact + emergency contact

### EMP-EDIT-CONTACT-001: Add cell_number and personal_email
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog Contact section
- **Payload:** `{"cell_number": "09171234567", "personal_email": "<realistic>"}`
- **Assert:** Both fields persisted

### EMP-EDIT-CONTACT-002: Fill emergency contact
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog Emergency Contact
- **Payload:** `{"person_to_be_contacted": "<name>", "emergency_phone_number": "09171112222", "relation": "Spouse"}`
- **Assert:** Verified via GET

### EMP-EDIT-CONTACT-003: Reject malformed personal_email
- **Type:** adversarial
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog Contact
- **Payload:** `{"personal_email": "no-at-sign"}`
- **Assert:** Rejected; old value remains

### EMP-EDIT-CONTACT-004: Reject invalid cell_number
- **Type:** adversarial
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog Contact
- **Payload:** `{"cell_number": "abc12345"}`
- **Assert:** Rejected

## EMP-EDIT-ADDRESS — S160 addresses

### EMP-EDIT-ADDRESS-001: Fill current_address
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog Address section
- **Payload:** `{"current_address": "<street, barangay, city, ZIP>"}`
- **Assert:** Verified via GET and by re-opening the dialog

### EMP-EDIT-ADDRESS-002: Fill permanent_address (different from current)
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog Address section
- **Payload:** `{"permanent_address": "<different-from-current>"}`
- **Assert:** Both addresses stored separately

### EMP-EDIT-ADDRESS-003: "Same as current" checkbox copies address
- **Type:** edge
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog Address → click "same as current" checkbox if exists
- **Payload:** N/A (UI checkbox)
- **Assert:** If exists: permanent address copies from current. If not: document and SKIP with reason in evidence

## EMP-EDIT-EMPLOYMENT — S160 employment section

### EMP-EDIT-EMPLOYMENT-001: Change designation via selector
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog Employment section
- **Payload:** `{"designation": "<new-designation>"}`
- **Assert:** Employee Master table row reflects new designation after refetch

### EMP-EDIT-EMPLOYMENT-002: Change department via selector
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog Employment section
- **Payload:** `{"department": "<new-dept>"}`
- **Assert:** Persisted

### EMP-EDIT-EMPLOYMENT-003: Change reports_to
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog Employment section
- **Payload:** `{"reports_to": "<existing-employee>"}`
- **Assert:** `reports_to_name` computed field updates in masterlist row

### EMP-EDIT-EMPLOYMENT-004: Change employment_type direct edit
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog Employment section
- **Payload:** `{"employment_type": "Regular"}` (was "Probitionary")
- **Assert:** Persisted (mirrors regularization path but via direct field edit)

### EMP-EDIT-EMPLOYMENT-005: Hard reload persistence check
- **Type:** regression
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog → save → hard reload page → re-open dialog
- **Payload:** Any field change
- **Assert:** Change persisted (not just in-memory state)

## EMP-PHOTO — S160 profile photo

### EMP-PHOTO-001: Upload profile photo
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog → upload profile picture
- **Payload:** Real 150KB JPG from SKILL.md fixture
- **Assert:** `image` field populated; URL returns HTTP 200

### EMP-PHOTO-002: Replace profile photo
- **Type:** edge
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-PHOTO-001
- **Call:** UI EmployeeDetailDialog → upload different photo
- **Payload:** Different 150KB JPG
- **Assert:** `image` URL changed; document whether old photo file is deleted or orphaned

## EMP-BANK — S160 bank details

### EMP-BANK-001: Fill bank_name and bank_ac_no
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog Bank section
- **Payload:** `{"bank_name": "BDO Unibank", "bank_ac_no": "001234567890"}`
- **Assert:** Verified via GET

### EMP-BANK-002: Replace bank_ac_no
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-BANK-001
- **Call:** UI EmployeeDetailDialog Bank section
- **Payload:** `{"bank_ac_no": "<new-account>"}`
- **Assert:** Old value replaced

### EMP-BANK-003: Half-filled bank record behavior
- **Type:** adversarial
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog Bank section
- **Payload:** `{"bank_name": "BDO Unibank", "bank_ac_no": ""}`
- **Assert:** Document whether system rejects or accepts; either outcome captured for HR manual

## EMP-GOVID — S160 government IDs after creation

### EMP-GOVID-001: Fill TIN
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog Gov ID section
- **Payload:** `{"tin_number": "123-456-789-000"}`
- **Assert:** Persisted

### EMP-GOVID-002: Fill SSS
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog Gov ID section
- **Payload:** `{"sss_number": "12-3456789-0"}`
- **Assert:** Persisted

### EMP-GOVID-003: Fill PhilHealth and Pag-IBIG
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog Gov ID section
- **Payload:** `{"philhealth_number": "<num>", "pagibig_number": "<num>"}`
- **Assert:** Both persisted

### EMP-GOVID-004: Upload TIN proof PDF
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-GOVID-001
- **Call:** UI EmployeeDetailDialog Gov ID upload
- **Payload:** Real 150KB PDF
- **Assert:** `custom_tin_proof_url` populated; file accessible via GET

### EMP-GOVID-005: Replace TIN proof PDF
- **Type:** edge
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-GOVID-004
- **Call:** UI EmployeeDetailDialog Gov ID upload
- **Payload:** Different 150KB PDF
- **Assert:** URL changed; new file accessible

## EMP-SALARY-SETUP — Initial salary structure assignment

### EMP-SALARY-SETUP-001: Set up base compensation
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI EmployeeDetailDialog Compensation → "Set Up Compensation"
- **Payload:** Pick production Salary Structure template; `{"base": 25000}`
- **Assert:**
  - Initial state asserts "No salary structure"
  - Salary Structure Assignment created in Draft
  - Evidence includes SSA name and raw JSON

### EMP-SALARY-SETUP-002: Set up compensation with earnings components
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-002
- **Call:** UI Compensation setup
- **Payload:** Base + meal allowance + transportation allowance
- **Assert:** ALL components stored on the SSA, not just base

### EMP-SALARY-SETUP-003: Set up compensation with deductions
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-002
- **Call:** UI Compensation setup
- **Payload:** Base + SSS + PhilHealth + Pag-IBIG employee-share deductions
- **Assert:** Deduction components stored with correct amounts

### EMP-SALARY-SETUP-004: Formula-based component computes on save
- **Type:** edge
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-002
- **Call:** UI Compensation setup
- **Payload:** Base only; rely on template formula (e.g. "10% of base")
- **Assert:** Formula component computes correctly on save. If template has no formula components, document and SKIP

## EMP-SALARY-CHANGE — Change + approval + audit

### EMP-SALARY-CHANGE-001: Raise base salary
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-SALARY-SETUP-001
- **Call:** UI Compensation section → change base
- **Payload:** `{"base": 30000}` (was 25000)
- **Assert:**
  - Either (a) creates new SSA row OR (b) enters S114 sensitive-change approval queue
  - Capture exact API endpoint used

### EMP-SALARY-CHANGE-002: Finance approves sensitive change
- **Type:** happy
- **Role:** test.finance@bebang.ph
- **Depends on:** EMP-SALARY-CHANGE-001 (approval-queue path)
- **Call:** UI payroll sensitive-change approval queue → Approve
- **Payload:** `{"note": "<approval-note>"}`
- **Assert:**
  - Change applied to SSA
  - Queue item moved to Approved state

### EMP-SALARY-CHANGE-003: Change one component only
- **Type:** happy
- **Role:** test.hr@bebang.ph + test.finance@bebang.ph
- **Depends on:** EMP-SALARY-SETUP-002
- **Call:** UI Compensation section → change one component → submit → Finance approves
- **Payload:** `{"meal_allowance": 3000}` (was 2000)
- **Assert:** ONLY that component changed; other components untouched

### EMP-SALARY-CHANGE-004: Future-dated change
- **Type:** edge
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-SALARY-SETUP-001
- **Call:** UI Compensation section
- **Payload:** `{"base": 32000, "from_date": "<today+30d>"}`
- **Assert:**
  - SSA `from_date` set to future date
  - Current rate still in effect today
  - New rate would only apply from future date

### EMP-SALARY-CHANGE-005: Finance rejects sensitive change
- **Type:** happy
- **Role:** test.finance@bebang.ph
- **Depends on:** EMP-SALARY-CHANGE-001
- **Call:** UI payroll sensitive-change approval queue → Reject
- **Payload:** `{"note": "<rejection-reason>"}`
- **Assert:**
  - SSA stays at old amount (25000)
  - Queue item moves to Rejected state
  - Rejection note visible to HR

### EMP-SALARY-CHANGE-006: Reject invalid base values
- **Type:** adversarial
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-SALARY-SETUP-001
- **Call:** UI Compensation section × 3 attempts
- **Payload:** `{"base": -1000}`, then `{"base": 0}`, then `{"base": "abc"}`
- **Assert:** All 3 attempts rejected (validation layer)

## EMP-SALARY-PAYROLL — Downstream payroll integrity

### EMP-SALARY-PAYROLL-001: Approved raise reflected in next payroll
- **Type:** integration
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-SALARY-CHANGE-002
- **Call:** Trigger or wait for next payroll run including the test employee
- **Payload:** N/A (read generated Salary Slip)
- **Assert:**
  - `gross_pay` reflects NEW approved amount, not old one
  - This is the ONLY test that proves the approval queue wires through to payroll

### EMP-SALARY-PAYROLL-002: Future-dated change applies after effective date
- **Type:** integration
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-SALARY-CHANGE-004
- **Call:** Run payroll for current period BEFORE effective date, then for period AFTER
- **Payload:** N/A
- **Assert:**
  - Pre-effective period uses OLD rate
  - Post-effective period uses NEW rate

## EMP-REGULARIZE — Probationary → Regular transition

### EMP-REGULARIZE-001: Regularize probationary employee
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI `/dashboard/hr/performance/regularization` (per HRM-001 hint) → click Regularize
- **Payload:** N/A
- **Assert:**
  - `employment_type` transitions to "Regular"
  - `date_of_regularization` (or equivalent) stamped with today's date

### EMP-REGULARIZE-002: Regularization visible in employee detail
- **Type:** edge
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-REGULARIZE-001
- **Call:** UI EmployeeDetailDialog → Employment section
- **Payload:** N/A
- **Assert:**
  - Section shows "Regular" with regularization date visible
  - 13th-month-pay eligibility flag / computed field updated

### EMP-REGULARIZE-003: Future regularization date
- **Type:** adversarial
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-010
- **Call:** UI Regularization with future date
- **Payload:** `{"regularization_date": "<future>"}`
- **Assert:** Document behavior — rejection is PASS-rejection; acceptance verifies date stored correctly

## EMP-TRANSFER — Branch change chain

### EMP-TRANSFER-001: Create transfer request
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI `/dashboard/hr/transfers` → "Create Transfer"
- **Payload:** `{"employee": "<test-emp>", "from_branch": "<TRANSFER-FROM>", "to_branch": "<TRANSFER-TO>", "effective_date": "<today>"}`
- **Assert:** Transfer Request created in Pending state

### EMP-TRANSFER-002: Approve transfer
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-TRANSFER-001
- **Call:** UI Transfers → Approve
- **Payload:** N/A
- **Assert:** Employee `branch` field changes from FROM to TO

### EMP-TRANSFER-003: Device commands queued (delete OLD + add NEW)
- **Type:** integration
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-TRANSFER-002
- **Call:** Query `BEI Transfer Device Command` (or ADMS audit log)
- **Payload:** N/A
- **Assert:**
  - `DELETE USERINFO` queued for OLD device with employee's Bio ID
  - `USERINFO UPDATE` queued for NEW device with same Bio ID
  - Both must be present

### EMP-TRANSFER-004: Device commands actually dispatched
- **Type:** integration
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-TRANSFER-003
- **Call:** Wait up to 60 seconds; query command status
- **Payload:** N/A
- **Assert:** Both commands dispatched (ACK received OR status "Sent"). If async/slow, document observed latency

### EMP-TRANSFER-005: Masterlist filter reflects transfer
- **Type:** regression
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-TRANSFER-002
- **Call:** UI Employee Master filter by branch
- **Payload:** N/A
- **Assert:**
  - Filter by OLD branch: employee NOT in list
  - Filter by NEW branch: employee IS in list

## EMP-BIOCHANGE — Bio ID reassignment without branch change

### EMP-BIOCHANGE-001: Reassign Bio ID on same device
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-002
- **Call:** UI Bio ID reassignment (if exists)
- **Payload:** N/A
- **Assert:**
  - If supported: `DELETE USERINFO` for OLD Bio ID + `USERINFO UPDATE` for NEW Bio ID on SAME device
  - If not supported: document workflow and SKIP

### EMP-BIOCHANGE-002: Historical attendance still resolves
- **Type:** regression
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-BIOCHANGE-001
- **Call:** Query employee + attendance
- **Payload:** N/A
- **Assert:**
  - `attendance_device_id` shows new Bio ID
  - Historical attendance records still resolve via employee_id link (not Bio ID)

## EMP-COMPLETION — Cross-cutting data-quality metrics

### EMP-COMPLETION-001: missing_bio_id count unchanged after creation
- **Type:** regression
- **Role:** test.hr@bebang.ph
- **Call:** Capture `summary.missing_bio_id` BEFORE and AFTER EMP-CREATE-001
- **Payload:** N/A
- **Assert:** Count did NOT change (proves S164 auto-generation works end-to-end)

### EMP-COMPLETION-002: profile_completion increases after EDIT scenarios
- **Type:** regression
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001 + all EMP-EDIT-* scenarios
- **Call:** Read masterlist `profile_completion` for test employee BEFORE and AFTER all edit scenarios
- **Payload:** N/A
- **Assert:**
  - After creation: ~40-60%
  - After all edits: ≥137% (proves `hr_reports.py` formula recomputes on field fills)

## EMP-CONFLICT — Concurrent edit

### EMP-CONFLICT-001: Two-session simultaneous edit
- **Type:** adversarial
- **Role:** test.hr@bebang.ph (two browser sessions)
- **Depends on:** EMP-CREATE-001
- **Call:** Two browser contexts open employee dialog simultaneously
- **Payload:**
  - Context A: `{"cell_number": "09170000001"}`
  - Context B: `{"cell_number": "09170000002"}` (without refreshing)
- **Assert:** Either last-write-wins OR optimistic-lock conflict error. Document actual behavior

## EMP-ADMS — Initial enrollment propagation

### EMP-ADMS-001: USERINFO UPDATE queued for new employee
- **Type:** integration
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** Query `BEI Transfer Device Command` (or ADMS audit log) after creation
- **Payload:** N/A
- **Assert:**
  - `USERINFO UPDATE` queued for the new Bio ID on expected device SN
  - Capture both UI toast (showing device SN) and backend audit record

### EMP-ADMS-002: Command dispatched within 60 seconds
- **Type:** integration
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-ADMS-001
- **Call:** Poll command status for 60 seconds
- **Payload:** N/A
- **Assert:** Command actually dispatched (ACK or status "Sent"/"Success"). Document observed latency if slower

## EMP-CHAT — Google Chat notification verification

### EMP-CHAT-001: HR notifications space gets new-employee message
- **Type:** integration
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** Read latest message in `SPACE_NOTIFICATIONS` via /google skill Chat helper
- **Payload:** N/A
- **Assert:**
  - Message contains: `New Employee Created`, exact Employee ID, exact Bio ID, branch name, source `employee_master_dashboard`
  - Capture raw Chat message body as evidence

### EMP-CHAT-002: Message must NOT contain legacy onboarding line
- **Type:** regression
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CHAT-001
- **Call:** Read same Chat message
- **Payload:** N/A
- **Assert:** Message does NOT contain literal `Onboarding Request:` (S164 Task 1.4 HARD BLOCKER inverse)

## EMP-RBAC — Consolidated role-based access control

### EMP-RBAC-001: Crew cannot see Add New Employee button
- **Type:** rbac-ui
- **Role:** test.crew1@bebang.ph
- **Call:** GET `/dashboard/hr/employee-master`
- **Payload:** N/A
- **Assert:** Either Access Restricted OR loads without "Add New Employee" button. Capture screenshot

### EMP-RBAC-002: Crew blocked from create_employee_direct
- **Type:** rbac-api
- **Role:** test.crew1@bebang.ph
- **Call:** `POST /api/frappe/api/method/hrms.api.employee_create.create_employee_direct`
- **Payload:** Valid create payload
- **Assert:** HTTP 403 / PermissionError; no employee created

### EMP-RBAC-003: Crew blocked from frappe.client.set_value on cell_number
- **Type:** rbac-api
- **Role:** test.crew1@bebang.ph
- **Call:** `POST /api/frappe/api/method/frappe.client.set_value`
- **Payload:** `{"doctype": "Employee", "name": "<existing>", "fieldname": "cell_number", "value": "09171234567"}`
- **Assert:** HTTP 403 (proves field-level permissions block crew writes)

### EMP-RBAC-004: Finance role scope on Employee Master
- **Type:** rbac-ui
- **Role:** test.finance@bebang.ph
- **Call:** UI `/dashboard/hr/employee-master` then payroll sensitive-change queue
- **Payload:** N/A
- **Assert:**
  - Document whether "Add New Employee" is visible to finance
  - Salary approval queue: finance CAN see pending items

### EMP-RBAC-005: Crew sees no Save buttons or salary fields in dialog
- **Type:** rbac-ui
- **Role:** test.crew1@bebang.ph
- **Call:** UI Open EmployeeDetailDialog as crew
- **Payload:** N/A
- **Assert:**
  - Save buttons on personal/employment/compensation sections disabled OR hidden
  - Compensation amount field masked, hidden, or read-only

## EMP-TERMINATE — Full separation + clearance flow

### EMP-TERMINATE-001: Initiate separation
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-CREATE-001
- **Call:** UI separation/termination trigger (button on detail dialog OR `/dashboard/hr/separations`)
- **Payload:** `{"reason": "<reason>", "last_working_date": "<date>"}`
- **Assert:** `BEI Clearance` request (or equivalent DocType) created in Pending state

### EMP-TERMINATE-002: Assign clearance stations
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-TERMINATE-001
- **Call:** UI clearance request → assign stations
- **Payload:** Assign IT, POS, Uniform, Keys (per Phase 0 list)
- **Assert:** Station list persisted (auto-assigned or manual)

### EMP-TERMINATE-003: Upload clearance items
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-TERMINATE-002
- **Call:** UI clearance station sign-offs
- **Payload:** Upload real 150KB files where applicable; sign-off notes
- **Assert:** All items stored on the clearance record

### EMP-TERMINATE-004: Documenso e-signature flow
- **Type:** integration
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-TERMINATE-003
- **Call:** Trigger Documenso e-signature for clearance form
- **Payload:** N/A
- **Assert:**
  - Documenso document created (HEAD/GET on Documenso API)
  - sign.bebang.ph returns valid signing URL
  - If unreachable: document blocker, do not auto-fail sprint

### EMP-TERMINATE-005: Approve clearance and transition status
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-TERMINATE-004
- **Call:** UI Approve clearance
- **Payload:** N/A
- **Assert:** Employee `status` transitions Active → Left with correct `relieving_date`

### EMP-TERMINATE-006: Masterlist filter reflects termination
- **Type:** regression
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-TERMINATE-005
- **Call:** UI Employee Master filter by status
- **Payload:** N/A
- **Assert:** Filter Active: NOT in list. Filter Left: IS in list

## EMP-FINALPAY — Last payslip and BIR 2316

### EMP-FINALPAY-001: Generate final salary slip
- **Type:** integration
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-TERMINATE-005
- **Call:** Trigger final pay calculation or wait for next payroll run
- **Payload:** N/A
- **Assert:**
  - Final Salary Slip generated with: pro-rated basic pay based on `relieving_date`, unused leave conversion (if applicable), final deductions
  - Capture raw Salary Slip JSON

### EMP-FINALPAY-002: BIR 2316 generation
- **Type:** integration
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-FINALPAY-001
- **Call:** Trigger BIR 2316 generation if feature exists
- **Payload:** N/A
- **Assert:** Form created and accessible. If feature missing: document and SKIP

### EMP-FINALPAY-003: Mark final pay released
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-FINALPAY-001
- **Call:** UI mark final pay as Released/Paid
- **Payload:** N/A
- **Assert:**
  - Payroll record shows released
  - Clearance record shows final-pay step complete

## EMP-USERDISABLE — Account disable verification

### EMP-USERDISABLE-001: User account disabled after termination
- **Type:** integration
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-TERMINATE-005
- **Call:** Query User DocType for terminated employee's `user_id`
- **Payload:** N/A
- **Assert:** `enabled == 0`. If not auto-disabled: log to DEFECTS.csv as HIGH defect and continue

### EMP-USERDISABLE-002: Ex-employee cannot log in
- **Type:** adversarial
- **Role:** (ex-employee credentials)
- **Depends on:** EMP-USERDISABLE-001
- **Call:** Login attempt at `my.bebang.ph` with terminated credentials
- **Payload:** N/A
- **Assert:** Login fails. If succeeds: log to DEFECTS.csv as CRITICAL and STOP sprint for user decision

## EMP-ADMSREMOVE — Bio ID removal from device

### EMP-ADMSREMOVE-001: DELETE USERINFO queued on termination
- **Type:** integration
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-TERMINATE-005
- **Call:** Query `BEI Transfer Device Command` (or ADMS audit log)
- **Payload:** N/A
- **Assert:** `DELETE USERINFO` queued for terminated employee's Bio ID on last-known device SN. If absent: log HIGH defect

### EMP-ADMSREMOVE-002: DELETE USERINFO actually dispatched
- **Type:** integration
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-ADMSREMOVE-001
- **Call:** Poll command status within 60 seconds
- **Payload:** N/A
- **Assert:** Command dispatched within 60s. If indefinite Pending: defect

## EMP-REHIRE — Re-activation path

### EMP-REHIRE-001: Re-hire ex-employee
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-USERDISABLE-002
- **Call:** UI re-activate or re-create
- **Payload:** N/A
- **Assert:** Document path:
  - (a) Re-activate existing record: status Active, new date_of_joining, audit log shows re-activation
  - (b) New record via EMP-CREATE flow: NEW Employee record created, no dupe collision

### EMP-REHIRE-002: Bio ID handling on re-hire
- **Type:** regression
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-REHIRE-001
- **Call:** Verify Bio ID and ADMS device commands
- **Payload:** N/A
- **Assert:**
  - Path (a): original Bio ID reassigned and pushed back (USERINFO UPDATE queued)
  - Path (b): fresh new Bio ID generated

## EMP-LEAVE — Leave application + approval

> Self-service leave uses test.crew1@bebang.ph; supervisor approval uses test.supervisor@bebang.ph.

### EMP-LEAVE-001: Apply 1-day leave
- **Type:** happy
- **Role:** test.crew1@bebang.ph
- **Call:** UI `/dashboard/hr/leave` → "Apply Leave"
- **Payload:** `{"leave_type": "Casual Leave", "from_date": "<tomorrow>", "to_date": "<tomorrow>", "reason": "<text>"}`
- **Assert:**
  - Toast success
  - Leave appears in "My Leaves" list with status Open/Pending
  - Capture leave request name

### EMP-LEAVE-002: Supervisor approves leave
- **Type:** happy
- **Role:** test.supervisor@bebang.ph
- **Depends on:** EMP-LEAVE-001
- **Call:** UI leave approval queue
- **Payload:** N/A
- **Assert:** Status transitions to Approved

### EMP-LEAVE-003: Leave balance decreased
- **Type:** regression
- **Role:** test.crew1@bebang.ph
- **Depends on:** EMP-LEAVE-002
- **Call:** UI re-open leave page as employee
- **Payload:** N/A
- **Assert:**
  - Leave shows status Approved
  - Leave balance decreased by 1 day for the leave type used
  - Capture before/after balance

### EMP-LEAVE-004: Supervisor rejects second leave
- **Type:** happy
- **Role:** test.crew1@bebang.ph + test.supervisor@bebang.ph
- **Call:** Apply second leave (different dates) → supervisor rejects with note
- **Payload:** `{"leave_type": "Casual Leave", "from_date": "<other>", "to_date": "<other>"}` then rejection note
- **Assert:**
  - Status Rejected
  - Leave balance did NOT decrease
  - Rejection note visible to employee

### EMP-LEAVE-005: Cancel pending leave
- **Type:** edge
- **Role:** test.crew1@bebang.ph
- **Call:** Apply a leave then cancel before supervisor action
- **Payload:** N/A
- **Assert:** Cancellation succeeds; leave disappears from pending list. If unsupported: document actual behavior

## EMP-OVERTIME — OT filing + approval

### EMP-OVERTIME-001: File overtime request
- **Type:** happy
- **Role:** test.crew1@bebang.ph (or test.supervisor)
- **Call:** UI `/dashboard/hr/overtime`
- **Payload:** `{"date": "<date>", "hours": 2, "ot_type": "Regular OT"}`
- **Assert:** OT request appears with status Pending/Open

### EMP-OVERTIME-002: HR approves OT
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-OVERTIME-001
- **Call:** UI overtime page → Approve
- **Payload:** `{"approved_payable_duration": 2, "approved_overtime_type": "Regular OT"}`
- **Assert:** Status transitions to Approved; `approved_payable_duration` matches input

### EMP-OVERTIME-003: HR rejects OT
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Call:** File second OT then reject
- **Payload:** Rejection note
- **Assert:** Status Rejected; rejection note visible

### EMP-OVERTIME-004: Approved OT in payroll
- **Type:** regression
- **Role:** test.crew1@bebang.ph
- **Depends on:** EMP-OVERTIME-002
- **Call:** Check payroll processing page next payroll period
- **Payload:** N/A
- **Assert:** OT hours appear as earning line. Document expected payroll cycle if dates differ

## EMP-ATTENDANCE — Correction request + approval

### EMP-ATTENDANCE-001: File attendance correction
- **Type:** happy
- **Role:** test.crew1@bebang.ph
- **Call:** UI `/dashboard/hr/attendance-correction`
- **Payload:** `{"date": "<past>", "type": "Late In", "reason": "<text>", "evidence": "<150KB-file-optional>"}`
- **Assert:** Correction request appears with status Pending

### EMP-ATTENDANCE-002: Supervisor approves correction
- **Type:** happy
- **Role:** test.supervisor@bebang.ph
- **Depends on:** EMP-ATTENDANCE-001
- **Call:** UI approval queue
- **Payload:** N/A
- **Assert:** Status transitions to Approved

### EMP-ATTENDANCE-003: Attendance record reflects correction
- **Type:** regression
- **Role:** test.crew1@bebang.ph
- **Depends on:** EMP-ATTENDANCE-002
- **Call:** UI attendance page
- **Payload:** N/A
- **Assert:** Actual attendance record for that date reflects the correction. Capture before/after

## EMP-PAYROLL-RUN — Full HR-driven payroll processing cycle

### EMP-PAYROLL-RUN-001: Process payroll for current period
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Call:** UI `/dashboard/hr/payroll/processing` → "Process Payroll" / "Create Salary Slips"
- **Payload:** N/A
- **Assert:**
  - Run initiates and completes
  - Test employee (EMP-CREATE-001) has a Salary Slip in output

### EMP-PAYROLL-RUN-002: Review salary slip output
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-PAYROLL-RUN-001
- **Call:** UI `/dashboard/hr/payroll/review-output`
- **Payload:** N/A
- **Assert:**
  - `gross_pay` matches SSA from EMP-SALARY-CHANGE-002 (approved raise amount)
  - Deductions present: SSS, PhilHealth, Pag-IBIG, BIR withholding
  - `net_pay == gross - deductions`
  - Capture full Salary Slip JSON

### EMP-PAYROLL-RUN-003: OT earning line in payslip
- **Type:** edge
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-PAYROLL-RUN-002
- **Call:** Inspect Salary Slip for OT earning
- **Payload:** N/A
- **Assert:** If approved OT (EMP-OVERTIME-002) falls in this period: OT earning line present. Else document and SKIP

### EMP-PAYROLL-RUN-004: Period-over-period comparison page
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-PAYROLL-RUN-002
- **Call:** UI `/dashboard/hr/payroll/comparison`
- **Payload:** N/A
- **Assert:** Comparison view loads and shows data for current period. Screenshot

### EMP-PAYROLL-RUN-005: Remittance summaries
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-PAYROLL-RUN-002
- **Call:** UI `/dashboard/hr/payroll/remittances`
- **Payload:** N/A
- **Assert:** SSS, PhilHealth, Pag-IBIG, BIR remittances generated. Test employee contribution appears in totals

### EMP-PAYROLL-RUN-006: Payroll history page
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-PAYROLL-RUN-002
- **Call:** UI `/dashboard/hr/payroll/history`
- **Payload:** N/A
- **Assert:** Current period's payroll run appears in history with correct status and summary counts

## EMP-PAYSLIP — Employee self-service payslip view

### EMP-PAYSLIP-001: View own payslip
- **Type:** happy
- **Role:** test.crew1@bebang.ph
- **Call:** UI `/dashboard/hr/payslip`
- **Payload:** N/A
- **Assert:**
  - Page loads showing logged-in employee's own payslips
  - Most recent payslip shows: gross_pay, net_pay, earning lines, deduction lines, payroll period
  - Screenshot

### EMP-PAYSLIP-002: Cannot view other employees' payslips
- **Type:** rbac
- **Role:** test.crew1@bebang.ph
- **Call:** UI/URL manipulation to access another employee's payslip
- **Payload:** Different employee_id in URL
- **Assert:** System blocks access — only own payslips visible

## EMP-DISCIPLINARY — HR memo → response → resolve

### EMP-DISCIPLINARY-001: Create disciplinary case
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Call:** UI `/dashboard/hr/disciplinary` → New Case
- **Payload:** `{"employee": "<test-emp>", "violation": "<category>", "action_type": "Written Warning", "description": "<text>", "incident_date": "<date>"}`
- **Assert:** Case created with case ID

### EMP-DISCIPLINARY-002: Open case and issue memo
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-DISCIPLINARY-001
- **Call:** UI `/dashboard/hr/disciplinary/[id]` → Issue Memo / Send NTE
- **Payload:** N/A
- **Assert:** Fields displayed correctly; memo/NTE status updates

### EMP-DISCIPLINARY-003: Record employee response
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-DISCIPLINARY-002
- **Call:** UI Record Employee Response form (or test.crew1 if self-service)
- **Payload:** `{"response": "<text>"}`
- **Assert:** Response saved. If requires self-service from test employee with no user account: document and SKIP

### EMP-DISCIPLINARY-004: Resolve case
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-DISCIPLINARY-003
- **Call:** UI Resolve case
- **Payload:** `{"resolution": "Warning Issued"}` (or Suspension / Recommend Termination)
- **Assert:**
  - Case status transitions Resolved/Closed
  - If suspension: employee status changes to Suspended or suspension flag set

### EMP-DISCIPLINARY-005: Case visible in list and history
- **Type:** regression
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-DISCIPLINARY-004
- **Call:** UI disciplinary main list + employee detail dialog
- **Payload:** N/A
- **Assert:**
  - Resolved case appears with correct final status
  - Employee detail dialog shows disciplinary record in history/related section

## EMP-EXITINTERVIEW — Exit interview + analytics

### EMP-EXITINTERVIEW-001: Submit exit interview
- **Type:** happy
- **Role:** test.hr@bebang.ph (or employee if self-service)
- **Depends on:** EMP-TERMINATE-005
- **Call:** UI exit interview form (`/clearance/exit-interview` or `/dashboard/hr/exit-interview/[id]`)
- **Payload:** All survey questions filled (ratings, text responses, reason for leaving)
- **Assert:** Interview saved

### EMP-EXITINTERVIEW-002: Analytics page reflects new interview
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-EXITINTERVIEW-001
- **Call:** UI `/dashboard/hr/exit-interview/analytics`
- **Payload:** N/A
- **Assert:** Analytics loads; charts/tables show one more response than before

### EMP-EXITINTERVIEW-003: Responses persisted
- **Type:** regression
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-EXITINTERVIEW-001
- **Call:** Re-open the specific exit interview record
- **Payload:** N/A
- **Assert:** All responses persisted correctly — no data loss

## EMP-COMPLIANCE — 13th month computation

### EMP-COMPLIANCE-001: 13th month list shows regularized employee
- **Type:** integration
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-REGULARIZE-001
- **Call:** UI `/dashboard/hr/compliance/13th-month` → Compute (or view existing)
- **Payload:** N/A
- **Assert:** Regularized test employee appears with computed amount > 0. If feature only runs at year-end: document and SKIP, but capture page-load evidence

### EMP-COMPLIANCE-002: 13th month pro-rated from regularization date
- **Type:** regression
- **Role:** test.hr@bebang.ph
- **Depends on:** EMP-COMPLIANCE-001
- **Call:** Inspect computed amount
- **Payload:** N/A
- **Assert:** Amount pro-rated from regularization date (not full year). If not: capture actual behavior

## EMP-ENRICHMENT — Enrichment tracker

### EMP-ENRICHMENT-001: Enrichment tracker baseline snapshot
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Call:** UI `/dashboard/hr/enrichment-tracker`
- **Payload:** N/A
- **Assert:**
  - Page loads showing enrichment statuses
  - Test employee (EMP-CREATE-001) shows lower enrichment status
  - Capture current enrichment status + percentage

### EMP-ENRICHMENT-002: Enrichment tracker increases after edits
- **Type:** regression
- **Role:** test.hr@bebang.ph
- **Depends on:** all EMP-EDIT-* scenarios complete
- **Call:** UI re-open enrichment tracker
- **Payload:** N/A
- **Assert:** Test employee enrichment status/percentage increased vs EMP-ENRICHMENT-001 snapshot

## EMP-UX — Document UX gaps found by audit agents

> These scenarios document gaps as test evidence so DEFECTS.csv yields a prioritized backlog.

### EMP-UX-001: Attendance page is self-service only
- **Type:** ux-gap
- **Role:** test.hr@bebang.ph
- **Call:** UI `/dashboard/hr/attendance`
- **Payload:** N/A
- **Assert:**
  - Page shows "My Attendance" not org-wide dashboard
  - No store/branch filters present
  - Log CRITICAL defect: "Attendance page is self-service only for HR role — cannot view org-wide attendance for 47 stores"

### EMP-UX-002: Schedule page is self-service only
- **Type:** ux-gap
- **Role:** test.hr@bebang.ph
- **Call:** UI `/dashboard/hr/schedule`
- **Payload:** N/A
- **Assert:**
  - Page shows "My Schedule" not shift assignment grid
  - No "Assign Shift" or "Bulk Assign" buttons
  - Log CRITICAL defect: "Schedule page is self-service only — cannot manage shifts for 700 employees"

### EMP-UX-003: Attendance correction has no admin review queue
- **Type:** ux-gap
- **Role:** test.hr@bebang.ph
- **Call:** UI `/dashboard/hr/attendance-correction`
- **Payload:** N/A
- **Assert:**
  - Page shows employee submission form, no admin review queue
  - No "Pending Corrections" / "Review Queue" sections
  - Log CRITICAL defect: "Attendance correction has no admin review queue — HR cannot approve/reject submitted corrections"

### EMP-UX-004: Compensation detail modal broken
- **Type:** ux-gap
- **Role:** test.hr@bebang.ph
- **Call:** UI `/dashboard/hr/payroll/compensation-setup` → click any employee row
- **Payload:** N/A
- **Assert:**
  - Modal is empty or shows only Bio ID
  - No salary components, no edit fields
  - Screenshot
  - Log CRITICAL defect: "Compensation detail modal is broken — HR cannot view or edit individual salary from the portal"

### EMP-UX-005: Sensitive-changes page has no Approve/Reject buttons
- **Type:** ux-gap
- **Role:** test.finance@bebang.ph
- **Call:** UI `/dashboard/hr/payroll/sensitive-changes`
- **Payload:** N/A
- **Assert:**
  - Pending change row has no visible Approve or Reject buttons
  - Screenshot
  - Log CRITICAL defect: "Finance cannot approve/reject sensitive salary changes from the UI — dual-control workflow is broken"

### EMP-UX-006: Sidebar bloat for crew role
- **Type:** ux-gap
- **Role:** test.crew1@bebang.ph
- **Call:** UI sidebar inspection
- **Payload:** N/A
- **Assert:**
  - Sidebar nav item count ≥15
  - Visit 5 items, ≥3 return Access Restricted
  - Screenshot
  - Log HIGH defect: "Sidebar shows 19 nav groups to crew role, most lead to Access Restricted pages"

### EMP-UX-007: No payslip download/print
- **Type:** ux-gap
- **Role:** test.crew1@bebang.ph
- **Call:** UI `/dashboard/hr/payslip` → most recent payslip
- **Payload:** N/A
- **Assert:**
  - No "Download PDF", "Print", or "Export" button
  - Screenshot
  - Log MEDIUM defect: "Crew cannot download or print their own payslip"

### EMP-UX-008: No notification system
- **Type:** ux-gap
- **Role:** test.crew1@bebang.ph
- **Call:** After filing leave/OT/correction, look for notification bell anywhere in UI; wait 30s and refresh
- **Payload:** N/A
- **Assert:**
  - No notification bell or inbox indicator
  - Log MEDIUM defect: "No notification system exists. Employees cannot know if their requests were approved without manually polling the page"

### EMP-UX-009: OT approval cannot specify approved hours
- **Type:** ux-gap
- **Role:** test.hr@bebang.ph
- **Call:** UI `/dashboard/hr/overtime` → click Approve on pending request
- **Payload:** N/A
- **Assert:**
  - Approve dialog has no "Approved Hours" input
  - Approval is all-or-nothing
  - Log HIGH defect: "Overtime approval cannot specify approved hours — must fully approve or reject"

### EMP-UX-010: No branch-level payroll processing
- **Type:** ux-gap
- **Role:** test.hr@bebang.ph
- **Call:** UI `/dashboard/hr/payroll/processing`
- **Payload:** N/A
- **Assert:**
  - No branch-level filter or "Process by Branch" option
  - Wizard processes entire company (700 employees) at once
  - Log HIGH defect: "No branch-level payroll processing — HR must run all 700 employees at once"

## EMP-STUB — Visit and document stub pages

### EMP-STUB-001: HR Reports page is a stub
- **Type:** stub-document
- **Role:** test.hr@bebang.ph
- **Call:** UI `/dashboard/hr/reports`
- **Payload:** Click each of 8 report tiles
- **Assert:**
  - Page loads with 8 report tiles (Employee Masterlist, Headcount, Attrition, New Hires, Separations, Recruitment Funnel, Attendance Summary, Overtime Report)
  - NONE navigate to a working report
  - Capture click outcomes
  - Log CRITICAL defect: "HR Reports page is a stub — all 8 report tiles are non-functional"

### EMP-STUB-002: Training module is read-only
- **Type:** stub-document
- **Role:** test.hr@bebang.ph
- **Call:** UI `/dashboard/hr/training`
- **Payload:** N/A
- **Assert:**
  - Page loads
  - No "Create Training Program" button
  - Page contains text referring users to Frappe Desk for training creation
  - Log HIGH defect: "Training module is read-only — page explicitly says to create programs in Frappe"

### EMP-STUB-003: Performance Review module read-only
- **Type:** stub-document
- **Role:** test.hr@bebang.ph
- **Call:** UI `/dashboard/hr/performance`
- **Payload:** N/A
- **Assert:**
  - No "Create Review Cycle" or "Assign Reviewers" button
  - Only Regularization sub-module is functional
  - Log MEDIUM defect: "Performance Review module is read-only — cannot create evaluation cycles"

### EMP-STUB-004: Disciplinary case detail renders blank
- **Type:** stub-document
- **Role:** test.hr@bebang.ph
- **Call:** UI `/dashboard/hr/disciplinary` → click first case to open detail
- **Payload:** N/A
- **Assert:**
  - Detail page renders BLANK (empty skeleton cards, no content)
  - Screenshot
  - Log HIGH defect: "Disciplinary case detail page renders blank — cases cannot be managed after creation"

### EMP-STUB-005: Clearance module is read-only milestone tracker
- **Type:** stub-document
- **Role:** test.hr@bebang.ph
- **Call:** UI `/clearance`
- **Payload:** N/A
- **Assert:**
  - Page shows read-only milestone tracker (Exit Interview / Final Pay / COE)
  - No clearance stations, no item return tracking, no Documenso integration
  - Screenshot
  - Log CRITICAL defect: "Clearance module is a read-only milestone tracker — no real clearance functionality exists"

## EMP-CLEAN — Final cleanup sweep

### EMP-CLEAN-001: Mark non-terminated test employees as Left
- **Type:** cleanup
- **Role:** test.hr@bebang.ph
- **Call:** UI EmployeeDetailDialog for each tracked test employee
- **Payload:** `{"status": "Left", "relieving_date": "<today>"}`
- **Assert:** Each employee status set to Left. NEVER hard-delete

### EMP-CLEAN-002: Final audit query — zero stragglers
- **Type:** cleanup
- **Role:** test.hr@bebang.ph
- **Call:** SQL `SELECT COUNT(*) AS n FROM tabEmployee WHERE name LIKE 'BEI-EMP-2026-%' AND status = 'Active' AND employee_name LIKE '%L3 2026-04-06%'`
- **Payload:** N/A
- **Assert:** Returns 0. Non-zero = FAIL sprint and list stragglers in SUMMARY.md

### EMP-CLEAN-003: Bio ID pollution check
- **Type:** cleanup
- **Role:** test.hr@bebang.ph
- **Call:** SQL `SELECT MAX(CAST(attendance_device_id AS UNSIGNED)) FROM tabEmployee WHERE attendance_device_id REGEXP '^9[0-9]{6}$'`
- **Payload:** N/A
- **Assert:**
  - Max ≤ Phase 0 baseline + EMP-CREATE scenario count (~9001882 + 10 = ~9001892)
  - If significantly higher: run `scripts/s164_fix_bio_id_outliers.py` pattern before marking sprint complete
  - Anti-regression check vs 2026-02-26 pollution
