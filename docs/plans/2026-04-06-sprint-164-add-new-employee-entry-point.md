---
sprint_id: S164
display: Sprint 164
title: "Add New Employee Entry Point on Employee Master"
branch: s164-add-new-employee-entry-point
status: PR_CREATED
planned_date: 2026-04-06
completed_date: null
depends_on: S160
total_work_units: 28
amendment_version: 1
amendment_date: 2026-04-06
amendment_reason: "/audit-plan-bei-erp found 13 confirmed blockers + 6 new gaps. All amendments applied inline. No features dropped. See AUDIT: 13 BLOCKERS RESOLVED section at bottom."
execution_summary: "Phases 0-4 implemented on branch s164-add-new-employee-entry-point (both repos). Phase verification scripts green (80 checks passed across 5 phases). Agent STOPS after PR creation per S099 PR-handoff. L3 tests deferred to a fresh session per S099 L3 handoff rule."
frontend_pr: "BEI-Tasks#347"
backend_pr: "hrms#463"
registry_row: "| `S164` | Sprint 164 | `s164-add-new-employee-entry-point` | — | PLANNED — \"Add New Employee\" dialog on Employee Master Dashboard. Auto-generates Employee ID + Bio ID, uploads Gov ID files, best-effort ADMS auto-enrollment on branch bio device, Google Chat notification. Surfaces \"Missing Bio Device\" metric card and red \"No Bio ID\" badge on rows. | `docs/plans/2026-04-06-sprint-164-add-new-employee-entry-point.md` |"
---

# S164: Add New Employee Entry Point on Employee Master

## Context

HR has no way to create a new employee from `my.bebang.ph`. Today they must use one of two friction-heavy routes:

1. **Frappe Desk** at `hq.bebang.ph/app/employee/new` — bypasses Bio ID validation, skips ADMS enrollment, no Google Chat notification. Employees created here end up without a biometric device assignment and have to be manually enrolled later (the root cause of the current "missing bio device" data gap the user is now asking us to surface).
2. **BEI Onboarding Request `new_hire`** — designed for employees to self-submit their own data during onboarding, not for HR to punch in a quick record for someone who started today.

Per the CEO directive (2026-04-06): HR should click a single button on the Employee Master Dashboard, type in the basics, and have the system handle everything else — employee ID generation, Bio ID generation, device enrollment, file uploads, notifications.

**Expected outcome:** A new employee created via this flow appears in the Employee Master table within one second, has a valid `BEI-EMP-YYYY-NNNNN` ID, has a valid sequential `9XXXXXX` Bio ID, is enrolled on the correct branch's bio device (or visibly flagged if no device is mapped), has any provided Gov ID files attached, and triggers a Google Chat notification to the HR space.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

The user has explicitly identified three pain points in the current employee creation workflow:

1. **No entry point on the employee-facing portal** — HR works from `my.bebang.ph`, not Frappe Desk. They should not have to switch tools to do the most basic HR task.
2. **ADMS enrollment is manual and forgotten** — Employees created via Desk never appear on the biometric device. The `Employee Master SSOT` (`memory/MEMORY.md` lesson #8) says all 696 current employees have Bio IDs, but the current codebase has no automation that enrolls new employees on their branch's device after creation. This has to be fixed at the creation step, not layered on later.
3. **No visibility into employees missing bio devices** — Once this flow exists, HR still needs to see legacy employees who lack a Bio ID or whose branch has no mapped device, so they can remediate.

### Why this architecture

**A new `create_employee_direct` endpoint instead of reusing `_create_employee_from_new_hire_request`:**

- The existing new_hire flow (`hrms/api/onboarding.py:802-892`) requires `department`, `designation`, `date_of_joining`, and `new_attendance_device_id` to all be provided by the caller. The CEO specified that only `first_name`, `last_name`, `date_of_birth`, `gender`, `branch`, and `company` should be mandatory. Relaxing the new_hire validation would break the existing onboarding workflow used by employee self-service.
- Instead, we extract the shared helpers (`generate_bei_employee_id`, `_notify_new_employee_created`) into reusable modules and build a thin new endpoint that reuses them. This is an EXTEND (shared helpers) + BUILD (new endpoint) hybrid per the Duplication Audit classification.

**Why auto-generate Bio ID instead of letting HR type it:**

The CEO explicitly directed: *"BIO ID should always be generated"* (AskUserQuestion answer, 2026-04-06). Rationale: HR currently tracks the "next available Bio ID" on a paper log, which is error-prone and has caused duplicate assignments in the past. The system already has the ground truth in `Employee.attendance_device_id` — it should compute the next available itself. A new helper `generate_next_bio_id()` in `hrms/utils/bio_id.py` uses `SELECT MAX(...) FOR UPDATE` to prevent concurrent collision.

**Why ADMS enrollment is best-effort, not a blocking gate:**

Per the CEO answer (2026-04-06): employees should always be created even if ADMS is unreachable or the branch has no mapped device. The alternative (blocking creation until ADMS sync succeeds) creates a worse failure mode — HR can't onboard someone because a biometric device is offline. Instead, failed enrollments are surfaced via:
- Toast message in the dialog ("ADMS enrollment pending — retry from Transfers")
- A new red "No Bio ID" badge in the employee row (visible across the table)
- A new "Missing Bio Device" metric card/chip count above the table

**Why we extract `generate_bei_employee_id` now:**

The existing inline employee ID logic at `hrms/api/onboarding.py:828-847` uses `FOR UPDATE` locking and is correct. Duplicating it would create two sources of truth for the ID sequence — a DM-5 (stored duplicates) anti-pattern. Extracting it to `hrms/utils/employee_id.py` and having both endpoints call the same helper guarantees sequence integrity across the two creation paths.

### Key trade-off decisions

| Decision | Chosen | Rejected | Reason |
|---|---|---|---|
| Bio ID entry | Always auto-generated | HR types it manually | CEO directive; eliminates duplicate Bio ID incidents |
| Date of Joining default | Today if blank | Leave null | Common case is "HR opens dialog on employee's first day" |
| ADMS enrollment on failure | Continue, flag row | Block creation | Can't hold up HR because device is offline |
| Mandatory company field | Yes, dropdown | Default to Bebang Enterprise Inc. | BEI vs BKI are separate legal entities; must be explicit (memory `bki-bei-entity-structure.md`) |
| New endpoint vs extend onboarding | New endpoint | Relax onboarding validation | Don't break the self-service new_hire flow |
| Gov ID files | Collapsible section, optional | Required | CEO said "if available" — most new hires don't have all 4 on day one |

### Known limitations and their mitigations

- **`DEVICE_TO_STORE` is a hardcoded Python dict** (`hrms/utils/device_mapping.py:8-57`). If a branch is added in Frappe but not added to this dict, the new employee's ADMS enrollment will silently skip. **Mitigation:** surface this via the new "Missing Bio Device" metric card so HR can see and escalate. (Addressing the dict-vs-DocType debt is out of scope — logged as a future sprint.)
- **`DEVICE_TO_STORE` key casing is unverified vs `Branch.name` casing.** A Branch named "Brittany Office" in Frappe may be mapped as "BRITTANY OFFICE" in the dict. **Mitigation:** `_enroll_employee_on_adms_for_branch` MUST do a case-insensitive lookup (see Task 2.2 for exact code).
- **`hr_reports.py` is currently in a pre-S160-revert state** (per 2026-04-06 system reminder). The file no longer has `profile_completion`, `missing_dob`, `missing_designation`, `missing_salary`, or the `exception` filter parameter. This sprint adds the minimum delta (`attendance_device_id` to fields list, `has_bio_id` per row, `missing_bio_id` in summary) without touching the other previously-shipped metrics — if they need to come back, that's a separate sprint.
- **ADMS `preflight_check_enrollment` validates Bio IDs against a static CSV snapshot** (`hrms/utils/adms_validation.py:414-451`). A freshly generated Bio ID is not in the CSV, so preflight will always reject new-create attempts. **Mitigation:** Skip `preflight_check_enrollment` entirely for this flow. The reverse lookup of `DEVICE_TO_STORE` is the authoritative device-to-branch mapping and is sufficient to decide whether the device exists. See Task 2.2 for the exact call pattern.
- **ORM-based Employee insert vs MEMORY.md lesson #6.** Memory says "NEVER use ORM for Employee records — use direct SQL." BUT the existing `_create_employee_from_new_hire_request` at `onboarding.py:896` uses `employee_doc.insert(ignore_permissions=True)` and is in active production use. This plan follows the same ORM pattern for consistency and because the existing flow works. **Mitigation:** If the execution agent hits an ORM failure during testing, fall back to direct SQL per `memory/frappe-lessons.md`. This is a known-risk inheritance, not a new risk.
- **Frontend doesn't have react-hook-form in the existing dialog pattern.** The existing `employee-detail-dialog.tsx` uses plain `useState` + submit-time validation. The new dialog follows the same pattern for consistency (verified `employee-detail-dialog.tsx:52, 671-673` for RBAC + form state pattern).
- **`getCsrfToken` is privately duplicated in TWO existing files** (`hr-employee-detail.ts:132` and `hr-payroll-compensation.ts:202`). Neither exports it. This sprint extracts it to `lib/frappe-csrf.ts` in Phase 0 and updates BOTH existing consumers in the same PR (NG1).
- **`_get_adms_config` is private (underscore-prefixed) with 4 same-file callers** in `transfer_requests.py` (lines 1015, 1162, 1581, 1741). Cross-module import of a private helper violates Python convention. This sprint extracts it to `hrms/utils/adms_config.py` in Phase 0 and updates all 4 existing callers in the same PR (NG5).

### Source references

- Existing employee creation: `hrms/api/onboarding.py:802-892` (`_create_employee_from_new_hire_request`)
- Existing employee ID generation: `hrms/api/onboarding.py:828-847`
- Existing Chat notification helper: `hrms/api/onboarding.py:900-926` (`_notify_new_employee_created`)
- Existing ADMS command queuing: `hrms/api/transfer_requests.py:733` (`_queue_adms_command`)
- Existing ADMS command builder: `hrms/api/transfer_requests.py:782` (`_build_update_command`)
- Existing ADMS preflight: `hrms/utils/adms_validation.py:414` (`preflight_check_enrollment`)
- Device mapping: `hrms/utils/device_mapping.py:8-57` (`DEVICE_TO_STORE`)
- Existing dialog pattern: `app/dashboard/hr/employee-master/employee-detail-dialog.tsx` (shadcn Dialog + useState)
- RBAC pattern: `app/dashboard/hr/employee-master/employee-detail-dialog.tsx:52, 671-673` (`ROLES`, `hasRole`, `useEmployee`)
- File upload helper: `lib/frappe-upload.ts` (`uploadFrappeFile`)
- Mutation/CSRF pattern: `lib/queries/hr-employee-detail.ts` (`getCsrfToken`)
- HrPageHeader action shape: `components/hr/hr-page-header.tsx:10-17` (supports `onClick`, `icon`, `variant`)
- Employee Master SSOT: `memory/MEMORY.md` lesson #8, max Bio ID 9001881, next = 9001882
- CEO clarification (2026-04-06): auto-generate Bio ID; best-effort ADMS; default DOJ to today; add "Missing Bio Device" label + red row badge
- BKI vs BEI separation: `memory/bki-bei-entity-structure.md`

---

## Requirements Regression Checklist

The executing agent MUST verify each item before writing code. Any NO is a HARD BLOCKER — stop and ask.

- [ ] Is the branch `s164-add-new-employee-entry-point` checked out in both `hrms` and `bei-tasks` repos from `origin/production` (hrms) and `origin/main` (bei-tasks)?
- [ ] Is the mandatory field set exactly `first_name, last_name, date_of_birth, gender, branch, company`? (CEO directive — no more, no less)
- [ ] Is Bio ID **always** auto-generated by the backend? (Never visible to HR, never typed, never optional)
- [ ] Is the employee ID format `BEI-EMP-YYYY-NNNNN` using the extracted `generate_bei_employee_id()` helper? (Not a new sequence)
- [ ] Is the Bio ID format `9XXXXXX` (regex `^9\d{6}$`), generated as `max(existing) + 1`, with `FOR UPDATE` locking?
- [ ] Is ADMS enrollment **best-effort** (wrapped in try/except, never blocks employee creation)?
- [ ] Does the endpoint call `set_backend_observability_context(module="hr", action="create_employee_direct", mutation_type="create")` as its first meaningful line? (DM-7)
- [ ] Does the endpoint call `frappe.has_permission("Employee", "create", throw=True)` after observability context?
- [ ] Does the endpoint reuse `_notify_new_employee_created()` from onboarding.py (after refactoring to keyword args with optional `request_name`)?
- [ ] Does the frontend dialog hide the "Add New Employee" button for non-HR users using `hasRole(roles, [ROLES.HR_MANAGER, ROLES.SYSTEM_MANAGER, ROLES.ADMINISTRATOR])`?
- [ ] Does the backend endpoint also enforce `frappe.has_permission("Employee", "create")` (not just the frontend gate)?
- [ ] Is `date_of_joining` defaulted to `today()` if HR leaves it blank? (CEO directive)
- [ ] Are Gov ID files optional (HR can create without any files)?
- [ ] Does the "Missing Bio Device" metric card appear in the Employee Master metric strip above the table?
- [ ] Does a red "No Bio ID" badge appear in employee rows where `attendance_device_id` is empty?
- [ ] Is the existing onboarding.py `new_hire` flow still fully functional after refactoring the ID generator and notification helper?
- [ ] **[AUDIT B1]** Does the ADMS helper import `_get_adms_config` (NOT `_load_adms_config` — that function does not exist)?
- [ ] **[AUDIT B2]** Does the call to `preflight_check_enrollment` (if any) pass `employee_name` as the third tuple element, NOT `branch`?
- [ ] **[AUDIT B3/B4]** Does `_enroll_employee_on_adms_for_branch` SKIP `preflight_check_enrollment` entirely? (The preflight validates against a static CSV snapshot that excludes freshly generated Bio IDs, so it would always reject new-create attempts. The `DEVICE_TO_STORE` reverse lookup is the authoritative check.)
- [ ] **[AUDIT B5]** Is `getCsrfToken` imported from `@/lib/frappe-csrf` (the NEW shared util created in Phase 0), NOT from `hr-employee-detail.ts` (which does not export it)?
- [ ] **[AUDIT B6]** Does the refactored `_notify_new_employee_created` accept an optional `request_name: str | None = None` parameter, conditionally appending "Onboarding Request: {name}" only when provided?
- [ ] **[AUDIT B7]** Do L3 Scenarios 7 and 8 use `test.crew1@bebang.ph` (NOT `test.crew1@bebang.ph` which does not exist)?
- [ ] **[AUDIT B8]** Does the dialog reuse the existing `<BranchSelector>` and `<DepartmentSelector>` from `@/components/shared` (NOT new duplicate hooks)?
- [ ] **[AUDIT B9]** Is gender NOT hardcoded to `("Male", "Female")` in backend validation? Does the frontend populate options from `frappe.get_all("Gender", pluck="name")`?
- [ ] **[AUDIT B10]** Do all `uploadFrappeFile` calls use `isPrivate: true` (boolean), NOT `is_private: 1` (snake_case)?
- [ ] **[AUDIT B11]** Are `hr_reports.py` edit instructions using grep anchors (e.g., "insert after `\"reports_to\",`"), NOT line numbers?
- [ ] **[AUDIT B13]** Are the SPRINT_REGISTRY.md and plan YAML closeout updates committed to the `s164-add-new-employee-entry-point` branch (NOT directly to `production`)?
- [ ] **[AUDIT NG5]** Does the ADMS config helper import from `hrms.utils.adms_config` (the NEW shared util extracted in Phase 0), NOT from `hrms.api.transfer_requests`?
- [ ] **[AUDIT R2]** Does `_enroll_employee_on_adms_for_branch` use CASE-INSENSITIVE matching when reverse-looking-up device SN by branch name?

---

## Files to Modify

### Create (hrms)

| # | File | Change | Phase |
|---|------|--------|-------|
| 1 | `hrms/utils/adms_config.py` | **NEW (Phase 0)** — extract `_get_adms_config()` from `transfer_requests.py` as public `get_adms_config()`. Resolves audit NG5. | 0 |
| 2 | `hrms/utils/employee_id.py` | NEW — extract `generate_bei_employee_id()` from onboarding.py | 1 |
| 3 | `hrms/utils/bio_id.py` | NEW — `generate_next_bio_id()` with `FOR UPDATE` lock | 1 |
| 4 | `hrms/api/employee_create.py` | NEW — `create_employee_direct()` whitelisted endpoint + ADMS helper | 2 |

### Modify (hrms)

| # | File | Change | Phase |
|---|------|--------|-------|
| 5 | `hrms/api/transfer_requests.py` | **Phase 0** — replace `_get_adms_config()` body with `from hrms.utils.adms_config import get_adms_config`. Update all 4 in-file callers (lines 1015, 1162, 1581, 1741). Resolves audit NG5. | 0 |
| 6 | `hrms/api/onboarding.py` | Refactor — import and call `generate_bei_employee_id()`; change `_notify_new_employee_created()` signature to keyword args WITH optional `request_name` (resolves audit B6); update its existing caller to pass `request_name=req.name` | 1 |
| 7 | `hrms/api/hr_reports.py` | **Phase 2 (moved from Phase 4 per audit B12)** — Add `attendance_device_id` to fields list; add `has_bio_id` per row; add `missing_bio_id` to summary. Use grep anchors, NOT line numbers (resolves audit B11/NG6). | 2 |

### Create (bei-tasks)

| # | File | Change | Phase |
|---|------|--------|-------|
| 8 | `lib/frappe-csrf.ts` | **NEW (Phase 0)** — extract `getCsrfToken()` helper. Resolves audit B5/NG1. | 0 |
| 9 | `components/shared/company-selector.tsx` | NEW — shared `<CompanySelector>` component (pattern from existing `branch-selector.tsx`). Resolves audit B8/NG4. | 3 |
| 10 | `components/shared/designation-selector.tsx` | NEW — shared `<DesignationSelector>` component. Resolves audit B8/NG4. | 3 |
| 11 | `components/shared/employment-type-selector.tsx` | NEW — shared `<EmploymentTypeSelector>` component. Resolves audit B8/NG4. | 3 |
| 12 | `lib/queries/hr-master-data.ts` | NEW — `useGenderOptions()` hook (from `frappe.get_all("Gender")`). Resolves audit B9. | 3 |
| 13 | `lib/queries/hr-employee-create.ts` | NEW — `useCreateEmployeeMutation()` + types + `PROOF_FIELD_MAP` | 3 |
| 14 | `app/dashboard/hr/employee-master/new-employee-dialog.tsx` | NEW — full form dialog with shadcn Dialog + sectioned fields, REUSES existing `<BranchSelector>` and `<DepartmentSelector>` (resolves audit B8) | 4 |

### Modify (bei-tasks)

| # | File | Change | Phase |
|---|------|--------|-------|
| 15 | `lib/queries/hr-employee-detail.ts` | **Phase 0** — replace private `getCsrfToken()` at line 132 with `import { getCsrfToken } from "@/lib/frappe-csrf"`. Resolves audit B5/NG1. | 0 |
| 16 | `lib/queries/hr-payroll-compensation.ts` | **Phase 0** — replace private `getCsrfToken()` at line 202 with `import { getCsrfToken } from "@/lib/frappe-csrf"`. Resolves audit NG1. | 0 |
| 17 | `app/dashboard/hr/employee-master/page.tsx` | Add "Add New Employee" button in header actions, RBAC gate, "Missing Bio Device" MetricCard, red "No Bio ID" badge in employee row, mount `<NewEmployeeDialog>` | 4 |
| 18 | `lib/queries/hr-reports.ts` | Type additions: `attendance_device_id`, `has_bio_id` on `EmployeeMasterlist`, `missing_bio_id` on summary | 4 |

---

## Phase 0: Audit-Derived Prep Work (3 units)

**Purpose:** Resolve audit findings NG1, NG5, B5 by extracting duplicated helpers BEFORE the main sprint work touches them. This reduces the fix surface for every downstream task and converts existing duplication debt into shared utils in the same PR.

### Task 0.1: Extract `getCsrfToken` to shared util (1 unit)

**MUST_MODIFY:** `lib/frappe-csrf.ts` (new file)
**MUST_MODIFY:** `lib/queries/hr-employee-detail.ts`
**MUST_MODIFY:** `lib/queries/hr-payroll-compensation.ts`
**MUST_CONTAIN:** `export function getCsrfToken` in `lib/frappe-csrf.ts`
**MUST_CONTAIN:** `from "@/lib/frappe-csrf"` in both existing consumer files
**MUST_NOT_CONTAIN:** `function getCsrfToken` in either existing consumer file (it must be imported, not redefined)

1. Create `F:\Dropbox\Projects\bei-tasks\lib\frappe-csrf.ts`:
   ```ts
   /**
    * Shared helper to read Frappe CSRF token from the frappe-csrf cookie.
    * Extracted from hr-employee-detail.ts and hr-payroll-compensation.ts
    * in S164 Phase 0 to eliminate duplication (audit NG1).
    */
   export function getCsrfToken(): string {
     if (typeof document === "undefined") return "";
     const match = document.cookie.match(/frappe_csrf_token=([^;]+)/);
     return match ? decodeURIComponent(match[1]) : "";
   }
   ```
   (Verify the exact cookie name + decode logic by reading the current private helper at `lib/queries/hr-employee-detail.ts:132` before copying — preserve existing behavior exactly.)

2. In `lib/queries/hr-employee-detail.ts`: delete the private `function getCsrfToken()` at line 132. Add `import { getCsrfToken } from "@/lib/frappe-csrf";` near the top. Verify all existing call sites still work.

3. In `lib/queries/hr-payroll-compensation.ts`: delete the private `function getCsrfToken()` at line 202. Add the same import.

**HARD BLOCKER:** If the `document.cookie` parsing logic differs between the two existing implementations, STOP and ask the user which one to preserve. Do NOT pick one arbitrarily.

### Task 0.2: Extract `_get_adms_config` to `hrms/utils/adms_config.py` (2 units)

**MUST_MODIFY:** `hrms/utils/adms_config.py` (new file)
**MUST_MODIFY:** `hrms/api/transfer_requests.py`
**MUST_CONTAIN:** `def get_adms_config` in `hrms/utils/adms_config.py` (public, no underscore prefix)
**MUST_CONTAIN:** `from hrms.utils.adms_config import get_adms_config` in `transfer_requests.py`
**MUST_NOT_CONTAIN:** `def _get_adms_config` in `transfer_requests.py` (must be removed, not kept as alias)

1. Read `hrms/api/transfer_requests.py` starting at `_get_adms_config` (defined at line 698, body spans ~20 lines). Copy the body verbatim into `hrms/utils/adms_config.py` as a public `get_adms_config()` function with the same signature and return type.

2. In `transfer_requests.py`: delete lines 698-~720 (the `_get_adms_config` definition). Add `from hrms.utils.adms_config import get_adms_config` near the top imports.

3. Update all 4 in-file callers to call `get_adms_config()` (public name) instead of `_get_adms_config()`. Callers per audit verification are at lines **1015, 1162, 1581, 1741** — verify with `grep -n "_get_adms_config\|get_adms_config" transfer_requests.py` after editing.

4. Run a quick smoke test: `python -c "from hrms.utils.adms_config import get_adms_config; print(get_adms_config())"` should return the config dict without errors.

**HARD BLOCKER:** All 4 existing callers in `transfer_requests.py` MUST be updated in the same edit. Leaving stale `_get_adms_config()` calls will break the existing transfer_requests flow. If the agent cannot locate all 4, STOP and run `grep -c _get_adms_config hrms/api/transfer_requests.py` to verify zero stale references remain.

---

## Phase 1: Extract Shared Helpers (8 units)

### Task 1.1: Create `hrms/utils/employee_id.py` (2 units)

**MUST_MODIFY:** `hrms/utils/employee_id.py` (new file)
**MUST_CONTAIN:** `def generate_bei_employee_id() -> str:`
**MUST_CONTAIN:** `FOR UPDATE`
**MUST_CONTAIN:** `BEI-EMP-`

Copy the ID generation body verbatim from `hrms/api/onboarding.py:828-847` into a new function:

```python
def generate_bei_employee_id() -> str:
    """Generate the next sequential BEI-EMP-YYYY-NNNNN employee ID.
    Uses FOR UPDATE lock to prevent concurrent collision."""
    # Paste lines 828-847 from onboarding.py verbatim
```

### Task 1.2: Refactor `hrms/api/onboarding.py` to call the new helper (2 units)

**MUST_MODIFY:** `hrms/api/onboarding.py`
**MUST_CONTAIN:** `from hrms.utils.employee_id import generate_bei_employee_id`
**MUST_CONTAIN:** `generate_bei_employee_id()`

Replace the inline ID generation at lines 828-847 with a single call to `generate_bei_employee_id()`. Preserve all surrounding context (session locking, logging). Verify with pytest or a manual Desk submission that the existing new_hire flow still produces the same ID format.

**HARD BLOCKER:** If you cannot confirm the existing new_hire flow still works after this refactor, STOP and restore the original code. Do NOT proceed to Phase 2 with a broken onboarding flow. (Source: Duplication Audit — EXTEND classification)

### Task 1.3: Create `hrms/utils/bio_id.py` (2 units)

**MUST_MODIFY:** `hrms/utils/bio_id.py` (new file)
**MUST_CONTAIN:** `def generate_next_bio_id() -> str:`
**MUST_CONTAIN:** `FOR UPDATE`
**MUST_CONTAIN:** `^9\\d{6}$` (regex string)

```python
import re
import frappe

BIO_ID_RE = re.compile(r"^9\d{6}$")

def generate_next_bio_id() -> str:
    """Return next sequential Bio ID in 9XXXXXX format.
    Uses SELECT MAX(...) FOR UPDATE to prevent concurrent collision.
    Starts at 9000003 if no valid Bio IDs exist yet."""
    result = frappe.db.sql("""
        SELECT MAX(CAST(attendance_device_id AS UNSIGNED)) AS max_bio
        FROM `tabEmployee`
        WHERE attendance_device_id REGEXP '^9[0-9]{6}$'
        FOR UPDATE
    """, as_dict=True)
    current_max = (result[0].get("max_bio") if result else None) or 9000002
    next_id = str(current_max + 1)
    if not BIO_ID_RE.match(next_id):
        frappe.throw(f"Bio ID generator overflow: computed {next_id}")
    # Double-check uniqueness (paranoia — FOR UPDATE should prevent this)
    if frappe.db.exists("Employee", {"attendance_device_id": next_id}):
        frappe.throw(f"Generated Bio ID {next_id} already exists")
    return next_id
```

### Task 1.4: Refactor `_notify_new_employee_created()` signature (2 units)

**MUST_MODIFY:** `hrms/api/onboarding.py`
**MUST_CONTAIN:** `def _notify_new_employee_created(`
**MUST_CONTAIN:** `employee_id:`
**MUST_CONTAIN:** `source:`
**MUST_CONTAIN:** `request_name: str | None = None`
**MUST_CONTAIN:** `if request_name:` (conditional append of Onboarding Request line)

**AUDIT B6 FIX:** The current implementation at `onboarding.py:922` emits `f"Onboarding Request: {req.name}"` as part of the Chat payload. The refactored signature MUST preserve this for the existing onboarding flow by accepting an optional `request_name` and conditionally appending the line. Plain keyword-only refactor without `request_name` would silently drop the line and break the "preserve the Chat payload shape" promise.

Change the signature to keyword-only args (find the function via grep anchor `def _notify_new_employee_created` — line numbers may have drifted):

```python
def _notify_new_employee_created(
    *,
    employee_id: str,
    employee_name: str,
    branch: str | None,
    designation: str | None,
    bio_id: str,
    source: str,  # "onboarding_approval" | "employee_master_dashboard"
    approver_email: str,
    request_name: str | None = None,  # AUDIT B6: preserve Onboarding Request line for existing flow
) -> None:
    # ... build message body ...
    lines = [
        f"New employee created: {employee_name}",
        f"Employee ID: {employee_id}",
        f"Bio ID: {bio_id}",
        f"Branch: {branch or '—'}",
        f"Designation: {designation or '—'}",
        f"Approver: {approver_email}",
        f"Source: {source}",
    ]
    if request_name:
        lines.append(f"Onboarding Request: {request_name}")
    # ... existing Chat send logic ...
```

Update the existing caller inside `approve_and_apply` (find via grep anchor `_notify_new_employee_created(req` — previously ~line 1121 but refresh). The existing caller must pass `request_name=req.name` and `source="onboarding_approval"`. The new `create_employee_direct` caller in Phase 2 will pass `source="employee_master_dashboard"` and omit `request_name`.

**HARD BLOCKER:** Before committing this refactor, verify the existing onboarding flow's Chat notification still contains the "Onboarding Request:" line. Send a test new_hire onboarding through the existing flow and inspect the actual Chat payload. If the line is missing, STOP and fix before Phase 2.

---

## Phase 2: Backend API Endpoint + hr_reports.py Delta (7 units)

### Task 2.1: Create `hrms/api/employee_create.py` with `create_employee_direct()` (4 units)

**MUST_MODIFY:** `hrms/api/employee_create.py` (new file)
**MUST_CONTAIN:** `@frappe.whitelist()`
**MUST_CONTAIN:** `def create_employee_direct(`
**MUST_CONTAIN:** `set_backend_observability_context(module="hr", action="create_employee_direct", mutation_type="create")`
**MUST_CONTAIN:** `frappe.has_permission("Employee", "create", throw=True)`
**MUST_CONTAIN:** `generate_bei_employee_id()`
**MUST_CONTAIN:** `generate_next_bio_id()`
**MUST_CONTAIN:** `_notify_new_employee_created(`
**MUST_CONTAIN:** `_enroll_employee_on_adms_for_branch(`
**MUST_NOT_CONTAIN:** `gender in ("Male", "Female")` (AUDIT B9 — no hardcoded gender whitelist)
**MUST_NOT_CONTAIN:** `gender not in` (AUDIT B9 — no gender whitelist of any kind)

Function signature:

```python
@frappe.whitelist()
def create_employee_direct(
    # mandatory
    first_name: str,
    last_name: str,
    date_of_birth: str,
    gender: str,
    branch: str,
    company: str,
    # optional
    middle_name: str | None = None,
    designation: str | None = None,
    department: str | None = None,
    date_of_joining: str | None = None,
    employment_type: str | None = None,
    personal_email: str | None = None,
    cell_number: str | None = None,
    tin_number: str | None = None,
    sss_number: str | None = None,
    philhealth_number: str | None = None,
    pagibig_number: str | None = None,
) -> dict:
```

Body sequence (MUST be in this exact order):

1. `set_backend_observability_context(module="hr", action="create_employee_direct", mutation_type="create")`
2. `frappe.has_permission("Employee", "create", throw=True)`
3. Mandatory presence check on the 6 required fields → `frappe.throw` with user-facing message
4. **[AUDIT B9 — DO NOT hardcode gender]** Validate gender exists in Frappe's Gender DocType: `if gender and not frappe.db.exists("Gender", gender): frappe.throw(f"Unknown gender: {gender}")`. This defers to whatever options exist in the Gender DocType (which may include "Other", "Prefer not to say", etc.) instead of the hardcoded `("Male", "Female")` tuple which would be a regression vs the existing onboarding flow.
5. `getdate(date_of_birth) < getdate(today())` → 400 if DOB in future
6. `frappe.db.exists("Branch", branch)` → 400 `BRANCH_NOT_FOUND`
7. `frappe.db.exists("Company", company)` → 400 `COMPANY_NOT_FOUND`
8. `employee_id = generate_bei_employee_id()`
9. `bio_id = generate_next_bio_id()`
10. Build Employee doc, following the population pattern from `_create_employee_from_new_hire_request` in `onboarding.py` (find via grep anchor `def _create_employee_from_new_hire_request`, NOT by line number — numbers have drifted). Only set fields when value is not None. Always set `attendance_device_id = new_attendance_device_id = bio_id`. Default `date_of_joining` to `today()` if None. Set `status = "Active"`. Set `company` from parameter (not the Global Defaults fallback — the parameter is now mandatory).
11. `employee_doc.insert(ignore_permissions=True)` (single doc, DM-2 not applicable). **Known risk inherited from existing onboarding flow** — MEMORY.md lesson #6 says NEVER use ORM for Employee, but existing `_create_employee_from_new_hire_request` uses this exact pattern and is in production use. If this insert raises, fall back to direct SQL per `memory/frappe-lessons.md` and report to user.
12. `adms_result = _enroll_employee_on_adms_for_branch(employee_id, employee_name, bio_id, branch)` — wrapped try/except inside the helper so it never raises
13. `_notify_new_employee_created(employee_id=employee_id, employee_name=employee_name, branch=branch, designation=designation, bio_id=bio_id, source="employee_master_dashboard", approver_email=frappe.session.user)` — note: no `request_name` kwarg (this is not an onboarding request). Wrap in try/except to swallow notification failures so they don't block the response.
14. Return:

```python
{
    "success": True,
    "data": {
        "employee_id": "BEI-EMP-2026-00638",
        "employee_name": "Juan Dela Cruz",
        "bio_id": "9001882",
        "adms_enrollment": {
            "enrolled": True,
            "reason": None,  # or "NO_DEVICE_FOR_BRANCH" | "PREFLIGHT_FAILED" | "DISPATCH_FAILED"
            "device_sn": "UDP3251600245",
        },
    },
}
```

**HARD BLOCKER:** The endpoint must NOT accept a `bio_id` parameter from the caller. Bio ID is generated server-side only. If a future requirement asks for manual override, add a separate admin endpoint. (Source: CEO directive 2026-04-06)

### Task 2.2: Create `_enroll_employee_on_adms_for_branch()` helper (2 units)

**MUST_MODIFY:** `hrms/api/employee_create.py`
**MUST_CONTAIN:** `def _enroll_employee_on_adms_for_branch(`
**MUST_CONTAIN:** `DEVICE_TO_STORE`
**MUST_CONTAIN:** `_queue_adms_command(`
**MUST_CONTAIN:** `_build_update_command(`
**MUST_CONTAIN:** `from hrms.utils.adms_config import get_adms_config` (AUDIT NG5 — use the Phase 0 extracted public helper)
**MUST_CONTAIN:** `.strip().upper()` (AUDIT R2 — case-insensitive branch lookup)
**MUST_NOT_CONTAIN:** `_load_adms_config` (AUDIT B1 — function does not exist)
**MUST_NOT_CONTAIN:** `_get_adms_config` (AUDIT NG5 — the private form was extracted to public `get_adms_config` in Phase 0)
**MUST_NOT_CONTAIN:** `preflight_check_enrollment` (AUDIT B3/B4 — preflight MUST be skipped for new-create flow because it validates against a static CSV snapshot that excludes freshly generated Bio IDs)
**MUST_NOT_CONTAIN:** `preflight.get("ok")` (AUDIT B3 — there is no "ok" key; actual key is "can_proceed")

**Audit fixes applied:**
- **B1:** Uses `get_adms_config` (not `_load_adms_config` which does not exist)
- **B2/B3/B4:** Skips `preflight_check_enrollment` entirely — its static-CSV validation would reject every freshly generated Bio ID. The `DEVICE_TO_STORE` reverse lookup is the authoritative device-to-branch check and is sufficient.
- **NG5:** Imports from `hrms.utils.adms_config` (the Phase 0 extraction), not from `hrms.api.transfer_requests` (private helper)
- **R2:** Case-insensitive branch name matching

```python
import frappe
from frappe.utils import get_traceback

from hrms.utils.device_mapping import DEVICE_TO_STORE
from hrms.utils.adms_config import get_adms_config
from hrms.api.transfer_requests import (
    _queue_adms_command,
    _build_update_command,
)


def _enroll_employee_on_adms_for_branch(
    employee_id: str, employee_name: str, bio_id: str, branch: str
) -> dict:
    """Best-effort ADMS enrollment for a newly-created employee.

    Never raises. Returns a dict with enrollment status.

    Audit notes:
    - Skips `preflight_check_enrollment` because that helper validates Bio IDs
      against a static CSV snapshot (Employee_Master.csv) that does NOT include
      freshly generated Bio IDs. Running preflight would reject every new-create
      attempt. The DEVICE_TO_STORE reverse lookup is the authoritative check.
    - Uses case-insensitive branch matching because DEVICE_TO_STORE key casing
      is not guaranteed to match Branch.name casing in Frappe.
    """
    try:
        # AUDIT R2: case-insensitive reverse lookup for device SN by branch name
        normalized_branch = (branch or "").strip().upper()
        device_sn = next(
            (
                sn for sn, store in DEVICE_TO_STORE.items()
                if (store or "").strip().upper() == normalized_branch
            ),
            None,
        )
        if not device_sn:
            return {
                "enrolled": False,
                "reason": "NO_DEVICE_FOR_BRANCH",
                "device_sn": None,
            }

        # AUDIT B3/B4: skip preflight_check_enrollment — it validates against a
        # static CSV snapshot and will always reject freshly generated Bio IDs.
        # DEVICE_TO_STORE reverse lookup is sufficient since it's the authoritative
        # device-to-branch mapping maintained by BEI.

        # Build and queue the ADMS USERINFO UPDATE command
        config = get_adms_config()  # AUDIT B1/NG5: from hrms.utils.adms_config, NOT _load_adms_config
        command = _build_update_command(bio_id, employee_name)
        _queue_adms_command(device_sn, command, config)

        return {"enrolled": True, "reason": None, "device_sn": device_sn}
    except Exception:
        frappe.log_error(
            title="ADMS auto-enroll on create_employee_direct failed",
            message=get_traceback(),
        )
        return {
            "enrolled": False,
            "reason": "DISPATCH_FAILED",
            "device_sn": None,
        }
```

**HARD BLOCKER:** Do NOT add `preflight_check_enrollment` back. If a future agent thinks "the helper exists, I should call it," they must read this comment block first. Preflight is skipped on purpose for new-create because the static CSV excludes fresh Bio IDs (audit B4, confirmed by source verification of `adms_validation.py:414-451`).

### Task 2.3: Modify `hrms/api/hr_reports.py` — add Bio ID surfacing (1 unit)

**MUST_MODIFY:** `hrms/api/hr_reports.py`
**MUST_CONTAIN:** `"attendance_device_id"`
**MUST_CONTAIN:** `"missing_bio_id"`
**MUST_CONTAIN:** `has_bio_id`

**AUDIT B11/NG2/NG6:** Use GREP ANCHORS, not line numbers. The file is 1087 lines and changes frequently; line references drift fast.

1. In the `fields=[...]` list inside `get_employee_masterlist()`, find the anchor `"reports_to",` (this is a stable field that exists today). Insert `"attendance_device_id",` after it.

2. Find the per-row for-loop anchor: the line that says `row["reports_to_name"] = manager_name_map.get(row.get("reports_to"), "")`. Add immediately after:
   ```python
   row["has_bio_id"] = bool(row.get("attendance_device_id"))
   ```

3. Find the `summary = {` dict anchor (grep for `"missing_company_email":` which is a stable existing key). Insert a new row immediately after it:
   ```python
   "missing_bio_id": sum(1 for r in results if not r.get("has_bio_id")),
   ```

4. **Verification:** Run `grep -n 'attendance_device_id\|missing_bio_id\|has_bio_id' hrms/api/hr_reports.py`. Expected output: at least 3 matches (fields list, per-row flag, summary dict).

No other changes to `hr_reports.py`. Do NOT re-introduce the `exception` filter parameter, `profile_completion`, `missing_dob`, `missing_designation`, or `missing_salary` — those are from pre-revert state and belong in a separate sprint.

---

## Phase 3: Frontend Data Hooks + Shared Selectors (4 units)

### Task 3.1: Reuse existing shared selectors + create 3 new shared components + Gender hook (2 units)

**AUDIT B8/NG4:** `<BranchSelector>` and `<DepartmentSelector>` ALREADY EXIST in `components/shared/` with 14 active consumers. Do NOT create duplicate hooks. Only create the 3 missing shared components (Company, Designation, Employment Type) + one Gender hook.

**MUST_MODIFY:** `components/shared/company-selector.tsx` (new file)
**MUST_MODIFY:** `components/shared/designation-selector.tsx` (new file)
**MUST_MODIFY:** `components/shared/employment-type-selector.tsx` (new file)
**MUST_MODIFY:** `components/shared/index.ts` (add exports)
**MUST_MODIFY:** `lib/queries/hr-master-data.ts` (new file, only contains `useGenderOptions`)
**MUST_CONTAIN:** `useFrappeGetDocList` in each new selector (pattern from existing `branch-selector.tsx`)
**MUST_CONTAIN:** `export function useGenderOptions` in `hr-master-data.ts`
**MUST_NOT_CONTAIN:** `useBranchOptions` in `hr-master-data.ts` (AUDIT B8 — use existing `<BranchSelector>` instead)
**MUST_NOT_CONTAIN:** `useDepartmentOptions` in `hr-master-data.ts` (AUDIT B8 — use existing `<DepartmentSelector>` instead)

1. Read `F:\Dropbox\Projects\bei-tasks\components\shared\branch-selector.tsx` to understand the existing pattern. It uses `useFrappeGetDocList<BranchRow>("Branch", { limit: 2000, fields: [...] })` from `frappe-react-sdk`.

2. Create `components/shared/company-selector.tsx` following the same pattern, targeting the `Company` DocType. Fields: `["name", "abbr"]`.

3. Create `components/shared/designation-selector.tsx` targeting the `Designation` DocType. Fields: `["name"]`.

4. Create `components/shared/employment-type-selector.tsx` targeting the `Employment Type` DocType. Fields: `["name"]`.

5. Update `components/shared/index.ts` to export the 3 new components alongside the existing exports.

6. Create `lib/queries/hr-master-data.ts` with ONLY the `useGenderOptions` hook:
   ```ts
   import { useQuery } from "@tanstack/react-query";

   export function useGenderOptions() {
     return useQuery({
       queryKey: ["frappe", "gender-options"],
       queryFn: async (): Promise<string[]> => {
         const res = await fetch(
           "/api/frappe/api/method/frappe.client.get_list?doctype=Gender&fields=[\"name\"]&limit_page_length=0",
           { credentials: "include" }
         );
         if (!res.ok) return ["Male", "Female"]; // graceful fallback
         const json = await res.json();
         return (json.message || []).map((row: { name: string }) => row.name);
       },
       staleTime: 5 * 60 * 1000,
     });
   }
   ```
   **AUDIT B9 NOTE:** The fallback `["Male", "Female"]` is only used if the Frappe Gender DocType query fails (network/permission error). The primary path reads the actual DocType so any options the admin has added (e.g., "Other", "Prefer not to say") are honored.

**HARD BLOCKER:** Do NOT use `limit_page_length=0` with Frappe resource API — audit verification confirmed Frappe v15 returns empty results with this value. Use `frappe.client.get_list` instead (which accepts `limit_page_length=0` as "no limit") OR specify a concrete high limit like `limit_page_length=500`.

### Task 3.2: Create `lib/queries/hr-employee-create.ts` (2 units)

**MUST_MODIFY:** `lib/queries/hr-employee-create.ts` (new file)
**MUST_CONTAIN:** `export const PROOF_FIELD_MAP`
**MUST_CONTAIN:** `custom_tin_proof_url`
**MUST_CONTAIN:** `custom_sss_proof_url`
**MUST_CONTAIN:** `custom_philhealth_proof_url`
**MUST_CONTAIN:** `custom_pagibig_proof_url`
**MUST_CONTAIN:** `export function useCreateEmployeeMutation`
**MUST_CONTAIN:** `hrms.api.employee_create.create_employee_direct`
**MUST_CONTAIN:** `from "@/lib/frappe-csrf"` (AUDIT B5 — imports from the Phase 0 shared util, NOT from `hr-employee-detail.ts` which does not export it)
**MUST_NOT_CONTAIN:** `from "./hr-employee-detail"` (AUDIT B5 — that file does not export getCsrfToken)
**MUST_NOT_CONTAIN:** `function getCsrfToken` (AUDIT NG1 — do NOT redefine it locally; must import from Phase 0 shared util)

```ts
export const PROOF_FIELD_MAP = {
  tin:        "custom_tin_proof_url",
  sss:        "custom_sss_proof_url",
  philhealth: "custom_philhealth_proof_url",
  pagibig:    "custom_pagibig_proof_url",
} as const;

export interface CreateEmployeePayload { /* mirror backend params */ }
export interface CreateEmployeeResponse {
  success: boolean;
  data: {
    employee_id: string;
    employee_name: string;
    bio_id: string;
    adms_enrollment: {
      enrolled: boolean;
      reason: null | "NO_DEVICE_FOR_BRANCH" | "PREFLIGHT_FAILED" | "DISPATCH_FAILED";
      device_sn: string | null;
    };
  };
}

export function useCreateEmployeeMutation() {
  // TanStack useMutation; POST to /api/frappe/api/method/hrms.api.employee_create.create_employee_direct
  // CSRF via getCsrfToken() from @/lib/frappe-csrf (Phase 0 shared util — audit B5/NG1)
  // onSuccess: invalidate ['hr','reports','masterlist']
}
```

---

## Phase 4: Frontend Dialog + Employee Master Integration (6 units)

### Task 4.1: Create `app/dashboard/hr/employee-master/new-employee-dialog.tsx` (3 units)

**MUST_MODIFY:** `app/dashboard/hr/employee-master/new-employee-dialog.tsx` (new file)
**MUST_CONTAIN:** `"use client"`
**MUST_CONTAIN:** `Dialog`
**MUST_CONTAIN:** `useCreateEmployeeMutation`
**MUST_CONTAIN:** `uploadFrappeFile`
**MUST_CONTAIN:** `first_name`
**MUST_CONTAIN:** `last_name`
**MUST_CONTAIN:** `date_of_birth`
**MUST_CONTAIN:** `gender`
**MUST_CONTAIN:** `branch`
**MUST_CONTAIN:** `company`
**MUST_CONTAIN:** `PROOF_FIELD_MAP`
**MUST_CONTAIN:** `BranchSelector` (AUDIT B8 — reuse existing shared component from `@/components/shared`)
**MUST_CONTAIN:** `DepartmentSelector` (AUDIT B8 — reuse existing shared component from `@/components/shared`)
**MUST_CONTAIN:** `CompanySelector` (new Phase 3 shared component)
**MUST_CONTAIN:** `DesignationSelector` (new Phase 3 shared component)
**MUST_CONTAIN:** `EmploymentTypeSelector` (new Phase 3 shared component)
**MUST_CONTAIN:** `useGenderOptions` (AUDIT B9 — populate gender Select from Frappe Gender DocType)
**MUST_CONTAIN:** `isPrivate: true` (AUDIT B10 — boolean, NOT `is_private: 1` snake_case number)
**MUST_NOT_CONTAIN:** `is_private:` (AUDIT B10 — must use `isPrivate` per `lib/frappe-upload.ts` option shape)
**MUST_NOT_CONTAIN:** `useBranchOptions` (AUDIT B8 — use `<BranchSelector>` component instead)
**MUST_NOT_CONTAIN:** `useDepartmentOptions` (AUDIT B8 — use `<DepartmentSelector>` component instead)

Client component. Follow the plain-useState pattern from `employee-detail-dialog.tsx` (no react-hook-form — matches house style).

**Structure** — shadcn `Dialog` with 4 sectioned fieldsets:

```
Section 1: Identity
  first_name* | middle_name | last_name*
  date_of_birth* | gender* (Select — populated from useGenderOptions)

Section 2: Employment
  <CompanySelector>* | <BranchSelector>*
  <DepartmentSelector> | <DesignationSelector>
  date_of_joining (date, placeholder="defaults to today") | <EmploymentTypeSelector>

Section 3: Contact
  personal_email | cell_number

Section 4: Government IDs (collapsible, collapsed by default)
  TIN          [Attach file]
  SSS          [Attach file]
  PhilHealth   [Attach file]
  Pag-IBIG     [Attach file]

Info banner: "Bio ID and Employee ID are auto-generated.
              ADMS enrollment runs automatically if the branch has a mapped bio device."
```

**Component imports:**
```tsx
import {
  BranchSelector,
  DepartmentSelector,
  CompanySelector,          // Phase 3 new
  DesignationSelector,      // Phase 3 new
  EmploymentTypeSelector,   // Phase 3 new
} from "@/components/shared";
import { useGenderOptions } from "@/lib/queries/hr-master-data";
import { useCreateEmployeeMutation, PROOF_FIELD_MAP } from "@/lib/queries/hr-employee-create";
import { uploadFrappeFile } from "@/lib/frappe-upload";
```

**State:**
```ts
const [form, setForm] = useState<NewEmployeeForm>(EMPTY_FORM);
const [files, setFiles] = useState<Partial<Record<
  "tin" | "sss" | "philhealth" | "pagibig", File
>>>({});
```

**Validation gate:**
```ts
const canSubmit = Boolean(
  form.first_name && form.last_name && form.date_of_birth &&
  form.gender && form.branch && form.company
);
```

**Submit flow:**
1. POST via `useCreateEmployeeMutation().mutateAsync(payload)`
2. Read `result.data.employee_id`, `result.data.bio_id`, `result.data.adms_enrollment`
3. For each `files[key]`: `uploadFrappeFile(file, { doctype: "Employee", docname: result.data.employee_id, fieldname: PROOF_FIELD_MAP[key], isPrivate: true })` (AUDIT B10 — `isPrivate` boolean, NOT `is_private: 1`). Per-file failures → warning toast, employee stays.
4. `queryClient.invalidateQueries({ queryKey: ['hr', 'reports', 'masterlist'] })`
5. Success toast composed from `adms_enrollment.reason`:
   - `null` → `"Employee {id} created. Bio ID {bio} enrolled on device {sn}."`
   - `"NO_DEVICE_FOR_BRANCH"` → `"Employee {id} created. No biometric device mapped to {branch} — enroll manually."`
   - `"PREFLIGHT_FAILED"` → `"Employee {id} created. ADMS preflight failed — retry from Transfers."`
   - `"DISPATCH_FAILED"` → `"Employee {id} created. ADMS dispatch failed — retry from Transfers."`
6. `setForm(EMPTY_FORM); setFiles({}); onOpenChange(false);`
7. On error: toast message, dialog stays open, no partial reset

### Task 4.2: Modify `app/dashboard/hr/employee-master/page.tsx` (2 units)

**MUST_MODIFY:** `app/dashboard/hr/employee-master/page.tsx`
**MUST_CONTAIN:** `import { NewEmployeeDialog }` (dialog import)
**MUST_CONTAIN:** `Add New Employee` (button label)
**MUST_CONTAIN:** `hasRole(roles, [ROLES.HR_MANAGER` (RBAC gate on button)
**MUST_CONTAIN:** `Missing Bio Device` (metric card label)
**MUST_CONTAIN:** `missing_bio_id` (summary field reference — proves card is wired to backend data, not a stub)
**MUST_CONTAIN:** `No Bio ID` (row badge label)
**MUST_CONTAIN:** `!employee.attendance_device_id` (row-level conditional — proves badge is wired to employee data, not a static literal)
**MUST_CONTAIN:** `bg-red-500/10` (red tone on row badge per CEO directive)
**MUST_CONTAIN:** `<NewEmployeeDialog` (dialog mount)
**MUST_CONTAIN:** `open={createOpen}` (dialog state binding — proves it's wired to state, not a literal false)
**MUST_CONTAIN:** `setCreateOpen(true)` (button onClick — proves the button actually opens the dialog)
**MUST_CONTAIN:** `useEmployee` (RBAC role source hook)
**MUST_CONTAIN:** `canCreate` (computed role gate)

**S154 CORRUPT-SUCCESS PREVENTION:** These MUST_CONTAIN gates are intentionally verbose to prevent the agent from "completing" this task by modifying only the type definition or hook while never editing the page.tsx component file. If even one of these literal strings is missing from the file after Task 4.2, the verification script MUST fail the phase. Do NOT relax or merge these assertions.

1. Import `Plus` from `lucide-react`, `NewEmployeeDialog` from `./new-employee-dialog`
2. Import `ROLES, hasRole` from `@/lib/roles` and `useEmployee` (pattern from `employee-detail-dialog.tsx:52, 671`)
3. Add state: `const [createOpen, setCreateOpen] = useState(false);`
4. Add: `const { roles } = useEmployee(); const canCreate = hasRole(roles, [ROLES.HR_MANAGER, ROLES.SYSTEM_MANAGER, ROLES.ADMINISTRATOR]);`
5. Conditionally prepend to `HrPageHeader.actions`:
   ```tsx
   actions={[
     ...(canCreate ? [{
       label: "Add New Employee",
       onClick: () => setCreateOpen(true),
       variant: "default" as const,
       icon: Plus,
     }] : []),
     { label: "Reports Companion", href: ROUTES.HR_REPORTS, variant: "outline" },
   ]}
   ```
6. Add a "Missing Bio Device" `MetricCard` to the metric strip:
   ```tsx
   <MetricCard
     label="Missing Bio Device"
     value={summary?.missing_bio_id || 0}
     hint="Employees without a Bio ID on file"
     tone={(summary?.missing_bio_id || 0) > 0 ? "alert" : "default"}
   />
   ```
7. Add a red "No Bio ID" badge inside the employee name cell in the table row:
   ```tsx
   {!employee.attendance_device_id && (
     <Badge className="bg-red-500/10 text-red-700 border-red-200 text-[10px]">
       No Bio ID
     </Badge>
   )}
   ```
8. Render the dialog near the existing `<EmployeeDetailDialog />` mount:
   ```tsx
   <NewEmployeeDialog open={createOpen} onOpenChange={setCreateOpen} />
   ```

### Task 4.3: Modify `lib/queries/hr-reports.ts` types (1 unit)

**MUST_MODIFY:** `lib/queries/hr-reports.ts`
**MUST_CONTAIN:** `attendance_device_id?:`
**MUST_CONTAIN:** `has_bio_id?:`
**MUST_CONTAIN:** `missing_bio_id:`

Add `attendance_device_id?: string` and `has_bio_id?: boolean` to the `EmployeeMasterlist` interface. Add `missing_bio_id: number` to the summary shape.

**Note:** The backend change to `hr_reports.py` lives in Phase 2 as Task 2.3 (moved per audit B12 because it's backend work, not frontend). This task is only the TypeScript type additions on the frontend side.

---

## Sentry Observability

Per `.claude/rules/sentry-observability.md` (DM-7), every `@frappe.whitelist()` function in this sprint must call `set_backend_observability_context()` as its first meaningful line.

**Backend endpoints added by this sprint:**

| Function | Module | Action | Mutation Type |
|---|---|---|---|
| `hrms.api.employee_create.create_employee_direct` | `hr` | `create_employee_direct` | `create` |

**Closeout blocker:** The plan cannot be marked COMPLETED unless `create_employee_direct` imports and calls `set_backend_observability_context(module="hr", action="create_employee_direct", mutation_type="create")`.

**Helpers (not whitelisted) — no Sentry required:**
- `_enroll_employee_on_adms_for_branch` — internal helper, no direct HTTP exposure
- `generate_bei_employee_id` — internal helper
- `generate_next_bio_id` — internal helper

**Frontend routes — none added by this sprint.** `@sentry/nextjs` auto-instrumentation covers the existing proxy routes under `bei-tasks/app/api/frappe/`.

Sentry project: `bei-hrms` (slug: `bei-hrms`, platform: python), org: `bebang-enterprise-inc`.

---

## Zero-Skip Enforcement

**Every task MUST be implemented. No exceptions.** If a task cannot be completed, the agent STOPS and asks the user.

### Forbidden agent behaviors

- Skipping a task silently
- Marking partial work as "done"
- Replacing a task with a simpler version without user approval
- Saying "deferred to next sprint"
- Combining tasks and dropping features in the merge
- Implementing the happy path only and skipping edge cases
- Declaring the ADMS enrollment helper complete if it doesn't wrap the body in try/except
- Declaring the backend endpoint complete without `set_backend_observability_context`

### Phase Completion Verification Script

After each phase, the executing agent MUST write and run `tmp/s164_verify_phase_{N}.py`. The script uses filesystem evidence only (no agent self-report). Template:

```python
#!/usr/bin/env python3
"""S164 Phase {N} verification — filesystem-based, not prose."""
import subprocess
import sys
import re

PHASE = {N}
REPO_HRMS = "F:/Dropbox/Projects/BEI-ERP"
REPO_BEI_TASKS = "F:/Dropbox/Projects/bei-tasks"

checks = []

def must_modify(repo, path):
    """File must appear in git diff --name-only."""
    result = subprocess.run(
        ["git", "-C", repo, "diff", "--name-only", "origin/production...HEAD"]
        if "BEI-ERP" in repo else
        ["git", "-C", repo, "diff", "--name-only", "origin/main...HEAD"],
        capture_output=True, text=True,
    )
    return path in result.stdout

def must_contain(repo, path, pattern, literal=False):
    """File must contain the pattern (regex or literal)."""
    try:
        with open(f"{repo}/{path}", "r", encoding="utf-8") as f:
            content = f.read()
        if literal:
            return pattern in content
        return bool(re.search(pattern, content))
    except FileNotFoundError:
        return False

# === Phase 1 checks ===
checks.append(("hrms/utils/employee_id.py created",
    must_modify(REPO_HRMS, "hrms/utils/employee_id.py")))
checks.append(("employee_id.py has generate_bei_employee_id",
    must_contain(REPO_HRMS, "hrms/utils/employee_id.py", "def generate_bei_employee_id")))
checks.append(("onboarding.py imports helper",
    must_contain(REPO_HRMS, "hrms/api/onboarding.py",
        "from hrms.utils.employee_id import generate_bei_employee_id", literal=True)))
# ... add per-task MUST_CONTAIN / MUST_MODIFY checks

# === Results ===
passed = sum(1 for _, ok in checks if ok)
failed = [name for name, ok in checks if not ok]
print(f"S164 Phase {PHASE}: {passed}/{len(checks)} checks passed")
for name in failed:
    print(f"  FAIL: {name}")
sys.exit(0 if not failed else 1)
```

**FAIL blocks progress.** If any check fails, the agent must fix the underlying issue before starting the next phase. No exceptions.

### Phase Completion Checklist

After each phase, append to `tmp/s164_phase_completion.md`:

```markdown
## Phase {N} — {timestamp}

| Task | Status | Evidence | Skipped? | If skipped, why? |
|------|--------|----------|----------|------------------|
| 1.1 Create employee_id.py | DONE | git diff shows file added, grep confirms function | No | — |
```

Any row marked "Skipped? Yes" or "Status: PARTIAL" triggers a STOP — notify the user before proceeding.

---

## L3 Workflow Scenarios

| # | User | Action | Expected Outcome | Failure Means |
|---|------|--------|-------------------|---------------|
| 1 | test.hr@bebang.ph | Click "Add New Employee" button → dialog opens | Dialog visible with all 4 sections, Submit button disabled until mandatory fields filled | Task 4.2 button wiring broken |
| 2 | test.hr@bebang.ph | Fill ONLY mandatory fields (first=Maria, last=Santos, DOB=1990-05-15, gender=Female, branch=BRITTANY OFFICE, company=Bebang Enterprise Inc.) → click Create | Toast: "Employee BEI-EMP-2026-XXXXX created. Bio ID 9001882 enrolled on device UDP3251600245." Row appears at top of Employee Master table after refetch | Mandatory-only flow broken OR ADMS auto-enroll not working |
| 3 | test.hr@bebang.ph | **Before test:** Run `grep -c "BRANCH_NAME_HERE" hrms/utils/device_mapping.py` and pick a branch that returns 0 (suggested: create a test Branch "S164 TEST BRANCH" in Frappe Desk first, OR use an existing non-retail Branch like "COMMISSARY OFFICE" if it exists in Branch DocType but not in DEVICE_TO_STORE). Fill mandatory fields with that branch → click Create | Toast: "Employee {id} created. No biometric device mapped to {branch} — enroll manually." Employee still created. Verify via grep that no ADMS command was queued for the test employee's Bio ID | ADMS skip path broken |
| 4 | test.hr@bebang.ph | Fill all mandatory fields + attach TIN PDF + SSS JPG + PhilHealth PDF + Pag-IBIG JPG → click Create | Employee created. Frappe Desk shows 4 `custom_*_proof_url` fields populated. Files visible under Employee attachments | File upload / field binding broken |
| 5 | test.hr@bebang.ph | Fill mandatory fields → leave date_of_joining blank → click Create | Employee created with date_of_joining = today's date (2026-04-06) | Default DOJ broken |
| 6 | test.hr@bebang.ph | Enter date_of_birth in the future (2030-01-01) → click Create | Backend 400 error, dialog stays open, error toast | DOB validation missing |
| 7 | test.crew1@bebang.ph (non-HR role) | Open Employee Master Dashboard | "Add New Employee" button NOT visible in header | RBAC gate broken |
| 8 | test.crew1@bebang.ph | Direct POST to `hrms.api.employee_create.create_employee_direct` without HR role | 403 Forbidden | Backend RBAC missing |
| 9 | test.hr@bebang.ph | Open Employee Master → scan metric cards | "Missing Bio Device" card visible with count > 0 (existing employees without Bio ID) | Metric card or `missing_bio_id` summary broken |
| 10 | test.hr@bebang.ph | Open Employee Master → find a row where `attendance_device_id` is blank | Red "No Bio ID" badge visible next to employee name | Row-level badge broken |

**Evidence file contract** (required before closeout):

```
output/l3/s164/form_submissions.json   # array with entries for scenarios 2, 3, 4, 5
output/l3/s164/api_mutations.json      # POST calls to create_employee_direct
output/l3/s164/state_verification.json # before/after state for each test scenario
output/l3/s164/screenshots/            # dialog open, filled form, success toast, error toast, badge visible
```

Minimum 10 entries in `form_submissions.json` matching the 10 scenarios above. L3 agent verifies count.

---

## Agent Boot Sequence

1. Read this plan fully (every section, especially Requirements Regression Checklist and Design Rationale).
2. **Create sprint branches:**
   - `cd F:\Dropbox\Projects\BEI-ERP && git fetch origin production && git checkout -b s164-add-new-employee-entry-point origin/production`
   - `cd F:\Dropbox\Projects\bei-tasks && git fetch origin main && git checkout -b s164-add-new-employee-entry-point origin/main`
   - NEVER write code on production or main.
3. Read `docs/plans/SPRINT_REGISTRY.md` to confirm S164 row is reserved (if not, STOP).
4. Read the following files in full before touching any code:
   - `hrms/api/onboarding.py` lines 802-926 (understand existing new_hire flow + notification helper)
   - `hrms/api/transfer_requests.py` lines 700-800 (understand ADMS config + command queuing)
   - `hrms/utils/adms_validation.py` lines 400-450 (understand `preflight_check_enrollment`)
   - `hrms/utils/device_mapping.py` lines 1-60 (understand branch→device mapping)
   - `app/dashboard/hr/employee-master/page.tsx` full (understand where to mount dialog + button)
   - `app/dashboard/hr/employee-master/employee-detail-dialog.tsx` lines 1-100, 670-680 (understand RBAC + dialog pattern)
   - `lib/frappe-upload.ts` full (understand file upload contract)
   - `lib/queries/hr-employee-detail.ts` full (understand CSRF + mutation pattern)
5. Write `tmp/s164_phase_completion.md` with the empty checklist template.
6. Start Phase 0 (audit-derived prep work: extract `getCsrfToken` and `get_adms_config` to shared utils). Do NOT skip Phase 0 — downstream phases depend on these extractions.
7. Start Phase 1 only after Phase 0 verification script passes.
8. Each subsequent phase gated on the previous phase's verification script.

---

## Execution Authority

This sprint is intended for autonomous end-to-end execution. Do not stop for progress-only updates. Only pause for items listed in the `stop_only_for` section below.

---

## Autonomous Execution Contract

- **completion_condition:**
  - All 10 tasks across Phases 1-4 complete with MUST_MODIFY and MUST_CONTAIN verified
  - Phase verification scripts green for all phases
  - Both PRs created (hrms + BEI-Tasks) targeting `production` and `main` respectively
  - Sprint registry updated with PR numbers in the same work unit
  - Plan YAML status updated to PR_CREATED with `frontend_pr` and `backend_pr` fields populated
  - L3 evidence files present in `output/l3/s164/` with minimum 10 form submission entries
  - Sentry observability closeout gate: `create_employee_direct` calls `set_backend_observability_context`
- **stop_only_for:**
  - Missing credentials or access
  - Onboarding.py refactor breaks existing new_hire flow (HARD BLOCKER in Task 1.2)
  - `DEVICE_TO_STORE` dict doesn't contain any branch that test scenarios need (add the mapping or pick a different branch)
  - Direct conflict with in-flight changes on shared files (`hrms/api/onboarding.py`, `hrms/api/hr_reports.py`)
  - Business-data/policy decision (none expected for this sprint)
- **continue_without_pause_through:** code → phase verification → PR creation → registry update → closeout
- **blocker_policy:**
  - programmatic → fix and continue
  - environment/runtime → debug; after 3 repeated failures, research and continue
  - business-data/policy → pause
  - approval/signoff → resolve using signoff model below
- **signoff_authority:** single-owner (Sam)

---

## Signoff Model

- **mode:** single-owner
- **approver_of_record:** Sam Karazi (CEO)
- **signoff_artifact:** PR merge by Sam
- **note:** No synthetic department approvals. Sam merges both PRs and runs deploy. Agent STOPS after both PRs are created and PR numbers shared.

---

## Anti-Rewind / Concurrent-Run Protection Contract

This sprint touches files that have been modified in prior sprints (S158, S160, S162). Protection rules:

- **ownership_matrix:**
  - **hrms repo:** `hrms/api/employee_create.py` (new, exclusive), `hrms/utils/employee_id.py` (new, exclusive), `hrms/utils/bio_id.py` (new, exclusive), `hrms/api/onboarding.py` (SHARED — restricted to refactoring ID gen lines 828-847 and notification signature lines 900-926 + one caller update), `hrms/api/hr_reports.py` (SHARED — restricted to adding `attendance_device_id` field, `has_bio_id` flag, `missing_bio_id` summary only)
  - **bei-tasks repo:** `app/dashboard/hr/employee-master/new-employee-dialog.tsx` (new, exclusive), `lib/queries/hr-master-data.ts` (new, exclusive), `lib/queries/hr-employee-create.ts` (new, exclusive), `app/dashboard/hr/employee-master/page.tsx` (SHARED — restricted to button, dialog mount, RBAC, new MetricCard, row badge), `lib/queries/hr-reports.ts` (SHARED — restricted to type additions)
- **protected_surfaces:**
  - Existing `_create_employee_from_new_hire_request` flow (onboarding.py:802-892) — MUST continue to work after Task 1.2 refactor
  - Existing Chat notification payload shape — HR must not see a change in format after Task 1.4
  - Existing `hr_reports.py` summary fields — do not touch anything other than adding `missing_bio_id`
  - S160 `EmployeeDetailDialog` — must continue to open on employee name click
- **remote_truth_baseline:**
  - hrms: `origin/production` HEAD as of branch creation (record SHA in `tmp/s164_baseline.json`)
  - bei-tasks: `origin/main` HEAD as of branch creation (record SHA in `tmp/s164_baseline.json`)
- **freshness_gate:** Before PR creation, rebase both branches onto their current release heads. If upstream moved on overlapping files (`onboarding.py`, `page.tsx`, `hr_reports.py`), reintegrate and rerun Phase verification scripts.
- **pretouch_backup:** Before Task 1.2 (onboarding.py refactor), `cp hrms/api/onboarding.py tmp/s164_onboarding_pretouch.py` as a safety snapshot.

---

## Execution Workflow

- Local test Python changes: `/local-frappe`
- Deploy Frappe changes: **user-mediated** — agent creates PR, user merges and deploys
- E2E testing: `/playwright-bei-erp`
- Full workflow: `/agent-kickoff` (handles all required skills)

### PR-Handoff Flow

**AUDIT B13 FIX:** Registry and plan updates are committed to the SAME `s164-add-new-employee-entry-point` branch as the code changes. They ride inside the hrms PR. Direct commits to `production` are FORBIDDEN (S099 branch isolation rule).

1. Agent completes all 5 phases (Phase 0-4) with verification scripts green
2. **Before creating PRs**, agent updates SPRINT_REGISTRY.md and the plan YAML on the `s164-add-new-employee-entry-point` branch (hrms repo):
   ```bash
   cd F:\Dropbox\Projects\BEI-ERP
   git checkout s164-add-new-employee-entry-point
   # Edit docs/plans/SPRINT_REGISTRY.md with PR numbers (can use placeholder # for now, fix in step 5)
   # Edit docs/plans/2026-04-06-sprint-164-add-new-employee-entry-point.md YAML: status: PR_CREATED, add placeholders for frontend_pr, backend_pr
   git add -f docs/plans/SPRINT_REGISTRY.md docs/plans/2026-04-06-sprint-164-add-new-employee-entry-point.md
   git commit -m "docs(S164): update registry and plan status to PR_CREATED"
   ```
3. Agent creates hrms PR targeting `production`:
   ```bash
   GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms --base production --head s164-add-new-employee-entry-point --title "S164: Add new employee entry point (backend)" --body "..."
   ```
4. Agent creates bei-tasks PR targeting `main`:
   ```bash
   cd F:\Dropbox\Projects\bei-tasks
   GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/BEI-Tasks --base main --head s164-add-new-employee-entry-point --title "S164: Add new employee entry point (frontend)" --body "..."
   ```
5. Agent updates the docs committed in step 2 with the real PR numbers (still on the s164 branch):
   ```bash
   cd F:\Dropbox\Projects\BEI-ERP
   # Edit both docs to replace placeholder PR numbers with real ones
   git add -f docs/plans/SPRINT_REGISTRY.md docs/plans/2026-04-06-sprint-164-add-new-employee-entry-point.md
   git commit -m "docs(S164): record PR numbers"
   git push origin s164-add-new-employee-entry-point
   ```
6. Agent outputs PR numbers in clear table + L3 handoff prompt
7. Agent STOPS — user handles merge and deploy

**HARD BLOCKER:** Do NOT use `git checkout production && git add ... && git push origin production` for the registry update. That is a direct push to production and violates S099. Registry and plan updates MUST ride inside the s164 PR so they merge atomically with the code.

---

## Out of Scope

- Click-to-filter on the "Missing Bio Device" card (would require re-adding the `exception` query parameter — separate sprint)
- Re-introducing `profile_completion`, `missing_dob`, `missing_designation`, `missing_salary` metrics that were in the pre-revert `hr_reports.py`
- Bulk employee import via CSV
- Editing existing employees from the same dialog (use S160 `EmployeeDetailDialog`)
- Creating employees for Bebang Kitchen Inc. with a `BKI-EMP-` prefix (the ID generator is BEI-EMP hard-coded; parameterizing it is a separate sprint)
- Converting `DEVICE_TO_STORE` hardcoded dict to a DocType-backed mapping
- Manual override of auto-generated Bio ID (CEO directive: always auto-generate)
- Profile picture upload on creation (use S160 dialog to add after creation)
- Auto-creation of Frappe User account for the new employee
- Assignment of Employee to a Salary Structure (done separately via Compensation Setup S158)

## Known Debt (audit-flagged, not fixed in S164)

- **NG3 — Hardcoded "Bebang Enterprise Inc." fallback in existing onboarding flow.** `hrms/api/onboarding.py` (at the `_create_employee_from_new_hire_request` function) defaults `company` to `"Bebang Enterprise Inc."` when Global Defaults is empty. This is a live BKI-vs-BEI separation bug (per `memory/bki-bei-entity-structure.md`). S164 fixes it in the new `create_employee_direct` endpoint (company is mandatory with no fallback) but leaves it broken in the existing onboarding flow. Requires a follow-up sprint to make the existing flow mandatory-company-aware.
- **NG6 — `hr_reports.py` is 1087 lines.** Refactor/split is deferred. This sprint uses grep anchors (not line numbers) for the three edits to minimize drift risk.

---

## AUDIT: 13 BLOCKERS RESOLVED (Amendment v1 — 2026-04-06)

`/audit-plan-bei-erp` ran on this plan 2026-04-06 after initial authoring. Audit ran 6 parallel domain agents + 1 code-verifier. Raw findings: 24 critical / 51 warning / 48 info. After source verification: **13 CONFIRMED blockers, 4 STALE, 6 NEW GAPS**.

All 13 blockers + 6 new gaps have been resolved in-plan via this amendment. No features were dropped. The feature envelope is identical to v0 of the plan:
- Add New Employee button + dialog with 6 mandatory fields + optional fields + Gov ID uploads
- Auto-generated Employee ID + Bio ID
- Best-effort ADMS auto-enrollment on branch bio device
- Google Chat notification
- Red "No Bio ID" badge on employee rows
- "Missing Bio Device" metric card

### Blocker resolution matrix

| # | Blocker | Resolution |
|---|---|---|
| B1 | `_load_adms_config` doesn't exist | Phase 0 Task 0.2 extracts `_get_adms_config` → public `get_adms_config` in `hrms/utils/adms_config.py`. Task 2.2 imports it from the new location. |
| B2 | `preflight_check_enrollment` tuple shape was wrong | Resolved by B3/B4 — preflight is now skipped entirely. |
| B3 | `preflight_check_enrollment` return key was `ok` (doesn't exist) | Resolved by B4 — preflight is skipped entirely. |
| B4 | `preflight_check_enrollment` validates against static CSV | Task 2.2 now SKIPS preflight. DEVICE_TO_STORE reverse lookup is the authoritative check. MUST_NOT_CONTAIN gate prevents re-adding. |
| B5 | `getCsrfToken` is not exported | Phase 0 Task 0.1 extracts to `lib/frappe-csrf.ts` and updates both existing consumers in the same PR. |
| B6 | `_notify_new_employee_created` refactor dropped `request_name` | Task 1.4 now adds optional `request_name: str \| None = None` kwarg with conditional append. HARD BLOCKER added for Chat payload verification before proceeding to Phase 2. |
| B7 | L3 test account `test.crew@bebang.ph` doesn't exist | All L3 scenario references updated to `test.crew1@bebang.ph`. |
| B8 | `BranchSelector`/`DepartmentSelector` already exist; plan duplicated them | Phase 3 rewritten. Plan now reuses existing shared components. Creates NEW shared components for Company, Designation, Employment Type (which don't exist per NG4). |
| B9 | Hardcoded `("Male", "Female")` is a regression | Backend validates via `frappe.db.exists("Gender", gender)` instead of hardcoded tuple. Frontend populates from new `useGenderOptions()` hook that queries Frappe Gender DocType. |
| B10 | `uploadFrappeFile` expects `isPrivate: true` not `is_private: 1` | Task 4.1 updated. MUST_NOT_CONTAIN `is_private:` gate added. |
| B11 | `hr_reports.py` line number references were wrong | Task 2.3 rewritten to use grep anchors ("insert after `\"reports_to\",`" and "insert after `\"missing_company_email\":`"). |
| B12 | Phase 4 unit math inconsistent; backend task in frontend phase | Task 4.4 moved to Phase 2 as Task 2.3. Phase 4 now has 6 units (3+2+1). Phase 2 now has 7 units (4+2+1). Total 28. |
| B13 | PR-Handoff flow pushed registry updates directly to production | PR-Handoff Flow rewritten. Registry + plan updates commit to the s164 branch and ride inside the hrms PR. HARD BLOCKER added forbidding direct push to production. |

### New Gap resolution matrix

| # | New Gap | Resolution |
|---|---|---|
| NG1 | `getCsrfToken` duplicated twice | Phase 0 Task 0.1 extracts to shared util AND updates both existing consumers in the same PR. |
| NG2 | Line-number refs are fragile | All remaining file edit instructions use grep anchors. |
| NG3 | Existing onboarding has hardcoded company fallback | Documented in "Known Debt" section with follow-up sprint reference. |
| NG4 | Company/Designation/Employment Type selectors don't exist | Phase 3 Task 3.1 creates them as shared components in `components/shared/` (not inline hooks). |
| NG5 | `_get_adms_config` is private with 4 callers | Phase 0 Task 0.2 extracts to `hrms/utils/adms_config.py` as public `get_adms_config` and updates all 4 existing callers in transfer_requests.py in the same PR. |
| NG6 | `hr_reports.py` is 1087 lines | Task 2.3 uses grep anchors. Documented in Known Debt. |

### Unresolved risks (documented, not fixed)

| Risk | Documentation | Impact |
|---|---|---|
| R1 | ORM-based Employee insert vs MEMORY.md lesson #6 | Design Rationale "Known limitations" section explicitly notes the tension. Task 2.1 step 11 includes fallback instruction to direct SQL if ORM insert raises. |
| R2 | `DEVICE_TO_STORE` key casing vs `Branch.name` casing | Task 2.2 uses case-insensitive match (`.strip().upper()`). MUST_CONTAIN gate enforces it. |

### Phase structure after amendment

| Phase | Units | Content |
|---|---|---|
| Phase 0 | 3 | Audit-derived prep: extract getCsrfToken + get_adms_config to shared utils (Task 0.1, 0.2) |
| Phase 1 | 8 | Shared helpers: employee_id, bio_id, notification refactor (Task 1.1, 1.2, 1.3, 1.4) |
| Phase 2 | 7 | Backend endpoint + ADMS helper + hr_reports.py delta (Task 2.1, 2.2, 2.3) |
| Phase 3 | 4 | Frontend shared selectors + gender hook + mutation hook (Task 3.1, 3.2) |
| Phase 4 | 6 | Dialog + Employee Master integration (Task 4.1, 4.2, 4.3) |
| **Total** | **28** | Under the 80-unit single-sprint ceiling. No phase exceeds the 12-unit preferred split threshold. |

### Audit artifacts

- Raw findings: `output/plan-audit/s164-add-new-employee-entry-point/{frappe-backend,frontend,deployment-qa,team-orchestration,system-arch,design-review}_findings.md`
- Code verification: `output/plan-audit/s164-add-new-employee-entry-point/code_verification.md`
- Consolidated blockers: `output/plan-audit/s164-add-new-employee-entry-point/verified_blockers.md`
