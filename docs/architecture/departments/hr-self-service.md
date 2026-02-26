---
**Last Scanned:** 2026-02-23 | **Previous Scan:** 2026-02-17
**Commit:** 7b998877f | **Health Score:** 92% LIVE
---

# Department Feature Matrix: HR Self-Service

## Summary

- Frontend pages: 18 (across `/attendance/`, `/my-profile/`, `/onboarding/`, `/hr/` self-service sections)
- Backend endpoints: 52 LIVE (across `__init__.py`, `official_business.py`, `shift_tracking.py`, `coverage.py`, `onboarding.py`, `roster.py`, `payroll.py` self-service endpoints)
- DocTypes: 10 BEI custom + 6 Frappe standard
- Health Score: 92% LIVE (1 STUB: training compliance; indentation bug in onboarding)

## Feature Matrix

| Feature | Frontend Page | FE Status | Backend API | BE Status | Notes |
|---------|--------------|-----------|-------------|-----------|-------|
| Punch In | `/attendance/punch-in` | LIVE | `shift_tracking.punch_in` | LIVE | GPS+selfie, row-level lock, anti-spoofing |
| Punch Out | `/attendance/punch-out` | LIVE | `shift_tracking.punch_out` | LIVE | GPS only, auto-calculates OT flag |
| Punch Dashboard | `/attendance/punch` | LIVE | `shift_tracking.get_active_punch`, `get_my_punch_history` | LIVE | Team review for supervisors |
| Punch Team Review | `/attendance/punch/review` | LIVE | `shift_tracking.get_team_punches`, `verify_punch`, `bulk_verify_punches` | LIVE | Subordinate-scoped; bulk up to 100 |
| OB Checkout | `/hr/official-business/checkout` | LIVE | `official_business.checkout` | LIVE | GPS+selfie, 305m anti-spoofing |
| OB Check-In | `/hr/official-business/checkin` | LIVE | `official_business.checkin`, `get_active_ob` | LIVE | |
| OB History | `/hr/official-business` | LIVE | `official_business.get_my_ob_records` | LIVE | |
| OB Supervisor Review | `/hr/official-business` | LIVE | `official_business.get_pending_review`, `review_ob` | LIVE | |
| OB Cancel | — | NOT BUILT | `official_business.cancel_ob` | LIVE | **GAP-050: no self-service UI** |
| Leave Application | `/hr/leave` | LIVE | `payroll.submit_leave_application`, `get_leave_balance_map` | LIVE | Creates BEI Approval Queue if branch resolved |
| Schedule View | `/hr/schedule` | LIVE | `payroll.get_my_schedule` | LIVE | Shift Assignment, 14-day default |
| My Payslip | `/hr/payslip` | LIVE | `payroll.get_my_payslips` | LIVE | Last 12 slips |
| Attendance Calendar | `/hr/attendance` | LIVE | `__init__.get_attendance_calendar_events` | LIVE | |
| Attendance Correction | `/hr/attendance-correction` | LIVE | `attendance_correction.submit_correction` | LIVE | Maps to Frappe Attendance Request |
| Coverage Request | `/hr/coverage` | LIVE | `coverage.request_coverage` | LIVE | |
| Coverage Request Approve | — | NOT BUILT | `coverage.approve_coverage`, `get_coverage_requests` | LIVE | **GAP-051: no supervisor UI** |
| Onboarding Session | `/onboarding` | LIVE | `onboarding.create_session`, `submit_request`, `approve_and_apply` | LIVE | **GAP-002: indentation bug in _create_employee_from_new_hire_request** |
| My Profile | `/my-profile` | LIVE | `enrichment.submit_edit_request`, `update_self_service_field` | LIVE | 3-tier field editing |
| Roster / Shift Calendar | Legacy Vue/Ionic PWA | LEGACY | `roster.py` | LIVE | **GAP-083: not ported to Next.js** |
| Training Compliance | `/hr/training` (compliance tab) | LIVE (mock) | `hr_reports.get_training_completion_by_store` | LIVE | **GAP-052: FE uses hardcoded mock data** |

## DocType Relationships

| DocType | Link Fields | Child Tables | Submittable? |
|---------|-------------|-------------|--------------|
| BEI Official Business | employee→Employee, supervisor→Employee, matched_ob_location→BEI OB Location | None | No |
| BEI Shift Record | employee→Employee, verified_by→User | None | No |
| BEI Staff Coverage Request | absent_employee→Employee, assigned_employee→Employee | None | No |
| BEI Onboarding Session | created_by_user→User | None | No |
| BEI Onboarding Request | employee→Employee, session_token→BEI Onboarding Session | None | No |
| BEI Edit Request | employee→Employee, reviewed_by→User | None | No |
| Leave Application (Frappe) | employee→Employee, leave_approver→User | None | Yes |
| Attendance Request (Frappe) | employee→Employee | None | Yes |
| Salary Slip (Frappe) | employee→Employee, payroll_entry→Payroll Entry | Earnings, Deductions | Yes |

## Gaps Found

| ID | Feature | Blocker Type | Severity | Notes |
|----|---------|-------------|----------|-------|
| GAP-001 | BEI Shift Record never bridges to Frappe Attendance | Integration | Critical | GPS punches invisible to payroll — employees appear absent |
| GAP-002 | onboarding.py IndentationError lines 354-357 | Bug | Critical | All onboarding endpoints return 500 |
| GAP-039 | Leave rejection balance correction: db_set not doc.cancel | Bug | High | Rejected leave does not release balance |
| GAP-050 | OB Cancel: no self-service UI | Frontend | Medium | |
| GAP-051 | Coverage Request approve: no frontend | Frontend | Medium | Supervisor cannot manage from app |
| GAP-052 | Training compliance: frontend uses mock data | Frontend-Backend mismatch | Medium | HR sees fake compliance data |
| GAP-083 | Roster/Shift Calendar: not on Next.js | Frontend | High | Employees on my.bebang.ph cannot view roster |
| GAP-084 | BEI Approval Queue not created when routing fails | Bug | High | Order in Approved status with no queue entry |

## Improvements

| Feature | Current State | Suggested Improvement | Priority |
|---------|--------------|----------------------|----------|
| Roster on Next.js | Still requires legacy Vue/Ionic PWA | Port roster.py functionality to Next.js schedule management page | HIGH |
| Leave routing | Requires warehouse resolution; if fails, no queue entry | Use employee branch directly as string | MEDIUM |
| OB duplicate routes | Two routes for same OB checkin/checkout | Consolidate to one route | MEDIUM |
