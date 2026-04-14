# S192 Library Audit — `bei-tasks/tests/e2e/`

**Audit date:** 2026-04-14
**Scope:** Identify what Page Objects / fixtures / builders / assertions already exist before extracting the S192 library.

## Existing Structure

```
tests/e2e/
├── 83 .spec.ts files (flat, mostly copy-pasted)
├── inventory/ (scenario folder)
├── mapping-contract/ (scenario folder)
└── support/
    ├── session.ts          (156 LOC — login, USERS, BASE_URL, fetch helpers) ← REUSE
    ├── s027.ts             (224 LOC — S027-specific setup)
    └── local-verification.ts (154 LOC — assertion helpers)
```

**No `pages/`, `fixtures/`, `builders/`, `assertions/` directories exist.** Phase L is a greenfield build.

## Extract-Worthy Patterns (from `support/session.ts`)

- `BASE_URL`, `HQ_URL`, `PASSWORD` constants — KEEP, import into library.
- `USERS` dict with env override — KEEP.
- `login(page, email, password)` — KEEP as private of `LoginPage.loginAs()`.
- `gotoProtectedRoute(page, email, route)` — KEEP, absorb into `BasePage.gotoProtected()`.
- `uniqueId(prefix)` — KEEP in `builders/`.

## Richest Existing Spec (Baseline for Comparison)

`live-store-ordering-l3-l4.spec.ts` — 510 LOC. Uses `page.request.post('/api/method/...')` for workflow operations (VIOLATES HB-4). This is the anti-pattern S192 replaces with browser-only drive via Page Objects.

## Phase L Gap Map (what we'll build)

| Missing | Where | Consumes |
|---------|-------|----------|
| `pages/BasePage.ts` | new | `support/session.ts` helpers |
| `pages/LoginPage.ts` | new | `login()` from session.ts |
| `pages/StoreOrderingPage.ts` | new | `BasePage` |
| `pages/OrderApprovalPage.ts` | new | `BasePage` |
| `pages/DispatchPage.ts` | new | `BasePage` |
| `pages/ReceivingPage.ts` | new | `BasePage` |
| `fixtures/auth.ts` | new | `LoginPage` + `storageState` |
| `fixtures/cleanup.ts` | new | `CleanupLedger` class |
| `fixtures/seed.ts` | new | SSM via `support/ssmSetup.ts` |
| `fixtures/evidence.ts` | new | Playwright video/HAR recording |
| `builders/OrderBuilder.ts` | new | — |
| `builders/UserBuilder.ts` | new | — |
| `assertions/orderAssertions.ts` | new | `support/frappeReadback.ts` |
| `assertions/billingAssertions.ts` | new | `support/frappeReadback.ts` |
| `support/selectors.ts` (TEST_IDS) | new | — |
| `support/frappeReadback.ts` | new | HQ API auth |
| `support/ssmSetup.ts` | new | AWS SSM |
| `support/paths.ts` | new | — |

## `data-testid` Strategy

Plan calls for `data-testid` attributes on components. Strategy:
1. Write `TEST_IDS` constant with stable names first.
2. Survey `bei-tasks/app/dashboard/{store-ops,scm,warehouse,commissary}/` for ordering/approval/dispatch/receiving components.
3. Add `data-testid={TEST_IDS.X}` to identified controls in the same PR.
4. Library Page Objects use `page.getByTestId(TEST_IDS.X)` with role-based fallback for buttons.

## Legacy Consolidation (DEFERRED)

Not deleting old `*.spec.ts` in this sprint. Migration flagged in `output/l3/s192/LIBRARY_MIGRATION_NOTE.md` for a future consolidation sprint.
