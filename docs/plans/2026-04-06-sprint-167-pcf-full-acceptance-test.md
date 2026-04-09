# Sprint 167 — PCF Full Acceptance Test (Multi-Department, Multi-User, Real Entries)

```yaml
sprint_id: S167
sprint_name: pcf-full-acceptance-test
sprint_date: 2026-04-06
plan_version: 1
status: COMPLETED
owner_decision_maker: Sam (CEO)
owner_technical_executor: Claude (single-owner execution)
branch: s167-pcf-full-acceptance-test-redo
target_repo: BEI-ERP (evidence only — no code changes)
target_branch_base: production
registry_row: "| `S167` | Sprint 167 | `s167-pcf-full-acceptance-test-redo` | — | COMPLETED |"
depends_on: S162 (COMPLETED)
reopened_date: 2026-04-07
reopened_reason: "First pass was rejected by Sam. Previous run cut corners: 15 of 22 scenarios either BLOCKED (store phase) or driven via direct API calls instead of real browser UI clicks (Phase 2.2 submit batch, Phase 3 review/classify/approve/reject/validate, Phase 4 admin edit). This redo is BROWSER-ONLY with per-scenario user confirmation. /frappe-bulk-edits authorized for test data setup to unblock DEFECT-004. ALL defects — in-scope and out-of-scope — must be reported in final register."
```

---

## Context

S162 shipped the PCF frontend redesign (3 PRs: #343, #346, #348 — all merged). Partial L2/L3 verification ran in the S162 session with limited coverage:

- **What was tested:** sidebar regression (R1–R12), page rendering (8/8 depts), add-entry form inspection (no actual submit), admin dialog opens, legacy redirects work.
- **What was NOT tested:** No real expense entries were created. No batches were submitted. No accountant reviews happened. No approvals or rejections. No multi-user flows. No department-fund lifecycle.

Sam's directive: *"Full acceptance test like a real user. Several departments, several test accounts. PCF entries to reimbursement and approvals. No smoke test, no corner cutting."*

This sprint creates real data, exercises real approval workflows, and produces hard evidence that the PCF system works end-to-end across roles and departments — or produces a defect list of exactly what's broken.

---

## Pre-Conditions (State of the World)

### PCF Funds in Production

| Fund name | Type | Store/Dept | Amount | Custodian | Balance | Status |
|---|---|---|---|---|---|---|
| `PCF-TEST-STORE-BGC - BEI` | Store | TEST-STORE-BGC | ₱10,000 | test.supervisor@bebang.ph | ₱10,000 | Active, zero pending, zero batches |
| 43 other store funds | Store | Various | ₱10,000 each | Administrator | ₱10,000 | Active, zero pending |
| **Zero department funds** | — | — | — | — | — | **None exist yet** |

### Frappe Departments Available for Fund Creation

```
Finance and Accounting - BEI
HR and Admin - BEI
Procurement - BEI
Marketing - BEI
Supply Chain - BEI
Projects - BEI
Commissary - BEI
Operations - BEI
```

### Test Accounts

| Role | Email | Password | PCF Use Case |
|---|---|---|---|
| Store OIC (crew-level) | test.staff@bebang.ph | BeiTest2026! | Submit store PCF expenses |
| Store Supervisor | test.supervisor@bebang.ph | BeiTest2026! | Custodian of TEST-STORE-BGC, submits batches |
| HR Officer | test.hr@bebang.ph | BeiTest2026! | Submit HR department expenses |
| Warehouse Staff | test.warehouse@bebang.ph | BeiTest2026! | Submit Warehouse department expenses |
| Commissary Supervisor | test.commissary@bebang.ph | BeiTest2026! | Submit Commissary department expenses |
| Accounts Manager | test.finance@bebang.ph | BeiTest2026! | Accountant: reviews batches, runs AI COA, approves/rejects |
| CEO / System Manager | sam@bebang.ph | 2289454 | Admin: creates department funds, configures settings |

---

## Design Rationale (For Cold-Start Agents)

### Why this sprint exists

S162's L3 session could not test any data-mutation scenarios because:
1. Test accounts had no PCF fund assignments (store crew saw "No PCF fund assigned")
2. Zero department funds existed — the admin UI can create them but nobody had
3. Zero pending expenses → no batches → nothing for accountants to review

This sprint fills those gaps by doing what a real operator would do on day 1 of PCF going live: set up funds, submit expenses, review batches, approve/reject.

### Why this is a separate sprint (not a continuation of S162)

S162 was a build sprint — the plan owned the code. This is a pure acceptance test sprint — no code changes allowed. The evidence either proves the system works or produces a concrete defect list. Mixing execution and testing in one session creates the corrupt-success bias documented in S092.

### Why create real data in production

Sam explicitly directed: "this app is still a demo so you should not hesitate to create real entries like real users." The test store (TEST-STORE-BGC) exists for exactly this purpose. Department funds we create will serve as the operational starting point for when BEI actually starts using PCF. Test expenses will be cleaned up in the final phase.

---

## Known Limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| Backend `_get_pcf_fund_for_user()` returns only ONE fund per user | Users in 2+ departments see only their primary fund | V2 multi-fund picker; not blocking for this test |
| `add_expense_to_pending` requires `receipt_photo` (non-empty) | Every form submit needs a real file upload | Generate a small test PNG and upload it via Playwright file chooser |
| AI COA classification (`classify_batch_items`) calls `hrms/api/expense_classifier.py` | Classifier may not have real vendor→COA mappings for test vendors | Use real-ish vendor names (e.g., "Mercury Drug", "Globe Telecom") so the classifier has data to match |
| `approve_batch_with_coa` requires `items` as JSON string (not array) | PR #348 fixed this in the proxy — live on production | No mitigation needed |
| Test accounts may not be mapped to departments in Frappe HR | `usePCFForUser()` resolves fund via the employee's store/department | Phase 0 verifies and documents which test accounts map to which funds |

---

## Phases

### Phase 0 — Setup: Create Department Funds + Verify Account Mappings (~8 units)

**Goal:** Ensure every test account has a working PCF fund to submit expenses against. Create department funds that don't exist yet.

#### Task 0.1: Admin creates 3 department funds

Login as `sam@bebang.ph` (Admin). Navigate to `/dashboard/accounting/pcf/admin`.

Create these funds via the "Create Department Fund" dialog:

| Department | Custodian | Fund Amount | Threshold % |
|---|---|---|---|
| `HR and Admin - BEI` | test.hr@bebang.ph | ₱5,000 | 60 |
| `Supply Chain - BEI` | test.warehouse@bebang.ph | ₱5,000 | 60 |
| `Commissary - BEI` | test.commissary@bebang.ph | ₱5,000 | 60 |

**MUST_VERIFY:** After each creation, the fund appears in the admin fund list with correct department, amount, and custodian.

**Evidence:** `form_submissions.json` entry for each fund created: `{ form: "create_department_fund", inputs: { department, custodian, fund_amount, threshold_percentage }, submit_action: "Create", response: <success/error> }`

#### Task 0.2: Verify test account → fund resolution

For each test account, login and navigate to their department's PCF dashboard. Verify the fund resolves (not "No PCF fund assigned"):

| Account | Route | Expected Fund |
|---|---|---|
| test.staff@bebang.ph | `/dashboard/store-ops/pcf` | PCF-TEST-STORE-BGC - BEI |
| test.supervisor@bebang.ph | `/dashboard/store-ops/pcf` | PCF-TEST-STORE-BGC - BEI |
| test.hr@bebang.ph | `/dashboard/hr-admin/pcf` | The HR dept fund from Task 0.1 |
| test.warehouse@bebang.ph | `/dashboard/warehouse/pcf` | The Supply Chain dept fund from Task 0.1 |
| test.commissary@bebang.ph | `/dashboard/commissary/pcf` | The Commissary dept fund from Task 0.1 |
| test.finance@bebang.ph | `/dashboard/accounting/pcf` | Any fund (accountant sees all) |

**MUST_VERIFY:** Each account sees a fund label heading (not empty state). Screenshot each dashboard.

**If any account shows "No PCF fund assigned":** Document as a BLOCKER with the exact account, the route, and the error. Do NOT proceed with that account's scenarios — use the ones that work.

**Evidence:** `state_verification.json` entry for each: `{ check: "fund_resolution_<user>", before: "login", after: "<fund_name or empty_state>", passed: true/false }`

---

### Phase 1 — Store PCF: Full Expense Lifecycle (~12 units)

**Goal:** Two store employees add real expenses, the custodian reviews the pending queue and submits a batch to accounting.

#### Task 1.1: Store OIC adds 3 expenses

Login as `test.staff@bebang.ph`. Navigate to `/dashboard/store-ops/pcf/add`.

Submit 3 separate expenses:

| # | Vendor | Description | Amount | Date | Receipt |
|---|---|---|---|---|---|
| 1 | Mercury Drug | First aid kit refill for store | ₱250 | 2026-04-06 | test_receipt.png |
| 2 | 7-Eleven | Ice for display cooler | ₱150 | 2026-04-06 | test_receipt.png |
| 3 | Globe Telecom | Prepaid WiFi for store operations | ₱299 | 2026-04-06 | test_receipt.png |

**For each expense:**
1. Fill all fields (vendor, description, amount, date)
2. Upload receipt (use Playwright `page.setInputFiles()` with a generated 1x1 PNG)
3. Verify submit button becomes enabled
4. Click "Add to Pending"
5. Verify toast "Expense added to pending queue"
6. Verify redirect to pending list
7. Verify the expense appears in the pending table with correct amount

**MUST_VERIFY:** After all 3, the pending list shows 3 items totaling ₱699.

**R1 regression check:** Verify NO COA field visible on the form at any point.

#### Task 1.2: Store Supervisor views pending queue as custodian

Login as `test.supervisor@bebang.ph`. Navigate to `/dashboard/store-ops/pcf/pending`.

**MUST_VERIFY:**
- Sees all 3 expenses from test.staff (custodian sees fund-wide pending)
- Total shows ₱699
- Each row shows vendor, description, amount, date

#### Task 1.3: Custodian edits one expense

On the pending list, click edit on expense #2 ("7-Eleven"). Change amount from ₱150 to ₱180 (corrected receipt amount). Save.

**MUST_VERIFY:** Pending total updates to ₱729 (250 + 180 + 299).

#### Task 1.4: Custodian submits batch to accounting

This is the critical step — the custodian decides the pending expenses are ready for accounting review and creates a batch.

**Action:** Click "Submit Batch" (this calls `submit_batch_now` with the store code).

**MUST_VERIFY:**
- Success toast: "Batch submitted successfully"
- Pending list clears to 0 items
- Navigate to `/dashboard/store-ops/pcf/history` — new batch appears with status "Submitted", amount ₱729, 3 items

**Evidence:** `api_mutations.json` entry: `{ endpoint: "/api/pcf", method: "POST", payload: { action: "submit_batch_now", store: "TEST-STORE-BGC - BEI" }, status: 200, response_body: <batch details> }`

---

### Phase 2 — Department PCF: HR Expense Lifecycle (~10 units)

**Goal:** HR user adds expenses to the HR department fund (not a store fund), proving department-type funds work end-to-end.

#### Task 2.1: HR user adds 2 expenses

Login as `test.hr@bebang.ph`. Navigate to `/dashboard/hr-admin/pcf/add`.

| # | Vendor | Description | Amount | Date |
|---|---|---|---|---|
| 1 | National Book Store | Training manual printouts | ₱480 | 2026-04-06 |
| 2 | Jollibee | Team meeting snacks | ₱350 | 2026-04-06 |

Same flow as Phase 1. Upload receipt for each.

**MUST_VERIFY:**
- Both expenses land in the HR PCF pending list (not the store fund)
- Fund label on the dashboard matches "HR and Admin" (not a store name)
- Pending total = ₱830

#### Task 2.2: HR user submits batch

As the HR fund custodian (`test.hr@bebang.ph`), submit the batch.

**MUST_VERIFY:**
- Batch created with 2 items, ₱830 total
- Appears in `/dashboard/hr-admin/pcf/history` with status "Submitted"

---

### Phase 3 — Accountant Review: AI COA + Approve + Reject (~15 units)

**Goal:** Finance user reviews both batches (store + HR), runs AI classification, approves one with COA overrides, rejects the other with a reason.

#### Task 3.1: Accountant opens review queue

Login as `test.finance@bebang.ph`. Navigate to `/dashboard/accounting/pcf/review`.

**MUST_VERIFY:**
- Review queue renders with the full fund list (44+ funds)
- The TEST-STORE-BGC fund shows a batch with status "Submitted"
- The HR fund shows a batch with status "Submitted"

#### Task 3.2: Review store batch — AI classification + approve

Click the TEST-STORE-BGC fund → drill into the submitted batch.

1. **Click "Run AI Classification"**
   - Verify suggested COA appears per row (e.g., "Medical Expenses" for Mercury Drug)
   - Verify confidence badges appear (High/Medium/Low)
   - Verify Final COA fields are pre-filled from the AI suggestion

2. **Edit Final COA on one row** (e.g., change "Medical Expenses" to "Office Supplies")

3. **Edit Approved Amount** on one row (e.g., change 7-Eleven from ₱180 to ₱150 — accountant spotted the custodian's edit was wrong)

4. **Add a review note:** "S167 L3 test — store batch approved with one COA override and one amount adjustment"

5. **Click "Approve with COA"**

**MUST_VERIFY:**
- Success toast: "Batch approved with COA overrides"
- Redirect to review queue
- Batch status changes to "Approved" in the fund's history

**Evidence:** `api_mutations.json` entry for `approve_batch_with_coa` with the full items payload showing the COA overrides and amount adjustments.

#### Task 3.3: Review HR batch — reject with reason

Navigate back to the review queue. Click the HR fund → drill into the submitted batch.

1. **Click "Run AI Classification"** — verify it runs on department-fund batches too
2. **Click "Reject Batch"** (NOT approve)
3. **Verify dialog opens** with required rejection reason textarea
4. **Type reason:** "S167 L3 test — receipts are unclear for the Jollibee expense. Please re-upload a legible photo and resubmit."
5. **Click "Reject Batch" in the dialog**

**MUST_VERIFY:**
- Success toast: "Batch rejected"
- Redirect to review queue
- Batch status in HR fund history shows "Rejected"
- Rejection reason is stored (verify in batch details if accessible)

**Evidence:** `api_mutations.json` entry for `reject_batch` with the reason.

#### Task 3.4: Validation failure — try approving with missing COA

Navigate to ANY batch review screen (if another submitted batch exists). OR: document that this was tested during Scenario D.1 of S162 if no batch is available.

1. Clear the Final COA field on one row
2. Click "Approve with COA"
3. **MUST_VERIFY:** Client-side validation blocks submit, row is highlighted red, Alert banner shows "X item(s) missing Final COA"

---

### Phase 4 — Admin Configuration (~6 units)

**Goal:** Admin edits fund settings and verifies changes take effect.

#### Task 4.1: Admin edits the HR fund settings

Login as `sam@bebang.ph`. Navigate to `/dashboard/accounting/pcf/admin`.

Find the HR fund card. Edit:
- Fund amount: ₱5,000 → ₱8,000
- Threshold: 60% → 70%
- Click Save

**MUST_VERIFY:**
- Success toast: "PCF settings updated"
- Fund card now shows ₱8,000 / 70%

#### Task 4.2: Verify updated settings reflect for the HR user

Login as `test.hr@bebang.ph`. Navigate to `/dashboard/hr-admin/pcf`.

**MUST_VERIFY:**
- Dashboard shows fund amount = ₱8,000
- Threshold progress bar uses 70% threshold

---

### Phase 5 — Cross-Department Sidebar + Navigation Regression (~5 units)

#### Task 5.1: Full sidebar audit (3 users)

For each of these users, login and screenshot the full sidebar:

| User | Expected PCF Location | Must NOT Appear Under |
|---|---|---|
| test.staff@bebang.ph | Store Operations → Petty Cash Fund | My Expenses |
| test.hr@bebang.ph | HR Management → Petty Cash Fund | My Expenses |
| test.finance@bebang.ph | Finance & Accounting → PCF Review Queue + PCF Fund Configuration | My Expenses |

**MUST_VERIFY (R10):** "My Expenses" has exactly 2 items (Submit Expense + My Expenses) — no PCF.
**MUST_VERIFY (R3):** Each user's department group has the PCF items.
**MUST_VERIFY (R4/R11):** "Submit Expense" points to `/dashboard/expense/submit`.

#### Task 5.2: Legacy URL redirects (with real fund resolution)

Login as `test.staff@bebang.ph` (who now has a fund). Navigate to:
- `/dashboard/expense/pcf` → should redirect to `/dashboard/store-ops/pcf` (their department PCF)
- `/dashboard/expense/pcf/add` → should redirect to `/dashboard/store-ops/pcf/add`

**MUST_VERIFY:** Redirect lands on the department PCF dashboard, NOT on `/dashboard?pcf=not-configured`.

---

### Phase 6 — Cleanup + Evidence Commit (~4 units)

#### Task 6.1: Document all test data created

Write a manifest of every piece of test data created during this run:

- Department funds created (names, departments)
- Expenses submitted (expense IDs, amounts)
- Batches created (batch names, statuses)
- Settings changed (fund amounts, thresholds)

Save to `output/l3/s167/TEST_DATA_MANIFEST.md`.

#### Task 6.2: Decide on cleanup vs preserve

**Recommended:** PRESERVE the department funds (they're operationally useful — BEI will need them when PCF goes live). Clean up only the test expenses by removing any remaining pending items.

The 3 store expenses from Phase 1 are already in an approved batch — they stay as the first real PCF batch in the system's history. The 2 HR expenses are in a rejected batch — they also stay as evidence of the reject workflow.

#### Task 6.3: Commit evidence

```bash
cd F:/Dropbox/Projects/BEI-ERP
git checkout -b s167-pcf-full-acceptance-test origin/production
git add -f output/l3/s167/ docs/plans/2026-04-06-sprint-167-pcf-full-acceptance-test.md docs/plans/SPRINT_REGISTRY.md
git commit -m "test(S167): PCF full acceptance test evidence"
git push -u origin s167-pcf-full-acceptance-test
```

---

## L3 Workflow Scenarios (Summary Table)

| # | User | Action | Expected Outcome | Failure Means |
|---|---|---|---|---|
| 0.1a | sam@bebang.ph | Create HR dept fund via admin dialog | Fund appears in admin list | create_pcf_fund broken or Department link validation fails |
| 0.1b | sam@bebang.ph | Create Supply Chain dept fund | Fund appears | same |
| 0.1c | sam@bebang.ph | Create Commissary dept fund | Fund appears | same |
| 0.2 | 6 accounts | Navigate to dept PCF dashboard | Fund label shows (not empty state) | usePCFForUser broken for this account/dept combo |
| 1.1a | test.staff | Add expense: Mercury Drug ₱250 | Toast success, appears in pending | add_expense_to_pending broken |
| 1.1b | test.staff | Add expense: 7-Eleven ₱150 | Toast success, appears in pending | same |
| 1.1c | test.staff | Add expense: Globe ₱299 | Toast success, pending total = ₱699 | same |
| 1.2 | test.supervisor | View pending as custodian | Sees 3 items from test.staff | fund-wide pending resolution broken |
| 1.3 | test.supervisor | Edit expense amount ₱150→₱180 | Total updates to ₱729 | edit_pending_expense broken |
| 1.4 | test.supervisor | Submit batch | Batch created, pending clears | submit_batch_now broken |
| 2.1a | test.hr | Add HR expense: NBS ₱480 | Lands in HR fund pending | dept fund add broken |
| 2.1b | test.hr | Add HR expense: Jollibee ₱350 | Pending total = ₱830 | same |
| 2.2 | test.hr | Submit HR batch | Batch created, status Submitted | dept fund batch broken |
| 3.1 | test.finance | Open review queue | Sees both batches | get_all_pcf_funds or review page broken |
| 3.2a | test.finance | Run AI classification on store batch | Suggested COA + confidence appears | classify_batch_items broken |
| 3.2b | test.finance | Edit COA + amount, approve | Batch status → Approved | approve_batch_with_coa broken |
| 3.3 | test.finance | Reject HR batch with reason | Batch status → Rejected | reject_batch broken |
| 3.4 | test.finance | Try approve with empty COA | Validation blocks, row highlighted | Client-side validation broken |
| 4.1 | sam@bebang.ph | Edit HR fund: ₱8k / 70% | Settings saved | update_pcf_settings broken |
| 4.2 | test.hr | View updated dashboard | Shows ₱8k / 70% | Settings not reflected for user |
| 5.1 | 3 accounts | Sidebar audit | PCF under dept, not My Expenses | R3/R10 regression |
| 5.2 | test.staff | Legacy URL redirect | Lands on dept PCF dashboard | Redirect broken for funded users |

**Total: 22 scenarios across 7 users**

---

## Evidence File Contract

All evidence MUST be committed before closeout:

```
output/l3/s167/
├── form_submissions.json      # Every form filled + submitted (≥8 entries: 3 store + 2 HR + 3 fund creations)
├── api_mutations.json         # Every POST that changed state (≥9: 5 expenses + 1 edit + 2 batches + 1 approve + 1 reject)
├── state_verification.json    # Before/after for every scenario (≥22 entries)
├── screenshots/               # Screenshot per scenario step
├── TEST_DATA_MANIFEST.md      # Manifest of all test data created
└── L3_FINAL_REPORT.md         # Summary: PASS/FAIL/SKIP per scenario + R1-R12 + defect list
```

---

## Requirements Regression Checklist

Re-verify ALL of these during execution (not just the ones S162 already checked):

```
[ ] R1. COA field is NOT visible to store crew on add-entry form — check during Phase 1 Task 1.1
[ ] R2. Threshold is notify-only at 60% (no auto-batch when pending reaches threshold) — check during Phase 4
[ ] R3. PCF nests under EVERY department's sidebar group — check during Phase 5
[ ] R4. "Submit Expense" stays separate under HR Self-Service — check during Phase 5
[ ] R5. Admin can configure fund_amount per department — check during Phase 4 Task 4.1
[ ] R6. Admin can configure threshold_percentage per department — check during Phase 4 Task 4.1
[ ] R7. Form fields: vendor, description, amount, date, receipt photo (NO COA) — check during Phase 1
[ ] R8. Each department's PCF resolves automatically — check during Phase 0 Task 0.2
[ ] R9. Accountant batch review: AI COA + confidence + editable final COA + editable approved amount — check during Phase 3 Task 3.2
[ ] R10. 4 PCF entries removed from "My Expenses" sidebar — check during Phase 5
[ ] R11. Existing personal reimbursement flow unchanged — check during Phase 5
[ ] R12. Sprint registry has S167 row — already done
```

---

## Zero-Skip Enforcement

### Forbidden behaviors

1. ❌ Skipping any scenario from the L3 table
2. ❌ Claiming a form was "submitted" without `form_submissions.json` evidence
3. ❌ Claiming a batch was "approved" without `api_mutations.json` showing the payload
4. ❌ Inspecting a page but not actually clicking buttons / filling forms / submitting
5. ❌ Using API tokens instead of browser-based user sessions
6. ❌ Reporting a scenario as PASS without a before/after `state_verification.json` entry
7. ❌ Skipping receipt upload ("it's just a test") — backend requires it, form requires it, real users must use it
8. ❌ Deferring any scenario to "a later session"

### If a scenario fails

1. Screenshot the failure state
2. Record the exact error (toast message, console error, API response)
3. Add to `DEFECT_REGISTER.md` with scenario #, error, and root cause hypothesis
4. Continue to the next scenario — do NOT stop the run
5. At closeout, summarize: X PASS / Y FAIL / 0 SKIP with exact defect list

---

## Autonomous Execution Contract

```yaml
completion_condition:
  - all 22 scenarios attempted (none skipped)
  - form_submissions.json has ≥8 entries
  - api_mutations.json has ≥9 entries
  - state_verification.json has ≥22 entries
  - L3_FINAL_REPORT.md written with per-scenario PASS/FAIL
  - R1-R12 all re-checked
  - TEST_DATA_MANIFEST.md lists every piece of test data
  - evidence committed to branch and PR created

stop_only_for:
  - login failure on a test account (credential issue)
  - Vercel/Frappe down (site unreachable)
  - Playwright cannot start (environment issue)

continue_without_pause_through:
  - fund creation
  - expense submission
  - batch submission
  - accountant review
  - admin config
  - sidebar audit
  - evidence commit

blocker_policy:
  - scenario fails → log defect, continue to next scenario
  - login fails → try alternate account, if all fail → BLOCKED
  - site down → wait 60s, retry 3x, then BLOCKED

signoff_authority: single-owner (Sam)

canonical_closeout_artifacts:
  - output/l3/s167/L3_FINAL_REPORT.md
  - output/l3/s167/form_submissions.json
  - output/l3/s167/api_mutations.json
  - output/l3/s167/state_verification.json
  - output/l3/s167/TEST_DATA_MANIFEST.md
  - output/l3/s167/DEFECT_REGISTER.md (if any failures)
  - docs/plans/SPRINT_REGISTRY.md
```

---

## Execution Authority

This sprint is intended for autonomous end-to-end execution. Do not stop for progress-only updates. Only pause for items listed in `stop_only_for`. Every scenario must be attempted — none may be deferred.

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s167-pcf-full-acceptance-test origin/production`. NEVER write code on production.
3. Read `memory/testing-accounts.md` for test credentials.
4. Generate a 100x100 test receipt PNG (solid blue background with "S167 TEST RECEIPT" text) and save to `/tmp/s167_test_receipt.png`. This file will be uploaded via Playwright `setInputFiles` for every expense submission.
5. Start Phase 0 — fund creation and account verification.
6. Proceed through Phases 1–6 without stopping.

## Execution Skills Reference

- Browser testing: `/playwright-bei-erp` or `/l3-v2-bei-erp`
- Test accounts: `memory/testing-accounts.md`
- PCF hooks API: `bei-tasks/hooks/use-pcf.ts`
- PCF proxy: `bei-tasks/app/api/pcf/route.ts`

---

## Phase Budget Contract

| Phase | Units | Description |
|---|---|---|
| 0 | 8 | Setup: create 3 dept funds + verify 6 account mappings |
| 1 | 12 | Store PCF: 3 expenses + custodian edit + batch submit |
| 2 | 10 | HR Department PCF: 2 expenses + batch submit |
| 3 | 15 | Accountant review: AI COA + approve + reject + validation |
| 4 | 6 | Admin config: edit settings + verify reflection |
| 5 | 5 | Sidebar + legacy redirect regression |
| 6 | 4 | Cleanup + evidence commit |
| **Total** | **60** | Within 80-unit single-session threshold |
