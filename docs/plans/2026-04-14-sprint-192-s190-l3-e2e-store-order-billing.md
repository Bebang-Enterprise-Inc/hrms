# S192 — S190 L3 E2E: Store Order → Warehouse Dispatch → GR → Billing

```yaml
sprint: S192
status: LIBRARY_DEPLOYED_PENDING_L3_EXECUTION
planned_date: 2026-04-14
plan_file: docs/plans/2026-04-14-sprint-192-s190-l3-e2e-store-order-billing.md
depends_on:
  - S190 Phase 5 deployed (PR #566) — Company-first resolution, CSV retired
completed_date: ""
execution_summary: "Phase 0 + Phase L complete. Library (18 files) + spec + data-testid + preflight script shipped via BEI-Tasks PR. Phases 1-3 execution BLOCKED on SSM (deploy hook requires Sam password) — handoff to Sam to unblock + run scenarios via preflight_setup.py. See output/l3/s192/SUMMARY.md."
branch: s192-s190-l3-e2e
frontend_pr: https://github.com/Bebang-Enterprise-Inc/BEI-Tasks/pull/new/s192-s190-l3-e2e
backend_pr: https://github.com/Bebang-Enterprise-Inc/hrms/pull/new/s192-preflight-artifacts
canonical_unit_total: 25
```

---

## Purpose

Full end-to-end L3 test of the S190-deployed Company-first billing chain. Validates that when a store places an order today, the entire flow from order submission → warehouse dispatch → goods receipt → BKI billing happens automatically and routes to the correct legal entity with valid TIN.

**Authorization (given by Sam 2026-04-14):** Test agent may adjust store delivery schedules, create/adjust users, seed delivery/route data, and mutate other test data. All created/adjusted test data MUST be cleaned up at end of run.

## Test Execution Rule — Browser-Only Like a Real User

**MANDATORY:** Every step of every scenario MUST be executed through a real browser using Playwright, simulating a real user. The runtime contract:

1. **Log in:** Navigate to `https://my.bebang.ph/login`, fill email + password fields, click the Sign In button. Wait for dashboard.
2. **Navigate:** Click actual sidebar/menu links. Do NOT `page.goto()` past login walls. No `page.request.post()` to API endpoints.
3. **Fill forms:** `page.fill()` / `page.click()` / `page.selectOption()` on real form elements. No `page.evaluate()` shortcuts that bypass the handler.
4. **Submit:** Click the Submit / Approve / Dispatch / Accept Receipt buttons visible in the UI. Wait for success toast or page navigation.
5. **Assert UI:** Check that the resulting page shows the expected state (order appears in list with correct status badge, success message, etc.) BEFORE any backend DB query.
6. **Then verify backend:** After UI confirms, SSM query Frappe to inspect the actual docs (this is verification, not testing — it confirms the UI reflects reality).
7. **Capture evidence per step:** Screenshot before and after click, full-page video of each scenario, DOM dump of critical states.

**Allowed exceptions (environmental setup only, NOT workflow testing):**
- Creating/updating test users via SSM (backend user provisioning)
- Granting permissions / roles via SSM (RBAC setup)
- Seeding warehouse inventory / Bin quantities via SSM (test prerequisite)
- Creating delivery schedules / routes via SSM (test prerequisite)
- Cleanup (reversing any of the above)

**Forbidden:**
- `fetch()` / `page.request.post()` / `curl` to exercise the app's workflow endpoints
- Navigating directly to pages that require UI state from a previous step
- Inferring success from backend state alone — UI MUST confirm first
- Using `page.evaluate(() => window.submitOrder(...))` to bypass the form

---

## Design Rationale (For Cold-Start Agents)

### Primer: What is S190 and why does it matter

Before this plan existed, BEI's ordering system resolved a store's billing entity through a CSV file (`store_buyer_entity_register.csv`) — a brittle pattern that silently broke when the CSV was missing rows. S190 replaced this with a **Company-first resolution chain**:

```
Store warehouse  ─┐
  (e.g. "SM Tanza - BEI")
                  │
                  ▼
  Warehouse.company   ──→  Frappe Company DocType
  (Link field, set by      (e.g. "BEBANG MEGA INC.")
   S190 Phase 5)                │  has tax_id, store_ownership_type, parent
                                ▼
                    Customer (matching customer_name)
                    (created by S181 auto_provision)
                                │  has tax_id inherited from Company
                                ▼
                    Sales Invoice on BKI → customer w/ TIN + VAT
```

**What changed in S190:**
- `resolve_warehouse_company()` reads `Warehouse.company` (no suffix-guessing).
- `resolve_store_buyer_entity()` Company-first with CSV fallback (P1) → Company-only (P5).
- `BEI Store Order.company` new Link field, stamped at submit.
- `_create_mr_for_store_order()` reads `order.company` instead of re-guessing.
- BKI billing chain (`build_bki_store_sale_invoice`) inherits the same resolution.
- S190 Phase 5 (PR #566) re-pointed 37 warehouses to correct buyer entities, created 7 missing Customers, backfilled 26 TINs, and **deleted** the CSV register entirely.

**What S192 does (this sprint):** validates the runtime chain end-to-end through a real browser, not the data layer (which was the scope of the S190 forensic audit).

### Why this sprint exists
S190 deployed the Company-first billing chain (PRs #563, #566). We verified data layer coverage (53/53 stores billable). But we have NOT validated the full runtime flow end-to-end. This sprint closes that gap with a live scenario.

### What we're testing (not the same as unit tests)
| Layer | What we validate |
|-------|------------------|
| Order submission | `submit_order()` stamps `order.company = Warehouse.company` |
| Approval | Area Supervisor approval → MR creation |
| MR creation | `_create_mr_for_store_order()` sets `custom_source_company`, `custom_target_company`, `custom_finance_treatment` correctly |
| Warehouse dispatch | Stock Entry created from source warehouse → store warehouse |
| GR (Goods Receipt) | Store accepts delivery via `complete_receiving` |
| BKI billing | Sales Invoice submitted on DR acceptance with correct Customer + TIN + 12% VAT |

### Known gotchas
- `_create_mr_for_store_order` uses `savepoint("create_mr_for_store_order")` (DM-2). If a sub-operation throws, MR is rolled back.
- Store delivery schedule gates order creation — schedule must be present for the test store.
- BKI markup is by store_type: JV 2.5%, Managed Franchise 8%, Full Franchise 8% (ICT-002).
- VAT template from `BEI Settings.bki_sales_vat_template` — must be configured.

### Why Option B (library-first) and not Option A (quick-and-dirty spec)
BEI's existing E2E suite has 100+ `.spec.ts` files with copy-pasted login, duplicated selectors, and no Page Object structure. Every sprint re-wrote 60-80% boilerplate. We chose **Option B** — invest 14u once in Phase L to build the Page Object Model + fixtures + builders + assertions + `data-testid` attributes, so every future E2E sprint costs ~5-8u instead of ~20-25u. Alternatives considered: (a) write S192 inline like past sprints → rejected, we'd just add to the pile; (b) extract library in a separate QA-infra sprint → rejected, we need the test and the library lands in the same PR so they ship together with reviewable consumption proof.

### Why browser-only (HB-4)
The existing `live-store-ordering-l3-l4.spec.ts` uses `page.request.post("/api/method/...")` to simulate user actions. That tests the backend, not the user experience. It misses button-wiring bugs, form validation, UI state issues, and toast handling — exactly the bugs a real user would hit first. S192 enforces browser-only because Sam explicitly asked for "a real user" test (2026-04-14).

---

## Environment (Cold-Start Constants)

| Thing | Value |
|-------|-------|
| Frontend app | `https://my.bebang.ph` (Vercel-hosted React/Next.js in `bei-tasks/` repo) |
| Frappe backend | `https://hq.bebang.ph` (production) |
| All test account passwords | `BeiTest2026!` |
| Test accounts needed | `test.area@bebang.ph` (Area Supervisor — sees all stores), `test.scm@bebang.ph` (Supply Chain Manager — approves + dispatches), `test.supervisor@bebang.ph` (Store Supervisor — places orders + accepts deliveries) |
| Test account reference | `memory/testing-accounts.md` (confirm roles + any missing accounts here) |
| Sam's personal account (admin, only if escalated) | `sam@bebang.ph` / `2289454` |
| SSM pattern for backend setup | See `/frappe-bulk-edits` skill. Instance: `i-026b7477d27bd46d6`, container: `adms_receiver_adms-db_1` for DB, `frappe_backend` for Frappe |
| hrms repo (backend, S190 deployed) | `Bebang-Enterprise-Inc/hrms`, default branch `production` |
| bei-tasks repo (frontend, where S192 lands) | `Bebang-Enterprise-Inc/BEI-Tasks`, default branch `main` |

## Repository & Branch Strategy

S192 touches ONE repo, not both:

| Repo | Branch | What lands here |
|------|--------|-----------------|
| `bei-tasks` | `s192-s190-l3-e2e` | Library (`tests/e2e/{pages,fixtures,builders,assertions,support}/`), spec (`tests/e2e/specs/s190-store-company-integration.spec.ts`), `data-testid` attributes on ordering/approval/dispatch/receiving components |
| `hrms` | — (no branch) | NONE — S190 is already deployed via PRs #563 and #566. Backend is frozen for the duration of S192. If a `[BUG]` in Frappe surfaces, file it; do NOT fix in S192. |

## Test Data Contract

To keep runs reproducible, scenarios use a **fixed item set** (not random picks):

| Scenario | Store | Cargo | Items (code : qty) | Rationale |
|---------|-------|-------|--------------------|-----------|
| S1 | SM Tanza | DRY | `FG-SAGO-DRY` : 5, `FG-GULAMAN-DRY` : 5, `FG-PINIPIG-DRY` : 5, `FG-BEANS-DRY` : 5, `FG-KAONG-DRY` : 5 | 5 common DRY items, 5-qty each (low enough to pass stock gates, high enough to exercise markup math) |
| S2 | SM Megamall | DRY | same as S1 | validates S188 per-store child resolution |
| S3 | The Grid - Rockwell | DRY | same as S1 | validates post-P5 billing hold lift |
| S4 | Ayala Evo | DRY | `FG-SAGO-DRY` : 3 (single-item variant) | validates same-Customer resolution for multi-store entity |

**HARD BLOCKER:** The items above must exist in Frappe Item master AND have Bin stock > 50 at source warehouse `Shaw BLVD - BKI` at preflight time. If any item is missing or short, preflight records the gap in `output/l3/s192/phase_0_preflight.json` and Task 0.3 (seed stock) runs via SSM. Do NOT substitute items silently.

**If any `FG-*-DRY` code doesn't exist in Frappe:** preflight Task 0.2 queries `tabItem` for 5 alternative DRY items with `item_group LIKE '%Finished Good%'` and `disabled = 0`, records the substitutes in the preflight artifact, and uses those. The substitution is explicit and logged, not silent.

---

## Test Scenarios

### Primary scenario (happy path)
**Store:** SM Tanza (`SM Tanza - BEI`) — maps to `BEBANG MEGA INC.` (Managed Franchise, TIN 010-885-436-00000)
**Flow:** Area Supervisor places DRY order (5 items) → approves → SCM dispatches → store accepts GR → SI submitted

### Per-entity-type coverage
| # | Store | Buyer Entity | Type | Why |
|---|-------|--------------|------|-----|
| 1 | SM Tanza | BEBANG MEGA INC. | Managed Franchise | Most common path, 5 stores share this entity |
| 2 | SM Megamall | Bebang Enterprise Inc. - SM Megamall | JV (per-store child, S188) | Tests S188 child resolution |
| 3 | The Grid - Rockwell | TASTECARTEL CORP. | Full Franchise | Tests billing hold lift (TIN exists now) |
| 4 | Ayala Evo | BEBANG MEGA INC. | Managed Franchise | Multi-store same entity (should get same Customer) |

### Failure scenarios
- Submit from store with broken Warehouse.company → expect throw
- Order with no items → expect 400
- Approval without permission → expect 403

---

## Phase Budget

```yaml
phase_unit_budget:
  Phase 0 (Preflight: dependency verify + forensic baseline + library audit + env setup): 8
  Phase L (LIBRARY EXTRACTION — Page Objects, fixtures, builders, TEST_IDS):              14
  Phase 1 (Scenario 1 — SM Tanza happy path, CONSUMES library):                            6
  Phase 2 (Scenarios 2-4 — other entity types, CONSUMES library):                          5
  Phase 3 (Failure scenarios, CONSUMES library):                                           3
  Phase 4 (Cleanup + evidence + library docs):                                             4
total_units: 40
hard_limit_per_phase: 15
```

> **Why the bigger budget:** S192 is a library-founding sprint. Future E2E sprints will consume these Page Objects / fixtures / builders and cost ~5-8 units each instead of starting from scratch (current cost: ~20+ units per sprint of duplicated boilerplate). **One-time cost now; amortized across all future tests.**

---

## Phase 0: Preflight + Library Audit (6u)

### Task 0.A: Verify S190 is live in production (HARD GATE)

Before anything else, confirm the backend dependency is deployed:
```bash
GH_TOKEN="" gh pr view 563 --repo Bebang-Enterprise-Inc/hrms --json mergedAt,state
GH_TOKEN="" gh pr view 566 --repo Bebang-Enterprise-Inc/hrms --json mergedAt,state
```
Both must show `"state": "MERGED"` with non-null `mergedAt`. Then confirm the deploy landed in production (via `/deploy-frappe-bei-erp` skill or by inspecting the most recent GitHub Actions run on `Bebang-Enterprise-Inc/hrms`, branch `production`).

**Gate artifact:** `output/l3/s192/diagnostics/dependency_verification.json` with `{"pr_563_merged": true, "pr_566_merged": true, "production_deploy_date": "<ISO>", "go_ready": true}`.

**STOP if `go_ready=false`.** Do not proceed with an un-deployed S190 — tests will produce misleading failures.

### Task 0.B: Run S190 forensic billing audit (live baseline)

Re-run the forensic audit to confirm billing-chain readiness at run-time (not just at S190 merge time):
```bash
# Uses the audit pattern from scripts/s190_forensic_billing_audit.py (via SSM — see /frappe-bulk-edits skill)
# For every store warehouse, verify: Warehouse.company → Customer → tax_id → no billing hold
```
Write `output/l3/s192/diagnostics/s190_billing_chain_baseline.json`. Expected: **53/53 stores billable** (matches the forensic audit at S190 deploy time). If < 50 stores, STOP and investigate regression. If 50-52, log the gap stores and skip them in scenarios.

### Task 0.0: Library audit — discover what already exists

Before writing any test code, inventory what the library covers. Run:
```bash
rg -l "login|Page|fixture" F:/Dropbox/Projects/bei-tasks/tests/e2e/ | head -40
ls F:/Dropbox/Projects/bei-tasks/tests/e2e/{pages,fixtures,builders,assertions,support}/ 2>/dev/null
```

Produce `output/l3/s192/diagnostics/LIBRARY_AUDIT.md` with:
- Existing Page Objects (if any) — mark coverage vs S192 needs
- Existing fixtures (if any) — note what we can reuse
- Existing assertion helpers — note what we can reuse
- **Gaps we will fill in Phase L** — every missing element becomes a task

The existing `live-store-ordering-l3-l4.spec.ts` and `l3_s152_helpers.mjs` are likely the richest starting points. Extract-worthy patterns, not imitate-inline.

### Task 0.1: Verify test users exist and have proper role + store assignment
- `test.area@bebang.ph` — Area Supervisor, should see all stores
- `test.supervisor@bebang.ph` — Store Supervisor (can approve)
- `test.scm@bebang.ph` — Supply Chain Manager (can dispatch)

If missing or mis-configured: create/update. Record original state for cleanup.

### Task 0.2: Verify SM Tanza delivery schedule
`BEI Store Delivery Schedule` for SM Tanza must be active for DRY lane today. If absent, create temporary schedule.

### Task 0.3: Verify source warehouse + route for DRY lane to SM Tanza
`BEI Route` for DRY lane must have SM Tanza as a stop. If absent, create temporary route.

### Task 0.4: Verify stock available at source warehouse for 5 test items
Pick items with actual_qty > 0 at Shaw BLVD - BKI (or active commissary). Record pre-test Bin.actual_qty.

### Gate
`output/l3/s192/phase_0_preflight.json` — records baseline + any test-data adjustments made (for cleanup).

---

## Phase L: Library Extraction (14u) — BUILDING THE FOUNDATION

**This is where future E2E testing velocity comes from.** Everything extracted here becomes a first-class library asset that S193+ will consume. Every component below is a DELIVERABLE.

### Task L.1: Create library skeleton + barrel exports (2u)
Create the canonical folder structure in `bei-tasks/tests/e2e/`:
```
pages/{BasePage.ts, LoginPage.ts, StoreOrderingPage.ts, OrderApprovalPage.ts, DispatchPage.ts, ReceivingPage.ts, index.ts}
fixtures/{auth.ts, seed.ts, cleanup.ts, evidence.ts, index.ts}
builders/{OrderBuilder.ts, UserBuilder.ts, index.ts}
assertions/{orderAssertions.ts, billingAssertions.ts, index.ts}
support/{frappeReadback.ts, ssmSetup.ts, selectors.ts, paths.ts}
```

Each `index.ts` is a barrel export. Tests import from `@/tests/e2e` (single entry point).

### Task L.2: `support/selectors.ts` + add `data-testid` attributes to components (3u)
Populate `TEST_IDS` constant with the stable selector names S192 needs:
- `store-picker`, `cargo-tab-{DRY,FC,FM}`, `qty-{itemCode}`, `submit-order-button`
- `approve-order-button`, `reject-order-button`
- `dispatch-row-{mrName}`, `dispatch-button`
- `accept-delivery-button`, `delivery-row-{deliveryId}`

Then open each component in `bei-tasks/` that renders these controls and add `data-testid` attributes. Each `data-testid` change is a small bei-tasks commit — part of this plan's deliverable.

### Task L.3: `pages/BasePage.ts` + `LoginPage.ts` (1u)
- `BasePage`: `waitForToast`, `screenshotStep`, `assertUrl`, common nav helpers.
- `LoginPage`: `.goto()`, `.loginAs(email, password)`.

### Task L.4: `pages/StoreOrderingPage.ts` (2u)
Methods: `goto`, `selectStore`, `selectCargoCategory`, `setItemQuantity`, `addItemByCode`, `submit`, `assertOrderInList`, `extractOrderIdFromToast`.

### Task L.5: `pages/OrderApprovalPage.ts` + `DispatchPage.ts` + `ReceivingPage.ts` (2u)
One class per screen. Methods mirror the user actions (approve/reject/dispatch/accept).

### Task L.6: `fixtures/` (2u)
- `auth.ts`: `loggedInAreaSupervisor`, `loggedInSCM`, `loggedInStoreSupervisor` — use `storageState` for speed.
- `cleanup.ts`: `CleanupLedger` class with `.record(kind, payload)` and `.reverse()`. Reversers for: bin seed, schedule seed, route seed, user creation, customer rename, warehouse create.
- `seed.ts`: `seededInventory`, `seededDeliverySchedule`, `seededRoute` — each registers itself with `cleanupLedger`.
- `evidence.ts`: auto screenshots per step, per-test video, per-scenario HAR file.

### Task L.7: `builders/OrderBuilder.ts` + `UserBuilder.ts` (1u)
Fluent API. `OrderBuilder.dry().forStore("SM Tanza").withItems(5).build()`.

### Task L.8: `assertions/orderAssertions.ts` + `billingAssertions.ts` (1u)
- `assertCompanyChainCorrect(orderId, {company, customer, tin})` — reads BEI Store Order → MR → SI and checks the whole chain.
- `assertOrderStatus`, `assertMRFields`, `assertSIHasTIN`, `assertVATApplied`, `assertMarkup`.
- `support/frappeReadback.ts`: `readDoc(doctype, name)` via SSM or HQ API.

### Task L.9: Library README + migration note (1u)
Write `bei-tasks/tests/e2e/README.md` explaining:
- The layout
- How to write a new spec (example: the 10-line S192 scenario 1)
- How to extend (when adding a new page, fixture, builder)
- Link to `.claude/docs/qa-test-library-discipline.md`

Add a migration note in `output/l3/s192/LIBRARY_MIGRATION_NOTE.md`: any existing spec that duplicates what the library now covers is flagged for future consolidation (not done this sprint).

### Gate (Phase L)
- All library files exist with tests compiling (even if no specs consume them yet)
- `grep -r "data-testid" bei-tasks/components/` returns the new attributes
- README published
- `output/l3/s192/phase_L_library_manifest.md` lists every asset delivered

---

## Phase 1: Scenario 1 — SM Tanza Happy Path (6u) — BROWSER ONLY, CONSUMES LIBRARY

**With the library in place, Scenario 1 is now a ~20-line spec, not 200 lines of inline Playwright. This is the payoff of Phase L.**

Example of what the spec looks like (the actual implementation lives in `bei-tasks/tests/e2e/specs/s190-store-company-integration.spec.ts`):

```ts
import { test, expect } from "@/tests/e2e/fixtures";
import { StoreOrderingPage, OrderApprovalPage, DispatchPage, ReceivingPage } from "@/tests/e2e/pages";
import { OrderBuilder } from "@/tests/e2e/builders";
import { assertCompanyChainCorrect } from "@/tests/e2e/assertions";

test("S190 S1: SM Tanza order → BKI SI billed to BEBANG MEGA INC.", async ({
  loggedInAreaSupervisor,
  orderingPage,
  seededInventory,
  cleanupLedger,
}) => {
  // Submit
  const order = OrderBuilder.dry().forStore("SM Tanza").withItems(5).build();
  const orderId = await orderingPage.submitOrder(order);
  await orderingPage.assertOrderInList(orderId, "Pending Approval");

  // Approve + dispatch + receive — fresh contexts per role via fixtures
  await test.step("approve", async ({}) => { /* OrderApprovalPage.approve(orderId) */ });
  await test.step("dispatch", async ({}) => { /* DispatchPage.dispatch(mrName) */ });
  await test.step("receive", async ({}) => { /* ReceivingPage.accept(deliveryId) */ });

  // Domain assertion — hides all backend query details
  await assertCompanyChainCorrect(orderId, {
    company: "BEBANG MEGA INC.",
    customer: "BEBANG MEGA INC.",
    tin: "010-885-436-00000",
    markup: 0.08,  // Managed Franchise
    vat: 0.12,
  });
});
```

### Detailed browser steps (for test implementer reference, executed by Page Object methods under the hood)

**NOTE:** The steps below document what the Page Object methods DO. They are NOT meant to be copy-pasted into the spec. The spec uses the method calls above.

### Task 1.1: Submit order as test.area@bebang.ph (BROWSER) — via `StoreOrderingPage`

**Steps (inside `StoreOrderingPage.submitOrder(order)`):**
1. `page.goto("https://my.bebang.ph/login")`
2. Fill `[name="email"]` = `test.area@bebang.ph`
3. Fill `[name="password"]` = `BeiTest2026!`
4. Click `button[type="submit"]` (Sign In)
5. Wait for redirect to `/dashboard`
6. Screenshot: `output/l3/s192/screenshots/s1_01_logged_in.png`
7. Click sidebar "Ordering" (or navigate via breadcrumb to `/dashboard/store-ops/ordering`)
8. If store picker appears, select "SM Tanza" from dropdown. Screenshot state of picker.
9. Select cargo category tab: DRY
10. For 5 items, use the UI quantity input to set qty (e.g., `input[data-testid="qty-${item_code}"]`, or whatever the actual selector is — inspect the page). Fill `5` for each.
11. Click the "Submit Order" button (or equivalent CTA, labeled per the page)
12. Wait for the confirmation modal or toast "Order submitted"
13. Screenshot success state
14. Extract order ID from the success toast/URL/recent orders list

**UI Assertion (before backend check):**
- A success toast/modal appears with the order ID (or URL navigates to `/dashboard/store-ops/ordering/<order_id>`)
- The order appears in the "My Orders" list with status badge "Pending Approval"

**Backend verification (after UI confirms):**
SSM query BEI Store Order by name:
- `store == "SM Tanza - BEI"`
- `company == "BEBANG MEGA INC."` ← **S190 FIELD**
- `status == "Pending Approval"`
- `submitted_by == "test.area@bebang.ph"`

### Task 1.2: Approve order as test.scm@bebang.ph (BROWSER)

**Steps:**
1. New browser context (log out + log in fresh) as `test.scm@bebang.ph` / `BeiTest2026!`
2. Navigate via sidebar to SCM Order Review page (`/dashboard/scm/order-review` or equivalent)
3. Find the order from Task 1.1 in the list. Screenshot.
4. Click the order row to open details
5. Review items. Click the "Approve" button.
6. If modal asks for confirmation, click "Confirm"
7. Wait for success state

**UI Assertion:**
- Order status badge updates to "Approved" / "Dispatched" / whatever the next state is
- Success toast "Order approved" shown

**Backend verification:**
- `BEI Store Order.status == "Approved"` (or equivalent)
- Material Request created linked via `custom_store_order`

### Task 1.3: Verify Material Request fields (BACKEND)

No UI action required — this is pure verification. Query MR via SSM:
- `custom_source_company == "Bebang Kitchen Inc."`
- `custom_target_company == "BEBANG MEGA INC."` ← **S190 FIELD**
- `custom_finance_treatment == "intercompany"`
- `material_request_type == "Material Issue"`

### Task 1.4: Dispatch (create Stock Entry) as SCM (BROWSER)

**Steps:**
1. Still as test.scm@bebang.ph, navigate to warehouse dispatch page (`/dashboard/warehouse/dispatch` or `/dashboard/commissary/dispatch` — inspect actual path)
2. Find the MR from Task 1.3. Screenshot list.
3. Click the MR row, select "Create Dispatch" / "Issue Stock" button
4. Fill dispatch quantities (full approved qty per item)
5. Click the "Dispatch" / "Submit" button
6. Confirm via modal if shown

**UI Assertion:**
- Dispatch success confirmation
- MR status updates to "Transferred" / similar
- Stock Entry appears in the list

**Backend verification:**
- Stock Entry with source_warehouse=commissary, target_warehouse="SM Tanza - BEI", docstatus=1
- Bin.actual_qty decreased at source for each item
- **Draft Sales Invoice created** (side effect of `build_bki_store_sale_invoice`):
  - `custom_bei_store_order == order.name`
  - `docstatus == 0` (draft)
  - `customer == "BEBANG MEGA INC."` ← **S190 RESOLUTION**
  - `company == "Bebang Kitchen Inc."`
  - `taxes_and_charges` template applied (12% VAT)
  - `items[0].rate` includes 8% markup (Managed Franchise)

### Task 1.5: Complete Goods Receipt as test.supervisor@bebang.ph (BROWSER)

**Steps:**
1. Fresh browser context as `test.supervisor@bebang.ph` / `BeiTest2026!`
2. Navigate to receiving page (`/dashboard/store-ops/receiving` or `/dashboard/store-ops/deliveries`)
3. Find the incoming delivery from Task 1.4
4. Click the delivery row, open receiving form
5. Fill receive quantities per item (use full dispatched qty)
6. Click "Accept Delivery" / "Complete Receiving" button
7. If modal: confirm

**UI Assertion:**
- Receiving success confirmation
- Delivery moves to "Received" / "Completed" state in UI
- Stock visible at SM Tanza warehouse (Bin updated)

**Backend verification (full chain):**
- Stock Entry updated with acceptance data
- Bin.actual_qty increased at "SM Tanza - BEI" for each item
- **Sales Invoice submitted** (`docstatus == 1`) with `posting_date == today`
- SI `tax_id` column = `010-885-436-00000` (BEBANG MEGA INC. TIN — verifies Frappe flow-through)
- GL entries created with party_type="Customer" + party="BEBANG MEGA INC." (DM-1)
- GL entries total debits == credits

### Evidence (per task, not per scenario)
- `output/l3/s192/screenshots/s1_*.png` (one per major step)
- `output/l3/s192/videos/s1_full.webm` (full-scenario recording)
- `output/l3/s192/dom_dumps/s1_*.html` (critical assertion points)
- `output/l3/s192/network/s1_*.har` (HAR file proving clicks triggered real API calls)
- `output/l3/s192/scenario_1_sm_tanza.json` — full field-by-field dump of order + MR + SE + SI + GL entries

---

## Phase 2: Scenarios 2-4 — Other Entity Types (6u) — BROWSER ONLY

Repeat the Phase 1 browser-driven flow (login → order → approve → dispatch → receive) abbreviated for:

- **S2: SM Megamall (JV, S188 child).** test.area logs in via browser, navigates Ordering page, selects "SM Megamall" from store picker, submits order. UI assertion: order appears with company shown as "Bebang Enterprise Inc. - SM Megamall". Backend: company field == per-store child name. Approve + dispatch + receive through browser. SI customer = `Bebang Enterprise Inc. - SM Megamall`.
- **S3: The Grid - Rockwell (Full Franchise, TASTECARTEL CORP.).** Validates that post-P5 this store is no longer on billing hold. Browser submit + approve + dispatch + receive. Assertion: Draft SI created (not skipped with billing-hold breadcrumb), submitted on GR, customer = `TASTECARTEL CORP.`, markup = 8%, TIN = `672-270-879-00000`.
- **S4: Ayala Evo (another BEBANG MEGA INC. store).** Browser submit. Key assertion: the Customer on the resulting SI is the **same** `BEBANG MEGA INC.` record used for SM Tanza in S1 (multi-store same-entity works).

**All steps via browser. Same evidence contract as Phase 1.**

### Evidence
- `output/l3/s192/screenshots/s{2,3,4}_*.png`
- `output/l3/s192/videos/s{2,3,4}_full.webm`
- `output/l3/s192/scenario_{2,3,4}_*.json`

---

## Phase 3: Failure Scenarios (3u) — BROWSER ONLY

### Task 3.1: Broken Warehouse.company (BROWSER)
**Setup (SSM):** Create temporary test warehouse `L3-TEST-NO-COMPANY - BEI` with `company = NULL`, grant test.area@bebang.ph access.
**Test:** In browser, log in as test.area, navigate to Ordering, select the test warehouse from picker, add 1 item, click Submit.
**UI Assertion:** Inline error or toast: "Store warehouse ... has no Company set. Contact admin." Order NOT created.
**Cleanup:** Delete the test warehouse.

### Task 3.2: Empty order (BROWSER)
**Test:** In browser as test.area, navigate to Ordering, select SM Tanza, DRY tab. Leave all quantity inputs at 0 (or default empty). Click Submit.
**UI Assertion:** The Submit button should be disabled OR clicking it shows error "At least one item with quantity greater than zero is required."

### Task 3.3: Missing Customer / Billing Hold (BROWSER)
**Setup (SSM):** Rename the Customer record for one test store (e.g., rename "BEBANG SM BICUTAN INC." → "BEBANG SM BICUTAN INC. __L3TEMP") so the Company-first resolution misses the Customer lookup.
**Test:** In browser, test.area submits order from SM Bicutan. Process through approval + dispatch normally.
**UI Assertion:** Dispatch succeeds (workflow doesn't break), but inspect `Error Log` in Frappe Desk — a `S190 Billing Hold` log_error entry exists. No Draft SI created for the order.
**Cleanup:** Rename Customer back.

### Cleanup ledger
All SSM mutations (Task 3.1 warehouse create, Task 3.3 Customer rename) logged in `output/l3/s192/cleanup_ledger.json` and reversed in Phase 4.

---

## Phase 4: Cleanup + Evidence (3u)

### Task 4.1: Reverse all test-data mutations
- Cancel or rollback test orders (MR, SE, SI) created during the run
- Remove any temporary users/roles/store assignments that didn't exist pre-run (revert via saved baseline)
- Restore any renamed records
- Leave delivery schedules/routes in their original state

### Task 4.2: Generate L3 evidence files (per S092 contract)
- `output/l3/s192/form_submissions.json` — every POST body + response
- `output/l3/s192/api_mutations.json` — Frappe docs created/modified with before/after state
- `output/l3/s192/state_verification.json` — per-scenario pass/fail matrix with assertions
- `output/l3/s192/cleanup_report.json` — before/after diff on test data

### Task 4.3: Summary report
`output/l3/s192/SUMMARY.md` — scenarios × assertions × pass/fail, any defects found (file as [BUG] tasks).

---

## L3 Workflow Scenarios (Browser-Only, S092 corrupt-success prevention)

| # | User | Browser Action (UI) | Expected UI State | Backend Truth (verified after UI) |
|---|------|---------------------|-------------------|-----------------------------------|
| 1 | test.area | Login → Ordering → pick SM Tanza → fill 5 item qtys → click Submit | "Order submitted" toast, order appears in list w/ "Pending Approval" badge | BEI Store Order w/ company="BEBANG MEGA INC." |
| 2 | test.scm | Login → Order Review → click order → click Approve | Status badge → "Approved", approval toast | MR created w/ custom_target_company="BEBANG MEGA INC." |
| 3 | test.scm | Dispatch page → select MR → fill qtys → click Dispatch | Dispatch success toast, MR → "Transferred" | SE submitted, Draft SI for BEBANG MEGA INC. created |
| 4 | test.supervisor | Login → Receiving → select delivery → fill qtys → click Accept | "Delivery accepted" toast, stock visible at store | SI submitted w/ TIN 010-885-436-00000, 12% VAT, GL party set |
| 5 | test.area | Login → Ordering → pick SM Megamall → submit | Order submitted, lists correctly | company="Bebang Enterprise Inc. - SM Megamall" (S188 child) |
| 6 | test.area → full flow | Login → Ordering → The Grid → submit + process through approval/dispatch/GR | All steps succeed in UI | customer=TASTECARTEL CORP., TIN=672-270-879-00000, no billing hold |
| 7 | test.area | Login → Ordering → Ayala Evo → submit + process | All UI steps succeed | Customer = BEBANG MEGA INC. (same record as S1) |

---

## Requirements Regression Checklist

- [ ] **RR-1:** `order.company` stamped on BEI Store Order at submit (S190 Task 1.5)
- [ ] **RR-2:** MR `custom_target_company` = order.company (S190 Task 1.6)
- [ ] **RR-3:** `resolve_store_buyer_entity` returns Company-first entity_row (S190 Phase 5)
- [ ] **RR-4:** Sales Invoice customer_name exactly matches resolved buyer entity
- [ ] **RR-5:** Sales Invoice tax_id inherited from Customer (Frappe standard)
- [ ] **RR-6:** VAT template applied (12% output VAT — CFO Q1)
- [ ] **RR-7:** Markup by store_type (2.5% JV / 8% Franchise — ICT-002)
- [ ] **RR-8:** GL entries have party_type/party (DM-1)
- [ ] **RR-9:** No CSV register read (S190 P5 retired it)
- [ ] **RR-10:** Cleanup restores all test-data mutations

---

## HARD BLOCKERS

- **HB-1 (waived by Sam 2026-04-14):** Builder-runs-L3 is permitted for this sprint. Fresh-session rule does not apply.
- **HB-2:** All test-data mutations MUST be reversed in Phase 4. Agent creates a `cleanup_ledger.json` at every mutation and walks it in reverse at cleanup.
- **HB-3:** No write to production orders that won't be cleaned up. If a test order reaches submitted state and can't be cancelled, log as [BUG] and escalate.
- **HB-4 (BROWSER ONLY):** No workflow operation may be executed via `page.request.*`, `fetch()`, `curl`, or direct API call. Every workflow step must be driven through UI controls (form fields + buttons) in a real browser. Evidence: HAR files must show API calls triggered by `click()` events from the test, not by the test script directly.
- **HB-5:** Network evidence required: per-scenario HAR file, grep the test source for `page\.request` — must return 0 hits.
- **HB-6 (Defect Response Protocol — FIX-NOW vs DEFER):** For every defect the L3 run surfaces, classify it **before** pausing the run:
  - **BLOCKS-TEST** — the defect prevents the current or downstream scenarios from completing.
    1. Fix the defect in code.
    2. Commit with a descriptive message referencing the scenario that surfaced it.
    3. Open the PR and merge (admin merge OK — use `# 2289454` password gate).
    4. Hot-patch the live container so the run can continue **this session** (do not wait for the next scheduled deploy).
    5. Restart the affected container(s), log the deploy.
    6. Resume the L3 run from the failing scenario.
    7. Append one entry to `output/l3/s192/blocking_defects.json` — fields: `{id, surface, scenario, commit, pr, hotpatch_time, resume_time}`.
  - **DOES-NOT-BLOCK-TEST** — the defect is noise, cosmetic, out of scope, or only affects later scenarios that can be reordered around it.
    1. **Do NOT** commit a code fix mid-run.
    2. Append an entry to `output/l3/s192/deferred_defects.json` — fields: `{id, surface, description, severity, suggested_fix, repro, seen_at}`.
    3. Continue running scenarios.
    4. After Phase 4 closeout, **batch-fix** all deferred defects in a single follow-up branch (`fix/s192-deferred-defects`) with one commit per defect and a single PR.
  - **When unsure which class a defect belongs to:** default to FIX-NOW. The cost of a mid-run fix is bounded; the cost of cascading failures from a mis-classified defer is not.
  - **Discipline anti-pattern (banned):** do **not** pause execution mid-run to ask the user which bucket a defect belongs to. The agent is authorized to make the call via the rule above.

---

## Autonomous Execution Contract

```yaml
completion_condition:
  - All 7 L3 scenarios executed with assertion-level pass/fail
  - Every BLOCKS-TEST defect fixed + committed + PR merged + hot-patched mid-run
  - Every DOES-NOT-BLOCK-TEST defect captured in deferred_defects.json
    and batch-fixed in a follow-up PR after Phase 4
  - Evidence files written to output/l3/s192/
  - Cleanup ledger shows all mutations reversed
  - SUMMARY.md written with overall pass/fail
  - Plan status updated to COMPLETED

stop_only_for:
  - Missing credentials for test accounts (no tool can resolve)
  - Cleanup fails and test data can't be reversed (ask human)
  - HARD BLOCKER violated
  - Fix-forward is architecturally unsafe (e.g., schema migration during live run) — document + escalate

never_stop_for:
  - A test-blocking defect — fix-commit-PR-hotpatch-resume per HB-6
  - A non-blocking defect — log to deferred_defects.json and continue

signoff_authority: single-owner (Sam Karazi)

canonical_closeout_artifacts:
  - output/l3/s192/SUMMARY.md
  - output/l3/s192/form_submissions.json
  - output/l3/s192/api_mutations.json
  - output/l3/s192/state_verification.json
  - output/l3/s192/cleanup_report.json
  - output/l3/s192/blocking_defects.json
  - output/l3/s192/deferred_defects.json
  - docs/plans/2026-04-14-sprint-192-s190-l3-e2e-store-order-billing.md (status → COMPLETED)
```

---

## Failure Response

During execution, every test failure is classified before any fix is attempted (see `.claude/docs/qa-test-library-discipline.md` §"Failure Discipline"):

| Mode | Symptom | Response |
|------|---------|----------|
| **A — App bug, BLOCKS-TEST** | Repeated same-state failure; manual UI verification confirms app is broken; the current scenario or any downstream scenario cannot proceed until fixed | **FIX-NOW** path in HB-6: fix code → commit → PR → admin-merge → hot-patch live container → restart → resume run. Append to `blocking_defects.json`. Never skip scenarios or stub the assertion. |
| **A′ — App bug, DOES-NOT-BLOCK-TEST** | App-side defect but scenarios can run around it (cosmetic, late-stage, or already-covered elsewhere) | Append to `deferred_defects.json` with repro + suggested fix. **Do NOT** commit mid-run. Continue. Batch-fix in `fix/s192-deferred-defects` after Phase 4. |
| **B — Test bug** | App works when verified by hand; test assumption or selector is wrong | Fix the test. If the same error pattern would bite other tests, promote the fix into the Page Object / fixture / assertion in this same PR. |
| **C — Brittleness / flakiness** | Fails intermittently; "timing issue"; needs retries | Fix the **library**, not the spec. Strengthen the Page Object: add `waitForResponse` / `waitForLoadState`, replace CSS selectors with `data-testid`, remove races. No `page.waitForTimeout(N)`, no `test.retry(3)` masking, no silent quarantine. |

**Closeout artifact:** if ≥3 library fixes are made during this run, emit `output/l3/s192/LIBRARY_IMPROVEMENTS.md` as a changelog of what the library learned. This is tribal knowledge made explicit and reviewed by the next L3 run.

### Defect response workflow (step-by-step)

```
On test failure
      ↓
┌──────────────────────────────────────────────┐
│ 1. Capture: DOM dump, screenshot, API trace,  │
│    backend error log (Error Log doctype)      │
└──────────────────────────────────────────────┘
      ↓
┌──────────────────────────────────────────────┐
│ 2. Classify: Mode A / A′ / B / C?              │
│   - Does it block the current scenario?        │
│   - Does it block ANY downstream scenario?     │
│   - If yes to either → FIX-NOW (Mode A)        │
│   - If no to both   → DEFER (Mode A′)          │
└──────────────────────────────────────────────┘
      ↓
  FIX-NOW branch
      ↓
┌──────────────────────────────────────────────┐
│ 3. Fix-commit-PR-hotpatch-resume               │
│    a. Write the minimal code change           │
│    b. git commit (no mid-run rebases)          │
│    c. git push + gh pr create                  │
│    d. gh pr merge --admin (password gate)      │
│    e. Hot-patch via SSM + base64 + docker cp   │
│    f. docker restart frappe_backend (all)      │
│    g. Append to blocking_defects.json          │
│    h. Resume L3 at the failing scenario        │
└──────────────────────────────────────────────┘
      ↓
  DEFER branch
      ↓
┌──────────────────────────────────────────────┐
│ 3'. Defer + continue                           │
│    a. Append to deferred_defects.json          │
│    b. Continue the L3 run                      │
│    c. After Phase 4:                           │
│       git checkout -b fix/s192-deferred-       │
│         defects origin/production              │
│       one commit per deferred defect            │
│       single PR, single review, single merge   │
└──────────────────────────────────────────────┘
```

**Why this asymmetry:**
- FIX-NOW defects block test signal. Every minute they live, the run produces false failures. Cost of fixing: bounded (one code edit + one deploy). Cost of deferring: unbounded (cascading failures, corrupted cleanup ledger, re-runs).
- DEFER defects are noise. Fixing them mid-run adds deploys, context switches, and rebase surface. Cost of deferring: tiny (one JSON entry). Cost of fixing mid-run: wasted minutes.

---

## Library Contributions (First-Class Deliverables)

S192 produces these permanent library assets in `bei-tasks/tests/e2e/`:

| Asset | File | Reusable by |
|-------|------|-------------|
| `BasePage` | `pages/BasePage.ts` | All future Page Objects |
| `LoginPage` | `pages/LoginPage.ts` | All tests (via `loggedInAs*` fixtures) |
| `StoreOrderingPage` | `pages/StoreOrderingPage.ts` | Every ordering/cart/submit test |
| `OrderApprovalPage` | `pages/OrderApprovalPage.ts` | Approval workflow tests (dual-approval, emergency, etc.) |
| `DispatchPage` | `pages/DispatchPage.ts` | SCM / warehouse dispatch tests |
| `ReceivingPage` | `pages/ReceivingPage.ts` | GR, delivery acceptance tests |
| `loggedInAs*` fixtures | `fixtures/auth.ts` | Every browser test |
| `seededInventory/Schedule/Route` | `fixtures/seed.ts` | Any test needing backend state |
| `CleanupLedger` | `fixtures/cleanup.ts` | Every test with SSM mutations |
| `OrderBuilder`, `UserBuilder` | `builders/` | Every test that needs test data |
| `assertCompanyChainCorrect` etc. | `assertions/` | Any test validating billing chain |
| `frappeReadback`, `ssmSetup` | `support/` | Any test with backend verification |
| `TEST_IDS` constant + component `data-testid`s | `support/selectors.ts` + bei-tasks components | All tests |

**Consumption target:** S193 and beyond should be able to write an E2E scenario in **~20 lines** (see spec example above), not ~200.

---

## Ownership

- **Library code** (`pages/`, `fixtures/`, `builders/`, `assertions/`, `support/`) is owned by S192 once extracted. Future sprints are consumers + extenders.
- **`TEST_IDS` + `data-testid`s on components:** jointly owned by frontend + QA layer. Any component PR may extend both.
- **Old `l3_sNNN_*.mjs` scripts in `scripts/testing/` and old `.spec.ts` files** that duplicate library coverage are flagged for future consolidation — NOT deleted in S192 (scope creep). A separate sprint will migrate them.
- **Canonical discipline document:** `.claude/docs/qa-test-library-discipline.md`. Out of date = out of sync across 3 skills. Update there first.

---

## Agent Boot Sequence

1. Read this plan fully — every scenario, every HB, **every browser step**.
2. Read `.claude/docs/qa-test-library-discipline.md` — the binding rules.
2. `cd F:\Dropbox\Projects\BEI-ERP && git fetch origin production && git checkout -b s192-s190-l3-e2e origin/production`
3. `mkdir -p output/l3/s192/{screenshots,videos,dom_dumps,network,diagnostics}`
4. Read test account details: `memory/testing-accounts.md`
5. Read S190 deployed code (for backend verification queries, NOT to call directly):
   - `hrms/api/store.py` — submit_order (line ~2955), _create_mr_for_store_order (line ~3683)
   - `hrms/utils/supply_chain_contracts.py` — resolve_store_buyer_entity (P5)
   - `hrms/api/commissary.py` — build_bki_store_sale_invoice (line ~973)
6. Load the `/playwright-bei-erp` skill for browser test patterns and selectors.
7. Inspect the actual pages in a browser first to discover real selectors:
   - `https://my.bebang.ph/dashboard/store-ops/ordering`
   - SCM order review page
   - Warehouse dispatch page
   - Store receiving page
   Record selectors in `output/l3/s192/diagnostics/selectors.md` before writing test code.
8. Preflight (Phase 0 — SSM setup only), then Scenario 1 (browser), 2-4 (browser), failure (browser), cleanup.
9. After every SSM mutation (setup or between-scenarios), append to `output/l3/s192/cleanup_ledger.json`.
10. Every browser step produces: screenshot before-click + screenshot after + video capture.

## Tooling Contract

- **Browser:** Playwright with `chromium` (or firefox). Config: `headless: false` while developing, `headless: true` for CI.
- **Recording:** `video: "on"`, `screenshot: "only-on-failure"` for automatic screenshots, plus explicit screenshots per plan.
- **Network capture:** `context.newContext({ recordHar: { path: "...", mode: "full" } })` per scenario. The HAR must show the actual `/api/method/...` call happening as a result of the button click — this is evidence the browser drove the call, not the test script.
- **No `page.request.post()`:** The entire test file MUST NOT contain any `page.request.*` method for workflow operations. Grep the test file before submitting evidence: `rg 'page\.request' output/l3/s192/` should return 0 matches.
- **No `page.evaluate()` bypasses:** `page.evaluate()` is allowed for READING state (e.g., reading toast text), not for calling submit handlers.
- **SSM setup is separate:** Backend-only setup (user creation, inventory seeding) runs via `scripts/s192_preflight_setup.py` executed via SSM. This is explicitly allowed per the authorization rule — it's prerequisite environment, not workflow testing.

---

## Governor Feedback Loop

- REJECT (test failure) → file as [BUG], log in defect register, continue remaining scenarios
- NEEDS_FIX (code bug found) → log as [BUG] and STOP Phase 1/2; failure scenarios still run
- Environment error → retry once; if persistent, log and document (don't retry forever)
