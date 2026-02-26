# E2E Testing Rules

**Last Updated:** 2026-02-11
**Source:** Learned from 31 bugs found by real testers that our E2E suite (87% pass rate) missed.

---

## RULE 1: SUBMIT + VERIFY

A test that proves a page LOADS is worthless. A test must prove the feature WORKS.

- Every form test MUST: fill -> submit -> **verify the backend state changed**
- After submit, call the Frappe API to confirm the record was created/updated
- If the API returns an error, the test FAILS
- A toast saying "success" is NOT sufficient -- verify the actual database state

## RULE 2: BACKEND ERROR = FAIL

- If the UI shows an error toast -> FAIL
- If the backend returns 500 -> FAIL
- If the backend returns 4xx (except 403 on RBAC tests) -> FAIL
- If Sentry logs an exception -> FAIL
- NO exceptions. NO "findings". NO "expected behavior". FAIL and create a [BUG] task.

## RULE 3: PHOTO UPLOAD IS MANDATORY

- If a form has a photo/file upload field, the test MUST upload a real file
- Use `scratchpad/test_photos/test_receipt.png` (or create one: 100x100 red square)
- After upload, verify the photo URL is accessible (fetch it, check 200)
- Common DB bug: photo columns set to VARCHAR instead of LONGTEXT -> catches DataError 1406

## RULE 4: POST-ACTION STATE VERIFICATION

- After approving a leave -> verify status changed to "Approved" (not still "Pending")
- After submitting a form -> verify the record appears in the list view
- After deleting -> verify the record is gone

## RULE 5: ALL ROLES MUST BE TESTED

Minimum role coverage per test run:

| Role | Email | Purpose |
|------|-------|---------|
| Store Crew | test.crew1@bebang.ph | Store ops, forms, submissions |
| Store Supervisor | test.supervisor@bebang.ph | Approvals, team management |
| Area Supervisor | test.area@bebang.ph | Multi-store oversight |
| HR User | test.hr@bebang.ph | HR management |
| Projects Head | test.projects@bebang.ph | Maintenance queue, projects |
| Projects Staff | test.projects.staff@bebang.ph | Assigned tasks |
| Commissary | test.commissary@bebang.ph | Commissary operations |
| Warehouse | test.warehouse@bebang.ph | Warehouse operations |

If a role is skipped, document WHY and create a [TEST] task for it.

## RULE 6: SKIP = FAIL + RETRY

- If a test cannot run (empty data, session expired, selector not found): FAIL
- Create a [BUG] task explaining why
- Retry with: fresh login, test data seeding, corrected selector
- NEVER classify as "finding" or "expected"

## RULE 7: SIDEBAR-FIRST NAVIGATION

- Tests MUST navigate via sidebar clicks, NOT `page.goto()` URLs
- Only exception: the initial login page
- This catches RBAC sidebar visibility bugs that URL-direct tests miss

## RULE 8: ONE-SHOT FIXING

- Read the FULL function before fixing a bug
- Identify ALL issues (not just the one in the error message)
- Test the fix with a real user session (not API token)
- Deploy ONE TIME with all fixes

## RULE 9: SCENARIO-DRIVEN TESTING (NO AGENT-AUTHORED TESTS)

- L3 tests MUST execute pre-written scenarios resolved from `docs/testing/scenarios/index.yaml`
- Legacy monolith `docs/testing/TEST_SCENARIOS.md` remains for history/backfill only
- Agents do NOT invent their own test cases — they follow the script exactly
- Every scenario specifies: exact payload, exact role, exact assertions
- Use 150KB+ real photos, not 1x1 pixel toy PNGs
- Test ALL status transitions, not just the happy path
- Every bug found by real users becomes a regression scenario (never removed)

**Why:** Agent-authored tests failed repeatedly. Agents tested completion WITHOUT photos (missed BUG-1), skipped Pending Acknowledgement transition (missed BUG-2), and used toy data that never hit real code paths. Real users found both bugs in 20 minutes. Scenario-driven testing prevents this.

## RULE 10: REGRESSION BANK GROWS ONLY

- Every bug found by a human tester gets added to `docs/testing/scenarios/regressions/` regression bank files
- Regression scenarios are NEVER removed, even if the fix seems obvious
- The regression bank is the permanent record of "things that broke before"
- Add regression scenarios in the SAME COMMIT as the bug fix

## RULE 11: L3 MUST BE BROWSER-DRIVEN (REAL USER PATH)

- L3 submit steps MUST use browser actions: click, type, select, upload, submit
- L3 MUST navigate through UI controls (sidebar/buttons), not direct API submission calls
- API calls are allowed only for post-submit verification (read checks)

## RULE 12: API-FIRST SUBMISSION IN L3 IS FORBIDDEN

- Forbidden in L3 tests:
- `requests.post/get/...` for submit/update workflow actions
- `page.request.post/put/patch` for submit/update workflow actions
- `fetch('/api/method/...')` inside `page.evaluate` as the main submit path
- Any test violating this fails gate review

## RULE 13: BROWSER EVIDENCE IS REQUIRED FOR L3 PASS

- Every L3 scenario must produce evidence with:
- Action log proving `nav_sidebar`, `click`, `fill`, `submit` (and `upload` when applicable)
- Network log showing browser-originated mutating `/api/` call
- Artifacts: Playwright trace + screenshots
- Validate evidence with:
- `python scripts/testing/l3_browser_guard.py validate --evidence <path-to-json> --expected-endpoint <frappe-method>`
- Run static guard before merge:
- `python scripts/testing/l3_browser_guard.py scan`

---

## Test Accounts

All passwords: `BeiTest2026!`

| Employee ID | Email | Department | Designation |
|-------------|-------|-----------|-------------|
| TEST-AREA-001 | test.area@bebang.ph | Operations - BEI | Area Supervisor |
| TEST-SUPERVISOR-001 | test.supervisor@bebang.ph | Operations - BEI | Store Supervisor |
| TEST-STAFF-001 | test.staff@bebang.ph | Operations - BEI | Store OIC |
| TEST-CREW-001 | test.crew1@bebang.ph | Operations - BEI | Crew |
| TEST-HR-001 | test.hr@bebang.ph | Human Resources - BEI | HR Officer |
| TEST-PROJECTS-001 | test.projects@bebang.ph | Projects - BEI | Projects Head |
| TEST-PROJECTS-002 | test.projects.staff@bebang.ph | Projects - BEI | Projects Staff |
| TEST-COMMISSARY-001 | test.commissary@bebang.ph | Commissary - BEI | Commissary Supervisor |
| TEST-WAREHOUSE-001 | test.warehouse@bebang.ph | Warehouse - BEI | Warehouse Staff |

**Test Stores:** TEST-STORE-BGC - BEI, TEST-STORE-MAKATI - BEI
