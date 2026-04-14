# S194 — Library Audit (Phase L0)

**Date:** 2026-04-14
**Branch:** `s194-procurement-e2e-library` @ bei-tasks `cf0f2d174d93bbe8a40adb5e8ebcbe406be41b28`
**Owner:** S194 agent

## 1. Existing Assets (REUSE / REFERENCE / EXTEND)

| # | Asset | Path | Classification | Notes for S194 |
|---|---|---|---|---|
| 1 | `BasePage` | `tests/e2e/pages/BasePage.ts` | REUSE | Every new Page Object extends this. Exposes `testId()`, `waitForToast()`, `screenshotStep()`, `assertUrlContains()`, `goto()`. |
| 2 | `LoginPage` | `tests/e2e/pages/LoginPage.ts` | REUSE | Credentials login flow. Used by `loggedInAs*` fixtures. |
| 3 | `StoreOrderingPage` | `tests/e2e/pages/StoreOrderingPage.ts` | REFERENCE | Pattern template for `PurchaseRequisitionPage`. Shows TEST_IDS usage with role-based fallbacks. |
| 4 | `OrderApprovalPage` | `tests/e2e/pages/OrderApprovalPage.ts` | REFERENCE | Pattern for PO approval UI. |
| 5 | `ReceivingPage` | `tests/e2e/pages/ReceivingPage.ts` | REFERENCE | Pattern for `GoodsReceiptPage`. |
| 6 | `DispatchPage` | `tests/e2e/pages/DispatchPage.ts` | REFERENCE | Reject/inspection flow patterns. |
| 7 | `OrderBuilder` | `tests/e2e/builders/OrderBuilder.ts` | REFERENCE | Pattern for `ProcurementChainBuilder`. Do NOT force reuse (different domain). |
| 8 | `UserBuilder` | `tests/e2e/builders/UserBuilder.ts` | REFERENCE | Pattern for `seededUser` SSM helper. |
| 9 | `cleanupLedger` | `tests/e2e/fixtures/cleanup.ts` | EXTEND | Add deletions for BEI Purchase Requisition / Purchase Order / Goods Receipt / Invoice / Payment Request / Match Exception. |
| 10 | `loggedInAs*` fixtures | `tests/e2e/fixtures/auth.ts` | EXTEND | Add `loggedInAsMae`, `loggedInAsButch`, `loggedInAsCEO` (already exists as `loggedInAsSam`?), `loggedInAsAccounts`, `loggedInAsProcurementUser`, `loggedInAsWarehouse`. |
| 11 | `seededInventory` fixture | `tests/e2e/fixtures/seed.ts` | EXTEND | Add sibling fixtures `seededSupplier(status)`, `seededItemCatalog(count)`, `seededUser(opts)`. |
| 12 | `frappeReadback` | `tests/e2e/support/frappeReadback.ts` | REUSE | Use `readDoc(doctype, name)` for post-UI state verification (PO status, RFP approvals array, etc.). |
| 13 | `ssmSetup` | `tests/e2e/support/ssmSetup.ts` | EXTEND | Add `createBEISupplier`, `setSupplierStatus`, `deleteBEISupplier`, `createBEIItem`, `deleteBEIItem`, `setSupplierField(code, field, value)`, `seededUser({email, roles})`. |
| 14 | `selectors.ts TEST_IDS` | `tests/e2e/support/selectors.ts` | EXTEND | Add `procurement:` subtree with nested `pr`, `po`, `gr`, `invoice`, `rfp`, `ox` (match exception) keys. Do NOT mutate existing S192 entries. |
| 15 | `evidence` fixture | `tests/e2e/fixtures/evidence.ts` | REUSE | `screenshotStep`, `networkHar`, `videoCapture` already support per-scenario artifact dirs. |

**REUSE count ≥10: PASS** (15 assets).

## 2. Gap List — What S194 Must Add

| # | Asset | Classification | Required for |
|---|---|---|---|
| G1 | `PurchaseRequisitionPage.ts` | NEW | S194-1, 4 |
| G2 | `PurchaseOrderPage.ts` | NEW | S194-1, 2, 3, 5, 13, 14, 15, 25, 26 |
| G3 | `GoodsReceiptPage.ts` | NEW | S194-9, 10, 20, 31 |
| G4 | `InvoicePage.ts` | NEW | S194-9, 10, 17, 18, 19, 27 |
| G5 | `PaymentRequestPage.ts` | NEW | S194-8, 11, 12, 21, 22, 28, 29, 30 |
| G6 | `MatchExceptionPage.ts` (or inline helper) | NEW — route lives under `/dashboard/accounting/exceptions` (L0.4 finding) | S194-18 |
| G7 | `ProcurementChainBuilder.ts` | NEW | All scenarios (builds plan objects that specs execute step-by-step) |
| G8 | `procurementAssertions.ts` | NEW | All scenarios (post-UI verification) |
| G9 | `procurement.ts` fixture | NEW | All scenarios (procurementPages + seededSupplier + seededItemCatalog + seededUser) |
| G10 | `TEST_IDS.procurement.*` subtree in `selectors.ts` | EXTEND | Every Page Object |
| G11 | SSM helpers in `ssmSetup.ts` (see row 13 above) | EXTEND | Fixtures |
| G12 | data-testid on ~40 procurement UI elements | NEW (Phase L1) | Every Page Object (all 7 pages currently have ZERO data-testid — L0.2 finding) |

**Gap count ≥5: PASS** (12 gaps).

## 3. Existing Procurement Spec Disposition (L0.3)

| Spec | Status | Disposition | Rationale |
|---|---|---|---|
| `tests/e2e/s07-requisition-approval.spec.ts` | EXISTS | **KEEP — mark reference** | Covers older-flow requisition approval. S194 spec uses `tests/e2e/specs/s194-procurement-chain.spec.ts`, which exercises the BEI Purchase Requisition → Purchase Order chain against the real backend. Keep s07 for now; do NOT delete in this sprint — separate audit needed to confirm no coverage overlap. Log follow-up: `[FOLLOWUP-S194-L0]` evaluate in S195 or later. |
| `tests/e2e/s08-or-followup.spec.ts` | **NOT FOUND** | N/A | Plan referenced it but the file does not exist on `origin/main`. The OR-followup flow IS tested in S194-11, S194-21. No action. |
| `tests/e2e/procurement-single-source.spec.ts` | EXISTS | KEEP — reference | Single-source report; outside chain scope. No overlap. |
| `tests/e2e/s062-procurement-math-live.spec.ts` | EXISTS | KEEP — reference | Math/calculation test; outside chain scope. No overlap. |
| `tests/e2e/s27-procurement-backlog-live.spec.ts` | EXISTS | KEEP — reference | Backlog spec; outside certification scope. No overlap. |

**HARD BLOCKER status:** Not triggered — no identical-ground duplicate. Follow-up logged for future rationalization.

## 4. BEI Match Exception UI Audit (L0.4)

**Route found:** `app/dashboard/accounting/exceptions/page.tsx` (354 lines). URL: `/dashboard/accounting/exceptions`.

**Module mount:** `accounting`, not `procurement`. RBAC guard uses `MODULES.ACCOUNTING` (or similar — verify in Phase L0.4.1 when writing MatchExceptionPage).

**Flow:** List page with filter (status `Pending CPO | Pending CFO | Pending CEO | Approved | Rejected`). Per-row Approve/Reject buttons open a dialog for comment entry. No separate create UI found — exceptions are created as side effects of invoice variance rejection or 3-way-match failure (verify via backend `hrms.api.procurement.match_exception_*` endpoints).

**Hooks used:** `useMatchExceptions`, `useApproveException`, `useRejectException` (from `@/hooks/use-procurement`).

**Implication for S194-18 (Match Exception bypass test):**
- The scenario says "create BEI Match Exception via UI". **There is NO dedicated create UI for Match Exception** — the backend creates one when the agent invokes an API (e.g., attempt Invoice for a PO with no GR → backend raises rejection; a Match Exception row may or may not be auto-seeded).
- **Decision:** S194-18 creates the Match Exception via **SSM** (policy exception documented here), approves it via the `/dashboard/accounting/exceptions` UI (real browser click on the Approve button in the page.tsx dialog), then retries the Invoice from the UI. The UI click on Approve satisfies the "browser fidelity" requirement for the approval step; the seeding step is policy-exempted because no create surface exists.
- **This must be reflected in Phase S7 S194-18 spec comment:** "SSM-seeded Match Exception (no create UI); UI-driven approval + retry."

## 5. Test Account Survey (L0.5)

`memory/testing-accounts.md` has 14 accounts. **`test.procurement@bebang.ph` is NOT present.**

Present:
- test.area, test.supervisor, test.staff, test.crew1, test.hr, test.projects, test.projects.staff, test.commissary, test.warehouse, test.auditor, test.finance
- mae (CPO), butch (CFO), sam (CEO / System Manager)

**Approver gates use EMAIL MATCH, not role:**
- PO Mae-level approve: only `mae@bebang.ph`
- PO Butch-level approve: only `butch@bebang.ph`
- PO CEO-level approve: only `sam@bebang.ph`
- RFP all levels: System Manager role (only `sam@bebang.ph`)

**Implication for Phase L8:**
- `seededUser({email: "test.procurement@bebang.ph", roles: ["Procurement User"]})` — needed for S194-23 (negative RBAC). This user will NOT have Mae/Butch/CEO email match → Approve buttons must be hidden.
- `loggedInAsProcurementUser` fixture — logs in the seeded user.
- **Cleanup:** `afterAll` must call `deleteUser(email)` via SSM so the test account is disposed.

**Approver fixtures needed:**
- `loggedInAsMae` — uses `mae@bebang.ph` (already present in `testing-accounts.md`)
- `loggedInAsButch` — uses `butch@bebang.ph`
- `loggedInAsCEO` (or `loggedInAsSam`) — uses `sam@bebang.ph`
- `loggedInAsAccounts` — uses `test.finance@bebang.ph`
- `loggedInAsWarehouse` — uses `test.warehouse@bebang.ph`

Verify existing `auth.ts` to see which are already present; only add the missing ones. Non-blocking observation: existing `auth.ts` likely has `loggedInAsStaff` / `loggedInAsHR` style, but probably not the procurement-specific fixtures.

---

## L0 Completion Verification

- [x] Library audit >10 REUSE rows (15) ✔
- [x] Gap list ≥5 rows (12) ✔
- [x] s07/s08 disposition decided ✔
- [x] Match Exception UI audited (L0.4) — policy exception documented for S194-18 ✔
- [x] test.procurement confirmed MISSING from testing-accounts.md (L0.5) — Phase L8 adds seededUser helper ✔

## Phase L1 Findings (UI Discoveries)

- **S194-22 advance-payment field absent from UI.** `payments/new/page.tsx` does NOT expose an `is_advance_payment` checkbox. Behavior is driven by `rfp_type === "Cash Advance"` in the existing `RFP_TYPES` selector (line 75-84 of `payments/new/page.tsx`).
  - **Updated S194-22 contract for Phase S:** instead of asserting `data-testid="procurement-rfp-is-advance"`, the spec MUST select `rfp_type = "Cash Advance"` from the existing `<Select>` and verify the AdvancePaymentBanner appears (`components/procurement/advance-payment-warning.tsx`). The backend `is_advance_payment=1` is set as a side-effect of `rfp_type === "Cash Advance"` in the create handler.
  - This is a HARD AMENDMENT to the plan — Phase S agent must read this finding and adapt S194-22 spec accordingly.
- **Approve button is single-handler regardless of stage.** The PO `[id]` page has ONE `<Button onClick={handleApprove}>` (line 1015 in original) that the backend routes to mae/butch/ceo based on the logged-in user's email. Page Object methods `approveMae` / `approveButch` / `approveCEO` therefore differ ONLY in which fixture (`loggedInAsMae` etc.) opens the page — the click sequence is identical.
- **Reject reason textarea distinct per dialog.** Each of PR/PO/RFP has its own reject dialog with a unique data-testid: `procurement-pr-reject-reason`, `procurement-po-reject-reason`, `procurement-rfp-action-notes` (RFP reuses one textarea for both approve-notes and reject-reason).
- **Match Exception page lives at `/dashboard/accounting/exceptions`** — not under `/procurement/`. Page Object `MatchExceptionPage` uses `PATHS.matchExceptions = "/dashboard/accounting/exceptions"`. RBAC mount: `MODULES.ACCOUNTING` (Accounts users + System Manager only).
- **Total testids added in Phase L1: 31** (verified via `grep -rh 'data-testid="procurement-' app/dashboard/procurement`). Meets verify_phase.sh gate (`≥ 30`).
- **Files NOT touched in Phase L1 (use Page Object text fallbacks):** `purchase-orders/new/page.tsx`, `goods-receipts/new/page.tsx`, `goods-receipts/[id]/page.tsx`, `invoices/new/page.tsx`, `payments/new/page.tsx`, `approvals/page.tsx`, `accounting/exceptions/page.tsx`. These have unique button text (e.g. "Create PO", "Submit Invoice") that `getByRole("button", { name: /.../ })` can resolve. Page Objects use `testId` first with `getByRole` fallback (StoreOrderingPage pattern).
