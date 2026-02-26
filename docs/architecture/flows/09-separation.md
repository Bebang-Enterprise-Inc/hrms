# Flow 09: Employee Separation / Clearance
**Departments:** HR → All Departments (DOLE compliance signatories) → Finance (final pay) | **Scanned:** 2026-02-23 | **Agent:** flow-tracer-3

## Flow Diagram (Mermaid)

```mermaid
sequenceDiagram
    participant Employee as Employee
    participant HR as HR Manager/User
    participant HRDash as /dashboard/hr/
    participant ClearPage as /clearance/page.tsx (my.bebang.ph)
    participant ExitPage as /clearance/exit-interview/
    participant ClearAPI as employee_clearance.py API
    participant SepDT as Employee Separation (Frappe)
    participant DoleDT as BEI DOLE Compliance (child)
    participant SepHook as on_separation_created hook
    participant UpdHook as on_separation_updated hook
    participant GChat as Google Chat (HR space)
    participant ADMS as ADMS Receiver (localhost:8080)
    participant Finance as Finance

    HR->>HRDash: Initiate separation (no dedicated HR page found)
    HR->>ClearAPI: create_employee_separation(employee, type, reason, begins_on)
    ClearAPI->>SepDT: INSERT (company from Employee, boarding_begins_on)
    ClearAPI->>ClearAPI: populate_dole_compliance(sep_name, sep_type)
    ClearAPI->>DoleDT: Query BEI DOLE Compliance Item for sep_type; append to custom_dole_compliance child table

    SepDT-->>SepHook: after_insert fires
    SepHook->>GChat: "Employee Separation Created — Action required: complete clearance items"

    Employee->>ClearPage: View own clearance status
    ClearPage->>ClearAPI: get_my_separation()
    ClearAPI-->>Employee: Separation details, compliance progress (%), milestones

    Employee->>ExitPage: Complete exit interview questionnaire
    ExitPage->>ClearAPI: get_exit_interview_questions()
    ClearAPI-->>Employee: Questions grouped by category
    Employee->>ExitPage: Submit responses
    ExitPage->>ClearAPI: submit_exit_interview_responses(exit_interview, responses)
    ClearAPI->>SepDT: custom_questionnaire_responses child table updated

    HR->>HRDash: Process clearance items (e.g. IT clearance, property return, etc.)
    HR->>ClearAPI: update_compliance_status(sep_name, row_name, status, notes, document)
    ClearAPI->>DoleDT: row.status = Completed, completed_date, completed_by

    Note over UpdHook: On every save of Employee Separation...
    SepDT-->>UpdHook: on_update fires
    UpdHook->>UpdHook: Check if ALL compliance items are Completed/Not Applicable
    alt All clearance items done
        UpdHook->>GChat: "Clearance Complete — Final Pay Pending. Finance: proceed with final pay."
    else Not all done
        UpdHook->>UpdHook: No action
    end

    HR->>ClearAPI: disable_bio_id(employee, removal_reason)
    ClearAPI->>ADMS: POST /admin/user/{bio_id}/disable
    ADMS-->>ClearAPI: devices_queued count
    ClearAPI->>SepDT: Frappe Comment added: "Bio ID {X} disabled: N devices queued"

    HR->>ClearAPI: generate_coe(employee)
    ClearAPI->>SepDT: custom_coe_generated = 1, save
    ClearAPI-->>HR: pdf_url (Frappe print format URL)

    Employee->>ClearPage: Click "Download COE"
    ClearPage->>ClearAPI: requestCOE(employee)
    ClearAPI-->>Employee: COE PDF download URL

    Finance->>SepDT: Manually set custom_final_pay_approved = 1 via Frappe Desk (no API endpoint)
    HR->>SepDT: Manually set Employee.status = "Left" via Frappe Desk (no API endpoint)
```

## Step-by-Step Trace

| Step | Actor | Action | Frontend Page | API Endpoint | DocType Created/Updated | Status |
|------|-------|--------|---------------|-------------|------------------------|--------|
| 1 | HR Manager | Initiate employee separation: choose type (Resignation/Termination/AWOL/Probation Failure/End of Contract/Retirement) | No dedicated HR management page found in `/dashboard/hr/` for creating separations. Separation can be created via API call or Frappe Desk. | `employee_clearance.create_employee_separation` | Employee Separation (INSERT — Frappe standard DocType with BEI custom fields: custom_separation_type, custom_separation_reason) | LIVE — but no HR management UI; HR must use direct API call or Frappe Desk |
| 2 | System (auto) | Auto-populate DOLE compliance checklist based on separation type | Auto-called inside `create_employee_separation` | `employee_clearance.populate_dole_compliance` | Employee Separation (custom_dole_compliance child table populated from BEI DOLE Compliance Item + BEI Separation Type Item join; all items status=Pending) | LIVE |
| 3 | System (hook) | GChat notification to HR space: "Separation created, action required" | (Background) | `on_separation_created` (hooks.py after_insert) | Frappe Comment; GChat message to `BEI Settings.gchat_notification_space` | LIVE — silently falls back if GChat not configured |
| 4 | Employee | View own clearance status, compliance progress %, and milestone flags | `/clearance/` (standalone, not `/dashboard/`) | `employee_clearance.get_my_separation` | Employee Separation, BEI DOLE Compliance Checklist (read) | LIVE |
| 5 | Employee | Complete exit interview questionnaire (questions grouped by category: Scale 1-5 / Yes-No / Text) | `/clearance/exit-interview/` | `employee_clearance.get_exit_interview_questions`, `employee_clearance.submit_exit_interview_responses` | Exit Interview (Frappe standard) — `custom_questionnaire_responses` child table; BEI Exit Interview Question (read) | LIVE — links to Frappe standard `Exit Interview` DocType (not a BEI custom one) |
| 6 | HR / Dept Heads | Update individual DOLE compliance items as Completed (with optional notes and document attachment) | No dedicated frontend; must use Frappe API directly or Desk | `employee_clearance.update_compliance_status` | Employee Separation custom_dole_compliance child row: status=Completed, completed_date, completed_by | LIVE — but no frontend UI for department heads to action their clearance items from my.bebang.ph |
| 7 | System (hook) | On every save: check if ALL compliance items are Completed or Not Applicable; if yes, notify Finance + HR via GChat | (Background) | `on_separation_updated` (hooks.py on_update) | No DocType update; GChat message sent: "Clearance Complete — Final Pay Pending" | LIVE — but fires on_update, which means it fires on EVERY save; the "notify once" guard checks `boarding_status == "Completed"` but `boarding_status` is never actually set to "Completed" by this hook — **idempotency issue, notification may send multiple times** |
| 8 | HR (IT Clearance) | Disable employee's Bio ID on all ADMS biometric devices | No dedicated frontend | `employee_clearance.disable_bio_id` | Frappe Comment on Employee; ADMS REST call to `localhost:8080/admin/user/{bio_id}/disable` | LIVE — ADMS is on same EC2 instance (`localhost`); connection error handling with fallback message |
| 9 | HR | Generate Certificate of Employment (COE) | `/clearance/` page — "Download COE" button | `employee_clearance.generate_coe` | Employee Separation (custom_coe_generated=1); returns Frappe print format PDF URL | LIVE — PDF is a Frappe print format, not a custom-generated document |
| 10 | Finance | Approve final pay | No API endpoint; manual field update on Employee Separation via Frappe Desk only | None found in codebase | Employee Separation (custom_final_pay_approved=1 — manual) | BROKEN — no API endpoint; no frontend page; Finance must use Frappe Desk |
| 11 | HR | Set employee status to "Left" | No API endpoint in employee_clearance.py | None found for this step | Employee (status="Left" — manual Frappe Desk update) | BROKEN — no API endpoint; no frontend page |
| 12 | HR | View separation statistics (read-only) | `/dashboard/hr/reports/separations` | `hr_reports.get_separations_report` | Employee Separation (read) | LIVE — reporting only, no actions |

## Handoff Points

| From Dept | To Dept | Trigger | Mechanism | Status |
|-----------|---------|---------|-----------|--------|
| HR | All Departments | Employee Separation created | `on_separation_created` hook → GChat to `gchat_notification_space` | LIVE — but the message is generic ("complete clearance items"). No per-department routing; all depts get one message |
| All Departments | Finance | All DOLE compliance items completed | `on_separation_updated` hook → GChat "Clearance Complete — Final Pay Pending" | LIVE — but idempotency bug (see FL09-BL02); Finance has no API endpoint or frontend page to action this |
| Finance | HR | Final pay approved | No automated mechanism. `custom_final_pay_approved` field must be manually set in Frappe Desk. | BROKEN — manual-only |
| HR | ADMS | IT Clearance completion triggers bio ID disable | `disable_bio_id` → ADMS REST API (`localhost:8080`) | LIVE — but no automatic trigger; HR must call the API manually |
| Employee | HR | Exit interview submitted | Exit interview responses saved to `Exit Interview` DocType. No notification to HR that responses are complete. | BROKEN — HR must poll Frappe Desk to see if exit interview was submitted |

## Broken Links / Gaps

| ID | Location | Problem | Impact | Severity |
|----|----------|---------|--------|----------|
| FL09-BL01 | HR management workflow | No frontend page in `/dashboard/hr/` for creating or managing employee separations. `create_employee_separation` API exists and is wired in `lib/clearance/api.ts` but there is no HR admin page that exposes separation creation or management. HR must use Frappe Desk. | HR managers cannot initiate or manage separation workflow from my.bebang.ph | HIGH |
| FL09-BL02 | `on_separation_updated` hook (line 760) | The hook checks `if getattr(doc, "boarding_status", "") == "Completed": return` to prevent duplicate notifications. However, `boarding_status` is NEVER set to "Completed" by this hook or any API in `employee_clearance.py`. The guard is ineffective. Every subsequent save of the Employee Separation after all items are complete will re-send the "Clearance Complete — Final Pay Pending" GChat message. | Finance and HR receive duplicate GChat alerts on every subsequent compliance item update | HIGH |
| FL09-BL03 | Department heads / clearance signatories | No frontend page for department heads to view or action their clearance items from my.bebang.ph. `update_compliance_status` API exists but is not exposed via any frontend page. Department heads must use Frappe Desk or wait for HR to update on their behalf. | The multi-department clearance workflow is centralized in HR only; the intent of "all dept heads clear" is not achievable from my.bebang.ph | HIGH |
| FL09-BL04 | Finance final pay workflow | No API endpoint for Finance to approve final pay. `custom_final_pay_approved` is a custom field that Finance must set manually in Frappe Desk. No computation of final pay amount (last salary, proportionate 13th month, unused leave conversions) exists anywhere in the codebase. | Finance has no app-level final pay workflow; GChat notification after clearance is a manual trigger with no digital follow-up | HIGH |
| FL09-BL05 | `get_my_separation` (line 660) | Fetches `BEI DOLE Compliance Checklist` using `parenttype="Employee Separation"`. However, `create_employee_separation` and `update_compliance_status` use `custom_dole_compliance` as the child table field name, not `BEI DOLE Compliance Checklist`. The DocType child table name and the API query target may be inconsistent. If the child table DocType is named differently from `BEI DOLE Compliance Checklist`, `get_my_separation` will return empty compliance items. | Employee-facing clearance page shows 0% compliance progress even when items are completed | MEDIUM |
| FL09-BL06 | Exit interview | `submit_exit_interview_responses` writes to `Exit Interview` (Frappe standard DocType), not a BEI custom DocType. Requires an `Exit Interview` document to already exist (linked from Employee Separation `activities` table by Frappe's standard boarding module). If the activities are not auto-created, the employee has no `exit_interview` document name to pass to the API. No HR admin page found for creating Exit Interview documents. | Exit interview flow is wired for happy path only; breaks if `Exit Interview` doc was not auto-generated by Frappe's standard boarding | MEDIUM |
| FL09-BL07 | `disable_bio_id` | Calls `http://localhost:8080/admin/user/{bio_id}/disable` — hardcoded to localhost. In a containerized deployment, ADMS may not be accessible at localhost. On connection failure, returns success=False with message but does NOT log to a retry queue or alert HR that bio ID disable failed. | Separated employees' biometric access may not be revoked if ADMS is unreachable | MEDIUM |
| FL09-BL08 | Employee status "Left" | No API endpoint to set `Employee.status = "Left"`. The GChat clearance notification tells HR to do this manually. No automated status update occurs even when `boarding_status = "Completed"` (which itself is never set). | Employee master remains "Active" status after separation is complete; payroll and attendance records may continue | HIGH |
| FL09-BL09 | COE generation | `generate_coe` returns a Frappe print format URL (`/api/method/frappe.utils.print_format.download_pdf?doctype=Employee+Separation&name=...&format=Standard`). There is no custom "Standard" print format designed for Employee Separation COE content. The URL will work but may produce a generic/unstyled Frappe print. | COE document quality/content may be inadequate for official use | LOW |

## Error Paths

| Trigger | What Happens | User Experience | Status |
|---------|-------------|----------------|--------|
| `create_employee_separation` — employee not found | `frappe.get_doc("Employee", employee)` raises `DoesNotExistError` | Raw Frappe exception | LIVE — unhandled; should be wrapped with user-friendly message |
| `submit_exit_interview_responses` — Exit Interview doc not found | `frappe.get_doc("Exit Interview", exit_interview)` raises `DoesNotExistError` | Raw Frappe exception | LIVE — unhandled |
| `update_compliance_status` — compliance_row_name not found in child table | Loop iterates over all rows; if row not found, no item is updated and `doc.save()` still succeeds | Silent no-op — returns success even if nothing was changed | LIVE — silent failure; no error raised when row_name not found |
| `disable_bio_id` — ADMS connection refused | `requests.exceptions.ConnectionError` caught; `frappe.log_error` called; returns `{success: False, message: "ADMS receiver not available"}` | HR sees failure message; bio ID NOT disabled | LIVE — fallback exists; no retry queue |
| `on_separation_created` — GChat space not configured | `gchat_notification_space` returns None; `frappe.log_error` called (not send) | Silent fallback; notification not sent | LIVE — but error logged, not alerted |
| `populate_dole_compliance` — no compliance items for sep_type | SQL returns empty result; `doc.custom_dole_compliance = []`; saved as empty | Clearance page shows 0 compliance items; employee sees 0% / 100% immediately | LIVE — no error raised; this should alert HR that compliance items are not configured for this separation type |
| `get_my_separation` — no active Employee for session user | `frappe.db.get_value` returns None; returns `{has_separation: False, message: "No employee record found"}` | Employee sees "No active separation" message | LIVE |

## Improvement Suggestions

1. **FL09-BL01 — HR Admin Separation Management Page**: Build `/dashboard/hr/separations/` with: (a) Create Separation form, (b) List of active separations with compliance progress bars, (c) Per-separation detail page showing compliance checklist with approve/reject per item per department. Wire to existing API endpoints.

2. **FL09-BL02 — Idempotency Fix for on_separation_updated**: After sending the "Clearance Complete" GChat message, explicitly set `doc.boarding_status = "Completed"` and `frappe.db.set_value("Employee Separation", doc.name, "boarding_status", "Completed")` in the hook. This makes the guard on line 760 effective and prevents duplicate notifications.

3. **FL09-BL03 — Department Head Clearance Portal**: Add a page at `/dashboard/clearance-items/` accessible by all department head roles. Show only clearance items where the department matches the user's department. Allow dept heads to mark their items Completed with notes/document upload.

4. **FL09-BL04 — Finance Final Pay Module**: Build a minimal `/dashboard/hr/final-pay/[separation]/` page for Finance. Include: auto-computed final pay (pro-rated salary, 13th month, unused leave), `custom_final_pay_approved` approval button, and Google Chat notification to HR on approval.

5. **FL09-BL05 — Compliance Child Table Name Audit**: Verify the actual DocType name used for the compliance child table in Employee Separation. If it is `BEI DOLE Compliance Item` (child), update `get_my_separation` to use `frappe.get_all("BEI DOLE Compliance Item", filters={"parent": sep.name, "parenttype": "Employee Separation"}, ...)` consistently. Run a test to confirm the field name used in `doc.append("custom_dole_compliance", {...})` resolves to the correct child DocType.

6. **FL09-BL08 — Auto-Set Employee Status "Left"**: In `on_separation_updated`, after sending the "Clearance Complete" GChat and setting `boarding_status = "Completed"`, also run `frappe.db.set_value("Employee", doc.employee, "status", "Left")` and `frappe.db.set_value("Employee", doc.employee, "relieving_date", frappe.utils.today())`.

7. **FL09-BL07 — ADMS Retry Queue**: On `ConnectionError`, create a Frappe `Background Job` or append a record to a `BEI ADMS Pending Action` DocType for retry. Add a scheduler that retries failed ADMS actions every hour.
