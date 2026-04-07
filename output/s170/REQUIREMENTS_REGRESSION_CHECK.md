# S170 Requirements Regression Check

Date: 2026-04-07
Branch: s170-s166-defect-fixes
hrms baseline: 6922ae39262660c63574ab7077be51c59ae74b71
bei-tasks baseline: 4a915e9b2fbff0b9b76f5c81b0608f7dac47ee63

## Locked Decisions Verification

| # | Item | Approach | Status |
|---|---|---|---|
| 1 | Defect 1 — Leave Ledger | FIX root cause via on_update_after_submit hook detecting status transition. Backfill is separate one-shot script. | YES |
| 2 | Defect 2 — Compensation route | Extract Dialog body into `<CompensationDetailPanel>`, add Page wrapper exporting default Page. Option B (correct), not Option A (lazy). | YES |
| 3 | Defect 3 — OT filing UI | Integrate with EXISTING `BEI Overtime Request` doctype. Resolve employee server-side from session.user. | YES |
| 4 | Defect 4 — Clearance | 3 minimum-viable doctypes, 8-station fixture, no Documenso. Employee status transition via `frappe.db.set_value` with rollback. ADMS de-enroll OUT OF SCOPE. | YES |
| 5 | Scope discipline | Touch only files needed for the 4 defects. No adjacent refactor. | YES |
| 6 | S166 catalog frozen | NOT editing docs/testing/scenarios/ or docs/plans/2026-04-06-sprint-166*. | YES |
| 7 | Single session | All 4 phases in this session. No splitting, no deferral. | YES |
| 8 | Sentry instrumentation | All new @frappe.whitelist() endpoints call set_backend_observability_context() | YES |
| 9 | Branch compliance | On s170-s166-defect-fixes (both repos) from origin/production and origin/main respectively | YES |
| 10 | PR-handoff | Stop at PR_CREATED. No merge, no deploy. | YES |

## HARD BLOCKER inventory

- Phase 1 Task 1.1: 60-min root cause budget for Leave Ledger diagnosis. If exceeded → STOP.
- Phase 4 Task 4.3: Employee transition MUST use `frappe.db.set_value` (MEMORY lesson #6 trap).
- Phase 3 Task 3.2: OT employee MUST be resolved server-side, never passed from client.
- Phase 2 Task 2.1: Pre-check ROLES.HR_MANAGER and ROLES.FINANCE before Phase 2 RoleGuard.

All HARD BLOCKERs acknowledged. Beginning execution.
