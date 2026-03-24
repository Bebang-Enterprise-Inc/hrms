# Sprint S115 — Payroll Processing & Remittances

```yaml
canonical_sprint_id: S115
status: In Progress
execution_started: 2026-03-24
branch: s115-payroll-processing-remittances
completed_date: null
execution_summary: null
parent_initiative: S083-payroll-war-room-replacement
parallel_sprints:
  - S113  # Command Center + Navigation (zero dependency)
  - S114  # Compensation + Sensitive Changes (zero dependency)
estimated_units: 33
phases: 3
created: 2026-03-24
owner: Sam Karazi (sam@bebang.ph)
```

---

## 1. Design Rationale (For Cold-Start Agents)

### Why a step wizard instead of one-click payroll?

BEI has **never run payroll in Frappe** (0 payroll entries, 0 salary slips — confirmed by S076 audit). This means:
- There are zero reference runs to validate against
- S076 identified day-zero blockers: no `default_payroll_payable_account`, zero income_tax_slab assignments, and 33 employees without salary structures
- One-click payroll would silently error or produce wrong output when these blockers are present

The step wizard makes each phase of payroll processing visible and stoppable. BEI management needs to see what is happening at each step before committing. This is the explicit decision from S083 (Decision #18): processing is an action surface, not a data entry surface.

### Why must S076 blockers surface as explicit blocked states?

If a user clicks "Generate Salary Slips" and Frappe throws an internal error about missing payable account, the user sees a cryptic Frappe traceback. Worse, they may think payroll ran partially. The correct pattern (S083 Decision + success outcome #12) is: **run a pre-flight readiness check first**, surface each blocker with its owner and remediation path, and **block UI progression** until all critical blockers are cleared. The UI must never show an enabled control whose action will fail.

### What is the current dead-link state being replaced?

`../bei-tasks/app/dashboard/hr/payroll/page.tsx` currently has:
- A bank file download button (floating CTA — poorly placed, belongs in processing workflow)
- Dead links for `/dashboard/hr/payroll/remittances` (404)
- Dead links for `/dashboard/hr/payroll/comparison` (belongs to S112)

This sprint creates the two missing child routes: `processing` and `remittances`. S112 owns the landing page and navigation. S113 owns compensation and sensitive change routes.

---

## 2. Requirements Regression Checklist

Before closing this sprint, verify all locked decisions are intact:

| # | Decision | Assertion | Status |
|---|----------|-----------|--------|
| D01 | Processing is separate from data entry (S083 Decision #18) | Processing page at `/processing` contains no salary structure or compensation fields | [ ] |
| D02 | S076 blockers must appear as explicit blocked states with owner/reason | Readiness check surfaces missing payable account, tax slab gaps, missing salary structures — not as a toast, as structured UI | [ ] |
| D03 | Bank file generation belongs in Processing workflow, not floating CTA (S083 Section 8) | `page.tsx` landing no longer has bank file CTA; bank file is Step 6 in processing wizard | [ ] |
| D04 | Remittances is a real child workspace, not a dead link (S083 Section 9.2) | `/dashboard/hr/payroll/remittances` returns 200 with SSS/PhilHealth/Pag-IBIG/BIR selector | [ ] |
| D05 | Finance companion access via deep links (S083 Decision #28) | Finance role can reach `/processing` and `/remittances` via direct URL (RBAC allows HR_ADMIN + Finance view) | [ ] |
| D06 | No visible control without a real action or explicit disabled reason (S026 shell prevention) | Zero placeholder buttons or disabled-without-explanation states in delivered pages | [ ] |
| D07 | Toast-only failure handling is forbidden (S083 success outcome #11) | All backend errors captured via `set_backend_observability_context` + Sentry; no silent toast-only failure paths | [ ] |
| D08 | Dense surfaces work on 14-inch laptop + mobile fallback | Both pages render correctly at 1366×768 and 375px viewport | [ ] |
| P0-1 | Payroll payable account configured | Is default_payroll_payable_account set on Company record? | [ ] |
| P0-2 | Income tax slab assigned to all SSAs | Do all 522 SSAs have income_tax_slab assigned? | [ ] |
| P0-3 | All active employees have SSA | Do all active employees have at least one submitted SSA? | [ ] |
| P0-4 | Remittance query passes type per-call | Does the remittance query pass remittance_type per-call? | [ ] |

---

## 3. Ground-Truth Lock

| Claim | Evidence Source |
|-------|----------------|
| 0 payroll entries, 0 salary slips in BEI | S076 audit findings |
| Missing `default_payroll_payable_account` | S076 day-zero blockers |
| 0 income_tax_slab assignments | S076 day-zero blockers |
| 33 employees without salary structure | S076 day-zero blockers |
| Existing backend endpoints | `hrms/api/payroll.py` (read before Phase 1 begins) |
| Query layer exists | `../bei-tasks/lib/queries/hr-payroll.ts` |
| RBAC: Payroll under HR_ADMIN | Confirmed in S083 scope |
| Remittances currently 404 | `../bei-tasks/app/dashboard/hr/payroll/page.tsx` dead link |

**Data Integrity Rule:** After any compaction, re-read `hrms/api/payroll.py` and `../bei-tasks/lib/queries/hr-payroll.ts` before writing code. Do NOT trust remembered function signatures.

---

## 4. Duplication Audit

### Existing endpoints to EXTEND (not replace):

| Endpoint | Location | S115 Action |
|----------|----------|-------------|
| `get_payroll_processing_status(payroll_entry)` | `hrms/api/payroll.py` | USE as-is for Step 3 progress tracking |
| `get_government_remittance(month, year, remittance_type)` | `hrms/api/payroll.py` | USE as-is for remittances employee breakdown |
| `generate_bank_file(payroll_entry)` | `hrms/api/payroll.py` | USE as-is for Step 6 bank file download |
| `get_payroll_dashboard` | `hrms/api/payroll.py` | NOT touched — owned by S112 |
| `get_payroll_comparison(from_date, to_date)` | `hrms/api/payroll.py` | NOT touched — owned by S112 |

### New endpoints S115 adds:

| New Endpoint | Purpose |
|-------------|---------|
| `get_payroll_readiness_check` | Pre-flight validation: payable account, tax slab, salary structures, bank details |
| `get_processing_blockers` | Employee-level list: who is blocked and why |
| `start_payroll_processing` | Initiate payroll entry creation with validation gate |
| `get_remittance_summary` | Aggregated totals by remittance type and period |

### Dead-link replacement:

| Current State | S115 Replacement |
|--------------|-----------------|
| `/remittances` → 404 | `/remittances` → real page with type selector + breakdown |
| Bank file floating CTA on landing | Step 6 in `/processing` wizard |

---

## 5. Files This Sprint Owns (Exclusive)

**Creates (new files):**
- `F:\Dropbox\Projects\bei-tasks\app\dashboard\hr\payroll\processing\page.tsx`
- `F:\Dropbox\Projects\bei-tasks\app\dashboard\hr\payroll\remittances\page.tsx`

**Extends (adds new functions only):**
- `F:\Dropbox\Projects\BEI-ERP\hrms\api\payroll.py` — new functions: `get_payroll_readiness_check`, `get_processing_blockers`, `start_payroll_processing`, `get_remittance_summary`
- `F:\Dropbox\Projects\bei-tasks\lib\queries\hr-payroll.ts` — new query/mutation hooks for S115 endpoints

**Does NOT touch:**
- `../bei-tasks/app/dashboard/hr/payroll/page.tsx` → S112 owns
- `hrms/api/payroll_compensation.py` → S113 creates
- `../bei-tasks/lib/roles.ts` → S112 handles
- Any compensation, sensitive-changes, current-cutoff, review-output, or history routes

---

## 6. Agent Boot Sequence

Execute in order. Do not skip steps.

**Step 1 — Read the sprint registry entry**
```
docs/plans/SPRINT_REGISTRY.md
```
Confirm S115 is registered. If not, stop and alert Sam.

**Step 2 — Checkout the sprint branch**
```bash
cd F:/Dropbox/Projects/BEI-ERP
git checkout s115-payroll-processing-remittances
```
If branch does not exist:
```bash
git checkout -b s115-payroll-processing-remittances
```

**Step 3 — Read existing backend (ground-truth lock)**
```
F:\Dropbox\Projects\BEI-ERP\hrms\api\payroll.py
```
Map all existing function signatures before writing any new code.

**Step 4 — Read existing query layer**
```
F:\Dropbox\Projects\bei-tasks\lib\queries\hr-payroll.ts
```
Understand existing query structure before adding new hooks.

**Step 5 — Read current landing page (understand dead links)**
```
F:\Dropbox\Projects\bei-tasks\app\dashboard\hr\payroll\page.tsx
```
Confirm what is dead, what exists. Do NOT modify this file.

**Step 6 — Read RBAC file (read-only)**
```
F:\Dropbox\Projects\bei-tasks\lib\roles.ts
```
Understand which roles can access payroll routes. Do NOT modify.

**Step 7 — Read Sentry utility**
```
F:\Dropbox\Projects\BEI-ERP\hrms\utils\sentry.py
```
Confirm `set_backend_observability_context` signature before using.

**Step 8 — Confirm bei-tasks dev environment**
```bash
cd F:/Dropbox/Projects/bei-tasks && npm run build 2>&1 | tail -20
```
Confirm clean build before adding new pages.

---

## 7. Shell Prevention

### Forbidden patterns in this sprint:

| Pattern | Why Forbidden |
|---------|--------------|
| Placeholder buttons that show alerts or "coming soon" | S026 shell prevention — no visible control without real action |
| Toast-only error handling on backend failures | S083 Decision — structured Sentry telemetry required |
| Enabling "Start Payroll" without readiness check gate | S076 — would result in cryptic Frappe errors |
| Hardcoded employee lists or contribution amounts | Must come from backend endpoints |
| Skipping empty-state handling | BEI has 0 payroll entries — empty states are the first-run experience |
| One-click payroll button | S083 Decision #18 — step wizard required |

### Build integrity gates (must pass before Phase closes):

**After any backend change:**
```bash
cd F:/Dropbox/Projects/BEI-ERP
bench --site current.localhost migrate
python -c "import hrms.api.payroll; print('import OK')"
```

**After any frontend change:**
```bash
cd F:/Dropbox/Projects/bei-tasks
npm run build
npm run lint
```

### Vertical slice first:

Phase 1 must deliver one working end-to-end path before building out: **readiness check endpoint → readiness check UI in Step 1 of processing wizard**. This proves backend/frontend integration is working before adding remaining steps.

---

## 8. Phase Budget Contract

Total budget: 33 units. No phase exceeds 12 units.

### Phase 0 — Frappe Configuration & Data Fixes (8 units)

**HARD BLOCKERS — must be resolved before Phase 1 processing wizard can succeed.**

**Task 1 — Set `default_payroll_payable_account` on Company "Bebang Enterprise Inc." (2 units):**

- Query: `frappe.get_doc("Company", "Bebang Enterprise Inc.")` → set `default_payroll_payable_account` to the correct GL account
- **HARD BLOCKER: Without this, Payroll Entry creation fails with GL posting error.**
- Note: The correct account must be confirmed — check Chart of Accounts for a "Payroll Payable" or "Salaries Payable" account. If none exists, create one under Current Liabilities.

**Task 2 — Assign Income Tax Slab to all 522 Salary Structure Assignments (2 units):**

- Tax slab name: "TRAIN Law 2025 - Philippines" (confirmed exists)
- Script: `frappe.db.sql("UPDATE tabSalary Structure Assignment SET income_tax_slab='TRAIN Law 2025 - Philippines' WHERE docstatus=1 AND (income_tax_slab IS NULL OR income_tax_slab='')")`
- **HARD BLOCKER: Without this, BIR withholding tax computes as zero for all employees.**

**Task 3 — Create Salary Structure Assignments for 45 employees who lack them (2 units):**

- Get list: active employees without submitted SSA
- Assign appropriate structure (HO Staff - Regular or Store Staff - Regular based on branch)
- Submit the assignments
- **Note: These 45 employees cannot be included in payroll without an SSA.**

**Task 4 — Fix `governmentRemittance` query hook in `../bei-tasks/lib/queries/hr-payroll.ts` (2 units):**

- Current: makes 1 call without `remittance_type` parameter
- Fix: create separate query options per type (SSS, PhilHealth, Pag-IBIG, BIR) each passing the required `remittance_type` parameter

**Tolerated gaps (explicitly documented, NOT blocking):**
- 54 employees missing bank details → bank file will exclude them (enrichment in progress)
- TIN/SSS/PhilHealth/Pag-IBIG statutory IDs → remittance reports will be incomplete (enrichment in progress)
- These are employee enrichment tasks, not code blockers

**Gate:** `default_payroll_payable_account` is set. All 522 SSAs have `income_tax_slab`. All active employees have at least one submitted SSA. Remittance query passes `remittance_type` per-call.

---

### Phase 1 — Backend Readiness/Blockers + Processing Step Wizard (10 units)

**Backend tasks (4 units):**
- [ ] 1u — Read existing `payroll.py` fully, map all function signatures
- [ ] 1u — Implement `get_payroll_readiness_check` with Sentry context
- [ ] 1u — Implement `get_processing_blockers` (employee-level, with S076 blocker categories) with Sentry context
- [ ] 1u — Implement `start_payroll_processing` with validation gate + Sentry context

**Frontend tasks — Processing wizard (6 units):**
- [ ] 1u — Scaffold `/processing/page.tsx` with 6-step wizard shell (no placeholder content)
- [ ] 1u — Step 1: Period selector (cutoff date range input)
- [ ] 1u — Step 2: Employee review panel with readiness check gate; blockers shown with owner/reason
- [ ] 1u — Step 3: Generate salary slips with progress tracking via `get_payroll_processing_status`
- [ ] 1u — Step 4: Review panel (summary totals, outlier detection placeholder wired to real data)
- [ ] 1u — Step 5 + Step 6: Submit salary slips → generate bank file (via existing `generate_bank_file`)

**Phase 1 exit gate:** `/processing` renders with readiness check, blockers surface for S076 state, Step 1-2 navigation works, clean `npm run build`.

### Phase 2 — Remittances View + Export + Backend Summary (8 units)

**Backend tasks (2 units):**
- [ ] 1u — Implement `get_remittance_summary` (aggregated totals by type and period) with Sentry context
- [ ] 1u — Extend query layer `hr-payroll.ts` with all S115 query/mutation hooks

**Frontend tasks — Remittances (6 units):**
- [ ] 1u — Scaffold `/remittances/page.tsx` with remittance type selector (SSS, PhilHealth, Pag-IBIG, BIR)
- [ ] 1u — Monthly view with employee-level breakdown via `get_government_remittance`
- [ ] 1u — Summary totals per remittance type per month
- [ ] 1u — Year-to-date accumulation view
- [ ] 1u — Export to CSV/Excel for each remittance type
- [ ] 1u — Empty state handling for periods with no payroll data (first-run experience)

**Phase 2 exit gate:** `/remittances` renders with type selector, SSS/PhilHealth/Pag-IBIG/BIR each loads (empty state acceptable), export downloads a valid CSV, clean `npm run build`.

### Phase 3 — Sentry Instrumentation + L1–L4 Certification + Closeout (7 units)

- [ ] 1u — Audit all new backend endpoints for `set_backend_observability_context` compliance
- [ ] 1u — Audit frontend pages for structured error handling (no toast-only paths)
- [ ] 1u — L1: Unit tests — readiness check returns correct blocker categories for S076 state
- [ ] 1u — L2: Integration tests — processing wizard step transitions, remittance data loads
- [ ] 1u — L3: Workflow scenario execution (all 6 scenarios from Section 10)
- [ ] 1u — L4: Regression — confirm S112 landing page unbroken, S113 routes unbroken
- [ ] 1u — Closeout: requirements regression checklist, sprint registry update, PR creation

**Phase 3 exit gate:** All L3 scenarios pass, requirements regression checklist complete, no regressions in S112/S113 owned routes.

---

## 9. Sentry Observability

### Backend (Python/Frappe)

Every new `@frappe.whitelist()` function MUST call `set_backend_observability_context` as its first meaningful line:

```python
from hrms.utils.sentry import set_backend_observability_context

@frappe.whitelist()
def get_payroll_readiness_check():
    set_backend_observability_context(
        module="payroll",
        action="get_payroll_readiness_check",
        mutation_type="read",
    )
    # ... rest of function

@frappe.whitelist()
def get_processing_blockers():
    set_backend_observability_context(
        module="payroll",
        action="get_processing_blockers",
        mutation_type="read",
    )

@frappe.whitelist()
def start_payroll_processing():
    set_backend_observability_context(
        module="payroll",
        action="start_payroll_processing",
        mutation_type="create",
    )

@frappe.whitelist()
def get_remittance_summary():
    set_backend_observability_context(
        module="payroll",
        action="get_remittance_summary",
        mutation_type="read",
    )
```

### Frontend (Next.js/React)

`@sentry/nextjs` auto-instruments Next.js API routes. No extra code needed for route handlers.

For client-side structured errors in processing wizard and remittances:
```typescript
import { captureExceptionWithContext } from "@/lib/sentry-observability";

captureExceptionWithContext(error, {
    module: "payroll",
    action: "processing_wizard_step_transition",  // or "remittances_export"
});
```

**Forbidden:** Toast-only failure handling. Every caught exception in processing or remittances must reach Sentry.

---

## 10. L3 Workflow Scenarios

All 6 scenarios must be executed with real user session (not API token) before sprint closes.

| # | User | Action | Expected Outcome | Failure Means |
|---|------|--------|-----------------|---------------|
| L3-01 | test.hr@bebang.ph | Navigate to `/dashboard/hr/payroll/processing` | Processing page loads with 6-step wizard; Step 1 (period selector) active | Processing route broken or blank page |
| L3-02 | test.hr@bebang.ph | Click "Check Readiness" / advance to Step 2 | Readiness check runs; shows S076 blockers: missing payable account, missing tax slab assignments, 33 employees without salary structure — each with owner and remediation path | Readiness check endpoint broken or blockers not surfaced |
| L3-03 | test.hr@bebang.ph | Attempt to advance past Step 2 with S076 blockers present | UI blocks progression; explicit message lists which blockers remain; no Frappe traceback | Blocked-state handling missing; user reaches Step 3 with blockers present |
| L3-04 | test.hr@bebang.ph | Navigate to `/dashboard/hr/payroll/remittances` | Remittances page loads with type selector showing SSS, PhilHealth, Pag-IBIG, BIR | Remittances route broken or 404 |
| L3-05 | test.hr@bebang.ph | Select "SSS" remittance type, month = March 2026 | SSS remittance data loads; if no payroll run, empty state shown with explanatory message; Export button visible | Remittance query broken; blank page with no empty state |
| L3-06 | test.hr@bebang.ph | Click "Export" on SSS remittance (March 2026) | CSV file downloads; file contains employee-level SSS contribution breakdown (even if empty/header-only for first-run state) | Export fails silently; toast error only; no download triggered |

---

## 11. Certification Coverage Contract

| Level | What is tested | Pass criteria |
|-------|---------------|---------------|
| L1 — Unit | `get_payroll_readiness_check` returns correct categories for S076 state; `get_processing_blockers` returns employee list with correct blocker reasons | Python assertions pass; import succeeds |
| L2 — Integration | Processing wizard step transitions (Step 1→2→blocked); remittance type selector loads data via backend; query layer hooks resolve without error | Pages render, no console errors, API calls return 200 or structured error |
| L3 — Workflow | All 6 scenarios in Section 10 | Each scenario produces the expected outcome with zero silent failures |
| L4 — Regression | S112 landing page (`/payroll/page.tsx`) unmodified and still renders; S113 routes unaffected | `git diff` shows no changes to S112/S113 owned files; pages load in dev |

---

## 12. Autonomous Execution Contract

An agent executing this sprint MUST:

1. Follow the Agent Boot Sequence (Section 6) fully before writing any code
2. Re-read `hrms/api/payroll.py` and `hr-payroll.ts` after any compaction — never trust remembered signatures
3. Run build integrity gates after every backend or frontend change
4. Complete the vertical slice (readiness check end-to-end) before building remaining steps
5. Surface all S076 blockers via structured UI — never enable a control that will fail
6. Never touch S112-owned or S113-owned files (see Section 5)
7. After 3 consecutive failures on the same approach: STOP, write failure summary to `tmp/s114-blockers.md`, alert Sam

An agent executing this sprint MUST NOT:

- Replace any existing endpoint in `payroll.py` (extend only)
- Add bank file CTA to the landing page (it belongs in Step 6 of processing)
- Add placeholder buttons or "coming soon" states
- Handle backend errors with toast only
- Commit to `production` or `develop` directly — all work goes to `s115-payroll-processing-remittances`

---

## 13. Signoff Model

**Single owner:** Sam Karazi (sam@bebang.ph), CEO

No sprint phase closes without Sam's explicit approval. Deliverables for each phase:

| Phase | Deliverable for Review |
|-------|----------------------|
| Phase 1 | `/processing` page with working readiness check and step wizard (Steps 1-6 structured, Steps 1-2 fully functional) |
| Phase 2 | `/remittances` page with all 4 remittance types loading, export working |
| Phase 3 | L3 scenario results, requirements regression checklist, PR link |

---

## 14. Status Reconciliation Contract

At the start of each work session on this sprint:

1. Run `git log --oneline -10` on branch `s115-payroll-processing-remittances`
2. Check which phases are marked complete in this plan
3. If plan phase status and git log disagree, re-read relevant files to re-establish ground truth
4. Do NOT trust conversation context for "what was done last session" — verify from git

Sprint status field transitions: `Planned` → `In Progress` → `Complete`

Update `docs/plans/SPRINT_REGISTRY.md` when status changes.

---

## 15. Closeout Phase

Final checklist before marking sprint Complete:

- [ ] All 6 L3 scenarios passed with real user session
- [ ] Requirements regression checklist (Section 2) all checked
- [ ] `hrms/api/payroll.py` has 4 new endpoints, all with Sentry context, none replacing existing
- [ ] Processing page at `/dashboard/hr/payroll/processing` renders with 6-step wizard
- [ ] Remittances page at `/dashboard/hr/payroll/remittances` renders with 4 remittance types
- [ ] Bank file CTA removed from landing page dead-link state (note: S112 owns landing; if CTA removal requires S112 coordination, flag to Sam)
- [ ] No changes to S112 or S113 owned files (`git diff` clean on those paths)
- [ ] `npm run build` passes on bei-tasks
- [ ] `bench migrate` clean on BEI-ERP
- [ ] PR created against `production` with description referencing S115 and S083
- [ ] `SPRINT_REGISTRY.md` updated: S115 status → Complete, completed_date set
- [ ] This plan file updated: `completed_date` and `execution_summary` filled in

---

## 16. Anti-Rewind Protection

This section documents what has been decided so no future agent session reverses these decisions.

| Decision | Rationale | Do Not Change Without Sam's Approval |
|----------|-----------|--------------------------------------|
| 6-step processing wizard | BEI has never run payroll; visibility into each step is required | Do not collapse to one-click |
| Readiness check blocks progression | S076 blockers would cause cryptic Frappe errors if allowed through | Do not skip readiness gate |
| Bank file in Step 6, not floating CTA | Logical flow: generate → review → submit → bank file | Do not add bank CTA back to landing |
| Remittances as real child workspace | Was a dead link; this sprint makes it real | Do not revert to dead link |
| Toast-only failure forbidden | Sentry telemetry required for payroll errors | Do not simplify error handling to toast-only |
| Finance deep-link access | Finance needs to view processing + remittances for month-end close | Do not restrict to HR_ADMIN only without asking |

---

## 17. Execution Workflow Reference

```
Boot Sequence (Section 6)
    ↓
Phase 1: Backend endpoints (readiness + blockers + start_processing)
    + Processing wizard (Steps 1-6, Steps 1-2 fully functional)
    ↓ Phase 1 exit gate
Phase 2: Backend remittance_summary
    + Remittances page (type selector + breakdown + export + empty states)
    + Query layer extensions
    ↓ Phase 2 exit gate
Phase 3: Sentry audit → L1 → L2 → L3 (all 6 scenarios) → L4 regression
    ↓
Closeout checklist → PR → Sprint Registry update
```

**Parallel sprint awareness:** S112 and S113 are running in parallel. Before any `git merge` or file edit outside owned files list, verify coordination with Sam.

---

*Sprint S115 — Created 2026-03-24 — Part of S083 Payroll War Room replacement (S112 + S113 + S115)*
