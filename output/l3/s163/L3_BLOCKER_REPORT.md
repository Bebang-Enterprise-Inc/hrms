# S163 L3 Acceptance Test — BLOCKER REPORT

**Date:** 2026-04-06
**Tester:** general-purpose subagent (Playwright/Node, headless)
**Sprint:** S163 — Store Ordering Product Grouping
**Result:** **BLOCKED at Scenario 1** (UI). 0 of 8 scenarios passed via the UI. Backend (L1) is GREEN.

---

## Summary

The 8 L3 scenarios cannot be executed via the my.bebang.ph UI as written because the test accounts named in the task brief **do not exist on production**, and the closest substitute accounts that DO exist either:

1. lack an Employee→branch assignment (so the ordering page renders empty), OR
2. lack the `store_ordering` RBAC role (so the page returns "Access Restricted").

Backend L1 evidence (`output/l3/s163/l1_api_check.json`, written by an earlier session) confirms the S163 grouping behavior is working at the API layer.

---

## What was verified GREEN (backend / L1, not L3)

`output/l3/s163/l1_api_check.json` (timestamp 2026-04-06 13:36 UTC, store=Araneta Gateway):

- 6 BEI Store Item Groups visible via `get_orderable_items`: GRP-FROZEN-MANGO, GRP-FRESH-RIPE-MANGO, GRP-SAGO, GRP-RAG, GRP-CUP-HOLDER, GRP-LECHE-FLAN-X
- For GRP-FROZEN-MANGO at Araneta Gateway: `is_group_row=1`, `member_count=2`, `display_uom=KG`, `store_actual_qty=2.82`, `available_to_promise=700.0`, `members_leaked_into_response=[]`
- All 17 negative checks pass: NONE of the member SKUs (RM010-A, RM030, FG011, RM010, FG009, FG050, CS013–CS019, PM004, PM005, FG001-A, FG001-B) appear as separate rows in the API response
- Group registration via `BEI Store Item Group/GRP-FROZEN-MANGO`: members RM010-A (priority 1, KG) and RM030 (priority 2, PACK, conversion 1.0). Verified live via `/api/resource` (this run, see `state_verification.json`).
- Bin stock for source warehouses: 3MD Logistics has RM010-A=500, RM030=200; Pinnacle has RM010-A=500, RM030=200 — sufficient for a 5 KG grouped order.

So Phases 1–4 (DocTypes + group aggregation in `get_orderable_items`) are confirmed working at the API layer.

---

## Why L3 is blocked

### Issue 1 — Test accounts named in brief do not exist

`test.storesup@bebang.ph` and `test.scm@bebang.ph` are not Frappe Users on hq.bebang.ph. Verified via `/api/auth/login` (returns `Invalid login credentials`) and via `frappe.client.get_list` on the `User` doctype filtered to `email like 'test.%'`.

Existing test users (full list captured in this run):

```
test.accounting, test.accounting.budget/ceo/cfo, test.area, test.assistant,
test.auditor, test.billing, test.commissary, test.crew, test.crew1..test.crew8,
test.driver, test.finance, test.hq, test.hr, test.hrmanager, test.it,
test.procurement, test.projects, test.projects.staff, test.salesstakeholder,
test.staff, test.store, test.supervisor, test.transfer.622f42, test.warehouse
```

Closest analogs to "storesup": `test.staff`, `test.supervisor`, `test.store`. Closest analog to "scm": `test.procurement`. (`test.scm` does not exist.)

### Issue 2 — None of the analog users can render the Store Ordering page populated

Three analogs were attempted in this run; all failed:

1. **`test.supervisor@bebang.ph`** → `/dashboard/store-ops/ordering` loads with sidebar+layout, but the body shows `Store` (no name) → "0 of 0 items" → "No items match your search". `Frappe Employee` query shows NO Employee record linked to this user. Screenshot: `screenshots/s1_ordering_loaded.png` (first run with this account).
2. **`test.staff@bebang.ph`** → identical empty state, no Employee record. Screenshot: same filename overwritten — see git history if needed; symptoms identical.
3. **`test.transfer.622f42@bebang.ph`** → has an Employee record (HR-EMP-00028, designation "Store Supervisor", branch "ARANETA GATEWAY") but the ordering page returns **"Access Restricted — You don't have permission to access this page"**. The user lacks the `store_ordering` RBAC role wired in `bei-tasks/lib/roles.ts`. Screenshot: `screenshots/s1_ordering_loaded.png` (final state).

There is no test user on production that has BOTH (a) `store_ordering` RBAC permission AND (b) an `Employee` record linked to a branch with stock for RM010-A/RM030. Without such a user, scenario 1 (and consequently 2, 3, 4, 5, 6, 7, 8 which all depend on a real submitted order) cannot be exercised through the real browser flow.

### Issue 3 — Other deviations from the brief

- `test.area@bebang.ph` does exist and logs in successfully, but it was never reached because scenarios 4+ depend on a successfully submitted order from scenario 3.
- The brief said "Frozen Mango stock = sum of RM010-A + RM030 at the store". L1 evidence shows Araneta Gateway has only RM010-A = 2.82 KG (RM030 is not in any store bin, only in 3MD/Pinnacle source warehouses), so the displayed `store_actual_qty` would be 2.82 KG, not 12.5 KG as the plan example assumed. This is informational, not a defect.

---

## Environment notes (for the next L3 session)

- **Python `playwright.sync_api` HANGS** in this Windows environment at `chromium.launch(headless=True)`. Process never returns. The Node Playwright API works fine. The L3 runner was written in Node (`scripts/s163_l3_run.js`). Recommend using Node Playwright going forward unless someone debugs the Python sync hang.
- The `my.bebang.ph` login endpoint is `POST /api/auth/login` with body `{"usr":"...","pwd":"..."}` (Frappe convention), not `{"email","password"}`. Form selectors: `input[name=email]`, `input[name=password]`, `button[type=submit]`.
- Correct ordering route: `/dashboard/store-ops/ordering` (NOT `/dashboard/store-ordering`).
- Correct SCM route: `/dashboard/scm/order-review`.
- Correct area approval route: `/dashboard/store-ops/order-approvals`.

---

## What needs to happen before L3 can be re-run

**OPTION A (recommended) — provision proper test users:**
1. Either grant `test.staff@bebang.ph` an `Employee` record linked to "Araneta Gateway - BEI" branch and ensure it has the store_ordering role,
2. OR grant `test.transfer.622f42@bebang.ph` the `store_ordering` RBAC role in bei-tasks `lib/roles.ts` (the user already has Araneta Gateway assigned).
3. Similarly create or grant a `test.scm` analog with the SCM role (currently no test user has SCM).

**OPTION B — run the L3 against a real production user account** (e.g. an actual Araneta Gateway store supervisor + an actual SCM officer). NOT recommended without explicit Sam approval because submission creates real BEI Store Order, real Material Request, and real warehouse reservation.

**OPTION C — narrow scope of L3 to backend-only** (already done in L1: `output/l3/s163/l1_api_check.json` is GREEN). Skip UI L3 for S163 and document the deviation.

---

## Evidence files written by THIS run

- `output/l3/s163/form_submissions.json` — login submissions for test.staff/supervisor/transfer attempts
- `output/l3/s163/api_mutations.json` — captured POST/PUT/PATCH from Playwright (auth + Sentry telemetry)
- `output/l3/s163/state_verification.json` — per-attempt before/after states with explicit pass=false rows
- `output/l3/s163/console_log.json` — browser console
- `output/l3/s163/screenshots/` — login_*, s1_ordering_landing.png, s1_ordering_loaded.png, s2_search_mango.png
- `output/l3/s163/L3_BLOCKER_REPORT.md` — this file

---

**DO NOT mark S163 as L3 COMPLETED.** Backend L1 is green but UI L3 is 0/8 due to test account provisioning gaps on production. This requires user input to choose Option A/B/C above.
