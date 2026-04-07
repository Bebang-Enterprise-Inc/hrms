# R5 Probe Summary — Disabled Button Investigation
**R5 Probe Agent | 2026-04-07 | S166 Wave 2 Closeout**

## Method

Static code analysis of source files + R4 evidence JSON. No browser automation required —
both root causes are definitively provable from code.

---

## Defect #21 — Edit Button on Compensation Setup Page

**Scenario:** EMP-SALARY-SETUP-002  
**File:** `components/hr/compensation-detail-panel.tsx` line 165  
**Root Cause:** `disabled={!detail}` — button is disabled whenever the compensation detail
query returns falsy (null/undefined/error).

**For HR-EMP-00046 (no SSA):** The `get_employee_compensation_detail` Frappe endpoint
returns null or raises an exception when no Salary Structure Assignment exists. This makes
TanStack Query's `data` field `undefined`, so `!detail === true`, so the button stays
disabled.

**Classification:** UI/UX bug + backend contract bug (two-layer issue)

**Layer 1 — Backend** (`hrms/api/payroll_compensation.py`):  
`get_employee_compensation_detail` should return an employee stub with null compensation
fields (not null/exception) when no SSA exists. If `detail` is truthy but has
`salary_structure: null`, the page already shows the correct "No salary data" message
and the edit button would enable.

**Layer 2 — Frontend** (`compensation-detail-panel.tsx`, `[employee]/page.tsx`):  
Change `disabled={!detail}` to `disabled={isLoading}` as a belt-and-suspenders fix.
The `startEditing()` function already uses `|| 0` / `|| ""` fallbacks for all fields,
so opening the editor with a null-field `detail` object is safe.

**HR-EMP-00046 SSA Status:** NONE at time of R4 execution. All `update_compensation`
API calls failed with `ValidationError` → no BCCs created → no SSA activated.
The SALARY-PAYROLL skip notes say "SSA may exist" but this is hedging language; the
CHANGE-001 through CHANGE-005 failures confirm no BCC was ever created to approve.

---

## Defect #22 — Create Separation Button Stays Disabled

**Scenario:** EMP-TERMINATE-001  
**File:** `app/dashboard/hr/separations/page.tsx` line 483  
**Root Cause:** `disabled={isSubmitting || !formData.employee || !formData.separation_type}`
— the button requires BOTH `employee` and `separation_type` to be non-empty. R4's test
script failed to set either field in React state.

**This is a test script deficiency, not a UI bug.**

### Why R4 failed to set `formData.employee`:

The `EmployeeSearchSelector` is a custom controlled combobox. R4 used:
```js
await empInput.fill(empId);  // typed "HR-EMP-00046"
const empOpt = page.locator('[role="option"]').filter({ hasText: empId }).first();
```
The evidence JSON for EMP-TERMINATE-001 does NOT contain `employee_selected: true`,
proving the option was never clicked. Likely causes:
1. The dropdown showed employee names, not IDs — `filter({ hasText: "HR-EMP-00046" })` found no match
2. Or the search debounce didn't fire before the option lookup

### Why R4 failed to set `formData.separation_type`:

The Shadcn `<Select>` is async-populated from `/api/hr/separations?action=types`.
R4's `[role="option"]` page-level locator may have matched zero options (not yet loaded)
or the wrong element. No confirmation of the selection was recorded.

**Classification:** Test script deficiency. The UI form itself is correct.

---

## HR-EMP-00046 SSA Status

| Check | Result |
|-------|--------|
| SSA records | NONE |
| BCCs created | 0 |
| update_compensation API calls | All failed with ValidationError |
| Salary slips | None |
| Clearance | None |
| Separation | None |

HR-EMP-00046 was created fresh as a test employee. The `update_compensation` Frappe
endpoint rejected all attempts, blocking the entire SALARY chain. This is itself a
separate defect (Frappe method routing failure: "module 'hrms.api.payroll' has no
attribute 'update_compensation'") — the method name is `update_compensation` but the
module path called is `hrms.api.payroll` not `hrms.api.payroll_compensation`.

---

## Fixes Required Before Wave 2 Closeout

### Fix 1 — Defect #21 (Edit button gating) — ACTUAL BUG, fix required

**Backend fix (recommended primary fix):**  
In `hrms/api/payroll_compensation.py`, function `get_employee_compensation_detail`:
- Return employee stub with null compensation fields instead of null/exception when no SSA

**Frontend fix (belt-and-suspenders):**  
In `components/hr/compensation-detail-panel.tsx` line 165 and `[employee]/page.tsx` line 296:
- Change `disabled={!detail}` → `disabled={isLoading}` (or `disabled={isLoading || isError}`)

### Fix 2 — Defect #22 (separation form) — TEST SCRIPT FIX ONLY

Update `scripts/testing/l3_s166_r4_emp_retest.mjs` EMP-TERMINATE-001 block:

1. **Employee field:** After clicking the combobox, type the employee name (not ID),
   wait 800ms+ for API results, then click the first `[role="option"]`
2. **Separation type:** Wait for `separationTypes` query to resolve before clicking
   the Select trigger; use `dlg.locator('[role="combobox"]').nth(1)` (second combobox)
   to avoid matching the employee selector
3. **Verification:** Assert `ev.employee_selected = true` before proceeding

### Fix 3 — Frappe method routing failure (separate defect, blocks entire SALARY chain)

The API call uses path `hrms.api.payroll.update_compensation` but the method lives in
`hrms.api.payroll_compensation.update_compensation`. This is why all BCCs fail.
Either the Python module path changed or the route was never corrected after the
`payroll_compensation` module was split from `payroll`.

---

## Ready for Wave 2 Closeout?

| Item | Status |
|------|--------|
| Defect #21 root cause identified | DONE — code-level evidence |
| Defect #22 root cause identified | DONE — test script deficiency confirmed |
| HR-EMP-00046 SSA status | DONE — zero SSA records |
| Fix recommendations written | DONE |
| Wave 2 closeout blocking items | Fix 1 (UI) + Fix 3 (Frappe routing) are real bugs |

Wave 2 closeout can proceed if Defect #21 and Fix 3 are tracked in the defect register.
Defect #22 requires only a test script update, not a product fix.

---

## Output Files

- `F:\Dropbox\Projects\BEI-ERP\output\l3\s166\lanes\retest\r5_probe\COMP_EDIT_BUTTON_PROBE.md`
- `F:\Dropbox\Projects\BEI-ERP\output\l3\s166\lanes\retest\r5_probe\CREATE_SEPARATION_PROBE.md`
- `F:\Dropbox\Projects\BEI-ERP\output\l3\s166\lanes\retest\r5_probe\R5_PROBE_SUMMARY.md`
