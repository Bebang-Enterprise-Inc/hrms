# S166 Wave 1-Full Blocker Diagnostic — Summary

**Date:** 2026-04-07 PHT
**Time spent:** ~30 min
**Verdict:** Lane A is RUNNABLE with documented scoping. Two new collateral defects to escalate.

## TL;DR for the orchestrator

| Question | Verdict | Lane impact |
|---|---|---|
| Q1 — EmployeeDetailDialog row trigger | **FOUND** (`tbody tr` first child button) | Lane A unblocked for ~50 of 67 scenarios |
| Q2 — Clearance functional? | **STUB_CONFIRMED** (no doctypes, no UI) | Lane A clearance scenarios (~6) MUST SKIP |
| Q3 — Compensation modal/page broken? | **BOTH BROKEN** — but EmployeeDetailDialog has read-only comp + Edit Compensation button | Lane B SPIKE required before commitment |

## Verdict-by-verdict

### Q1 — Row trigger FOUND
Working selector: `page.locator('tbody tr').first().locator('button').first().click()`
- Wave 0 was wrong about ARIA roles — the table is a real `<table><tbody><tr>`, but the dialog opens via the first cell's `<button>` (employee name), NOT the row.
- Bio ID is text adjacent to the button (not in its accessible name), so `getByRole('button', { name: /9\d{6}/ })` fails.
- See `Q1_ROW_TRIGGER.md` for the full snippet, dialog contents, and DOM structure.
- Dialog contains all employee detail sections + an "Edit Compensation" entry point.

### Q2 — Clearance is a stub (Lane F was right)
- Backend doctype enumeration confirms: NO `BEI Clearance Station`, NO `BEI Clearance Item`, NO `Employee Clearance` doctype. Only upstream `Bank Clearance` (a finance reconciliation doctype unrelated to employees).
- `/clearance` page: only milestone tracker (Exit Interview, Final Pay Approval, COE) — no stations, no item return, no Documenso.
- Tested with `test.hr` who is currently in active separation since 2026-03-17 — even with separation context, no functional clearance UI appears.
- The Separation workflow itself (`Employee Separation` doctype, `Start Separation` button on `/dashboard/hr/separations`) IS functional.

### Q3 — Compensation editor surfaces broken
- List-page modal (`/compensation-setup` row click): opens with only `9000746 / 9000746 / Close`. **Reproduced.**
- Per-employee dynamic route (`/compensation-setup/9000003`): renders sidebar shell only, 0 inputs, 0 fields, 0 action buttons. **NEW defect, distinct from Lane F's finding.**
- Rescue: EmployeeDetailDialog has read-only COMPENSATION section + "Edit Compensation" button. **Whether that button opens a working editor was NOT tested in this diagnostic** — Lane A must spike it first.

## Lane A scoping recommendation

I do not have the exact 67-scenario list in front of me to enumerate runnable/skip line-by-line. The Lane A agent brief should apply this **routing table** to the catalog:

| Scenario family | Status | Selector / path |
|---|---|---|
| EMP-CREATE-* (AddNewEmployeeDialog) | **RUN** | Already proven in Wave 0 spike (combobox workaround) |
| EMP-VIEW-DETAIL-* | **RUN** | EmployeeDetailDialog via `tbody tr > button:first` |
| EMP-EDIT-PERSONAL-* | **RUN** | EmployeeDetailDialog → PERSONAL INFO → Edit |
| EMP-EDIT-EMPLOYMENT-* | **RUN** | EmployeeDetailDialog → EMPLOYMENT → Edit |
| EMP-COMPENSATION-VIEW | **RUN** | EmployeeDetailDialog → COMPENSATION (read-only) |
| EMP-SALARY-SETUP / EMP-SALARY-CHANGE | **SPIKE FIRST**, then RUN or SKIP | EmployeeDetailDialog → "Edit Compensation" button. If empty modal → SKIP entire family. |
| EMP-SALARY-SETUP via list page | **SKIP** | `/compensation-setup` modal is empty (Lane F EMP-UX-004 reproduced) |
| EMP-SALARY-SETUP via dynamic route | **SKIP** | `/compensation-setup/[id]` renders empty shell (NEW defect) |
| EMP-SENSITIVE-CHANGE-* (HR submit) | **RUN** | Initiation works (`Sensitive Changes queue` link in dialog) |
| EMP-SENSITIVE-CHANGE-* (Finance approve) | **VERIFY** | Lane F EMP-UX-005 was DEFECT_NOT_REPRODUCED — likely the approve/reject buttons are inside row detail click. Lane A should spike clicking a row in the "Pending Finance" tab as `test.finance` and check for inline action buttons before declaring blocked. |
| EMP-TRANSFER-* | **RUN** | TransferCreationForm discovered in Wave 0; uses combobox workaround |
| EMP-LEAVE-* | **RUN** | LeaveRequestDialog and Leave Command Center routes proven |
| EMP-OVERTIME-* | **RUN** | OvertimeForm_Crew / OvertimeForm_HR captured in Wave 0 |
| EMP-DISCIPLINARY-* | **RUN** | DisciplinaryCaseForm captured in Wave 0 |
| EMP-REGULARIZATION-* | **RUN** | RegularizationPage captured |
| EMP-ATTENDANCE-CORRECTION-* | **RUN** | AttendanceCorrectionForm captured |
| EMP-PAYSLIP-VIEW | **RUN** | PayslipPage captured |
| EMP-PAYROLL-RUN-* (Lane G — not Lane A) | RUN except 003 (OT gap pre-flagged) | n/a |
| EMP-SEPARATION-INITIATE | **RUN** | "Start Separation" button on `/dashboard/hr/separations` |
| EMP-SEPARATION-MILESTONE-VIEW | **RUN** | `/clearance` page renders milestone tracker |
| EMP-EXIT-INTERVIEW-* | **RUN (with caveat)** | `/clearance/exit-interview` route exists; Lane A should verify form actually accepts answers |
| EMP-CLEARANCE-STATION-* | **SKIP** | No doctype, no UI |
| EMP-CLEARANCE-ITEM-RETURN-* | **SKIP** | No item return UI |
| EMP-CLEARANCE-DOCUMENSO-* | **SKIP** | No Documenso integration in `/clearance` |
| EMP-COE-DOWNLOAD | **SKIP** | "Available after clearance" — no completion path |
| EMP-FINAL-PAY-APPROVAL | **SPIKE** | `Final Pay Approval` milestone shows "Pending HR" — Lane A should probe whether HR actually has an action surface |

**Approximate runnable count:** ~50-55 of 67 (assuming the SPIKE on Edit Compensation passes; if it fails, drop ~10 to ~40-45).

## Lane B (~10 salary scenarios) impact

**HIGH RISK.** Lane B is entirely dependent on Q3's Edit Compensation spike outcome. If the dialog's "Edit Compensation" button opens the same broken modal as the list page, Lane B has zero working entry surface.

**Recommendation:** Lane B should NOT be dispatched in Wave 1-Full until Lane A's first scenario reports back on the Edit Compensation spike. Sequence Lane B AFTER Lane A's first run.

## Lane C (~12 transfer scenarios) impact

**NO IMPACT.** Lane C uses `AddNewEmployeeDialog` (proven via combobox spike) and `TransferCreationForm` (discovered in Wave 0). Both surfaces are independent of the broken compensation/clearance routes. Lane C can dispatch in parallel with Lane A.

## Lane G (~6 payroll run scenarios) impact

**NO NEW BLOCKERS.** Pre-existing skip on `EMP-PAYROLL-RUN-003` (OT gap) stands. Payroll run scenarios use `PayrollProcessing`, `PayrollComparison`, `PayrollReviewOutput`, `PayrollHistory`, `PayrollRemittances` — all captured in Wave 0 dumps. Lane G can dispatch.

## NEW defects to escalate (S167)

1. **EMP-UX-004b (NEW, CRITICAL):** `/dashboard/hr/payroll/compensation-setup/[employee]` dynamic route renders only sidebar shell — no compensation editor, no fields. Sister defect to Lane F's EMP-UX-004 (list page modal). Both surfaces use the same broken data contract.
2. **EMP-STUB-005 confirmation (already S167-flagged):** Add backend evidence — clearance doctypes are entirely missing (`BEI Clearance Station`, `BEI Clearance Item`, `Employee Clearance` do NOT exist as Frappe doctypes). The gap is structural, not just UI. Implementation requires backend doctype creation in addition to UI work.

## Decision

**Ready to dispatch Wave 1-Full as follows:**
- **Lane A** (scoped, ~50-55 scenarios): DISPATCH with the routing table above and the SPIKE-EDIT-COMP-FROM-DIALOG as the FIRST scenario.
- **Lane C** (transfers): DISPATCH in parallel with Lane A.
- **Lane G** (payroll runs): DISPATCH in parallel with Lane A.
- **Lane B** (salary): **HOLD** until Lane A reports back on the Edit Compensation spike outcome. Likely 5-10 min after Lane A starts.

**Status: READY (with Lane B sequencing dependency)**

## Files written

- `findings.json` — full machine-readable diagnostic output
- `Q1_ROW_TRIGGER.md` — selector spike report
- `Q2_CLEARANCE.md` — stub confirmation + backend evidence
- `Q3_COMPENSATION.md` — both surfaces broken + rescue path
- `screenshots/` — q1/q2/q3 visual evidence (5 PNGs)
- `api_queries/` — raw doctype enumeration JSON
- `scripts/testing/l3_s166_wave1_full_diagnostic.mjs` — reproducible probe script
