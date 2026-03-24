# Sprint S114 — Payroll: Compensation Management & Sensitive Data Controls

```yaml
canonical_sprint_id: S114
status: DEPLOYED
branch: s114-payroll-compensation-sensitive
backend_pr: "#345"
execution_started: 2026-03-24
deployed_at: null
completed_date: null
execution_summary: |
  Phase 0: 3 DocTypes + enrichment dual-control routing. Phase 1+2: 12-endpoint
  backend API with Sentry, compensation grid + sensitive-changes queue frontend.
  PR#345 submitted. Awaiting governor merge + L3 in fresh session.
parallel_group: S083-replacement
sibling_sprints:
  - S113  # Command Center + Navigation (no dependency)
  - S115  # Processing + Remittances (no dependency)
total_units: 38
```

---

## Purpose

S114 is the second of three independent sprints decomposed from S083 (Payroll War Room). It owns the compensation editing workflow and the dual-control sensitive-data approval queue. S113 owns the landing/navigation/RBAC. S115 owns processing and remittances. These three sprints have **zero dependencies on each other** and can execute in parallel.

This sprint builds two new portal routes and one new backend file. Nothing it touches is owned by S112 or S114.

---

## Design Rationale (For Cold-Start Agents)

### Why Dual-Control?

BEI processes payroll for 665 employees across 47 locations. Sensitive payroll fields — bank account numbers, TINs, government IDs — are high-fraud targets. A single-actor change (HR alone, or Finance alone) creates an internal control gap that would fail an external audit.

S083's model (Decisions #9, #10, #23) requires:
- HR verifies identity and initiates sensitive change
- Finance approves the financial routing change
- HR activates the change to take effect

This three-step chain means no single person in either department can redirect payroll to a fraudulent account without detection.

### Why a Separate `payroll_compensation.py`?

`hrms/api/payroll.py` contains query/reporting logic. `hrms/api/enrichment.py` handles generic employee-profile enrichment with approval flows. Compensation management is payroll-domain logic with different approval chains, different effectivity rules, and permanent audit history. Mixing it into either existing file violates single-responsibility and makes S114 harder to extend without conflict.

### Why Future-Dated Effectivity as Default?

Payroll cutoffs are bimonthly. A mid-cycle change that retroactively affects a closed cutoff requires payroll reconstruction. Defaulting to the next cutoff prevents accidental retroactive payroll errors. Same-cutoff or retroactive activation requires an explicit exception flow with stronger approval — a deliberate speed bump.

### Why Bulk-First Design?

Compensation reviews typically affect cohorts: all store managers get a rate increase, all crew on a new contract get a new structure. A row-by-row UI for 665 employees is operationally unusable. The compensation grid must support multi-select with a single change applied across selected employees.

---

## Requirements Regression Checklist

All 12 locked decisions from S083 must be satisfied. An executing agent MUST verify each before marking Phase complete.

| # | Decision | Assertion | Satisfied? |
|---|----------|-----------|------------|
| D3 | Contract-backed fields use selectors, not free text | Salary structure, salary component, deduction component, company, branch, department — all dropdowns backed by Frappe data | YES |
| D4 | Bulk-first design for large workforce | Compensation grid supports multi-select; bulk apply same change to selected employees | YES |
| D8 | HR can directly edit salary, bonus, allowance, recurring earnings/deductions | `update_compensation` endpoint accessible to HR_ADMIN roles without additional approver gate at submission | YES (approval happens post-submission, not pre) |
| D9 | HR + Finance jointly govern bank accounts and sensitive payroll data | Sensitive change queue enforces dual-control; neither HR nor Finance alone can fully activate a bank change | YES |
| D10 | If Finance changes sensitive value, HR must approve | `submit_sensitive_change_request` detects initiator role; Finance-initiated requests route to HR for approval | YES |
| D20 | Recurring compensation is SEPARATE from current-cutoff inputs | `compensation-setup` route manages recurring only; one-time current-cutoff inputs are S114's domain | YES |
| D21 | Sensitive edits require reason, effective date, permanent history — no overwrite | Every `update_compensation` and `approve_sensitive_change` call writes an immutable history entry | YES |
| D22 | Salary/compensation approval chain: HR → HR Head → Mae | `update_compensation` creates request with status "Pending HR Head"; HR Head approve routes to Mae | YES |
| D23 | Bank-account approval chain: HR verify → Finance approve → HR activate | Three-step flow enforced in `approve_sensitive_change` and `activate_sensitive_change` | YES |
| D25 | Payroll-sensitive changes live inside Payroll workspace, not generic enrichment | Routes are under `/dashboard/hr/payroll/`, backend in `payroll_compensation.py` | YES |
| D31 | Employee self-service = request intake only, never direct overwrite | Employee-submitted requests enter the sensitive-changes queue with status "Pending HR Verification" — no field is written directly | YES |
| D32 | Default effectivity = future/next cutoff; same-cutoff or retro needs exception flow | `submit_sensitive_change_request` defaults `effective_date` to next cutoff; same-cutoff/retro requires `exception_justification` field populated | YES |
| P0-1 | BEI Compensation Change DocType exists | Do BEI Compensation Change and BEI Sensitive Change Request DocTypes exist in Frappe? | [ ] |
| P0-2 | Enrichment portal routes sensitive fields | Does enrichment.py route bank/statutory fields through BEI Sensitive Change Request instead of direct write? | [ ] |
| P0-3 | Approval chain mapped to roles | Is the approval chain mapped to HR Manager (Ronald) and Accounts Manager (Mae) roles? | [ ] |
| P0-4 | Enrichment bypass blocked | Can an employee still directly change bank details via enrichment portal? (Must be NO) | [ ] |

---

## Duplication Audit

Before writing any code, an executing agent MUST check these overlaps:

### enrichment.py overlap
`hrms/api/enrichment.py` handles employee enrichment with approval flows including: `bank_name`, `bank_account_number`, `tin`, `sss_id`, `philhealth_id`, `pagibig_id`. These fields also appear in S114's sensitive-changes domain.

**Resolution:** S114's `payroll_compensation.py` handles payroll-context changes (initiated from the Payroll workspace, effective-dated to cutoffs, dual-control). `enrichment.py` handles HR-profile enrichment (onboarding, corrections, profile completion). If an employee submits via the HR profile flow and the field is payroll-sensitive, `enrichment.py` should surface the request into the sensitive-changes queue rather than processing independently. **Do NOT duplicate approval logic — `payroll_compensation.py` owns the queue; `enrichment.py` may call into it.**

### completeness.ts overlap
`../bei-tasks/types/completeness.ts` tracks banking/gov-ID completeness categories. The sensitive-changes queue may need to update completeness status when a change is activated.

**Resolution:** Read `completeness.ts` to understand the category keys before writing the frontend. On activation of a sensitive change, call the existing completeness update mechanism — do not re-implement it.

---

## Ground-Truth Lock

| Fact | Evidence Source |
|------|----------------|
| Salary structures: 522 approved assignments | S076 benchmark result |
| RBAC: Payroll under HR_ADMIN (HR_USER, HR_MANAGER, System Manager, Administrator) | S112 inherits; verify `../bei-tasks/lib/roles.ts` before querying |
| Test accounts: test.hr@bebang.ph, test.finance@bebang.ph, all passwords BeiTest2026! | `memory/testing-accounts.md` |
| Employee Master: 665 employees, 471 active | `data/_FINAL/EMPLOYEE_MASTER.csv` |
| Existing payroll query layer | `../bei-tasks/lib/queries/hr-payroll.ts` |
| Enrichment API (check for overlap) | `hrms/api/enrichment.py` |
| Completeness types (check before frontend) | `../bei-tasks/types/completeness.ts` |
| Sentry rule | `.claude/rules/sentry-observability.md` |

**Do NOT trust any specific data value from conversation memory after compaction. Re-read source files.**

---

## File Ownership

### Files this sprint CREATES (exclusive ownership):
- `hrms/api/payroll_compensation.py`
- `../bei-tasks/app/dashboard/hr/payroll/compensation-setup/page.tsx`
- `../bei-tasks/app/dashboard/hr/payroll/sensitive-changes/page.tsx`
- `../bei-tasks/lib/queries/hr-payroll-compensation.ts`

### Files this sprint READS but does NOT modify:
- `hrms/api/payroll.py` — reference only
- `hrms/api/enrichment.py` — duplication audit only
- `../bei-tasks/app/dashboard/hr/payroll/page.tsx` — S112 owns
- `../bei-tasks/lib/roles.ts` — S112 owns; read for RBAC constants
- `../bei-tasks/types/completeness.ts` — read for category keys
- `../bei-tasks/lib/queries/hr-payroll.ts` — read for query pattern

### Files this sprint does NOT touch (owned by siblings):
- All routes under `/dashboard/hr/payroll/` except `compensation-setup` and `sensitive-changes`
- `hrms/api/payroll.py` (no modification)
- Processing, remittances, history routes (S114)
- Current cutoff, review output routes (S112)

---

## Agent Boot Sequence

An agent picking up this sprint MUST execute these steps in order before writing any code:

1. **Read this plan file completely** — do not skip sections.
2. **Check out the sprint branch:**
   ```bash
   cd F:/Dropbox/Projects/BEI-ERP
   git checkout -b s114-payroll-compensation-sensitive
   # If branch already exists:
   # git checkout s114-payroll-compensation-sensitive
   ```
3. **Run duplication audit** — read `hrms/api/enrichment.py` and `../bei-tasks/types/completeness.ts`. Note all field names that overlap with S114's domain. Write findings to `tmp/s113-duplication-audit.md`.
4. **Read RBAC constants** — read `../bei-tasks/lib/roles.ts` to get exact role constant names used in S112's payroll RBAC.
5. **Read existing query pattern** — read `../bei-tasks/lib/queries/hr-payroll.ts` to match conventions.
6. **Verify test accounts** — read `memory/testing-accounts.md` and confirm test.finance@bebang.ph exists and has a Finance role.
7. **Read Sentry rule** — read `.claude/rules/sentry-observability.md`. Every `@frappe.whitelist()` endpoint in this sprint MUST call `set_backend_observability_context`.
8. **Begin Phase 1.**

---

## Shell Prevention

### Failure Patterns to Avoid

| Anti-Pattern | Prevention |
|-------------|------------|
| Writing backend endpoints without Sentry context | Sentry gate: check every `@frappe.whitelist()` before Phase commit |
| Free-text inputs for contract-backed fields | D3 gate: all structure/component/branch/department/company fields must be Frappe-backed selectors |
| Frontend that mutates state optimistically without error handling | Every mutation hook must have `onError` rollback |
| Retroactive effectivity without exception gate | D32 gate: `effective_date` validation — if date ≤ current cutoff start, `exception_justification` required |
| Single-actor sensitive change approval | D9 gate: `approve_sensitive_change` must check initiator role ≠ approver role |
| Extending `payroll.py` or `enrichment.py` for compensation logic | S114 creates `payroll_compensation.py` only |
| Importing S112 components before S112 is complete | Use placeholder stubs if S112 routes are not yet merged |

### Build Integrity Gates

Before committing any phase:
```bash
# Backend: Python syntax check
cd F:/Dropbox/Projects/BEI-ERP
python -m py_compile hrms/api/payroll_compensation.py

# Frontend: TypeScript check
cd F:/Dropbox/Projects/bei-tasks
npx tsc --noEmit

# Frontend: Build check
npm run build
```

A phase commit MUST NOT break the TypeScript build.

### Vertical Slice First

Build each phase as a complete vertical slice: backend endpoint → query hook → UI component → manual test. Do not build all backend endpoints first, then all frontend. Each endpoint+UI pair must be testable independently.

---

## Phase Budget Contract

No phase may exceed 12 units. Total budget: 38 units.

| Phase | Name | Units | Deliverables |
|-------|------|-------|--------------|
| 0 | DocTypes, Role Mapping & Enrichment Integration | 10 | `BEI Compensation Change` DocType, `BEI Sensitive Change Request` DocType, enrichment.py integration, approval chain role mapping |
| 1 | Backend Compensation API + Compensation Grid Frontend | 10 | `payroll_compensation.py` (compensation endpoints), `compensation-setup/page.tsx`, `hr-payroll-compensation.ts` (compensation queries) |
| 2 | Backend Sensitive-Change API + Dual-Control Queue Frontend | 10 | `payroll_compensation.py` (sensitive-change endpoints added), `sensitive-changes/page.tsx`, `hr-payroll-compensation.ts` (sensitive-change queries added) |
| 3 | Employee Self-Service Intake + Sentry + L1–L4 Certification + Closeout | 8 | Self-service request flow, full Sentry instrumentation verified, all L3 scenarios passing, closeout commit |

### Phase 0 Detail — DocTypes, Role Mapping & Enrichment Integration (10 units)

**HARD BLOCKERS — must be resolved before Phase 1 backend work begins.**

**Task 1 — Create `BEI Compensation Change` DocType (3 units):**

- Fields:
  - `employee` (Link → Employee)
  - `salary_component` (Link → Salary Component)
  - `change_type` (Select: Salary / Allowance / Bonus / Recurring Earning / Recurring Deduction)
  - `old_value` (Currency)
  - `new_value` (Currency)
  - `effective_date` (Date)
  - `reason` (Small Text, mandatory)
  - `status` (Select: Draft / Pending HR Manager / Pending Accounts Manager / Approved / Rejected)
  - `requested_by` (Link → User)
  - `hr_reviewer` (Link → User)
  - `final_approver` (Link → User)
  - `approval_date` (Datetime)
  - `rejection_reason` (Small Text)
- Naming: `BCC-.YYYY.-.####`
- Permissions: HR User (create/read), HR Manager (read/write/submit), Accounts Manager (read/write/amend)

**Task 2 — Create `BEI Sensitive Change Request` DocType (3 units):**

- Fields:
  - `employee` (Link → Employee)
  - `field_name` (Select: bank_name / bank_ac_no / tin_number / sss_number / philhealth_number / pagibig_number)
  - `old_value` (Data)
  - `new_value` (Data)
  - `effective_date` (Date)
  - `reason` (Small Text, mandatory)
  - `proof_attachment` (Attach)
  - `status` (Select: Draft / Pending Finance / Finance Approved / Pending HR Activation / Active / Rejected)
  - `initiated_by` (Link → User)
  - `hr_verifier` (Link → User)
  - `finance_approver` (Link → User)
  - `hr_activator` (Link → User)
  - `rejection_reason` (Small Text)
  - `activated_date` (Datetime)
- Child table `BEI Sensitive Change Audit Log`: timestamp, actor, action, note
- Naming: `BSCR-.YYYY.-.####`
- Permissions: HR User (create/read), HR Manager (read/write/submit), Accounts Manager (read/write/amend)

**Task 3 — Modify `hrms/api/enrichment.py` enrichment integration (2 units):**

In `process_edit_request()`, when the field being changed is in `['bank_name', 'bank_ac_no', 'tin_number', 'sss_number', 'philhealth_number', 'pagibig_number']`, create a `BEI Sensitive Change Request` instead of directly writing to the Employee record. Return a message to the user: "Bank/statutory changes require Finance approval. Your request has been submitted to the Payroll Sensitive Changes queue."

**HARD BLOCKER: Without this, employees can bypass dual-control via the enrichment portal.**

**Task 4 — Map approval chain to concrete Frappe roles (2 units):**

- Salary/compensation changes: HR User (prepares) → HR Manager role = Ronald (reviews) → Accounts Manager role = Mae (approves)
- Bank/statutory changes: HR Manager role = Ronald (verifies) → Accounts Manager role = Mae (approves) → HR Manager role = Ronald (activates)
- In code: check `frappe.get_roles(frappe.session.user)` for "HR Manager" or "Accounts Manager"

**Gate:** Both DocTypes created and visible in Frappe. `enrichment.py` routes sensitive fields through `BEI Sensitive Change Request`. Approval chain documented in code comments.

---

### Phase 1 Detail (10 units)

**Backend — compensation endpoints (5 units):**

```python
# hrms/api/payroll_compensation.py

@frappe.whitelist()
def get_compensation_grid(filters=None):
    """
    Returns all employees with current salary structure, base salary,
    allowances, bonuses, recurring earnings, recurring deductions.
    filters: department, branch, employment_status
    """
    set_backend_observability_context(
        module="payroll",
        action="get_compensation_grid",
        mutation_type="read",
    )
    # ... implementation

@frappe.whitelist()
def get_compensation_history(employee):
    """
    Returns full change history for an employee's compensation.
    """
    set_backend_observability_context(
        module="payroll",
        action="get_compensation_history",
        mutation_type="read",
    )
    # ... implementation

@frappe.whitelist()
def update_compensation(employee, change_type, new_value, reason, effective_date,
                        salary_component=None, bulk_employees=None):
    """
    Creates a compensation change request with history entry.
    change_type: "basic_salary" | "allowance" | "bonus" | "recurring_earning" | "recurring_deduction"
    bulk_employees: list of employee IDs for bulk operations
    Creates approval request: status = "Pending HR Head"
    """
    set_backend_observability_context(
        module="payroll",
        action="update_compensation",
        mutation_type="create",
        extras={"change_type": change_type, "effective_date": effective_date},
    )
    # ... implementation

@frappe.whitelist()
def approve_compensation_change(change_id, approver_action, remarks=None):
    """
    HR Head or Mae approves/rejects a compensation change.
    Advances approval chain: "Pending HR Head" → "Pending Mae" → "Approved"
    """
    set_backend_observability_context(
        module="payroll",
        action="approve_compensation_change",
        mutation_type="update",
        extras={"change_id": change_id, "action": approver_action},
    )
    # ... implementation

@frappe.whitelist()
def get_salary_structure_options():
    """Returns all active salary structures for dropdown."""
    set_backend_observability_context(module="payroll", action="get_salary_structure_options", mutation_type="read")

@frappe.whitelist()
def get_salary_component_options(component_type=None):
    """Returns salary components (earning/deduction) for dropdown."""
    set_backend_observability_context(module="payroll", action="get_salary_component_options", mutation_type="read")
```

**Frontend — compensation grid (5 units):**

`compensation-setup/page.tsx`:
- Dense grid with columns: Employee Name, Employee ID, Department, Branch, Salary Structure, Basic Rate, Recurring Allowances, Recurring Bonuses, Recurring Earnings, Recurring Deductions, Pending Changes
- Filter bar: Department, Branch, Employment Status, search by name/ID
- Row actions: Edit (opens slide-out panel), View History
- Multi-select checkboxes + "Apply Bulk Change" button
- Bulk change modal: change type selector, new value, reason, effective date, confirm list of affected employees
- Edit slide-out: shows current values, form fields per change type, reason textarea, effective date picker (default = next cutoff), submit button
- All structure/component/branch/department selectors fetch from backend options endpoints
- Approval status badge on each row (if pending change exists)
- Pagination: 50 rows per page
- Responsive: horizontal scroll on <1366px, sticky first two columns

`hr-payroll-compensation.ts` (compensation queries):
- `compensationGridQueryOptions(filters)` — queryKey + queryFn
- `compensationHistoryQueryOptions(employee)` — queryKey + queryFn
- `salaryStructureOptionsQueryOptions()` — queryKey + queryFn
- `salaryComponentOptionsQueryOptions(type)` — queryKey + queryFn
- `useUpdateCompensationMutation()` — useMutation with onError rollback + cache invalidation
- `useApproveCompensationChangeMutation()` — useMutation

### Phase 2 Detail (10 units)

**Backend — sensitive-change endpoints (5 units, added to `payroll_compensation.py`):**

```python
@frappe.whitelist()
def get_sensitive_change_queue(status_filter=None, initiated_by_me=False):
    """
    Returns pending sensitive change requests.
    status_filter: "Pending Finance Approval" | "Pending HR Verification" |
                   "Pending HR Activation" | "Approved" | "Rejected"
    """
    set_backend_observability_context(
        module="payroll",
        action="get_sensitive_change_queue",
        mutation_type="read",
        extras={"status_filter": status_filter},
    )

@frappe.whitelist()
def submit_sensitive_change_request(employee, field_name, new_value, reason,
                                    effective_date, proof_attachment=None,
                                    exception_justification=None):
    """
    Creates a sensitive change request.
    Sensitive fields: bank_name, bank_account_number, tin, sss_id, philhealth_id, pagibig_id, payout_exception
    effective_date validation: if <= current cutoff start, exception_justification required.
    Initiator role detection: HR-initiated → "Pending Finance Approval"
                              Finance-initiated → "Pending HR Verification"
                              Employee-initiated (self-service) → "Pending HR Verification"
    """
    set_backend_observability_context(
        module="payroll",
        action="submit_sensitive_change_request",
        mutation_type="create",
        extras={"field_name": field_name, "effective_date": effective_date},
    )

@frappe.whitelist()
def approve_sensitive_change(request_id, remarks=None):
    """
    Approves a sensitive change request.
    Guards: approver role must differ from initiator role.
    Status transitions:
      "Pending Finance Approval" + Finance approver → "Pending HR Activation"
      "Pending HR Verification" + HR approver → "Pending Finance Approval"  (Finance-initiated path)
      "Pending HR Activation" + HR approver → "Approved, Pending Activation"
    """
    set_backend_observability_context(
        module="payroll",
        action="approve_sensitive_change",
        mutation_type="update",
        extras={"request_id": request_id},
    )

@frappe.whitelist()
def reject_sensitive_change(request_id, reason):
    """Rejects a sensitive change request with mandatory reason."""
    set_backend_observability_context(
        module="payroll",
        action="reject_sensitive_change",
        mutation_type="update",
        extras={"request_id": request_id},
    )

@frappe.whitelist()
def activate_sensitive_change(request_id):
    """
    Final activation: writes the field value to the employee record.
    Only callable when status = "Approved, Pending Activation".
    Only callable by HR role.
    Creates immutable history entry with full audit trail.
    """
    set_backend_observability_context(
        module="payroll",
        action="activate_sensitive_change",
        mutation_type="update",
        extras={"request_id": request_id},
    )
```

**Frontend — sensitive-changes queue (5 units):**

`sensitive-changes/page.tsx`:
- Queue table: columns: Employee, Field Changed, From → To (masked for bank account: show last 4 digits), Initiator, Initiator Role, Status, Effective Date, Pending Approver, Actions
- Status filter tabs: All | Pending My Action | Pending Other | Approved | Rejected
- "New Request" button: opens modal with employee selector, sensitive field selector (dropdown of allowed fields), new value input, reason textarea, effective date picker (default = next cutoff), proof attachment upload, exception justification textarea (shown conditionally if date ≤ current cutoff)
- Request detail slide-out: full audit history timeline (who did what, when, remarks), approve/reject actions (shown conditionally based on current user role and status), activate button (shown to HR when status = "Approved, Pending Activation")
- Rejection: requires reason textarea before confirming
- Mobile: stack table into cards, all actions accessible

`hr-payroll-compensation.ts` (sensitive-change queries, added to file):
- `sensitiveChangeQueueQueryOptions(filters)` — queryKey + queryFn
- `useSubmitSensitiveChangeRequestMutation()` — useMutation with onError + invalidation
- `useApproveSensitiveChangeMutation()` — useMutation
- `useRejectSensitiveChangeMutation()` — useMutation
- `useActivateSensitiveChangeMutation()` — useMutation

### Phase 3 Detail (8 units)

**Employee self-service intake (2 units):**
- Add self-service entry point: a "Submit Correction" button accessible from the employee's own profile view (if such a view exists in the portal)
- Routes into `submit_sensitive_change_request` with `initiator_type="employee"`
- Employee sees their own pending requests and status — read-only
- If no employee profile view exists yet, note as future hook and skip UI; backend already handles employee-initiated path via `initiator_type`

**Sentry instrumentation verification (1 unit):**
- Read `hrms/api/payroll_compensation.py`
- Confirm every `@frappe.whitelist()` function has `set_backend_observability_context(...)` as first meaningful line
- Run: `python -c "import ast; ast.parse(open('hrms/api/payroll_compensation.py').read()); print('Syntax OK')"`

**L1–L4 certification (4 units):**
- See Certification Coverage Contract section
- Run all 6 L3 scenarios manually
- Capture pass/fail per scenario
- Write results to `tmp/s113-certification-results.md`

**Closeout (1 unit):**
- Final TypeScript build clean
- Commit with sprint tag
- PR creation

---

## Sentry Observability Contract

**Backend (mandatory for every endpoint):**

```python
from hrms.utils.sentry import set_backend_observability_context

@frappe.whitelist()
def my_endpoint(...):
    set_backend_observability_context(
        module="payroll",
        action="<function_name>",
        mutation_type="create" | "update" | "delete" | "read",
    )
```

Every `@frappe.whitelist()` function in `payroll_compensation.py` MUST have this as its first meaningful line. No exceptions.

For try/except blocks that catch silently, `frappe.log_error()` feeds Sentry automatically via monkey-patch — no extra code needed.

**Frontend:**
`@sentry/nextjs` auto-instruments Next.js API routes. No extra code needed in route handlers. For client-side manual captures, import from `@/lib/sentry-observability`.

**Gate:** Before closing Phase 3, agent must count `@frappe.whitelist()` functions in `payroll_compensation.py` and confirm that count equals the number of `set_backend_observability_context` calls.

---

## L3 Workflow Scenarios

These scenarios are pre-written. An executing agent MUST run them verbatim — agents do NOT invent test scenarios.

| # | User | Action | Expected Outcome | Failure Means |
|---|------|--------|------------------|---------------|
| L3-1 | test.hr@bebang.ph | Navigate to `/dashboard/hr/payroll/compensation-setup` | Dense compensation grid loads with employee list, salary structures, current amounts visible | Compensation query broken or route missing |
| L3-2 | test.hr@bebang.ph | In compensation grid, select employee ARRABIS → click Edit → change basic salary to 20000, enter reason "Annual increase", effective_date 2026-04-01 → click Save | Change saved, history entry created, row shows approval badge "Pending HR Head" | `update_compensation` endpoint broken or approval status not set |
| L3-3 | test.hr@bebang.ph | Navigate to `/dashboard/hr/payroll/sensitive-changes` | Queue page loads (empty or with pending requests), "New Request" button visible | Route missing or query broken |
| L3-4 | test.hr@bebang.ph | Click "New Request" → select employee ARRABIS → select field "bank_account_number" → enter new value + reason + proof → effective_date = next cutoff → submit | Request created with status "Pending Finance Approval", appears in queue | `submit_sensitive_change_request` broken or wrong initiator routing |
| L3-5 | test.finance@bebang.ph | Navigate to `/dashboard/hr/payroll/sensitive-changes` → find the pending bank change for ARRABIS → click Approve → add remarks → confirm | Status changes to "Pending HR Activation" | Dual-control approve broken or Finance user cannot see queue |
| L3-6 | test.hr@bebang.ph | In sensitive-changes queue, find the ARRABIS change at "Pending HR Activation" → click Activate | Status changes to "Approved", bank account field written to employee record, immutable history entry visible with full audit trail (initiator, Finance approver, HR activator, timestamps, values) | Activation endpoint broken or history not written |

**Bonus scenario (if employee self-service is built in Phase 3):**

| # | User | Action | Expected Outcome | Failure Means |
|---|------|--------|------------------|---------------|
| L3-7 | test employee account | Submit a bank correction with proof attachment from employee profile | Request appears in sensitive-changes queue with status "Pending HR Verification", employee sees "Submitted, Pending HR Review" | Self-service intake broken |

---

## Certification Coverage Contract

An executing agent MUST obtain a passing result for all four levels before declaring Phase 3 complete.

| Level | What | Gate |
|-------|------|------|
| L1 — Syntax | `python -m py_compile hrms/api/payroll_compensation.py` passes | Zero errors |
| L2 — Build | `npx tsc --noEmit` + `npm run build` in bei-tasks | Zero errors |
| L3 — Workflow | All 6 L3 scenarios above executed with real user sessions (test accounts) | All 6 pass |
| L4 — Sentry | Count `@frappe.whitelist()` functions = count `set_backend_observability_context` calls | Numbers match |

Results written to `tmp/s113-certification-results.md` before closeout commit.

---

## Autonomous Execution Contract

An agent executing this sprint MUST:

1. Work on branch `s114-payroll-compensation-sensitive` only.
2. Not modify any file listed in "Files this sprint does NOT touch."
3. Not extend `payroll.py` or `enrichment.py` for compensation logic.
4. Not implement approval logic in `enrichment.py` — call into `payroll_compensation.py` if needed.
5. Not use free-text inputs for contract-backed fields (D3).
6. Not allow single-actor activation of sensitive changes (D9).
7. Not default effective date to current cutoff without exception gate (D32).
8. Not skip Sentry instrumentation on any endpoint.
9. Stop and present options (do not silently pivot) if any planned approach fails.
10. Write all research, audit findings, and test results to `tmp/` files before discussing in conversation.
11. After 3 failed attempts at the same approach: stop, summarize, ask user for guidance.

---

## Status Reconciliation Contract

At the start of each work session on this sprint, the agent MUST:

1. Run `git status` and `git log --oneline -5` on branch `s114-payroll-compensation-sensitive`.
2. Check which phase files exist to determine current progress.
3. If `payroll_compensation.py` exists, count its `@frappe.whitelist()` functions to know Phase 1/2 state.
4. If `compensation-setup/page.tsx` exists, check its last modification timestamp.
5. Read `tmp/s113-certification-results.md` if it exists to see prior test results.
6. Reconcile against Phase Budget Contract before writing any new code.

Do NOT trust conversation memory for specific progress data after compaction. Re-read files.

---

## Anti-Rewind Protection

This sprint owns these files exclusively. If a sibling sprint (S112 or S114) accidentally creates a file in this sprint's namespace, this sprint's agent MUST:
1. Stop immediately.
2. Report the conflict to Sam Karazi.
3. Do NOT overwrite the sibling file without explicit instruction.

If this sprint's files are found in a partial state (e.g., `payroll_compensation.py` exists but has fewer endpoints than the spec), the agent MUST read the existing file first, note what is already implemented, and continue from where it left off — never rewrite from scratch without checking.

---

## Execution Workflow Reference

This sprint follows the BEI standard execution loop:

```
Boot Sequence → Phase 1 (vertical slice) → Build Gate → Phase 2 (vertical slice) → Build Gate → Phase 3 (certification + closeout)
```

Each phase ends with a git commit on `s114-payroll-compensation-sensitive`. Phase 3 ends with a PR against `production`.

Build gates:
```bash
# Backend
python -m py_compile hrms/api/payroll_compensation.py

# Frontend
cd F:/Dropbox/Projects/bei-tasks
npx tsc --noEmit
npm run build
```

No phase commit is made if a build gate fails.

---

## Signoff Model

**Single owner:** Sam Karazi (sam@bebang.ph), CEO, Bebang Enterprise Inc.

All design decisions not explicitly covered by the 12 locked decisions from S083 require Sam's approval before implementation. No autonomous scope expansion.

Sprint is complete when:
- All 6 L3 scenarios pass
- L1, L2, L4 certification gates pass
- PR created against `production`
- Sam reviews and merges

---

## Closeout Checklist

- [ ] `hrms/api/payroll_compensation.py` created with all endpoints, Sentry on every endpoint
- [ ] `../bei-tasks/app/dashboard/hr/payroll/compensation-setup/page.tsx` created
- [ ] `../bei-tasks/app/dashboard/hr/payroll/sensitive-changes/page.tsx` created
- [ ] `../bei-tasks/lib/queries/hr-payroll-compensation.ts` created
- [ ] Duplication audit written to `tmp/s113-duplication-audit.md`
- [ ] L1 gate: Python syntax check passes
- [ ] L2 gate: TypeScript build passes
- [ ] L3 gate: All 6 scenarios pass with real test accounts
- [ ] L4 gate: Sentry count matches endpoint count
- [ ] Certification results written to `tmp/s113-certification-results.md`
- [ ] No files outside the owned list were modified
- [ ] PR created against `production` with this plan referenced in PR body
- [ ] Sam Karazi notified for review

---

*Sprint S114 | S083-replacement group | Parallel to S112 and S114 | Owner: Sam Karazi | Created: 2026-03-24*
