# S253 Library Audit
**Date:** 2026-05-21
**Reference:** `.claude/docs/qa-test-library-discipline.md`

## Existing Page Objects + fixtures S253 reuses READ-ONLY

| Asset | Location | S253 use |
|---|---|---|
| `StoreOrderingPage` | `tests/e2e/pages/StoreOrderingPage.ts` | order submission (Phase 2 base chain) |
| `StoreOrderingPage.submitOrderWithExplicitQty` | same file lines 391-441 | **Phase 4.1** multi-item (REPLACES the proposed `submitOrderWithExactItems`) |
| `OrderApprovalPage` | `tests/e2e/pages/OrderApprovalPage.ts` | dual-approval (Phase 2 base chain) |
| `DispatchPage` | `tests/e2e/pages/DispatchPage.ts` | dispatch (Phase 2 base chain) |
| `DispatchPage.dispatch({qtyOverrides})` | same file | **Phase 4.5** partial fulfillment (REPLACES proposed `dispatchPartial`) |
| `WarehouseApprovalPage` | `tests/e2e/pages/WarehouseApprovalPage.ts` | MR approval (Phase 2 base chain) |
| `ReceivingPage` | `tests/e2e/pages/ReceivingPage.ts` | receive (Phase 2 base chain) — EXTEND with `rejectAll` for Phase 4.6 |
| `loggedInAreaSupervisor` | `fixtures/auth.ts` | order submit |
| `loggedInSCM` | `fixtures/auth.ts` | dual-approve + dispatch |
| `loggedInStoreSupervisor` | `fixtures/auth.ts` | receive |
| `loggedInDeskAdmin` (NEW P0.10) | `fixtures/auth.ts` | Phase 2 + Phase 3 Frappe Desk submit/cancel |
| `CleanupLedger` | `fixtures/cleanup.ts` | docs tracking for teardown |
| `frappeReadback.readDoc / queryDocs / waitForDocStatus` | `support/frappeReadback.ts` | read-only API verification |

## NEW S253 library contributions

| Asset | Location (to create) | Phase | Purpose |
|---|---|---|---|
| `loggedInDeskAdmin` fixture | `fixtures/auth.ts` (**DONE in P0.10**) | 0 | Separate BrowserContext for hq.bebang.ph Administrator |
| `FrappeDeskSubmitPage` | `tests/e2e/pages/FrappeDeskSubmitPage.ts` | 2 | submitPurchaseInvoice + submitStockEntry |
| `SICancelPage` | `tests/e2e/pages/SICancelPage.ts` | 3 | cancelSalesInvoice |
| `glAssertions.ts` | `tests/e2e/assertions/glAssertions.ts` | 2, 3 | `assertPairedDocGLChain` (5 buyer-side rows), `assertCancelCascadeOrder` (SE-first), `assertPairedDocsAfterSICancel` (PI asymmetry-aware) |
| `ReceivingPage.rejectAll` extension | extend existing file | 4 | reject all line items on WR |

## REJECTED — proposed but duplicates existing

- ❌ `submitOrderWithExactItems` — `submitOrderWithExplicitQty` already exists with identical signature
- ❌ `dispatchPartial` — `dispatch({qtyOverrides: Map})` already supports this

## CleanupLedger API note

`CleanupLedger` exposes: `record()`, `reverse()`, `entriesSnapshot()`, `load()`. There is NO `pendingEntries` property. Use `cleanupLedger.entriesSnapshot().length === 0` if a TypeScript-level pending count check is needed.

## qa-test-library-discipline compliance

- ✅ Library-first: extends existing Page Objects, only adds 3 new (FrappeDeskSubmitPage, SICancelPage, glAssertions) + 1 fixture (loggedInDeskAdmin)
- ✅ Real-browser only for workflow ops: NO `page.request.*` or `fetch()` in workflow sections; read-only API allowed for verification
- ✅ Cleanup via `cleanupLedger` fixture
- ✅ Three-uses rule: GL assertion pattern used in Phase 2 + Phase 5 sweep — extracted to `glAssertions.ts`
- ✅ `data-testid` everywhere: Frappe Desk standard buttons use `getByRole("button", {name: ...})` (Frappe Desk doesn't expose `data-testid`); acceptable carve-out
