---
sprint_id: S166
display: Sprint 166
title: "L3 Full Employee Lifecycle Scenarios — Hire → Edit → Compensate → Regularize → Leave → OT → Attendance → Payroll → Disciplinary → Transfer → Terminate → Exit Interview → Final Pay → Deactivate → Rehire"
branch: s166-l3-employee-lifecycle-scenarios
status: COMPLETED
planned_date: 2026-04-06
completed_date: 2026-04-07
depends_on: S164, S160, S148, S158, S114, employee-transfer flow, clearance module, leave module, overtime module, attendance-correction module, payroll-processing module, disciplinary module
total_work_units: 63
amendment_version: 3
amendment_date: 2026-04-07
amendment_reason: "v3 (2026-04-07 PM): Replace single-session execution model with 8-lane parallel /teammates topology + mandatory independent Audit Agent gate. Original v1/v2 sequential model proved infeasible during 2026-04-07 chat-driven attempt — selector flake on Radix dialog overlays + context exhaustion would force corrupt-success at scale. v3 adds: Wave 0 selector discovery, Wave 1 8-lane parallel execution with per-lane evidence files, Wave 1.5 mandatory Audit Gate (separate agent, NOT the lane runner) with re-run authority, Wave 2 merge+cleanup+closeout, pilot-first sequencing (D+E+F+H before A+B+C+G), Bio ID sequence collision rule, try/finally per-lane cleanup contract. v2 (2026-04-07 AM): Post-audit amendment, 4 parallel audit agents walked the live production portal and identified 30+ functional gaps and 25 UX improvements. Added EMP-UX-* (10) and EMP-STUB-* (5). Total 122→137 scenarios, 34→36 prefixes, 60→63 work units."
execution_type: scenario-authoring + test-execution (no product code)
execution_topology: 8-lane-parallel-with-audit-gate
frontend_pr: null
backend_pr: null
catalog_pr: hrms#469
phase_0_complete: true
phase_1_complete: true
phase_2_complete: true
execution_summary:
  total_scenarios: 137
  pass: 71
  defect_pass: 20
  fail: 6
  skip: 40
  lanes_completed: 8
  retest_iterations: 5
  defects_found: 21
  defects_closed_by_s170: 6
  defects_open: 12
  new_defects_from_retest: 3
  wave2_pr: pending
  canonical_evidence: output/l3/s166/SUMMARY.md
---

# S166: L3 Full Employee Lifecycle Scenarios

## Mission

Prove that the complete employee lifecycle on `my.bebang.ph` — from the moment HR clicks **"Add New Employee"** to the moment the ex-employee can no longer log in and their Bio ID is no longer on the device — works end-to-end in a real browser with real data. No corner cutting. No scope dodges. No "covered elsewhere" deferrals.

Today the HR module scenario catalog has only 3 surface-smoke entries (HRM-001/002/003) that load pages but do not click any submit button. After S164 landed, we have zero end-to-end coverage of employee creation, editing, compensation changes, regularization, transfer, or termination — the exact workflows HR uses daily. This sprint closes the entire gap in one pass.

**Full lifecycle covered** (19 stages, 137 scenarios):

1. **HIRE** — S164 Add New Employee dialog (create, happy/edge/adversarial/RBAC, Bio ID sequence integrity)
2. **EDIT** — S160 EmployeeDetailDialog (personal, employment, contact, address, bank, government IDs, profile photo)
3. **COMPENSATE** — `/dashboard/hr/payroll/compensation-setup/[employee]` page (salary structure assignment + earnings + deductions + formula components + sensitive-change approval queue)
4. **REGULARIZE** — Probationary → Regular transition (regularization date, 13th month eligibility)
5. **LEAVE** — Employee applies for leave via `LeaveRequestDialog`, supervisor approves/rejects, balance deducted
6. **OVERTIME** — Employee/supervisor files OT, HR approves with approved hours + OT type, appears on payslip
7. **ATTENDANCE CORRECTION** — Employee submits correction request, supervisor approves, attendance record updated
8. **PAYROLL RUN** — Full HR-driven cycle: process → review output → approve → remit (not just "downstream check" — HR clicks every button)
9. **PAYSLIP** — Employee views their payslip, verifies gross/net/deductions match expectations
10. **DISCIPLINARY** — HR issues memo/NTE → employee responds → HR resolves (suspension or clearance)
11. **TRANSFER** — Branch change with OLD device DELETE + NEW device INSERT + payroll branch update
12. **TERMINATE** — Separation trigger → Clearance request → station assignments → sign-offs → Documenso e-signature
13. **EXIT INTERVIEW** — Separating employee fills exit survey, HR reviews analytics
14. **FINAL PAY** — Last payslip calculation, BIR 2316, final pay released
15. **COMPLIANCE** — 13th month computation verification for the regular employee
16. **DEACTIVATE** — User account disabled on `my.bebang.ph`, Bio ID `DELETE USERINFO` dispatched to device
17. **REHIRE** — Re-activate or create new record for previously terminated employee
18. **ENRICHMENT** — HR monitors self-service enrichment tracker, verifies completion rates update
19. **CLEANUP** — All test employees Left, Bio ID sequence clean, zero active L3 stragglers

**Self-service note:** The newly created test employee has no User account (S164 excluded auto-provisioning). Self-service scenarios (leave filing, payslip viewing, OB request) use `test.crew1@bebang.ph` — an existing test account with a valid login — instead of the freshly created employee. HR-driven scenarios (compensate, payroll, terminate) operate on the freshly created employee.

**This is an execution-only sprint.** No product code changes. Only scenario authoring + test execution + defect triage. Any product defects found become their own follow-up sprints.

---

## Scope

### In scope — 137 scenarios across 36 prefixes

| Stage | Prefix | Count | Surface |
|---|---|---|---|
| HIRE | `EMP-CREATE-*` | 10 | S164 Add New Employee dialog |
| EDIT | `EMP-EDIT-PERSONAL-*` | 6 | S160 personal section (name, DOB, gender) |
| EDIT | `EMP-EDIT-CONTACT-*` | 4 | S160 contact + emergency contact |
| EDIT | `EMP-EDIT-ADDRESS-*` | 3 | S160 current + permanent address |
| EDIT | `EMP-EDIT-EMPLOYMENT-*` | 5 | S160 designation/department/reports_to/employment_type |
| EDIT | `EMP-PHOTO-*` | 2 | S160 profile photo upload + replace |
| EDIT | `EMP-BANK-*` | 3 | S160 bank_name / bank_ac_no |
| EDIT | `EMP-GOVID-*` | 5 | S160 TIN/SSS/PhilHealth/Pag-IBIG number + file edits |
| COMPENSATE | `EMP-SALARY-SETUP-*` | 4 | `/payroll/compensation-setup/[employee]` page — base + earnings + deductions + formula |
| COMPENSATE | `EMP-SALARY-CHANGE-*` | 6 | Raise via sensitive-change queue, reject, effective-dated, partial component, audit, adversarial |
| COMPENSATE | `EMP-SALARY-PAYROLL-*` | 2 | Downstream payroll run uses the new approved rate |
| REGULARIZE | `EMP-REGULARIZE-*` | 3 | Probationary → Regular, regularization date, 13th month eligibility |
| LEAVE | `EMP-LEAVE-*` | 5 | Apply leave via `LeaveRequestDialog` → supervisor approve → balance check → reject path → cancel |
| OVERTIME | `EMP-OVERTIME-*` | 4 | File OT → HR approve with approved hours + OT type → reject path → payslip reflection |
| ATTENDANCE | `EMP-ATTENDANCE-*` | 3 | Submit correction → supervisor approve → attendance record updated |
| PAYROLL RUN | `EMP-PAYROLL-RUN-*` | 6 | Process → review output → approve → remittances → history → comparison |
| PAYSLIP | `EMP-PAYSLIP-*` | 2 | Employee views own payslip, verifies gross/net/deductions |
| DISCIPLINARY | `EMP-DISCIPLINARY-*` | 5 | Issue memo/NTE → employee responds → HR resolves → suspension path → clearance escalation |
| TRANSFER | `EMP-TRANSFER-*` | 5 | Transfer request → approval → OLD device DELETE → NEW device INSERT → payroll branch update |
| BIO CHANGE | `EMP-BIOCHANGE-*` | 2 | Reassign Bio ID (device-level DELETE old + INSERT new for same employee) |
| CROSS-CUT | `EMP-COMPLETION-*` | 2 | Profile completion % recomputes; Missing Bio Device count decrements |
| CROSS-CUT | `EMP-CONFLICT-*` | 1 | Concurrent edit conflict (two HR users editing same employee) |
| ADMS | `EMP-ADMS-*` | 2 | Initial enrollment queued + actually dispatched |
| NOTIFY | `EMP-CHAT-*` | 2 | Chat message body verified + absence of legacy `Onboarding Request:` line |
| RBAC | `EMP-RBAC-*` | 5 | Consolidated: crew UI blocked, crew API blocked, finance approve-only, field-level, read vs write |
| TERMINATE | `EMP-TERMINATE-*` | 6 | Trigger separation → Clearance request → stations → items → Documenso e-sig → final approval |
| EXIT INTERVIEW | `EMP-EXITINTERVIEW-*` | 3 | Employee fills exit survey → HR reviews analytics → data persisted |
| FINAL PAY | `EMP-FINALPAY-*` | 3 | Last payslip calculation, BIR 2316, final pay release |
| COMPLIANCE | `EMP-COMPLIANCE-*` | 2 | 13th month computation verification for regularized employee |
| DEACTIVATE | `EMP-USERDISABLE-*` | 2 | User account disabled check, login attempt after Left fails |
| DEACTIVATE | `EMP-ADMSREMOVE-*` | 2 | DELETE USERINFO queued, actually dispatched to device |
| REHIRE | `EMP-REHIRE-*` | 2 | Rehire previously Left employee, historical data preserved |
| ENRICHMENT | `EMP-ENRICHMENT-*` | 2 | HR views enrichment tracker, completion rate updates after edits |
| UX GAPS | `EMP-UX-*` | 10 | Audit-derived: document UX gaps found by the 4 parallel audit agents as test evidence |
| STUB PAGES | `EMP-STUB-*` | 5 | Audit-derived: visit known-stub pages and capture current state for the next sprint backlog |
| CLEANUP | `EMP-CLEAN-*` | 3 | Final sweep, audit query = 0, Bio ID sequence clean |
| **TOTAL** | | **137** | |

### Test employees created during the run

| ID | Role | Used for | Fate |
|---|---|---|---|
| **EMP-A** | Main lifecycle subject | Full chain: create → edit → compensate → regularize → transfer → terminate → clearance → final pay → deactivate | Status = Left at end |
| **EMP-B** | Multi-component salary testing | Parallel salary change paths (approval vs rejection need separate employees) + Bio ID reassignment | Status = Left at end |
| **EMP-C** | Rehire subject | Created, terminated quickly, then rehired to test re-activation path | Status = Active or Left |
| *(existing)* `TEST-CREW-001` | Self-service actor | Files leave, views payslip, files OT/OB, fills exit interview (has User account, unlike freshly created employees) | Not touched — existing test account |
| *(existing)* `TEST-SUPERVISOR-001` | Approval actor | Approves leave, OT, attendance corrections for TEST-CREW-001 | Not touched |

All scenarios live in one new module file `docs/testing/scenarios/modules/hr-employee-lifecycle.md`.

### Out of scope
- Product code changes (any bug found is logged, not fixed in-sprint)
- Existing HRM-001/002/003 surface-smoke scenarios (untouched)
- `/dashboard/hr/onboarding` self-service flow (covered by existing `onboarding` module)
- Recruitment / MRF / offer pipeline (covered by existing HRM-002)
- Bulk CSV employee import (not a UI flow on my.bebang.ph)
- Salary Structure template/component definition (admin-only, not HR-operator workflow)
- Multi-employee bulk operations (bulk transfer, bulk separation) — single-employee lifecycle only
- Payroll calendar / cutoff configuration (admin-only)
- Performance evaluation cycle (annual review cycle — not part of single-employee daily lifecycle)
- Loan management (not yet built)
- Benefits enrollment (not yet built)
- Schedule management (shift assignment — tests only the schedule page loads, not the full shift-planning flow)
- Official Business filing (checkin/checkout while offsite — exists but low-priority vs the 19 stages above)
- Gov ID bulk import (batch operation, tested separately via `hr.md` HRM-003)
- Coverage management (labor plan module — exists but is a separate workforce-planning surface, not per-employee lifecycle)

### Dependencies
- **S164 merged + deployed** (Add New Employee dialog live) — ✅ confirmed live 2026-04-06
- **S160 merged + deployed** (EmployeeDetailDialog live) — ✅ confirmed live
- **S148/S158 merged + deployed** (CompensationDetailDialog + approval queue) — ✅ confirmed live
- **Test accounts** from `memory/testing-accounts.md` with passwords `BeiTest2026!`
- **Production backend** at `hq.bebang.ph` and frontend at `my.bebang.ph` both reachable
- **Playwright workspace** at `playwright-bei-erp-workspace/` with working auth session fixtures

---

## Non-Negotiable Rules (No Corner Cutting)

These rules enforce the S092 anti-corrupt-success discipline and the S099 L3 handoff protocol.

1. **Real browser, not API.** Every scenario MUST drive the UI through Playwright. Direct API calls are forbidden for submit steps. A scenario that posts to `hrms.api.employee_create.create_employee_direct` without opening the dialog and clicking "Create Employee" is a FAIL regardless of the response code.

2. **Real sidebar/menu navigation.** No direct deep-link URLs like `?open=dialog`. The scenario must click through `sidebar → HR → Employee Master → [button click]` as a real user would.

3. **Real form fills on real form controls.** Fill inputs by their visible labels (Label/placeholder/text), not by hardcoded CSS selectors that bypass the label wiring. Every dropdown must be opened and an item clicked — no `page.selectOption()` shortcut when the control is a shadcn Popover combobox.

4. **Real submit, real network capture.** Every scenario must capture the outgoing POST to `/api/frappe/api/method/...` with its full request body AND the response. These go into `output/l3/s166/api_mutations.json` per S092 rule 2.

5. **Real state verification.** Every scenario that creates or edits data MUST re-read the affected record through a subsequent API call and verify the mutation landed. No "toast success = pass" shortcuts. State verification goes into `output/l3/s166/state_verification.json` per S092 rule 3.

6. **Evidence gate is the judge, not the agent.** If any one of `form_submissions.json`, `api_mutations.json`, `state_verification.json` has fewer entries than the scenario count, the run is FAIL — regardless of what the agent says in its summary.

7. **No toy data.** Names like `Test Test` or Bio IDs like `1234567` are forbidden. Use realistic Filipino names (`Juan Dela Cruz`, `Maria Santos Reyes`), real branch names from production, real dates. Names must be uniquified with a timestamp suffix so reruns don't collide (`Juan Dela Cruz (L3 2026-04-06 14:32:00)`).

8. **Cleanup is part of the scenario.** Every test employee created during the run MUST be de-activated at the end via a CLEAN scenario. Failing to clean up fails the sprint — the 2026-02-26 L3 test pollution that S164's post-deploy fix had to remediate (6 bogus rows with Bio IDs up to 9709647) is the exact failure mode this rule prevents.

9. **RBAC must be tested as an adversarial scenario, not just a visibility check.** "Button not visible to crew user" is necessary but not sufficient. The scenario must also attempt the direct API call as the crew role and verify 403 Forbidden. Visibility-only RBAC tests miss backend gaps.

10. **Full lifecycle in a single chain.** The sprint execution run must create one test employee and carry it through the entire chain: CREATE → EDIT personal → EDIT employment → ADD salary → APPROVE salary → REJECT edit → AUDIT log visible → DE-ACTIVATE. A scenario catalog that only tests isolated endpoints misses integration bugs.

11. **Pre-written scenarios only.** The executing agent in the fresh session does NOT invent scenarios. It reads this plan and the companion scenario file, executes each in order, captures evidence, and reports. S099 L3 handoff rule is non-negotiable.

---

## Existing Assets to Reuse

Before writing new scenarios, REFERENCE or EXTEND these:

| Asset | Classification | Usage |
|---|---|---|
| `docs/testing/scenarios/COMMON.md` | REFERENCE | Standard login helper, 150KB photo generator, evidence path conventions |
| `docs/testing/scenarios/index.yaml` | EXTEND | Register new `hr-employee-lifecycle` module key |
| `docs/testing/scenarios/modules/hr.md` | REFERENCE ONLY | Existing surface-smoke scenarios — do NOT modify |
| `docs/testing/scenarios/flows/employee-transfer.md` | REFERENCE | Pattern for multi-step scenarios that chain employee state changes |
| `scripts/testing/l3_v2_runner.py` | REFERENCE | Entry point for `/l3-v2-bei-erp` execution |
| `scripts/testing/l3_browser_guard.py` | REFERENCE | Guard that validates evidence files match scenario count |
| `scripts/testing/l3_manifest_check.py` | REFERENCE | Pre-run manifest validation |
| `playwright-bei-erp-workspace/` | REFERENCE | Real browser session with storageState for each test account |
| `memory/testing-accounts.md` | REFERENCE | Test account list (HR, Crew, Finance, etc.) — all passwords `BeiTest2026!` |
| `.claude/skills/l3-v2-bei-erp/SKILL.md` | REFERENCE | Execution protocol — scenario-driven, no agent-authored tests |

**No new product code. No new helpers. No new runners.** If an existing runner can't handle a scenario, fix the scenario — not the runner.

---

## Phases

### Phase 0 — Research and precondition gathering (4 units)

Before writing any scenario:

1. **Read the surface plans** to pin down exact field names, selectors, API methods, and RBAC gates:
   - `docs/plans/2026-04-06-sprint-164-add-new-employee-entry-point.md` (hire)
   - `docs/plans/2026-04-05-sprint-160-employee-detail-dialog.md` (edit + compensation dialog shell)
   - Whichever S148/S158 plan is canonical for CompensationDetailDialog / compensation-setup page
   - Whichever S114 plan is canonical for the sensitive-change approval queue
   - The `employee-transfer` flow plan (transfer)
   - The canonical clearance / separation plan (termination)
   - Any S-plan for payroll run / final pay / BIR 2316 generation

2. **Read the deployed frontend components** to list exact labels, button text, roles, and endpoints for ALL 19 stages:
   - `app/dashboard/hr/employee-master/new-employee-dialog.tsx` (hire)
   - `app/dashboard/hr/employee-master/employee-detail-dialog.tsx` — all collapsible sections (edit)
   - `app/dashboard/hr/payroll/compensation-setup/[employee]/page.tsx` — 523-line per-employee compensation page (compensate). **NOTE: the real compensation flow is this DEDICATED PAGE, not a dialog inside the EmployeeDetailDialog.**
   - `app/dashboard/hr/payroll/sensitive-changes/page.tsx` — 635-line approval queue (compensate approval)
   - `app/dashboard/hr/payroll/processing/page.tsx` — 784-line payroll processing page (payroll run)
   - `app/dashboard/hr/payroll/review-output/page.tsx` — payroll review (payroll run)
   - `app/dashboard/hr/payroll/remittances/page.tsx` — remittance generation (payroll run)
   - `app/dashboard/hr/payroll/comparison/page.tsx` — period-over-period comparison (payroll run)
   - `app/dashboard/hr/payroll/history/page.tsx` — payroll history (payroll run)
   - `app/dashboard/hr/payslip/page.tsx` — employee payslip view (payslip)
   - `app/dashboard/hr/leave/page.tsx` — 330-line leave page with `LeaveRequestDialog` (leave)
   - `app/dashboard/hr/overtime/page.tsx` — 533-line OT page with approve/reject/clarify/escalate (overtime)
   - `app/dashboard/hr/attendance-correction/page.tsx` — 297-line correction submit (attendance)
   - `app/dashboard/hr/performance/regularization/page.tsx` — 198-line regularization (regularize)
   - `app/dashboard/hr/disciplinary/page.tsx` — 437-line disciplinary case page (disciplinary)
   - `app/dashboard/hr/disciplinary/[id]/page.tsx` — individual case detail (disciplinary)
   - `app/dashboard/hr/separations/page.tsx` — 546-line separation page (terminate)
   - `app/clearance/page.tsx` — 308-line clearance page (terminate)
   - `app/clearance/exit-interview/page.tsx` or `app/dashboard/hr/exit-interview/[id]/page.tsx` (exit interview)
   - `app/dashboard/hr/exit-interview/analytics/page.tsx` — HR analytics view (exit interview)
   - `app/dashboard/hr/compliance/13th-month/page.tsx` — 13th month computation (compliance)
   - `app/dashboard/hr/enrichment-tracker/page.tsx` — 1020-line enrichment tracker (enrichment)
   - `app/dashboard/hr/transfers/page.tsx` — transfer creation (transfer)

3. **Query production (read-only)** for preconditions:
   - 3 real branches mapped in `DEVICE_TO_STORE` (HIRE branch, TRANSFER-FROM branch, TRANSFER-TO branch)
   - 1 real branch NOT in `DEVICE_TO_STORE` (NO_DEVICE_FOR_BRANCH scenario)
   - Current `generate_next_bio_id()` value (baseline for EMP-CLEAN-003 assertion)
   - A real Salary Structure template (name + full component list including earnings + deductions)
   - Current leave types defined in the system (for leave scenarios)
   - Current overtime types defined (Regular OT, Rest Day OT, Holiday OT, etc.)
   - List of clearance stations defined in the system
   - Disciplinary action types / categories available
   - Current payroll period that would include a freshly-created employee
   - Whether `test.crew1@bebang.ph` has leave balance remaining (needed for leave-apply scenario)
   - Documenso `sign.bebang.ph` availability (HEAD /api/)
   - **Test account login verification** — all 5 accounts needed for this sprint:
     - `test.hr@bebang.ph` (HR Manager — primary actor)
     - `test.crew1@bebang.ph` (Crew — self-service actor + negative RBAC target)
     - `test.finance@bebang.ph` (Finance — salary approval)
     - `test.supervisor@bebang.ph` (Supervisor — leave/OT/attendance approval)
     - `test.area@bebang.ph` (Area Supervisor — transfer approval if needed)

4. **Write `PRECONDITIONS.md`** in the run directory with all findings:
   - Exact branch names picked for HIRE / TRANSFER-FROM / TRANSFER-TO / NO-DEVICE
   - Exact Salary Structure template name + component list
   - Exact leave types + whether test.crew1 has balance
   - Exact overtime types available
   - Exact disciplinary action categories
   - Exact clearance station list
   - Exact payroll period applicable
   - Exact approval-queue route URL
   - Exact clearance-request entry point (dialog or route)
   - Exact exit-interview route (is it under `/clearance/exit-interview` or `/dashboard/hr/exit-interview/[id]`?)
   - Whether Documenso is reachable
   - All 5 test accounts confirmed login-able via real browser
   - **Which pages are real vs stubs** — if a page like `leave-command-center` is only 1 line, it's a stub and we should note that the scenario will document "feature not implemented" rather than test a non-existent flow

### Phase 1 — Author the scenario catalog (24 units)

Create `docs/testing/scenarios/modules/hr-employee-lifecycle.md` with **all 137 scenarios listed below**, following the exact format of `modules/maintenance.md` (ID, Type, Role, Call, Payload as JSON, Assert as bullet list).

Scenarios are grouped and numbered with the prefixes listed in the Scope section. The full scenario list is in the subsections below.

**Full scenario list:**

> **Chain convention:** Most scenarios chain off `EMP-CREATE-001`. That scenario produces the "base test employee" used by everything downstream. `EMP-CREATE-010` produces a second test employee used as a transfer-destination test subject. Scenarios explicitly mark `Depends on:` to show the chain.

#### EMP-CREATE (10 scenarios — S164 surface)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-CREATE-001 | happy | test.hr@bebang.ph | Open Employee Master, click "Add New Employee" button, fill only 6 mandatory fields (first_name, last_name, DOB, gender, branch, company) with realistic Filipino name + real BEI branch, submit, assert toast shows `Employee BEI-EMP-2026-XXXXX created. Bio ID 90XXXXX enrolled on device UDP...`, assert row appears at top of Employee Master table after refetch. Evidence must include the real device SN from the toast. |
| EMP-CREATE-002 | happy | test.hr@bebang.ph | Fill all optional fields (middle_name, designation, department, date_of_joining, employment_type, personal_email, cell_number, tin_number, sss_number, philhealth_number, pagibig_number), submit, re-open the new employee via EmployeeDetailDialog, verify every field round-tripped. |
| EMP-CREATE-003 | edge | test.hr@bebang.ph | Leave date_of_joining blank, submit, verify employee created with `date_of_joining == today()`. |
| EMP-CREATE-004 | edge | test.hr@bebang.ph | Pick a branch that is NOT in `DEVICE_TO_STORE` (from Phase 0 precondition list), submit, verify toast shows `No biometric device mapped to {branch} — enroll manually`, verify employee still created, verify `adms_enrollment.reason == "NO_DEVICE_FOR_BRANCH"` in the captured API response. |
| EMP-CREATE-005 | edge | test.hr@bebang.ph | Attach a real 150KB PDF for TIN proof, a 150KB JPG for SSS proof, leave PhilHealth/Pag-IBIG empty, submit, verify 2 files uploaded to the new employee, verify `custom_tin_proof_url` and `custom_sss_proof_url` are populated on the server. |
| EMP-CREATE-006 | adversarial | test.hr@bebang.ph | Enter DOB in the future (2030-01-01), click submit, assert dialog stays open, assert backend returns 417 / ValidationError `date_of_birth must be in the past`, assert no employee was created. |
| EMP-CREATE-007 | adversarial | test.hr@bebang.ph | Enter an unknown gender (`gender = "NotAGender"`) via the Select (force-select if needed), submit, assert backend returns `Unknown gender: NotAGender`, assert no employee created. |
| EMP-CREATE-008 | rbac-ui | test.crew1@bebang.ph | Navigate to `/dashboard/hr/employee-master`. Assert page either returns Access Restricted OR loads but the "Add New Employee" button is NOT visible in the header. Capture a screenshot as evidence. |
| EMP-CREATE-009 | rbac-api | test.crew1@bebang.ph | As logged-in crew user, issue a direct POST to `/api/frappe/api/method/hrms.api.employee_create.create_employee_direct` with a valid payload. Assert HTTP 403 / PermissionError. Assert no employee was created. This closes the "visibility-only" RBAC gap. |
| EMP-CREATE-010 | regression | test.hr@bebang.ph | Create a test employee and capture the assigned Bio ID. Immediately create a second one. Assert the second Bio ID is exactly `first + 1`. This guards against the 2026-02-26 L3 pollution pattern where test data broke the sequence. |

#### EMP-EDIT-PERSONAL (6 scenarios — S160 personal section)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-EDIT-PERSONAL-001 | happy | test.hr@bebang.ph | Depends on EMP-CREATE-001. Change `middle_name` from blank to `Dela Cruz`, save, verify persistence via subsequent GET and via hard page reload. |
| EMP-EDIT-PERSONAL-002 | edge | test.hr@bebang.ph | Depends on EMP-CREATE-001. Change `first_name` to handle a legal name correction case (e.g., typo fix). Verify `employee_name` recomputed downstream. |
| EMP-EDIT-PERSONAL-003 | edge | test.hr@bebang.ph | Depends on EMP-CREATE-001. Change `date_of_birth` to a corrected past date, save, verify. (Unusual but happens when HR discovers an ID correction.) |
| EMP-EDIT-PERSONAL-004 | adversarial | test.hr@bebang.ph | Depends on EMP-CREATE-001. Attempt to change `date_of_birth` to a future date, assert rejection. |
| EMP-EDIT-PERSONAL-005 | happy | test.hr@bebang.ph | Depends on EMP-CREATE-001. Change `gender` via the Select, save, verify the change and verify the Gender value came from the Frappe Gender DocType (not a hardcoded tuple). |
| EMP-EDIT-PERSONAL-006 | regression | test.hr@bebang.ph | Depends on EMP-CREATE-001. Open the personal section, make a change, click Cancel (not Save). Re-open and verify the change was NOT persisted. |

#### EMP-EDIT-CONTACT (4 scenarios — S160 contact + emergency contact)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-EDIT-CONTACT-001 | happy | test.hr@bebang.ph | Depends on EMP-CREATE-001. Change `cell_number` from blank to `09171234567`, change `personal_email` to a realistic value, save, verify both fields persisted. |
| EMP-EDIT-CONTACT-002 | happy | test.hr@bebang.ph | Depends on EMP-CREATE-001. Fill `person_to_be_contacted`, `emergency_phone_number`, `relation` (e.g., "Spouse"). Save. Verify via GET. |
| EMP-EDIT-CONTACT-003 | adversarial | test.hr@bebang.ph | Depends on EMP-CREATE-001. Enter a malformed email (`no-at-sign`), click Save, assert rejection, assert old value remains. |
| EMP-EDIT-CONTACT-004 | adversarial | test.hr@bebang.ph | Depends on EMP-CREATE-001. Enter an invalid cell number (`abc12345`), assert rejection. |

#### EMP-EDIT-ADDRESS (3 scenarios — S160 addresses)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-EDIT-ADDRESS-001 | happy | test.hr@bebang.ph | Depends on EMP-CREATE-001. Fill `current_address` with a multi-line realistic address (street, barangay, city, ZIP). Save. Verify via GET and by re-opening the dialog. |
| EMP-EDIT-ADDRESS-002 | happy | test.hr@bebang.ph | Depends on EMP-CREATE-001. Fill `permanent_address` with a different address from `current_address`. Save. Verify both are stored separately. |
| EMP-EDIT-ADDRESS-003 | edge | test.hr@bebang.ph | Depends on EMP-CREATE-001. If a "same as current" checkbox exists for permanent address, click it, verify permanent address copies from current. If no such checkbox, document and SKIP this scenario (document why in evidence). |

#### EMP-EDIT-EMPLOYMENT (5 scenarios — S160 employment section)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-EDIT-EMPLOYMENT-001 | happy | test.hr@bebang.ph | Depends on EMP-CREATE-001. Change `designation` via the designation selector, save, verify the Employee Master table row reflects the new designation after refetch. |
| EMP-EDIT-EMPLOYMENT-002 | happy | test.hr@bebang.ph | Depends on EMP-CREATE-001. Change `department` via the department selector, save, verify. |
| EMP-EDIT-EMPLOYMENT-003 | happy | test.hr@bebang.ph | Depends on EMP-CREATE-001. Change `reports_to` to another existing employee via the user selector, save, verify `reports_to_name` computed field updates in the masterlist row. |
| EMP-EDIT-EMPLOYMENT-004 | happy | test.hr@bebang.ph | Depends on EMP-CREATE-001. Change `employment_type` (e.g., from "Probitionary" to "Regular" — mirrors regularization path but via direct field edit, not the regularization workflow). Save. Verify. |
| EMP-EDIT-EMPLOYMENT-005 | regression | test.hr@bebang.ph | Depends on EMP-CREATE-001. Change a field, save, hard-reload the whole page, re-open dialog. Assert change persisted (not just in-memory state). |

#### EMP-PHOTO (2 scenarios — S160 profile photo)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-PHOTO-001 | happy | test.hr@bebang.ph | Depends on EMP-CREATE-001. Upload a real 150KB JPG photo (generated from the SKILL.md fixture) as the employee's profile picture. Save. Verify `image` field is populated. Verify the URL returns HTTP 200 when GETted. |
| EMP-PHOTO-002 | edge | test.hr@bebang.ph | Depends on EMP-PHOTO-001. Upload a DIFFERENT photo to replace the first. Verify the `image` URL changed AND the old photo file is either deleted OR orphaned (document whichever the implementation does). |

#### EMP-BANK (3 scenarios — S160 bank details)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-BANK-001 | happy | test.hr@bebang.ph | Depends on EMP-CREATE-001. Fill `bank_name` (e.g., "BDO Unibank") and `bank_ac_no` (e.g., "001234567890"). Save. Verify via GET. |
| EMP-BANK-002 | happy | test.hr@bebang.ph | Depends on EMP-BANK-001. Change `bank_ac_no` to a new account number (simulates employee switching banks). Save. Verify the old value is replaced. |
| EMP-BANK-003 | adversarial | test.hr@bebang.ph | Depends on EMP-CREATE-001. Attempt to save with only `bank_name` but empty `bank_ac_no` (partial fill). Document whether the system rejects this or allows a half-filled bank record. Either outcome is acceptable — the scenario captures the actual behavior for the HR manual. |

#### EMP-GOVID (5 scenarios — S160 government IDs after creation)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-GOVID-001 | happy | test.hr@bebang.ph | Depends on EMP-CREATE-001. Fill `tin_number` (12 digits with dashes: `123-456-789-000`). Save. Verify. |
| EMP-GOVID-002 | happy | test.hr@bebang.ph | Depends on EMP-CREATE-001. Fill `sss_number` (10 digits: `12-3456789-0`). Save. Verify. |
| EMP-GOVID-003 | happy | test.hr@bebang.ph | Depends on EMP-CREATE-001. Fill `philhealth_number` and `pagibig_number`. Save. Verify both. |
| EMP-GOVID-004 | happy | test.hr@bebang.ph | Depends on EMP-GOVID-001. Upload a real 150KB PDF as the TIN proof file. Verify `custom_tin_proof_url` is populated AND the file is accessible via GET. |
| EMP-GOVID-005 | edge | test.hr@bebang.ph | Depends on EMP-GOVID-004. Upload a DIFFERENT PDF to replace the TIN proof (HR uploading a corrected copy). Verify the URL changed and the new file is accessible. |

#### EMP-SALARY-SETUP (4 scenarios — initial salary structure assignment)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-SALARY-SETUP-001 | happy | test.hr@bebang.ph | Depends on EMP-CREATE-001. Open compensation section, assert "No salary structure" initial state. Click "Set Up Compensation", pick the production Salary Structure template identified in Phase 0. Enter ONLY the base amount (e.g., 25000). Click Save. Assert a `Salary Structure Assignment` was created in Draft. Evidence must include the SSA name and its raw JSON. |
| EMP-SALARY-SETUP-002 | happy | test.hr@bebang.ph | Depends on EMP-CREATE-002 (separate employee). Set up compensation with base + earnings components (meal allowance, transportation allowance). Save. Verify ALL components are stored on the SSA, not just base. |
| EMP-SALARY-SETUP-003 | happy | test.hr@bebang.ph | Depends on EMP-CREATE-002. Set up compensation with deductions (SSS, PhilHealth, Pag-IBIG contributions at employee share). Save. Verify deduction components are stored with correct amounts. |
| EMP-SALARY-SETUP-004 | edge | test.hr@bebang.ph | Depends on EMP-CREATE-002. If the template includes formula-based components (e.g., "10% of base as allowance"), enter the base amount and verify the formula component computes correctly on save. If no formula components exist in the template, document and SKIP. |

#### EMP-SALARY-CHANGE (6 scenarios — change + approval + audit)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-SALARY-CHANGE-001 | happy | test.hr@bebang.ph | Depends on EMP-SALARY-SETUP-001. Open compensation section, change base amount from 25000 to 30000 (raise). Save. Assert this either (a) creates a new SSA row OR (b) enters the S114 sensitive-change approval queue. Whichever path the implementation takes, the scenario follows it. Capture the exact API endpoint used. |
| EMP-SALARY-CHANGE-002 | happy | test.finance@bebang.ph | Depends on EMP-SALARY-CHANGE-001 (if path (b) approval queue). Navigate to the payroll sensitive-change approval queue, find the pending change for the test employee, click Approve with a note. Verify the change was applied to the SSA and the queue item moved to Approved state. |
| EMP-SALARY-CHANGE-003 | happy | test.hr@bebang.ph + test.finance | Depends on EMP-SALARY-SETUP-002 (employee 2). Change one component's amount (e.g., meal allowance from 2000 to 3000), submit, approve via Finance. Verify ONLY that component changed — the other components are untouched. |
| EMP-SALARY-CHANGE-004 | edge | test.hr@bebang.ph | Depends on EMP-SALARY-SETUP-001. Enter a future effective date for the change (e.g., 30 days from today). Save. Verify the SSA has `from_date` set to the future date. Verify the current rate is still in effect today, and the new rate would only apply from the future date. |
| EMP-SALARY-CHANGE-005 | happy | test.finance@bebang.ph | Depends on EMP-SALARY-CHANGE-001. Instead of approving, Reject with a rejection note. Verify the SSA stays at the old amount (25000) and the queue item moves to Rejected state. Verify the rejection note is visible to HR. |
| EMP-SALARY-CHANGE-006 | adversarial | test.hr@bebang.ph | Depends on EMP-SALARY-SETUP-001. Attempt to enter a negative base amount. Attempt to enter zero. Attempt to enter a non-numeric value. Each attempt must be rejected. This is 3 sub-assertions packaged as one scenario because they all test the same validation layer. |

#### EMP-SALARY-PAYROLL (2 scenarios — downstream payroll integrity)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-SALARY-PAYROLL-001 | integration | test.hr@bebang.ph | Depends on EMP-SALARY-CHANGE-002 (an approved raise). Trigger or wait for the next payroll run that includes the test employee. Read the generated Salary Slip and assert the `gross_pay` reflects the NEW approved amount, not the old one. This is the ONLY test that proves the approval queue actually wires through to payroll. |
| EMP-SALARY-PAYROLL-002 | integration | test.hr@bebang.ph | Depends on EMP-SALARY-CHANGE-004 (a future-dated change). Trigger a payroll run for the current period BEFORE the effective date. Assert the Salary Slip uses the OLD rate. Then trigger (or simulate) a payroll for a period AFTER the effective date. Assert it uses the NEW rate. |

#### EMP-REGULARIZE (3 scenarios — Probationary → Regular transition)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-REGULARIZE-001 | happy | test.hr@bebang.ph | Depends on EMP-CREATE-001 (created with `employment_type=Probitionary`). Navigate to the regularization UI (wherever it lives — likely `/dashboard/hr/performance/regularization` per HRM-001 route hint). Find the test employee. Click "Regularize" or equivalent. Verify `employment_type` transitions to "Regular" AND `date_of_regularization` (or equivalent custom field) is stamped with today's date. |
| EMP-REGULARIZE-002 | edge | test.hr@bebang.ph | Depends on EMP-REGULARIZE-001. After regularization, open the employee detail dialog and verify the employment section shows "Regular" with the regularization date visible. Verify any 13th-month-pay eligibility flag or computed field is updated. |
| EMP-REGULARIZE-003 | adversarial | test.hr@bebang.ph | Attempt to regularize EMP-CREATE-010 (the second test employee, still probationary) with a future regularization date. Document the behavior. If the system rejects future dates, that's a PASS-rejection. If it accepts, verify the date is stored correctly. |

#### EMP-TRANSFER (5 scenarios — branch change chain)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-TRANSFER-001 | happy | test.hr@bebang.ph | Depends on EMP-CREATE-001 (at branch TRANSFER-FROM, which has a mapped device). Navigate to the Transfer module at `/dashboard/hr/transfers`. Click "Create Transfer", pick the test employee, pick the TRANSFER-TO branch (also mapped), enter effective date = today. Submit. Verify a Transfer Request was created in Pending state. |
| EMP-TRANSFER-002 | happy | test.hr@bebang.ph (or whoever approves) | Depends on EMP-TRANSFER-001. Approve the Transfer Request. Verify the employee's `branch` field changes from FROM to TO. |
| EMP-TRANSFER-003 | integration | test.hr@bebang.ph | Depends on EMP-TRANSFER-002. Query `BEI Transfer Device Command` (or the ADMS audit log). Assert that a `DELETE USERINFO` command was queued for the OLD device (at TRANSFER-FROM branch) with the employee's Bio ID. Assert that a new `USERINFO UPDATE` command was queued for the NEW device (at TRANSFER-TO branch) with the same Bio ID. Both must be present for the transfer to be correct. |
| EMP-TRANSFER-004 | integration | test.hr@bebang.ph | Depends on EMP-TRANSFER-003. Wait up to 60 seconds, then verify both device commands were actually dispatched (ACK received OR status updated to "Sent"). If the dispatcher is async and slow, document the observed latency. |
| EMP-TRANSFER-005 | regression | test.hr@bebang.ph | Depends on EMP-TRANSFER-002. Open the Employee Master table filtered by the OLD branch. Assert the transferred employee is NOT in that list. Filter by the NEW branch. Assert they ARE in that list. This proves the masterlist reflects the transfer. |

#### EMP-BIOCHANGE (2 scenarios — Bio ID reassignment without branch change)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-BIOCHANGE-001 | happy | test.hr@bebang.ph | Depends on EMP-CREATE-002. Simulate the "employee's device finger broke, need new Bio ID" scenario. If there's a dedicated reassignment UI, use it. If not, document the current workflow and skip. If supported: verify a `DELETE USERINFO` command fires for the OLD Bio ID and a new `USERINFO UPDATE` fires for the NEW Bio ID on the SAME device. |
| EMP-BIOCHANGE-002 | regression | test.hr@bebang.ph | Depends on EMP-BIOCHANGE-001. Verify the employee's `attendance_device_id` field shows the new Bio ID. Verify historical attendance records (if any) still resolve correctly via the employee_id link. (Attendance records should link by employee_id, not by Bio ID — this scenario catches if they link by the wrong field.) |

#### EMP-COMPLETION (2 scenarios — cross-cutting data-quality metrics)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-COMPLETION-001 | regression | test.hr@bebang.ph | Capture the `summary.missing_bio_id` count BEFORE EMP-CREATE-001. Capture AFTER EMP-CREATE-001. Assert the count did NOT change (new employee has a Bio ID from the start). This proves S164's auto-generation works end-to-end. |
| EMP-COMPLETION-002 | regression | test.hr@bebang.ph | Depends on EMP-CREATE-001 + all EMP-EDIT-* scenarios. Capture the employee's `profile_completion` percentage after creation (should be ~40-60% for a minimally-filled employee). After all EMP-EDIT-* and EMP-GOVID-* and EMP-BANK-* scenarios complete, re-read the masterlist and assert the same employee's `profile_completion` is now ≥137%. This proves the profile completion formula in `hr_reports.py` recomputes on field fills. |

#### EMP-CONFLICT (1 scenario — concurrent edit)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-CONFLICT-001 | adversarial | test.hr@bebang.ph (two sessions) | Depends on EMP-CREATE-001. Open the employee detail dialog in two browser contexts simultaneously. In context A, change `cell_number` to `09170000001` and save. In context B (without refreshing), change `cell_number` to `09170000002` and save. Assert EITHER the second save wins (last-write-wins) OR the second save raises a conflict error (optimistic lock). Document which behavior is the current implementation. Either is acceptable — the scenario captures what HR should expect. |

#### EMP-ADMS (2 scenarios — initial enrollment propagation)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-ADMS-001 | integration | test.hr@bebang.ph | Depends on EMP-CREATE-001 (which must have used a branch with a mapped device per Phase 0 precondition). After creation, query `BEI Transfer Device Command` (or the ADMS receiver audit log) and assert a `USERINFO UPDATE` command was queued for the new employee's Bio ID on the expected device SN. Capture both the UI toast (showing the device SN) and the backend audit record as evidence. |
| EMP-ADMS-002 | integration | test.hr@bebang.ph | Depends on EMP-ADMS-001. Verify the queued command was ACTUALLY dispatched within 60 seconds (ACK received or status transitioned to "Sent"/"Success"). Not just queued — actually sent. If the dispatcher is async and slower, document the observed latency instead of failing. |

#### EMP-CHAT (2 scenarios — Google Chat notification verification)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-CHAT-001 | integration | test.hr@bebang.ph | Depends on EMP-CREATE-001. Read the most recent message in the HR notifications Chat space (`SPACE_NOTIFICATIONS`) via the `/google` skill's Chat API helper. Assert the message contains: `New Employee Created`, the exact Employee ID, the exact Bio ID, the branch name, the source `employee_master_dashboard`. Capture the raw Chat message body as evidence. |
| EMP-CHAT-002 | regression | test.hr@bebang.ph | Depends on EMP-CHAT-001. Verify the Chat message does NOT contain the literal `Onboarding Request:` (because this flow is not from an onboarding request). This is the inverse of the S164 Task 1.4 HARD BLOCKER — the new flow must NOT leak the legacy line. |

#### EMP-RBAC (5 scenarios — consolidated role-based access control)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-RBAC-001 | rbac-ui | test.crew1@bebang.ph | Navigate to `/dashboard/hr/employee-master`. Assert EITHER the page returns "Access Restricted" OR it loads without the "Add New Employee" button visible. Capture screenshot as evidence. |
| EMP-RBAC-002 | rbac-api | test.crew1@bebang.ph | Authenticated as crew, issue a direct POST to `/api/frappe/api/method/hrms.api.employee_create.create_employee_direct` with a valid payload. Assert HTTP 403 / PermissionError. Assert no employee was created. This closes the UI-visibility-only gap. |
| EMP-RBAC-003 | rbac-api | test.crew1@bebang.ph | Authenticated as crew, attempt `POST /api/frappe/api/method/frappe.client.set_value` trying to change `cell_number` on an existing employee. Assert 403. This proves field-level permissions on Employee block crew writes. |
| EMP-RBAC-004 | rbac-ui | test.finance@bebang.ph | As finance user, navigate to Employee Master. Assert the "Add New Employee" button is EITHER visible (if finance has HR permissions) or hidden (if finance is approve-only). Document which. Then navigate to the salary approval queue and verify finance CAN see pending items. This proves the approve-only role has the correct scope. |
| EMP-RBAC-005 | rbac-ui | test.crew1@bebang.ph | Open the EmployeeDetailDialog as crew (via whatever path is reachable). Assert the Save buttons on personal/employment/compensation sections are EITHER disabled OR hidden. Assert the compensation amount field is EITHER masked, hidden, or read-only (crew must not see other employees' salaries). |

#### EMP-TERMINATE (6 scenarios — full separation + clearance flow)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-TERMINATE-001 | happy | test.hr@bebang.ph | Depends on EMP-CREATE-001 (employee has been through all EDIT + SALARY scenarios by now). Navigate to the employee detail, click the separation / termination trigger (per Phase 0 research — could be a button on the detail dialog or a route at `/dashboard/hr/separations`). Fill the separation reason, last working date, and any other required fields. Submit. Assert a `BEI Clearance` request (or equivalent DocType) was created in Pending state. |
| EMP-TERMINATE-002 | happy | test.hr@bebang.ph | Depends on EMP-TERMINATE-001. Open the clearance request. Verify clearance stations (IT, POS, Uniform, Keys, etc. per Phase 0 research) were auto-assigned OR HR can manually assign them. Assign all stations. Save. Verify the station list persisted. |
| EMP-TERMINATE-003 | happy | test.hr@bebang.ph | Depends on EMP-TERMINATE-002. For each clearance station, upload a clearance item or sign-off (e.g., "Returned POS access key", "Uniform returned"). Real 150KB files where applicable. Verify all items are stored on the clearance record. |
| EMP-TERMINATE-004 | integration | test.hr@bebang.ph | Depends on EMP-TERMINATE-003. Trigger the Documenso e-signature flow for the clearance form. Verify the Documenso document was created (HEAD or GET on the Documenso API) and that sign.bebang.ph returned a valid signing URL. If Documenso is unreachable, the scenario documents the blocker but does not auto-fail the entire sprint. |
| EMP-TERMINATE-005 | happy | test.hr@bebang.ph (or whoever approves clearance) | Depends on EMP-TERMINATE-004. Approve the clearance (all stations signed off + Documenso complete). Verify the employee's `status` transitions from `Active` to `Left` with the correct `relieving_date`. |
| EMP-TERMINATE-006 | regression | test.hr@bebang.ph | Depends on EMP-TERMINATE-005. Re-open the Employee Master table filtered by status=Active. Assert the terminated employee is NOT in the list. Filter by status=Left. Assert they ARE in the list. |

#### EMP-FINALPAY (3 scenarios — last payslip and BIR 2316)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-FINALPAY-001 | integration | test.hr@bebang.ph | Depends on EMP-TERMINATE-005. Trigger the final pay calculation for the terminated employee (or wait for the next payroll run that includes them). Verify a final Salary Slip was generated with: pro-rated basic pay based on `relieving_date`, unused leave conversion (if applicable), final deductions. Capture the raw Salary Slip JSON. |
| EMP-FINALPAY-002 | integration | test.hr@bebang.ph | Depends on EMP-FINALPAY-001. Trigger BIR 2316 generation (if the feature exists per Phase 0 research). Verify the form is created and accessible. If the feature doesn't exist yet, document and SKIP. |
| EMP-FINALPAY-003 | happy | test.hr@bebang.ph | Depends on EMP-FINALPAY-001. Mark the final pay as "Released" / "Paid" via whatever UI action exists. Verify the payroll record shows released. Verify the clearance record shows the final-pay step as complete. |

#### EMP-USERDISABLE (2 scenarios — account disable verification)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-USERDISABLE-001 | integration | test.hr@bebang.ph | Depends on EMP-TERMINATE-005. Query the User DocType for the terminated employee's user account (`user_id`). Assert the `enabled` field is `0` (disabled). If the termination flow does NOT auto-disable the user, that's a PRODUCT DEFECT — log it to DEFECTS.csv with severity HIGH and continue. |
| EMP-USERDISABLE-002 | adversarial | (ex-employee) | Depends on EMP-USERDISABLE-001. Attempt to log in to `my.bebang.ph` using the terminated employee's credentials. Assert login fails with an appropriate error. If login succeeds, that's a CRITICAL security defect — log it to DEFECTS.csv with severity CRITICAL and stop the sprint for the user to decide. |

#### EMP-ADMSREMOVE (2 scenarios — Bio ID removal from device)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-ADMSREMOVE-001 | integration | test.hr@bebang.ph | Depends on EMP-TERMINATE-005. Query `BEI Transfer Device Command` (or the ADMS audit log). Assert a `DELETE USERINFO` command was queued for the terminated employee's Bio ID on their last-known device SN. If no such command was queued, that's a PRODUCT DEFECT — the device still has an active Bio ID for an ex-employee. Log to DEFECTS.csv severity HIGH. |
| EMP-ADMSREMOVE-002 | integration | test.hr@bebang.ph | Depends on EMP-ADMSREMOVE-001. Verify the DELETE USERINFO command was actually dispatched within 60 seconds. If the dispatcher is async and slow, document latency. If the command stays Pending indefinitely, that's a defect. |

#### EMP-REHIRE (2 scenarios — re-activation path)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-REHIRE-001 | happy | test.hr@bebang.ph | Depends on EMP-USERDISABLE-002 (the ex-employee is fully terminated). Simulate HR re-hiring them. Two valid paths: (a) re-activate the existing Employee record with a new joining date, or (b) create a new Employee record via EMP-CREATE flow. Document which path the implementation supports. If (a): verify status back to Active, new date_of_joining, audit log shows re-activation. If (b): verify a NEW Employee record was created (not a dupe collision). |
| EMP-REHIRE-002 | regression | test.hr@bebang.ph | Depends on EMP-REHIRE-001. If path (a): verify the original Bio ID is reassigned and pushed back to the device (USERINFO UPDATE queued). If path (b): verify a fresh new Bio ID was generated. Either is acceptable — the scenario captures which path the product takes. |

#### EMP-LEAVE (5 scenarios — leave application + approval)

Self-service leave scenarios use `test.crew1@bebang.ph` (has User account + leave balance). Supervisor approval uses `test.supervisor@bebang.ph`.

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-LEAVE-001 | happy | test.crew1@bebang.ph | Navigate to `/dashboard/hr/leave`. Click "Apply Leave" (or `+` / `New Leave` button). In the `LeaveRequestDialog`, select a leave type from Phase 0 precondition list (e.g., "Casual Leave"), pick from_date = tomorrow, to_date = tomorrow (1-day leave), enter reason. Submit. Assert toast success. Assert the leave appears in the "My Leaves" list with status "Open" / "Pending". Capture the leave request name. |
| EMP-LEAVE-002 | happy | test.supervisor@bebang.ph | Depends on EMP-LEAVE-001. As supervisor, navigate to the leave approval view (could be `/dashboard/hr/leave` filtered by "Pending for Approval" or a separate queue — Phase 0 research determines). Find the leave request from EMP-LEAVE-001. Click Approve. Assert status transitions to "Approved". |
| EMP-LEAVE-003 | regression | test.crew1@bebang.ph | Depends on EMP-LEAVE-002. Re-open the leave page as the employee. Verify the approved leave shows status "Approved". Verify the leave balance decreased by 1 day for the leave type used. Capture before/after balance as evidence. |
| EMP-LEAVE-004 | happy | test.crew1@bebang.ph + test.supervisor@bebang.ph | Apply a SECOND leave (different dates). Supervisor rejects it with a rejection note. Verify status = "Rejected". Verify leave balance did NOT decrease. Verify the rejection note is visible to the employee. |
| EMP-LEAVE-005 | edge | test.crew1@bebang.ph | Apply a leave, then attempt to cancel it BEFORE supervisor action. Verify the cancellation succeeds and the leave disappears from the pending list. If cancellation is not supported pre-approval, document the actual behavior. |

#### EMP-OVERTIME (4 scenarios — OT filing + approval)

OT filing uses `test.crew1@bebang.ph` or `test.supervisor@bebang.ph` (whoever files OT at BEI). HR approval uses `test.hr@bebang.ph`.

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-OVERTIME-001 | happy | test.crew1@bebang.ph (or test.supervisor) | Navigate to `/dashboard/hr/overtime`. File an overtime request: select date, enter overtime hours (e.g., 2 hours), select OT type from Phase 0 list (e.g., "Regular OT"). Submit. Assert the OT request appears in the list with status "Pending" or "Open". |
| EMP-OVERTIME-002 | happy | test.hr@bebang.ph | Depends on EMP-OVERTIME-001. As HR, navigate to the overtime page (which shows all pending OT requests). Find the request. Click Approve. Fill in `approved_payable_duration` (may differ from requested hours) and `approved_overtime_type`. Save. Assert status transitions to "Approved". Assert `approved_payable_duration` matches what was entered. |
| EMP-OVERTIME-003 | happy | test.hr@bebang.ph | File a second OT request (different date). Reject it with a note. Assert status = "Rejected". Assert the rejection note is visible. |
| EMP-OVERTIME-004 | regression | test.crew1@bebang.ph | Depends on EMP-OVERTIME-002. After the approved OT, check if it appears in the payroll processing page when reviewing the next payroll period. If the payroll period is different from the OT date, document the expected payroll cycle. The OT hours should appear as an earning line. |

#### EMP-ATTENDANCE (3 scenarios — correction request + approval)

Attendance correction uses `test.crew1@bebang.ph` to submit. Supervisor approves.

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-ATTENDANCE-001 | happy | test.crew1@bebang.ph | Navigate to `/dashboard/hr/attendance-correction`. Fill the correction form: select a past date, select correction type (Late In / Early Out / Absent → Present / etc. — from Phase 0 research), enter reason, optionally attach evidence (150KB file). Submit. Assert the correction request appears in the list with status "Pending". |
| EMP-ATTENDANCE-002 | happy | test.supervisor@bebang.ph | Depends on EMP-ATTENDANCE-001. As supervisor, find the pending correction in the approval queue (wherever it lives — Phase 0 research). Approve it. Assert status transitions to "Approved". |
| EMP-ATTENDANCE-003 | regression | test.crew1@bebang.ph | Depends on EMP-ATTENDANCE-002. After approval, verify the actual attendance record for that date reflects the correction. If attendance records are visible on the employee's attendance page, navigate there and confirm. Capture before/after state. |

#### EMP-PAYROLL-RUN (6 scenarios — full HR-driven payroll processing cycle)

All payroll-run scenarios use `test.hr@bebang.ph`. These operate on the current payroll period that includes the test employee from EMP-CREATE-001.

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-PAYROLL-RUN-001 | happy | test.hr@bebang.ph | Navigate to `/dashboard/hr/payroll/processing`. Identify the current payroll period (from Phase 0 precondition). Click "Process Payroll" or "Create Salary Slips" for that period. Verify the payroll run initiates — salary slips are being generated. Wait for completion (may take seconds to minutes). Assert the test employee (EMP-CREATE-001) has a Salary Slip in the output. |
| EMP-PAYROLL-RUN-002 | happy | test.hr@bebang.ph | Depends on EMP-PAYROLL-RUN-001. Navigate to `/dashboard/hr/payroll/review-output`. Find the test employee's Salary Slip. Open it. Verify: `gross_pay` matches the Salary Structure Assignment amount from EMP-SALARY-CHANGE-002 (the approved raise amount, not the original), deduction components are present (SSS, PhilHealth, Pag-IBIG, BIR withholding), `net_pay` = gross - deductions. Capture the full Salary Slip JSON. |
| EMP-PAYROLL-RUN-003 | edge | test.hr@bebang.ph | Depends on EMP-PAYROLL-RUN-002. If the approved OT from EMP-OVERTIME-002 falls within this payroll period, verify the Salary Slip includes an OT earning line. If the OT was for a different period, document this and SKIP. |
| EMP-PAYROLL-RUN-004 | happy | test.hr@bebang.ph | Depends on EMP-PAYROLL-RUN-002. Navigate to `/dashboard/hr/payroll/comparison`. Verify the period-over-period comparison page loads and shows data for the current period. Screenshot the comparison view. |
| EMP-PAYROLL-RUN-005 | happy | test.hr@bebang.ph | Depends on EMP-PAYROLL-RUN-002. Navigate to `/dashboard/hr/payroll/remittances`. Verify remittance summaries (SSS, PhilHealth, Pag-IBIG, BIR) are generated for the current period. The test employee's contribution should appear in the totals. |
| EMP-PAYROLL-RUN-006 | happy | test.hr@bebang.ph | Depends on EMP-PAYROLL-RUN-002. Navigate to `/dashboard/hr/payroll/history`. Verify the current period's payroll run appears in the history list with correct status and summary counts. |

#### EMP-PAYSLIP (2 scenarios — employee self-service payslip view)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-PAYSLIP-001 | happy | test.crew1@bebang.ph | Navigate to `/dashboard/hr/payslip`. Verify the page loads showing the logged-in employee's own payslips (not other employees'). Find the most recent payslip. Assert it shows: `gross_pay`, `net_pay`, earning lines, deduction lines, and the payroll period. Capture a screenshot. |
| EMP-PAYSLIP-002 | rbac | test.crew1@bebang.ph | On the payslip page, attempt to view or access another employee's payslip (e.g., by manipulating the URL with a different employee_id). Assert the system blocks access — the employee should only see their own payslips. |

#### EMP-DISCIPLINARY (5 scenarios — HR issues memo → employee responds → HR resolves)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-DISCIPLINARY-001 | happy | test.hr@bebang.ph | Navigate to `/dashboard/hr/disciplinary`. Click "Create" or "New Case". Fill: select the test employee (EMP-CREATE-001 or any existing), select violation category (from Phase 0 research), select action type (e.g., "Written Warning" or "Notice to Explain"), enter description of the offense, enter date of incident. Submit. Assert a disciplinary case was created with a case ID. |
| EMP-DISCIPLINARY-002 | happy | test.hr@bebang.ph | Depends on EMP-DISCIPLINARY-001. Open the created case at `/dashboard/hr/disciplinary/[id]`. Verify all fields are displayed correctly. If there's an "Issue Memo" or "Send NTE" button, click it. Verify the memo/NTE status updates. |
| EMP-DISCIPLINARY-003 | happy | test.hr@bebang.ph | Depends on EMP-DISCIPLINARY-002. Simulate the employee response step: if the case detail page has a "Record Employee Response" form, fill it with a response text and save. If this step requires the employee themselves to respond (self-service), document that and use `test.crew1@bebang.ph` or SKIP if the test employee has no user account. |
| EMP-DISCIPLINARY-004 | happy | test.hr@bebang.ph | Depends on EMP-DISCIPLINARY-003. HR resolves the case: select a resolution (e.g., "Warning Issued", "Case Closed", "Suspension", or "Recommend Termination"). If suspension: verify the employee's status changes to "Suspended" or a suspension flag is set. Save. Verify the case status transitions to "Resolved" or "Closed". |
| EMP-DISCIPLINARY-005 | regression | test.hr@bebang.ph | Depends on EMP-DISCIPLINARY-004. Return to the main disciplinary list. Verify the resolved case appears with the correct final status. Verify the employee detail dialog (if opened) shows the disciplinary record in the employee's history or a related section. |

#### EMP-EXITINTERVIEW (3 scenarios — exit interview + analytics)

Exit interview scenarios fire after EMP-TERMINATE-005 (employee has status=Left). The interview may be filled by the employee (self-service) or by HR on behalf.

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-EXITINTERVIEW-001 | happy | test.hr@bebang.ph (or the employee if self-service) | Depends on EMP-TERMINATE-005. Navigate to the exit interview form for the terminated employee. The entry point could be `/clearance/exit-interview`, `/dashboard/hr/exit-interview/[id]`, or a link from the clearance record — Phase 0 research determines. Fill all survey questions (rating scales, text responses, reason for leaving). Submit. Assert the interview was saved. |
| EMP-EXITINTERVIEW-002 | happy | test.hr@bebang.ph | Depends on EMP-EXITINTERVIEW-001. Navigate to `/dashboard/hr/exit-interview/analytics`. Verify the analytics page loads and includes data from the just-submitted exit interview. The charts/tables should reflect one more response than before. |
| EMP-EXITINTERVIEW-003 | regression | test.hr@bebang.ph | Depends on EMP-EXITINTERVIEW-001. Re-open the specific exit interview record. Verify all responses are persisted correctly — no data loss between submit and re-read. |

#### EMP-COMPLIANCE (2 scenarios — 13th month computation)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-COMPLIANCE-001 | integration | test.hr@bebang.ph | Depends on EMP-REGULARIZE-001 (employee is now "Regular"). Navigate to `/dashboard/hr/compliance/13th-month`. Trigger the 13th month computation for the current year (if there's a "Compute" button) or view the existing computation. Verify the regularized test employee appears in the 13th month list with a computed amount > 0. If the feature only runs at year-end and can't be triggered mid-year, document and SKIP — but capture evidence of the page loading with the employee's eligibility status. |
| EMP-COMPLIANCE-002 | regression | test.hr@bebang.ph | Depends on EMP-COMPLIANCE-001. If the test employee was probationary before regularization (which they were per EMP-CREATE-001), verify the 13th month computation correctly pro-rates the amount from the regularization date (not from the full year). If the computation doesn't pro-rate, that's a documentation item — capture the actual behavior. |

#### EMP-ENRICHMENT (2 scenarios — enrichment tracker)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-ENRICHMENT-001 | happy | test.hr@bebang.ph | Navigate to `/dashboard/hr/enrichment-tracker`. Verify the page loads showing employee enrichment statuses. Find the test employee (EMP-CREATE-001) in the list — they should show a lower enrichment status since many optional fields were not filled during onboarding. Capture the current enrichment status + percentage. |
| EMP-ENRICHMENT-002 | regression | test.hr@bebang.ph | Depends on all EMP-EDIT-* scenarios being complete. Re-open the enrichment tracker. Verify the test employee's enrichment status/percentage increased compared to EMP-ENRICHMENT-001's snapshot. This proves the tracker updates dynamically as fields are filled. |

#### EMP-UX (10 scenarios — document UX gaps found by audit agents)

These scenarios do NOT test features that exist. They **document gaps as test evidence** so the DEFECTS.csv produces a prioritized backlog for the next sprint cycle. Each scenario visits a specific page, captures what's there, and asserts the absence of a feature the 4 audit agents flagged.

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-UX-001 | ux-gap | test.hr@bebang.ph | Navigate to `/dashboard/hr/attendance`. Assert the page shows "My Attendance" (self-service) NOT an org-wide attendance dashboard. Capture the page title and the absence of store/branch filters. Log as CRITICAL defect in DEFECTS.csv: "Attendance page is self-service only for HR role — cannot view org-wide attendance for 47 stores." |
| EMP-UX-002 | ux-gap | test.hr@bebang.ph | Navigate to `/dashboard/hr/schedule`. Assert the page shows "My Schedule" (self-service) NOT a shift assignment grid. Capture the absence of "Assign Shift" or "Bulk Assign" buttons. Log as CRITICAL defect: "Schedule page is self-service only — cannot manage shifts for 700 employees." |
| EMP-UX-003 | ux-gap | test.hr@bebang.ph | Navigate to `/dashboard/hr/attendance-correction`. Assert the page shows the employee submission form, not an admin review queue. Capture the absence of "Pending Corrections" or "Review Queue" sections. Log as CRITICAL defect: "Attendance correction has no admin review queue — HR cannot approve/reject submitted corrections." |
| EMP-UX-004 | ux-gap | test.hr@bebang.ph | Navigate to `/dashboard/hr/payroll/compensation-setup`. Click any employee row in the table. Assert the opened modal is EMPTY or shows only Bio ID (no salary components, no edit fields). Capture screenshot. Log as CRITICAL defect: "Compensation detail modal is broken — HR cannot view or edit individual salary from the portal." |
| EMP-UX-005 | ux-gap | test.finance@bebang.ph | Navigate to `/dashboard/hr/payroll/sensitive-changes`. Find a pending change row. Assert the row does NOT have visible Approve or Reject buttons. Capture screenshot. Log as CRITICAL defect: "Finance cannot approve/reject sensitive salary changes from the UI — dual-control workflow is broken." |
| EMP-UX-006 | ux-gap | test.crew1@bebang.ph | Log in as crew. Count sidebar navigation items. Assert the count is ≥15 (indicating sidebar bloat). Visit 5 sidebar items. Assert ≥3 return "Access Restricted". Capture screenshot. Log as HIGH defect: "Sidebar shows 19 nav groups to crew role, most lead to Access Restricted pages." |
| EMP-UX-007 | ux-gap | test.crew1@bebang.ph | Navigate to `/dashboard/hr/payslip`. Find the most recent payslip. Assert there is NO "Download PDF", "Print", or "Export" button visible. Capture screenshot. Log as MEDIUM defect: "Crew cannot download or print their own payslip." |
| EMP-UX-008 | ux-gap | test.crew1@bebang.ph | After filing any request (leave, OT, attendance correction), look for a notification bell or inbox indicator anywhere in the UI. Assert absence. Wait 30 seconds, refresh. Still no notification. Log as MEDIUM defect: "No notification system exists. Employees cannot know if their requests were approved without manually polling the page." |
| EMP-UX-009 | ux-gap | test.hr@bebang.ph | Navigate to `/dashboard/hr/overtime`. Click Approve on any pending OT request. Check the approve dialog/form for an "Approved Hours" input. Assert it does NOT exist (approval is all-or-nothing). Log as HIGH defect: "Overtime approval cannot specify approved hours — must fully approve or reject." |
| EMP-UX-010 | ux-gap | test.hr@bebang.ph | Navigate to `/dashboard/hr/payroll/processing`. Look for a branch-level filter or "Process by Branch" option. Assert absence — the wizard processes the entire company (700 employees) at once. Log as HIGH defect: "No branch-level payroll processing — HR must run all 700 employees at once." |

#### EMP-STUB (5 scenarios — visit and document stub pages)

These scenarios visit pages that the audit agents identified as stubs (UI exists but functionality is missing or placeholder-only). Each scenario captures the current state so the next sprint cycle has concrete evidence.

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-STUB-001 | stub-document | test.hr@bebang.ph | Navigate to `/dashboard/hr/reports`. Verify the page loads with 8 report tiles (Employee Masterlist, Headcount, Attrition, New Hires, Separations, Recruitment Funnel, Attendance Summary, Overtime Report). Click each tile. Assert NONE navigate to a working report. Capture the click outcomes. Log as CRITICAL defect: "HR Reports page is a stub — all 8 report tiles are non-functional." |
| EMP-STUB-002 | stub-document | test.hr@bebang.ph | Navigate to `/dashboard/hr/training`. Assert the page loads. Assert there is NO "Create Training Program" button. Verify the page contains text referring users to Frappe Desk for training creation. Log as HIGH defect: "Training module is read-only — page explicitly says to create programs in Frappe." |
| EMP-STUB-003 | stub-document | test.hr@bebang.ph | Navigate to `/dashboard/hr/performance`. Assert there is NO "Create Review Cycle" or "Assign Reviewers" button. Only the Regularization sub-module is functional. Log as MEDIUM defect: "Performance Review module is read-only — cannot create evaluation cycles." |
| EMP-STUB-004 | stub-document | test.hr@bebang.ph | Navigate to `/dashboard/hr/disciplinary`. Click the first case in the list to open its detail page. Assert the detail page renders BLANK (empty skeleton cards, no content). Capture screenshot. Log as HIGH defect: "Disciplinary case detail page renders blank — cases cannot be managed after creation." |
| EMP-STUB-005 | stub-document | test.hr@bebang.ph | Navigate to `/clearance`. Assert the page shows a read-only milestone tracker (Exit Interview / Final Pay / COE) and does NOT show clearance stations, item return tracking, or Documenso e-signature integration. Capture screenshot. Log as CRITICAL defect: "Clearance module is a read-only milestone tracker — no real clearance functionality exists." |

#### EMP-CLEAN (3 scenarios — final cleanup sweep)

| ID | Type | Role | Scenario |
|---|---|---|---|
| EMP-CLEAN-001 | cleanup | test.hr@bebang.ph | Read the run-local test employee registry (track IDs throughout execution). For each employee not already terminated via the EMP-TERMINATE chain, open their detail dialog and change status to `Left` with today's date. Do NOT hard-delete. |
| EMP-CLEAN-002 | cleanup | test.hr@bebang.ph | Run a final audit query: `SELECT COUNT(*) AS n FROM tabEmployee WHERE name LIKE 'BEI-EMP-2026-%' AND status = 'Active' AND employee_name LIKE '%L3 2026-04-06%'`. Must return 0. If non-zero, the cleanup is incomplete — FAIL the sprint and list the stragglers in SUMMARY.md. |
| EMP-CLEAN-003 | cleanup | test.hr@bebang.ph | Run a Bio ID pollution check: `SELECT MAX(CAST(attendance_device_id AS UNSIGNED)) FROM tabEmployee WHERE attendance_device_id REGEXP '^9[0-9]{6}$'`. The max MUST be ≤ the value captured in Phase 0 precondition + the number of EMP-CREATE scenarios (should be ~9001882 + 10 = ~9001892). If the max is significantly higher, there is leftover test data — run the `scripts/s164_fix_bio_id_outliers.py` pattern to clean it before marking the sprint complete. This is the explicit anti-regression check against the 2026-02-26-style pollution that S164 post-deploy had to fix. |

### Phase 2 — Register the module in index.yaml (1 unit)

Add a new module entry to `docs/testing/scenarios/index.yaml`:

```yaml
  - key: hr-employee-lifecycle
    status: ready
    command: hr-employee-lifecycle
    scenario_count: 137
    route_count_hint: 26
    prefixes:
      - EMP-CREATE
      - EMP-EDIT-PERSONAL
      - EMP-EDIT-CONTACT
      - EMP-EDIT-ADDRESS
      - EMP-EDIT-EMPLOYMENT
      - EMP-PHOTO
      - EMP-BANK
      - EMP-GOVID
      - EMP-SALARY-SETUP
      - EMP-SALARY-CHANGE
      - EMP-SALARY-PAYROLL
      - EMP-REGULARIZE
      - EMP-LEAVE
      - EMP-OVERTIME
      - EMP-ATTENDANCE
      - EMP-PAYROLL-RUN
      - EMP-PAYSLIP
      - EMP-DISCIPLINARY
      - EMP-TRANSFER
      - EMP-BIOCHANGE
      - EMP-COMPLETION
      - EMP-CONFLICT
      - EMP-ADMS
      - EMP-CHAT
      - EMP-RBAC
      - EMP-TERMINATE
      - EMP-EXITINTERVIEW
      - EMP-FINALPAY
      - EMP-COMPLIANCE
      - EMP-USERDISABLE
      - EMP-ADMSREMOVE
      - EMP-REHIRE
      - EMP-ENRICHMENT
      - EMP-UX
      - EMP-STUB
      - EMP-CLEAN
    scenario_files:
      - docs/testing/scenarios/modules/hr-employee-lifecycle.md
```

And add `hr-employee-lifecycle` to the top-level `commands:` list so `/l3-v2-bei-erp hr-employee-lifecycle` resolves.

### Phase 3 — Execute via `/l3-v2-bei-erp hr-employee-lifecycle` in a fresh session (26 units)

**This phase runs in a SEPARATE fresh Claude Code session** per the S099 L3 handoff rule. The builder of the scenario catalog (Phases 0–2) is NOT the executor.

The fresh-session executor:

1. Reads `docs/plans/2026-04-06-sprint-166-l3-employee-lifecycle-scenarios.md` (this file) and the companion `docs/testing/scenarios/modules/hr-employee-lifecycle.md`.
2. Runs the standard L3 preflight: `python scripts/testing/l3_browser_guard.py scan`, `python scripts/testing/l3_manifest_check.py`.
3. Generates the 150KB test photo fixture from the SKILL.md snippet.
4. Logs in as each required role via real browser UI (no API token shortcut).
5. Executes all 137 scenarios in dependency order. `EMP-CREATE-001` runs first; `EMP-CREATE-002` (second test employee used for multi-employee scenarios) runs next; `EMP-CREATE-010` (third test employee used for transfer destination) runs next; everything else chains off one of these three base employees per the `Depends on:` markers.
6. Captures per-scenario evidence to:
   - `output/l3/s166/form_submissions.json` — minimum 137 entries
   - `output/l3/s166/api_mutations.json` — one per scenario that mutates state
   - `output/l3/s166/state_verification.json` — before/after snapshots
   - `output/l3/s166/evidence/{SCENARIO_ID}.json` — Playwright action log + network capture per scenario
   - `output/l3/s166/artifacts/{SCENARIO_ID}.trace.zip` — Playwright trace for each scenario
   - `output/l3/s166/screenshots/` — pre-submit + post-submit screenshots
7. After execution, runs `l3_browser_guard validate` on every evidence file.
8. Writes a summary to `output/l3/s166/SUMMARY.md` with pass/fail counts grouped by prefix.

### Phase 4 — Defect triage + disposition (3 units)

For every FAIL in the Phase 3 summary:

1. Classify the failure: `selector-flake | precondition-missing | product-defect | environment`.
2. For `selector-flake` and `precondition-missing`: re-run the scenario with the fix applied (per SKILL.md Step 5.5 flake resolution loop).
3. For `product-defect`: do NOT fix in this sprint. Log to `output/l3/s166/DEFECTS.csv` with columns `scenario_id, classification, observed, expected, severity, recommended_sprint`. Open a follow-up sprint reservation in `SPRINT_REGISTRY.md` with the defect list.
4. For `environment`: document the environment blocker and continue.

### Phase 5 — Cleanup + Closeout (2 units)

1. Execute EMP-CLEAN-001 and EMP-CLEAN-002 explicitly (even if they were executed inline in Phase 3, run them again as a final sweep).
2. Verify the Phase 2 audit query returns zero leftover test employees.
3. Commit the scenario catalog + index.yaml change + evidence files via `git add -f output/l3/s166/`.
4. Update `SPRINT_REGISTRY.md`: S166 status → `COMPLETED` with summary counts.
5. Update this plan's YAML `status: COMPLETED`, `execution_summary:` with pass/fail counts.
6. Push to the sprint branch, create the PR.

---

## Evidence Contract (per S092 anti-corrupt-success rule)

Before anyone claims `COMPLETED` on this sprint, ALL of the following must exist in the committed output:

| File | Minimum shape |
|---|---|
| `output/l3/s166/form_submissions.json` | array of ≥137 objects, each with `scenario_id`, `form` (dialog name), `inputs` (field→value map), `submit_action` (button text), `response` (JSON body), `screenshot_after` (path) |
| `output/l3/s166/api_mutations.json` | array of objects with `scenario_id`, `endpoint`, `method`, `payload`, `status`, `response_body` |
| `output/l3/s166/state_verification.json` | array of `{scenario_id, check, before, after, passed}` |
| `output/l3/s166/SUMMARY.md` | Markdown summary: total pass/fail, breakdown by prefix, defect list, cleanup confirmation |
| `output/l3/s166/DEFECTS.csv` | columns above, present even if empty |
| `output/l3/s166/evidence/*.json` | one file per scenario ID |
| `output/l3/s166/artifacts/*.trace.zip` | one Playwright trace per scenario |

**Hard gate:** if `form_submissions.json` has fewer than 137 entries, the sprint is `CORRUPT_SUCCESS` — not `COMPLETED`. No exceptions. No "I tested them all, just didn't write them down." The evidence IS the verification.

**Secondary hard gate:** `form_submissions.json` must contain at least one entry per prefix. A run that skips an entire prefix (e.g., all of EMP-TERMINATE because "clearance module was hard") is CORRUPT_SUCCESS even if the total count is ≥137 through scenario duplication elsewhere.

---

## RBAC Test Matrix

Every RBAC scenario must cover both layers:

| Layer | Gate | Test approach |
|---|---|---|
| UI visibility | React `hasRole(roles, [...])` from `@/lib/roles` | Playwright asserts element visible/hidden for each role |
| UI interactivity | Same hook, used on buttons | Playwright asserts button disabled/enabled |
| Backend endpoint | `frappe.has_permission("Employee", "create", throw=True)` or equivalent | Direct API call as crew user expecting 403 |
| Backend field mutation | Frappe field-level permissions | Direct `set_value` as crew expecting 403 |

Roles tested: `test.hr@bebang.ph` (positive), `test.crew1@bebang.ph` (negative for all), `test.finance@bebang.ph` (positive for salary approval only, negative for employee creation).

---

## Verification Checklist (sprint-level definition of done)

### Catalog + registration
- [ ] `docs/testing/scenarios/modules/hr-employee-lifecycle.md` exists with all 137 scenarios in the exact format of `modules/maintenance.md`
- [ ] `docs/testing/scenarios/index.yaml` has the new `hr-employee-lifecycle` module key and command entry with `scenario_count: 137` and all 36 prefixes listed
- [ ] `/l3-v2-bei-erp hr-employee-lifecycle` is a valid command that resolves to the new module

### Evidence files exist
- [ ] Phase 3 execution produced all 7 evidence files listed in the Evidence Contract
- [ ] `form_submissions.json` has ≥137 entries
- [ ] `form_submissions.json` has at least one entry per prefix (secondary hard gate)
- [ ] `api_mutations.json` has entries for every mutating scenario
- [ ] `state_verification.json` has before/after for every state-changing scenario

### HIRE stage proof
- [ ] All `EMP-CREATE-*` scenarios ran against real production branches, not test fixtures
- [ ] At least one `EMP-CREATE-*` captured a real ADMS device SN from a real mapped branch
- [ ] `EMP-CREATE-004` proved the `NO_DEVICE_FOR_BRANCH` path (not just passed the assertion)
- [ ] `EMP-CREATE-010` proved Bio ID sequence integrity (second create = first + 1)

### EDIT stage proof (all 6 field groups)
- [ ] `EMP-EDIT-PERSONAL-*` covered name, DOB, gender edits
- [ ] `EMP-EDIT-CONTACT-*` covered cell, email, emergency contact
- [ ] `EMP-EDIT-ADDRESS-*` covered current + permanent address
- [ ] `EMP-EDIT-EMPLOYMENT-*` covered designation, department, reports_to, employment_type
- [ ] `EMP-PHOTO-*` proved photo upload + replace with real 150KB JPG
- [ ] `EMP-BANK-*` proved bank name + account number edit
- [ ] `EMP-GOVID-*` proved TIN/SSS/PhilHealth/Pag-IBIG number + file edits post-creation

### COMPENSATE stage proof
- [ ] `EMP-SALARY-SETUP-002` proved multiple earnings components are stored (not just base)
- [ ] `EMP-SALARY-SETUP-003` proved deduction components are stored
- [ ] `EMP-SALARY-CHANGE-002` proved the approval queue actually persisted the approved change
- [ ] `EMP-SALARY-CHANGE-004` proved effective-dated changes work (future date honored)
- [ ] `EMP-SALARY-CHANGE-005` proved the rejection path rolled back correctly
- [ ] `EMP-SALARY-PAYROLL-001` proved the approved change flowed to the next payroll run's Salary Slip (downstream integrity)

### REGULARIZE stage proof
- [ ] `EMP-REGULARIZE-001` proved Probationary → Regular transition with regularization date stamped

### LEAVE stage proof
- [ ] `EMP-LEAVE-001` proved leave application via `LeaveRequestDialog` (form submitted, request created)
- [ ] `EMP-LEAVE-002` proved supervisor approval flow (status → Approved)
- [ ] `EMP-LEAVE-003` proved leave balance decreased after approval
- [ ] `EMP-LEAVE-004` proved rejection path (balance NOT decreased, note visible)

### OVERTIME stage proof
- [ ] `EMP-OVERTIME-001` proved OT filing with hours + type
- [ ] `EMP-OVERTIME-002` proved HR approval with `approved_payable_duration`
- [ ] `EMP-OVERTIME-004` proved OT appears as earning line on payslip (or documented why not)

### ATTENDANCE CORRECTION stage proof
- [ ] `EMP-ATTENDANCE-001` proved correction submission
- [ ] `EMP-ATTENDANCE-002` proved supervisor approval
- [ ] `EMP-ATTENDANCE-003` proved the actual attendance record changed after approval

### PAYROLL RUN stage proof
- [ ] `EMP-PAYROLL-RUN-001` proved salary slips were generated for the current period
- [ ] `EMP-PAYROLL-RUN-002` proved the test employee's slip uses the APPROVED raise amount (not the old one)
- [ ] `EMP-PAYROLL-RUN-005` proved remittance summaries (SSS/PhilHealth/Pag-IBIG/BIR) were generated

### PAYSLIP stage proof
- [ ] `EMP-PAYSLIP-001` proved employee can view their own payslip with gross/net/deductions
- [ ] `EMP-PAYSLIP-002` proved employee cannot view other employees' payslips

### DISCIPLINARY stage proof
- [ ] `EMP-DISCIPLINARY-001` proved case creation (memo/NTE issued)
- [ ] `EMP-DISCIPLINARY-004` proved case resolution (warning/suspension/closure)
- [ ] `EMP-DISCIPLINARY-005` proved resolved case appears in history with correct status

### TRANSFER stage proof
- [ ] `EMP-TRANSFER-003` proved BOTH the OLD device DELETE USERINFO AND the NEW device USERINFO UPDATE were queued (not just one)
- [ ] `EMP-TRANSFER-004` proved both commands were actually dispatched, not just queued
- [ ] `EMP-TRANSFER-005` proved the masterlist reflects the branch change correctly

### NOTIFICATION proof
- [ ] `EMP-ADMS-002` proved initial ADMS enrollment was actually dispatched
- [ ] `EMP-CHAT-001` captured the real Chat message body (not just the send API call)
- [ ] `EMP-CHAT-002` proved the absence of the legacy `Onboarding Request:` line

### RBAC proof (both layers)
- [ ] `EMP-RBAC-001` proved UI gate for crew
- [ ] `EMP-RBAC-002` proved backend API gate for crew (403 on create_employee_direct)
- [ ] `EMP-RBAC-003` proved field-level permissions (crew cannot set_value on Employee)
- [ ] `EMP-RBAC-005` proved compensation amount is hidden/masked from crew

### TERMINATE stage proof
- [ ] `EMP-TERMINATE-001` proved separation trigger created a BEI Clearance request
- [ ] `EMP-TERMINATE-003` proved clearance station sign-offs were uploaded
- [ ] `EMP-TERMINATE-004` proved Documenso e-signature was triggered (or documented why not)
- [ ] `EMP-TERMINATE-005` proved the employee transitioned to `status = Left` with `relieving_date`

### EXIT INTERVIEW stage proof
- [ ] `EMP-EXITINTERVIEW-001` proved exit interview form was filled and submitted
- [ ] `EMP-EXITINTERVIEW-002` proved analytics page reflects the new response

### FINAL PAY stage proof
- [ ] `EMP-FINALPAY-001` proved a final Salary Slip was generated for the terminated employee
- [ ] `EMP-FINALPAY-003` proved the final pay was marked as Released

### COMPLIANCE stage proof
- [ ] `EMP-COMPLIANCE-001` proved 13th month computation includes the regularized test employee (or documented why not)

### DEACTIVATE stage proof
- [ ] `EMP-USERDISABLE-001` verified the User account is disabled (or logged a HIGH defect if not)
- [ ] `EMP-USERDISABLE-002` verified login fails for the terminated employee (or logged a CRITICAL defect if not)
- [ ] `EMP-ADMSREMOVE-001` verified a DELETE USERINFO command was queued on termination
- [ ] `EMP-ADMSREMOVE-002` verified the DELETE USERINFO was actually dispatched

### REHIRE proof
- [ ] `EMP-REHIRE-001` documented and exercised the actual rehire path (re-activate vs new record)

### ENRICHMENT proof
- [ ] `EMP-ENRICHMENT-001` captured initial enrichment status for the test employee
- [ ] `EMP-ENRICHMENT-002` proved enrichment tracker percentage increased after all EMP-EDIT-* scenarios

### UX GAPS documented (audit-derived from 2026-04-06 audit)
- [ ] `EMP-UX-001` documented attendance page self-service gap (CRITICAL defect logged)
- [ ] `EMP-UX-002` documented schedule page self-service gap (CRITICAL defect logged)
- [ ] `EMP-UX-003` documented attendance-correction admin queue absence (CRITICAL defect logged)
- [ ] `EMP-UX-004` documented broken compensation detail modal (CRITICAL defect logged)
- [ ] `EMP-UX-005` documented missing Finance approve/reject buttons (CRITICAL defect logged)
- [ ] `EMP-UX-006` documented crew sidebar bloat (HIGH defect logged)
- [ ] `EMP-UX-007` documented missing payslip PDF download (MEDIUM defect logged)
- [ ] `EMP-UX-008` documented absent notification system (MEDIUM defect logged)
- [ ] `EMP-UX-009` documented missing Approved Hours on OT (HIGH defect logged)
- [ ] `EMP-UX-010` documented missing branch-level payroll processing (HIGH defect logged)

### STUB PAGES documented
- [ ] `EMP-STUB-001` documented HR Reports page as 100% non-functional (CRITICAL defect logged)
- [ ] `EMP-STUB-002` documented Training module as read-only (HIGH defect logged)
- [ ] `EMP-STUB-003` documented Performance Review as read-only (MEDIUM defect logged)
- [ ] `EMP-STUB-004` documented Disciplinary case detail blank render (HIGH defect logged)
- [ ] `EMP-STUB-005` documented Clearance module as milestone-tracker stub (CRITICAL defect logged)

### DEFECTS.csv coverage
- [ ] DEFECTS.csv has at least 15 rows (10 UX + 5 STUB minimum)
- [ ] Each row has: scenario_id, severity, title, observed, expected, recommended_sprint
- [ ] CRITICAL defects (clearance, reports, compensation modal, finance approval, attendance/schedule self-service, attendance-correction queue) flagged for next sprint reservation

### CLEANUP proof (no corner cutting)
- [ ] `EMP-CLEAN-002` audit query returned `0`
- [ ] `EMP-CLEAN-003` Bio ID pollution check returned max ≤ (Phase 0 baseline + EMP-CREATE count)
- [ ] All test employees created during the run have `status = Left` or equivalent
- [ ] `DEFECTS.csv` exists (may be empty)
- [ ] `SUMMARY.md` explicitly states pass/fail counts per prefix AND a lifecycle-coverage matrix (all 19 stages present)

### Governance
- [ ] Sprint registry and plan YAML updated to `COMPLETED` on the sprint branch (not production, per S099)
- [ ] Single PR created against `production`, targeting `docs/testing/scenarios/` + `output/l3/s166/` only (no code changes)

---

## Cleanup Contract

This sprint creates exactly one branch in one repo:

- **Branch:** `s166-l3-employee-lifecycle-scenarios` in the `hrms` (BEI-ERP) repo only
- **No worktrees**
- **No bei-tasks changes** (scenario catalog lives in BEI-ERP)
- **Merge target:** `production`
- **Cleanup trigger:** after PR merge, the executing session deletes the local branch and runs `git worktree list` to confirm no stale worktrees exist
- **Test data cleanup:** EMP-CLEAN-001 + EMP-CLEAN-002 are the in-sprint cleanup path. If they fail, the sprint FAILs and the user must be notified — do not close out with leftover Active test employees.

---

## Autonomous Execution Contract (for Phase 3 fresh session)

- **completion_condition:** all 137 scenarios executed with evidence files complete (≥137 form_submissions, ≥1 per prefix), all 8 lifecycle stages represented in the run, cleanup scenarios PASS, defect register written
- **stop_only_for:**
  - Cannot log in as any of the 3 required test accounts after 3 attempts with grounded research
  - Production backend returns 5xx on every scenario attempt (outage)
  - `DEVICE_TO_STORE` precondition for ADMS scenarios cannot be satisfied with any available branch
  - Business-data decision: a test employee created during the run somehow escaped cleanup AND the user must decide whether to delete
- **continue_without_pause_through:** scenario execution → evidence capture → guard validation → defect triage → cleanup → closeout
- **blocker_policy:** selector flake = 3-attempt loop with research; product defect = log and continue; environment instability = document and continue
- **signoff_authority:** single-owner (Sam)

---

## Out of Scope Reminders

These are tempting add-ons. Do NOT add them to this sprint:

- Writing a new Playwright helper library (use existing `playwright-bei-erp-workspace/`)
- Modifying the S164/S160/S148 product code (execution-only sprint)
- Adding new test accounts (use the 10 in `memory/testing-accounts.md`)
- Exporting Playwright traces to an external viewer (zip files in `output/l3/s166/artifacts/` are enough)
- Writing scenarios for HR self-service flows (covered by `hr-self-service` module)
- Writing scenarios for the transfer workflow (covered by `employee-transfer` flow)
- Writing scenarios for the onboarding request approval path (covered by `onboarding` module)
- Running the full L3 suite (`/l3-v2-bei-erp all`) — only `hr-employee-lifecycle`

---

## Known Risks (documented, not fixed)

| Risk | Mitigation |
|---|---|
| Test employees polluting production `tabEmployee` with `BEI-EMP-2026-*` names | EMP-CLEAN-001/002 run as the final gate. Names include `(L3 YYYY-MM-DD HH:MM:SS)` suffix to make pollution visible in any masterlist query. |
| ADMS device dispatch is asynchronous and may not complete in 60 seconds | EMP-ADMS-002 documents observed latency instead of failing if the dispatcher is slow — not a product bug, just a measurement |
| Google Chat notifications space is shared with real HR alerts | Use the standard test-only space if one exists, OR include a `[L3 TEST]` prefix in the test employee's name so the Chat message is visibly tagged |
| `docs/testing/scenarios/` may get rewritten by the scenario catalog build script | Check if `scripts/testing/build_l3_scenario_catalog.py` regenerates the file from another source of truth first. If yes, author scenarios in the source instead of the derived file. |
| Salary change UI flow depends on which of S148/S158/S114 is the canonical one | Phase 0 research pins this down before authoring. If the three sprints disagree, the one currently deployed on main wins. |
| Bio ID sequence could be re-polluted by this sprint's own test runs | EMP-CREATE-010 actively tests for sequence integrity. EMP-CLEAN-002 sweeps leftovers. Worst case: a follow-up SSM script clears polluted Bio IDs (pattern from S164 post-deploy fix at `scripts/s164_fix_bio_id_outliers.py`). |

---

## Handoff Prompt (for Phase 3 fresh session)

Paste this into a new Claude Code session after Phases 0–2 are committed and pushed:

```
Run /l3-v2-bei-erp for sprint S166.

Plan: docs/plans/2026-04-06-sprint-166-l3-employee-lifecycle-scenarios.md
Scenario catalog: docs/testing/scenarios/modules/hr-employee-lifecycle.md
Branch: s166-l3-employee-lifecycle-scenarios
Module: hr-employee-lifecycle

Scope: all 137 scenarios across 36 prefixes, covering the COMPLETE employee lifecycle (19 stages):
  HIRE → EDIT (personal/contact/address/employment/photo/bank/gov-id)
  → COMPENSATE (per-employee page: setup/change/approval/rejection/payroll integrity)
  → REGULARIZE → LEAVE (apply/approve/reject/balance)
  → OVERTIME (file/approve/reject/payslip-reflection)
  → ATTENDANCE CORRECTION (submit/approve/record-updated)
  → PAYROLL RUN (process/review/approve/remittances/comparison/history)
  → PAYSLIP (employee self-service view)
  → DISCIPLINARY (memo/NTE/response/resolve/suspension)
  → TRANSFER (with ADMS device re-enrollment)
  → TERMINATE (clearance/Documenso)
  → EXIT INTERVIEW (fill/analytics)
  → FINAL PAY (last payslip/BIR 2316/released)
  → COMPLIANCE (13th month)
  → DEACTIVATE (user disable + device DELETE)
  → REHIRE → ENRICHMENT (tracker updates) → CLEANUP.

Test employees created during run:
- EMP-A: main lifecycle subject (create → all edits → compensate → regularize → transfer → terminate → clearance → final pay → deactivate)
- EMP-B: multi-component salary testing + Bio ID reassignment
- EMP-C: rehire subject (create → quick terminate → rehire)

Self-service scenarios (leave, OT, payslip, attendance correction) use test.crew1@bebang.ph
because freshly created employees have no User account (S164 excluded auto-provisioning).

Dependency chain:
- EMP-CREATE-001 (EMP-A) runs first
- EMP-CREATE-002 (EMP-B) runs second
- All EMP-EDIT-*, EMP-SALARY-*, EMP-REGULARIZE chain off EMP-A
- EMP-LEAVE/OT/ATTENDANCE/PAYSLIP use test.crew1@bebang.ph (self-service actor)
- EMP-PAYROLL-RUN uses test.hr@bebang.ph operating on a period that includes both EMP-A and test.crew1
- EMP-DISCIPLINARY targets EMP-A
- EMP-TRANSFER targets EMP-A (moves branches)
- EMP-TERMINATE chains off EMP-A after all edits/salary/transfer are done
- EMP-EXITINTERVIEW/FINALPAY/USERDISABLE/ADMSREMOVE chain off EMP-TERMINATE-005
- EMP-REHIRE uses EMP-C (separate employee, not EMP-A)
- EMP-COMPLIANCE/ENRICHMENT are cross-cut verification
- EMP-CLEAN-* runs last, always

Test accounts needed (5):
- test.hr@bebang.ph (HR Manager — primary actor, creates employees, processes payroll, issues disciplinary)
- test.crew1@bebang.ph (Crew — self-service: leave, OT, payslip, attendance + negative RBAC target)
- test.finance@bebang.ph (Finance — salary change approval/rejection)
- test.supervisor@bebang.ph (Supervisor — approves leave, OT, attendance corrections)
- test.area@bebang.ph (Area Supervisor — transfer approval if needed)

Evidence files to produce (per S092 anti-corrupt-success rule):
- output/l3/s166/form_submissions.json  (≥137 entries, at least one per prefix)
- output/l3/s166/api_mutations.json
- output/l3/s166/state_verification.json
- output/l3/s166/evidence/{SCENARIO_ID}.json  (one per scenario)
- output/l3/s166/artifacts/{SCENARIO_ID}.trace.zip
- output/l3/s166/screenshots/
- output/l3/s166/SUMMARY.md  (must include lifecycle-coverage matrix showing all 19 stages)
- output/l3/s166/DEFECTS.csv  (may be empty)

Test accounts: memory/testing-accounts.md (all passwords BeiTest2026!)

No corner cutting:
- Real browser clicks through sidebar navigation
- Real form fills on real controls (no selectOption shortcut on comboboxes)
- Real submit button clicks
- Real network capture on every submit
- Real state verification via subsequent GET
- Realistic Filipino test names with timestamp suffix
- Cleanup is mandatory — EMP-CLEAN-002 must return 0 leftover Active test employees

After all scenarios pass:
1. Commit evidence: git add -f output/l3/s166/ docs/testing/scenarios/ && git commit -m "test(S166): L3 employee lifecycle evidence" && git push
2. Update plan YAML status to COMPLETED with execution_summary
3. Update SPRINT_REGISTRY.md S166 row to COMPLETED
4. Create PR against production for the scenario catalog + evidence
```

---

## Scope Overflow Acknowledgement

This sprint is **60 work units total**, under the 80-unit per-sprint ceiling but with two dense phases (Phase 1 authoring = 18 units, Phase 3 execution = 20 units). Per the S089 scope overflow rule, this is accepted by design:

- The user explicitly requested "focus on completion, do not mind the 80 units" on 2026-04-06
- The lifecycle cannot be meaningfully tested by splitting across sprints because every stage depends on the previous (you can't test termination without a created employee that has been edited and compensated)
- Splitting would create inter-sprint state handoffs that defeat the purpose of catching integration bugs

**Context pressure defense for Phase 3:** The executing session MUST aggressively write scenario evidence to disk as it runs (one file per scenario under `output/l3/s166/evidence/`), NOT batch the writes to the end. Per S089 continuous drift detection, the executor should re-read this plan's Verification Checklist after every 20 scenarios completed and self-check that no prefix has been silently skipped. If the executor hits context exhaustion, the appropriate recovery is to stop, commit all evidence to the branch, hand off to a fresh session via the resume prompt in the run's `RUN_STATUS.json`, and continue — NOT to declare partial completion and summarize away.

## Execution Authority

This is a scenario-authoring + test-execution sprint. Phases 0–2 (authoring + registering) run in the current session. Phase 3 (execution) runs in a fresh session per S099 L3 handoff. Phases 4–5 (triage + closeout) run in whichever session is carrying the evidence.

Do not pause between Phases 0–2 for progress reports. Do not skip the Phase 0 research — corner-cutting there is what produces flaky scenarios that fail on first execution.

**For Phase 3 only:** If context pressure becomes severe before all 137 scenarios complete, the executor MUST write `output/l3/s166/RUN_STATUS.json` with the last completed scenario ID and a list of pending ones, commit the partial evidence, and output a resume-from-X prompt for a fresh session. Multi-session execution of a single run is acceptable. Silent partial completion is NOT acceptable.

---

## Execution Topology v3 (Amendment 2026-04-07 PM) — MANDATORY

The original Phases 0–5 described a sequential single-session execution model. A 2026-04-07 chat-driven execution attempt proved that model infeasible: selector flake on Radix dialog overlays (Gender combobox click intercepted by `dialog-overlay` z-index after 16 retries), login race conditions on rapid post-auth navigation, and context exhaustion at scale would force corrupt-success behavior. Per the S092 anti-corrupt-success rule, "agent declares COMPLETED while skipping the procedural steps that reveal real bugs" is exactly what would happen with a single agent attempting 137 scenarios in one session.

**v3 replaces sequential execution with an 8-lane parallel /teammates topology gated by a mandatory independent Audit Agent.** This section is the binding execution model for Phase 3+ — Phases 3, 4, 5 in the original plan are restructured into Waves 0, 1, 1.5, and 2 below.

### Why a separate Audit Agent (research basis)

The S092 hard evidence gate says "the evidence files are the judge, not the agent." That gate only works if a different agent inspects the evidence than the one that produced it. Self-grading is the root cause of corrupt success (see S099 L3 handoff rule, S092 anti-corrupt-success rule, and arXiv 2603.03116 corrupt success in LLM agents). The Audit Agent enforces this separation at every wave gate.

### Wave 0 — Selector Discovery (sequential, 1 agent, ~30 min)

**Purpose:** Eliminate per-lane selector duplication and Radix-overlay flakiness before any execution lane runs.

**Output:** `output/l3/s166/SELECTORS.json` — locator strings, dialog hierarchies, and known-overlay-z-index workarounds for every dialog/form referenced by the 137 scenarios:

- Add New Employee dialog (S164)
- EmployeeDetailDialog (S160) — every collapsible section: personal, contact, address, employment, photo, bank, gov ID
- CompensationDetailDialog (S148/S158) and the dedicated `/dashboard/hr/payroll/compensation-setup/[employee]` page
- Sensitive-changes approval queue (S114) at `/dashboard/hr/payroll/sensitive-changes`
- LeaveRequestDialog at `/dashboard/hr/leave`
- Overtime form at `/dashboard/hr/overtime`
- Attendance Correction form at `/dashboard/hr/attendance-correction`
- Regularization page at `/dashboard/hr/performance/regularization`
- Transfer creation form at `/dashboard/hr/transfers`
- Disciplinary case form at `/dashboard/hr/disciplinary` and detail at `/dashboard/hr/disciplinary/[id]`
- Separations page at `/dashboard/hr/separations`
- Clearance page at `/clearance`
- Exit interview form (route TBD by Phase 0 research)
- Payslip view at `/dashboard/hr/payslip`
- Enrichment tracker at `/dashboard/hr/enrichment-tracker`
- 13th-month compliance page at `/dashboard/hr/compliance/13th-month`
- Payroll run pages: `/dashboard/hr/payroll/{processing,review-output,remittances,comparison,history}`

**Each entry in SELECTORS.json must include:** the trigger button locator, the dialog/popover root locator, every form field's stable selector (preferring `getByLabel` then `getByRole` then explicit `data-testid`), the submit button locator, and any known overlay-z-index workaround (e.g., `force: true` clicks for combobox triggers inside dialogs, `Escape` key dismissal patterns).

**Wave 0 must finish and SELECTORS.json must validate before any execution lane starts.** No exceptions.

### Wave 1 — Parallel Execution (8 lanes via /teammates)

| Lane | Owner | Scenarios | Count | Notes |
|---|---|---|---|---|
| **A** — Main lifecycle | EMP-A | EMP-CREATE-001, all EMP-EDIT-PERSONAL/CONTACT/ADDRESS/EMPLOYMENT, EMP-PHOTO, EMP-BANK, EMP-GOVID, EMP-SALARY-SETUP-001, EMP-SALARY-CHANGE-001/002/004/005, EMP-SALARY-PAYROLL-001, EMP-REGULARIZE, EMP-COMPLETION, EMP-CONFLICT, EMP-CHAT, EMP-ADMS, EMP-DISCIPLINARY (all 5), EMP-TERMINATE (all 6), EMP-FINALPAY (all 3), EMP-USERDISABLE (both), EMP-ADMSREMOVE (both), EMP-EXITINTERVIEW (all 3), EMP-COMPLIANCE (both), EMP-ENRICHMENT (both), EMP-REHIRE (both) | ~67 | Deepest lane. Almost certain to need a Lane-A continuation handoff via `LANE_A_CHECKPOINT.json` |
| **B** — Salary parallel paths | EMP-B | EMP-CREATE-002, EMP-SALARY-SETUP-002/003/004, EMP-SALARY-CHANGE-003/006, EMP-SALARY-PAYROLL-002, EMP-BIOCHANGE-001/002 | ~10 | Self-contained |
| **C** — Transfer + 2nd-create | EMP-C | EMP-CREATE-003/005/006/007/010, EMP-TRANSFER-001..005, EMP-REGULARIZE-003 | ~12 | Owns EMP-C; gated by Lanes A+B CREATE completion (Bio ID rule) |
| **D** — Self-service crew1 | (existing test.crew1) | EMP-LEAVE-001..005, EMP-OVERTIME-001..004, EMP-ATTENDANCE-001..003, EMP-PAYSLIP-001/002 | 14 | Zero deps on A/B/C — fully parallel from t=0 |
| **E** — RBAC | (any existing) | EMP-CREATE-008/009, EMP-RBAC-001..005 | 7 | Zero data deps |
| **F** — UX gaps + Stubs | (no employee created) | EMP-UX-001..010, EMP-STUB-001..005 | 15 | Pure observation, zero data writes |
| **G** — Payroll run | (uses EMP-A late) | EMP-PAYROLL-RUN-001..006 | 6 | Waits for Lane A's salary chain to finish |
| **H** — NO_DEVICE branch + Bio baseline | (1 throwaway) | EMP-CREATE-004 | 1 | Needs an unmapped branch from Phase 0 device map |

Total: 132 in lanes + 5 cross-lane verification = 137.

#### Bio ID sequence collision rule (binding)

EMP-CREATE-010 asserts `second_bio_id == first_bio_id + 1`. This requires that NO other agent creates an employee in between Lane C's two atomic CREATE calls. **Wave 1 launches in two micro-bursts:**

1. **t=0:** Lanes A, B, D, E, F, H all start (D, E, F, H have no employee-creation dependency on each other; A and B each create one employee at the start of their run)
2. **t≈3 min:** Wait for Lanes A and B to confirm in their `LANE_STATE.json` that EMP-A and EMP-B are created
3. **t≈3 min:** Lanes C and G start. Lane C runs EMP-CREATE-003/005/010 as an atomic burst with no waits, immediately verifies the sequence assertion, then proceeds to TRANSFER chain.

#### Per-lane evidence files (NO shared writes)

Each lane writes ONLY to its own subdirectory to avoid concurrent JSON corruption:

```
output/l3/s166/lanes/{lane_id}/
├── form_submissions.json
├── api_mutations.json
├── state_verification.json
├── EMP_STATE.json                # which employees this lane created
├── LANE_STATE.json               # progress + last completed scenario
├── SUMMARY.md
├── evidence/{SCENARIO_ID}.json
├── screenshots/{SCENARIO_ID}_*.png
└── artifacts/{SCENARIO_ID}.trace.zip
```

Wave 2 merges these into the canonical top-level files.

#### Per-lane try/finally cleanup contract (BINDING)

Every lane agent MUST wrap its execution in a try/finally block that soft-deletes (sets `status=Left`, `relieving_date=today`) every employee it created, regardless of crash, exception, or context exhaustion. The cleanup must run via the same browser session and the same UI flow whenever possible (not a backend API shortcut). On unrecoverable crash (browser dead), the lane agent must write the orphan list to `output/l3/s166/lanes/{lane}/ORPHANS.csv` with employee IDs so Wave 2's sweep can find them.

**Test employee name pattern (binding):** Every test employee created by any lane uses the suffix `(L3 2026-04-07 HH:MM:SS)` in its `last_name` field. This is the canonical pollution-finder pattern for Wave 2 cleanup queries.

**Soft-delete only.** No hard `frappe.delete_doc()` calls. Set status=Left and the employee remains in the database for audit but is excluded from active workflows.

### Wave 1.5 — Audit Gate (MANDATORY, after EACH lane reports completion)

Per the S092 anti-corrupt-success rule, evidence files are the judge — but only if someone actually inspects them. The Audit Gate is a SEPARATE agent (not the lane runner) whose job is to verify each lane's evidence is real, not fabricated, before Wave 2 can merge it.

#### Audit Agent responsibilities (per lane)

1. **File existence check.** Verify all required files exist in `output/l3/s166/lanes/{lane}/`: form_submissions.json, api_mutations.json, state_verification.json, evidence/*.json, screenshots/*.png, SUMMARY.md, EMP_STATE.json. Any missing file = lane FAILS audit.

2. **Entry count check.** Verify the form_submissions.json entry count matches the lane's scenario count exactly (no padding, no missing). Verify at least one entry per prefix the lane owns.

3. **Per-scenario integrity check.** For every scenario in the lane's catalog:
   - form_submissions entry exists with non-empty `inputs` object and a `response` containing real `status` code + non-empty `body`
   - api_mutations entry exists for every mutating scenario type (happy/edge/integration/regression) where state was changed
   - state_verification entry has real `before` and `after` values (NOT `null`, NOT empty string)
   - screenshot file exists and is non-zero bytes
   - The trace zip exists if the scenario was a happy/integration type

4. **Random spot-check (30% of scenarios per lane).** For 30% of scenarios chosen at random:
   - Open the post-action screenshot. Confirm it shows the relevant page (NOT a login page, NOT an error page, NOT a blank page).
   - Read the api_mutations `response_body`. Verify it contains expected success markers from the scenario's plan-defined assertions (e.g., `name: BEI-EMP-2026-...`, `status: 200`, the right `employee_name`).
   - Cross-check `inputs` against the scenario's plan-defined payload. If inputs are missing fields the scenario said to fill, FAIL.
   - For RBAC scenarios, verify the response is actually a 403 (not a 200 the agent re-classified as "blocked").
   - For UX-gap scenarios, verify the screenshot actually shows the absence of the expected feature, not just any random page.

5. **Anti-fabrication checks.** Reject as fabricated if any of these are detected:
   - All screenshots in the lane are byte-identical (lane never actually navigated)
   - All toast strings are identical (lane reused a captured response)
   - PHT timestamps are out of sequence or all identical (lane wrote evidence in a single batch at the end)
   - api_mutations response bodies are all `{}` or all contain the same string
   - state_verification `before == after` for every scenario (lane skipped real state changes)

6. **Output:**
   - If lane has zero rejections: write `output/l3/s166/lanes/{lane}/AUDIT_PASSED.flag` with audit timestamp + auditor agent ID
   - If any rejections: append rows to `output/l3/s166/AUDIT_REJECTIONS.csv` with columns: `lane, scenario_id, reason, suggested_rerun_action, rejected_at`. Do NOT write the AUDIT_PASSED.flag.

#### Audit Agent authority (binding)

- The Audit Agent CAN mark any scenario `EVIDENCE_REJECTED` regardless of the lane runner's PASS claim.
- The Audit Agent CAN demand a re-run on the lane (up to 3 attempts per scenario).
- The Audit Agent MUST NOT be the same agent that ran the lane (S099 separation principle).
- The Audit Agent MUST NOT modify lane evidence files — only write to AUDIT_REJECTIONS.csv and AUDIT_PASSED.flag.
- The Audit Agent's PASS/FAIL decision is final for that lane unless the human orchestrator overrides.

#### Re-run loop (binding)

- If audit rejects ≥1 scenario in a lane, the orchestrator dispatches a NEW agent (not the original lane runner, not the auditor) to re-run only the rejected scenarios. The fix-only agent's prompt includes the audit's `reason` and `suggested_rerun_action`.
- After the fix-only agent completes, the SAME audit agent (or a fresh auditor) re-checks ONLY the rejected scenarios.
- Maximum 3 fix-loop iterations per scenario before escalation to the human orchestrator as a true blocker.
- Each fix iteration writes its own audit row so the iteration history is visible.

#### Human orchestrator audit gate (binding)

The orchestrator (the chat session managing the waves) MUST personally read each lane's `SUMMARY.md` and the cumulative `AUDIT_REJECTIONS.csv` before approving Wave 2. The orchestrator MUST challenge anything suspicious:
- Padded counts (137.0 reported but no per-prefix breakdown)
- Identical screenshots across scenarios
- Generic toast strings ("Success" or "Created")
- Missing PHT timestamps in evidence files
- Lanes that finished suspiciously fast (e.g., Lane A in <30 minutes)

If anything looks suspicious, the orchestrator MUST dispatch additional re-runs or escalate to the user before merging Wave 2 evidence.

### Wave 2 — Merge + Cleanup + Closeout (sequential, 1 agent)

Runs only after EVERY lane has an `AUDIT_PASSED.flag` file present.

1. Concatenate per-lane evidence files into canonical:
   - `output/l3/s166/form_submissions.json` (must end with ≥137 entries)
   - `output/l3/s166/api_mutations.json`
   - `output/l3/s166/state_verification.json`
2. Run `EMP-CLEAN-001` — sweep all `(L3 2026-04-07 ...)` employees not already Left (catches lane orphans from any crashed cleanup)
3. Run `EMP-CLEAN-002` — final audit query: `SELECT COUNT(*) FROM tabEmployee WHERE name LIKE 'BEI-EMP-2026-%' AND status='Active' AND employee_name LIKE '%L3 2026-04-07%'` MUST return 0
4. Run `EMP-CLEAN-003` — Bio ID baseline check (Phase 0 max + EMP-CREATE count tolerance)
5. Run guard validation: `python scripts/testing/l3_browser_guard.py validate` against the canonical files
6. Write canonical `output/l3/s166/SUMMARY.md` with totals, per-prefix counts, lifecycle-coverage matrix (all 19 stages must be present), per-lane audit results, and re-run iteration history
7. Write `output/l3/s166/DEFECTS.csv` aggregating in-scope defects + collateral defects from all lanes' UX/STUB observations
8. Update plan YAML status → COMPLETED with execution_summary populated
9. Update SPRINT_REGISTRY.md S166 row → COMPLETED
10. Commit evidence with `git add -f output/l3/s166/`
11. Push to `s166-l3-execution-evidence` branch (separate from the catalog PR #469 which was already merged 2026-04-07) and open the evidence PR
12. Hand off PR number to user for merge approval

### Pilot-first execution decision (binding, 2026-04-07)

To minimize blast radius if the pattern fails, Wave 1 execution starts with **only the 4 zero-dependency lanes (D, E, F, H — 42 scenarios)** as **Wave 1-Pilot**. If pilot lanes pass audit, **Wave 1-Full** (lanes A, B, C, G — 95 scenarios) launches. If pilot reveals systemic issues (Radix overlay flake unresolved by SELECTORS.json, login race conditions in /teammates dispatch, Audit Agent finding fabrication patterns), the orchestrator stops and escalates to the user before Wave 1-Full launches.

### Decisions captured (anti-drift, anti-hallucination)

The following decisions are now BINDING for any session that picks up S166 execution. Do not re-decide these in future sessions:

1. **8-lane parallel topology** is the official execution model. Single-session execution is NOT acceptable for S166 and will produce CORRUPT_SUCCESS.
2. **Audit Agent is mandatory** between every lane's completion and Wave 2 merge. NO exceptions. The lane runner does NOT get to mark its own work PASS without independent audit. Self-grading is forbidden.
3. **Per-lane evidence files** prevent concurrent JSON corruption. NO lane writes to top-level evidence files until Wave 2.
4. **Try/finally cleanup per lane** prevents pollution accumulation. Wave 2 sweep is belt-and-suspenders, not the primary cleanup.
5. **Test employee name pattern** is `(L3 2026-04-07 HH:MM:SS)` in `last_name`. This is the canonical pollution-finder marker.
6. **Soft-delete only** (status=Left). Hard `delete_doc()` is forbidden.
7. **Wave 0 selector discovery is mandatory** before any execution lane runs. SELECTORS.json must validate.
8. **Bio ID sequence integrity** requires Lane C ordering constraint (starts after A+B CREATE, runs C's CREATEs as atomic burst).
9. **Pilot-first**: D+E+F+H run as Wave 1-Pilot first, then A+B+C+G as Wave 1-Full after pilot audit passes.
10. **Re-run budget**: 3 fix-loop iterations per scenario before user escalation.
11. **Human orchestrator audit**: orchestrator MUST personally read SUMMARY.md + AUDIT_REJECTIONS.csv before Wave 2.
12. **Sprint branch for evidence**: `s166-l3-execution-evidence` (separate from the merged catalog branch `s166-l3-employee-lifecycle-scenarios` which became PR #469). Catalog PR #469 was merged on 2026-04-07. Evidence PR is a follow-up.
13. **Phase 0 was completed on 2026-04-07** by `scripts/testing/l3_s166_phase0_preconditions.mjs` — see `data/_CLEANROOM/agent_runs/2026-04-07_s166-l3-execution/PRECONDITIONS.json` for findings (5/5 logins, 71 branches, 4 salary structures, 7 leave types, Documenso reachable). Phase 0 does NOT need to re-run.
14. **Phase 0 known gaps:** `DEVICE_TO_STORE` map endpoint returned 417/404 — Lane H must discover the unmapped branch live by attempting EMP-CREATE-004 against branches and capturing the toast. OT type, clearance station, and disciplinary doctype names not resolved — those lanes (A, D) discover them live during execution.
15. **Catalog PR #469** is merged. Module file `docs/testing/scenarios/modules/hr-employee-lifecycle.md` is on production. Scenario IDs and dependencies are FROZEN — do not edit the catalog during execution.

### Reference: chat session that produced this amendment

- Session date: 2026-04-07 (Tuesday, PHT)
- Orchestrator: Sam (CEO) + Claude Opus 4.6
- Catalog authoring: completed in this session via subagent dispatch, merged as hrms#469
- Phase 0: completed in this session via `l3_s166_phase0_preconditions.mjs`
- Execution attempt: aborted on EMP-CREATE-001 due to Radix dialog overlay z-index issue — proved single-session execution infeasible at this scale
- v3 amendment: written in same session after the failure analysis confirmed the parallel-with-audit topology is the only realistic path
