# HR Leave Management Center - Proposal & Architecture Plan
**Date:** 2026-02-22

## 1. The Core Problem
Currently, the `my.bebang.ph` portal relies on the generic "Supervisor Approval Queue" for leave approvals, and routes the "Leave Management" sidebar link to the employee's personal self-service page. 

For a company of BEI's size (765+ employees, 45 stores), HR and Area Supervisors need a **dedicated, God's-eye view** of the organization's schedule to prevent store understaffing and easily manage historical data.

## 2. Comprehensive Requirements
To build a "top-of-the-line" Leave Management system, the page must act as an operational command center rather than just a list of forms.

*   **Real-time Monitoring:** Who is absent *right now* across all stores?
*   **Conflict Prevention:** If an employee requests a Friday off, the system must warn the manager if another employee in the *same store* already has an approved leave for that Friday.
*   **Centralized Approvals:** Approve/Reject requests with one click directly from the dashboard.
*   **Historical Tracking:** Filter past leaves by Store, Department, Date Range, and Status.

---

## 3. Frontend Architecture (`bei-tasks` / React)

**New Route:** `/dashboard/hr-admin/leaves` (We will separate this from the personal `/dashboard/hr/leave` page).

### UI Layout & Components
1.  **KPI Header Row:**
    *   **On Leave Today:** Count of employees currently off.
    *   **Pending Approvals:** Count of requests waiting for action.
    *   **Upcoming This Week:** Quick glance at future scheduling gaps.
2.  **The "Coverage Calendar" (Visual View):**
    *   A full-width interactive calendar component (using `react-big-calendar` or `fullcalendar`).
    *   Displays all Approved and Pending leaves as color-coded blocks.
    *   *Crucial Feature:* Managers can filter the calendar by "Store Branch" to immediately see if approving a new leave will leave a store short-staffed.
3.  **Action Queue (Pending Table):**
    *   Data table showing all `Open` Leave Applications.
    *   Includes an inline **"Conflict Warning"** badge (e.g., ⚠️ *2 others on leave in Market Market on this date*).
    *   Inline Approve/Reject buttons with a modal for rejection reasons.
4.  **Historical Ledger (Data View):**
    *   A paginated table for all historical leaves (`Approved`, `Rejected`, `Cancelled`).
    *   Advanced filters: Date Range Picker, Employee Search, Branch Dropdown, Leave Type Dropdown.

---

## 4. Backend Architecture (Frappe `BEI-ERP`)

To make the frontend blazing fast, we shouldn't make 10 different API calls. We need to build a dedicated backend API module (`hrms/api/leave_dashboard.py`).

### Required Endpoints:
1.  **`GET /api/method/hrms.api.leave_dashboard.get_dashboard_data`**
    *   **Params:** `branch` (optional), `date_range`
    *   **Returns:** A consolidated JSON object containing:
        *   `kpis`: { on_leave_today, pending_count, upcoming_count }
        *   `pending_requests`: List of Open Leave Applications.
        *   `calendar_events`: List of all leaves formatted for the React Calendar component.
2.  **`GET /api/method/hrms.api.leave_dashboard.check_leave_conflicts`**
    *   **Params:** `employee_id`, `from_date`, `to_date`
    *   **Returns:** Checks the employee's branch/department and returns a list of *other* employees in that exact same unit who already have approved leaves overlapping with those dates.
3.  **`POST /api/method/hrms.api.leave_dashboard.bulk_action`**
    *   Allows HR to select multiple leave requests and approve/reject them in bulk to save time.

---

## 5. Security & RBAC Routing Fix
1.  **Fix `nav-main.tsx`:** Update the sidebar configuration so that "Leave Management" under "HR Management" points to `/dashboard/hr-admin/leaves` instead of the personal `/dashboard/hr/leave`.
2.  **Role Guarding:** Wrap the new page in a `<RoleGuard>` that restricts access strictly to `HR Manager`, `HR User`, and `Area Supervisor`. Store Staff will never see this page.

---

## Next Steps for Execution
If you approve this plan, I will:
1. Write the Python API backend (`leave_dashboard.py`) to handle the data aggregation and conflict detection.
2. Provide the exact React code to build the new `/dashboard/hr-admin/leaves` page in the `bei-tasks` repository.
3. Fix the frontend routing bug in `nav-main.tsx`.