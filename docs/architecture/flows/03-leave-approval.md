# Flow 03: Leave Request to Approval
**Departments:** Employee → Supervisor → HR | **Scanned:** 2026-02-23 | **Agent:** flow-tracer-1

---

## Flow Diagram (Mermaid)

```mermaid
sequenceDiagram
    participant Emp as Employee
    participant LeavePage as /hr/leave
    participant LeaveDialog as LeaveRequestDialog
    participant PayrollAPI as payroll.py
    participant InitAPI as __init__.py
    participant HRReportsAPI as hr_reports.py
    participant LeaveApp as Leave Application (Frappe)
    participant ApprovalQ as BEI Approval Queue
    participant SupChatHook as google_chat.on_approval_queue_insert
    participant HRAdminPage as /hr-admin/leaves
    participant Attendance as Attendance (Frappe)

    Emp->>LeavePage: Open leave page
    LeavePage->>PayrollAPI: get_leave_balance_map(employee)
    LeavePage->>InitAPI: get_leave_applications(employee)
    LeavePage->>PayrollAPI: get_leave_types()
    Emp->>LeaveDialog: Fill form + Submit
    LeaveDialog->>PayrollAPI: submit_leave_application(leave_type, from_date, to_date, reason)
    PayrollAPI->>LeaveApp: new_doc().insert() → status=Open, docstatus=0

    alt leave_approver set AND branch resolves to warehouse
        PayrollAPI->>ApprovalQ: new_doc().insert() → reference_doctype=Leave Application
        ApprovalQ-->>SupChatHook: after_insert hook fires
        SupChatHook-->>GChat: Notification to approver space
    else branch cannot resolve OR no leave_approver
        Note over PayrollAPI,ApprovalQ: BROKEN: No approval queue created; approver has no notification
    end

    Note over ApprovalQ,HRAdminPage: HANDOFF: Supervisor/HR sees leave in command center

    HR->>HRAdminPage: Load leave command center
    HRAdminPage->>HRReportsAPI: get_leave_overview(date_range, branch)
    HRAdminPage->>HRReportsAPI: get_all_leaves(status="Open")
    HR->>HRAdminPage: Check conflicts for an employee
    HRAdminPage->>HRReportsAPI: check_leave_conflicts(employee, from_date, to_date)
    HR->>HRAdminPage: Approve single or bulk leaves
    HRAdminPage->>HRReportsAPI: bulk_update_leave_status(leave_ids, "Approved")

    alt status == Approved AND docstatus == 0
        HRReportsAPI->>LeaveApp: doc.submit() → docstatus=1
    else status == Rejected
        HRReportsAPI->>LeaveApp: doc.db_set("status", "Rejected") → docstatus stays 0
        Note over HRReportsAPI,LeaveApp: BROKEN: Rejected leave stays draft (docstatus=0)
    end

    Note over LeaveApp,Attendance: Frappe workflow: submitted Leave Application auto-updates Attendance

    LeaveApp-->>Attendance: on_submit hook creates/updates Attendance records for leave period (status=On Leave)

    Note over Attendance,Emp: No push notification to employee about approval decision
```

---

## Step-by-Step Trace

| Step | Actor | Action | Frontend Page | API Endpoint | DocType Created/Updated | Status |
|------|-------|--------|---------------|-------------|------------------------|--------|
| 1 | Employee | Open leave page to see balances and history | `/hr/leave/page.tsx` | `payroll.get_leave_balance_map(employee)`, `__init__.get_leave_applications(employee)`, `payroll.get_leave_types()` | — (read only) | LIVE |
| 2 | Employee | Open leave request dialog + submit | `/hr/leave/page.tsx` → `LeaveRequestDialog` | `payroll.submit_leave_application(leave_type, from_date, to_date, reason, half_day)` | Leave Application (docstatus=0, status=Open) | LIVE |
| 3 | System | Attempt to create BEI Approval Queue entry | — | Internal within `submit_leave_application()` | BEI Approval Queue (if branch resolves AND leave_approver is set) | PARTIAL |
| 4 | System | Google Chat notification to approver | — | `google_chat.on_approval_queue_insert` (doc_events hook) | — | LIVE (when queue entry created) |
| 5 | Supervisor/HR | Load leave command center overview | `/hr-admin/leaves/page.tsx` | `hr_reports.get_leave_overview(date_range, branch)` | — (read only) | LIVE |
| 6 | HR | List all pending leaves with filters | `/hr-admin/leaves/page.tsx` | `hr_reports.get_all_leaves(status, branch, from_date, to_date)` | — (read only) | LIVE |
| 7 | HR | Check staffing conflicts for a leave | `/hr-admin/leaves/page.tsx` | `hr_reports.check_leave_conflicts(employee, from_date, to_date)` | — (read only) | LIVE |
| 8 | HR | Approve one or more leaves (bulk or single) | `/hr-admin/leaves/page.tsx` | `hr_reports.bulk_update_leave_status(leave_ids, "Approved")` | Leave Application (doc.submit() → docstatus=1, status=Approved) | LIVE |
| 9 | HR | Reject one or more leaves | `/hr-admin/leaves/page.tsx` | `hr_reports.bulk_update_leave_status(leave_ids, "Rejected")` | Leave Application (db_set status=Rejected, docstatus STAYS 0) | BUGGY |
| 10 | Frappe | Auto-update Attendance for leave period on submit | — | Frappe standard Leave Application `on_submit` hook | Attendance (status=On Leave for each working day in leave period) | LIVE (Frappe standard) |
| 11 | Employee | View leave status update | `/hr/leave/page.tsx` | `__init__.get_leave_applications(employee)` | — (read, shows updated status) | LIVE (manual refresh only) |
| 12 | HR | View leave balance after approval | `/hr/leave/page.tsx` | `payroll.get_leave_balance_map(employee)` | Leave Allocation (balance deducted by Frappe ledger) | LIVE |

---

## Handoff Points

| From Dept | To Dept | Trigger | Mechanism | Status |
|-----------|---------|---------|-----------|--------|
| Employee | Supervisor/HR | Leave Application created (status=Open) | BEI Approval Queue created IF `branch` resolves to Warehouse AND `leave_approver` is set on Employee | PARTIAL — silent failure if branch doesn't resolve |
| Employee → Supervisor (BEI Approval Queue) | Google Chat notification | `after_insert` hook on BEI Approval Queue fires `google_chat.on_approval_queue_insert` | LIVE (conditional on queue entry being created) |
| Supervisor review | HR Command Center | Supervisor can approve in command center; HR can also bulk approve | Both use same `bulk_update_leave_status()` endpoint; no role separation between supervisor approval and HR confirmation | PARTIAL — no two-step supervisor→HR approval chain |
| HR approval | Frappe Attendance update | Leave Application `doc.submit()` triggers Frappe standard `on_submit` hook | LIVE — Frappe auto-creates Attendance records with status=On Leave | LIVE |
| HR approval | Employee notification | No notification sent to employee after approval or rejection | BROKEN — employee must manually check leave page | BROKEN |

---

## Broken Links / Gaps

| ID | Location | Problem | Impact | Severity |
|----|----------|---------|--------|----------|
| BL-01 | `payroll.submit_leave_application()` — BEI Approval Queue creation | The queue entry is only created if: (a) `employee.leave_approver` is set AND (b) `resolve_warehouse(branch)` succeeds without exception. Both conditions must pass. If the branch name doesn't match a Warehouse document name, the `except` block silently swallows the error, and NO queue entry is created. The leave is submitted but the approver has no notification and no queue item. | Employees whose branch is not configured as a Warehouse receive zero approval notification; their leave may sit in Open status indefinitely | HIGH |
| BL-02 | `hr_reports.bulk_update_leave_status()` rejection path | When `status == "Rejected"`, the function calls `doc.db_set("status", "Rejected")` which only sets the custom `status` field. `Leave Application` is a submittable DocType — proper rejection requires `doc.cancel()` (docstatus=2). The rejected leave stays at docstatus=0 (draft). Frappe may still allow it to be submitted later; leave balance is not deducted/returned correctly. | Rejected leaves are not properly closed in Frappe; leave balances may be inconsistent; HR sees "Rejected" but Frappe sees "Open Draft" | HIGH |
| BL-03 | No employee notification after approval or rejection | There is no push notification, Google Chat message, or any outbound communication sent to the employee when their leave is approved or rejected in `bulk_update_leave_status()`. `hr_self.md` Gap G8 confirms this is a known gap. | Employees must manually reload the leave page to discover their leave status; for shift planning this creates delays | MEDIUM |
| BL-04 | No supervisor-level approval step (two-step flow absent) | The system has one approval layer: HR Command Center. There is no dedicated supervisor approval page or API before HR sees the leave. The described flow (Employee → Supervisor → HR) is not implemented as two separate approval gates. Both supervisor and HR use the same `bulk_update_leave_status()` endpoint. | The intended governance (supervisor approves first, HR confirms) is not enforced in the system; HR does all approvals directly | MEDIUM |
| BL-05 | `get_all_leaves()` has no pagination | `hr_reports.get_all_leaves()` runs a raw SQL query with `ORDER BY la.from_date DESC` but no LIMIT or pagination. For organizations with many leave records, this will return an unbounded result set. | Performance degradation on HR admin page as leave record count grows; potential timeout with large datasets | MEDIUM |
| BL-06 | `check_leave_conflicts()` scope is branch/department only | The conflict check looks for overlapping approved leaves within the same branch or department. It does not check leave limits (e.g., "max 2 staff on leave simultaneously") or minimum coverage rules. | HR may approve conflicting leaves for critical roles if the branch is large or coverage rules are not simply headcount-based | LOW |
| BL-07 | `bulk_update_leave_status()` approval does not set `leave_approver` to current user | When approving, `doc.submit()` is called without first setting `doc.leave_approver = frappe.session.user`. The Leave Application's `leave_approver` field retains whatever was set at application creation (if anything). | Audit trail does not show which HR Manager actually approved the leave; Frappe's standard Leave Application workflow uses `leave_approver` for approval gating | LOW |
| BL-08 | `get_leave_approval_details()` approver fallback is two-level but not three-level | The function returns `leave_approver` from Employee record, then falls back to Department Approver. The described three-level flow (employee's supervisor → HR) is not captured here; there is no `reports_to` chain escalation | Approver discovery logic is flat; if neither Employee.leave_approver nor Department Approver is set, no approver is found and no queue entry will be created | LOW |

---

## Error Paths

| Trigger | What Happens | User Experience | Status |
|---------|-------------|----------------|--------|
| Leave submitted with missing required fields | `frappe.throw()` in `submit_leave_application()` | Form shows error; no leave created | LIVE |
| Leave submitted with no employee record for user | Returns `{"success": False, "error": "No employee record found"}` | User sees error message | LIVE |
| Frappe Leave Application validation error (e.g., overlapping leave, insufficient balance) | `frappe.exceptions.ValidationError` caught; returns `{"success": False, "error": str(e)}` | User sees Frappe validation message | LIVE |
| Approval Queue insert fails (branch not a Warehouse) | `try/except` swallows error; `frappe.log_error()` written; leave is still created | Leave Application exists but approver never notified; silent failure logged | BROKEN (BL-01) |
| `bulk_update_leave_status()` on already-processed leave | `doc.status != "Open"` check; appended to `failed` list with error message | HR sees per-leave error in response | LIVE |
| `bulk_update_leave_status()` approve on already-submitted doc (docstatus=1) | Condition `doc.docstatus == 0` else path calls `doc.db_set("status", "Approved")` — avoids double-submit | Handled, but bypasses normal submit flow | PARTIAL |
| `get_leave_overview()` called by non-ALLOWED_ROLES user | `frappe.only_for(ALLOWED_ROLES)` raises PermissionError | 403-equivalent error | LIVE |
| `check_leave_conflicts()` for employee not found | Returns empty `conflicts` list (no error thrown); `emp_details` checked first | Returns empty result; no error | LIVE |
| Leave Application `on_submit` fails in Frappe standard hook | Frappe rolls back transaction; Leave Application stays draft | User sees Frappe error; `submit_leave_application()` would have already returned success — de-sync possible | PARTIAL |

---

## Improvement Suggestions

| Feature | Current State | Suggested Improvement | Priority |
|---------|--------------|----------------------|----------|
| BEI Approval Queue creation — branch resolution dependency | Only created when `resolve_warehouse(branch)` succeeds | Use `employee.branch` directly as the queue `store` field (string), removing the Warehouse resolution dependency. Approval queue should exist for ALL leaves regardless of branch setup. | HIGH |
| Leave rejection uses `db_set` instead of `doc.cancel()` | docstatus stays 0 after rejection; leave balance not correctly managed | Change rejection path in `bulk_update_leave_status()` to call `doc.cancel()` for proper Frappe lifecycle; add `reason` to cancellation comment | HIGH |
| No employee notification on approval/rejection | Employee must manually poll the leave page | Add Google Chat message to employee's space (or push notification) in `bulk_update_leave_status()` after each status change, using same `send_message_to_space` pattern | HIGH |
| Two-step supervisor → HR approval | Both use same endpoint; no supervisor gating | Add a "Supervisor Approval" status to Leave Application lifecycle; create `/hr/approvals/leave/` page for supervisors that moves leave from Open → Supervisor Approved before HR command center sees it | MEDIUM |
| `get_all_leaves()` unbounded result | No pagination; full table scan | Add `limit_page_length` and `limit_start` pagination params; add index on `from_date, status` columns | MEDIUM |
| `bulk_update_leave_status()` does not record approver | `leave_approver` field not set on approval | Before `doc.submit()`, set `doc.leave_approver = frappe.session.user` and save, then submit | MEDIUM |
| Leave balance displayed before submission | `get_leave_balance_map()` shows current balance; after submission the balance deduction is pending until approval/submission | Show "pending" leave days separately from "approved" leave days in the balance cards on `/hr/leave/page.tsx` | LOW |
| `check_leave_conflicts()` no coverage rules | Only checks overlapping approved leaves | Add configurable "minimum coverage" rule per role/shift type (e.g., always 1 OIC on duty); surface as warning in conflict check response | LOW |
