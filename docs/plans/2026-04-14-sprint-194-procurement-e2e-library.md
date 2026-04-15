# S194 — Procurement Chain E2E Library + Certification Spec

**v2 — 2026-04-14: Airtight review. Added 11 scenarios (S194-13 through S194-23) covering every audit control found in procurement.py: TIN gate, dual-threshold boundary, duplicate invoice (C3), match exception, date sequence (AUDIT 2.2), GR partial-receive then complete, OR > 5% variance, double-payment guard (AUDIT 2.5), payment > received value (AUDIT 2.3), payment approval incomplete for >₱500K (AUDIT 2.4), negative RBAC, Warehouse User read-only. Every original scenario preserved. Total: 23 scenarios, ~77 units.**

**v3 — 2026-04-14: Completeness review. Added 14 more scenarios (S194-25 through S194-38) covering every remaining reject path and the full edit/delete lifecycle. Total: 38 scenarios, ~98 units.**

**v4 — 2026-04-14: Audit-driven correction. Audit found that v3 scenarios 32-38 test UI that DOES NOT EXIST (no PR edit page, no PO edit page, no price change UI). Removed S194-32 through S194-38 (7 scenarios) — moved to a future Procurement Edit/Delete sprint (separate plan: build edit UI + test). Kept S194-25 through S194-31 (the 6 reject paths + GR reject-all) — they test existing UI. Also: extended S194-23 to test approvals queue page, added seededUser helper for test.procurement (was missing from testing-accounts), added Match Exception UI audit task to Phase L0, fixed screenshot verification script bug (`if [ -d ]` wrapper), removed Out-of-Scope contradiction with S194-22 advance path, added S194-3 fixture freshness note for 30-day is_new_supplier rule, added citation requirement for S194-31 PO status assertion. Final: 31 scenarios, ~82u (still within 80u soft ceiling once descoped). Every preserved scenario tests existing production UI.**

**v4.1 — 2026-04-14 (Phase L follow-up): Sprint S195 was claimed by Store Universe SSOT (unrelated to procurement edits). The descoped scenarios 32-38 belong to a not-yet-numbered "Procurement Edit/Delete" sprint that will be reserved when the procurement-edit UI work is scheduled (see SPRINT_REGISTRY.md "Next Sprint Reservation"). Plan body updated to use "future Procurement Edit sprint" instead of the now-conflicting "S195" reference. Also adds: Phase L1 finding that `is_advance_payment` is NOT a UI checkbox — S194-22 must drive it via `rfp_type === "Cash Advance"` selector instead. See `output/s194/library_audit.md` for the updated S194-22 contract.**

- canonical_sprint_id: `S194`
- status: PLANNED
- completed_date: —
- execution_summary: —
- created: 2026-04-14
- owner: Sam
- branch: `s194-procurement-e2e-library` (bei-tasks)
- depends_on: S186 (Supplier Hub backend), S193 (Supplier Status Guard) — both DEPLOYED
- estimated_units: ~82 (library ~38, specs ~40 for 31 scenarios, closeout ~4). At soft ceiling — recommend 2-session execution (Phase L in one, Phases S + C in fresh session).
- registry_lock: `| S194 | Sprint 194 | s194-procurement-e2e-library (bei-tasks) | — | PLANNED 2026-04-14 |`

## Mission

Certify the entire procurement chain — **Purchase Requisition → Purchase Order → Goods Receipt → Invoice → Payment Request → Official Receipt** — with real-browser Playwright tests that exercise every approval path, rejection path, threshold variant, multi-item order, and the S193 supplier status gate.

**Two deliverables, one sprint:**
1. **Library contribution (Phase L):** 5 new Page Objects + 1 builder + 1 assertion module + 4 fixtures — consumable by future procurement sprints.
2. **Certification spec (Phase S):** 12 scenarios covering single/dual/CEO approval, rejection at every stage, 3-way match success + variance, 4-level RFP approval, OR upload with 5% variance.

## Why Now

S193 just shipped the supplier status guard (hrms #569 deployed, validated 5/5 PASS). The supplier hub redesign (S186) deployed. Before the next procurement feature sprint lands, lock the chain with a regression suite so future changes cannot silently revert any control (TIN gate, dual approval, 3-way match, S193 guard, OR 5% rule).

**Origin incidents:**
- S027 (corrupt-success on workflow tests) — every scenario must submit forms and click buttons, not just load pages.
- S092 L3 discipline — form_submissions.json / api_mutations.json / state_verification.json required.
- QA Test Library Discipline doc (`.claude/docs/qa-test-library-discipline.md`) — library-first, no inline workflow, three-uses rule, `data-testid` everywhere.

## Design Rationale (For Cold-Start Agents)

**Why this is a library sprint, not just a spec sprint:**
Grepping `tests/e2e/pages/` shows only `StoreOrderingPage`, `OrderApprovalPage`, `DispatchPage`, `ReceivingPage` — no procurement page objects. The procurement flow has 5 distinct pages (`/purchase-requisitions`, `/purchase-orders`, `/goods-receipts`, `/invoices`, `/payments`) each with create/list/detail states. Writing a spec without extracting Page Objects would violate the discipline doc and create 5 inline patterns that the next sprint would duplicate. The cost: +38 units for the library; the benefit: every future procurement sprint consumes, never re-writes.

**Why Playwright (real browser), not SSM / API:**
- S092 proved LLM agents declare "21 PASS, 0 FAIL" after only loading pages (L2). Real browser forces actual form submissions with visible UI state.
- The 3-way match, dual approval, and 4-level RFP logic lives on the frontend too (enabled buttons, role-gated tabs, threshold-driven action panels). API-only tests cannot catch a disabled button or a missing tab.
- The QA discipline doc mandates real browser for workflow ops. SSM is allowed ONLY for environmental setup (test accounts, supplier fixtures) and post-UI state verification.

**Why dual-approval + CEO amounts are tested with specific thresholds:**
`BEI Settings.dual_approval_threshold` is ₱500K (verified in `procurement.py:1249`). To trigger each path deterministically we use:
- ₱250,000 PO → single approval (Mae only)
- ₱750,000 PO → dual approval (Mae + Butch)
- ₱1,500,000 PO with `is_new_supplier=1` → CEO approval path
Below ₱250K we'd also hit the TIN gate (procurement.py:1491) so amounts are chosen to isolate one gate at a time.

**Why `Pending Verification` for the S193 gate test (not Blacklisted):**
Production has 3 Pending Verification suppliers and 0 Blacklisted (verified via S193 validation 2026-04-14). Logic is identical (same `_SUPPLIER_BLOCK_ALL_STATUSES` frozenset), so testing PV covers Blacklisted. Avoids mutating real supplier data.

**Why `cleanupLedger` fixture is mandatory:**
The flow creates 6 documents per scenario (PR, PO, GR, Invoice, RFP, OR upload). With 12 scenarios × 6 docs = 72 potential orphan documents if cleanup fails. The `cleanupLedger` fixture (pattern in `fixtures/cleanup.ts`) records every SSM create and reverses it on `afterEach`, auto-cancelling or deleting via `frappe.delete_doc` through an SSM bridge helper. Manual try/finally in specs is forbidden by discipline §3.

**Why we extract `ProcurementChainBuilder` (not re-use OrderBuilder):**
`OrderBuilder` (existing) models a `BEI Store Order` (internal commissary ordering). Procurement POs target external suppliers, have different fields (`supplier`, `dual_approval`, `tin`), and flow through different status machines. A shared builder would force conditionals; a dedicated builder is cleaner and matches the existing pattern (OrderBuilder exists because Store Ordering was its own domain).

**Source references:**
- Procurement chart: `docs/diagrams/PROCUREMENT_FLOW_2026-04-14.md`
- Approval thresholds: `hrms/api/procurement.py:1249` (dual ₱500K), :1491 (TIN ₱250K)
- Four-level RFP: `procurement.py:3053-3085` (review → budget → cfo → ceo)
- S193 guard: `procurement.py:136` (`_assert_supplier_active`), :1467 (PO call site), :2405 (Invoice), :2723 (RFP)
- OR 5% rule: `procurement.py:4897` (`upload_official_receipt`)
- Test library layout: `.claude/docs/qa-test-library-discipline.md` §"Canonical Library Layout"
- Existing fixtures: `../bei-tasks/tests/e2e/fixtures/{auth,cleanup,evidence,seed}.ts`
- Existing selectors registry: `../bei-tasks/tests/e2e/support/selectors.ts`
- Test accounts: `memory/testing-accounts.md`

## Scope Summary

### In-Scope — Library (Phase L)
- `tests/e2e/pages/PurchaseRequisitionPage.ts` — list, create form, detail, approve/reject buttons
- `tests/e2e/pages/PurchaseOrderPage.ts` — list, create (from PR), detail, Mae/Butch/CEO approval, send-to-supplier, reject
- `tests/e2e/pages/GoodsReceiptPage.ts` — list, create (from PO), inspection form, partial-reject flow
- `tests/e2e/pages/InvoicePage.ts` — list, create (from GR), 3-way match status, variance approval
- `tests/e2e/pages/PaymentRequestPage.ts` — list, create (from Invoice), 4-level approval tabs, reject, OR upload modal
- `tests/e2e/builders/ProcurementChainBuilder.ts` — fluent builder: `.forSupplier(x).withItems([...]).atAmount(₱).build()` returning a plan the spec executes step-by-step
- `tests/e2e/assertions/procurementAssertions.ts` — `assertPOStatus`, `assertDualApprovalRequired`, `assertGRLinkedToPO`, `assertInvoice3WayMatched`, `assertRFPApprovalChain`, `assertORClosesRFP`
- `tests/e2e/fixtures/procurement.ts` — new fixtures: `procurementPages` (all 5 page objects), `seededSupplier(status)` (creates test supplier via SSM with cleanup), `seededItems(count)` (creates items via SSM with cleanup)
- Extensions to `tests/e2e/support/selectors.ts` — `TEST_IDS.procurement.*` keys for all 5 pages
- `data-testid` additions to procurement UI components (audit finds missing IDs)

### In-Scope — Spec (Phase S)
12 scenarios in `tests/e2e/specs/s194-procurement-chain.spec.ts`:

| # | Scenario | Chain | Expected |
|---|---|---|---|
| S194-1 | PR happy path — small PO (single approval) | PR(3 items) → approve → PO ₱250K → Mae approves → Sent | Status = "Sent to Supplier" |
| S194-2 | PO dual approval threshold | PR → PO ₱750K → Mae approves → status=Pending Butch → Butch approves | Status = "Approved" |
| S194-3 | PO CEO approval (new supplier) (v4 fix Blocker 5) | PR → PO ₱1.5M with `is_new_supplier=1` → Mae → Butch → CEO. **HARD BLOCKER:** `is_new_supplier` is age-based (procurement.py:323 — `creation >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)`). The `seededSupplier` fixture MUST create a fresh supplier each test run; do NOT rely on a permanent test fixture older than 30 days. | Status = "Approved" |
| S194-4 | PR rejection | PR(5 items) → Mae clicks Reject with comment "Over budget" | PR status = Rejected, no PO created |
| S194-5 | PO rejection at Mae | PO ₱500K → Mae rejects with comment | PO status = Rejected |
| S194-6 | S193 guard: block PO for Pending Verification supplier | Pick supplier with status=Pending Verification → try create PO | HTTP 417 toast: "Cannot create Purchase Order: Supplier ... is Pending Verification..." |
| S194-7 | S193 guard: block Invoice for PV supplier | Same supplier, try create Invoice | HTTP 417 toast for Invoice |
| S194-8 | S193 guard: block RFP for PV supplier | Same supplier, try create RFP | HTTP 417 toast for Payment Request |
| S194-9 | GR full receive + Invoice 3-way match | Approved PO → full GR → Invoice matches PO | Invoice status = Verified |
| S194-10 | GR partial reject + Invoice variance approval | Approved PO → GR with 2 items rejected → Invoice with reduced qty → variance > tolerance → approve_invoice_variance | Invoice status = Verified (with variance notes) |
| S194-11 | Full RFP 4-level approval + OR within 5% | Verified Invoice → RFP → review → budget → cfo → ceo → mark_complete → upload OR (within 5%) | RFP status = Closed |
| S194-12 | RFP rejection at CFO level | Same flow, Butch (CFO) rejects → | RFP status = Rejected, no payment proof required |
| S194-13 | **Dual-approval boundary** | PO exactly ₱500K.00 (threshold edge) | `requires_dual_approval=0` (threshold is `>` not `>=`), Mae alone approves |
| S194-14 | **Dual-approval +₱1** | PO ₱500,001 | `requires_dual_approval=1`, Butch required |
| S194-15 | **TIN gate** (AUDIT 2.8) | Supplier TIN cleared via SSM; attempt PO that pushes 12mo annual above ₱250K | HTTP 417: "Supplier ... requires TIN registration" — PO rejected |
| S194-16 | **S193 Inactive PO-block, Invoice-allow asymmetry** | Inactive supplier: (a) try PO → BLOCKED; (b) create Invoice against a pre-existing Active-era PO → S193 does NOT fire (may fail for other reasons, which is OK) | PO toast contains `Inactive`, Invoice error does NOT contain `Inactive` |
| S194-17 | **Duplicate invoice** (C3 at line 2560) | Create Invoice with `supplier_invoice_no=INV-DUP-001`, then try second Invoice same supplier + same number | Second submission: HTTP 417 "duplicate invoice" — rejected unless role is Procurement Manager (test both) |
| S194-18 | **Match Exception bypass** | Create Invoice for a PO that has NO Goods Receipt → rejected; then create BEI Match Exception (approved) → retry Invoice → accepted | Two API mutations captured: first rejection, then accept after exception |
| S194-19 | **Invoice date < PO date** (AUDIT 2.2) | Create PO with po_date=today; create Invoice with invoice_date=yesterday | HTTP 417: "Invoice date ... cannot be earlier than PO date ..." |
| S194-20 | **Partial receive then complete** | Approved PO for 10 units; GR #1 receives 6 units (PO status → Partially Received); GR #2 receives remaining 4 (PO status → Fully Received) | Two GRs linked; PO status transitions verified via readback |
| S194-21 | **OR > 5% variance flag** | RFP approved, paid ₱100,000; upload OR with amount ₱88,000 (12% variance) | Accepted with `or_variance_flagged=1`, RFP status shows variance review tag (not Closed immediately) |
| S194-22 | **Double-payment guard** (AUDIT 2.5) | Create advance RFP (`is_advance_payment=1`) for PO X at ₱300K (covers full PO ₱300K). Try second RFP on same PO | Second RFP: HTTP 417 "This PO is fully covered by an outstanding advance payment of PHP 300,000.00" |
| S194-23 | **Negative RBAC — Procurement User cannot approve** (v4 expanded — Blocker 7) | `test.procurement@bebang.ph` (seeded via `seededUser` per L0.5) logs in. Two surfaces: (a) PO detail page awaiting Mae approval — "Approve (Mae)" button NOT visible. (b) `/dashboard/procurement/approvals/` queue page — either the row is hidden OR the row's Approve action is hidden for this user. | Both surfaces hide the action; backend returns 403 if forced |
| S194-24 | **Warehouse User read-only** (S193 RBAC) | `test.warehouse@bebang.ph` logs in, can view `/dashboard/procurement/suppliers` grid and supplier detail, but CANNOT see "Add Supplier", "Edit", or "Approve" CTAs | Grid renders with rows; no write CTAs; route guard does not 403 (Warehouse User IS in PROCUREMENT module per S193) |
| S194-25 | **PO reject at Butch level** | ₱750K PO passes Mae approve → status=Pending Butch → Butch rejects with reason "Budget freeze" | PO status=Rejected, audit log shows `rejected_by=butch`, reason recorded |
| S194-26 | **PO reject at CEO level** | ₱1.5M new-supplier PO passes Mae + Butch → status=Pending CEO → CEO rejects with reason "Supplier not vetted" | PO status=Rejected, `rejected_by=ceo` in audit trail |
| S194-27 | **Invoice variance REJECT** | GR partial, Invoice has variance > tolerance, Accounts user clicks REJECT (not Approve) on variance queue → calls `reject_invoice_variance(reason)` | Invoice status remains unverified; reason stored; no GL posting |
| S194-28 | **RFP reject at Review level** | Verified Invoice → RFP submit → Procurement reviewer rejects with reason → `reject_payment_request(level="review")` | RFP status=Rejected at review; Budget/CFO/CEO tabs never become active |
| S194-29 | **RFP reject at Budget level** | RFP passes Review → Budget officer rejects → `reject_payment_request(level="budget")` | RFP status=Rejected at budget; CFO/CEO tabs never activated |
| S194-30 | **RFP reject at CEO level** | RFP passes Review + Budget + CFO → CEO rejects → `reject_payment_request(level="ceo")` | RFP status=Rejected at ceo; no mark_complete possible |
| S194-31 | **GR reject entire shipment** (v4 fix Blocker 4) | Approved PO 10 units → GR receives 10 → inspection rejects ALL (rejected_qty = received_qty for every line). **HARD BLOCKER:** Before writing this scenario, the agent MUST grep for `_update_po_status_after_gr` (or equivalent helper) in procurement.py and cite the EXACT status branch for the all-rejected case in the spec comment. If the code does not specify a branch, this becomes an audit finding ([BUG-S194-31] in `output/l3/s194/defects/`), not a test pass/fail. | GR status="With Issues"; PO status assertion derived from cited code branch |

> **Scenarios S194-32 through S194-38 — DESCOPED (v4).** Audit confirmed PR/PO edit pages, price change UI, and `BEI Price Change Request` UI do not exist in production. These 7 scenarios moved to a future **Procurement Edit/Delete Feature + E2E** sprint (not yet numbered — S195 was claimed by Store Universe SSOT). See `docs/plans/SPRINT_REGISTRY.md` "Next Sprint Reservation". **Backend endpoints exist** (`update_po_item_price` proc.py:7027, `approve_price_change` :6844, `reject_price_change` :6861) — that future sprint will build the UI for them, then test via browser.

### Out-of-Scope
- Extending approval thresholds (covered by existing BEI Settings)
- Adding new procurement pages (testing existing surfaces only)
- Mobile layouts (desktop certified here; mobile a future sprint)
- Multi-currency (single PHP currency)
- Full advance-payment clearing lifecycle (`approve_advance_clearing` + multi-stage clear). **Note (v4 fix Blocker 6):** S194-22 DOES test the advance-creation half (to trigger the double-payment guard) — only the clearing/settlement half is deferred.

## Airtight Browser Enforcement (v2 — Added After Review)

Every one of the 23 scenarios runs in a **real Chromium browser** driven by Playwright. The following are strict, machine-verifiable:

1. **No API-only shortcut mutations.** Every create / approve / reject / upload action is a UI action: `page.click`, `page.fill`, `page.selectOption`, `page.setInputFiles`. The test suite is configured with `use: { channel: "chrome" }` or equivalent — NOT request-only context.
2. **Network intercept is READ-ONLY.** `page.on("request", ...)` for HAR capture and assertion is allowed; `page.route("**/api/**", route => route.fulfill(...))` to fake responses is FORBIDDEN.
3. **SSM escape hatch is setup-only.** `ssmSetup.*` helpers are called ONLY in `beforeAll` / `beforeEach` for fixture creation, and in `afterEach` via `cleanupLedger` for teardown. Never inside a test body during a workflow step.
4. **Screenshots prove browser usage.** Every scenario MUST produce ≥5 PNG files in `output/l3/s194/screenshots/S194-N/`. The verification script asserts screenshot count ≥ 5 per scenario — if Playwright ran in request-only mode, screenshots can't be generated.
5. **Video capture on every scenario.** `playwright.config.ts` must set `use: { video: "on" }` (not `"retain-on-failure"`). The test suite produces one `.webm` per scenario, proving the browser actually ran.
6. **HAR capture on every scenario.** `use: { trace: "on" }` + per-test HAR attachment.
7. **Headed mode for CI authentication.** The test suite must support `--headed` locally. In CI, headless is fine — but the evidence artifacts (screenshots, video, HAR) must exist either way.
8. **Real network requests to hq.bebang.ph.** The test MUST NOT mock the Frappe backend. Every POST to `/api/method/hrms.api.procurement.*` hits live production (with test fixtures cleaned up after). This is the only way to catch SSM-side regressions that API-only tests miss.

**Anti-shortcut verification** — the verification script greps for these violations:
- `page.route.*fulfill` → FORBIDDEN (mocking)
- `ssmSetup.*` calls inside `test(...)` body (only beforeAll / afterEach allowed) → FORBIDDEN
- `axios`, `got`, `node-fetch` imports in spec file → FORBIDDEN
- Screenshots missing for any scenario → FAIL
- Video file missing for any scenario → FAIL

## Non-Negotiable Rules (QA Discipline)

1. **Library-first:** every `page.click`, `page.fill`, `page.goto` outside `tests/e2e/pages/` is a blocker. Specs consume Page Object methods.
2. **Real browser only for workflow:** `page.request.*`, `fetch()`, `curl` are FORBIDDEN in spec files for workflow operations. SSM allowed ONLY via `support/ssmSetup.ts` helpers and ONLY for: (a) test user creation/role grant, (b) test supplier/item seeding, (c) post-UI state verification.
3. **`cleanupLedger` fixture mandatory:** every scenario that creates a PR / PO / GR / Invoice / RFP / OR must register the cleanup with `cleanupLedger`. No manual try/finally.
4. **Three-uses rule:** if any pattern (button click, form fill sequence, status assertion) appears 3+ times, it MUST be extracted to the library in the same sprint.
5. **`data-testid` everywhere:** the procurement pages lack some test IDs. Phase L includes an audit task that lists missing IDs + a task to add them to the React components.
6. **Real test accounts only:** `memory/testing-accounts.md` lists the accounts. No fabricated fake users created just for this sprint.

## Existing Assets (Duplication Audit)

| Asset | Location | Classification | Notes |
|---|---|---|---|
| `BasePage` | `tests/e2e/pages/BasePage.ts` | REUSE | All new page objects extend it |
| `LoginPage` | `tests/e2e/pages/LoginPage.ts` | REUSE | For login flows |
| `StoreOrderingPage` | `tests/e2e/pages/StoreOrderingPage.ts` | REFERENCE | Pattern to copy for PurchaseRequisitionPage |
| `OrderApprovalPage` | `tests/e2e/pages/OrderApprovalPage.ts` | REFERENCE | Pattern to copy for PO approval UI |
| `ReceivingPage` | `tests/e2e/pages/ReceivingPage.ts` | REFERENCE | Pattern to copy for GoodsReceiptPage |
| `OrderBuilder` | `tests/e2e/builders/OrderBuilder.ts` | REFERENCE | Pattern to copy for ProcurementChainBuilder — DO NOT force reuse |
| `cleanupLedger` fixture | `tests/e2e/fixtures/cleanup.ts` | REUSE | Extend with procurement doctype deletions |
| `loggedInAs*` fixtures | `tests/e2e/fixtures/auth.ts` | EXTEND | Add `loggedInAsMae`, `loggedInAsButch`, `loggedInAsCEO`, `loggedInAsAccounts` if missing |
| `seededInventory` fixture | `tests/e2e/fixtures/seed.ts` | EXTEND | Add `seededSupplier(status)` + `seededItemCatalog(count)` |
| `frappeReadback` | `tests/e2e/support/frappeReadback.ts` | REUSE | For post-UI state verification |
| `ssmSetup` | `tests/e2e/support/ssmSetup.ts` | EXTEND | Add `createBEISupplier`, `setSupplierStatus`, `deleteBEISupplier` |
| `selectors.ts TEST_IDS` | `tests/e2e/support/selectors.ts` | EXTEND | Add `TEST_IDS.procurement.*` subtree |
| Existing `s07-requisition-approval.spec.ts` | `tests/e2e/` | REFERENCE | Older spec — check for duplication; may be REPLACED by s194 |
| Existing `s08-or-followup.spec.ts` | `tests/e2e/` | REFERENCE | OR flow hints — extract reusable pieces into library |

**HARD BLOCKER:** If `s07-requisition-approval.spec.ts` covers identical ground, evaluate for deletion in Phase L to avoid parallel suites.

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch:** `cd F:/Dropbox/Projects/bei-tasks && git fetch origin main && git checkout -b s194-procurement-e2e-library origin/main`. NEVER commit to main.
3. Read `.claude/docs/qa-test-library-discipline.md` fully — this sprint is its exemplar.
4. Read `docs/diagrams/PROCUREMENT_FLOW_2026-04-14.md` (in BEI-ERP repo) — visual chart of the flow being tested.
5. Read `tests/e2e/pages/BasePage.ts`, `StoreOrderingPage.ts`, `ReceivingPage.ts` — copy these patterns for new page objects.
6. Read `tests/e2e/fixtures/auth.ts`, `cleanup.ts`, `evidence.ts`, `seed.ts` — confirm fixture conventions.
7. Read `tests/e2e/support/selectors.ts` to see the existing `TEST_IDS` shape; extend without mutation.
8. Read `../BEI-ERP/memory/testing-accounts.md` — all 10 test accounts with passwords.
9. Read `../BEI-ERP/hrms/api/procurement.py` lines 136 (guard), 1249 (dual threshold), 1455 (PO create), 2709 (RFP create), 4897 (OR upload) — ground the expected API behavior.
10. Execute **Phase L first**, then Phase S. Specs depend on Page Objects existing.

## Execution Authority

Autonomous end-to-end. Do not stop for progress updates. Pause only for items in the Autonomous Execution Contract `stop_only_for` list.

---

## Delivery Phases

### Phase L0 — Library audit + data-testid survey (3 units)

**MUST_MODIFY:** `output/s194/library_audit.md` (new file)
**MUST_CONTAIN:** a table of every existing Page Object / fixture / builder / assertion that touches procurement + a gap list for what this sprint will add.

**Tasks:**
- L0.1: grep `tests/e2e/pages/` for existing procurement-related code. Document in `output/s194/library_audit.md`.
- L0.2: Open each of the 5 procurement pages (`/dashboard/procurement/{purchase-requisitions,purchase-orders,goods-receipts,invoices,payments}/{new,[id],page.tsx}`) and survey `data-testid` coverage. Write findings to `output/s194/testid_survey.md` with a row per required UI element (submit button, supplier picker, qty input, approve button, reject button, amount field, etc.) + whether a `data-testid` exists.
- L0.3: Decide on REUSE / EXTEND / REPLACE for `s07-requisition-approval.spec.ts` and `s08-or-followup.spec.ts`. Document decision in `library_audit.md`.
- **L0.4 (v4 audit Blocker 9):** Audit BEI Match Exception UI surface. Search `app/dashboard/procurement/audit/`, `pcf/`, `invoices/` for any route that creates / approves a Match Exception. If no UI exists, add a HARD BLOCKER note for S194-18 in `library_audit.md` — either descope or convert to API-only with explicit policy exception.
- **L0.5 (v4 audit Blocker 8):** Confirm `test.procurement@bebang.ph` does NOT exist in `memory/testing-accounts.md`. Plan Phase L8 must add a `seededUser({email, roles: ["Procurement User"]})` helper in `ssmSetup.ts` AND a `loggedInAsProcurementUser` fixture in `fixtures/auth.ts`. Cleanup must delete the user on `afterAll`.

**Verification:**
- [ ] `output/s194/library_audit.md` exists with ≥10 REUSE and ≥5 gap rows
- [ ] `output/s194/testid_survey.md` exists with ≥30 UI element rows

### Phase L1 — Add missing `data-testid` to procurement components (5 units)

**MUST_MODIFY:** every file listed in `output/s194/testid_survey.md` with "MISSING" flag.
**MUST_CONTAIN:** `data-testid=` in every target file's diff.

Follow the existing convention: `data-testid="procurement-<entity>-<action>"` (e.g. `procurement-pr-submit`, `procurement-po-mae-approve`, `procurement-gr-inspect-reject-all`).

**HARD BLOCKER:** Do NOT rename existing `data-testid` values — extend only. Break-glass: if an existing `data-testid` is misleading, note it in `output/s194/testid_rename_proposal.md` but do NOT rename in this sprint.

**Verification:**
- [ ] `git diff --name-only origin/main...HEAD | grep -c "app/dashboard/procurement"` matches the MISSING row count in `testid_survey.md`
- [ ] `rg 'data-testid="procurement-' app/dashboard/procurement | wc -l` ≥ 30

### Phase L2 — `selectors.ts` + `ssmSetup.ts` extensions (2 units)

**MUST_MODIFY:** `tests/e2e/support/selectors.ts`, `tests/e2e/support/ssmSetup.ts`
**MUST_CONTAIN (selectors.ts):** `procurement:` key at top level of `TEST_IDS` with nested `pr`, `po`, `gr`, `invoice`, `rfp` sub-objects
**MUST_CONTAIN (ssmSetup.ts):** `createBEISupplier`, `setSupplierStatus`, `deleteBEISupplier`, `createBEIItem`, `deleteBEIItem` exports

**Verification:**
- [ ] `grep -c "procurement:" tests/e2e/support/selectors.ts` ≥ 1
- [ ] `grep -c "createBEISupplier\|setSupplierStatus" tests/e2e/support/ssmSetup.ts` ≥ 2

### Phase L3 — `PurchaseRequisitionPage` Page Object (4 units)

**MUST_MODIFY:** `tests/e2e/pages/PurchaseRequisitionPage.ts` (new)
**MUST_CONTAIN:** class `PurchaseRequisitionPage extends BasePage`, methods: `goto`, `gotoList`, `openNew`, `fillItems(items: Array<{code, qty, notes?}>)`, `setDepartment`, `submit`, `openDetail(name)`, `approve(comment?)`, `reject(reason)`, `extractPRName()`
**MUST_CONTAIN:** at least one call to `this.screenshotStep(...)` per workflow method

### Phase L4 — `PurchaseOrderPage` Page Object (5 units)

**MUST_MODIFY:** `tests/e2e/pages/PurchaseOrderPage.ts` (new)
**MUST_CONTAIN:** class `PurchaseOrderPage extends BasePage`, methods: `goto`, `gotoList`, `convertFromPR(prName, supplier)`, `openDetail(poName)`, `approveMae(comment?)`, `approveButch(comment?)`, `approveCEO(comment?)`, `reject(reason)`, `sendToSupplier()`, `assertStatusIs(status)`, `assertRequiresDualApproval(bool)`, `extractPOName()`

### Phase L5 — `GoodsReceiptPage` + `InvoicePage` + `PaymentRequestPage` Page Objects (10 units — split 4+3+3)

- L5a: `GoodsReceiptPage.ts` — `createFromPO(poName)`, `receiveQuantities(Map<itemCode, receivedQty>)`, `rejectItem(itemCode, rejectedQty, reason)`, `submit`, `completeInspection(status)`, `assertStatusIs`, `extractGRName`
- L5b: `InvoicePage.ts` — `createFromGR(grName, supplierInvoiceNo, invoiceDate, grandTotal)`, `submitForVerification`, `verifyMatch`, `approveVariance(notes)`, `assert3WayMatched`, `assertStatusIs`, `extractInvoiceName`
- L5c: `PaymentRequestPage.ts` — `createFromInvoice(invoiceName, paymentAmount, paymentDate)`, `submitForApproval`, `approveReview`, `approveBudget`, `approveCFO`, `approveCEO`, `reject(reason, level)`, `markComplete(transactionRef, paymentProof)`, `uploadOR(orNumber, orDate, orAmount, orAttachment)`, `assertStatusIs`, `extractRFPName`

### Phase L6 — `ProcurementChainBuilder` (4 units)

**MUST_MODIFY:** `tests/e2e/builders/ProcurementChainBuilder.ts`
**MUST_CONTAIN:** static factory `ProcurementChainBuilder.create()`, chainable methods: `.forSupplier(code)`, `.withItems(list)`, `.atAmount(php)`, `.asNewSupplier(bool)`, `.withRejection(stage, reason?)`, `.withPartialReceive(itemCode, receivedQty, rejectedQty)`, `.withVariance(pct)`, `.withOR(amount, variancePct?)`, `.build() -> ProcurementPlan`

Each `build()` returns a plan object that the spec's helper function executes step-by-step via the Page Objects.

### Phase L7 — Procurement assertions module (3 units)

**MUST_MODIFY:** `tests/e2e/assertions/procurementAssertions.ts`
**MUST_CONTAIN:** exports: `assertPOStatus(page, poName, expected)`, `assertDualApprovalRequired(page, poName, bool)`, `assertGRLinkedToPO(page, grName, poName)`, `assertInvoice3WayMatched(page, invoiceName)`, `assertRFPApprovalChain(page, rfpName, [level1, level2, ...])`, `assertORClosesRFP(page, rfpName, orNumber)`, `assertS193GuardFired(page, operation, supplierStatus)`

Each assertion uses Page Object methods + `frappeReadback.readDoc` for backend state verification.

### Phase L8 — Fixtures: `procurementPages`, `seededSupplier`, `seededItemCatalog`, `seededUser`, `loggedInAsProcurementUser` (3 units — v4 expanded for Blocker 8)

**MUST_MODIFY:** `tests/e2e/fixtures/procurement.ts` (new); extend `tests/e2e/fixtures/auth.ts` (new `loggedInAsProcurementUser`); extend `tests/e2e/fixtures/index.ts`
**MUST_MODIFY:** `tests/e2e/support/ssmSetup.ts` — add `seededUser({email, roles})` helper with cleanup
**MUST_CONTAIN:** 5 fixtures total. `seededSupplier(status)` takes a status param and creates a supplier via `ssmSetup.createBEISupplier` + registers cleanup. `seededItemCatalog(count)` creates N items via SSM + cleanup. `seededUser({email: "test.procurement@bebang.ph", roles: ["Procurement User"]})` creates the missing test account (NOT in memory/testing-accounts.md) — registers cleanup so user is deleted on `afterAll`. `loggedInAsProcurementUser` returns a logged-in `Page` for that seeded user.

### Phase S1 — Scenarios S194-1 through S194-5 (PR + PO happy + rejection paths) (5 units)

**MUST_MODIFY:** `tests/e2e/specs/s194-procurement-chain.spec.ts` (new)
**MUST_CONTAIN:** `test("S194-1:`, `test("S194-2:`, `test("S194-3:`, `test("S194-4:`, `test("S194-5:`
**MUST_CONTAIN:** every test uses a `loggedInAs*` fixture, the `procurementPages` fixture, and `cleanupLedger`. No `page.request`, no `fetch(`.

### Phase S2 — Scenarios S194-6 through S194-8 (S193 supplier status guard) (4 units)

**MUST_MODIFY:** same spec file
**MUST_CONTAIN:** `test("S194-6:`, `test("S194-7:`, `test("S194-8:`
**MUST_CONTAIN:** each test uses `seededSupplier("Pending Verification")` fixture and asserts the exact S193 error message via `assertS193GuardFired`.

### Phase S3 — Scenarios S194-9, S194-10 (GR + Invoice 3-way match) (4 units)

**MUST_CONTAIN:** `test("S194-9:`, `test("S194-10:`
**MUST_CONTAIN:** S194-10 uses `assertInvoice3WayMatched` with variance path and asserts the `approve_invoice_variance` CTA is visible and wired for the Accounts role.

### Phase S4 — Scenarios S194-11, S194-12 (RFP 4-level + OR; RFP rejection at CFO) (4 units)

**MUST_CONTAIN:** `test("S194-11:`, `test("S194-12:`
**MUST_CONTAIN:** S194-11 exercises `approveReview` → `approveBudget` → `approveCFO` → `approveCEO` → `markComplete` → `uploadOR` with an OR amount within 5%. S194-12 rejects at CFO level and asserts the chain stops.

### Phase S6 — Threshold & TIN boundary scenarios (S194-13, S194-14, S194-15) (4 units)

**MUST_CONTAIN:** `test("S194-13:`, `test("S194-14:`, `test("S194-15:`
**HARD BLOCKER:** S194-13 and S194-14 exercise the `dual_approval_threshold` = ₱500,000.00 at and above the edge. S194-13 MUST use `grand_total = 500000.00` exactly and assert `requires_dual_approval === 0` BEFORE any approval click. S194-14 MUST use `grand_total = 500001.00` and assert `requires_dual_approval === 1`. If the threshold in `BEI Settings` has been changed, the test MUST read it first (via `frappeReadback.readDoc("BEI Settings", "BEI Settings")`) and compute the test amounts from it — do NOT hardcode ₱500K.
**HARD BLOCKER:** S194-15 modifies supplier TIN via `ssmSetup.setSupplierField(code, "tin", null)` then reverts on cleanup. The test MUST restore the original TIN in `afterEach` or the supplier is left in a broken state.

### Phase S7 — S193 asymmetry + Duplicate invoice + Match Exception (S194-16, S194-17, S194-18) (5 units)

**MUST_CONTAIN:** `test("S194-16:`, `test("S194-17:`, `test("S194-18:`
**HARD BLOCKER:** S194-17 MUST test BOTH the regular procurement user (rejected) AND the Procurement Manager override (accepted) — the line 2575 `_require_roles(["Procurement Manager", "System Manager"], "override duplicate invoice")` gate. If the agent only tests one role, the scenario is incomplete.
**HARD BLOCKER:** S194-18 MUST create the `BEI Match Exception` via the actual UI route (`/dashboard/procurement/audit` or equivalent) and capture the approval click — not via SSM. The whole point is browser fidelity.

### Phase S8 — Date sequence + Partial receive + OR variance + Double-payment + RBAC (S194-19, S194-20, S194-21, S194-22, S194-23, S194-24) (8 units — 1.3/scenario)

**MUST_CONTAIN:** `test("S194-19:`, `test("S194-20:`, `test("S194-21:`, `test("S194-22:`, `test("S194-23:`, `test("S194-24:`
**HARD BLOCKER (S194-20):** The two GRs MUST be created from the SAME PO via the UI sequentially. After GR #1, the spec MUST open the PO detail page and assert the status changed to "Partially Received". After GR #2, re-open and assert "Fully Received". This is the multi-GR path regression test.
**HARD BLOCKER (S194-21):** The OR amount MUST be ≥10% off (use ₱88,000 on a ₱100,000 payment = 12% variance) to unambiguously trigger the flag. 5.5%–9% is ambiguous on rounding.
**HARD BLOCKER (S194-22):** `is_advance_payment=1` requires checking the advance checkbox in the RFP form. The test MUST verify the checkbox is interactable and labeled correctly in the UI (`data-testid="procurement-rfp-is-advance"`).
**HARD BLOCKER (S194-23):** "Button not visible" is tested via Playwright `toBeHidden()` — NOT `toBeEnabled(false)`. Per the discipline doc, a false-affordance disabled button is a shell-risk pattern. If the button IS in the DOM but disabled, file [BUG-S194-RBAC] and mark the scenario FAIL until fixed.
**HARD BLOCKER (S194-24):** This validates the S193 audit amendment (Warehouse User added to PROCUREMENT module). If this scenario fails, it's a regression on the already-shipped S193 + S186 work, not a new bug.

### Phase S5 — Evidence capture + screenshot-per-step + video (3 units)

**MUST_MODIFY:** same spec file uses the `evidence` fixture: `screenshotPerStep`, `networkHar`, `videoCapture`
**MUST_CONTAIN:** `screenshotStep(` called at every form submission + approval click (verified via `rg "screenshotStep" tests/e2e/specs/s194*`)
**Output:** `output/l3/s194/screenshots/<scenario>/<step>.png`, `output/l3/s194/har/<scenario>.har`, `output/l3/s194/video/<scenario>.webm`

### Phase C — Closeout (4 units)

- C1: Write `output/l3/s194/form_submissions.json`, `api_mutations.json`, `state_verification.json` from Playwright test run aggregated data.
- C2: If ≥3 library fixes happened during Phase S execution, emit `output/l3/s194/LIBRARY_IMPROVEMENTS.md` listing each fix + its promotion to the library.
- C3: Write `output/l3/s194/RUN_SUMMARY.md` with per-scenario PASS/FAIL + evidence paths.
- C4: Update plan YAML: `status: PLANNED` → `status: PR_CREATED`, fill `completed_date`, `execution_summary`.
- C5: Update `docs/plans/SPRINT_REGISTRY.md` S194 row with PR number.
- C6: `git add -f docs/plans/... output/s194/ output/l3/s194/` → commit → push.
- C7: Create PR: `GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/BEI-Tasks --base main --head s194-procurement-e2e-library --title "feat(S194): procurement chain E2E library + certification spec"`. Body includes per-scenario PASS/FAIL table.

---

## Requirements Regression Checklist

- [ ] Does every spec file use at least one `loggedInAs*` fixture? (`rg "loggedInAs" tests/e2e/specs/s194*.spec.ts` ≥ 12)
- [ ] Does the spec file have ZERO occurrences of `page.request`, `fetch(`, `curl` for workflow ops? (`rg 'page\.request|fetch\(|curl' tests/e2e/specs/s194*.spec.ts` = 0)
- [ ] Does every test end with `cleanupLedger.pendingEntries === 0` in afterEach? (Discipline §3)
- [ ] Does every button click in a spec call a Page Object method (not `page.click("button:has-text(...)")`)? (`rg 'page\.click\("button:has-text|page\.locator\("button' tests/e2e/specs/s194*` = 0)
- [ ] Did Phase L1 add `data-testid` to every procurement UI element listed in `testid_survey.md` with MISSING flag?
- [ ] Did Phase L audit `s07-requisition-approval.spec.ts` and `s08-or-followup.spec.ts` for duplication, and either delete or explicitly justify keeping them?
- [ ] Does S194-2 verify that PO at ₱750K raises `requires_dual_approval=1` BEFORE any approval click (asserted via `assertDualApprovalRequired(page, poName, true)`)?
- [ ] Does S194-3 use a supplier with `is_new_supplier=1` set via SSM BEFORE the test runs (recorded in `cleanupLedger`)?
- [ ] Do S194-6/7/8 use the EXACT error message match `/Cannot create (Purchase Order|Invoice|Payment Request): Supplier .* is Pending Verification/`?
- [ ] Does S194-11 verify OR 5% variance tolerance by uploading an OR with amount within 5% and asserting RFP closes?
- [ ] Does S194-12 verify CFO rejection prevents CEO approval tab from ever becoming active?
- [ ] Is the `ProcurementChainBuilder` extracted to `tests/e2e/builders/` (not inline in spec)?
- [ ] Are `TEST_IDS.procurement.*` defined in `selectors.ts`, not inline strings in Page Objects?
- [ ] **(v2 airtight)** Does S194-13 use exactly `500000.00` AND S194-14 use exactly `500001.00`, and do BOTH tests read `dual_approval_threshold` from BEI Settings at test-start rather than hardcoding?
- [ ] **(v2 airtight)** Does S194-15 restore the supplier's original TIN in `afterEach`?
- [ ] **(v2 airtight)** Does S194-16 assert the negative case — Invoice for Inactive supplier returns an error that does NOT contain the word `Inactive` (proving S193 did not fire)?
- [ ] **(v2 airtight)** Does S194-17 test both the Procurement User path (REJECTED) and the Procurement Manager override (ACCEPTED)?
- [ ] **(v2 airtight)** Does S194-18 create the BEI Match Exception through the UI (not SSM) and capture the approval click as a screenshot?
- [ ] **(v2 airtight)** Does S194-19 set `invoice_date` to PO date MINUS 1 day (not today, not a random past date)?
- [ ] **(v2 airtight)** Does S194-20 create TWO Goods Receipts sequentially via the UI and assert "Partially Received" between them, "Fully Received" after the second?
- [ ] **(v2 airtight)** Does S194-21 use ≥10% variance (₱88,000 on ₱100,000) and assert the variance flag, NOT just that the OR was accepted?
- [ ] **(v2 airtight)** Does S194-22 check the `is_advance_payment` checkbox through the UI with `data-testid="procurement-rfp-is-advance"`?
- [ ] **(v2 airtight)** Does S194-23 use Playwright `toBeHidden()` (not `toBeDisabled()`) for the approve button assertion?
- [ ] **(v2 airtight)** Does S194-24 log in as `test.warehouse@bebang.ph` and assert the supplier grid renders WITHOUT 403, while write CTAs are hidden?
- [ ] **(v2 airtight)** Does `playwright.config.ts` have `use: { video: "on", trace: "on" }` (not "retain-on-failure")?
- [ ] **(v2 airtight)** Does every scenario produce ≥5 screenshots verified by `verify_phase.sh S`?
- [ ] **(v2 airtight)** Does the spec file have ZERO occurrences of `page.route(...fulfill` (no request mocking)?
- [ ] **(v2 airtight)** Does the spec file have ZERO imports of `axios`, `got`, `node-fetch`?

## Zero-Skip Enforcement

Every task MUST be implemented. If a task cannot be completed, the agent STOPS and asks Sam.

### Forbidden Agent Behaviors
- Inlining `page.click` / `page.fill` in a spec file instead of Page Object
- Using `page.request.post` to bypass UI for "speed"
- Using `waitForTimeout(n)` instead of `waitForSelector` / `waitForResponse` (flakiness masking — Discipline §C)
- Marking a scenario PASS when cleanup failed
- Retrying a scenario 3+ times until it passes without logging a flakiness ticket
- Combining scenarios (e.g., S194-4 and S194-5 into "rejection tests") and dropping a path
- Skipping Phase L1 `data-testid` additions to "save time" and using CSS selectors instead

### Phase Completion Verification Script

Create `output/s194/verify_phase.sh`:
```bash
#!/usr/bin/env bash
set -e
PHASE="$1"  # L, S, or C
cd /f/Dropbox/Projects/bei-tasks

if [ "$PHASE" = "L" ] || [ "$PHASE" = "ALL" ]; then
  test -f tests/e2e/pages/PurchaseRequisitionPage.ts || { echo "❌ PurchaseRequisitionPage missing"; exit 1; }
  test -f tests/e2e/pages/PurchaseOrderPage.ts || { echo "❌ PurchaseOrderPage missing"; exit 1; }
  test -f tests/e2e/pages/GoodsReceiptPage.ts || { echo "❌ GoodsReceiptPage missing"; exit 1; }
  test -f tests/e2e/pages/InvoicePage.ts || { echo "❌ InvoicePage missing"; exit 1; }
  test -f tests/e2e/pages/PaymentRequestPage.ts || { echo "❌ PaymentRequestPage missing"; exit 1; }
  test -f tests/e2e/builders/ProcurementChainBuilder.ts || { echo "❌ ProcurementChainBuilder missing"; exit 1; }
  test -f tests/e2e/assertions/procurementAssertions.ts || { echo "❌ procurementAssertions missing"; exit 1; }
  test -f tests/e2e/fixtures/procurement.ts || { echo "❌ procurement fixture missing"; exit 1; }
  grep -q "procurement:" tests/e2e/support/selectors.ts || { echo "❌ TEST_IDS.procurement missing"; exit 1; }
  grep -q "createBEISupplier" tests/e2e/support/ssmSetup.ts || { echo "❌ createBEISupplier missing"; exit 1; }
  echo "✅ Phase L file gate passed"
fi

if [ "$PHASE" = "S" ] || [ "$PHASE" = "ALL" ]; then
  SPEC=tests/e2e/specs/s194-procurement-chain.spec.ts
  test -f "$SPEC" || { echo "❌ s194 spec missing"; exit 1; }
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31; do
    grep -q "S194-${i}:" "$SPEC" || { echo "❌ S194-${i} missing"; exit 1; }
  done
  # Anti-shortcut gates (Discipline + Airtight Browser Enforcement)
  if grep -E 'page\.request|fetch\(|curl ' "$SPEC"; then echo "❌ Forbidden API call in spec"; exit 1; fi
  if grep -E 'page\.click\("button:has-text|page\.locator\("button' "$SPEC"; then echo "❌ Inline button selector in spec"; exit 1; fi
  if grep -q 'waitForTimeout' "$SPEC"; then echo "❌ waitForTimeout used (flakiness mask)"; exit 1; fi
  if grep -E 'page\.route.*fulfill|page\.route\(.*mock' "$SPEC"; then echo "❌ page.route mocking forbidden (airtight browser rule)"; exit 1; fi
  if grep -E "^import.*(axios|got|node-fetch)" "$SPEC"; then echo "❌ HTTP client import forbidden — use browser"; exit 1; fi
  grep -q "cleanupLedger" "$SPEC" || { echo "❌ cleanupLedger not used"; exit 1; }
  # Airtight: each scenario must have screenshots
  # v4 fix (audit Blocker 10): require directory to exist — empty dir = scenario didn't run
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31; do
    DIR="output/l3/s194/screenshots/S194-${i}"
    [ -d "$DIR" ] || { echo "❌ S194-${i} screenshot dir missing — scenario did not run"; exit 1; }
    COUNT=$(ls "$DIR"/*.png 2>/dev/null | wc -l)
    [ "$COUNT" -ge 5 ] || { echo "❌ S194-${i} has only $COUNT screenshots (need ≥5)"; exit 1; }
  done
  echo "✅ Phase S spec gate passed"
fi

if [ "$PHASE" = "C" ] || [ "$PHASE" = "ALL" ]; then
  test -f output/l3/s194/form_submissions.json || { echo "❌ form_submissions.json missing"; exit 1; }
  test -f output/l3/s194/api_mutations.json || { echo "❌ api_mutations.json missing"; exit 1; }
  test -f output/l3/s194/state_verification.json || { echo "❌ state_verification.json missing"; exit 1; }
  test -f output/l3/s194/RUN_SUMMARY.md || { echo "❌ RUN_SUMMARY missing"; exit 1; }
  echo "✅ Phase C artifact gate passed"
fi
```

Run: `bash output/s194/verify_phase.sh L` after Phase L. `... S` after Phase S. `... C` after closeout.

---

## L3 Workflow Scenarios (Plan-Governed)

The 12 scenarios are authoritative here. Any scenario dropped or combined during execution is a Zero-Skip violation.

### L3 Prerequisites (SSM setup — Sam or agent via `ssmSetup` helpers)

Before Phase S runs, ensure these test fixtures exist on production hq.bebang.ph:

| Fixture | Create method | Purpose |
|---|---|---|
| `TEST-S194-SUP-ACTIVE` | `createBEISupplier({status: "Active"})` | S194-1/2/3/9/10/11/12 baseline supplier |
| `TEST-S194-SUP-NEW` | `createBEISupplier({status: "Active", is_new_supplier: 1})` | S194-3 new-supplier CEO path |
| `TEST-S194-SUP-PV` | `createBEISupplier({status: "Pending Verification"})` | S194-6/7/8 S193 guard tests |
| `TEST-S194-ITEM-01..05` | `createBEIItem({item_group: "Test"})` × 5 | Line items for multi-item scenarios |

All created via `cleanupLedger`-registered `ssmSetup` helpers — auto-deleted on `afterAll`.

### Evidence files required before closeout

```
output/l3/s194/form_submissions.json      # every form submit with payload + resulting doc name
output/l3/s194/api_mutations.json         # every mutation API call (POST to /api/method/...) with response
output/l3/s194/state_verification.json    # post-UI readback of each created doc via frappeReadback
output/l3/s194/screenshots/<S194-N>/*.png # screenshot per step per scenario
output/l3/s194/video/<S194-N>.webm        # full video per scenario
output/l3/s194/har/<S194-N>.har            # network HAR per scenario
output/l3/s194/RUN_SUMMARY.md              # per-scenario PASS/FAIL + evidence paths
output/l3/s194/LIBRARY_IMPROVEMENTS.md     # (if ≥3 library fixes made during execution)
```

### Fresh session recommendation

62 units > 40. **Run Phase S in a fresh agent session** after Phase L is merged. Context exhaustion at the tail of a long session is the #1 cause of L3 shortcuts (S092 incident).

---

## Failure Response — Iterate Until Green (v5 amendment 2026-04-15)

**The agent MUST NOT stop until every test-blocking defect is fixed, committed, pushed, AND the next sweep re-attempted. "Defects documented" is NOT a closeout state.** S194's first run cycle stopped at 0 PASS / 31 FAIL because the agent treated documentation as completion. That mode is forbidden going forward.

### Defect classification (mandatory before deciding to stop)

Every failure must be tagged BLOCKING or DEFERRABLE before any closeout decision:

| Class | Definition | Required action |
|---|---|---|
| **BLOCKING** | The defect prevents a scenario from reaching its assertion phase. Examples: Page Object selector that times out, fixture that fails to provision, login that fails, navigation that returns 4xx, dependent test chain (S194-1 fails → S194-2..3..9..10..11..12.. cascade fail). | **Fix in this session. Commit. Push. Re-run.** No exceptions. Continue iteration loop until the scenario reaches its assertion phase (PASS or genuine FAIL on assertion, not on infrastructure). |
| **DEFERRABLE** | The defect is real but does NOT prevent the scenario from reaching its assertion phase, OR is a product finding outside the test's certification scope. Examples: missing data-testid that has a working text fallback; UI cosmetic glitch; backend RBAC finding (S194-24 Warehouse role) that is a real product issue but separate from the workflow being certified; missing OR optional UI surface (S194-22 advance-payment checkbox absent). | **Document in `output/l3/s194/defects/POST_CERT_DEFECTS.md`** with reproduction steps and severity. Do NOT fix in this session. Do NOT block other tests. Fix as a single follow-up PR after all 31 scenarios PASS. |

### Iterate-Until-Green Loop (mandatory)

```
1. Run sweep (or single scenario): npx playwright test ...
2. For each FAIL:
   a. Open the trace: npx playwright show-trace output/l3/s194/har/<file>.zip
   b. Identify the failure point (selector / wait / fixture / chain)
   c. Classify: BLOCKING or DEFERRABLE
   d. If BLOCKING:
      - Patch the smallest unit (Page Object selector, fixture, ssmSetup helper)
      - Commit with message: "fix(S194 P-iter): <scenario> <one-line>"
      - Push immediately so PR #398 / #579 reflect every iteration
      - Add the fix to `output/l3/s194/LIBRARY_IMPROVEMENTS.md`
   e. If DEFERRABLE:
      - Append to `output/l3/s194/defects/POST_CERT_DEFECTS.md` with repro
      - Do not patch
3. After ALL blocking fixes for the cycle: re-run the sweep
4. Repeat until: 31 PASS / 0 FAIL OR a true Stop-Only-For trigger fires
5. Only then write the final RUN_SUMMARY and advance plan status to COMPLETED
```

### Stop-Only-For (the only reasons to halt iteration)

The agent stops the iteration loop ONLY for items that match the `stop_only_for` list in the Autonomous Execution Contract:

- Missing credentials / access that cannot be resolved with available Doppler secrets
- Backend hard-down (502 / DNS) that persists for >15 min — wait or escalate to Sam
- A defect that requires a destructive backend mutation (DDL / data wipe) needing explicit operator authorization
- A defect rooted in an in-flight separate sprint's code where overwriting risks losing that work

A test FAILING is **not** a stop reason. A defect being hard to fix is **not** a stop reason. Lack of energy is **not** a stop reason. The stop condition is binary: green or one of the four triggers above.

### Post-cert cleanup PR

After the certification run shows 31/31 PASS, the agent creates a single follow-up PR titled `chore(S194): post-cert deferred defects + library polish` that:

1. Reads `output/l3/s194/defects/POST_CERT_DEFECTS.md`
2. Fixes every entry that has a clear remedy (data-testids, RBAC corrections, etc.)
3. Files true product issues (e.g., missing UI surfaces) as separate sprint plans (`docs/plans/YYYY-MM-DD-sprint-NNN-<slug>.md`) with reservation in `SPRINT_REGISTRY.md`
4. Closes out S194 fully (plan YAML → COMPLETED, registry → COMPLETED)

### Library improvements log

Throughout the iterate-until-green cycle, every Page Object / fixture / helper change goes into `output/l3/s194/LIBRARY_IMPROVEMENTS.md` with:

- File touched
- One-line reason
- Which scenarios it unblocks (e.g., "fix `convertToPO` waits for `pr.status === 'Pending Approval'` — unblocks S194-1, 2, 3, 4, 5, 9, 10, 11, 12, 13, 14, 16, 17, 19, 20, 21, 22, 25, 26, 27, 28, 29, 30, 31")

This file IS the certification-cycle audit trail and informs the post-cert cleanup PR.

---

## Phase Budget Contract

| Phase | Units | Scope |
|---|---|---|
| L0 — Library audit + testid survey | 3 | Read-only + gap list |
| L1 — Add data-testid to procurement UI | 5 | React component edits |
| L2 — selectors.ts + ssmSetup.ts | 2 | Library-only |
| L3 — PurchaseRequisitionPage | 4 | Page Object |
| L4 — PurchaseOrderPage | 5 | Page Object |
| L5 — GR + Invoice + RFP Page Objects | 10 (4+3+3) | Page Objects |
| L6 — ProcurementChainBuilder | 4 | Builder |
| L7 — procurementAssertions | 3 | Assertions module |
| L8 — procurement fixtures | 2 | Fixture |
| S1 — Scenarios 1-5 (PR + PO + rejection) | 5 | Specs |
| S2 — Scenarios 6-8 (S193 guard) | 4 | Specs |
| S3 — Scenarios 9-10 (GR + Invoice) | 4 | Specs |
| S4 — Scenarios 11-12 (RFP + OR) | 4 | Specs |
| S6 — Scenarios 13-15 (threshold + TIN boundaries) | 4 | Specs |
| S7 — Scenarios 16-18 (S193 asymmetry + duplicate invoice + match exception) | 5 | Specs |
| S8 — Scenarios 19-24 (date + partial + OR variance + double-pay + RBAC) | 8 | Specs |
| **S9 — Scenarios 25-27 (PO Butch/CEO reject + Invoice variance reject)** | 4 | Specs |
| **S10 — Scenarios 28-31 (RFP Review/Budget/CEO reject + GR reject-entire)** | 5 | Specs |
| ~~S11~~ ~~S12~~ | DESCOPED in v4 | — | Moved to future Procurement Edit sprint (S195 was reassigned to Store Universe SSOT) |
| S5 — Evidence capture wiring | 3 | Spec extensions |
| C — Closeout | 4 | PR + registry + artifacts |
| **Total** | **~82** | **2 sessions recommended** — Session A: Phase L (~38u). Session B: Phases S1-S10 + S5 + C (~44u). |

- hard_limit: 15 per phase (L5 splits enforced)
- preferred_split_threshold: 12
- All phases within budget.

## Scope Size Warning

62 units is under the 80-unit ceiling but near the upper band for a single session. **Strong recommendation:** execute Phase L in one session (≤38 units), commit + push, then execute Phase S + C in a **fresh session**. This matches Discipline §4 "Separate session recommendation for >40 work units".

---

## Ground-Truth Lock

- **evidence_sources:**
  - `.claude/docs/qa-test-library-discipline.md` → library layout, five non-negotiables, failure modes
  - `docs/diagrams/PROCUREMENT_FLOW_2026-04-14.md` → workflow being certified
  - `hrms/api/procurement.py:1249` → `dual_approval_threshold` (₱500K)
  - `hrms/api/procurement.py:136` → `_assert_supplier_active` S193 guard
  - `hrms/api/procurement.py:4897` → `upload_official_receipt` OR 5% rule
  - `memory/testing-accounts.md` → test account credentials
  - `tests/e2e/pages/StoreOrderingPage.ts` → pattern for new Page Objects
- **authoritative_sections:** Delivery Phases, Requirements Regression Checklist, L3 Workflow Scenarios. Design Rationale is traceability.
- **normalization_required:** amendments that change scenario count, thresholds, or Page Object method names must update all 4 sections in the same edit.

---

## Anti-Rewind / Concurrent-Run Protection

- **ownership_matrix:** This sprint owns `tests/e2e/pages/Purchase*.ts`, `tests/e2e/pages/GoodsReceiptPage.ts`, `tests/e2e/pages/InvoicePage.ts`, `tests/e2e/pages/PaymentRequestPage.ts`, `tests/e2e/builders/ProcurementChainBuilder.ts`, `tests/e2e/assertions/procurementAssertions.ts`, `tests/e2e/fixtures/procurement.ts`, `tests/e2e/specs/s194-procurement-chain.spec.ts`. EXTENDS `tests/e2e/support/selectors.ts`, `tests/e2e/support/ssmSetup.ts`, `tests/e2e/fixtures/{auth,cleanup,seed,index}.ts` (additive only).
- **protected_surfaces:** DO NOT modify `StoreOrderingPage`, `OrderApprovalPage`, `DispatchPage`, `ReceivingPage` page objects. DO NOT modify `OrderBuilder`. DO NOT modify existing specs (`s190-*`, `s192-*`, `s27-procurement-*`). DO NOT remove any existing `data-testid`.
- **remote_truth_baseline:** `origin/main` HEAD at branch creation. Record SHA in closeout artifact.
- **freshness_gate:** Before PR creation: `git fetch origin main && git rebase origin/main`. If conflicts in `selectors.ts` / `ssmSetup.ts` / `index.ts`, resolve with additive-only strategy.

---

## Autonomous Execution Contract

- **completion_condition:**
  - All 14 phases (L0-L8, S1-S5, C) green
  - 12/12 scenarios PASS (or app-bug [BUG-S194-N] filed with root cause)
  - Evidence files committed to `output/l3/s194/`
  - `verify_phase.sh ALL` exits 0
  - PR created against main
  - Plan YAML status = `PR_CREATED`
  - `SPRINT_REGISTRY.md` S194 row has PR number
- **stop_only_for:**
  - Missing credentials for test accounts (Doppler / memory file access)
  - SSM bridge unavailable for supplier/item seeding (environmental blocker)
  - Production UI missing a route/control the plan depends on (REPLACE with [UNVERIFIED — requires resolution] in a scenario, continue others, flag Sam)
  - ≥3 scenarios failing for reasons clearly outside plan scope
- **continue_without_pause_through:** library → spec → evidence → PR → closeout
- **blocker_policy:**
  - programmatic (lint / type error) → fix and continue
  - flaky test → fix the library per Failure Mode C, continue
  - app bug → file BUG defect, skip scenario with documented reason, continue
  - business-policy (e.g. Sam changes a threshold mid-sprint) → pause
- **signoff_authority:** single-owner (Sam)
- **canonical_closeout_artifacts:**
  - `docs/plans/2026-04-14-sprint-194-procurement-e2e-library.md` (status → PR_CREATED)
  - `docs/plans/SPRINT_REGISTRY.md` (row updated)
  - `output/s194/library_audit.md`, `testid_survey.md`, `verify_phase.sh`
  - `output/l3/s194/form_submissions.json`, `api_mutations.json`, `state_verification.json`, `RUN_SUMMARY.md`
  - `output/l3/s194/screenshots/`, `video/`, `har/`
  - `output/l3/s194/LIBRARY_IMPROVEMENTS.md` (conditional)

---

## Execution Workflow

- Extract library: just edit files on the sprint branch
- Run specs locally: `cd ../bei-tasks && npx playwright test tests/e2e/specs/s194-procurement-chain.spec.ts --headed` to watch real browser
- Run headless for CI: `npx playwright test tests/e2e/specs/s194-procurement-chain.spec.ts`
- Deploy: PR-handoff (agent creates PR, Sam merges). No backend deploy needed — tests run against live hq.bebang.ph + my.bebang.ph.

---

## Verification Checklist (Final)

- [ ] 5 new Page Objects exist in `tests/e2e/pages/`
- [ ] `ProcurementChainBuilder` in `tests/e2e/builders/`
- [ ] `procurementAssertions` in `tests/e2e/assertions/`
- [ ] `procurement` fixture in `tests/e2e/fixtures/`
- [ ] `TEST_IDS.procurement.*` in `selectors.ts`
- [ ] `createBEISupplier`, `setSupplierStatus`, `createBEIItem` in `ssmSetup.ts`
- [ ] 12 scenarios in `s194-procurement-chain.spec.ts`
- [ ] Zero `page.request|fetch(` in spec file
- [ ] Zero `page.click("button:has-text` or `page.locator("button` in spec file
- [ ] Zero `waitForTimeout` in spec file
- [ ] Every spec uses `cleanupLedger` fixture
- [ ] `data-testid` added to all UI elements listed in `testid_survey.md` with MISSING flag
- [ ] Evidence files in `output/l3/s194/`
- [ ] `verify_phase.sh ALL` exits 0
- [ ] PR against `main` created with per-scenario PASS/FAIL table
- [ ] Plan YAML updated to `PR_CREATED`
- [ ] Registry row has PR number

## Branch Lifecycle

| Branch | Repo | Merge Target | Cleanup |
|---|---|---|---|
| `s194-procurement-e2e-library` | bei-tasks | main | Delete after PR merge |

Created from latest `origin/main`. PR-handoff — Sam merges after reviewing PASS/FAIL table and evidence files.
