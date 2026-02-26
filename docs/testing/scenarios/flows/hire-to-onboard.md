# Hire To Onboard Flow

Status: `ready`
Prefix: `HTO`

This flow closes recruitment, onboarding, and clearance lifecycle checkpoints using currently implemented backend APIs.

### HTO-001: HR creates manpower request form
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Call:** `POST hrms.api.recruitment.create_mrf`
- **Payload:**
  ```json
  {
    "requesting_department": "Operations - BEI",
    "position_title": "Store Crew",
    "designation": "<valid_designation_name>",
    "department": "Operations - BEI",
    "number_of_vacancies": 1,
    "reason": "Replacement",
    "preferred_start_date": "2026-03-05",
    "job_description": "Replacement hire for active store operations.",
    "justification": "Replacement needed to maintain staffing baseline."
  }
  ```
- **Assert:**
  - Response returns `name` and non-empty `status`.
  - Created MRF is persisted and queryable from MRF list endpoint.

### HTO-002: HR approves MRF to progress recruitment pipeline
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Call:** `POST hrms.api.recruitment.approve_mrf`
- **Payload:**
  ```json
  {
    "mrf_name": "<mrf_name_from_hto_001>",
    "action": "approve",
    "notes": "Approved for recruitment processing."
  }
  ```
- **Assert:**
  - Response returns updated status (`Pending CEO` or `Approved` based on designation level).
  - MRF status change is persisted.

### HTO-003: HR tracks recruitment stage movement
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Call:** `POST hrms.api.recruitment.update_applicant_stage`
- **Payload:**
  ```json
  {
    "applicant_name": "<existing_job_applicant_name>",
    "stage": "Screening",
    "notes": "Initial HR screening completed."
  }
  ```
- **Assert:**
  - Response returns updated applicant stage mapping.
  - Recruitment pipeline endpoint reflects new stage count.

### HTO-004: Supervisor/HR creates onboarding session and submits onboarding request
- **Type:** happy
- **Role:** test.supervisor@bebang.ph
- **Calls:**
  - `POST hrms.api.onboarding.create_session`
  - `POST hrms.api.onboarding.submit_request`
- **Payload (submit_request):**
  ```json
  {
    "token": "<token_from_create_session>",
    "request_type": "new_hire",
    "requested_changes": "{\"first_name\":\"Flow\",\"last_name\":\"Candidate\",\"branch\":\"TEST-STORE-BGC - BEI\",\"department\":\"Operations - BEI\",\"designation\":\"<valid_designation_name>\",\"date_of_joining\":\"2026-03-05\",\"new_attendance_device_id\":\"9001901\"}"
  }
  ```
- **Assert:**
  - Session creation returns active token.
  - Onboarding request is created in `Pending` status.

### HTO-005: HR approves onboarding request and applies employee creation
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Call:** `POST hrms.api.onboarding.approve_and_apply`
- **Payload:**
  ```json
  {
    "request_name": "<request_name_from_hto_004>",
    "approver_email": "test.hr@bebang.ph",
    "decision": "approve",
    "approver_notes": "Approved onboarding payload."
  }
  ```
- **Assert:**
  - Response succeeds with status `Applied` for successful application.
  - Onboarding request records approver and applied timestamp.
  - Employee creation path does not return `EMPLOYEE_CREATE_FAILED`.

### HTO-006: Separation and clearance endpoints remain available for employee lifecycle closeout
- **Type:** happy
- **Role:** test.hr@bebang.ph
- **Calls:**
  - `POST hrms.api.employee_clearance.create_employee_separation`
  - `GET hrms.api.employee_clearance.get_clearance_status`
- **Payload (create_employee_separation):**
  ```json
  {
    "employee": "<existing_employee_id>",
    "separation_type": "Resignation",
    "separation_reason": "Flow validation",
    "boarding_begins_on": "2026-03-10"
  }
  ```
- **Assert:**
  - Separation document is created and returns success.
  - Clearance status endpoint returns lifecycle progress object for the employee.
  - No runtime exception occurs on DOLE checklist initialization.
