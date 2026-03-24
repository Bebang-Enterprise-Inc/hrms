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
- OT-Leave guard (OT side): `hrms.api.overtime._has_approved_leave()`
- OT-Leave guard (Leave side): `hrms.overrides.leave_application_hooks`
- Hooks wired in: `hrms/hooks.py` → Leave Application → validate + on_update
