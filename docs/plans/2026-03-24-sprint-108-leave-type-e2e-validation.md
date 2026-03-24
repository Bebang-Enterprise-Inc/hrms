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

Validate all 7 leave types end-to-end: file via my.bebang.ph → approval → attendance record creation → payroll/salary slip impact. Wire leave-overtime abuse prevention guards. Document each leave type's behavior for BEI operations team.

**Scope:** 7 leave types to test, each through the full lifecycle. Leave-overtime mutual exclusion guards. Reference document. Hide non-functional leave types from dropdown.

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

## Phase 2.5 — Leave-Overtime Abuse Prevention (~8 units)

### Why this is needed

Currently there is ZERO enforcement preventing an employee from:
1. Filing leave on a day AND having an OT record auto-created for that same day
2. Getting approved OT, then filing leave for the same day (double-dipping)
3. Having LWOP on a day where OT is approved (salary deducted but OT paid)

The OT detection system (`hrms/api/overtime.py:_upsert_from_attendance_doc`) creates `BEI Overtime Request` from Attendance records without checking if the employee has approved leave.

### P2.5-1: Block OT creation when leave exists [BUILD]

**What:** In `_upsert_from_attendance_doc()` (overtime.py line 510), add a leave check BEFORE creating the OT record:

```python
# After line 513 (employee_doc = _employee(...))
# Check if employee has approved leave on this date
has_leave = frappe.db.exists("Leave Application", {
    "employee": attendance_doc.employee,
    "from_date": ["<=", str(attendance_doc.attendance_date)],
    "to_date": [">=", str(attendance_doc.attendance_date)],
    "status": "Approved",
    "docstatus": ["!=", 2],
})
if has_leave:
    # Employee is on approved leave — no overtime allowed
    return None
```

**HARD BLOCKER:** This check must run BEFORE `_evaluate()` and `_sync_attendance_flags()`. Do NOT move it after OT record creation.

**Sentry:** Add `set_backend_observability_context(module="hr", action="overtime_leave_guard")` at function entry.

**Files:** `hrms/api/overtime.py`

### P2.5-2: Block leave filing when approved OT exists [BUILD]

**What:** Add validation in the Leave Application flow. Since BEI uses the standard Frappe Leave Application DocType (not a custom one), add validation via a hook or by extending the `validate()` method.

**Approach:** Add a custom validation in `hrms/overrides/leave_application_hooks.py` (or equivalent) that checks:

```python
def validate_no_overtime_conflict(doc, method=None):
    """Prevent leave filing on dates with approved overtime."""
    if doc.status != "Open" and doc.docstatus == 0:
        return  # Only check on new applications

    from frappe.utils import getdate, add_days
    cursor = getdate(doc.from_date)
    end = getdate(doc.to_date)
    while cursor <= end:
        ot_exists = frappe.db.exists("BEI Overtime Request", {
            "employee": doc.employee,
            "attendance_date": str(cursor),
            "overtime_status": ["in", ["Approved", "Payroll Locked", "Bridged"]],
        })
        if ot_exists:
            frappe.throw(
                _("Cannot file leave on {0} — approved overtime exists for that date. Cancel the OT first.").format(
                    frappe.utils.formatdate(cursor)
                )
            )
        cursor = add_days(cursor, 1)
```

Wire via `hooks.py`:
```python
doc_events = {
    "Leave Application": {
        "validate": "hrms.overrides.leave_application_hooks.validate_no_overtime_conflict"
    }
}
```

**HARD BLOCKER:** Only block when OT status is Approved/Locked/Bridged. Do NOT block on Pending OT — the supervisor may reject it. Blocking on Pending would create a deadlock where neither leave nor OT can be filed first.

**Files:** `hrms/overrides/leave_application_hooks.py` (new), `hrms/hooks.py`

### P2.5-3: Auto-cancel pending OT when leave is approved [BUILD]

**What:** When a Leave Application is approved (status changes to "Approved"), auto-reject any PENDING overtime requests for the same employee on overlapping dates:

```python
def on_leave_approved(doc, method=None):
    """Auto-reject pending OT when leave is approved for same dates."""
    if doc.status != "Approved":
        return
    from frappe.utils import getdate, add_days
    cursor = getdate(doc.from_date)
    end = getdate(doc.to_date)
    while cursor <= end:
        pending_ots = frappe.get_all("BEI Overtime Request", filters={
            "employee": doc.employee,
            "attendance_date": str(cursor),
            "overtime_status": ["in", ["Pending Review", "Pending Approval", "Needs Clarification", "Clarification Submitted"]],
        }, pluck="name")
        for ot_name in pending_ots:
            frappe.db.set_value("BEI Overtime Request", ot_name, {
                "overtime_status": "Rejected",
                "review_note": f"Auto-rejected: leave approved for this date ({doc.leave_type}, {doc.name})",
            })
        cursor = add_days(cursor, 1)
```

Wire via `hooks.py` on Leave Application `on_update`.

**Files:** `hrms/overrides/leave_application_hooks.py`, `hrms/hooks.py`

### P2.5-4: Hide non-functional leave types from dropdown [BUILD]

**What:** The Leave Request dialog shows 7 leave types but 3 don't work:
- **Compensatory Off** — no request mechanic built (needs CompensatoryLeaveRequest flow)
- **Casual Leave** — 0 balance for all employees (no allocations imported)
- **Privilege Leave** — 0 balance for all employees (no allocations imported)

**Fix in frontend:** Filter the leave types dropdown in `LeaveRequestDialog` to exclude types where:
1. Balance is 0 AND the type is NOT `is_lwp` (LWOP always shows regardless of balance)
2. OR the type is `Compensatory Off` (no filing mechanic exists yet)

**Approach:** The `useLeave` hook already fetches balances. Filter `leaveTypes` in the dialog:
```typescript
const usableTypes = leaveTypes.filter(lt => {
  if (lt === "Compensatory Off") return false;  // No mechanic
  if (lt === "Leave Without Pay") return true;   // Always available
  const bal = balances.find(b => b.leave_type === lt);
  return bal && bal.leaves_available > 0;
});
```

**Files:** `bei-tasks/components/hr/leave-request-dialog.tsx`

### P2.5-5: Add employee compensation eligibility tagging [BUILD]

**What:** Create a helper function in `overtime.py` that classifies whether an employee gets the voluntary compensation choice (OT pay vs Comp Off) or stays on auto-OT only.

**Policy (locked by CEO 2026-03-24):**

```
IF branch matches HEAD_OFFICE_KEYS → VOLUNTARY (choose OT pay or Comp Off)
ELIF department NOT IN ("Operations - BEI", "Commissary - BEI") → VOLUNTARY
ELSE → AUTO_OT_ONLY (store + commissary, no choice)
```

**Rationale:** Store and commissary employees work scheduled shifts — weekends/holidays are normal work days for them, so OT is auto-detected. Office employees (Finance, HR, Marketing, IT, Projects, Customer Support, Procurement, BD, Audit, Supply Chain) only work weekends/holidays as an exception, so they should choose their compensation.

**Implementation in `hrms/api/overtime.py`:**

```python
# --- Employee compensation eligibility ---
# Policy: CEO decision 2026-03-24
# Office employees: voluntary choice (OT pay OR comp off)
# Store + Commissary: auto-OT only (scheduled shift workers)
VOLUNTARY_COMPENSATION_EXCLUDED_DEPTS = {"Operations - BEI", "Commissary - BEI"}

def is_voluntary_compensation_eligible(employee_doc) -> bool:
    """Office employees get to choose OT pay vs Compensatory Off.
    Store and commissary employees don't — holidays/weekends are normal shifts.

    Rule:
      1. HEAD_OFFICE branch → always voluntary
      2. Department NOT in (Operations, Commissary) → voluntary
      3. Everything else → auto-OT only
    """
    if _is_head_office(employee_doc.branch):
        return True
    dept = _txt(employee_doc.department)
    if dept and dept not in VOLUNTARY_COMPENSATION_EXCLUDED_DEPTS:
        return True
    return False
```

**HARD BLOCKER:** Commissary is EXCLUDED from voluntary choice — all commissary employees (including office staff within commissary) stay on auto-OT. This was explicitly decided by the CEO. Do NOT add commissary exceptions.

**Files:** `hrms/api/overtime.py`

### P2.5-6: Write voluntary compensation policy document [BUILD]

**What:** Create `docs/policies/OVERTIME_COMPENSATION_POLICY.md` documenting the locked decision so future agents and HR team know the rule.

**Contents:**

```markdown
# Overtime & Compensation Policy

## Effective: 2026-03-24
## Approved by: Sam Karazi (CEO)

### Employee Classification

| Category | Departments | Compensation on Holiday/Weekend Work |
|----------|------------|--------------------------------------|
| **Office** | Finance, HR, IT, Marketing, Projects, Customer Support, Procurement, BD, Audit, Supply Chain | **Voluntary** — employee chooses OT pay OR Compensatory Off |
| **Store** | Operations (all store branches) | **Auto-OT** — system detects, supervisor approves |
| **Commissary** | Commissary (all roles) | **Auto-OT** — same as store |

### How it works

**Office employees:** When you work on a holiday, weekend, or your scheduled day off:
1. System detects the extra work from your punch-in/out
2. You receive a notification to choose your compensation
3. Choose: "Request OT Pay" (extra cash) OR "Request Comp Day Off" (1 paid day off)
4. If you don't choose within 48 hours, defaults to Comp Day Off
5. Your supervisor approves the request

**Store & Commissary employees:** Your schedule includes weekends/holidays as normal shifts.
1. System auto-detects overtime (>8 hours worked)
2. OT request goes to supervisor for approval
3. Approved OT is paid in the next payroll cycle

### Rules

1. You CANNOT have both OT pay and leave on the same day
2. If you have approved leave on a day, no OT can be created for that day
3. If you have approved OT on a day, you cannot file leave for that day
4. When leave is approved, any pending OT for those dates is auto-cancelled
5. Compensatory Off days must be used within 90 days of earning

### Technical implementation

- Eligibility function: `hrms.api.overtime.is_voluntary_compensation_eligible()`
- Branch keywords for office: BRITTANY, CAPITAL HOUSE, BGC, HEAD OFFICE, HQ
- Excluded departments: Operations - BEI, Commissary - BEI
- OT-Leave guard: `hrms.overrides.leave_application_hooks`
```

**Files:** `docs/policies/OVERTIME_COMPENSATION_POLICY.md`

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
| 11 | (API) | Create approved leave + attempt OT on same day | OT creation returns None (blocked) | P2.5-1 guard not working |
| 12 | (API) | Create approved OT + attempt leave on same day | Leave Application throws validation error | P2.5-2 guard not working |
| 13 | (API) | Create pending OT + approve leave on same day | Pending OT auto-rejected with reason | P2.5-3 auto-cancel not working |
| 14 | (Browser) | Open Leave Request dialog, check dropdown | Compensatory Off NOT shown, CL/PL hidden if 0 balance | P2.5-4 filter not working |
| 15 | (API) | Call is_voluntary_compensation_eligible for AGUARINO (store, Operations) | Returns False | P2.5-5 tagging wrong for store |
| 16 | (API) | Call is_voluntary_compensation_eligible for an HR/Finance employee | Returns True | P2.5-5 tagging wrong for office |
| 17 | (API) | Call is_voluntary_compensation_eligible for a Commissary employee | Returns False | P2.5-5 commissary exclusion broken |

## Requirements Regression Checklist

- [ ] Does VL create Attendance with status "On Leave"?
- [ ] Does SL create Attendance with status "On Leave"?
- [ ] Does LWOP NOT check balance (is_lwp=1)?
- [ ] Does LWOP show as leave_without_pay in salary calculation?
- [ ] Does VL show as 0 LWP (no salary deduction)?
- [ ] Does balance decrease after approved leave?
- [ ] Does balance restore after cancelled leave?
- [ ] Can employee file leave from my.bebang.ph UI?
- [ ] Does OT creation check for approved leave and return None if found? (P2.5-1)
- [ ] Does leave filing validate against approved OT and throw error? (P2.5-2)
- [ ] Does leave approval auto-reject pending OT on same dates? (P2.5-3)
- [ ] Are Compensatory Off, zero-balance CL, and zero-balance PL hidden from dropdown? (P2.5-4)
- [ ] Does the OT guard only block on Approved/Locked/Bridged OT, NOT Pending? (P2.5-2 HARD BLOCKER)
- [ ] Does is_voluntary_compensation_eligible return False for Operations dept? (P2.5-5)
- [ ] Does is_voluntary_compensation_eligible return False for Commissary dept? (P2.5-5 — CEO explicit exclusion)
- [ ] Does is_voluntary_compensation_eligible return True for HEAD_OFFICE branch? (P2.5-5)
- [ ] Does is_voluntary_compensation_eligible return True for non-Ops/non-Commissary depts? (P2.5-5)
- [ ] Does the policy document exist at docs/policies/OVERTIME_COMPENSATION_POLICY.md? (P2.5-6)
- [ ] Does every new/modified @frappe.whitelist() endpoint call set_backend_observability_context()?

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
  - Leave-overtime mutual exclusion guards deployed and verified (P2.5-1 through P2.5-3)
  - Non-functional leave types hidden from dropdown (P2.5-4)
  - Employee compensation eligibility function deployed and tested (P2.5-5)
  - Overtime compensation policy document committed (P2.5-6)
  - Reference document written
  - All 17 L3 scenarios pass
  - plan YAML and SPRINT_REGISTRY.md updated
- stop_only_for:
  - SSM/EC2 access failure for payroll verification
  - Leave type not configured in Frappe (missing from system)
- signoff_authority: single-owner (Sam)

## Scope Size Warning

Total ~36 units (was 22, +14 for Phase 2.5 leave-overtime guards + employee tagging + policy doc), within the 80-unit ceiling. Single session executable. Phase 2.5 is the code-change phase; all others are testing/documentation.

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
- Phase 2.5 requires backend code deployment via governor PR
- Sentry: Add `set_backend_observability_context()` to any new/modified `@frappe.whitelist()` endpoints (module="hr", action="leave_overtime_guard")
