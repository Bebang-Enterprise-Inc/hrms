---
sprint_id: S158
display: Sprint 158
title: "Compensation Setup — Single-Page Employee Editor"
branch: s158-compensation-editor
status: "PR_CREATED"
planned_date: 2026-04-03
completed_date: null
depends_on: null
total_work_units: 42
execution_summary: "PRs: hrms#426, BEI-Tasks#316. Backend: detail endpoint, DocType schema migration, update_compensation bei_* handling, activation logic. Frontend: detail page, ph-statutory.ts, batch mutation, clickable names in grid + employee master."
registry_row: "| `S158` | Sprint 158 | `s158-compensation-editor` | — | PLANNED | `docs/plans/2026-04-03-sprint-158-compensation-editor.md` |"
---

# S158: Compensation Setup — Single-Page Employee Editor

## Context

The HR team (Ronald Caringal, HR Manager) reported that the current "Edit Compensation" slide-out is unusable for bulk data entry. It forces one-field-at-a-time editing via dropdown (Change Type) → dropdown (Salary Component) → value → reason → submit. Editing 6 allowances for one employee = 6 separate form submissions. With 500+ employees, this is a productivity blocker.

The CEO (Sam) confirmed: replace the slide-out with a single-page editor showing all compensation fields at once, with clickable employee names and recent payroll history.

**Ronald's confirmed allowance categories (Tue Apr 1):** Non-Taxable (de minimis), Honorarium, Gasoline, Meal, Others. Plus Communication (already in data).

**What's broken today:**
1. Employee names in Compensation Setup grid are not clickable — no way to navigate to an employee detail view
2. The Edit Compensation sheet edits ONE field at a time via cascading dropdowns
3. No payroll history visible when editing — HR has no context on prior changes
4. Same issue on Employee Master page — names not clickable

## Design Rationale (For Cold-Start Agents)

**Why this architecture (detail page, not inline editing):**
- The grid has 25+ columns and is already dense. Adding inline editing to the grid would make it unusable.
- A dedicated detail page allows showing compensation, deductions, history, and payroll info in a clean layout without horizontal scrolling.
- The grid stays as-is for overview/export; the detail page is for editing individual employees.

**Why batch save via parallel API calls (not a new bulk endpoint):**
- The existing `update_compensation()` endpoint creates `BEI Compensation Change` records with an approval workflow (HR Manager → Accounts Manager). Each field change needs its own audit trail.
- Creating a bulk endpoint would bypass the per-field approval workflow.
- Parallel API calls give the same UX ("save all at once") while preserving the approval chain.

**Why client-side statutory computation:**
- The backend already computes deductions in `get_compensation_grid()`. But for live preview (as user types a new base salary), we need instant feedback without an API call.
- The statutory formulas are pure math (SSS bracket lookup, PhilHealth %, Pag-IBIG %, TRAIN tax brackets) — safe to mirror in TypeScript.
- All client-side values are labeled "est." and are overridden by server-side computation on save.

**Why a new `get_employee_compensation_detail()` endpoint:**
- The existing `get_compensation_grid()` is paginated for the grid. Calling it with `search=<id>&page_size=1` works but returns unnecessary pagination metadata and runs a `COUNT(*)` query.
- A dedicated endpoint is cleaner, returns history inline (saves a second API call), and is optimized for single-employee use.

## Files to Modify

| # | File | Repo | Change | Phase |
|---|------|------|--------|-------|
| 1 | `hrms/api/payroll_compensation.py` | BEI-ERP | Add `get_employee_compensation_detail()`, modify `update_compensation()` for `bei_*` fields | 1 |
| 2 | `lib/queries/hr-payroll-compensation.ts` | bei-tasks | Add `compensationQueries.detail()`, `useBatchUpdateCompensation()` | 2 |
| 3 | `lib/ph-statutory.ts` | bei-tasks | **NEW** — SSS, PhilHealth, Pag-IBIG, TRAIN tax in TypeScript | 2 |
| 4 | `app/dashboard/hr/payroll/compensation-setup/[employee]/page.tsx` | bei-tasks | **NEW** — Single-page compensation editor | 3 |
| 5 | `app/dashboard/hr/payroll/compensation-setup/page.tsx` | bei-tasks | Make employee names clickable `<Link>` | 4 |
| 6 | `app/dashboard/hr/employee-master/page.tsx` | bei-tasks | Make employee names clickable `<Link>` | 4 |

## Existing Code to Reuse

| What | Location | How |
|------|----------|-----|
| Statutory computation (Python) | `hrms/api/payroll_compensation.py:30-108` | Mirror to TypeScript for client-side preview |
| `CompensationGridEmployee` type | `bei-tasks/lib/queries/hr-payroll-compensation.ts:21-57` | Extend for detail view |
| `useUpdateCompensationMutation()` | `bei-tasks/lib/queries/hr-payroll-compensation.ts` | Reuse for batch save |
| `formatCurrency()` | `bei-tasks/app/dashboard/hr/payroll/compensation-setup/page.tsx:66-72` | Extract to shared util or copy |
| `RoleGuard` + `ROLES` | `bei-tasks/components/layout/role-guard.tsx`, `bei-tasks/lib/roles.ts` | Same RBAC as grid page |
| `HrPageHeader` | `bei-tasks/components/hr/index.ts` | Back button + title pattern |
| Frappe API proxy | `bei-tasks/app/api/frappe/[...path]/route.ts` | All API calls go through this proxy |
| `set_backend_observability_context()` | `hrms/utils/sentry.py` | Required for new endpoint (DM-7) |

---

## Phase 1: Backend (BEI-ERP) — 12 units (was 10, +2 for Task 1.0 schema migration)

### Task 1.1: Add `get_employee_compensation_detail(employee)` endpoint
**MUST_MODIFY:** `hrms/api/payroll_compensation.py`
**MUST_CONTAIN:** `def get_employee_compensation_detail`

New `@frappe.whitelist()` endpoint returning:
- Employee identity: `name`, `employee_name`, `department`, `branch`, `designation`, `employment_type`, `date_of_joining`
- SSA: `base_salary`, `salary_structure`, `tax_slab`, `ssa_from_date`
- 6 allowance fields: `bei_comm_allow_monthly`, `bei_deminimis_monthly`, `bei_honorarium_monthly`, `bei_meal_allow_monthly`, `bei_gasoline_allow_monthly`, `bei_other_fixed_monthly`
- Projected deductions: reuse `compute_sss_employee()`, `compute_philhealth_employee()`, `compute_pagibig_employee()`, `compute_monthly_tax()` from same file
- Bank info: `salary_mode`, `bank_name`, `bank_ac_no`
- Pending changes count from `BEI Compensation Change` where status IN ('Pending HR Manager', 'Pending Accounts Manager')
- Last 10 compensation changes inline (from `BEI Compensation Change` ordered by creation DESC)

Must call `set_backend_observability_context(module="payroll", action="get_employee_compensation_detail", mutation_type="read")`.

**Guard (AUDIT V3):** Add employee existence check as first line (pattern: `payroll_compensation.py:328-329`):
```python
if not frappe.db.exists("Employee", employee):
    frappe.throw(_("Employee {0} not found").format(employee), frappe.DoesNotExistError)
```

**Masking (AUDIT V8):** Mask `bank_ac_no` server-side before returning (pattern: `payroll_compensation.py:609-615`):
```python
if result.get("bank_ac_no") and len(result["bank_ac_no"]) > 4:
    result["bank_ac_no"] = "****" + result["bank_ac_no"][-4:]
```

### Task 1.0: Add `employee_field_name` Data field to `BEI Compensation Change` DocType [AUDIT B1]
**MUST_MODIFY:** `hrms/hr/doctype/bei_compensation_change/bei_compensation_change.json`
**MUST_CONTAIN:** `employee_field_name`

**HARD BLOCKER (AUDIT B1):** The existing `salary_component` field is `fieldtype: "Link"` to `Salary Component`. Setting it to `bei_comm_allow_monthly` will raise `LinkValidationError` — these are Employee field names, not Salary Component records. A new `employee_field_name` Data field is required.

Add a new field to the DocType JSON:
```json
{
  "fieldname": "employee_field_name",
  "fieldtype": "Data",
  "label": "Employee Field Name",
  "description": "For direct Employee field allowances (bei_* fields)",
  "depends_on": "eval:doc.salary_component === null || doc.salary_component === ''",
  "read_only": 1
}
```

After modifying the JSON, `bench migrate` is required. Add to deploy steps.

### Task 1.2: Modify `update_compensation()` for direct allowance fields
**MUST_MODIFY:** `hrms/api/payroll_compensation.py`
**MUST_CONTAIN:** `bei_comm_allow_monthly`

When `change_type = "Allowance"` and `salary_component` is one of the 6 `bei_*` field names:

**HARD BLOCKER (AUDIT B6):** Current code at ~line 421-436 looks up Salary Detail for ALL non-Salary changes. For `bei_*` fields, this returns 0 (wrong old_value). Add branch FIRST:
```python
if salary_component and salary_component.startswith("bei_"):
    old_value = flt(frappe.db.get_value("Employee", emp_id, salary_component) or 0)
elif salary_component:
    # existing Salary Detail SQL lookup
    ...
```

**HARD BLOCKER (AUDIT B1):** When inserting the `BEI Compensation Change` record for `bei_*` fields:
- Set `salary_component = None` (leave blank — not a Salary Component record)
- Set `employee_field_name = salary_component` (the `bei_*` field name)
- Create record as normal (same approval chain)

### Task 1.3: Add activation logic for ALL change types on approval [AUDIT B2]
**MUST_MODIFY:** `hrms/api/payroll_compensation.py`
**MUST_CONTAIN:** `_activate_compensation_change`

**HARD BLOCKER (AUDIT B2):** The controller `bei_compensation_change.py` is a stub (`pass`). `approve_compensation_change()` sets status to "Approved" but NEVER writes values to Employee or SSA. No activation exists for ANY change type.

Add `_activate_compensation_change(doc)` helper called at final approval inside `approve_compensation_change()`, wrapped in savepoint:
```python
def _activate_compensation_change(doc):
    """Write approved change to Employee record or SSA."""
    if doc.employee_field_name and doc.employee_field_name.startswith("bei_"):
        # Direct Employee field (bei_* allowances)
        frappe.db.set_value("Employee", doc.employee, doc.employee_field_name, doc.new_value)
    elif doc.change_type == "Salary":
        # New SSA required — NOT set_value on Employee
        latest_ssa = frappe.db.get_value(
            "Salary Structure Assignment",
            {"employee": doc.employee, "docstatus": 1},
            ["salary_structure", "income_tax_slab"],
            order_by="from_date DESC", as_dict=True
        )
        new_ssa = frappe.get_doc({
            "doctype": "Salary Structure Assignment",
            "employee": doc.employee,
            "salary_structure": latest_ssa.salary_structure,
            "income_tax_slab": latest_ssa.income_tax_slab,
            "base": doc.new_value,
            "from_date": doc.effective_date,
            "company": frappe.db.get_value("Employee", doc.employee, "company"),
        })
        new_ssa.insert(ignore_permissions=True)
        new_ssa.submit()
    else:
        # Other Salary Detail components — update child table
        pass  # Extend when non-bei_* allowance changes are needed
```

Call in `approve_compensation_change()` at the `"Approved"` transition, wrapped in `frappe.db.savepoint("compensation_activation")`.

---

## Phase 2: Frontend Query + Utils (bei-tasks) — 8 units

### Task 2.1: Add `CompensationDetailEmployee` interface + `compensationQueries.detail()` [AUDIT B4]
**MUST_MODIFY:** `lib/queries/hr-payroll-compensation.ts`
**MUST_CONTAIN:** `compensation-detail`
**MUST_CONTAIN:** `CompensationDetailEmployee`

**HARD BLOCKER (AUDIT B4):** Define and export the TypeScript interface BEFORE writing the query:
```typescript
export interface CompensationDetailEmployee {
  employee: string;
  employee_name: string;
  department: string;
  branch: string;
  designation: string;
  employment_type: string;
  date_of_joining: string;
  base_salary: number;
  salary_structure: string | null;
  tax_slab: string | null;
  ssa_from_date: string | null;
  bei_comm_allow_monthly: number;
  bei_deminimis_monthly: number;
  bei_honorarium_monthly: number;
  bei_meal_allow_monthly: number;
  bei_gasoline_allow_monthly: number;
  bei_other_fixed_monthly: number;
  projected_sss: number;
  projected_philhealth: number;
  projected_pagibig: number;
  projected_tax: number;
  salary_mode: string | null;
  bank_name: string | null;
  bank_ac_no: string | null; // masked server-side
  pending_changes_count: number;
  changes: CompensationChange[];
}
```

Add queryOptions for single-employee compensation detail:
- queryKey: `["hr", "payroll", "compensation-detail", employee]`
- queryFn: calls `hrms.api.payroll_compensation.get_employee_compensation_detail` via Frappe proxy
- enabled: `!!employee`
- staleTime: `10 * 1000` (10 seconds — prevents redundant API calls on navigation)

### Task 2.2: Add `useBatchUpdateCompensation()` mutation
**MUST_MODIFY:** `lib/queries/hr-payroll-compensation.ts`
**MUST_CONTAIN:** `useBatchUpdateCompensation`

Custom hook that:
1. Accepts `{ changes: Record<string, number>, employee: string, reason: string, effective_date: string }`
2. Filters to only fields where `changes[field] !== currentValue`
3. Fires parallel `frappePost()` calls directly (NOT `updateMutation.mutateAsync()` — parallel calls on a single mutation instance race on TanStack reactive state) [AUDIT V6]
4. For `base_salary` changes: `change_type = "Salary"`
5. For `bei_*` changes: `change_type = "Allowance"`, `salary_component = fieldName`
6. Collects all results, returns count of submitted changes
7. Invalidates `["hr", "payroll", "compensation-detail"]` and `["hr", "payroll", "compensation-grid"]`

### Task 2.3: Create `lib/ph-statutory.ts`
**NEW FILE:** `lib/ph-statutory.ts`
**MUST_CONTAIN:** `computeSssEmployee`

Mirror Python functions from `payroll_compensation.py:30-108`:
```typescript
export function computeSssEmployee(base: number): number { /* MSC bracket × 4.5% */ }
export function computePhilhealthEmployee(base: number): number { /* 2.5%, floor 250, cap 2500 */ }
export function computePagibigEmployee(base: number): number { /* 1-2%, cap 100 */ }
export function computeMonthlyTax(base: number): number { /* TRAIN 2025 brackets */ }
export function computeSssEmployer(base: number): number { /* MSC × 9.5% */ }
export function computePhilhealthEmployer(base: number): number { /* same as employee */ }
export function computePagibigEmployer(base: number): number { /* 2%, cap 100 */ }
```

All pure functions. Used for live preview only (labeled "est." in UI).

**Known limitation (AUDIT B5):** `computeMonthlyTax(base)` uses base salary only. Honorarium and above-cap meal/gasoline are taxable but excluded. Tax preview will be understated for affected employees. Add comment: `// NOTE: base-only — taxable allowances (honorarium, above-cap meal/gasoline) excluded`. This matches the existing Python behavior and is acceptable for "est." labeling.

---

## Phase 3: Employee Detail Page (bei-tasks) — 14 units

### Task 3.1: Create detail page component
**NEW FILE:** `app/dashboard/hr/payroll/compensation-setup/[employee]/page.tsx`
**MUST_CONTAIN:** `CompensationDetailPage`

Layout (single scrollable page):

**Header:**
- Back button → `/dashboard/hr/payroll/compensation-setup`
- Employee name (large), department badge, branch badge
- Sub-line: ID, designation, employment type, date of joining

**Compensation Card:**
- "Edit Compensation" button (top right, toggles edit mode)
- Base Salary: display value or input (in edit mode)
- Daily Rate: computed from base/26, always read-only
- Allowances section (6 rows): label + display/input for each `bei_*` field
- Total Allowances: sum of 6, read-only
- Gross Pay: base + allowances, read-only
- When editing: Effective Date picker (default next cutoff: 16th or 1st), Reason textarea, Save + Cancel buttons

**Statutory Deductions Card (read-only, live-computed):**
- SSS, PhilHealth, Pag-IBIG, Tax (est.) — from `lib/ph-statutory.ts`
- Total Deductions
- Net Take-Home (green, bold) = Gross - Deductions
- Company Cost = Gross + employer SSS/PhilHealth/Pag-IBIG
- All update instantly when base salary changes in edit mode

**Recent Changes Card:**
- Table: Date | Type | Component | Old → New | Status | Requested By
- From `detail.changes` (last 10), no separate API call

**Payroll Info Card (read-only):**
- Salary Structure, Tax Slab, Pay Mode, Bank (masked), SSA Effective Date

### Task 3.2: Edit mode state management
**MUST_CONTAIN in `[employee]/page.tsx`:** `isEditing`

- `isEditing` boolean state, toggled by "Edit Compensation" / "Cancel"
- `editValues` object: `{ base_salary, bei_comm_allow_monthly, bei_deminimis_monthly, bei_honorarium_monthly, bei_meal_allow_monthly, bei_gasoline_allow_monthly, bei_other_fixed_monthly }`
- On entering edit mode: populate `editValues` from current server data
- On cancel: reset `editValues`, exit edit mode
- On save: call `useBatchUpdateCompensation()` with changed fields only, show toast with count, exit edit mode

### Task 3.3: RBAC guard
**MUST_CONTAIN in `[employee]/page.tsx`:** `RoleGuard`

**HARD BLOCKER (AUDIT B7):** The prop is `roles`, NOT `allowedRoles`. Using `allowedRoles` silently bypasses the guard (falls through to `hasAccess = true`). Copy the exact pattern from `compensation-setup/page.tsx:894`:
```tsx
<RoleGuard roles={[ROLES.HR_USER, ROLES.HR_MANAGER, ROLES.ACCOUNTS_MANAGER, ROLES.SYSTEM_MANAGER, ROLES.ADMINISTRATOR]}>
```

---

## Phase 4: Grid Clickable Names (bei-tasks) — 6 units

### Task 4.1: Make names clickable in compensation grid
**MUST_MODIFY:** `app/dashboard/hr/payroll/compensation-setup/page.tsx`
**MUST_CONTAIN:** `compensation-setup/${row.original.employee}`

Change the `employee_name` column cell renderer from plain `<div>` to `<Link>`:
```tsx
import Link from "next/link";
// ...
cell: ({ row }) => (
  <Link href={`/dashboard/hr/payroll/compensation-setup/${row.original.employee}`}
        className="text-primary hover:underline font-medium">
    <div>{row.original.employee_name}</div>
    <div className="text-xs text-muted-foreground">{row.original.employee}</div>
  </Link>
)
```

### Task 4.2: Make names clickable in Employee Master [AUDIT B3]
**MUST_MODIFY:** `app/dashboard/hr/employee-master/page.tsx`
**MUST_CONTAIN:** `compensation-setup/`

**HARD BLOCKER (AUDIT B3):** This page does NOT use TanStack Table. It uses a hand-written `<tbody>` with `employees.map()`. Do NOT use ColumnDef pattern. Target the `<p>` element at line ~601:
```tsx
// BEFORE (line ~601):
<p className="font-medium">{employee.employee_name}</p>

// AFTER:
<Link href={`/dashboard/hr/payroll/compensation-setup/${employee.employee_id}`}
      className="text-primary hover:underline font-medium">
  {employee.employee_name}
</Link>
```

---

## Sentry Observability (DM-7)

New endpoint `get_employee_compensation_detail` must call `set_backend_observability_context()` as its first meaningful line (Task 1.1). Existing `update_compensation` already has it.

Frontend: `@sentry/nextjs` auto-instruments the Next.js page route. No extra code needed.

---

## Requirements Regression Checklist

- [ ] Does the detail page show ALL 7 editable fields (base + 6 allowances) on a single page?
- [ ] Can the user edit all 7 fields and save them in ONE action (not 7 separate submissions)?
- [ ] Does each changed field create a separate `BEI Compensation Change` record (preserving per-field approval)?
- [ ] Do statutory deductions update live as the user types a new base salary?
- [ ] Are employee names in the grid clickable links to the detail page?
- [ ] Does the detail page show recent compensation changes (last 10)?
- [ ] Does the new backend endpoint call `set_backend_observability_context()`?
- [ ] Is the detail page protected by the same RoleGuard as the grid page?
- [ ] Does the `bei_*` allowance update flow use `frappe.db.get_value("Employee", ...)` for old_value (not Salary Detail lookup)?

---

## Zero-Skip Enforcement

Every task MUST be implemented. If a task cannot be completed, the agent STOPS and asks the user.

**Forbidden behaviors:**
- Skipping a task silently
- Marking partial work as "done"
- Replacing a task with a simpler version without user approval
- Saying "deferred to next sprint"
- Implementing happy path only, skipping edge cases

**Phase Completion Verification:**
After each phase, run the verification assertions (MUST_MODIFY + MUST_CONTAIN) to confirm all tasks are complete.

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| test.hr@bebang.ph | Click employee name in compensation grid | Navigate to `/dashboard/hr/payroll/compensation-setup/HR-EMP-xxxxx` with all data loaded | Task 4.1 broken |
| test.hr@bebang.ph | Click "Edit Compensation" → change base salary from 20000 to 22000 → type reason "Annual increase" → click Save | Toast: "1 change submitted for approval", base salary shows 22000 | Task 3.2 or 2.2 broken |
| test.hr@bebang.ph | Edit base salary + meal allowance + gasoline → Save | Toast: "3 changes submitted for approval" (only 3, not 7) | Batch save not filtering unchanged fields |
| test.hr@bebang.ph | In edit mode, type base salary 25000 → observe deductions card | SSS/PhilHealth/Pag-IBIG/Tax update immediately without API call | Task 2.3 broken |
| test.hr@bebang.ph | Navigate to detail page for employee with no SSA | Page loads, shows "No salary data" gracefully, no crash | Missing null handling |

---

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s158-compensation-editor origin/production`. NEVER write code on production.
3. Read `docs/plans/SPRINT_REGISTRY.md` for cross-sprint context.
4. Read `hrms/api/payroll_compensation.py` (full file) to understand existing endpoints.
5. Read `bei-tasks/lib/queries/hr-payroll-compensation.ts` for existing types and queries.
6. Read `bei-tasks/app/dashboard/hr/payroll/compensation-setup/page.tsx` for grid column definitions and edit sheet.
7. Start Phase 1 (backend).

## Execution Authority

This sprint is intended for autonomous end-to-end execution. Do not stop for progress-only updates. Only pause for items listed in the stop_only_for section below.

## Autonomous Execution Contract

- **completion_condition:**
  - All 4 phases complete with MUST_MODIFY/MUST_CONTAIN verified
  - PR created for both repos (BEI-ERP + bei-tasks)
  - L3 evidence committed: `git add -f output/l3/s158/ && git push` [AUDIT B9]
  - Sprint registry updated with PR numbers
  - Plan YAML status updated to PR_CREATED
- **stop_only_for:**
  - Missing credentials/access
  - `BEI Compensation Change` DocType schema unclear (need to inspect controller)
  - Direct conflict with in-flight S154 changes
- **continue_without_pause_through:** code → test → PR creation → closeout
- **blocker_policy:**
  - programmatic → fix and continue
  - environment/runtime → debug, continue
  - business-data/policy → pause
- **signoff_authority:** single-owner (Sam)
- **governor_feedback_loop** [AUDIT B10]:
  - REJECT → read PR comments, fix issues, push to same branch
  - NEEDS_FIX → apply suggested fix, push
  - Merge Conflict → `git fetch origin production && git rebase origin/production`, resolve, force-push
  - Deploy Failure → check Docker/Vercel logs, fix if code issue, redeploy
  - Low confidence review (<0.80) → pause auto-merge, wait for manual review
- **release_manager_gate:** `bei-release-manager` blocks merge unless L3 evidence files exist in branch. Required: `output/l3/s158/form_submissions.json`, `output/l3/s158/api_mutations.json`, `output/l3/s158/state_verification.json`.

## Execution Workflow

- Test Python changes: `/local-frappe`
- Deploy BEI-ERP (backend FIRST): `/deploy-frappe` with `no_cache=true` (new Python code requires full build — MEMORY.md Lesson 2) [AUDIT B8]
- Deploy bei-tasks (frontend SECOND): Vercel auto-deploys on push. Verify backend endpoint exists before frontend goes live.
- Full workflow: `/agent-kickoff`
- E2E testing: `/e2e-test`
- **DocType migration:** Task 1.0 modifies `bei_compensation_change.json` — `bench migrate` is required after deploy.

## Verification

1. **Backend**: Call `get_employee_compensation_detail` via bench console for a known employee — verify all fields returned
2. **Detail page**: Navigate to `/dashboard/hr/payroll/compensation-setup/HR-EMP-xxxxx` — verify all compensation data renders
3. **Edit flow**: Edit base salary + 2 allowances → save → verify 3 `BEI Compensation Change` records created
4. **Live preview**: Change base salary in edit mode → verify deduction estimates update immediately
5. **Grid link**: Click employee name in grid → verify navigation to detail page
6. **E2E**: Run L2 page check on new detail page route

## Out of Scope

- Salary slip history (no slips exist yet — revisit when payroll runs in Frappe)
- Bulk editing from the detail page (grid page already has bulk change dialog)
- Bank/sensitive field changes on detail page (keep existing dual-control flow on grid page)
- Mobile responsiveness (HR uses desktop for compensation work)

---

## Audit Amendments (v1.1) — 2026-04-03

### Audit Methodology

9 specialized agents audited this plan in parallel. Full reports with code fixes are in the referenced files.

| Domain | Findings File | Score |
|--------|---------------|-------|
| Frappe Backend | `output/plan-audit/compensation-editor/frappe_backend_findings.md` | 4 CRITICAL, 6 WARNING, 5 INFO |
| PH Finance | `output/plan-audit/compensation-editor/ph_finance_findings.md` | 63/100 compliance |
| Frontend | `output/plan-audit/compensation-editor/frontend_findings.md` | 6/10 quality |
| Deployment/QA | `output/plan-audit/compensation-editor/deployment_qa_findings.md` | NO-GO, 7 blocking |
| Team Orchestration | `output/plan-audit/compensation-editor/team_orchestration_findings.md` | 30% compliance |
| System Architecture | `output/plan-audit/compensation-editor/system_arch_findings.md` | 3.2/5 |
| Design Review | `output/plan-audit/compensation-editor/design_review_findings.md` | 3.1/5 |
| **Code Verifier** | `output/plan-audit/compensation-editor/code_verification.md` | 12 confirmed, 6 stale, 5 new gaps |
| **Fact-Checker** | `output/plan-audit/compensation-editor/fact_check_verification.md` | 10/10 SUPPORTED |

**Consolidated report:** `output/plan-audit/compensation-editor/AUDIT_REPORT.md`

### Blockers Resolved Inline (operative sections updated)

All 10 blockers have been applied directly to the operative task descriptions above:
- **B1:** Task 1.0 added (schema migration for `employee_field_name`)
- **B2:** Task 1.3 rewritten (activation for all change types)
- **B3:** Task 4.2 rewritten (hand-written table, not ColumnDef)
- **B4:** Task 2.1 rewritten (interface defined)
- **B5:** Task 2.3 updated (tax limitation documented)
- **B6:** Task 1.2 rewritten (bei_* old_value branch)
- **B7:** Task 3.3 rewritten (correct `roles` prop)
- **B8:** Execution Workflow updated (`no_cache=true`)
- **B9:** AEC updated (L3 evidence + `git add -f`)
- **B10:** AEC updated (governor feedback loop)

### Additional Recommendations (Non-Blocking)

1. **Edit slide-out coexistence** (`frontend_findings.md` W-08): After S158, both edit paths exist (click name → detail page, pencil icon → slide-out). Decision: keep slide-out as fallback for quick single-field edits. Document in user training.
2. **staleTime for grid query** (`code_verification.md` G3): Add `staleTime: 30_000` to `compensationQueries.grid()` to reduce redundant API calls on back-navigation.
3. **placeholderData from grid row** (`frontend_findings.md` C-05): Use `placeholderData: () => gridRowData` in detail query for instant perceived load.
4. **History endpoint overlap** (`code_verification.md` G1): Inline changes in detail response (already planned) — do NOT also call `compensationQueries.history()`.

### Pre-Flight Checks: Audit Additions

- [ ] **AUDIT-1:** `employee_field_name` field exists in `bei_compensation_change.json` and `bench migrate` succeeds
- [ ] **AUDIT-2:** `_activate_compensation_change()` exists and handles Salary (SSA insert+submit) + bei_* (set_value) paths
- [ ] **AUDIT-3:** `old_value` for `bei_*` fields comes from `frappe.db.get_value("Employee", ...)`, not Salary Detail SQL
- [ ] **AUDIT-4:** Detail page uses `<RoleGuard roles={[...]}>` (not `allowedRoles`)
- [ ] **AUDIT-5:** `CompensationDetailEmployee` interface exported from `hr-payroll-compensation.ts`
- [ ] **AUDIT-6:** Task 4.2 edits the `<p>` at line ~601, not a ColumnDef
- [ ] **AUDIT-7:** Deploy uses `no_cache=true` for BEI-ERP
- [ ] **AUDIT-8:** L3 evidence files committed before PR: `git add -f output/l3/s158/`
- [ ] **AUDIT-9:** CTA wiring: "Edit Compensation" button toggles edit mode, Save fires batch, Cancel resets
- [ ] **AUDIT-10:** Empty/error states: no-SSA employee shows "No salary data", API error shows retry
- [ ] **AUDIT-11:** RBAC: unauthorized role sees access-denied, not empty page

### GO / NO-GO Gate (Updated)

**Status: NO-GO until AUDIT-1 through AUDIT-11 are all checked during execution.**

The operative plan sections above have been updated with all fixes. Once executed, the agent must verify each AUDIT check passes before creating the PR.
