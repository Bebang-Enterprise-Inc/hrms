# S227 Library Audit (Phase 0.1 + 0.2)

Recorded against `bei-tasks/tests/e2e/` at sprint start (origin/main = `31fa4707`).

## Page Objects (existing in `tests/e2e/pages/`)

| Page Object | Exists? | Covers what | Gap for S227 |
|---|---|---|---|
| `BasePage.ts` | YES | Generic page primitives (waits, navigation, screenshot capture) | none — base will be reused |
| `LoginPage.ts` | YES | Login flow, `loginAs(email, password)` | none — used directly by `loggedInAsStorePartner` |
| `DispatchPage.ts` | YES | Commissary dispatch | irrelevant |
| `GoodsReceiptPage.ts` | YES | Procurement GR | irrelevant |
| `InvoicePage.ts` | YES | Procurement invoice | irrelevant |
| `MatchExceptionPage.ts` | YES | 3-way match exceptions | irrelevant |
| `OrderApprovalPage.ts` | YES | Procurement approval queue | irrelevant |
| `PaymentRequestPage.ts` | YES | RFP/payment request | irrelevant |
| `PurchaseOrderPage.ts` | YES | PO creation/approval | irrelevant |
| `PurchaseRequisitionPage.ts` | YES | PR flow | irrelevant |
| `ReceivingPage.ts` | YES | Warehouse receiving | irrelevant |
| `ReceivingQueuePage.ts` | YES | Warehouse queue | irrelevant |
| `StoreOrderingPage.ts` | YES | Store ordering | irrelevant |
| `WarehouseApprovalPage.ts` | YES | Warehouse approval | irrelevant |
| `AnalyticsSalesPage.ts` | **MISSING** | (would cover `/dashboard/analytics/sales`) | **NEW — required for S227** |
| `AnalyticsProductPage.ts` | **MISSING** | (would cover `/dashboard/analytics/product`) | **NEW — required for S227** |

## Fixtures (existing in `tests/e2e/fixtures/`)

| Fixture | Exists? | Reuse / Extend / New |
|---|---|---|
| `loggedInAreaSupervisor` (auth.ts) | YES | `[REUSE]` — needed for negative regression scenario (assert fleet keys ARE present for non-partner) |
| `loggedInSCM` | YES | irrelevant |
| `loggedInStoreSupervisor` | YES | irrelevant for partner test, but useful as comparison |
| `loggedInAsMae` / `loggedInAsButch` / `loggedInAsCEO` | YES | irrelevant |
| `loggedInAsAccounts` / `loggedInAsWarehouse` / `loggedInAsProcurementUser` | YES | irrelevant |
| `loggedInAsStorePartner` | **MISSING** | **`[NEW]` — Phase 5 task 5.2** |
| `seedSalesDashboardStoreAccess` | **MISSING** | **`[NEW]` — Phase 5 task 5.2 (seed + cleanup-ledger reverse handler)** |
| `cleanup` (cleanup.ts) | YES | `[EXTEND]` — add `"sales-dashboard-store-access-create"` and `"user-role-added-store-partner"` cleanup kinds |
| `seed` (seed.ts) | YES | `[REUSE]` — existing seed primitives |
| `evidence` (evidence.ts) | YES | `[REUSE]` — for capturing form_submissions / api_mutations / state_verification JSON |

## Assertions (existing in `tests/e2e/assertions/`)

| Assertion helper | Exists? | Gap for S227 |
|---|---|---|
| `billingAssertions.ts` | YES | irrelevant |
| `inventoryAssertions.ts` | YES | irrelevant |
| `notificationAssertions.ts` | YES | irrelevant |
| `orderAssertions.ts` | YES | irrelevant |
| `procurementAssertions.ts` | YES | irrelevant |
| `assertNoFleetLeak` (analytics) | **MISSING** | **`[NEW]` — Phase 5 task 5.3** |

## Support helpers (existing in `tests/e2e/support/`)

| Helper | Exists? | Reuse / Extend / New |
|---|---|---|
| `session.ts` (USERS, PASSWORD, PASSWORDS) | YES | `[EXTEND]` — add `USERS.partner = "test.partner.s227@bebang.ph"` |
| `ssmSetup.ts` | YES | `[EXTEND]` — add `seedSalesDashboardStoreAccess`, `deleteSalesDashboardStoreAccess` |
| `frappeReadback.ts` | YES | `[REUSE]` — used to verify access rows seeded |
| `selectors.ts` | YES | `[REUSE]` — declare partner-specific data-testid constants |
| `paths.ts` | YES | `[REUSE]` |

## data-testid coverage on partner-facing components (Phase 0.4)

Searched both `app/dashboard/analytics/sales/` and `app/dashboard/analytics/product/` for `data-testid="analytics-`:
- **Result: zero matches in either directory.**
- L3 assertions need `analytics-sales-leaderboard`, `analytics-product-fleet-rank-cell`, `analytics-product-fleet-rank-header`, `analytics-product-assortment-gap-card`, `analytics-sales-discount-rankings-card`, `analytics-sales-open-full-leaderboard-cta`.
- **Phase 4 task 4.7 will add all 6 testids.** Without them, Phase 5 must rely on text-content matching (brittle); with them, Phase 5 can use `getByTestId()` and `expect(...).not.toBeVisible()` cleanly.

## Worktree state at audit time

| Repo | Worktree | Branch | Base SHA |
|---|---|---|---|
| hrms | `F:/Dropbox/Projects/BEI-ERP-s227-store-partner-analytics` | `s227-store-partner-analytics` | `7eea6f7dc` (origin/production) |
| bei-tasks | `F:/Dropbox/Projects/bei-tasks-s227-store-partner-analytics` | `s227-store-partner-analytics` | `31fa47074` (origin/main) |

Both worktrees `git status --short` clean at audit time.
