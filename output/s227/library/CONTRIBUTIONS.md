# S227 Library Contributions (Phase 0.3)

This sprint contributes the following reusable artifacts to `bei-tasks/tests/e2e/`.
Each is owned by S227; future sprints are consumers and extenders, not co-owners.

| # | Artifact | Path | Purpose |
|---|---|---|---|
| 1 | Fixture | `tests/e2e/fixtures/storePartner.ts` (new file) — exports `test` extending base with `loggedInAsStorePartner` | Reusable login-as-partner fixture for any future spec testing partner-scoped surfaces. |
| 2 | Helper | `tests/e2e/support/buildPartnerWithStores.ts` | Builder: creates `Store Partner` user + N `BEI Sales Dashboard Store Access` rows in one call, returns a cleanup token. Idempotent. |
| 3 | Cleanup ledger kinds | `tests/e2e/fixtures/cleanup.ts` (extend) | Add `sales-dashboard-store-access-create`, `user-create-store-partner` to `CleanupKind` union; add reverse handlers to walk ledger backward at `afterEach`. |
| 4 | SSM helpers | `tests/e2e/support/ssmSetup.ts` (extend) | `seedSalesDashboardStoreAccess({user, warehouse, notes})` + `deleteSalesDashboardStoreAccess({user, warehouse})`. |
| 5 | Page Object | `tests/e2e/pages/AnalyticsSalesPage.ts` (new file) | Wraps `/dashboard/analytics/sales`; exposes `gotoDefault()`, `pickStore(name)`, `assertPartnerView()`, `assertNoLeaderboardLeak()`, `assertOpenFullLeaderboardCTAHidden()`. |
| 6 | Page Object | `tests/e2e/pages/AnalyticsProductPage.ts` (new file) | Wraps `/dashboard/analytics/product`; exposes `gotoDefault()`, `pickStore(name)`, `assertPartnerView()`, `assertFleetRankColumnHidden()`, `assertGapCardHidden()`, `assertDrilldownDisabled()`, `downloadCsvAndAssertHeaders()`. |
| 7 | Assertion helper | `tests/e2e/assertions/assertNoFleetLeak.ts` (new file) | `assertNoFleetLeakOnPage(page, {knownThirdPartyStoreNames})`: checks DOM has no `analytics-product-fleet-rank-cell` / `analytics-product-assortment-gap-card`, AND no third-party store name from a hardcoded fleet sample (e.g., "BGC", "ORTIGAS GREENHILLS"). Reusable for any partner-scoped page audit. |
| 8 | Test account constant | `tests/e2e/support/session.ts` (extend `USERS`) | Add `USERS.partner = "test.partner.s227@bebang.ph"`. |

## Test scenarios that consume these artifacts (Phase 5)

`tests/e2e/specs/s227-store-partner-analytics.spec.ts` exercises the 12 L3 scenarios documented
in the plan §"L3 Workflow Scenarios" using the artifacts above. Per QA library discipline:
- Workflow steps: real-browser interactions only (clicks, picker selection, navigation).
- Setup: SSM-via-helper allowed (seeds + reverse cleanup).
- Verification: SSM probes allowed for response-shape JSON capture.
- No `page.request.*` / no raw `fetch()` in workflow steps.

## Library improvements predicted (NOT firm commitments)

If during Phase 5 we hit Mode C (brittleness) on `>=3` separate selectors, we'll emit
`output/s227/library/LIBRARY_IMPROVEMENTS.md` per `qa-test-library-discipline.md`.
At plan time we expect `0` Mode C fixes — partner UI is small, conditional render is binary
(field present or absent), no flaky modal interaction is expected.
