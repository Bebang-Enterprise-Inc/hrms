---
sprint_id: S170
display: Sprint 170
title: "S166 Defect Fixes — Leave Ledger + Compensation Route + OT Filing UI + Clearance Doctypes"
branch: s170-s166-defect-fixes
status: GO
planned_date: 2026-04-07
completed_date: null
depends_on: S166 (Wave 1-Pilot evidence + Wave 1-Full diagnostic), S164 (employee creation flow), S158 (CompensationDetailDialog component)
total_work_units: 72
execution_type: product-code-fix (4 defects in one session)
frontend_pr: null
backend_pr: null
execution_topology: single-session-sequential-phases
sprint_registry_row: "S170 reserved on 2026-04-07. Branch: s170-s166-defect-fixes. Parent: origin/production."
---

# S170: S166 Defect Fixes

## Mission

Fix the 4 product defects independently verified by S166 Wave 1-Pilot + Wave 1-Full diagnostic so S166 can complete Lane A retest and deliver full 137-scenario coverage. This is a **product-code-fix sprint** running in **parallel** with the S166 testing session — the S166 orchestrator continues dispatching Wave 1-Full Lanes A/C/G while this sprint's single agent fixes the code. When Sam deploys S170's PRs, the S166 orchestrator will dispatch a retest pass on the affected scenarios.

**Out of scope (any of these = STOP and ask):**
- Any fix that expands beyond the 4 defects listed
- Any L3 scenario execution (S166 handles L3 retest)
- Any scenario catalog edit (catalog is frozen per S166)
- Any plan edit other than this file + SPRINT_REGISTRY.md closeout

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

S166 Wave 1-Pilot ran 37 L3 scenarios in parallel across 4 lanes. Lane D (self-service crew1) produced 10 PASS + 1 DEFECT-PASS + 3 SKIP. The DEFECT-PASS and SKIPs surfaced 2 critical product issues. Wave 1-Full blocker diagnostic surfaced 2 more CRITICAL defects that would block ~35-40 Lane A scenarios. All 4 defects were **independently verified** by separate audit agents running live production queries. S166 cannot reach full 137-scenario coverage until these are fixed.

### Why one sprint

User directive (2026-04-07 chat): "delegate the defect fixing to another agent session while your teammates continue testing and then we retest those when fixes are applied." The S166 execution-only contract forbids S166 from fixing code, so these fixes live in a separate sprint (S170) executed by a separate agent in parallel with S166. When S170 PRs land and deploy, S166 retests the affected scenarios.

### Why this phase ordering

- **Phase 1 (Leave Ledger)** — smallest fix, unblocks EMP-LEAVE-003 immediately. Start here to get a fast early win.
- **Phase 2 (Compensation route)** — moderate fix, unblocks ~10 Lane A SALARY scenarios + Lane B (10 scenarios on HOLD in S166).
- **Phase 3 (OT filing UI)** — moderate fix, unblocks EMP-OVERTIME-001/002/003 + EMP-PAYROLL-RUN-003. Backend doctype already exists (`BEI Overtime Request`), only frontend page is missing.
- **Phase 4 (Clearance doctypes)** — the big one. Structural work. Creates `BEI Clearance`, `BEI Clearance Station`, `BEI Clearance Item` doctypes + minimal workflow. Unblocks ~18 Lane A TERMINATE chain scenarios. **This phase is high-risk for a single-session budget.** If Phase 4 exceeds its budget or scope expands, the agent MUST stop, commit Phases 1-3, open a PR for those, and create a S171 reservation for Phase 4. See Scope Size Warning.

### Known limitations and their mitigations

- **Clearance is structural work** — 3 new doctypes + workflow + Documenso integration is genuinely multi-day work. This sprint aims for a **minimum-viable** clearance: doctypes exist, stations can be manually assigned, status transitions work. Documenso integration is DEFERRED. The S166 Lane A retest will still SKIP Documenso scenarios until S171 completes Documenso integration.
- **Leave Ledger root cause is unknown** — the hook exists in `leave_application.py:101-113` but doesn't fire on production. Phase 1 must diagnose before fixing. Three hypotheses documented in Phase 1.
- **Compensation [employee]/page.tsx is 523 lines of Dialog component** — Phase 2 must decide whether to add a Page wrapper in the same file, extract the Dialog to a components/ file, or replace the route with a different pattern.
- **OT filing UI is a new page** — must follow existing bei-tasks page patterns (RoleGuard, HrPageHeader, react-hook-form + Zod, combobox workaround from SELECTORS.json).

### Source references

- S166 Wave 1-Pilot evidence: `output/l3/s166/lanes/lane_d/` (AUDIT_PASSED.flag present)
- S166 Lane F stub findings: `output/l3/s166/lanes/lane_f/evidence/EMP-STUB-005.json`
- Wave 1-Full diagnostic: `output/l3/s166/lanes/wave1_full_diagnostic/DIAGNOSTIC_SUMMARY.md`
- Q1 row trigger: `output/l3/s166/lanes/wave1_full_diagnostic/Q1_ROW_TRIGGER.md`
- Q2 clearance (structural): `output/l3/s166/lanes/wave1_full_diagnostic/Q2_CLEARANCE.md`
- Q3 compensation: `output/l3/s166/lanes/wave1_full_diagnostic/Q3_COMPENSATION.md`
- Leave Application source: `hrms/hr/doctype/leave_application/leave_application.py` (lines 29, 101-113, 703-832)
- Leave hooks override: `hrms/hooks.py` lines 231-233
- BEI Overtime Request doctype: `hrms/hr/doctype/bei_overtime_request/bei_overtime_request.json`
- Compensation dynamic route: `../bei-tasks/app/dashboard/hr/payroll/compensation-setup/[employee]/page.tsx` (523 lines, header says "CompensationDetailDialog — S158")
- Compensation list page: `../bei-tasks/app/dashboard/hr/payroll/compensation-setup/page.tsx`

---

## Ground Truth Lock

### Evidence sources (all verified to exist)

| File | What it proves |
|---|---|
| `hrms/hr/doctype/leave_application/leave_application.py:101-113` | `on_submit` exists and calls `create_leave_ledger_entry()` — hook is written |
| `hrms/hr/doctype/leave_application/leave_application.py:703-832` | `create_leave_ledger_entry` method exists with full implementation |
| `hrms/hooks.py:231-233` | Only `validate` and `on_update` overrides; `on_submit` is NOT overridden |
| `hrms/hr/doctype/leave_ledger_entry/leave_ledger_entry.py` | `create_leave_ledger_entry` utility function exists |
| `../bei-tasks/app/dashboard/hr/payroll/compensation-setup/[employee]/page.tsx` (523 lines) | Header comment says "CompensationDetailDialog — S158 — Large modal dialog showing full compensation detail" — file is misused as Next.js Page route |
| `../bei-tasks/app/dashboard/hr/payroll/compensation-setup/page.tsx` | List page exists with RoleGuard + HrPageHeader + grid |
| `hrms/hr/doctype/bei_overtime_request/bei_overtime_request.json` | DocType exists with employee, attendance, attendance_date (all reqd), overtime_hours, overtime_status, approved_payable_duration, candidate_overtime_type, and full approval workflow fields |
| `hrms/hr/doctype/bei_overtime_request/bei_overtime_request.py` | Python controller exists |
| `find hrms -iname "*clearance*" -type d` (Lane F diagnostic Q2) | Returns empty — no BEI clearance doctypes exist |
| `output/l3/s166/lanes/lane_d/evidence/EMP-LEAVE-003.json` | Live Frappe API reproduction: HR-LAP-2026-00118 is Approved docstatus=1 total_leave_days=1.0 but Leave Ledger Entry filter returns data=[] |

### Count method

- **Work units per defect:** estimated from task granularity (1 unit ≈ 1 focused 20-30 min task)
- **Scenarios unblocked:** counted against S166 Lane A scope in the v3 plan

### Authoritative sections

Phases 1-4 are the execution source of truth. The L3 retest scenarios list at the bottom is S166's concern, not S170's — S170 does NOT run L3.

### Unresolved values

None at plan-write time. Phase 1 root cause is intentionally a diagnostic step, not an unresolved value.

---

## Requirements Regression Checklist (Cold-Start Verification)

Before writing any code, verify your approach against every item:

- [ ] **Defect 1 — Leave Ledger:** Am I FIXING the root cause (hook not firing) rather than writing a cron job to backfill missing ledger entries? Backfilling is a workaround, not a fix. HARD BLOCKER: if root cause cannot be determined in 60 min, STOP and ask Sam.
- [ ] **Defect 2 — Compensation route:** Am I making the `[employee]/page.tsx` file export a default Page component that Next.js can render? A Dialog component cannot be a route file.
- [ ] **Defect 3 — OT filing UI:** Am I integrating with the EXISTING `BEI Overtime Request` doctype, not creating a new doctype?
- [ ] **Defect 4 — Clearance:** Am I creating MINIMUM-VIABLE doctypes (3 doctypes, basic fields, no Documenso), not a full clearance system? Documenso integration is DEFERRED to S171.
- [ ] **Scope discipline:** Am I touching ONLY the files needed to fix these 4 defects? Any adjacent refactoring is out of scope.
- [ ] **Execution-only sprint (S166) independence:** Am I NOT editing any file under `docs/testing/scenarios/` or `docs/plans/2026-04-06-sprint-166*`? S166 catalog is frozen.
- [ ] **Single session:** Am I staying within 72-unit budget? If Phase 4 alone exceeds 35 units during execution, I STOP and split per the Scope Size Warning.
- [ ] **Sentry instrumentation:** Does every new/modified `@frappe.whitelist()` endpoint call `set_backend_observability_context()`?
- [ ] **Branch compliance:** Am I on branch `s170-s166-defect-fixes` (from `origin/production`)?
- [ ] **No force-push to production:** Am I creating a PR and stopping at PR_CREATED, not merging or deploying?

---

## Agent Boot Sequence

1. **Read this plan fully.** Every phase. Every HARD BLOCKER.
2. **Read the Requirements Regression Checklist above.** Write your approach for each item to `output/s170/REQUIREMENTS_REGRESSION_CHECK.md`.
3. **Create sprint branch:** `git fetch origin production && git checkout -b s170-s166-defect-fixes origin/production`. NEVER write code on production.
4. **Read S166 Wave 1-Pilot defect evidence:**
   - `output/l3/s166/lanes/lane_d/evidence/EMP-LEAVE-003.json` (Leave Ledger reproduction)
   - `output/l3/s166/lanes/lane_d/OT_DIAGNOSTIC.md` (OT gap diagnostic)
   - `output/l3/s166/lanes/wave1_full_diagnostic/Q2_CLEARANCE.md` (Clearance doctype inventory)
   - `output/l3/s166/lanes/wave1_full_diagnostic/Q3_COMPENSATION.md` (Compensation route diagnosis)
5. **Read source files listed in Ground Truth Lock** before touching them.
6. **Read `.claude/rules/sentry-observability.md`** for DM-7 Sentry instrumentation.
7. **Read `hrms/overrides/leave_application_hooks.py`** if it exists — that's where the BEI fork adds hooks to Leave Application.
8. **NOW start Phase 1.**

---

## Phases

### Phase 0 — Preconditions + branch setup (2 units)

1. Create branch from `origin/production`
2. Create artifact dir: `mkdir -p output/s170/{diagnostics,verification}`
3. Write `output/s170/REQUIREMENTS_REGRESSION_CHECK.md` filling in each checklist item
4. Write `output/s170/PHASE_BUDGET.json` tracking estimated vs actual units per phase
5. Pull latest main on both repos: `cd F:/Dropbox/Projects/BEI-ERP && git pull origin production` and `cd ../bei-tasks && git checkout main && git pull origin main && git checkout -b s170-s166-defect-fixes`

**Verification:**
- `git branch --show-current` in both repos returns `s170-s166-defect-fixes`
- `output/s170/REQUIREMENTS_REGRESSION_CHECK.md` exists

---

### Phase 1 — Leave Ledger Pipeline Fix (6 units)

**Defect:** Lane D reproduced on 2026-04-07: `HR-LAP-2026-00118` (Casual Leave, employee=TEST-CREW-001) was submitted via real browser UI, approved by test.supervisor, returned from Frappe API as `status=Approved, docstatus=1, total_leave_days=1.0, modified_by=test.supervisor@bebang.ph` — yet `GET /api/frappe/api/resource/Leave Ledger Entry?filters=[["transaction_name","=","HR-LAP-2026-00118"]]` returns `data: []`. Also confirmed for HR-LAP-2026-00117. **Generalized — affects all recently approved leaves. Production leave balances will NOT deduct on approval.**

**Task 1.1 — Diagnose root cause** (2 units)

**HARD BLOCKER:** If root cause cannot be determined in 60 min, STOP and present findings to Sam. Do NOT write a backfill workaround.

Three hypotheses to test in order:

1. **H1: BEI override shadows `on_submit`.** Check `hrms/overrides/leave_application_hooks.py` for any class override, monkey-patch, or `@classmethod` that replaces the parent `LeaveApplication.on_submit`. Check `hooks.py` for any `override_doctype_class` or `doc_events.on_submit` entry. If found → the override is dropping the ledger call → fix by re-adding `self.create_leave_ledger_entry()` to the override.

2. **H2: `create_leave_ledger_entry` method is silently returning early.** Read `hrms/hr/doctype/leave_application/leave_application.py:703-832`. Check for `if self.status != "Approved"` or similar guard. The hook runs on `on_submit` which fires when `docstatus` transitions 0→1. But the BEI flow may be: employee submits leave (docstatus=1, status=Open/Pending), supervisor approves via `update` (status=Approved, docstatus stays 1). If the ledger entry is created on `on_submit` but status is still "Open" at submit time, the method may skip. **The fix: the ledger entry must be created when `status` transitions to "Approved" on an already-submitted doc, which is NOT `on_submit` — it's `on_update_after_submit` or `before_update_after_submit`.**

3. **H3: Production is running stale bytecode.** Compare `git log hrms/hr/doctype/leave_application/leave_application.py` on production vs what's deployed. If the fix exists in source but not on production, the deploy is stale — but that's a deploy bug, not a code fix. Escalate to `/deploy-frappe` to rebuild.

   MUST_MODIFY: `output/s170/diagnostics/LEAVE_LEDGER_DIAGNOSIS.md`
   MUST_CONTAIN: `output/s170/diagnostics/LEAVE_LEDGER_DIAGNOSIS.md` must contain "Root cause:" followed by H1/H2/H3

**Task 1.2 — Implement the fix** (3 units)

Based on the H2 hypothesis (most likely per the Lane D evidence — leaves were docstatus=1 but status was transitioned via supervisor `update` action on `leave-command-center`):

- If `on_submit` skips when `status != "Approved"`, add an `on_update_after_submit` hook OR fix `on_submit` to create the ledger regardless of status, and add a reversal/creation on status change
- The cleanest fix: override `on_update_after_submit` in a BEI hook to detect status transitions Open → Approved / Approved → Cancelled and call `create_leave_ledger_entry` / `delete_leave_ledger_entry` accordingly
- Add Sentry context: `set_backend_observability_context(module="leave", action="on_update_after_submit", mutation_type="update")`

   MUST_MODIFY: either `hrms/hr/doctype/leave_application/leave_application.py` or `hrms/overrides/leave_application_hooks.py` or `hrms/hooks.py`
   MUST_CONTAIN: the modified file must contain `create_leave_ledger_entry` AND a status-transition check

**Task 1.3 — Backfill existing broken leaves** (1 unit)

After the fix is deployed, existing leaves (HR-LAP-2026-00117, 00118, 00119, etc.) still have missing ledger entries. Write a one-shot Python script `scripts/s170_backfill_leave_ledger.py` that:
1. Queries `tabLeave Application` where `docstatus=1 AND status='Approved' AND name NOT IN (SELECT DISTINCT transaction_name FROM \`tabLeave Ledger Entry\`)`
2. For each, calls the fixed `create_leave_ledger_entry` method
3. Logs each backfilled leave to `output/s170/backfilled_leaves.csv`

This script runs manually after deploy; NOT in this phase's code.

   MUST_MODIFY: `scripts/s170_backfill_leave_ledger.py`
   MUST_CONTAIN: the script must contain `create_leave_ledger_entry` AND a filter for `status='Approved'`

**Phase 1 verification (gate):**

```bash
# MUST_MODIFY assertions
git diff --name-only origin/production | grep -E "leave_application\.py|leave_application_hooks\.py|hooks\.py" || exit 1
git diff --name-only origin/production | grep -E "s170_backfill_leave_ledger\.py" || exit 1

# MUST_CONTAIN assertions
grep -l "create_leave_ledger_entry" $(git diff --name-only origin/production | grep -E "\.py$") || exit 1

# Diagnostic file exists
test -f output/s170/diagnostics/LEAVE_LEDGER_DIAGNOSIS.md || exit 1
grep -q "Root cause:" output/s170/diagnostics/LEAVE_LEDGER_DIAGNOSIS.md || exit 1
```

---

### Phase 2 — Compensation `[employee]/page.tsx` fix (10 units)

**Defect:** The file is 523 lines of `CompensationDetailDialog` component (header comment confirms) living at a Next.js App Router route path. Next.js expects `export default function Page({params})` at route files. The file exports a Dialog component, so Next.js renders the layout shell with 0 fields/inputs — confirmed by Wave 1-Full diagnostic Q3.

**Task 2.1 — Read the existing file** (1 unit)

Read all 523 lines of `../bei-tasks/app/dashboard/hr/payroll/compensation-setup/[employee]/page.tsx`. Identify:
- The Dialog component's props (likely `employeeId`, `open`, `onOpenChange`)
- The data fetching hook(s) used (`compensationQueries`)
- The section layout (statutory, earnings, deductions, audit)

**Task 2.2 — Add a Page wrapper at the bottom of the same file** (3 units)

Append a default-exported Page component to the file that:
- Receives `params: { employee: string }` from the route
- Uses the existing Dialog component with `open={true}` and routes back to `/dashboard/hr/payroll/compensation-setup` on `onOpenChange(false)`
- Or more elegant: extract the Dialog internals into a non-dialog layout that renders as a full page (Card + sections) — preferable because a dialog-on-page-route feels wrong

Option A (lazy): `export default function Page({ params }) { const router = useRouter(); return <CompensationDetailDialog employeeId={params.employee} open={true} onOpenChange={(open) => { if (!open) router.push('/dashboard/hr/payroll/compensation-setup'); }} />; }`

Option B (correct): Extract the existing Dialog's body (everything inside `<DialogContent>`) into a reusable `<CompensationDetailPanel>` component, then the Page renders it inside a Card, and the Dialog also renders it inside DialogContent.

**Pick Option B.** Option A is a hack that causes UX oddness (the dialog is modal but the URL is a page route).

   MUST_MODIFY: `../bei-tasks/app/dashboard/hr/payroll/compensation-setup/[employee]/page.tsx`
   MUST_MODIFY: `../bei-tasks/components/hr/compensation-detail-panel.tsx` (new file, extracted component)
   MUST_CONTAIN: `../bei-tasks/app/dashboard/hr/payroll/compensation-setup/[employee]/page.tsx` must contain `export default function Page`

**Task 2.3 — Fix the list-page modal** (3 units)

Lane F EMP-UX-004 found the list-page modal opens showing only Bio ID. After Task 2.2 extracts `CompensationDetailPanel`, update `page.tsx` (the list page) to use the panel inside its existing Dialog trigger. The Dialog should show the same rich content as the dedicated route.

   MUST_MODIFY: `../bei-tasks/app/dashboard/hr/payroll/compensation-setup/page.tsx`
   MUST_CONTAIN: must import `CompensationDetailPanel` from the new component file

**Task 2.4 — Verify both routes work** (2 units)

Run `npm run build` in bei-tasks to confirm the Page route compiles. Run Playwright against local dev (`npm run dev`) to confirm:
- `/dashboard/hr/payroll/compensation-setup/9000003` (pick any real employee Bio ID from production) renders the full compensation detail
- `/dashboard/hr/payroll/compensation-setup` list page + row-click modal also renders the full detail

**Task 2.5 — RoleGuard wrapping** (1 unit)

The Page must wrap in `<RoleGuard roles={[ROLES.HR_MANAGER, ROLES.FINANCE]}>` like the list page does. Do NOT allow crew to see compensation details.

   MUST_CONTAIN: `page.tsx` must contain `<RoleGuard`

**Phase 2 verification gate:**

```bash
git diff --name-only origin/production | grep "compensation-setup/\[employee\]/page.tsx" || exit 1
git diff --name-only origin/production | grep "compensation-setup/page.tsx" || exit 1
git diff --name-only origin/production | grep "compensation-detail-panel.tsx" || exit 1
grep -q "export default function Page" ../bei-tasks/app/dashboard/hr/payroll/compensation-setup/\[employee\]/page.tsx || exit 1
grep -q "RoleGuard" ../bei-tasks/app/dashboard/hr/payroll/compensation-setup/\[employee\]/page.tsx || exit 1
cd ../bei-tasks && npm run build || exit 1
```

---

### Phase 3 — OT Filing UI (15 units)

**Defect:** `BEI Overtime Request` doctype exists with full workflow fields (employee, attendance, attendance_date, overtime_hours, overtime_status, approved_payable_duration, review chain). No frontend page lets employees file against it. Lane D verified: `/dashboard/hr/overtime` shows approval-only UI for supervisor/hr, Access Restricted for crew. No `apply`/`new` variants exist.

**Task 3.1 — Create frontend Apply OT page** (5 units)

Create `../bei-tasks/app/dashboard/hr/overtime/apply/page.tsx`:
- RoleGuard: `[ROLES.CREW, ROLES.SUPERVISOR, ROLES.HR_MANAGER]` (everyone can file OT)
- HrPageHeader with title "File Overtime Request"
- Form: `attendance_date` (date picker), `overtime_hours` (number input, min=0.5, max=12), `reason_category` (select from doctype options), `overtime_reason` (textarea), optional `shift` (combobox — use the proven `click({force:true})` workaround)
- Submit button → POST to backend endpoint (Task 3.2)
- On success: toast + redirect to `/dashboard/hr/overtime`

Use react-hook-form + Zod schema for validation. Follow the pattern of `../bei-tasks/app/dashboard/hr/leave/page.tsx` LeaveRequestDialog.

   MUST_MODIFY: `../bei-tasks/app/dashboard/hr/overtime/apply/page.tsx`
   MUST_CONTAIN: must contain `RoleGuard`, `useForm`, `zodResolver`, `attendance_date`, `overtime_hours`

**Task 3.2 — Create backend endpoint** (4 units)

Create `hrms/api/overtime_request.py` with `@frappe.whitelist()` function:
- `create_overtime_request(employee, attendance_date, overtime_hours, reason_category, overtime_reason, shift=None)`
- First line: `set_backend_observability_context(module="overtime", action="create_overtime_request", mutation_type="create")`
- Permission check: `frappe.has_permission("BEI Overtime Request", "create", throw=True)`
- Validate: `attendance_date` must be within last 7 days, `overtime_hours` must be 0.5-12
- Insert BEI Overtime Request with `employee=<current user's employee id>`, `overtime_status="Pending"`, etc.
- Return `{employee, name, overtime_status}`

   MUST_MODIFY: `hrms/api/overtime_request.py`
   MUST_CONTAIN: must contain `@frappe.whitelist()`, `set_backend_observability_context`, `BEI Overtime Request`

**Task 3.3 — Add "File OT" button to existing `/dashboard/hr/overtime` page** (2 units)

The existing OT page is approval-only. Add a "File New OT Request" button (visible to everyone with the correct roles) that links to `/dashboard/hr/overtime/apply`. This gives crew a discoverable entry point.

   MUST_MODIFY: `../bei-tasks/app/dashboard/hr/overtime/page.tsx`
   MUST_CONTAIN: `File New` OR `Apply Overtime` (button text)

**Task 3.4 — Update RBAC on existing OT page** (2 units)

Lane D found `/dashboard/hr/overtime` returns Access Restricted for crew. Crew should be able to VIEW their own OT requests even if they can't see others'. Update the RoleGuard + server-side permission to allow crew access to a filtered view ("My Overtime Requests") AND the apply page.

   MUST_MODIFY: `../bei-tasks/app/dashboard/hr/overtime/page.tsx`
   MUST_CONTAIN: `ROLES.CREW`

**Task 3.5 — Playwright local smoke test** (2 units)

Before PR, run Playwright locally:
1. Log in as test.crew1
2. Navigate to `/dashboard/hr/overtime/apply`
3. Fill form with realistic values
4. Submit
5. Verify OT record created via API GET

Capture screenshots to `output/s170/verification/ot_apply_smoke.png`.

**Phase 3 verification gate:**

```bash
git diff --name-only origin/production | grep "overtime/apply/page.tsx" || exit 1
git diff --name-only origin/production | grep "hrms/api/overtime_request.py" || exit 1
grep -q "@frappe.whitelist" hrms/api/overtime_request.py || exit 1
grep -q "set_backend_observability_context" hrms/api/overtime_request.py || exit 1
grep -q "useForm" ../bei-tasks/app/dashboard/hr/overtime/apply/page.tsx || exit 1
test -f output/s170/verification/ot_apply_smoke.png || exit 1
```

---

### Phase 4 — Clearance Minimum-Viable Doctypes (35 units — HIGHEST RISK)

**Defect:** Zero `*Clearance*` doctypes exist in hrms/hr/doctype/. Only Frappe upstream `Bank Clearance` exists. Lane F + Wave 1-Full Q2 both confirmed this is structural, not UI. The Separation page works (1 active record test.hr 2026-03-17) but has nothing to attach clearance to.

**⚠️ SCOPE SIZE WARNING:** This phase alone is 35 units. If the agent reaches 40 units during execution, STOP, commit Phases 0-3 + partial Phase 4 progress, open a PR for what's done, create S171 reservation for the remainder. Do NOT silently extend scope.

**Task 4.1 — Create `BEI Clearance Station` doctype** (5 units)

New doctype at `hrms/hr/doctype/bei_clearance_station/bei_clearance_station.json`:
- Fields: `station_name` (Data, reqd, unique), `station_code` (Data, reqd, unique), `default_responsible_role` (Link to Role), `description` (Small Text), `enabled` (Check, default 1), `sort_order` (Int)
- This is a MASTER doctype (not per-employee). Each real station (IT, POS, Uniform, Keys, Finance, HR, Security, Store Manager) gets one row.

Create a fixture file `hrms/fixtures/bei_clearance_station.json` with 8 default stations.

Create the Python controller `bei_clearance_station.py` with standard `FrappeDocument` boilerplate.

   MUST_MODIFY: `hrms/hr/doctype/bei_clearance_station/bei_clearance_station.json`
   MUST_MODIFY: `hrms/hr/doctype/bei_clearance_station/bei_clearance_station.py`
   MUST_MODIFY: `hrms/fixtures/bei_clearance_station.json`

**Task 4.2 — Create `BEI Clearance Item` child doctype** (5 units)

New child table doctype at `hrms/hr/doctype/bei_clearance_item/bei_clearance_item.json`:
- Fields: `station` (Link to BEI Clearance Station, reqd), `item_description` (Data), `returned_qty` (Int, default 0), `required_qty` (Int, default 1), `returned_on` (Date), `returned_to` (Link to Employee), `notes` (Small Text), `status` (Select: Pending/Returned/Waived/Missing, default Pending), `proof_file` (Attach)
- `istable: 1` (child table)

Python controller boilerplate.

   MUST_MODIFY: `hrms/hr/doctype/bei_clearance_item/bei_clearance_item.json`
   MUST_MODIFY: `hrms/hr/doctype/bei_clearance_item/bei_clearance_item.py`

**Task 4.3 — Create `BEI Clearance` parent doctype** (10 units)

New doctype at `hrms/hr/doctype/bei_clearance/bei_clearance.json`:
- Fields: 
  - `employee` (Link to Employee, reqd)
  - `employee_name` (Data, fetch from employee)
  - `separation_request` (Link to Employee Separation, reqd)
  - `relieving_date` (Date, fetch from separation)
  - `status` (Select: Draft/In Progress/Pending Approval/Approved/Released, default Draft)
  - `initiated_on` (Date, default today)
  - `initiated_by` (Link to User, default session user)
  - `approved_on` (Date, read_only)
  - `approved_by` (Link to User, read_only)
  - `items` (Table, BEI Clearance Item — the returned items/sign-offs)
  - `notes` (Small Text)
- `is_submittable: 1` (has submit workflow)
- Naming: `HR-CLR-.YYYY.-.#####`

Python controller with:
- `on_submit`: transition employee `status` to `Left` with `relieving_date` from the separation
- `validate`: ensure all items are in terminal state (Returned/Waived/Missing) before submit
- Hook into `Employee Separation` to auto-create a BEI Clearance on separation approval (or leave this manual for v1)

   MUST_MODIFY: `hrms/hr/doctype/bei_clearance/bei_clearance.json`
   MUST_MODIFY: `hrms/hr/doctype/bei_clearance/bei_clearance.py`
   MUST_CONTAIN: `bei_clearance.py` must contain `on_submit` AND `status = "Left"`

**Task 4.4 — API endpoints for clearance** (5 units)

Create `hrms/api/clearance.py`:
- `@frappe.whitelist() create_clearance(separation_name)` — creates a BEI Clearance for the given separation, auto-populates items from all enabled BEI Clearance Stations
- `@frappe.whitelist() update_clearance_item(clearance_name, item_idx, status, notes=None, proof_file_url=None)` — updates a single item's status
- `@frappe.whitelist() submit_clearance(clearance_name)` — submits the clearance (calls on_submit, which transitions employee to Left)

Every function starts with `set_backend_observability_context()`.

   MUST_MODIFY: `hrms/api/clearance.py`
   MUST_CONTAIN: `@frappe.whitelist()`, `set_backend_observability_context`, `create_clearance`, `submit_clearance`

**Task 4.5 — Frontend clearance page** (8 units)

Update `../bei-tasks/app/clearance/page.tsx` to:
- Read current user's separation from backend
- If separation exists and clearance exists, show the full clearance with stations + items + status controls
- If separation exists but no clearance, show "Initiate Clearance" button → calls `create_clearance` API
- If no separation, show existing stub ("no active clearance")

Minimum UI:
- Header with employee name + relieving date
- List of stations with items grouped by station
- Each item: status badge + Mark Returned / Mark Waived / Mark Missing buttons (for HR role)
- Submit Clearance button at bottom (HR role only, disabled until all items terminal)

   MUST_MODIFY: `../bei-tasks/app/clearance/page.tsx`
   MUST_CONTAIN: `create_clearance`, `submit_clearance`

**Task 4.6 — Make migration file** (2 units)

Frappe new doctypes need a migration: run `bench migrate` target on local dev first to verify the 3 new doctypes install cleanly. Create a deployment note in `output/s170/DEPLOY_NOTES.md` with:
- New doctypes to migrate
- Fixture load command: `bench --site <site> reload-doctype "BEI Clearance Station" && bench load-fixtures`
- Sentry monitoring reminder

   MUST_MODIFY: `output/s170/DEPLOY_NOTES.md`

**Phase 4 verification gate:**

```bash
git diff --name-only origin/production | grep "bei_clearance_station/bei_clearance_station.json" || exit 1
git diff --name-only origin/production | grep "bei_clearance_item/bei_clearance_item.json" || exit 1
git diff --name-only origin/production | grep "bei_clearance/bei_clearance.json" || exit 1
git diff --name-only origin/production | grep "hrms/api/clearance.py" || exit 1
git diff --name-only origin/production | grep "app/clearance/page.tsx" || exit 1

grep -q "on_submit" hrms/hr/doctype/bei_clearance/bei_clearance.py || exit 1
grep -q "status = \"Left\"" hrms/hr/doctype/bei_clearance/bei_clearance.py || exit 1
grep -q "@frappe.whitelist" hrms/api/clearance.py || exit 1
grep -q "set_backend_observability_context" hrms/api/clearance.py || exit 1
```

---

### Phase 5 — Closeout (4 units)

**Task 5.1 — Update plan YAML status** (1 unit)

In this file, change:
- `status: GO` → `status: COMPLETED`
- Add `completed_date: 2026-04-07`
- Add `execution_summary:` block with per-phase unit counts and defects fixed

**Task 5.2 — Update SPRINT_REGISTRY.md** (1 unit)

Change the S170 row's status from `PLANNED` to `COMPLETED` with PR references. `git add -f` because docs/ is gitignored.

**Task 5.3 — Create PRs** (1 unit)

Two PRs (one per repo):
- **hrms PR** against `production` base: Leave Ledger fix + OT backend + Clearance doctypes + clearance API
- **BEI-Tasks PR** against `main` base: Compensation route fix + OT apply page + clearance frontend + nav updates

```bash
GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms --base production --head s170-s166-defect-fixes --title "S170: S166 defect fixes — Leave Ledger + OT backend + Clearance doctypes" --body "..."
GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/BEI-Tasks --base main --head s170-s166-defect-fixes --title "S170: S166 defect fixes — Compensation route + OT apply page + clearance frontend" --body "..."
```

**Task 5.4 — STOP at PR_CREATED** (1 unit)

Per BEI PR-handoff: do NOT merge, do NOT deploy. Share PR numbers with Sam, output a "ready for merge" message, STOP.

**Verification:**
- Plan status = COMPLETED
- SPRINT_REGISTRY.md row = COMPLETED with PR refs
- Both PRs visible on GitHub
- No git operations beyond PR creation

---

## L3 Workflow Scenarios (for S166 retest — NOT for S170 execution)

S170 does NOT run L3. After S170's PRs merge + deploy, the S166 orchestrator dispatches a retest agent that re-runs these scenarios:

| User | Action | Expected Outcome | Defect covered |
|------|--------|-------------------|----------------|
| test.crew1 | File leave via Request Leave dialog → supervisor approves | Leave Ledger Entry row created with `transaction_name=HR-LAP-...`, leaves_taken > 0 | Defect 1 |
| test.hr | Navigate to `/dashboard/hr/payroll/compensation-setup/9000003` | Page renders full compensation detail (sections, fields, Edit button) — NOT empty shell | Defect 2 |
| test.hr | Navigate to `/dashboard/hr/payroll/compensation-setup`, click a row | Modal opens with full detail (NOT just Bio ID) | Defect 2 |
| test.crew1 | Navigate to `/dashboard/hr/overtime/apply`, fill form, submit | BEI Overtime Request created with `overtime_status=Pending`, visible in crew's own OT list | Defect 3 |
| test.hr | Initiate clearance for existing Employee Separation | BEI Clearance created with 8 stations (from fixtures), status=Draft | Defect 4 |
| test.hr | Mark all clearance items terminal, click Submit Clearance | Employee transitions to `status=Left` with `relieving_date` from separation | Defect 4 |

---

## Scope Size Warning

**This plan is 72 units. The 80-unit ceiling is respected, but Phase 4 alone is 35 units — nearly half the total budget.**

Per S089 and operational experience, any single phase above 15 units is at high risk of partial delivery under context exhaustion. Phase 4 is a structural sprint normally scoped on its own.

**Recommended fallback if Phase 4 overruns:**
1. Complete Phases 1-3 in this session (Leave Ledger + Compensation + OT = 33 units)
2. Open a PR covering Phases 1-3 only
3. Create S171 reservation for "Clearance module minimum-viable doctypes"
4. Do NOT silently expand this sprint or skip tasks

Sam approved the "one sprint for all 4 defects" directive (2026-04-07 chat). The agent should attempt Phase 4 but STOP decisively at the 40-unit Phase-4 mark (or when Clearance proves to need work outside this plan's task list) and split to S171.

**Budget tracking:** the agent writes `output/s170/PHASE_BUDGET.json` after each phase. If the running total approaches 70 units with Phase 4 incomplete, that's the stop signal.

---

## Autonomous Execution Contract

- **completion_condition:** all 4 defects fixed OR Phases 1-3 fixed + S171 reservation for Phase 4. Both PRs open (hrms + BEI-Tasks). Plan YAML status=COMPLETED (or IMPLEMENTED_NOT_MERGED with partial scope). SPRINT_REGISTRY.md row updated.
- **stop_only_for:**
  - Leave Ledger root cause cannot be determined in 60 min (Task 1.1 HARD BLOCKER)
  - Phase 4 exceeds 40 units during execution (Scope Size Warning)
  - Production deployment of a dependency is not ready (e.g., fixtures fail to load)
  - Sentry instrumentation rule cannot be satisfied without scope expansion
  - Direct conflict with S166 testing session (shouldn't happen — disjoint file sets)
- **continue_without_pause_through:** diagnostic → implement → verify → PR creation → plan closeout. Do NOT pause for progress-only updates.
- **blocker_policy:**
  - programmatic → fix and continue
  - selector flake in Phase 3 smoke → retry with SELECTORS.json workarounds
  - 3+ failures on same issue → grounded research, then continue OR stop if HARD BLOCKER
  - business-data/policy → pause
- **signoff_authority:** single-owner (Sam). PRs land in Sam's inbox for merge.
- **canonical_closeout_artifacts:**
  - `output/s170/PHASE_BUDGET.json`
  - `output/s170/REQUIREMENTS_REGRESSION_CHECK.md`
  - `output/s170/diagnostics/LEAVE_LEDGER_DIAGNOSIS.md`
  - `output/s170/verification/*.png`
  - `output/s170/DEPLOY_NOTES.md`
  - `docs/plans/2026-04-07-sprint-170-s166-defect-fixes.md` (this file, status=COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (S170 row=COMPLETED)

---

## Verification Script Template

Per S154 machine-verifiable phase gate rule, write `output/s170/verify_all_phases.py` BEFORE starting execution:

```python
#!/usr/bin/env python3
"""S170 phase verification — evidence from filesystem, not agent self-report."""
import subprocess, sys, os

def git_diff_has(pattern):
    r = subprocess.run(["git","diff","--name-only","origin/production"], capture_output=True, text=True)
    return any(pattern in l for l in r.stdout.splitlines())

def file_contains(path, pattern):
    if not os.path.exists(path): return False
    with open(path, encoding="utf-8") as f:
        return pattern in f.read()

checks = {
    # Phase 1
    "P1 Leave Ledger file modified": git_diff_has("leave_application") or git_diff_has("hooks.py"),
    "P1 Backfill script created": git_diff_has("s170_backfill_leave_ledger.py"),
    "P1 Diagnosis written": os.path.exists("output/s170/diagnostics/LEAVE_LEDGER_DIAGNOSIS.md"),

    # Phase 2
    "P2 Compensation [employee] page modified": git_diff_has("compensation-setup/[employee]/page.tsx"),
    "P2 Compensation list page modified": git_diff_has("compensation-setup/page.tsx"),
    "P2 Compensation panel extracted": git_diff_has("compensation-detail-panel.tsx"),
    "P2 Page has default export": file_contains("../bei-tasks/app/dashboard/hr/payroll/compensation-setup/[employee]/page.tsx", "export default function Page"),

    # Phase 3
    "P3 OT apply page created": git_diff_has("overtime/apply/page.tsx"),
    "P3 OT backend endpoint created": git_diff_has("hrms/api/overtime_request.py"),
    "P3 OT backend has Sentry": file_contains("hrms/api/overtime_request.py", "set_backend_observability_context"),
    "P3 OT smoke screenshot exists": os.path.exists("output/s170/verification/ot_apply_smoke.png"),

    # Phase 4 (may be partial or deferred to S171)
    "P4 Clearance Station doctype": git_diff_has("bei_clearance_station"),
    "P4 Clearance Item doctype": git_diff_has("bei_clearance_item"),
    "P4 Clearance parent doctype": git_diff_has("bei_clearance/bei_clearance"),
    "P4 Clearance API": git_diff_has("hrms/api/clearance.py"),
    "P4 Clearance frontend": git_diff_has("app/clearance/page.tsx"),
}

passed = sum(1 for v in checks.values() if v)
total = len(checks)
print(f"\nS170 Verification: {passed}/{total} passed\n")
for name, ok in checks.items():
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

# Phase 4 is allowed to be partial if split to S171 — don't auto-fail
p4_passed = sum(1 for k,v in checks.items() if k.startswith("P4") and v)
if p4_passed < 5 and os.path.exists("output/s170/S171_SPLIT_TRIGGERED.flag"):
    print(f"\nPhase 4 partial ({p4_passed}/5) but S171 split was declared — acceptable")
    sys.exit(0 if passed - (5 - p4_passed) >= total - 5 else 1)

sys.exit(0 if passed == total else 1)
```

The agent runs this after each phase and fixes any FAIL before proceeding.

---

## Related Skills

- `/local-frappe` — test Frappe backend changes locally before PR
- `/deploy-frappe` — DO NOT invoke; Sam handles deploy after merge
- `/fact-check-bei-erp` — verify file paths/line numbers in the Ground Truth Lock section before final commit
- `/playwright-bei-erp` — for the Phase 3 Task 3.5 smoke test

---

## Execution Authority

This sprint is intended for autonomous end-to-end execution BY A DIFFERENT AGENT SESSION than the one running S166. The S166 orchestrator continues Wave 1-Full dispatch while S170 runs. When S170 PRs merge and Sam deploys, the S166 orchestrator dispatches a retest for the affected scenarios.

Do NOT coordinate with the S166 session directly. Communicate via:
- This plan's `output/s170/` artifacts
- PR numbers shared with Sam
- `SPRINT_REGISTRY.md` status updates

Stop ONLY for items in the Autonomous Execution Contract `stop_only_for` section.
