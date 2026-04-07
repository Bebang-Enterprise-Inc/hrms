# Q3 — Compensation Setup Modal vs Per-Employee Page

**Verdict: BOTH BROKEN — but Lane A is rescued by Q1's EmployeeDetailDialog finding**

## List-page modal (`/dashboard/hr/payroll/compensation-setup`)

Click: first employee row button → modal opens with **only**:

```
9000746
9000746
Close
```

- 0 inputs
- 0 salary fields
- 1 button (Close)
- h2: `9000746`

**Lane F's EMP-UX-004 finding is REPRODUCED.** The modal is genuinely empty — only the bio ID is rendered. This is a real defect in the `/compensation-setup` list page row click handler.

## Per-employee dynamic route (`/dashboard/hr/payroll/compensation-setup/[employee]`)

Tested with `9000003`. After 8s wait + networkidle:

- url: `https://my.bebang.ph/dashboard/hr/payroll/compensation-setup/9000003`
- 0 inputs
- 0 salary fields (no salary structure, no basic pay, no allowance, no earnings, no deductions)
- 0 visible action buttons (only sidebar/topnav shell rendered)
- has_404: false (page didn't 404, it just rendered no content)
- 29 buttons total — all sidebar/navigation chrome

**The per-employee route is also broken** — it returns a layout shell with no compensation editor. Whether this is a missing page component, a failed data fetch, or a routing fallback is unclear from black-box probing.

## The rescue path: EmployeeDetailDialog (from Q1)

The dialog opened by clicking the employee-name button on `/dashboard/hr/employee-master` includes:

- Read-only COMPENSATION section showing all 16 compensation fields (Base Salary, Daily Rate, Gross Pay, all earnings/deductions, Bank, Account No., etc.)
- An **"Edit Compensation"** button at the bottom of that section

Whether Edit Compensation opens a working editor (vs the same broken modal) was not probed in this diagnostic. **Lane A must spike this in its first scenario** before committing to the EMP-SALARY-* chain. If Edit Compensation also opens an empty modal, Lane B (~10 salary scenarios) is fully blocked.

## Lane A / Lane B Impact

| Path | Status |
|---|---|
| Read compensation values for QA assertions | **RUNNABLE** via EmployeeDetailDialog COMPENSATION section |
| Edit compensation via `/compensation-setup` row click | **BLOCKED** (modal empty) |
| Edit compensation via `/compensation-setup/[id]` direct URL | **BLOCKED** (page renders nothing) |
| Edit compensation via EmployeeDetailDialog → Edit Compensation | **UNKNOWN — Lane A spike required first** |

## Recommendation

1. Lane A FIRST scenario (before any other comp scenario) = `SPIKE-EDIT-COMP-FROM-DIALOG`. If it works → continue with EMP-SALARY-* scenarios via that path. If it ALSO opens an empty modal → mark Lane B as fully BLOCKED and SKIP all 10 salary scenarios.
2. Both broken surfaces (`/compensation-setup` list modal, `/compensation-setup/[id]` page) should be escalated as **NEW** defects in addition to Lane F's EMP-UX-004 — Lane F only flagged the list modal; the per-employee dynamic route is a second, distinct defect.

## Screenshots

- `screenshots/q3_comp_list.png`
- `screenshots/q3_comp_list_modal.png`
- `screenshots/q3_comp_per_employee.png`

## New defect to add to S167

**EMP-UX-004b (NEW):** `/dashboard/hr/payroll/compensation-setup/[employee]` dynamic route renders only the layout shell — no compensation editor, no fields, no save action. Sister defect to EMP-UX-004 (the list-page modal). Both routes serve the same broken contract.
