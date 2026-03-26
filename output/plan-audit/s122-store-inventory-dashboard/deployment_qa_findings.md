# S122 Deployment & QA Audit Findings
**Sprint:** S122 — Store Inventory Dashboard (bei-tasks, Vercel)
**Audited:** 2026-03-25
**Auditor:** Deployment & QA Engineer (subagent)
**Verdict:** NO-GO (6 blocking gaps, 4 advisory gaps)

---

## BLOCKING GAPS (must fix before execution)

### B1 — Vercel Deploy Trigger Underspecified
**Issue:** The plan states "PR to main → auto-deploy" but does not specify:
- Whether this is a Preview deploy (PR open) or Production deploy (PR merged to main).
- Vercel auto-deploys **previews** on PR open, and **production** only on merge to the default branch.
- The plan must distinguish: (a) PR open → preview URL for L3 testing, (b) PR merged → production promotion.
**Required fix:** Explicitly state "Open PR against main → Vercel Preview URL used for all L3 testing. Merge PR → Production promotion. Do NOT merge until all L3 scenarios pass on Preview URL."

### B2 — L3 Scenarios Cover Mobile Only; Desktop Table Layout Untested
**Issue:** All 10 defined L3 scenarios appear to exercise the mobile card layout. The dashboard almost certainly has a responsive breakpoint that switches to a table layout on desktop (md/lg breakpoints). No scenario covers:
- Desktop viewport (1280px+) — table columns rendering correctly
- Column overflow / horizontal scroll on narrow laptop (1024px)
- Sticky header behavior in table mode
**Required fix:** Add at minimum 2 L3 scenarios: one at 1280px viewport (full desktop table), one at 1024px (laptop edge case).

### B3 — No Error State / API-Down Scenarios
**Issue:** Zero L3 scenarios cover degraded states:
- `useWarehouseStock` hook returns network error (API down / 5xx)
- Empty store (stock data returns 0 items, not null — different rendering path)
- Partial data (some items have no demand data, others do)
- Slow response (loading skeleton persists >5s)
**Required fix:** Add minimum 3 L3 error-state scenarios: (a) API failure → error banner shown, (b) empty store → empty-state UI shown, (c) items with null demand data → graceful fallback rendering (no crash, no NaN%).

### B4 — Area Supervisor with 0 Stores Assigned: Behavior Undefined
**Issue:** The plan defines AS-scoped views but does not specify the zero-store edge case:
- What does the dashboard render for an AS with no store assignments?
- Is this a blank page, a "no stores assigned" message, or a redirect?
- This is a real operational scenario (new AS accounts before store mapping is complete).
**Required fix:** Define expected behavior, add 1 L3 scenario covering AS with 0 stores, verify the component does not crash or show a misleading empty inventory table.

### B5 — `useWarehouseStock` Demand Data Assumption Unverified
**Issue:** The plan states "No new backend APIs" and implies `useWarehouseStock` already surfaces demand data. This is unverified. Specific risks:
- The hook may return stock-on-hand only (quantity), with no demand/reorder signal.
- Demand data may live in a separate endpoint not yet hooked up.
- If demand data is absent, any percentage-of-demand columns will render as NaN or crash.
**Required fix:** Before sprint execution, engineer must read the current `useWarehouseStock` return shape, confirm demand fields exist (or explicitly decide to omit demand columns from S122 scope), and document the confirmed fields in the sprint plan. This is a pre-condition gate, not a during-sprint discovery.

### B6 — Evidence File Repository Unspecified
**Issue:** The plan commits evidence to `output/l3/S122/` but does not state which repo receives these files:
- If bei-tasks: the output directory must exist and be gitignored or committed intentionally. Screenshots in a Next.js repo need a decision.
- If BEI-ERP: the plan references bei-tasks code but evidence lands in a different repo — cross-repo traceability breaks.
- Neither option is stated.
**Required fix:** Explicitly state: "Evidence files (screenshots, JSON payloads) are committed to `[bei-tasks OR BEI-ERP]/output/l3/S122/`. `.gitignore` amended if binary screenshots are excluded."

---

## ADVISORY GAPS (fix before merge, not blocking sprint start)

### A1 — Governor Flow Clarification (Informational)
The plan correctly targets Vercel auto-deploy (not bei-governor). This is correct for bei-tasks. No action required, but the plan should contain an explicit note: "bei-governor does NOT apply to this sprint. Vercel handles CI/CD via GitHub integration. Rollback = revert PR merge on GitHub."

### A2 — Rollback Procedure Incomplete
"Rollback = revert PR" is correct but underspecified. State the exact sequence:
1. `gh pr revert <PR-number>` or GitHub UI revert
2. Confirm Vercel re-deploys the reverted commit automatically
3. Smoke-test the production URL after revert completes
Without step 3, a silent Vercel build failure after revert goes undetected.

### A3 — No L3 Coverage for Pagination / Large Store
If a store has >50 SKUs, pagination or infinite scroll may trigger. No scenario tests this. Low priority but worth noting for stores like Paranaque or Alabang which may have large SKU counts.

### A4 — No L3 Coverage for Permission Boundary (Store Manager vs AS)
Only one role boundary is implied. A Store Manager should NOT see other stores. Confirm a Store Manager L3 scenario explicitly tests that cross-store data is inaccessible (not just hidden from UI, but API call also scoped).

---

## SUMMARY TABLE

| # | Finding | Type | Severity |
|---|---------|------|----------|
| B1 | Vercel deploy trigger (preview vs production) underspecified | Deploy | BLOCKING |
| B2 | Desktop table layout untested (mobile-only L3) | L3 Coverage | BLOCKING |
| B3 | No error state / API-down / empty store L3 scenarios | L3 Coverage | BLOCKING |
| B4 | AS with 0 stores — behavior undefined, no L3 | L3 Edge Case | BLOCKING |
| B5 | `useWarehouseStock` demand data shape unverified | Pre-condition | BLOCKING |
| B6 | Evidence file target repo unspecified | Evidence | BLOCKING |
| A1 | Governor flow clarification (already correct, just unstated) | Advisory | LOW |
| A2 | Rollback procedure incomplete (missing smoke-test step) | Deploy | ADVISORY |
| A3 | No L3 for pagination / large-SKU store | L3 Coverage | ADVISORY |
| A4 | No L3 for Store Manager cross-store permission boundary | L3 Edge Case | ADVISORY |

---

## REQUIRED ACTIONS BEFORE GO

1. Amend plan: distinguish Preview deploy (L3 testing) from Production deploy (post-merge).
2. Add 2 L3 scenarios: desktop 1280px table layout, laptop 1024px edge case.
3. Add 3 L3 error-state scenarios: API down, empty store, null demand data.
4. Add 1 L3 scenario: AS with 0 stores assigned.
5. Engineer reads `useWarehouseStock` return shape NOW and documents confirmed fields in plan.
6. Specify evidence file repo and `.gitignore` handling.
7. Expand rollback procedure to include post-revert smoke-test step.

**Minimum to achieve GO:** Items 1–6 (B1–B6). Item 7 (A2) strongly recommended.
