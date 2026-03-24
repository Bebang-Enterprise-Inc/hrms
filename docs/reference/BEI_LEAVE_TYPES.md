# BEI Leave Types Reference

## Leave Types Available

| Leave Type | Code | Paid? | Days/Year | Balance Required? | Payroll Impact | Status |
|-----------|------|-------|-----------|-------------------|----------------|--------|
| **Vacation Leave** | VL | Yes | 15 | Yes | No deduction | Active |
| **Sick Leave** | SL | Yes | 15 | Yes | No deduction | Active |
| **Emergency Leave** | EL | Yes | 5 | Yes | No deduction | Active |
| **Leave Without Pay** | LWOP | No | Unlimited | No | Full day salary deducted | Active |
| **Casual Leave** | CL | Yes | Per allocation | Yes | No deduction | Inactive (no allocations) |
| **Privilege Leave** | PL | Yes | Per allocation | Yes | No deduction | Inactive (no allocations) |
| **Compensatory Off** | CO | Yes | Auto-created | No (auto) | No deduction | Inactive (no request mechanic) |

## How to File Leave

1. Login to **my.bebang.ph**
2. Go to **HR Self-Service** > **Leave Management**
3. Click **Request Leave**
4. Select leave type from dropdown (only types with available balance are shown)
5. Pick start and end dates
6. Enter reason
7. Click **Submit Request**
8. Your leave approver is notified automatically

## How Approval Works

1. Leave application is created with status **Open** (Pending)
2. Your leave approver reviews the request
3. Approver clicks **Approve** or **Reject**
4. If approved:
   - Status changes to **Approved**
   - Attendance records auto-created as "On Leave" for each day
   - Your leave balance is reduced
5. If rejected, you are notified with the reason

## Attendance and Payroll Impact

### Paid Leave (VL, SL, EL)
- Attendance record: status = "On Leave", leave_type = the specific type
- Payroll: **No deduction** — you receive full salary for the day
- Balance: Reduced by number of days taken

### Leave Without Pay (LWOP)
- Attendance record: status = "On Leave", leave_type = "Leave Without Pay"
- Payroll: **Full day salary deducted** — payment_days reduced by LWOP days
- Balance: Not tracked (unlimited, no allocation needed)

### Balance Restoration on Cancel
- If a leave application is cancelled, the balance is restored
- Attendance records are also cancelled

## Important Rules

1. **Cannot file leave on holidays** — Frappe automatically blocks leave filing on dates that are holidays in your Holiday List
2. **Cannot file leave on days with approved overtime** — the system blocks leave filing if you have approved/locked OT on that day
3. **Cannot have OT and leave on the same day** — the OT system blocks OT creation if you have approved leave on a date
4. **When leave is approved, pending OT is auto-cancelled** — if you had pending overtime requests on the same dates, they are automatically rejected

## Frequently Asked Questions

**Q: What if my VL/SL balance is 0?**
A: You can still file Leave Without Pay (LWOP). Your salary will be deducted for those days.

**Q: Can I file half-day leave?**
A: Yes, Frappe supports half-day leave. Select the half-day option when filing.

**Q: Why can't I see Compensatory Off in the dropdown?**
A: Compensatory Off requires a separate request flow (CompensatoryLeaveRequest) that is not yet built. It will be available in a future sprint.

**Q: Why can't I see Casual Leave or Privilege Leave?**
A: These leave types have 0 balance for all employees currently. They will appear once HR imports allocations for them.

**Q: What happens if I file leave and then want to cancel?**
A: You can request cancellation. Once cancelled, your balance is restored and the attendance records are removed.

## Technical Details

- Leave balance source of truth: **Leave Ledger Entry** table
- Balance check function: `get_leave_balance_on()` in `leave_application.py`
- Attendance creation: `update_attendance()` in `leave_application.py` on submit
- LWOP flag: `is_lwp=1` on the Leave Type record
- OT-Leave guard (backend): `hrms/overrides/leave_application_hooks.py`
- OT-Leave guard (OT side): `hrms/api/overtime.py:_has_approved_leave()`
