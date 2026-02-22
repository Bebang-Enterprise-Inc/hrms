# Frappe Backend Audit Findings
## Plan: 2026-02-22-hr-leave-approval-enhancement.md
## Date: 2026-02-22

### CRITICAL Findings
#### C1: Missing Permission Checks on API Endpoints
**Location in plan:** Phase 1, Task 1.1-1.4
**Problem:** The plan describes building four new endpoints (`get_leave_overview`, `get_all_leaves`, `check_leave_conflicts`, `bulk_update_leave_status`) but doesn't mention enforcing Frappe role permissions (e.g., checking if the caller is an HR Manager or Supervisor).
**Fix:** Explicitly state that all endpoints must be `@frappe.whitelist()` and include a `frappe.has_permission()` or `frappe.only_for(["HR Manager", "System Manager", "HR User"])` check at the start of each function to prevent unauthorized access.

### WARNING Findings
#### W1: Performance of Conflict Detection
**Location in plan:** Task 1.3: Conflict Detection API
**Problem:** Querying all overlapping leaves across a large branch (e.g., 50+ employees) on the fly without database indices might cause slow dashboard load times.
**Fix:** Use raw SQL (`frappe.db.sql`) with optimized index queries on `from_date` and `to_date` instead of ORM loops.

### Summary
- CRITICAL: 1
- WARNING: 1
- INFO: 0
