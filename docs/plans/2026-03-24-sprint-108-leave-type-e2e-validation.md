# Sprint 108 — Leave Type E2E Validation

```yaml
canonical_sprint_id: S108
status: GO
created: 2026-03-24
branch: s108-leave-type-validation
lane: single
depends_on: S106, S107
completed_date: null
execution_summary: null
```

## Summary

Validate all 7 leave types end-to-end: file via my.bebang.ph → approval → attendance record creation → payroll/salary slip impact. Document each leave type's behavior for BEI operations team.

**Scope:** 7 leave types to test, each through the full lifecycle. Plus a reference document explaining what each leave type means for BEI.

## Design Rationale (For Cold-Start Agents)

### Why this exists

S106 fixed 1,557 broken Leave Allocations. S107 fixes the navigation so employees can find the Leave page. But nobody has verified that the full leave lifecycle works end-to-end: file → approve → attendance marked → payroll deduction correct.

The CEO needs a reference explaining each leave type and confirmation that they all work.

### BEI Leave Types — What Each One Means

| Leave Type | Paid? | Days/Year | Balance Needed? | Payroll Impact | When to Use |
|-----------|-------|-----------|-----------------|----------------|-------------|
| **Vacation Leave (VL)** | Yes — full pay | 15 | Yes | No deduction | Planned time off, vacation, personal days |
| **Sick Leave (SL)** | Yes — full pay | 15 | Yes | No deduction | Illness, medical appointment, recovery |
| **Emergency Leave (EL)** | Depends on config | 5 | Yes | Check `is_lwp` flag | Urgent family emergency, death, disaster |
| **Casual Leave (CL)** | Yes — full pay | Per allocation | Yes | No deduction | Short personal errands, 1-2 days |
| **Compensatory Off (CO)** | Yes — full pay | Auto-created | No (auto-allocated) | No deduction | Worked on a holiday → get a day off later |
| **Privilege Leave (PL)** | Yes — full pay | Per allocation | Yes | No deduction | Long-service earned leave (PH: similar to VL) |
| **Leave Without Pay (LWOP)** | **No — 100% deducted** | Unlimited | **No** | **Full day salary deducted** | When all paid leave exhausted, or unpaid personal leave |

### How Leave Flows Through the System

```
Employee files leave (my.bebang.ph/dashboard/hr/leave)
  → Leave Application created (status: Open)
  → Leave approver notified
  → Approver approves (status: Approved, docstatus: 1)
  → Attendance records auto-created (status: "On Leave" for each day)
  → At payroll run:
    - Paid leave: payment_days unchanged (full salary)
    - LWOP: payment_days reduced by LWOP days (salary deducted)
    - PPL: payment_days reduced by fraction (partial deduction)
```

### Source references

- Leave Type DocType: `hrms/hr/doctype/leave_type/leave_type.json`
- Leave Application: `hrms/hr/doctype/leave_application/leave_application.py`
- Attendance creation: `leave_application.py` → `update_attendance()`
- Salary Slip leave calc: `hrms/payroll/doctype/salary_slip/salary_slip.py` → `get_working_days_details()`
- Balance check: `leave_application.py` → `get_leave_balance_on()` reads from Leave Ledger Entry

## Phase 1 — Test Each Leave Type via API (~10 units)

For each of the 7 leave types, test the full lifecycle:

### P1-1: Test Vacation Leave (VL)

1. Check balance for test employee via `get_leave_balance_on` → expect 15
2. Create Leave Application (1 day) via Frappe REST API → expect 200
3. Approve it → status changes to Approved
4. Submit it → docstatus changes to 1
5. Verify Attendance record created with status "On Leave"
6. Verify balance reduced by 1 → expect 14
7. Cancel the leave application → Attendance cancelled, balance restored

### P1-2: Test Sick Leave (SL)

Same as P1-1 with leave_type = "Sick Leave". Different employee or different date.

### P1-3: Test Emergency Leave (EL)

Same flow. Check if `is_lwp` flag affects payroll impact.

### P1-4: Test Casual Leave (CL)

Same flow with leave_type = "Casual Leave".

### P1-5: Test Leave Without Pay (LWOP)

1. **No balance check** — LWOP doesn't need allocation
2. Create Leave Application → expect 200
3. Approve + submit
4. Verify Attendance created
5. **Verify payroll impact:** Check that salary slip would deduct this day (via `get_lwp_or_ppl_for_date_range`)
6. Cancel afterward

### P1-6: Test Compensatory Off (CO)

1. This requires a CompensatoryLeaveRequest first (employee worked on a holiday)
2. If no holiday work exists, **document as NOT TESTABLE** without creating fake attendance
3. Verify the Leave Type configuration (is_compensatory=1)

### P1-7: Test Privilege Leave (PL)

Same flow as VL. Check if allocation exists.

## Phase 2 — Browser E2E for VL and SL (~6 units)

### P2-1: File VL via my.bebang.ph browser (Playwright)

1. Login as test.crew1@bebang.ph (or test employee with balance)
2. Navigate to /dashboard/hr/leave
3. Click "New Leave Request" button
4. Select "Vacation Leave" from dropdown
5. Pick from_date and to_date (1 day)
6. Enter reason: "S108 E2E test"
7. Click "Submit Request"
8. Verify success toast
9. Verify application appears in pending list
10. Cancel/delete afterward via API

### P2-2: File SL via my.bebang.ph browser (Playwright)

Same as P2-1 with Sick Leave.

### P2-3: Verify LWOP shows salary deduction warning (if any)

File LWOP and check if any UI warning about salary deduction appears.

## Phase 3 — Write Reference Document (~4 units)

### P3-1: Create leave type reference for BEI operations

Write `docs/reference/BEI_LEAVE_TYPES.md` with:
- Table of all 7 leave types with paid/unpaid, days, rules
- How to file leave (step by step with screenshots)
- How approval works
- How it affects attendance and payroll
- FAQs (what happens if balance is 0? can I file LWOP? etc.)

## Phase 4 — Closeout (~2 units)

### P4-1: Update plan and registry

## L3 Workflow Scenarios

| # | User | Action | Expected Outcome | Failure Means |
|---|------|--------|-------------------|---------------|
| 1 | (API) | Create VL Leave Application for test employee, 1 day | HTTP 200, application created | Leave Application flow broken |
| 2 | (API) | Approve + submit the VL application | status=Approved, docstatus=1 | Approval pipeline broken |
| 3 | (API) | Check Attendance record for that date | Attendance exists with status="On Leave" | Attendance creation broken |
| 4 | (API) | Check balance after VL | Balance = original - 1 | Ledger not updating |
| 5 | (API) | Cancel VL, verify balance restored | Balance = original | Cancel flow broken |
| 6 | (API) | Create LWOP Leave Application | HTTP 200 (no balance check) | LWOP creation broken |
| 7 | (API) | Approve LWOP, check Attendance | "On Leave" attendance created | LWOP attendance broken |
| 8 | (API) | Check LWOP payroll impact via salary slip method | LWP days > 0 | Payroll deduction not working |
| 9 | (Browser) | Login → HR Self-Service → Leave → New Request → VL → Submit | Application created, success toast | UI broken |
| 10 | (Browser) | Login → HR Self-Service → Leave → New Request → SL → Submit | Application created, success toast | UI broken |

## Requirements Regression Checklist

- [ ] Does VL create Attendance with status "On Leave"?
- [ ] Does SL create Attendance with status "On Leave"?
- [ ] Does LWOP NOT check balance (is_lwp=1)?
- [ ] Does LWOP show as leave_without_pay in salary calculation?
- [ ] Does VL show as 0 LWP (no salary deduction)?
- [ ] Does balance decrease after approved leave?
- [ ] Does balance restore after cancelled leave?
- [ ] Can employee file leave from my.bebang.ph UI?

## Ground-Truth Lock

- evidence_sources:
  - `output/l3/s108/form_submissions.json` → browser leave submissions
  - `output/l3/s108/api_mutations.json` → API leave lifecycle calls
  - `output/l3/s108/state_verification.json` → balance/attendance/payroll checks
- count_method:
  - metric: leave types tested
  - basis: 7 leave types × lifecycle steps (create, approve, attendance, payroll, cancel)
  - method: API calls + Playwright browser tests

## Autonomous Execution Contract

- completion_condition:
  - All 7 leave types tested via API with attendance verification
  - VL and SL tested via browser E2E
  - LWOP payroll impact verified
  - Reference document written
  - All L3 scenarios pass
  - plan YAML and SPRINT_REGISTRY.md updated
- stop_only_for:
  - SSM/EC2 access failure for payroll verification
  - Leave type not configured in Frappe (missing from system)
- signoff_authority: single-owner (Sam)

## Scope Size Warning

Total ~22 units, well within the 80-unit ceiling. Single session executable. Phase 1 is the heaviest (10 units) but repetitive — same pattern across 7 types.

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s108-leave-type-validation origin/production`.
3. Read S106 results to confirm leave allocations are fixed.
4. Execute Phase 1 (API tests) → Phase 2 (Browser E2E) → Phase 3 (Reference doc) → Phase 4 (Closeout).

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.

## Execution Workflow

- API tests: Direct Frappe REST API calls via Python
- Browser tests: Playwright for my.bebang.ph
- Payroll verification: API call to salary slip methods (no need to run actual payroll)
- No code deployment needed — this is a validation/certification sprint
- Sentry: Not applicable (no new endpoints)
