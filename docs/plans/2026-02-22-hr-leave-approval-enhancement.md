# Plan: HR Leave Approval Enhancement (Command Center)
**Date:** 2026-02-22
**Status:** NO-GO (Pending Audit Blockers)
**Objective:** Replace the duplicate self-service leave page under "HR Management" with a dedicated, top-of-the-line HR Leave Command Center. This new module will allow HR and Supervisors to monitor company-wide leaves, approve/reject requests centrally, view a coverage calendar, and automatically detect staffing conflicts (overlapping approved leaves in the same branch).

## 1. Problem Statement
*   **Routing Bug:** The frontend sidebar (`nav-main.tsx`) incorrectly routes "HR Management -> Leave Management" to the self-service page (`/dashboard/hr/leave`).
*   **Missing Functionality:** HR lacks a centralized dashboard to view all company leaves, see who is currently on leave, and visualize future leaves on a calendar.
*   **Risk of Understaffing:** Managers currently approve leaves blindly without knowing if another team member in the same store has already been approved for the same date.

## 2. Execution Phases

### Phase 1: Backend API Development (Frappe)
Create a new dedicated API module `hrms/api/leave_dashboard.py` to aggregate data efficiently for the frontend, avoiding the need for the React app to make dozens of individual REST calls.

- [ ] **Task 1.1: KPI & Overview API**
  - Endpoint: `get_leave_overview(date_range, branch=None, department=None)`
  - Returns: Counts for "On Leave Today", "Pending Approvals", "Upcoming Leaves (Next 7 Days)".
- [ ] **Task 1.2: Calendar & History API**
  - Endpoint: `get_all_leaves(status=None, branch=None, from_date=None, to_date=None)`
  - Returns: A consolidated list of `Leave Application` records formatted for a React Calendar and data table, joined with Employee details (Branch, Department, Profile Image).
- [ ] **Task 1.3: Conflict Detection API**
  - Endpoint: `check_leave_conflicts(employee, from_date, to_date)`
  - Logic: Finds the employee's branch/department, then queries for any *Approved* Leave Applications within that exact branch/department that overlap with `from_date` and `to_date`.
  - Returns: List of conflicting employee names and their leave dates.
- [ ] **Task 1.4: Bulk Action API**
  - Endpoint: `bulk_update_leave_status(leave_ids, status, remarks=None)`
  - Logic: Iterates through provided Leave Application IDs and updates their status to Approved/Rejected.

### Phase 2: Frontend Routing & Layout (`bei-tasks`)
Fix the navigation bug and set up the new route structure protected by Role Guards.

- [ ] **Task 2.1: Route Registration**
  - Update `lib/constants.ts` to add `HR_ADMIN_LEAVE: "/dashboard/hr-admin/leaves"`.
- [ ] **Task 2.2: Sidebar Correction**
  - Update `components/layout/nav-main.tsx` under the "HR Management" section to point "Leave Management" to the new `ROUTES.HR_ADMIN_LEAVE`.
- [ ] **Task 2.3: Page Scaffolding**
  - Create `app/dashboard/hr-admin/leaves/page.tsx`.
  - Wrap the entire page in `<RoleGuard module={MODULES.HR_ADMIN}>` to restrict access to HR and upper management only.

### Phase 3: Frontend UI Implementation (`bei-tasks`)
Build the interactive dashboard components.

- [ ] **Task 3.1: The KPI Header**
  - Build top-level summary cards (On Leave Today, Pending Approvals, Upcoming).
- [ ] **Task 3.2: The Coverage Calendar**
  - Implement a visual calendar view (using `react-big-calendar` or similar) to plot approved and pending leaves. Include a Store/Branch filter dropdown.
- [ ] **Task 3.3: The Approval Queue (Action Center)**
  - Build a data table for all `Open` Leave Applications.
  - Integrate the Conflict Detection API: Display a warning badge (⚠️) next to requests that overlap with existing approved leaves in the same store.
  - Implement inline Approve/Reject action buttons and a Bulk Select feature.
- [ ] **Task 3.4: Historical Ledger**
  - Build a secondary tab/table for historical tracking (Approved, Rejected, Cancelled leaves) with advanced filtering (Date Picker, Employee Search, Status).

### Phase 4: Verification & E2E Testing
- [ ] **Test 4.1:** Verify a Store Staff user CANNOT access `/dashboard/hr-admin/leaves`.
- [ ] **Test 4.2:** Submit two overlapping leave requests for two employees in the same branch (e.g., Market Market). Verify the Conflict Warning appears on the HR Dashboard for the second request.
- [ ] **Test 4.3:** Verify HR can approve a leave directly from the new dashboard, and it correctly updates the backend Frappe `Leave Application` status to "Approved".
- [ ] **Test 4.4:** Verify the Calendar view accurately reflects the approved leave.

## 3. Deployment Notes
- Backend changes require a standard Frappe app deployment (`bench update`).
- Frontend changes require pushing to the `bei-tasks` repository to trigger a Vercel deployment.

---

## Audit Amendments (v1.1) — 2026-02-22

### Audit Methodology

Specialized domain agents (Backend, Frontend) audited this plan in parallel, and a code-verifier grounded the findings in the actual repository code.

| Domain | Agent | Findings File | Score |
|--------|-------|---------------|-------|
| Frappe Backend | frappe-backend-auditor | `output/plan-audit/2026-02-22-hr-leave-approval-enhancement/frappe_backend_findings.md` | 1 CRITICAL, 1 WARNING |
| Frontend | frontend-auditor | `output/plan-audit/2026-02-22-hr-leave-approval-enhancement/frontend_findings.md` | 2 CRITICAL, 1 WARNING |
| **Code Verification** | code-verifier | `output/plan-audit/2026-02-22-hr-leave-approval-enhancement/code_verification.md` | 2 confirmed, 0 stale, 0 new gaps |

### Top 2 Blockers (Must Resolve Before Execution)

#### BLOCKER 1: Missing Permission Checks on API Endpoints
**Source:** `frappe_backend_findings.md` C1 | **Severity:** CRITICAL
**Problem:** The plan describes building four new endpoints but doesn't mention enforcing Frappe role permissions. Code verifier confirmed `hrms/api/leave_dashboard.py` doesn't exist yet, so we must build it securely.
**Fix:** Explicitly state that all endpoints must be `@frappe.whitelist()` and include a `frappe.has_permission()` or `frappe.only_for(["HR Manager", "System Manager", "HR User"])` check at the start of each function to prevent unauthorized access to sensitive employee leave data.

#### BLOCKER 2: Missing Data Fetching Strategy & Optimistic Updates
**Source:** `frontend_findings.md` C-01, C-02 | **Severity:** CRITICAL
**Problem:** The plan describes building the UI but does not specify how the data will be fetched, cached, or how the action queue handles state. Without optimistic updates, the UI will freeze when approving leaves. Code verifier confirmed no `use-leave-dashboard.ts` exists.
**Fix:** Specify the creation of `bei-tasks/hooks/use-leave-dashboard.ts` using TanStack Query to cache `get_leave_overview` and `get_all_leaves`. Add optimistic update logic in the `useMutation` for `bulk_update_leave_status` to immediately remove items from the pending list.

### Additional Recommendations (Non-Blocking)

1. **Performance of Conflict Detection** (`frappe_backend_findings.md` W1): Use raw SQL (`frappe.db.sql`) with optimized index queries on `from_date` and `to_date` instead of ORM loops for conflict detection to avoid slow dashboard load times.
2. **Calendar Component Selection** (`frontend_findings.md` W-01): Consider using a lightweight custom grid or ensuring the calendar library is properly wrapped in a Shadcn-compatible styling container.

### Pre-Flight Checks: Audit Additions

- [ ] **AUDIT-1:** `hrms/api/leave_dashboard.py` endpoints are protected by `frappe.only_for(["HR Manager", "HR User"])` or explicit `frappe.has_permission()` checks.
- [ ] **AUDIT-2:** `bei-tasks/hooks/use-leave-dashboard.ts` is created and utilizes TanStack Query for data fetching and optimistic mutations.

### GO / NO-GO Gate (Updated)

**Execution is NO-GO until AUDIT-1 and AUDIT-2 are all checked.**