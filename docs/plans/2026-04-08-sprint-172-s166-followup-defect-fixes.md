---
sprint_id: S172
display: Sprint 172
title: "S166 Follow-up Defect Fixes — 15 OPEN/PARTIAL defects after S170 partial deploy + 2026-04-08 audit"
branch: s172-s166-followup-defect-fixes
status: PHASE_8_READY
planned_date: 2026-04-08
completed_date: null
depends_on: S166 (catalog + audit), S170 (partial fixes already deployed), audit PR #496
total_work_units: 71
execution_type: product-code-fix-sprint + L3-retest
frontend_pr: "Bebang-Enterprise-Inc/BEI-Tasks#362, #363, #364, #365, #366"
backend_pr: "Bebang-Enterprise-Inc/hrms#507, #509, #511, #514"
sprint_registry_row: "S172 reserved on 2026-04-08. Branch: s172-s166-followup-defect-fixes. Parent: origin/production (post #497 merge)."
---

# S172: S166 Follow-up Defect Fixes

# ═══════════════════════════════════════════════════════════════════════
# ▶ PHASE 8 L3 RETEST HANDOFF — READ THIS SECTION FIRST
# ═══════════════════════════════════════════════════════════════════════

**You are the fresh agent running Phase 8 L3 retest.** Everything you need is in this section. If you find yourself needing to read the rest of the plan, something is wrong — check the "read only until here" marker below.

## Context (30 seconds)

S172 shipped 13 defect fixes across 8 PRs (merged 2026-04-08 → 2026-04-09):

| Repo | PRs merged | Defects fixed |
|---|---|---|
| hrms | #507, #509, #511, #514 | #6, #21, #16, #18, #8, #9, #11, #15, #20, #24 (+traceability retrofit in #514) |
| BEI-Tasks | #362, #363, #364, #365, #366 | #6, #21, #19, #13, #14 |

All PRs deployed to production (hrms via Frappe bench, bei-tasks via Vercel). Your job: drive real browser through the 8 retest scenarios below and produce audit-proof evidence. You do NOT write code. You do NOT merge PRs.

## Rules (non-negotiable, from post-PR #497 `/l3-v2-bei-erp` + S092 + S099)

1. **Real browser only.** Use Playwright headless against `https://my.bebang.ph`. Script pattern lives at `scripts/testing/l3_s166_lane_h_runner.mjs`. No local dev server, no mock backend.
2. **No API shortcuts. Ever.** Filling a form via a direct `fetch('/api/method/*')` call is NOT L3 — it's L1. If you can't drive the UI for any reason, the scenario is **BLOCKED**, not PASS. Examples of shortcuts that auto-REJECT the scenario at audit:
   - Using `page.evaluate(() => fetch('/api/method/...'))` to bypass the form
   - Using `frappe.call()` in page context instead of clicking visible buttons
   - Constructing the API payload yourself and POSTing directly
   - Skipping form field interactions because "the test only cares about the submit response"
3. **Minimum interaction contract per scenario.** Each scenario below has a `REQUIRED_ACTIONS_COUNT`, a `REQUIRED_SELECTORS` list, and a `REQUIRED_NETWORK` list. Evidence is REJECTED by the audit gate if any of these are not present in the written evidence file.
4. **Evidence file shape (strict).** For each scenario write:
   ```
   output/l3/s172/retest/<scenario_id>/evidence.json
   ```
   with this exact shape (fields marked `required:true` cannot be empty):
   ```json
   {
     "scenario_id": "RT-S172-NN",
     "started_at": "<ISO PHT timestamp>",
     "ended_at": "<ISO PHT timestamp>",
     "url": "<actual URL the test ran against>",
     "login_user": "<test email>",
     "actions": [
       {"t": "<iso>", "kind": "click|fill|select|waitForSelector|reload", "selector": "<css>", "value": "<text or null>"}
     ],
     "selectors_seen": ["<css of every selector the runner asserted visible>"],
     "network": [
       {"t": "<iso>", "method": "GET|POST|PUT", "url": "<relative>", "status": <int>, "response_excerpt": "<first 300 chars>"}
     ],
     "screenshots": [
       {"label": "pre|post|<step-name>", "path": "<relative path>", "bytes": <int>, "taken_at_url": "<url>"}
     ],
     "ssm_queries": [
       {"sql": "<query>", "rows": <int>, "result_excerpt": "<first 500 chars>"}
     ],
     "negative_assertions": [
       {"description": "<what should NOT be visible>", "satisfied": true}
     ],
     "runner_status": "PASS|FAIL|BLOCKED|NEW_DEFECT",
     "runner_verdict_note": "<1 sentence>"
   }
   ```
   Minimum sizes audit gate enforces per scenario:
   - `actions[]` length ≥ the scenario's `REQUIRED_ACTIONS_COUNT`
   - Every item in `REQUIRED_SELECTORS` must appear in `selectors_seen[]`
   - Every item in `REQUIRED_NETWORK` must appear in `network[]` (method + URL pattern match)
   - `screenshots[]` length ≥ 2 (pre + post minimum); each file must be ≥ 5000 bytes on disk
   - Every `ssm_queries[]` entry the scenario calls for must be present with row count recorded
   - Every `negative_assertions[]` entry the scenario calls for must have `satisfied: true`
5. **Independent audit gate (MANDATORY).** After finishing the runner pass, you MUST dispatch a **separate subagent in a clean context** (via the Agent tool, `general-purpose` type) with the audit-gate brief below. The orchestrator reads `output/l3/s172/retest/AUDIT_REPORT.md` and `AUDIT_PASSED.flag`, NOT your self-report. Do not skip this. This rule exists because S166 R3 fabricated a PASS verdict on EMP-UX-004 (corrupt-success incident corrected by the 2026-04-08 audit).
6. **`SUMMARY_LIED` detection rubric.** The audit gate flags a scenario as SUMMARY_LIED (worse than FAIL — it means the runner is compromised) when any of these are true:
   - `runner_status = PASS` but `actions[]` length < `REQUIRED_ACTIONS_COUNT`
   - `runner_status = PASS` but any `REQUIRED_NETWORK` endpoint missing
   - `runner_status = PASS` but any required SSM query returned 0 rows or wrong row count
   - `runner_status = PASS` but any screenshot file is ≤ 4999 bytes or doesn't exist
   - `runner_status = PASS` but any `negative_assertions` item is `satisfied: false`
   A single SUMMARY_LIED detection REJECTS the entire retest pass — `AUDIT_PASSED.flag` is NOT created and Sam is escalated.
7. **Anti-pollution cleanup.** Any test data you create (test employees, BCCs, IRs, SSAs, salary slips) must be soft-deleted in a `finally` block at end of run via the `/frappe-bulk-edits` SSM pattern. Do not leave `(L3 2026-04-%)` artifacts on prod. Record cleanup in `output/l3/s172/retest/CLEANUP_LOG.md`.
8. **PR-handoff.** You do not merge, you do not deploy. If a scenario reveals a defect, log it to `output/l3/s172/retest/NEW_DEFECTS.csv` and move on; do not attempt to fix it in-session.

## Test accounts (all passwords `BeiTest2026!`)

From `memory/testing-accounts.md`:

| Email | Role | Used in |
|---|---|---|
| test.hr@bebang.ph | HR Manager | HR-001, CC-001, CC-002, DC-001, PR-001, EC-001, EMP-001 |
| test.crew1@bebang.ph | Crew (Store Staff) | OT-001 |
| test.finance@bebang.ph | Accounts Manager | CC-002 (dual-control approval) |
| test.supervisor@bebang.ph | Store Supervisor | — (available if needed) |

## The 8 retest scenarios (priority-ordered)

Every scenario maps to one or more deployed defect fixes. Each scenario has explicit steps, expected outcome, and a failure meaning (what regression it would reveal).

### Scenario RT-S172-01 — Compensation list-page modal renders full form
**Covers Defect #6 + #21 + partially #16**
**URL:** `https://my.bebang.ph/dashboard/hr/payroll/compensation-setup`
**Login:** `test.hr@bebang.ph`
**Steps:**
1. Navigate to compensation-setup page
2. Wait for employee grid to load (`[data-testid="compensation-row"]` or `table tbody tr` visible, count ≥ 1)
3. Click the first employee row — capture `clicked_employee_id` from the row's `data-employee` attribute or DOM text
4. Wait for `CompensationDetailDialog` to open (selector `[role="dialog"]` visible)
5. Assert the dialog body contains visible form labels: "Base Salary", "Commission", "De Minimis", "Honorarium", "Meal", "Gasoline", "Other Fixed" (query all 7 labels)
6. Assert the "Edit" button exists and is NOT disabled (`button:has-text("Edit"):not([disabled])`)
7. Click Edit
8. Assert at least 3 input fields become editable (`input[type="number"]:not([disabled])` count ≥ 3)
9. Take post-edit screenshot
10. Click Cancel (no save)
11. Take post-cancel screenshot (dialog closed)

**REQUIRED_ACTIONS_COUNT:** 8 (minimum: goto, waitForSelector grid, click row, waitForSelector dialog, waitForSelector edit-button, click edit, waitForSelector inputs, click cancel)
**REQUIRED_SELECTORS:**
- `table tbody tr` (or `[data-testid="compensation-row"]`) — grid loaded
- `[role="dialog"]` — modal opened
- `button:has-text("Edit"):not([disabled])` — #21 fix visible
- At least 3 of `input[type="number"]` — form fields rendered (not skeleton)
**REQUIRED_NETWORK:**
- `GET` matching `/api/method/hrms.api.payroll_compensation.get_employee_compensation_detail` — status 200
- Response JSON must contain the `has_ssa` key (boolean) — this is the #21 backend fix proof
**REQUIRED_SSM_QUERIES:** none (read-only scenario)
**REQUIRED_NEGATIVE_ASSERTIONS:**
- Post-dialog screenshot does NOT contain text "No employee selected" or "Skeleton" placeholder text
- Dialog HTML does NOT contain a single `<Skeleton>` element visible after load
**REQUIRED_SCREENSHOTS:** pre-click (grid), post-open (dialog with form), post-edit (edit fields visible), post-cancel
**Expected:** modal opens with visible form fields, Edit button is enabled even with no SSA.
**Failure means:** #6 regressed (empty skeleton) OR #21 regressed (Edit button disabled). If response JSON lacks `has_ssa`, the backend fix didn't ship — escalate.

### Scenario RT-S172-02 — Compensation change activation creates SSA (end-to-end)
**Covers Defect #16 + #21**
**URL A:** `https://my.bebang.ph/dashboard/hr/employee-master` (to create test employee)
**URL B:** `https://my.bebang.ph/dashboard/hr/payroll/compensation-setup/<new_employee_id>` (to submit comp change)
**URL C:** `https://my.bebang.ph/dashboard/hr/payroll/compensation-queue` (Finance approval queue — confirm actual path via UI nav; if the queue lives elsewhere, capture the real path as `url_c` in evidence)
**Login:** `test.hr@bebang.ph` for steps 1-5, then `test.finance@bebang.ph` for steps 6-9
**Steps:**
1. As test.hr: create a fresh test employee via the employee-master "Add Employee" button (first_name="L3RT2", last_name="RETEST02", DOB=1990-01-01, gender=Male, branch=any active, company=any). Capture `new_employee_name` (HR-EMP-NNNNN) and `new_employee_id` (BEI-EMP-YYYY-NNNNN) from the create network response.
2. Navigate to `/dashboard/hr/payroll/compensation-setup/<new_employee_id>`
3. Wait for dialog/page load, click Edit
4. Fill `input[name="base_salary"]` (or the labelled input) with `25000`
5. Fill `textarea[name="reason"]` (or the labelled textarea) with `L3 retest RT-S172-02`
6. Click Save
7. Assert: toast or success banner contains "submitted for approval" (case-insensitive)
8. Assert: POST to `/api/method/hrms.api.payroll_compensation.update_compensation` OR `hrms.api.payroll_compensation.submit_sensitive_change_request` (whichever the frontend calls) is in network[] with status 200
9. Log out. Take screenshot of the logged-out state.
10. Log in as test.finance@bebang.ph
11. Navigate to the sensitive-change / compensation-change approval queue page (capture the actual URL)
12. Find the row for `new_employee_name` with reason "L3 retest RT-S172-02"
13. Click the Approve button for that row (NOT via API — click a visible button)
14. Wait for the approve network call to complete
15. Assert: POST to `/api/method/hrms.api.payroll_compensation.approve_compensation_change` (or equivalent) is in network[] with status 200
16. Assert: toast contains "approved" or "success" AND does NOT contain "activation failed"
17. Take post-approve screenshot
18. Run SSM query: `SELECT name, base FROM \`tabSalary Structure Assignment\` WHERE employee = '<new_employee_name>' AND docstatus = 1`
19. Assert: exactly 1 row returned with `base = 25000.0`
20. Cleanup (finally): SSM cancel the SSA + mark_employee_left the test employee

**REQUIRED_ACTIONS_COUNT:** 15 (create employee: goto + click + fill×5 + click; edit+save: goto + click + fill×2 + click; logout+login; approve: goto + click)
**REQUIRED_SELECTORS:**
- `[role="dialog"]` OR the compensation-setup page's Edit button container
- `input[name="base_salary"]` OR `label:has-text("Base Salary") + input`
- `textarea[name="reason"]` OR `label:has-text("Reason") + textarea`
- `button:has-text("Save")`
- Approval queue: `button:has-text("Approve")` or `[data-action="approve"]`
**REQUIRED_NETWORK:**
- `POST /api/method/hrms.api.employee_create.create_employee_direct` (or the wrapper endpoint the frontend uses) — status 200, response contains `employee_id` and `name`
- `POST /api/method/hrms.api.payroll_compensation.update_compensation` OR `...submit_sensitive_change_request` — status 200
- `POST /api/method/hrms.api.payroll_compensation.approve_compensation_change` — status 200, response NOT containing "activation failed" OR "frappe.throw"
**REQUIRED_SSM_QUERIES:**
- `SELECT name, base FROM \`tabSalary Structure Assignment\` WHERE employee = '<new_employee_name>' AND docstatus = 1` → must return exactly 1 row, `base = 25000.0`
- `SELECT status FROM \`tabBEI Compensation Change\` WHERE employee = '<new_employee_name>' ORDER BY creation DESC LIMIT 1` → must return status = 'Approved'
**REQUIRED_NEGATIVE_ASSERTIONS:**
- Approve response does NOT contain the string "Activation Failed" (the frappe.throw title from the #16 fix)
- SSA query does NOT return 0 rows (the exact pre-fix failure mode)
**REQUIRED_SCREENSHOTS:** pre-create, post-create, pre-save-comp, post-save-comp, logged-out, logged-in-as-finance, post-approve, SSM-query-result (optional)
**Expected:** SSA exists with `base=25000.0` after approval.
**Failure means:** #16 regressed — BCC reached Approved but no SSA created (the exact pre-fix silent corrupt-success). If approve response contains "Activation Failed", the #16 fix IS working (caller is now throwing instead of silently claiming success) but some downstream condition broke — log as NEW_DEFECT, not #16 regression.

### Scenario RT-S172-03 — Overtime self-service page loads for crew
**Covers Defect #19**
**URL:** `https://my.bebang.ph/dashboard/hr/overtime/apply`
**Login:** `test.crew1@bebang.ph`
**Steps:**
1. Log in as test.crew1@bebang.ph (fresh session, not test.hr)
2. Capture pre-screenshot of the login page + role in session cookie
3. Navigate to `/dashboard/hr/overtime/apply`
4. Wait for `networkidle` state
5. Assert: the form exists — locate an input or select for date, an input for hours, and a textarea/input for reason
6. Assert: the text "Access Restricted" is NOT anywhere in the page's visible text content (case-insensitive)
7. Assert: a Submit button exists and is enabled
8. Take post-load screenshot showing the rendered form
9. Do NOT submit the form (Defect #20 scenario covers submission)

**REQUIRED_ACTIONS_COUNT:** 5 (login sequence + goto + waitForSelector form + waitForSelector submit + screenshot)
**REQUIRED_SELECTORS:**
- `input[type="date"]` OR `input[name*="date"]` (date input)
- `input[type="number"]` OR `input[name*="hours"]` (hours input)
- `textarea` OR `input[name*="reason"]` (reason input)
- `button[type="submit"]:not([disabled])` (enabled Submit)
**REQUIRED_NETWORK:**
- `GET` to `/dashboard/hr/overtime/apply` (or the Next.js route — status 200)
- No `GET` / `POST` to anything returning 401/403 for the current user
**REQUIRED_NEGATIVE_ASSERTIONS:**
- Page body text does NOT contain "Access Restricted" (case-insensitive)
- Page body text does NOT contain "You don't have permission" (case-insensitive)
- No `<Lock>` icon SVG is visible in the rendered page (check via `[data-lucide="lock"]` or presence of the AccessDenied component DOM)
- Logged-in user is test.crew1@bebang.ph (verify via a `/api/method/frappe.auth.get_logged_user` call OR session cookie)
**REQUIRED_SCREENSHOTS:** login-success, post-navigation (form visible)
**Expected:** Form renders; no Access Restricted.
**Failure means:** #19 regressed — RoleGuard re-added or the removal commit didn't ship in the frontend deploy.
**Do NOT attempt to submit the form** — submission requires an existing Attendance record and that's the subject of Defect #20 (by-design). Scenario RT-S172-04 tests the error message path.

### Scenario RT-S172-04 — Overtime submit without attendance shows clear error
**Covers Defect #20**
**URL:** Same as RT-S172-03
**Login:** `test.crew1@bebang.ph` (continue from RT-S172-03 session)
**Pre-condition:** test.crew1 has no Attendance record for the target date (pick a date at least 7 days ago to be safe).
**Steps:**
1. On the OT apply form, `page.fill` the date input with a date 7+ days ago (e.g., today minus 8 days in YYYY-MM-DD)
2. `page.fill` the hours input with `2`
3. `page.fill` the reason textarea with `L3 retest RT-S172-04`
4. Take pre-submit screenshot
5. `page.click` the Submit button
6. Wait for the network response to `create_overtime_request`
7. Assert: the response status is 417 (frappe.throw returns HTTP 417) OR 400
8. Assert: the response body contains the string "attendance correction" (case-insensitive) — this is the improved #20 message
9. Assert: the UI shows a visible error toast/banner containing "attendance correction"
10. Take post-submit screenshot with the error visible

**REQUIRED_ACTIONS_COUNT:** 6 (fill date + fill hours + fill reason + click submit + wait for network + read error)
**REQUIRED_SELECTORS:**
- All from RT-S172-03 plus
- `[role="alert"]` OR `[data-sonner-toast]` OR `.toast` — the error banner
**REQUIRED_NETWORK:**
- `POST /api/method/hrms.api.overtime_request.create_overtime_request` — status 417 OR 400 (NOT 200, NOT 500)
- Response body JSON/text must contain the phrase "attendance correction" (case-insensitive)
**REQUIRED_NEGATIVE_ASSERTIONS:**
- Error message does NOT exactly match the old terse message: "No attendance record found on {date}. Overtime can only be filed for days you actually worked." (the new message is longer and explicitly mentions correction workflow)
- No OT request was actually created: SSM query `SELECT COUNT(*) FROM \`tabBEI Overtime Request\` WHERE employee IN (SELECT name FROM tabEmployee WHERE user_id='test.crew1@bebang.ph') AND attendance_date='<the date>' AND creation > NOW() - INTERVAL 5 MINUTE` → must return 0
**REQUIRED_SSM_QUERIES:**
- The COUNT query above (proves no OT request was accidentally created)
**REQUIRED_SCREENSHOTS:** pre-submit (form filled), post-submit (error visible)
**Expected:** Clear error message explaining to file an attendance correction first; no OT request created.
**Failure means:** #20 regressed to the old terse message, OR the validation check was bypassed and an OT was created without an attendance record (worse — that would be a new defect).

### Scenario RT-S172-05 — Disciplinary case create succeeds with Branch value
**Covers Defect #18 + #24**
**URL:** `https://my.bebang.ph/dashboard/hr/disciplinary`
**Login:** `test.hr@bebang.ph`
**Pre-condition:** need a target employee with a valid `branch` populated. Use the RT-S172-07 test employee if running scenarios in order, or query for any active Employee whose `branch` is not NULL.
**Steps:**
1. Navigate to `/dashboard/hr/disciplinary`
2. Click "New Case" button (visible button, not API)
3. Wait for the create form/dialog to open
4. `page.fill` or `page.selectOption` Employee = `<target_employee_id>` (capture the ID)
5. `page.fill` Incident Date = today (YYYY-MM-DD)
6. `page.selectOption` Incident Type = "Attendance" (this is `incident_type` in the payload — the frontend field name)
7. `page.selectOption` Severity = "Minor" (the frontend sends this; backend accepts via the new #24 DocType field)
8. `page.fill` Description = "L3 retest RT-S172-05"
9. Take pre-submit screenshot
10. `page.click` the Create/Submit button
11. Wait for network response to `create_incident_report`
12. Assert: response status 200 (NOT 417, NOT "Missing required field", NOT "LinkValidationError")
13. Assert: response body contains an IR name (e.g., `BEI-IR-2026-NNNN`)
14. Take post-submit screenshot
15. Run SSM query:
    ```sql
    SELECT name, employee, store, incident_category, severity
    FROM `tabBEI Incident Report`
    WHERE employee = '<target_employee>'
    ORDER BY creation DESC LIMIT 1
    ```
16. Assert: row exists with:
    - `store` = target employee's branch (verify by cross-query `SELECT branch FROM tabEmployee WHERE name='<target>'`)
    - `incident_category` = "Attendance" (proves #24 alias mapping worked)
    - `severity` = "Minor" (proves #24 new field accepts the value)
17. Cleanup (finally): SSM delete this IR row + any linked NTE/NOD

**REQUIRED_ACTIONS_COUNT:** 10 (goto + click new + select emp + fill date + select type + select severity + fill desc + click submit + wait net + screenshot)
**REQUIRED_SELECTORS:**
- `button:has-text("New Case")` OR `[data-testid="new-incident"]`
- Form inputs: employee selector, date input, incident type select, severity select, description textarea
- Submit button
**REQUIRED_NETWORK:**
- `POST /api/method/hrms.api.disciplinary.create_incident_report` — status 200
- Request payload (visible in browser network tab) must include `incident_type` AND `severity` — prove the frontend actually sent the #24-affected fields
- Response body must contain the new IR name
**REQUIRED_SSM_QUERIES:**
- `SELECT name, employee, store, incident_category, severity FROM \`tabBEI Incident Report\` WHERE employee = '<target>' ORDER BY creation DESC LIMIT 1` → must return 1 row with all 4 fields non-null AND `store` matching the employee's branch
- `SELECT branch FROM \`tabEmployee\` WHERE name = '<target>'` → cross-reference to confirm store=branch equivalence
**REQUIRED_NEGATIVE_ASSERTIONS:**
- Response body does NOT contain "LinkValidationError" (would mean #18 regressed)
- Response body does NOT contain "Missing required field: incident_category" (would mean #24 regressed)
- Response body does NOT contain "Missing required field: severity"
- The created IR's `store` is NOT NULL (would mean the #18 default-to-employee-branch fallback didn't run)
**REQUIRED_SCREENSHOTS:** pre-open (disciplinary list), form-filled, post-submit (success toast)
**Expected:** IR created end-to-end, all 4 fields persisted, no errors.
**Failure means:** #18 regressed (LinkValidationError) OR #24 regressed (field mismatch errors) OR the fallback branch population didn't run.

### Scenario RT-S172-06 — Employee Reports To autocomplete works
**Covers Defect #14**
**URL:** `https://my.bebang.ph/dashboard/hr/employee-master`
**Login:** `test.hr@bebang.ph`
**Steps:**
1. Navigate to employee-master page
2. Click any employee row to open `EmployeeDetailDialog`
3. Click the "Employment" section header to expand it (Collapsible)
4. Assert the section is expanded (`[data-state="open"]` on the CollapsibleContent)
5. Click the global "Edit" button for the Employment section
6. Assert the Reports To field is now rendered as `ReportsToLookupField` (the lookup component, not a plain `<input>`)
    - Selector: `input[list="reports-to-employee-list"]` — this exact selector IS the proof the new component rendered (the plain Input would not have the `list` attribute)
7. `page.focus` the Reports To input
8. `page.fill` the Reports To input with `ana` (or `abr` — 3 letters of any common name)
9. Wait for the search_employees network call (debounced by useQuery; should fire within 1-2 seconds)
10. After the network call, query the DOM for `datalist#reports-to-employee-list option` — assert count ≥ 1 (suggestions populated)
11. Capture the first suggestion's `value` attribute (this is the employee_id, e.g., HR-EMP-00123)
12. Take a screenshot showing the focused input with the typed text
13. Optionally: `page.fill` the input with the captured employee_id (simulates the user picking from the datalist)
14. Cancel without saving (no save network call should happen)

**REQUIRED_ACTIONS_COUNT:** 9 (goto + click row + click section + click edit + focus + fill + waitForNetwork + DOM query + screenshot)
**REQUIRED_SELECTORS:**
- `[role="dialog"]` — employee detail dialog
- `[data-state="open"]` on the Employment Collapsible content (section expanded)
- `input[list="reports-to-employee-list"]` — **this proves the ReportsToLookupField component rendered** (plain Input has no `list` attribute)
- `datalist#reports-to-employee-list` — the datalist element exists in the DOM
- At least 1 `datalist#reports-to-employee-list option` after the search fires (suggestions populated)
**REQUIRED_NETWORK:**
- `GET /api/method/hrms.api.enrichment.search_employees?query=ana*` (query parameter starts with the typed text) — status 200
- Response body is a JSON array/object with at least 1 entry containing `employee_id` and `employee_name`
**REQUIRED_NEGATIVE_ASSERTIONS:**
- The Reports To input does NOT have `type="text"` without the `list` attribute (would mean the old plain `<Input>` rendered instead of the lookup component)
- After typing, `datalist#reports-to-employee-list option` count is NOT 0 (suggestions actually populated)
**REQUIRED_SCREENSHOTS:** pre-expand (dialog open, section collapsed), post-expand (section open), post-edit (Reports To field visible), post-fill (with typed text visible)
**Expected:** `search_employees` fires, datalist populates, suggestions are selectable.
**Failure means:** #14 regressed — ReportsToLookupField component didn't render (still using old plain Input) OR `search_employees` endpoint is unreachable OR the datalist options aren't being populated.

### Scenario RT-S172-07 — Employee create returns distinct IDs across calls
**Covers Defect #8 + #11 (cleanup path)**
**URL:** `https://my.bebang.ph/dashboard/hr/employee-master`
**Login:** `test.hr@bebang.ph`
**Steps:**
1. Navigate to employee-master page
2. Click "Add Employee" button (visible button, not API)
3. Wait for the create form/dialog
4. Fill ALL required fields (one `page.fill` per field — do NOT combine):
   - First Name: `L3TEST`
   - Last Name: `RETEST07A`
   - Date of Birth: `1990-01-01`
   - Gender: `Male` (via `page.selectOption`)
   - Branch: any active branch from the dropdown (via `page.selectOption`, capture the value)
   - Company: any company from the dropdown (via `page.selectOption`)
5. Take pre-submit screenshot
6. Click Create/Submit
7. Wait for the `create_employee_direct` network response
8. Capture from network response: `employee_id_A` (BEI-EMP-YYYY-NNNNN) and `name_A` (HR-EMP-NNNNN)
9. Take post-submit screenshot
10. Close the dialog (or navigate back if the flow requires)
11. **Repeat steps 2-10** with Last Name = `RETEST07B` and capture `employee_id_B` and `name_B`
12. Assert: `employee_id_A !== employee_id_B` (the #8 fix — previously both returned BEI-EMP-2026-00004)
13. Assert: `name_A !== name_B` (sanity)
14. Assert: both `employee_id_*` match the pattern `^BEI-EMP-\d{4}-\d{5}$`
15. SSM query to confirm both employees exist with distinct `employee` field values:
    ```sql
    SELECT name, employee FROM `tabEmployee`
    WHERE name IN ('<name_A>', '<name_B>')
    ORDER BY name
    ```
16. Assert: 2 rows returned, both with non-null `employee` values, and those 2 values are distinct
17. Cleanup (finally): for both employees, call the REST endpoint for `mark_employee_left` via the UI "soft-delete" button if available, OR fall back to SSM; record the cleanup in CLEANUP_LOG.md

**REQUIRED_ACTIONS_COUNT:** 14 (6 actions per create × 2 creates = 12, + 2 for cleanup initiation)
**REQUIRED_SELECTORS:**
- `button:has-text("Add Employee")` or `[data-testid="add-employee"]`
- `input[name="first_name"]`, `input[name="last_name"]`, `input[name="date_of_birth"]`
- `select[name="gender"]`, `select[name="branch"]`, `select[name="company"]`
- `button:has-text("Create")` or `button[type="submit"]`
**REQUIRED_NETWORK:**
- **Exactly 2** `POST /api/method/hrms.api.employee_create.create_employee_direct` calls — status 200 each
- Each response body must contain both `employee_id` (matching `^BEI-EMP-\d{4}-\d{5}$`) AND `name` (matching `^HR-EMP-\d+$`)
- **The two `employee_id` values in the two responses MUST be different** (record both in evidence explicitly)
**REQUIRED_SSM_QUERIES:**
- `SELECT name, employee FROM \`tabEmployee\` WHERE name IN ('<name_A>', '<name_B>')` → 2 rows with 2 distinct non-null `employee` values
- Cleanup verification: `SELECT status, relieving_date FROM \`tabEmployee\` WHERE name IN ('<name_A>', '<name_B>')` → both rows have status='Left' and relieving_date populated
**REQUIRED_NEGATIVE_ASSERTIONS:**
- `employee_id_A` is NOT equal to `employee_id_B` (the exact regression this scenario catches)
- Neither `employee_id_*` equals the literal string `BEI-EMP-2026-00004` (the pre-fix cached value that was stuck on prod)
- Both test employees are soft-deleted before the scenario ends (cleanup actually ran)
**REQUIRED_SCREENSHOTS:** pre-create-A, post-create-A, pre-create-B, post-create-B
**Expected:** Two distinct employee_ids returned; both employees soft-deleted after.
**Failure means:** #8 regressed — `generate_bei_employee_id` still querying wrong column OR Frappe autoname drift OR the #8 fix didn't ship in the latest deploy.
**Cleanup in finally (MANDATORY):** for both employees, use `hrms.api.employee_create.mark_employee_left` (the new #11 helper, also acts as integration test for #11) with today's date, then verify via SSM that both rows are `status='Left'`. If mark_employee_left fails, fall back to direct SSM update and log the fallback in NEW_DEFECTS.csv for #11 investigation.

### Scenario RT-S172-08 — Emergency phone saves correctly via self-service path
**Covers Defect #13**
**URL:** `https://my.bebang.ph/dashboard/hr/employee-master`
**Login:** `test.hr@bebang.ph`
**Pre-condition:** a target test employee (use the RT-S172-07 employee_A or any employee whose `emergency_phone_number` is currently NULL — verify via SSM pre-check).
**Steps:**
1. Pre-check via SSM: `SELECT person_to_be_contacted, relation, emergency_phone_number FROM \`tabEmployee\` WHERE name = '<target>'` — record the starting values
2. Navigate to `/dashboard/hr/employee-master`
3. Click the target employee row to open `EmployeeDetailDialog`
4. Expand the Personal section (Collapsible `[data-state="open"]`)
5. Click the Personal section Edit button
6. `page.fill` Person to be Contacted: `Maria Dela Cruz RT08`
7. `page.fill` Relation: `Spouse`
8. `page.fill` Emergency Phone Number: `09181112222`
9. Take pre-save screenshot
10. Click Save
11. Wait for ALL 3 update network calls to complete (the frontend sends one per changed field via `update_self_service_field`)
12. Assert: all 3 POSTs to `update_self_service_field` returned status 200
13. Assert: each response body contains `"status": "success"` (or Frappe's message shape)
14. Close the dialog
15. **`page.reload()`** — MANDATORY full-page reload (not just dialog reopen) to bypass React Query cache
16. Wait for `networkidle`
17. Click the same target employee row again
18. Expand the Personal section (don't click Edit — just view)
19. Assert: the Person to be Contacted field displays "Maria Dela Cruz RT08"
20. Assert: the Relation field displays "Spouse"
21. Assert: the Emergency Phone Number field displays "09181112222" — this is the #13 fix proof
22. Take post-reload screenshot showing all 3 values visible
23. SSM verify (authoritative):
    ```sql
    SELECT person_to_be_contacted, relation, emergency_phone_number
    FROM `tabEmployee`
    WHERE name = '<target>'
    ```
24. Assert: all 3 columns are populated with the exact values we sent (not NULL, not empty string)

**REQUIRED_ACTIONS_COUNT:** 13 (goto + click row + click section + click edit + fill×3 + click save + reload + click row + click section + screenshot)
**REQUIRED_SELECTORS:**
- `[role="dialog"]`
- Personal section `[data-state="open"]`
- Inputs (by label or data-field-name): `person_to_be_contacted`, `relation`, `emergency_phone_number`
- `button:has-text("Save")`
**REQUIRED_NETWORK:**
- **Exactly 3** `POST /api/method/hrms.api.enrichment.update_self_service_field` calls — status 200 each. The field_name in the payload must match `person_to_be_contacted`, `relation`, `emergency_phone_number` (one per call).
- **CRITICAL: no calls to `/api/method/frappe.client.set_value` for these fields** — if the frontend hits set_value instead of update_self_service_field, the #13 fix didn't ship.
**REQUIRED_SSM_QUERIES:**
- Pre-check: starting state of the 3 fields (for diff comparison)
- Post-save: all 3 fields must hold the exact values the test sent
**REQUIRED_NEGATIVE_ASSERTIONS:**
- `emergency_phone_number` post-save is NOT NULL and NOT empty string (the exact pre-fix failure mode)
- No `POST /api/method/frappe.client.set_value` in network[] for any of the 3 fields (proves routing fix shipped)
- After the `page.reload()`, the dialog shows the persisted values (proves the save was durable, not React Query cache)
**REQUIRED_SCREENSHOTS:** pre-edit (fields in view mode), pre-save (fields filled), post-save (dialog closed or success toast), post-reload-re-open (fields visible with new values)
**Expected:** all 3 fields persist through save → reload → re-read.
**Failure means:** #13 regressed — either routing is back to `frappe.client.set_value` (check network[]) OR the enrichment endpoint's validators are still dropping the phone (check SSM for what actually landed).

## Optional: HR test.hr Employee list access (Defect #9 sanity)

Not a full scenario, but worth a 30-second smoke check:
1. As `test.hr`, GET `https://my.bebang.ph/api/frappe/api/resource/Employee?limit_page_length=5`
2. Assert: status 200, response JSON has `data` array (possibly empty if `permission_query_conditions` filters everything out, but NOT a 403)
3. **If 403:** #9's patch didn't run on deploy. Escalate to Sam; do NOT attempt to fix the patch from this session.

## Runner agent brief (copy-paste for dispatch)

When you (the fresh Phase 8 agent) are ready to run the scenarios:

```
You are the Phase 8 L3 retest runner for S172. A separate independent
audit gate agent WILL verify every evidence file you produce against
the plan's REQUIRED_* blocks. Corrupt success is NOT an option — the
audit gate flags any PASS verdict without matching evidence as
SUMMARY_LIED and rejects the entire pass.

Task: Run the 8 scenarios RT-S172-01 through RT-S172-08 listed in
docs/plans/2026-04-08-sprint-172-s166-followup-defect-fixes.md section
"PHASE 8 L3 RETEST HANDOFF" (top of plan, lines 17-291).

Environment:
- Real browser via Playwright headless against https://my.bebang.ph
- NOT a local dev server. NOT a mocked backend.
- Test accounts in memory/testing-accounts.md (all passwords BeiTest2026!)
- Script pattern: scripts/testing/l3_s166_lane_h_runner.mjs

HARD RULES (enforced by the audit gate):
1. No API shortcuts. If you use page.evaluate(() => fetch('/api/method/*'))
   to bypass a form, the scenario is SUMMARY_LIED.
2. For every scenario, your evidence.json MUST satisfy the scenario's
   REQUIRED_ACTIONS_COUNT, REQUIRED_SELECTORS, REQUIRED_NETWORK,
   REQUIRED_SSM_QUERIES, REQUIRED_NEGATIVE_ASSERTIONS, and
   REQUIRED_SCREENSHOTS blocks. Read each scenario's block in the plan
   BEFORE running the scenario. Do not guess.
3. Every screenshot file must be ≥ 5000 bytes on disk. Take another shot
   if the page was still loading.
4. Every REQUIRED_NETWORK endpoint must appear in your network[] with
   the expected HTTP status. The audit gate cross-checks status codes.
5. Every REQUIRED_SSM_QUERY must be executed and the real row count
   recorded. You can use /frappe-bulk-edits skill for SSM access.
6. Every REQUIRED_NEGATIVE_ASSERTION must be checked and marked as
   satisfied: true/false. The audit gate reads these.
7. For persistence scenarios (RT-S172-08), a page.reload() between save
   and re-read is MANDATORY to bypass React Query cache.

For each scenario, write:
- output/l3/s172/retest/<scenario_id>/evidence.json (strict shape per
  the plan's "Evidence file shape" section)
- output/l3/s172/retest/<scenario_id>/screenshots/*.png
- Include pre-action and post-action screenshots (minimum 2 per scenario)

If a scenario is legitimately BLOCKED (e.g., missing test data that
can't be created) or reveals a NEW_DEFECT, mark it that way honestly.
BLOCKED and NEW_DEFECT are not failures — SUMMARY_LIED is. Log new
defects to output/l3/s172/retest/NEW_DEFECTS.csv with columns:
  scenario_id, defect_description, severity, reproducer

Cleanup (MANDATORY): in a finally block, soft-delete every test
employee you create via hrms.api.employee_create.mark_employee_left
+ SSM bulk-edits. Record in output/l3/s172/retest/CLEANUP_LOG.md.

After running all 8 scenarios and writing evidence files:
- Do NOT mark any scenario PASS just because no error occurred — check
  the scenario's REQUIRED_* blocks and verify they are all satisfied.
- Do NOT run the audit gate yourself — it MUST be a separate fresh
  subagent.
- Do NOT touch git.
- STOP and report to the orchestrator: "Runner complete, evidence
  written to output/l3/s172/retest/. Dispatch audit gate agent next."
```

## Audit gate agent brief (copy-paste for dispatch — MANDATORY after runner)

```
You are the Phase 8 L3 audit gate for S172. A runner agent has written
evidence files to output/l3/s172/retest/<scenario_id>/evidence.json.
Your job is to independently verify each scenario's evidence without
trusting the runner's self-report.

You have no prior context about what the runner did. Be skeptical.
Assume corrupt success is the default and require proof of the opposite.

=== AUDIT CHECKLIST PER SCENARIO ===

For each of RT-S172-01 through RT-S172-08:

1. Open output/l3/s172/retest/<scenario_id>/evidence.json. If missing,
   mark the scenario MISSING_EVIDENCE and fail the audit immediately.

2. Load the corresponding scenario block from the plan (lines 17-291 of
   docs/plans/2026-04-08-sprint-172-s166-followup-defect-fixes.md).
   Extract the REQUIRED_ACTIONS_COUNT, REQUIRED_SELECTORS,
   REQUIRED_NETWORK, REQUIRED_SSM_QUERIES, REQUIRED_NEGATIVE_ASSERTIONS,
   REQUIRED_SCREENSHOTS blocks.

3. Actions count check:
   - len(evidence.actions) >= scenario.REQUIRED_ACTIONS_COUNT?
   - If NO → SUMMARY_LIED_ACTION_COUNT.

4. Selectors seen check:
   - Every entry in scenario.REQUIRED_SELECTORS appears in
     evidence.selectors_seen[]?
   - If NO → SUMMARY_LIED_MISSING_SELECTOR: <list the missing ones>.

5. Network check:
   - For every entry in scenario.REQUIRED_NETWORK, find a matching
     entry in evidence.network[] where the method AND URL pattern match.
   - Verify status code matches the scenario's expectation (e.g., 200
     for successful POSTs, 417 for the #20 error case).
   - For each required endpoint, verify the status code is within the
     scenario-allowed set.
   - For scenarios that say "response body must contain X", verify
     the response_excerpt actually contains X.
   - If any check fails → SUMMARY_LIED_NETWORK: <which one>.

6. SSM queries check:
   - Every REQUIRED_SSM_QUERY must have a corresponding entry in
     evidence.ssm_queries[] with the query text matching (fuzzy — at
     least the FROM table and WHERE clause shape).
   - The rows count must match the scenario's expectation (e.g., "must
     return exactly 1 row").
   - If any check fails → SUMMARY_LIED_SSM: <which query>.

7. Negative assertions check:
   - Every entry in scenario.REQUIRED_NEGATIVE_ASSERTIONS must have
     a corresponding entry in evidence.negative_assertions[] with
     satisfied: true.
   - If any is false or missing → SUMMARY_LIED_NEGATIVE: <description>.

8. Screenshot check:
   - Every entry in scenario.REQUIRED_SCREENSHOTS has a matching
     screenshots[] entry where the file exists on disk AND
     bytes >= 5000 (use `stat` / os.path.getsize to verify — do NOT
     trust the runner's self-reported bytes value).
   - Verify taken_at_url in the scenario is under my.bebang.ph.
   - If any file is missing or too small → SUMMARY_LIED_SCREENSHOT.

9. Runner status integrity:
   - If evidence.runner_status == "PASS" and ANY of the above checks
     failed, the scenario is SUMMARY_LIED. This is the worst verdict
     because it means the runner claimed success without proof.
   - If evidence.runner_status == "FAIL" or "BLOCKED" or "NEW_DEFECT"
     AND the above checks are internally consistent, the audit's
     verdict is ACCEPT_FAILURE (the runner was honest about failure).

10. Write the verdict for this scenario to AUDIT_REPORT.md:
    - scenario_id
    - audit_verdict: PASS | FAIL | BLOCKED | NEW_DEFECT | SUMMARY_LIED_* | MISSING_EVIDENCE
    - which specific required item(s) failed (if any)
    - whether any negative assertions fired
    - 1-line summary

=== OVERALL ROLLUP ===

After all 8 scenarios are audited:

- If EVERY scenario is PASS or ACCEPT_FAILURE-with-justification, create
  the empty file output/l3/s172/retest/AUDIT_PASSED.flag.
- If ANY scenario is SUMMARY_LIED_*, do NOT create the flag. The entire
  retest pass is compromised — write a top-level CRITICAL rollup in
  AUDIT_REPORT.md and stop.
- If some scenarios are PASS and others are legitimate FAIL/BLOCKED,
  create a partial report. Do NOT create the flag. List which scenarios
  need re-running.

=== ANTI-GAMING RULES ===

- Do NOT re-run any scenario. If evidence is missing or thin, the
  verdict is FAIL or SUMMARY_LIED, not "let me check for you".
- Do NOT fix evidence. Do NOT edit evidence.json files. You are the
  tester of the tester.
- Do NOT trust the runner's summary line. Check each rule independently.
- If you cannot determine whether an assertion was satisfied because
  the evidence shape is ambiguous, the verdict is FAIL, not "benefit
  of the doubt".
- If ANY screenshot file is exactly 0 bytes or smaller than 5000 bytes,
  the scenario is SUMMARY_LIED_SCREENSHOT — no exceptions for "it was
  a loading state" or "the page was empty". Take another shot or FAIL.

=== OUTPUT ===

Write AUDIT_REPORT.md with:
- Top: summary (8 scenarios audited, X PASS, Y FAIL, Z SUMMARY_LIED)
- Per-scenario verdict block (as above)
- Bottom: GO/NO-GO recommendation for Phase 9 closeout

If and only if the verdict is unanimous PASS (or PASS+ACCEPT_FAILURE with
justification), create output/l3/s172/retest/AUDIT_PASSED.flag (empty file).

You are expected to reject the first pass. Corrupt success is the default
failure mode. Require proof of correctness, not absence of proof of failure.
```

## Closeout (after audit gate creates AUDIT_PASSED.flag)

1. Update plan YAML: `status: PHASE_8_READY` → `status: COMPLETED`, fill `completed_date` (ISO PHT).
2. Update `docs/plans/SPRINT_REGISTRY.md` S172 row to COMPLETED with date + all PR refs.
3. Update `docs/plans/2026-04-08-sprint-173-s166-retest-debt-ledger.md` — flip PENDING → CLOSED_BROWSER_PASS for the ~25 S166 scenarios that were unblocked by the S172 defect fixes (the 8 RT-S172-* scenarios cover the ground-truth subset; the rest are downstream unblocks that the ledger maintainer should close only if independently verified by similar browser evidence).
4. `git add -f` (docs/ is gitignored) and commit to a new branch `s172-p9-closeout`.
5. Create PR and STOP.

## Evidence files required for closeout

- `output/l3/s172/retest/RT-S172-01/evidence.json` through `RT-S172-08/evidence.json`
- `output/l3/s172/retest/RT-S172-*/screenshots/*.png` (pre + post per scenario)
- `output/l3/s172/retest/AUDIT_REPORT.md`
- `output/l3/s172/retest/AUDIT_PASSED.flag` (empty file, created by audit gate only if all 8 PASS)
- `output/l3/s172/retest/NEW_DEFECTS.csv` (may be empty if none found)

## What-if: a scenario finds a new defect

1. Log to `output/l3/s172/retest/NEW_DEFECTS.csv` with columns: `scenario_id,defect_description,severity,reproducer`
2. Do NOT fix it in this session. Phase 8 runner is a tester, not a builder.
3. Escalate to Sam: "Phase 8 found N new defects, here they are, please decide: add to S173 ledger, or spawn a new sprint?"
4. You can still mark the other 7 scenarios PASS if their evidence is clean.

---

# 🛑 read only until here unless necessary — Plan was completed 2026-04-09 13:12 PHT

Everything below is the original build-phase plan that produced PRs #507, #509, #511, #514 (hrms) and #362, #363, #364, #365, #366 (bei-tasks). Phases 1-7 are all merged and deployed. Phase 8 runner: you do not need to read the rest unless a scenario above references a specific commit or diagnostic file you need to cross-check.

---

## ⚠️ KNOWN DEBT NOT ADDRESSED BY THIS SPRINT — READ FIRST

S172 fixes **product defects** only. It does NOT burn down the 86-row browser-proof test debt surfaced by the 2026-04-08 audit. That debt is tracked in its own sprint artifacts:

- **S173 — Debt Ledger (LOCKED catalog):** `docs/plans/2026-04-08-sprint-173-s166-retest-debt-ledger.md`
  - Lists all 86 S166 scenarios that failed the strict browser-proof audit (55 `NO_BROWSER_PROOF` + 29 `API_ONLY` + 2 `MISSING_SCREENSHOT`)
  - Breakdown by module (EMP-CREATE ×7, EMP-SALARY ×10, EMP-EDIT ×16, EMP-UX ×11, EMP-PAYROLL ×6, EMP-STUB ×6, EMP-RBAC ×5, EMP-TRANSFER ×5, EMP-LEAVE ×4, EMP-ATTENDANCE ×3, EMP-REGULARIZE ×3, EMP-BIOCHANGE ×2, EMP-ADMS ×2, EMP-PAYSLIP ×2, EMP-PHOTO ×2, plus residuals)
  - This file is the canonical audit trail. It survives compaction, cross-session handoffs, and sprint closeouts.
- **S174 — Burn-down execution sprint (continuation):** `docs/plans/2026-04-08-sprint-174-s166-browser-reproof-burndown.md`
  - 75 work units across 7 phases
  - Pure re-execution via real Playwright headless, with independent audit gate per scenario per PR #497 rule
  - Depends on S172 deploy + S173 ledger

**S172 Phase 8 retests only ~25 scenarios** (the ones directly unblocked by the 9 product fixes in Phases 1-7). The remaining ~60 scenarios in the ledger remain PENDING after S172 closes — they are NOT forgotten, they are owned by S174.

**At S172 closeout**, Phase 9 MUST update the S173 ledger file, flipping the status of the ~25 retested rows from `PENDING` to `CLOSED_BROWSER_PASS` / `CLOSED_BROWSER_FAIL` / `DEFERRED_BLOCKED`. Not updating the ledger = the sprint is non-compliant.

## Mission

Close the 15 product defects still OPEN after S166 + S170 + the 2026-04-08 audit (PR #496). Each defect has been independently verified by either a per-lane audit gate or by orchestrator-direct browser retest. This sprint fixes them, deploys, and re-runs the L3 scenarios that were previously SKIPPED because the underlying UI/backend was broken.

The strict 2026-04-08 audit caught a fabrication: R3's retest summary claimed Defect #6 was CLOSED but the underlying evidence file said `STILL_BROKEN`. PR #496 corrected the registry, PR #497 added the audit-gate rule to `/l3-v2-bei-erp`. S172 now actually fixes the bug.

**Out of scope (any of these = STOP and ask):**
- New product features beyond fixing the 15 listed defects
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
| #6 list-modal | `../bei-tasks/app/dashboard/hr/payroll/compensation-setup/page.tsx` | **CORRECTION (post-fact-check):** an earlier draft referenced `compensation-detail-dialog.tsx` which DOES NOT EXIST. The list-page row-click modal is rendered by the list page itself (or by `compensation-detail-panel.tsx` reused as a dialog). Execution agent MUST grep `../bei-tasks/app/dashboard/hr/payroll/compensation-setup/` for the row onClick handler and the modal/dialog component it opens, then apply the same `disabled={!detail}` → `disabled={isLoading}` fix AND ensure form fields render when `has_ssa: false`. |
| #21 backend | `hrms/api/payroll_compensation.py` | line 318: `def get_employee_compensation_detail(employee):` — returns null/exception when employee has no SSA |
| #16 backend | `hrms/api/payroll_compensation.py` | line 1054: `def _activate_compensation_change(doc):` — contains the try/except that swallows errors (R5 reported lines 633-639 in an older view; execution agent must read lines 1054-1100 for the actual try/except) |
| #19 frontend | `../bei-tasks/app/dashboard/hr/overtime/apply/page.tsx` | line 23: `import { RoleGuard }`. Lines 241-249 (verified post-fact-check): RoleGuard already allows `[EMPLOYEE, STORE_STAFF, STORE_SUPERVISOR, AREA_SUPERVISOR, HR_USER, HR_MANAGER, HQ_FINANCE, SYSTEM_MANAGER, ADMINISTRATOR]` (9 roles). Investigate why test.crew1 still hits "Access Restricted" — bug is likely NOT the RoleGuard list itself but somewhere else (middleware, `lib/roles.ts` mapping, or test.crew1's actual Frappe role does not map to any of those 9). |
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
| 10 | DISPUTED | OPEN | employee-master dashboard vs list (Wave 0 disagrees) |
| 11 | LOW | OPEN | Soft-delete order dependency: relieving_date before status |
| 13 | MEDIUM | OPEN | emergency_phone_number silently dropped on Employee save |
| 14 | MEDIUM | OPEN | Reports To field has no autocomplete |
| 15 | LOW | OPEN | First-of-session BSCR silently rolled back |
| 16 | HIGH | UNVERIFIED → OPEN | _activate_compensation_change silent failure (R4 couldn't reach due to #21) |
| 18 | HIGH | OPEN | BEI Incident Report.store Link Warehouse but UI passes Branch name |
| 19 | HIGH | OPEN (NEW from retest) | /dashboard/hr/overtime/apply RoleGuard excludes crew |
| 20 | MEDIUM | OPEN (NEW from retest) | OT filing API requires pre-existing Attendance record |
| 21 | HIGH | OPEN (NEW from retest) | Comp Edit button gated on existing SSA — chicken-and-egg |

(Defects #2, #3, #4, #7 already CLOSED by S170. Defects #12 and #17 are gaps in the DEFECTS.csv numbering — never assigned. The "#22/#23 test-harness bug" notes from earlier drafts referred to in-session retest failures (R4 Frappe routing typo) that never made it into the canonical CSV.)

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
| Phase 7 | 9 | Defects #5 #9 #11 #14 #15 #20 + #24 (newly discovered Phase 4 follow-up) |
| Phase 8 | 15 | L3 retest of unblocked S166 SKIP scenarios + per-agent audit gate |
| Phase 9 | 4 | Closeout (plan + registry + final PR) |
| **Total** | **71** | Within 80-unit ceiling. No phase exceeds 15. |

---

## Agent Boot Sequence

1. **Read this plan fully.** Every phase. Every HARD BLOCKER.
2. **Read the Requirements Regression Checklist above.** Write your approach for each item to `output/s172/REQUIREMENTS_REGRESSION_CHECK.md`.
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
2. Create artifact dir: `mkdir -p output/s172/{diagnostics,verification,retest,evidence}`
3. Write `output/s172/REQUIREMENTS_REGRESSION_CHECK.md` with one entry per checklist item
4. Write `output/s172/PHASE_BUDGET.json` with estimated vs actual unit tracking
5. Verify no L3 test pollution exists on production: query `Employee` filtered by `employee_name LIKE '%(L3 2026-04-%' AND status='Active'` — should return empty. If non-zero, escalate to Sam before any new test work.

**Verification:**
- Both repos on `s172-s166-followup-defect-fixes` branch
- `output/s172/REQUIREMENTS_REGRESSION_CHECK.md` exists with 11 items filled
- Production L3 pollution check returns 0

---

### Phase 1 — Defect #6 + #21 — Compensation Edit + list-modal (shared root cause) (12 units)

**Defects:**
- **#6** [CRITICAL] List-page compensation modal opens with only Bio ID (no fields). Visually confirmed by audit 2026-04-08 retest (`output/l3/s166/AUDIT_2026-04-08/EMP-UX-004-retest/04_dialog_only.png`).
- **#21** [HIGH] Edit button on `/dashboard/hr/payroll/compensation-setup/[employee]` is permanently disabled when employee has no SSA (chicken-and-egg).

**Root cause (R5 source-grounded):**
- Backend: `hrms/api/payroll_compensation.py:318 get_employee_compensation_detail(employee)` returns null/raises when employee has no Salary Structure Assignment.
- Frontend: `../bei-tasks/components/hr/compensation-detail-panel.tsx:165` has `<Button onClick={onEditClick} disabled={!detail}>` — when `detail` is undefined (no SSA), Edit is permanently disabled.
- List-page modal: rendered inside `../bei-tasks/app/dashboard/hr/payroll/compensation-setup/page.tsx` (no separate `compensation-detail-dialog.tsx` file exists — the R5 probe note was incorrect).

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

**Task 1.3 — Frontend fix: list-page row-click modal** (2 units)

**CORRECTION (post-fact-check):** The earlier draft of this plan named `compensation-detail-dialog.tsx` — that file DOES NOT exist. Defect #6 (list-page modal showing only Bio ID) is rendered from inside the compensation-setup list page itself.

1. `grep -rn "onClick\|Dialog\|Modal" ../bei-tasks/app/dashboard/hr/payroll/compensation-setup/page.tsx` to find the row-click handler and the modal it opens.
2. The modal is likely either (a) inline JSX in `page.tsx`, or (b) `compensation-detail-panel.tsx` reused inside a `<Dialog>` wrapper.
3. Apply the same `disabled={!detail}` → `disabled={isLoading}` pattern wherever the Edit button is gated.
4. Ensure the modal actually renders the form fields when `has_ssa: false` (the audit screenshot showed empty skeleton placeholders — the render path probably bails when `detail` is null).

   MUST_MODIFY: at least one of `../bei-tasks/app/dashboard/hr/payroll/compensation-setup/page.tsx` OR `../bei-tasks/components/hr/compensation-detail-panel.tsx`
   MUST_CONTAIN: form fields rendering when `has_ssa: false` (verify by browser screenshot in Task 1.5)

**Task 1.4 — Sentry instrumentation** (1 unit)

Confirm Sentry context is set in the new `get_employee_compensation_detail` path AND in any other modified `@frappe.whitelist()` endpoint touched.

**Task 1.5 — Local L1 + L2 verify** (2 units)

Use `/local-frappe` to test the backend change locally. Use Playwright headless to load the list page in dev mode and click a real employee row — verify the modal opens with a form, not an empty skeleton.

   Verification screenshot: `output/s172/verification/phase1_modal_with_form.png`

**Task 1.6 — Phase 1 verification gate** (1 unit)

```bash
git diff --name-only origin/production | grep -E "payroll_compensation\.py" || exit 1
git diff --name-only origin/main | grep -E "compensation-detail-panel\.tsx" || exit 1
git diff --name-only origin/main | grep -E "(compensation-setup/page\.tsx|compensation-detail-panel\.tsx)" || exit 1
grep -q "has_ssa" hrms/api/payroll_compensation.py || exit 1
grep -q "disabled={isLoading}" ../bei-tasks/components/hr/compensation-detail-panel.tsx || exit 1
test -f output/s172/verification/phase1_modal_with_form.png || exit 1
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

Write `scripts/s172_backfill_stranded_bccs.py` (Frappe-executable, mirrors the S170 backfill pattern):

```python
"""
S172 — Backfill SSAs for BCCs that reached Approved without creating an SSA.
Caused by Defect #16 silent activation failure.
"""
# Find BCCs in Approved state where no corresponding SSA exists for the employee
# For each, attempt to call the (now-fixed) _activate_compensation_change
# Log results to output/s172/backfilled_bccs.csv
```

Run via SSM following the `/frappe-bulk-edits` skill pattern (init boilerplate + base64 + docker exec).

   MUST_MODIFY: `scripts/s172_backfill_stranded_bccs.py`
   MUST_CONTAIN: `_activate_compensation_change`

**Task 2.4 — Phase 2 verification gate** (1 unit)

```bash
git diff --name-only origin/production | grep "payroll_compensation\.py" || exit 1
git diff --name-only origin/production | grep "s172_backfill_stranded_bccs\.py" || exit 1
grep -q "set_backend_observability_context" hrms/api/payroll_compensation.py || exit 1
# Confirm the broad try/except is gone (should not have a bare except: that returns success)
```

---

### Phase 3 — Defect #19 — `/overtime/apply` crew RBAC (4 units)

**Defect:** [HIGH] test.crew1 navigating to `/dashboard/hr/overtime/apply` gets "Access Restricted". The page is the self-service OT filing form deployed by S170 Phase 3.

**HARD BLOCKER for diagnosis:**
The current RoleGuard at `../bei-tasks/app/dashboard/hr/overtime/apply/page.tsx` lines 241-249 already includes `EMPLOYEE`, `STORE_STAFF`, `STORE_SUPERVISOR`, `AREA_SUPERVISOR`, `HR_USER`, `HR_MANAGER`, `HQ_FINANCE`, `SYSTEM_MANAGER`, `ADMINISTRATOR` (9 roles). If test.crew1's role IS one of those (likely STORE_STAFF or EMPLOYEE), the bug is somewhere ELSE — not the RoleGuard. Possibilities:
- Middleware in `../bei-tasks/middleware.ts` blocks the route before the page renders
- `lib/roles.ts` has a stale role mapping
- The page uses a different access check below the RoleGuard

**Task 3.1 — Diagnose actual blocker** (1 unit)

1. Read `../bei-tasks/lib/roles.ts` and find how `test.crew1@bebang.ph` (or the BEI "crew" Frappe role) maps to the bei-tasks role enum
2. Read `../bei-tasks/middleware.ts` (if exists) and check for any route-specific gating
3. Read the full `app/dashboard/hr/overtime/apply/page.tsx` body for any additional permission checks below the RoleGuard
4. Write findings to `output/s172/diagnostics/DEFECT_19_DIAGNOSIS.md`

**Task 3.2 — Apply the correct fix** (2 units)

Based on the diagnosis:
- **If RoleGuard is missing the actual crew role:** add it to lines 241-249
- **If middleware blocks the route:** update the middleware allowlist
- **If `lib/roles.ts` has wrong mapping:** fix the mapping
- **If a separate access check is wrong:** fix it

Whatever the fix is, it must result in test.crew1 successfully loading the OT apply form.

   MUST_MODIFY: at least one of `../bei-tasks/app/dashboard/hr/overtime/apply/page.tsx`, `../bei-tasks/middleware.ts`, `../bei-tasks/lib/roles.ts`

**Task 3.3 — Phase 3 verification gate** (1 unit)

```bash
test -f output/s172/diagnostics/DEFECT_19_DIAGNOSIS.md || exit 1
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
grep -rn "bei_incident_report.*store\|incident_report.*store\|BEI Incident Report.*store" hrms/ bei-tasks/ scripts/ 2>&1 | tee output/s172/diagnostics/DEFECT_18_REFERENCE_INVENTORY.md
```

Decide A vs B based on the inventory.

**Task 4.2 — Apply the chosen fix** (4 units)

If Option A: edit the doctype JSON, change `options: Warehouse` → `options: Branch`. Run `bench migrate` locally to test.

If Option B: rename the field via Frappe migration, update all UI/API references, update fixtures.

Document the decision and reasoning in `output/s172/diagnostics/DEFECT_18_DECISION.md`.

   MUST_MODIFY: `hrms/hr/doctype/bei_incident_report/bei_incident_report.json` (at minimum)

**Task 4.3 — Local migration test** (1 unit)

Use `/local-frappe` to run the migration locally. Verify creating a BEI Incident Report with the disciplinary form's branch value (e.g., "ARANETA GATEWAY") now succeeds.

**Task 4.4 — Phase 4 verification gate** (1 unit)

```bash
git diff --name-only origin/production | grep "bei_incident_report\.json" || exit 1
test -f output/s172/diagnostics/DEFECT_18_DECISION.md || exit 1
test -f output/s172/diagnostics/DEFECT_18_REFERENCE_INVENTORY.md || exit 1
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

   Verification log: `output/s172/verification/defect_8_dual_create_log.txt`

**Task 5.4 — Phase 5 verification gate** (1 unit)

```bash
git diff --name-only origin/production | grep "employee_create\.py" || exit 1
test -f output/s172/verification/defect_8_dual_create_log.txt || exit 1
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

### Phase 7 — Smaller defects bundled + Phase 4 follow-up (9 units)

| Defect | Severity | Fix |
|---|---|---|
| **#5** Generate Slips disabled | HIGH | Likely auto-fixes when #21+#16 are fixed (button gates on having salary structures in place). Phase 8 retest will confirm. If still disabled, investigate the gate condition in `../bei-tasks/app/dashboard/hr/payroll/processing/page.tsx`. Document either way in `output/s172/diagnostics/DEFECT_5_STATUS.md`. (2 units) |
| **#9** test.hr proxy 403 | MEDIUM | Add `Employee` doctype to the my.bebang.ph proxy permission allowlist for `test.hr` role. Find the proxy auth config in `../bei-tasks/app/api/frappe/[...path]/route.ts` or similar. (2 units) |
| **#11** Soft-delete order dependency | LOW | Add a docs note in `data/04_Project_Management/Import_Log/CONTEXT.md` documenting the 2-pass PUT pattern (relieving_date first, then status=Left). Also add a helper function in `hrms/api/employee_master.py` if one doesn't exist. (1 unit) |
| **#14** Reports To no autocomplete | MEDIUM | Replace plain text input with a shadcn combobox bound to the Frappe `User` Link field. Find the EmployeeDetailDialog Employment section. (2 units) |
| **#15** First-of-session BSCR rolled back | LOW | Investigate the rollback path in `hrms/api/payroll_compensation.py submit_sensitive_change_request`. Likely a missing `frappe.db.commit()` after the first call in a session. (1 unit) |
| **#20** OT requires attendance | MEDIUM | NOT a code fix — document as expected behavior in `data/04_Project_Management/Import_Log/CONTEXT.md` AND add a clearer error message to `hrms/api/overtime_request.py` line 94 (already says "Overtime can only be filed for days you actually worked" — confirm acceptable). (1 unit — minimal) |
| **#24** Disciplinary create field mismatch | HIGH | **NEW — added 2026-04-09 during Phase 4 inventory.** Frontend `useCreateIncidentReport` (`lib/queries/hr-disciplinary.ts:179-187`) sends `incident_type` + `severity`. Backend `create_incident_report` (`hrms/api/disciplinary.py:40`) requires `incident_category`. Every IR create call fails with "Missing required field: incident_category". Independent blocker on the disciplinary chain beyond Defect #18. Fix: accept both `incident_type` and `incident_category` in the backend payload; map `incident_type` → `incident_category` with `severity` passed through. Also check DocType JSON for a `severity` field. (1 unit) |

   MUST_MODIFY: at least 4 files across the bundle

**Phase 7 verification gate:**
```bash
test -f output/s172/diagnostics/DEFECT_5_STATUS.md || exit 1
git diff --name-only origin/production origin/main | grep -cE "(\.py|\.tsx|\.ts|\.md)" | awk '{if ($1 < 4) exit 1}'
grep -q 'incident_type' hrms/api/disciplinary.py || exit 1
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

> Re-run the ~25 unblocked scenarios listed in `docs/plans/2026-04-08-sprint-172-s166-followup-defect-fixes.md` Phase 8. Use real browser via Playwright headless. Use proven patterns from `scripts/testing/l3_s166_lane_h_runner.mjs` (the only fully-working browser runner currently in repo). For each scenario, write evidence to `output/s172/retest/{lane}/evidence/{scenario_id}-retest.json` with `actions: [...]`, `screenshots`, `network: [...]`. Cleanup any test data created in finally via `/frappe-bulk-edits`. STOP after writing files. Do NOT touch git. Do NOT mark scenarios PASS without browser proof.

Required scenario IDs: list all 25 explicitly in the brief.

**Task 8.2 — Dispatch INDEPENDENT audit gate agent** (5 units)

After the runner reports back, dispatch a SEPARATE fresh subagent (different model/context) as the audit gate:

> Audit `output/s172/retest/` evidence files. For each scenario, verify (a) screenshot exists and is non-zero bytes, (b) actions array shows real Playwright UI interactions, (c) status field cross-checks against runner summary. Flag any SUMMARY_LIED discrepancy per the post-#497 `/l3-v2-bei-erp` rule. Write `output/s172/retest/AUDIT_REPORT.md` with verdict per scenario and overall PASS/REJECT.

If the audit rejects any scenario, dispatch a fix-only agent (3-iteration budget per scenario, per the v3 plan rule).

**Task 8.3 — Update DEFECTS.csv with retest results** (3 units)

For each defect that the retest verified CLOSED:
- Update `output/l3/s166/DEFECTS.csv` row to `CLOSED (S172 verified)` with evidence pointer
- Note: `DEFECTS.csv` is the canonical S166 registry — write the S172 retest verification INTO that file as the audit trail

**Task 8.4 — Phase 8 verification gate** (2 units)

```bash
test -f output/s172/retest/AUDIT_REPORT.md || exit 1
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

**Task 9.2b — Update S173 Debt Ledger (MANDATORY — not optional)** (1 unit)

Open `docs/plans/2026-04-08-sprint-173-s166-retest-debt-ledger.md`. For every scenario that S172 Phase 8 actually retested (~25 scenarios), flip its status in the full scenario list:

- `PENDING` → `CLOSED_BROWSER_PASS` (if audit gate passed)
- `PENDING` → `CLOSED_BROWSER_FAIL` (if audit gate failed — and log a new defect row in `output/l3/s166/DEFECTS.csv`)
- `PENDING` → `DEFERRED_BLOCKED` (if scenario couldn't run due to upstream block — write blocker to `output/s172/BLOCKERS.csv`)

Also append a dated section at the end of the ledger:
```
## 2026-04-08 — S172 Phase 8 update
- Retested: <count>
- CLOSED_BROWSER_PASS: <count>
- CLOSED_BROWSER_FAIL: <count> (new defects: <list of defect IDs>)
- DEFERRED_BLOCKED: <count>
- Remaining PENDING: <count> (owned by S174)
```

**HARD RULE:** Do NOT mark a ledger row CLOSED just because S172 fixed the underlying product defect. The scenario MUST be browser-re-proven through the independent audit gate. A row can only flip PENDING → CLOSED when the audit gate writes a PASS_WITH_PROOF flag.

**Verification:** `grep -c "CLOSED_BROWSER" docs/plans/2026-04-08-sprint-173-s166-retest-debt-ledger.md` must equal the Phase 8 browser-verified count.

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
- `output/s172/retest/form_submissions.json` (≥25 entries)
- `output/s172/retest/api_mutations.json`
- `output/s172/retest/state_verification.json`
- `output/s172/retest/AUDIT_REPORT.md`
- `output/s172/retest/<lane>/evidence/<scenario_id>-retest.json` (per scenario)
- `output/s172/retest/<lane>/screenshots/*.png` (pre + post per scenario)

---

## Zero-Skip Enforcement

Every task in Phase 1-9 MUST be implemented. No exceptions. If a task cannot be completed:
1. STOP and write a `BLOCKER:` entry to `output/s172/BLOCKERS.csv` with phase, task, error, attempted fix
2. Notify Sam via PR comment or session message
3. Do NOT skip silently, do NOT mark partial as DONE, do NOT defer to "next sprint"

**Phase Completion Checklist** — after each phase, append to `output/s172/PHASE_COMPLETION_CHECKLIST.md`:

| Phase | Task | Status | Evidence | Skipped? | Why |
|---|---|---|---|---|---|

**Forbidden agent behaviors:**
- Skipping a task silently
- Marking partial work as "done"
- Replacing a task with a simpler version without user approval
- Saying "deferred to next sprint"
- Implementing happy path only, skipping edge cases
- **Phase 8 retest:** running scenarios via API instead of real browser (the post-#497 rule applies)

**Verification script template** — write `output/s172/verify_phase_<N>.py` BEFORE starting each phase:

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
  - `output/s172/REQUIREMENTS_REGRESSION_CHECK.md`
  - `output/s172/PHASE_BUDGET.json`
  - `output/s172/PHASE_COMPLETION_CHECKLIST.md`
  - `output/s172/diagnostics/*.md`
  - `output/s172/verification/*.png`
  - `output/s172/retest/AUDIT_REPORT.md`
  - `output/s172/retest/<lane>/evidence/*.json`
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
| Dialog interaction + force-click combobox | `scripts/testing/l3_s166_lane_a_conflict001_fix_iter1.mjs` (only lane_a runner currently in repo) |
| 2-pass PUT soft-delete cleanup | `scripts/testing/l3_s166_lane_h_cleanup2.mjs` |
| SSM Frappe SQL execution (frappe-bulk-edits skill) | `scripts/testing/s166_cleanup_conflict_orphans.py` (reference for boilerplate) |
| Audit script template | `scripts/testing/s166_audit_browser_proof_v3.py` |
| Compensation page interaction | **No phase4 runner exists in repo.** Lane A4 used the API path; for S172 the agent must build the browser interaction from scratch using `l3_s166_lane_h_runner.mjs` as the template + `output/l3/s166/lanes/lane_a/PHASE_A4_SUMMARY.md` for the workflow steps. |

Test accounts (all passwords `BeiTest2026!`): see `memory/testing-accounts.md`. Primary actors:
- test.hr@bebang.ph (HR Manager — most defect fixes)
- test.crew1@bebang.ph (Crew — for Defect #19 OT verification)
- test.finance@bebang.ph (Finance — for sensitive change approvals)
- test.supervisor@bebang.ph (Supervisor — for OT/leave approvals)

---

## Execution Workflow

- Test Python changes locally: `/local-frappe`
- Run frontend dev server: `cd ../bei-tasks && npm run dev`
- Real browser test: `/playwright-bei-erp` skill (reference: `scripts/testing/l3_s166_lane_h_runner.mjs`)
- Frappe bulk operations via SSM: `/frappe-bulk-edits` skill
- Deployment: **DO NOT invoke `/deploy-frappe` yourself.** Sam handles deploy after PR merge.

---

## Execution Authority

This sprint is intended for autonomous end-to-end execution by a single agent in a single session, EXCEPT Phase 8 retest which requires waiting for Sam's deploy signal. Do not stop for progress-only updates. Only pause for items in the Autonomous Execution Contract `stop_only_for` section.

When dispatching subagents for Phase 8 retest, you MUST pair every retest runner with an INDEPENDENT audit gate per the post-#497 `/l3-v2-bei-erp` rule. No exceptions.
