---
sprint_id: S172
display: Sprint 172
title: "S166 Follow-up Defect Fixes — 12-14 OPEN defects after S170 partial deploy + 2026-04-08 audit"
branch: s172-s166-followup-defect-fixes
status: GO
planned_date: 2026-04-08
completed_date: null
depends_on: S166 (catalog + audit), S170 (partial fixes already deployed), audit PR #496
total_work_units: 70
execution_type: product-code-fix-sprint + L3-retest
frontend_pr: null
backend_pr: null
sprint_registry_row: "S172 reserved on 2026-04-08. Branch: s172-s166-followup-defect-fixes. Parent: origin/production (post #497 merge)."
---

# S172: S166 Follow-up Defect Fixes

## Mission

Close the 12-14 product defects still OPEN after S166 + S170 + the 2026-04-08 audit (PR #496). Each defect has been independently verified by either a per-lane audit gate or by orchestrator-direct browser retest. This sprint fixes them, deploys, and re-runs the L3 scenarios that were previously SKIPPED because the underlying UI/backend was broken.

The strict 2026-04-08 audit caught a fabrication: R3's retest summary claimed Defect #6 was CLOSED but the underlying evidence file said `STILL_BROKEN`. PR #496 corrected the registry, PR #497 added the audit-gate rule to `/l3-v2-bei-erp`. S172 now actually fixes the bug.

**Out of scope (any of these = STOP and ask):**
- New product features beyond fixing the 12-14 listed defects
- Refactoring adjacent code that isn't required by a fix
- Re-running S166 scenarios that already PASSED (only retest the ones unblocked by these fixes)
- Any L3 scenario authoring (catalog is frozen)

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

S166 ran 137 L3 scenarios across 8 lanes + 5 retest agents and surfaced 21 defects. S170 (already merged + deployed) attempted to close 7 of them. The 2026-04-08 strict audit (PR #496) caught one fabrication and reclassified Defect #6 from CLOSED → OPEN. Net state after S166 + S170 + audit:

- **3 of 7 S170-targeted defects fully closed:** #2 (Leave Ledger), #4 (Clearance doctypes), #7 (Finance approve/reject)
- **2 partial:** #1 OT filing UI (page deployed but RBAC + attendance prereq block use), #3 Comp [employee] route (page renders but Edit button gated by #21)
- **1 STILL OPEN:** #6 list-page comp modal (R3 lied; orchestrator retest 2026-04-08 confirmed)
- **3 NEW from retest:** #19 (crew RBAC), #20 (OT requires attendance), #21 (Edit chicken-and-egg)
- **11 OPEN pre-existing:** #5 #8 #9 #10 #11 #13 #14 #15 #16 #18 (various severities)

S172 fixes the real product bugs in this list and re-runs the L3 scenarios that those bugs blocked.

### Why one sprint, not multiple

The defects are mostly in two adjacent surface areas (compensation workflow + employee CRUD) and several share root causes:
- **#3, #6, #21** all touch the same `CompensationDetailDialog` / `CompensationDetailPanel` component pair
- **#16** is the backend half of the same compensation workflow
- **#8, #13** are in the employee CRUD path
- **#19** is a 1-line RoleGuard fix
- **#18** is a single doctype field rewire
- **#5, #20** likely become moot once #21+#16 are fixed (Generate Slips probably gates on having salary structures)

Bundling them into one sprint avoids 6-7 micro-PRs and gets one clean L3 retest pass at the end.

### Why this won't fall into the same audit trap

Per PR #497 (the new `/l3-v2-bei-erp` rule), every retest agent in this sprint MUST be paired with an independent audit gate. Phase 8's L3 retest is structured as `runner agent → audit agent (separate session) → orchestrator reads AUDIT_PASSED.flag, NOT the runner's summary`. No retest verdict is accepted without independent evidence-file inspection.

### Known limitations and mitigations

- **Defect #16 root cause is fragile** — `_activate_compensation_change` lives at `payroll_compensation.py:1054` (S172 will need to inspect lines 1054-1100 to find the try/except). The R5 audit (S166) reported the swallow at lines 633-639 — that may have been line numbers from an earlier file version. The execution agent must grep for `_activate_compensation_change` and read the actual function body before assuming line numbers.
- **Defect #19 RBAC gap** — `/dashboard/hr/overtime/apply` RoleGuard already includes `STORE_STAFF`, `STORE_SUPERVISOR`, `AREA_SUPERVISOR`, `HR_USER`, `HR_MANAGER`, `HQ_FINANCE`, `SYSTEM_MANAGER` (lines 241-248). It does NOT include a `CREW` role — if there is one in `lib/roles.ts`. The execution agent MUST inspect `lib/roles.ts` to verify the actual role mapping for `test.crew1@bebang.ph` before deciding whether to (a) add CREW to the RoleGuard, (b) verify test.crew1's actual role is one of the existing ones (and the bug is something else), or (c) discover the role-name mismatch.
- **Defect #13 emergency_phone_number** — backend `enrichment.py` and `onboarding.py` both whitelist this field. Lane A2's audit verified it was submitted via the EmployeeDetailDialog Personal section but post-save GET returned null. Root cause is likely in the form's payload mapping (frontend) OR in a Frappe save handler that drops the field. Execution agent must add a print/log + retry to find the drop.

### Source references

- **Audit findings (proves what's broken):** `output/l3/s166/AUDIT_2026-04-08/AUDIT_FINDINGS_FINAL.md`
- **Defect #6 visual proof:** `output/l3/s166/AUDIT_2026-04-08/EMP-UX-004-retest/04_dialog_only.png`
- **Defect #6 retest result:** `output/l3/s166/AUDIT_2026-04-08/EMP-UX-004-retest/RETEST_RESULT.json`
- **Canonical defect registry:** `output/l3/s166/DEFECTS.csv` (post-audit corrected)
- **Final S166 summary:** `output/l3/s166/SUMMARY.md` (post-audit corrected)
- **R5 probe (root-causes #21+#22):** `output/l3/s166/lanes/retest/r5_probe/R5_PROBE_SUMMARY.md`
- **Lane D OT diagnostic (#1+#19+#20):** `output/l3/s166/lanes/lane_d/OT_DIAGNOSTIC.md`
- **Lane A4 source-verified #16:** `output/l3/s166/lanes/lane_a/PHASE_A4_SUMMARY.md`
- **S166 plan:** `docs/plans/2026-04-06-sprint-166-l3-employee-lifecycle-scenarios.md`
- **S170 plan:** `docs/plans/2026-04-07-sprint-170-s166-defect-fixes.md`
- **`/l3-v2-bei-erp` skill (audit gate rule):** `.claude/skills/l3-v2-bei-erp/SKILL.md` (post #497 merge)

---

## Ground Truth Lock

### Verified file paths and line numbers (cold-start ready)

| Defect | Source | Line / Element |
|---|---|---|
| #6 + #21 frontend | `../bei-tasks/components/hr/compensation-detail-panel.tsx` | line 165: `<Button onClick={onEditClick} disabled={!detail}>` |
| #6 + #21 frontend | `../bei-tasks/components/hr/compensation-detail-dialog.tsx` | (per R5 probe, has same `disabled={!detail}` pattern around line 296 — verify at execution time) |
| #21 backend | `hrms/api/payroll_compensation.py` | line 318: `def get_employee_compensation_detail(employee):` — returns null/exception when employee has no SSA |
| #16 backend | `hrms/api/payroll_compensation.py` | line 1054: `def _activate_compensation_change(doc):` — contains the try/except that swallows errors (R5 reported lines 633-639 in an older view; execution agent must read lines 1054-1100 for the actual try/except) |
| #19 frontend | `../bei-tasks/app/dashboard/hr/overtime/apply/page.tsx` | line 23: `import { RoleGuard }`. Lines 239-248: RoleGuard with `[ROLES.EMPLOYEE, STORE_STAFF, STORE_SUPERVISOR, AREA_SUPERVISOR, HR_USER, HR_MANAGER, HQ_FINANCE, SYSTEM_MANAGER]` — investigate why test.crew1 hits "Access Restricted" despite STORE_STAFF being in the list. Possibly test.crew1's actual role is `EMPLOYEE` (line 241 already includes it) — so the bug is not the RoleGuard but something else (maybe the page's middleware OR `lib/roles.ts` mapping). |
| #19 RBAC source | `../bei-tasks/lib/roles.ts` | grep for `EMPLOYEE`, `STORE_STAFF`, `CREW` — confirm test.crew1's role assignment |
| #18 doctype | `hrms/hr/doctype/bei_incident_report/bei_incident_report.json` | field `store` has `fieldtype: Link, options: Warehouse, reqd: 0`. UI passes a Branch name like "ARANETA GATEWAY" → 417 LinkValidationError. Fix: change `options` to `Branch` OR rename field to `warehouse` and rewire UI. |
| #8 backend | `hrms/api/employee_create.py` | line 87: `def create_employee_direct(...)`. Returns dict (line 57 area). Verified by Lane B+C: returns cached `employee_id="BEI-EMP-2026-00004"` for every call. Check the dict construction in the return statement around line 222-231 — the `employee_id` may be hardcoded or refer to a cached variable instead of `generate_bei_employee_id()` result. |
| #13 backend | `hrms/api/enrichment.py` | line 25: `"emergency_phone_number"` in field whitelist. line 282: in PHONE_FIELDS. line 795: in another field list. Search the EmployeeDetailDialog frontend save handler for whether emergency_phone_number is in the payload it sends. |

### Canonical defect list with severities (audit-corrected)

Source: `output/l3/s166/DEFECTS.csv` post 2026-04-08 audit.

| # | Severity | Status | Title |
|---|---|---|---|
| 1 | CRITICAL | PARTIALLY_FIXED | OT filing UI deployed but blocked by #19 + #20 |
| 5 | HIGH | UNTESTED | Generate Slips button disabled on payroll processing |
| 6 | CRITICAL | OPEN (NEW from audit) | List-page compensation modal STILL EMPTY (R3 fabrication caught) |
| 8 | HIGH | OPEN | create_employee_direct cached employee_id constant |
| 9 | MEDIUM | OPEN | test.hr proxy permission gap on /api/frappe/api/resource/Employee |
| 10 | LOW (DISPUTED) | OPEN | employee-master dashboard vs list (Wave 0 disagrees) |
| 11 | LOW | OPEN | Soft-delete order dependency: relieving_date before status |
| 13 | MEDIUM | OPEN | emergency_phone_number silently dropped on Employee save |
| 14 | MEDIUM | OPEN | Reports To field has no autocomplete |
| 15 | LOW | OPEN | First-of-session BSCR silently rolled back |
| 16 | HIGH | UNVERIFIED → OPEN | _activate_compensation_change silent failure (R4 couldn't reach due to #21) |
| 18 | HIGH | OPEN | BEI Incident Report.store Link Warehouse but UI passes Branch name |
| 19 | HIGH | OPEN (NEW from retest) | /dashboard/hr/overtime/apply RoleGuard excludes crew |
| 20 | MEDIUM | OPEN (NEW from retest) | OT filing API requires pre-existing Attendance record |
| 21 | HIGH | OPEN (NEW from retest) | Comp Edit button gated on existing SSA — chicken-and-egg |

(Defects #2, #3, #4, #7 already CLOSED by S170. Defects #12, #22, #23 reclassified as test-harness bugs / meta — not real product defects.)

---

## Requirements Regression Checklist (Cold-Start Verification)

Before writing any code, verify your approach against every item:

- [ ] Have I read `output/l3/s166/AUDIT_2026-04-08/AUDIT_FINDINGS_FINAL.md` (the audit that triggered this sprint)?
- [ ] Have I read `output/l3/s166/lanes/retest/r5_probe/R5_PROBE_SUMMARY.md` (the source-grounded root-cause analysis for #21 + #22)?
- [ ] Am I fixing #6 and #21 with ONE shared root-cause fix (CompensationDetailPanel `disabled={!detail}` + backend stub) rather than two separate hacks?
- [ ] **HARD BLOCKER for #16:** Did I actually `Read` `hrms/api/payroll_compensation.py` lines 1054-1100 to find the real try/except, instead of trusting the audit's older line number reference (633-639)?
- [ ] **HARD BLOCKER for #19:** Did I check `../bei-tasks/lib/roles.ts` for test.crew1's actual role assignment BEFORE assuming the RoleGuard needs a CREW role added?
- [ ] **HARD BLOCKER for #18:** Did I confirm whether the right fix is (a) change `store` field options from Warehouse to Branch, OR (b) rename the field to `warehouse` and rewire the UI? Pick ONE approach with rationale.
- [ ] Am I creating a backfill/correction script for any data that was wrongly stored due to these defects (e.g., compensation changes that reached "Approved" but never created an SSA per #16)?
- [ ] Sentry instrumentation: does every new/modified `@frappe.whitelist()` endpoint call `set_backend_observability_context()`?
- [ ] Branch compliance: am I on `s172-s166-followup-defect-fixes` (created from `origin/production`)?
- [ ] PR-handoff: am I creating PRs and stopping at PR_CREATED, NOT merging or deploying?
- [ ] **Audit gate for retest (Phase 8):** am I dispatching an INDEPENDENT audit agent for each retest scenario, per the post-PR-#497 `/l3-v2-bei-erp` rule?

---

## Phase Budget Contract

| Phase | Units | Description |
|---|---|---|
| Phase 0 | 2 | Branch + preconditions + read audit findings |
| Phase 1 | 12 | Defect #6 + #21 — Compensation Edit + list-modal (shared root cause) |
| Phase 2 | 6 | Defect #16 — `_activate_compensation_change` silent failure |
| Phase 3 | 4 | Defect #19 — `/overtime/apply` crew RBAC investigation + fix |
| Phase 4 | 8 | Defect #18 — BEI Incident Report Warehouse→Branch rewire |
| Phase 5 | 6 | Defect #8 — `create_employee_direct` cached employee_id |
| Phase 6 | 5 | Defect #13 — emergency_phone_number drop |
| Phase 7 | 8 | Defects #5 #9 #11 #14 #15 #20 (smaller defects + docs) |
| Phase 8 | 15 | L3 retest of unblocked S166 SKIP scenarios + per-agent audit gate |
| Phase 9 | 4 | Closeout (plan + registry + final PR) |
| **Total** | **70** | Within 80-unit ceiling. No phase exceeds 15. |

---

## Agent Boot Sequence

1. **Read this plan fully.** Every phase. Every HARD BLOCKER.
2. **Read the Requirements Regression Checklist above.** Write your approach for each item to `output/s171/REQUIREMENTS_REGRESSION_CHECK.md`.
3. **Create sprint branch:** `git fetch origin production && git checkout -b s172-s166-followup-defect-fixes origin/production`. Same in bei-tasks: `cd ../bei-tasks && git fetch origin main && git checkout -b s172-s166-followup-defect-fixes origin/main`. NEVER write code on production/main.
4. **Read the audit findings:** `output/l3/s166/AUDIT_2026-04-08/AUDIT_FINDINGS_FINAL.md`
5. **Read R5 probe (root causes for #21):** `output/l3/s166/lanes/retest/r5_probe/R5_PROBE_SUMMARY.md`
6. **Read Lane D OT diagnostic (root causes for #1+#19+#20):** `output/l3/s166/lanes/lane_d/OT_DIAGNOSTIC.md`
7. **Read Lane A4 summary (source-verified #16):** `output/l3/s166/lanes/lane_a/PHASE_A4_SUMMARY.md`
8. **Read post-#497 audit-gate rule:** `.claude/skills/l3-v2-bei-erp/SKILL.md` — search for "Audit Gate on EVERY Verdict-Producing Agent"
9. **Read `.claude/rules/sentry-observability.md`** for DM-7 Sentry instrumentation pattern
10. **NOW start Phase 0.**

---

## Phases

### Phase 0 — Preconditions + branch setup (2 units)

1. Create branches in both repos from current `origin/production` / `origin/main`
2. Create artifact dir: `mkdir -p output/s171/{diagnostics,verification,retest,evidence}`
3. Write `output/s171/REQUIREMENTS_REGRESSION_CHECK.md` with one entry per checklist item
4. Write `output/s171/PHASE_BUDGET.json` with estimated vs actual unit tracking
5. Verify no L3 test pollution exists on production: query `Employee` filtered by `employee_name LIKE '%(L3 2026-04-%' AND status='Active'` — should return empty. If non-zero, escalate to Sam before any new test work.

**Verification:**
- Both repos on `s172-s166-followup-defect-fixes` branch
- `output/s171/REQUIREMENTS_REGRESSION_CHECK.md` exists with 11 items filled
- Production L3 pollution check returns 0

---

### Phase 1 — Defect #6 + #21 — Compensation Edit + list-modal (shared root cause) (12 units)

**Defects:**
- **#6** [CRITICAL] List-page compensation modal opens with only Bio ID (no fields). Visually confirmed by audit 2026-04-08 retest (`output/l3/s166/AUDIT_2026-04-08/EMP-UX-004-retest/04_dialog_only.png`).
- **#21** [HIGH] Edit button on `/dashboard/hr/payroll/compensation-setup/[employee]` is permanently disabled when employee has no SSA (chicken-and-egg).

**Root cause (R5 source-grounded):**
- Backend: `hrms/api/payroll_compensation.py:318 get_employee_compensation_detail(employee)` returns null/raises when employee has no Salary Structure Assignment.
- Frontend: `../bei-tasks/components/hr/compensation-detail-panel.tsx:165` has `<Button onClick={onEditClick} disabled={!detail}>` — when `detail` is undefined (no SSA), Edit is permanently disabled.
- Sister: `../bei-tasks/components/hr/compensation-detail-dialog.tsx` has the same pattern (R5 noted approx line 296 — verify at execution).

**Task 1.1 — Backend fix: return employee stub when no SSA exists** (3 units)

Modify `get_employee_compensation_detail` at `hrms/api/payroll_compensation.py:318`:
- Read the current implementation
- Find where it returns null / raises when no SSA
- Change to return an employee stub: `{employee, employee_name, has_ssa: false, base_salary: 0, allowances: [], deductions: [], statutory: {...defaults}}`
- Add `set_backend_observability_context(module="payroll", action="get_employee_compensation_detail", mutation_type="read")` at the top
- Preserve the existing happy path (with SSA) unchanged

   MUST_MODIFY: `hrms/api/payroll_compensation.py`
   MUST_CONTAIN: `has_ssa` AND `set_backend_observability_context`

**Task 1.2 — Frontend fix: enable Edit button when no SSA** (3 units)

In `../bei-tasks/components/hr/compensation-detail-panel.tsx:165`:
- Change `disabled={!detail}` → `disabled={isLoading}` (or whatever loading state variable is used)
- Verify `startEditing()` already null-guards all field reads with `|| 0` fallbacks (R5 confirmed it does)
- The Edit button must be enabled for new employees with no SSA so HR can set up the first salary

   MUST_MODIFY: `../bei-tasks/components/hr/compensation-detail-panel.tsx`
   MUST_CONTAIN: `disabled={isLoading}` (or equivalent)

**Task 1.3 — Frontend fix: same in CompensationDetailDialog** (2 units)

Locate `../bei-tasks/components/hr/compensation-detail-dialog.tsx` (the file used by the LIST page row click). Apply the same `disabled={!detail}` → `disabled={isLoading}` fix. Also verify the dialog actually reads the new backend stub correctly and renders the form fields (rather than the empty skeleton placeholders shown in the audit screenshot).

   MUST_MODIFY: `../bei-tasks/components/hr/compensation-detail-dialog.tsx`
   MUST_CONTAIN: `disabled={isLoading}` AND form fields rendering when `has_ssa: false`

**Task 1.4 — Sentry instrumentation** (1 unit)

Confirm Sentry context is set in the new `get_employee_compensation_detail` path AND in any other modified `@frappe.whitelist()` endpoint touched.

**Task 1.5 — Local L1 + L2 verify** (2 units)

Use `/local-frappe` to test the backend change locally. Use Playwright headless to load the list page in dev mode and click a real employee row — verify the modal opens with a form, not an empty skeleton.

   Verification screenshot: `output/s171/verification/phase1_modal_with_form.png`

**Task 1.6 — Phase 1 verification gate** (1 unit)

```bash
git diff --name-only origin/production | grep -E "payroll_compensation\.py" || exit 1
git diff --name-only origin/main | grep -E "compensation-detail-panel\.tsx" || exit 1
git diff --name-only origin/main | grep -E "compensation-detail-dialog\.tsx" || exit 1
grep -q "has_ssa" hrms/api/payroll_compensation.py || exit 1
grep -q "disabled={isLoading}" ../bei-tasks/components/hr/compensation-detail-panel.tsx || exit 1
test -f output/s171/verification/phase1_modal_with_form.png || exit 1
```

---

### Phase 2 — Defect #16 — `_activate_compensation_change` silent failure (6 units)

**Defect:** [HIGH] BCC reaches "Approved" status (both HR + Finance approve via the dual-control queue) but the corresponding Salary Structure Assignment is silently NOT created. Lane A audit verified this on production: `tabSalary Structure Assignment WHERE employee=HR-EMP-00032` returned 0 rows despite BCC-2026-00020 being Approved with Salary 30000.

**Root cause (Lane A4 audit source-verified):**
- `hrms/api/payroll_compensation.py:1054 def _activate_compensation_change(doc):` contains a try/except that catches all exceptions, calls `frappe.log_error(...)`, rolls back the savepoint, but the OUTER caller still receives `{"status": "success"}`. Classic corrupt-success.

**Task 2.1 — Read the actual function body** (1 unit)

**HARD BLOCKER:** Read `hrms/api/payroll_compensation.py` lines 1054-1150 (or wider) to find the try/except. The audit reported lines 633-639 from an earlier file version — line numbers in the current file may differ. Confirm the exact lines BEFORE editing.

   MUST_READ: `hrms/api/payroll_compensation.py:1054-1150`

**Task 2.2 — Replace broad try/except with specific handling** (2 units)

Refactor the swallowing try/except so that:
- Specific expected exceptions (e.g., `frappe.ValidationError` from a known validation) are caught and logged with a clear error message returned to the caller
- Unexpected exceptions are NOT swallowed — they propagate up so the caller's `success` claim becomes a failure
- The savepoint rollback still happens, but the caller is informed

Add `set_backend_observability_context(module="payroll", action="_activate_compensation_change", mutation_type="create")` at the function entry.

   MUST_MODIFY: `hrms/api/payroll_compensation.py`
   MUST_CONTAIN: explicit exception handling that does NOT silently return success on failure

**Task 2.3 — Backfill script for stranded BCCs** (2 units)

Write `scripts/s171_backfill_stranded_bccs.py` (Frappe-executable, mirrors the S170 backfill pattern):

```python
"""
S172 — Backfill SSAs for BCCs that reached Approved without creating an SSA.
Caused by Defect #16 silent activation failure.
"""
# Find BCCs in Approved state where no corresponding SSA exists for the employee
# For each, attempt to call the (now-fixed) _activate_compensation_change
# Log results to output/s171/backfilled_bccs.csv
```

Run via SSM following the `/frappe-bulk-edits` skill pattern (init boilerplate + base64 + docker exec).

   MUST_MODIFY: `scripts/s171_backfill_stranded_bccs.py`
   MUST_CONTAIN: `_activate_compensation_change`

**Task 2.4 — Phase 2 verification gate** (1 unit)

```bash
git diff --name-only origin/production | grep "payroll_compensation\.py" || exit 1
git diff --name-only origin/production | grep "s171_backfill_stranded_bccs\.py" || exit 1
grep -q "set_backend_observability_context" hrms/api/payroll_compensation.py || exit 1
# Confirm the broad try/except is gone (should not have a bare except: that returns success)
```

---

### Phase 3 — Defect #19 — `/overtime/apply` crew RBAC (4 units)

**Defect:** [HIGH] test.crew1 navigating to `/dashboard/hr/overtime/apply` gets "Access Restricted". The page is the self-service OT filing form deployed by S170 Phase 3.

**HARD BLOCKER for diagnosis:**
The current RoleGuard at `../bei-tasks/app/dashboard/hr/overtime/apply/page.tsx` lines 239-248 already includes `EMPLOYEE`, `STORE_STAFF`, `STORE_SUPERVISOR`, `AREA_SUPERVISOR`, `HR_USER`, `HR_MANAGER`, `HQ_FINANCE`, `SYSTEM_MANAGER`. If test.crew1's role IS one of those (likely STORE_STAFF or EMPLOYEE), the bug is somewhere ELSE — not the RoleGuard. Possibilities:
- Middleware in `../bei-tasks/middleware.ts` blocks the route before the page renders
- `lib/roles.ts` has a stale role mapping
- The page uses a different access check below the RoleGuard

**Task 3.1 — Diagnose actual blocker** (1 unit)

1. Read `../bei-tasks/lib/roles.ts` and find how `test.crew1@bebang.ph` (or the BEI "crew" Frappe role) maps to the bei-tasks role enum
2. Read `../bei-tasks/middleware.ts` (if exists) and check for any route-specific gating
3. Read the full `app/dashboard/hr/overtime/apply/page.tsx` body for any additional permission checks below the RoleGuard
4. Write findings to `output/s171/diagnostics/DEFECT_19_DIAGNOSIS.md`

**Task 3.2 — Apply the correct fix** (2 units)

Based on the diagnosis:
- **If RoleGuard is missing the actual crew role:** add it to lines 239-248
- **If middleware blocks the route:** update the middleware allowlist
- **If `lib/roles.ts` has wrong mapping:** fix the mapping
- **If a separate access check is wrong:** fix it

Whatever the fix is, it must result in test.crew1 successfully loading the OT apply form.

   MUST_MODIFY: at least one of `../bei-tasks/app/dashboard/hr/overtime/apply/page.tsx`, `../bei-tasks/middleware.ts`, `../bei-tasks/lib/roles.ts`

**Task 3.3 — Phase 3 verification gate** (1 unit)

```bash
test -f output/s171/diagnostics/DEFECT_19_DIAGNOSIS.md || exit 1
# After local rebuild, the OT apply page must render the form (not Access Restricted) when logged in as test.crew1
# Verified via headless Playwright in Phase 8 retest
```

---

### Phase 4 — Defect #18 — BEI Incident Report Warehouse→Branch rewire (8 units)

**Defect:** [HIGH] `BEI Incident Report.store` is `Link Warehouse` (verified via doctype JSON inspection during 2026-04-08 audit). The disciplinary form UI at `/dashboard/hr/disciplinary/[id]` passes a Branch name like "ARANETA GATEWAY" → backend returns 417 `LinkValidationError: Could not find Store: ARANETA GATEWAY` (Lane A5b audit verified). Blocks all 4 EMP-DISCIPLINARY-001..004 scenarios.

**Two valid fix options — pick ONE with rationale:**

**Option A — Change field options from Warehouse to Branch (preserve field name `store`)**
- Pros: smaller change, no UI rewire, no field rename migration
- Cons: confusing — field is named `store` but stores a Branch reference. May break any existing reports/dashboards that JOIN to Warehouse

**Option B — Rename field from `store` to `warehouse` AND rewire UI to pass an actual Warehouse name**
- Pros: field name matches its semantic meaning
- Cons: doctype rename migration required, UI components must be updated, any SQL referencing `store` breaks

**HARD BLOCKER:** The execution agent MUST grep for `bei_incident_report.store` and `incident_report.store` across hrms/, bei-tasks/, scripts/ to find every consumer of this field BEFORE picking an option. If there are <5 references, Option A is fine. If there are many references and most expect a Branch, Option A is correct. If most reference Warehouse semantics, Option B.

**Task 4.1 — Inventory existing references** (2 units)

```bash
grep -rn "bei_incident_report.*store\|incident_report.*store\|BEI Incident Report.*store" hrms/ bei-tasks/ scripts/ 2>&1 | tee output/s171/diagnostics/DEFECT_18_REFERENCE_INVENTORY.md
```

Decide A vs B based on the inventory.

**Task 4.2 — Apply the chosen fix** (4 units)

If Option A: edit the doctype JSON, change `options: Warehouse` → `options: Branch`. Run `bench migrate` locally to test.

If Option B: rename the field via Frappe migration, update all UI/API references, update fixtures.

Document the decision and reasoning in `output/s171/diagnostics/DEFECT_18_DECISION.md`.

   MUST_MODIFY: `hrms/hr/doctype/bei_incident_report/bei_incident_report.json` (at minimum)

**Task 4.3 — Local migration test** (1 unit)

Use `/local-frappe` to run the migration locally. Verify creating a BEI Incident Report with the disciplinary form's branch value (e.g., "ARANETA GATEWAY") now succeeds.

**Task 4.4 — Phase 4 verification gate** (1 unit)

```bash
git diff --name-only origin/production | grep "bei_incident_report\.json" || exit 1
test -f output/s171/diagnostics/DEFECT_18_DECISION.md || exit 1
test -f output/s171/diagnostics/DEFECT_18_REFERENCE_INVENTORY.md || exit 1
```

---

### Phase 5 — Defect #8 — `create_employee_direct` cached employee_id (6 units)

**Defect:** [HIGH] `create_employee_direct` returns the same `employee_id="BEI-EMP-2026-00004"` for every CREATE call. Verified by Lane B + Lane C across multiple distinct creates with different bio_ids (9001891/92/93/94/95).

**Source location:** `hrms/api/employee_create.py:87 def create_employee_direct(...)`. Returns dict around line 222-231. Likely a cached/hardcoded `employee_id` or a stale variable reference instead of `generate_bei_employee_id()` result.

**Task 5.1 — Read the function body** (1 unit)

Read `hrms/api/employee_create.py` lines 87-250. Find where `employee_id` is generated and where it's returned. Identify the cache/staleness.

**Task 5.2 — Fix the return shape** (2 units)

Ensure `employee_id` in the return dict is the freshly-generated value from `generate_bei_employee_id()`, not a cached or stale variable. Also include the Frappe `name` (HR-EMP-NNNNN) in the return so callers can lookup the employee without needing a separate query.

Add Sentry context if not present.

   MUST_MODIFY: `hrms/api/employee_create.py`
   MUST_CONTAIN: explicit `employee_id` AND `name` keys in return dict

**Task 5.3 — Local L1 test** (2 units)

Use `/local-frappe` to call `create_employee_direct` twice in sequence with different inputs. Verify the two calls return distinct `employee_id` values.

   Verification log: `output/s171/verification/defect_8_dual_create_log.txt`

**Task 5.4 — Phase 5 verification gate** (1 unit)

```bash
git diff --name-only origin/production | grep "employee_create\.py" || exit 1
test -f output/s171/verification/defect_8_dual_create_log.txt || exit 1
```

---

### Phase 6 — Defect #13 — emergency_phone_number drop (5 units)

**Defect:** [MEDIUM] EMP-EDIT-CONTACT-002: submitted `person_to_be_contacted: "Maria Dela Cruz"`, `relation: "Spouse"`, `emergency_phone_number: "09181112222"` via the EmployeeDetailDialog Personal section. Post-save GET returned `person_to_be_contacted: "Maria Dela Cruz"` ✓, `relation: "Spouse"` ✓, but `emergency_phone_number: null`. Lane A2 + audit live-verified.

**Task 6.1 — Find the form's payload mapping** (2 units)

Search bei-tasks for the EmployeeDetailDialog Personal section save handler:
```bash
grep -rn "person_to_be_contacted\|emergency_phone_number" ../bei-tasks/components/hr/ ../bei-tasks/app/api/ 2>&1
```

Find the save handler / API route. Check whether `emergency_phone_number` is in the payload it sends.

If absent: add it to the payload.
If present: the bug is in the backend save handler — check `hrms/api/employee_master.py` or wherever Employee saves are processed for an explicit field whitelist that's missing `emergency_phone_number`.

**Task 6.2 — Apply the fix** (2 units)

Add the missing field to whichever layer dropped it (frontend payload OR backend whitelist).

   MUST_MODIFY: at least one file containing `emergency_phone_number`
   MUST_CONTAIN: the new code path that includes the field

**Task 6.3 — Phase 6 verification gate** (1 unit)

```bash
git diff --name-only origin/production | grep -E "(employee|hr)" | xargs grep -l "emergency_phone_number" 2>/dev/null || exit 1
```

---

### Phase 7 — Smaller defects bundled (8 units)

| Defect | Severity | Fix |
|---|---|---|
| **#5** Generate Slips disabled | HIGH | Likely auto-fixes when #21+#16 are fixed (button gates on having salary structures in place). Phase 8 retest will confirm. If still disabled, investigate the gate condition in `../bei-tasks/app/dashboard/hr/payroll/processing/page.tsx`. Document either way in `output/s171/diagnostics/DEFECT_5_STATUS.md`. (2 units) |
| **#9** test.hr proxy 403 | MEDIUM | Add `Employee` doctype to the my.bebang.ph proxy permission allowlist for `test.hr` role. Find the proxy auth config in `../bei-tasks/app/api/frappe/[...path]/route.ts` or similar. (2 units) |
| **#11** Soft-delete order dependency | LOW | Add a docs note in `data/04_Project_Management/Import_Log/CONTEXT.md` documenting the 2-pass PUT pattern (relieving_date first, then status=Left). Also add a helper function in `hrms/api/employee_master.py` if one doesn't exist. (1 unit) |
| **#14** Reports To no autocomplete | MEDIUM | Replace plain text input with a shadcn combobox bound to the Frappe `User` Link field. Find the EmployeeDetailDialog Employment section. (2 units) |
| **#15** First-of-session BSCR rolled back | LOW | Investigate the rollback path in `hrms/api/payroll_compensation.py submit_sensitive_change_request`. Likely a missing `frappe.db.commit()` after the first call in a session. (1 unit) |
| **#20** OT requires attendance | MEDIUM | NOT a code fix — document as expected behavior in `data/04_Project_Management/Import_Log/CONTEXT.md` AND add a clearer error message to `hrms/api/overtime_request.py` line 94 (already says "Overtime can only be filed for days you actually worked" — confirm acceptable). (1 unit — minimal) |

   MUST_MODIFY: at least 4 files across the bundle

**Phase 7 verification gate:**
```bash
test -f output/s171/diagnostics/DEFECT_5_STATUS.md || exit 1
git diff --name-only origin/production origin/main | grep -cE "(\.py|\.tsx|\.ts|\.md)" | awk '{if ($1 < 4) exit 1}'
```

---

### Phase 8 — L3 Retest of unblocked S166 SKIP scenarios (15 units)

**Per the post-#497 audit-gate rule, every retest agent must be paired with an INDEPENDENT audit gate.** No exceptions.

**Scope: scenarios from S166 that should now pass post-S172 deploy.**

| Defect closed | S166 scenarios unblocked |
|---|---|
| #6 | EMP-UX-004 (R3 retest) — list-page modal opens with full content |
| #21 + #16 | EMP-SALARY-SETUP-001..004, EMP-SALARY-CHANGE-001..006, EMP-SALARY-PAYROLL-001/002 (12 scenarios — Lane A SALARY chain) |
| #19 | EMP-OVERTIME-001/002/003 (3 scenarios — Lane D OT chain) |
| #18 | EMP-DISCIPLINARY-001/002/003/004 (4 scenarios — Lane A5b chain) |
| #5 | EMP-PAYROLL-RUN-001/002/003 (3 scenarios — Lane G chain) |
| #13 | EMP-EDIT-CONTACT-002 (1 scenario — Lane A2 fix verification) |

Total retest scope: ~25 scenarios.

**HARD GATE — wait for deploy:** Phase 8 cannot start until ALL Phase 1-7 PRs are MERGED and DEPLOYED. The execution agent stops at end of Phase 7, opens PRs (Phase 9 closeout), and waits for Sam's deploy signal before running Phase 8.

**Task 8.1 — Dispatch retest runner agent** (5 units)

After Sam confirms S172 is deployed, dispatch a fresh subagent (NOT the orchestrator session) with this brief:

> Re-run the ~25 unblocked scenarios listed in `docs/plans/2026-04-08-sprint-172-s166-followup-defect-fixes.md` Phase 8. Use real browser via Playwright headless. Use proven patterns from `scripts/testing/l3_s166_lane_a_phase2_runner.mjs`. For each scenario, write evidence to `output/s171/retest/{lane}/evidence/{scenario_id}-retest.json` with `actions: [...]`, `screenshots`, `network: [...]`. Cleanup any test data created in finally via `/frappe-bulk-edits`. STOP after writing files. Do NOT touch git. Do NOT mark scenarios PASS without browser proof.

Required scenario IDs: list all 25 explicitly in the brief.

**Task 8.2 — Dispatch INDEPENDENT audit gate agent** (5 units)

After the runner reports back, dispatch a SEPARATE fresh subagent (different model/context) as the audit gate:

> Audit `output/s171/retest/` evidence files. For each scenario, verify (a) screenshot exists and is non-zero bytes, (b) actions array shows real Playwright UI interactions, (c) status field cross-checks against runner summary. Flag any SUMMARY_LIED discrepancy per the post-#497 `/l3-v2-bei-erp` rule. Write `output/s171/retest/AUDIT_REPORT.md` with verdict per scenario and overall PASS/REJECT.

If the audit rejects any scenario, dispatch a fix-only agent (3-iteration budget per scenario, per the v3 plan rule).

**Task 8.3 — Update DEFECTS.csv with retest results** (3 units)

For each defect that the retest verified CLOSED:
- Update `output/l3/s166/DEFECTS.csv` row to `CLOSED (S172 verified)` with evidence pointer
- Note: `DEFECTS.csv` is the canonical S166 registry — write the S172 retest verification INTO that file as the audit trail

**Task 8.4 — Phase 8 verification gate** (2 units)

```bash
test -f output/s171/retest/AUDIT_REPORT.md || exit 1
test -f output/l3/s166/DEFECTS.csv || exit 1
# Confirm at least 20 of 25 scenarios reclassified to CLOSED (allow 5 partial / new defects)
```

---

### Phase 9 — Closeout (4 units)

**Task 9.1 — Update plan YAML status** (1 unit)

In this file:
- `status: GO` → `status: COMPLETED`
- Add `completed_date: <ISO PHT>`
- Add `execution_summary:` with per-phase unit counts, defects fixed, retest counts
- Add `frontend_pr` and `backend_pr` numbers

**Task 9.2 — Update SPRINT_REGISTRY.md** (1 unit)

Change S172 row status PLANNED → COMPLETED with date + PR refs. `git add -f` since `docs/` is gitignored.

**Task 9.3 — Create PRs** (1 unit)

Two PRs (one per repo):
```bash
GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms --base production --head s172-s166-followup-defect-fixes --title "S172: S166 follow-up defect fixes (Phases 1-7 + retest)"  --body "..."
GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/BEI-Tasks --base main --head s172-s166-followup-defect-fixes --title "S172: S166 follow-up defect fixes (frontend half)" --body "..."
```

PR description must include the per-phase task checklist with status per Zero-Skip Enforcement rule.

**Task 9.4 — STOP at PR_CREATED** (1 unit)

Do NOT merge. Do NOT deploy. Share PR numbers with Sam and STOP. Sam handles merge + deploy + Phase 8 dispatch.

---

## L3 Workflow Scenarios

For Phase 8 retest. These are the concrete scenarios the L3 retest agent must run via real browser:

| User | Action | Expected Outcome | Failure Means |
|---|---|---|---|
| test.hr | Navigate `/dashboard/hr/payroll/compensation-setup` → click ABALLAR JERRY F. row | Modal opens with full salary structure detail (statutory + earnings + deductions sections), NOT empty skeleton with just bio ID | Defect #6 not actually fixed |
| test.hr | Navigate `/dashboard/hr/payroll/compensation-setup/9000003` → click Edit button | Edit form opens with all fields editable; button is NOT disabled even though employee may have no SSA | Defect #21 not actually fixed |
| test.hr | Create a fresh test employee → set up salary 25000 → Finance approves → query SSA via API | New SSA row exists with `employee=<HR-EMP>` and `base=25000` | Defect #16 still silent failure |
| test.crew1 | Navigate `/dashboard/hr/overtime/apply` | OT filing form renders (NOT "Access Restricted") | Defect #19 not actually fixed |
| test.hr | Create disciplinary case via `/dashboard/hr/disciplinary` New Case button → fill employee + violation + branch=ARANETA GATEWAY → Submit | Case created successfully (no LinkValidationError) | Defect #18 not actually fixed |
| test.hr | Navigate `/dashboard/hr/payroll/processing` → click Generate Slips for current period | Button is enabled and clicking produces salary slips | Defect #5 not auto-fixed |
| test.hr | Edit any employee's emergency contact via EmployeeDetailDialog → set phone "09181112222" → Save → API GET | `emergency_phone_number` returns "09181112222" not null | Defect #13 not actually fixed |
| any test user (twice) | Call create_employee_direct twice with different first_names | Returned `employee_id` differs between the two calls | Defect #8 still cached |

Evidence files required (per S092 rule):
- `output/s171/retest/form_submissions.json` (≥25 entries)
- `output/s171/retest/api_mutations.json`
- `output/s171/retest/state_verification.json`
- `output/s171/retest/AUDIT_REPORT.md`
- `output/s171/retest/<lane>/evidence/<scenario_id>-retest.json` (per scenario)
- `output/s171/retest/<lane>/screenshots/*.png` (pre + post per scenario)

---

## Zero-Skip Enforcement

Every task in Phase 1-9 MUST be implemented. No exceptions. If a task cannot be completed:
1. STOP and write a `BLOCKER:` entry to `output/s171/BLOCKERS.csv` with phase, task, error, attempted fix
2. Notify Sam via PR comment or session message
3. Do NOT skip silently, do NOT mark partial as DONE, do NOT defer to "next sprint"

**Phase Completion Checklist** — after each phase, append to `output/s171/PHASE_COMPLETION_CHECKLIST.md`:

| Phase | Task | Status | Evidence | Skipped? | Why |
|---|---|---|---|---|---|

**Forbidden agent behaviors:**
- Skipping a task silently
- Marking partial work as "done"
- Replacing a task with a simpler version without user approval
- Saying "deferred to next sprint"
- Implementing happy path only, skipping edge cases
- **Phase 8 retest:** running scenarios via API instead of real browser (the post-#497 rule applies)

**Verification script template** — write `output/s171/verify_phase_<N>.py` BEFORE starting each phase:

```python
import subprocess, sys, os

def git_diff_has(pattern, repo="."):
    r = subprocess.run(["git","-C",repo,"diff","--name-only","origin/production"], capture_output=True, text=True)
    return any(pattern in l for l in r.stdout.splitlines())

def file_contains(path, pattern):
    if not os.path.exists(path): return False
    with open(path, encoding="utf-8") as f:
        return pattern in f.read()

checks = {
    "P1 backend payroll_compensation modified": git_diff_has("payroll_compensation.py"),
    "P1 frontend panel modified": git_diff_has("compensation-detail-panel.tsx", "../bei-tasks"),
    "P1 backend has has_ssa": file_contains("hrms/api/payroll_compensation.py", "has_ssa"),
    # ... per phase
}
passed = sum(1 for v in checks.values() if v)
print(f"\n{passed}/{len(checks)} checks passed")
for k,v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
sys.exit(0 if passed == len(checks) else 1)
```

---

## Autonomous Execution Contract

- **completion_condition:**
  - All 9 phases technically complete (Phase 8 only after Sam's deploy signal)
  - Both PRs (hrms + BEI-Tasks) opened
  - Plan YAML status=COMPLETED
  - SPRINT_REGISTRY.md S172 row updated
  - Phase 8 retest evidence committed with audit gate PASS
- **stop_only_for:**
  - Defect #16 root cause cannot be determined in 60 min (Phase 2 HARD BLOCKER)
  - Defect #18 inventory ambiguous between Option A and Option B (escalate to Sam)
  - Defect #19 RoleGuard fix unclear after diagnosis (escalate to Sam with findings)
  - Direct conflict with unrelated in-flight changes
  - Phase 8 cannot proceed because Sam hasn't deployed yet (NORMAL — wait for signal)
- **continue_without_pause_through:** diagnose → implement → verify → PR → wait for deploy → retest → closeout
- **blocker_policy:**
  - programmatic → fix and continue
  - 3+ failures on same approach → grounded research, then continue OR escalate
  - business-data → pause
- **signoff_authority:** single-owner (Sam). PRs land in Sam's inbox for merge.
- **canonical_closeout_artifacts:**
  - `output/s171/REQUIREMENTS_REGRESSION_CHECK.md`
  - `output/s171/PHASE_BUDGET.json`
  - `output/s171/PHASE_COMPLETION_CHECKLIST.md`
  - `output/s171/diagnostics/*.md`
  - `output/s171/verification/*.png`
  - `output/s171/retest/AUDIT_REPORT.md`
  - `output/s171/retest/<lane>/evidence/*.json`
  - `output/l3/s166/DEFECTS.csv` (updated with S172 verification)
  - `docs/plans/2026-04-08-sprint-172-s166-followup-defect-fixes.md` (this file, status=COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (S172 row=COMPLETED)

---

## Test Scripts Reference

Existing scripts the execution agent should reuse / lift patterns from:

| Purpose | Script |
|---|---|
| Frappe→my.bebang.ph login chain | `scripts/testing/l3_s166_phase0_preconditions.mjs` |
| Real browser EMP-CREATE pattern | `scripts/testing/l3_s166_lane_h_runner.mjs` |
| Dialog interaction + force-click combobox | `scripts/testing/l3_s166_lane_a_phase2_runner.mjs` |
| 2-pass PUT soft-delete cleanup | `scripts/testing/l3_s166_lane_h_cleanup2.mjs` |
| SSM Frappe SQL execution (frappe-bulk-edits skill) | `scripts/testing/s166_cleanup_conflict_orphans.py` (reference for boilerplate) |
| Audit script template | `scripts/testing/s166_audit_browser_proof_v3.py` |
| Compensation page interaction | `scripts/testing/l3_s166_lane_a_phase4_runner.mjs` (reference — Lane A4 used the API path; agent must adapt to use real browser for S172) |

Test accounts (all passwords `BeiTest2026!`): see `memory/testing-accounts.md`. Primary actors:
- test.hr@bebang.ph (HR Manager — most defect fixes)
- test.crew1@bebang.ph (Crew — for Defect #19 OT verification)
- test.finance@bebang.ph (Finance — for sensitive change approvals)
- test.supervisor@bebang.ph (Supervisor — for OT/leave approvals)

---

## Execution Workflow

- Test Python changes locally: `/local-frappe`
- Run frontend dev server: `cd ../bei-tasks && npm run dev`
- Real browser test: `/playwright-bei-erp` skill (reference: `scripts/testing/l3_s166_lane_a_phase2_runner.mjs`)
- Frappe bulk operations via SSM: `/frappe-bulk-edits` skill
- Deployment: **DO NOT invoke `/deploy-frappe` yourself.** Sam handles deploy after PR merge.

---

## Execution Authority

This sprint is intended for autonomous end-to-end execution by a single agent in a single session, EXCEPT Phase 8 retest which requires waiting for Sam's deploy signal. Do not stop for progress-only updates. Only pause for items in the Autonomous Execution Contract `stop_only_for` section.

When dispatching subagents for Phase 8 retest, you MUST pair every retest runner with an INDEPENDENT audit gate per the post-#497 `/l3-v2-bei-erp` rule. No exceptions.
