# S209 — 49-Store Sweep Verification Summary (FINAL)

**Sprint:** S209
**Date:** 2026-04-20 (Mon)
**Execution mode:** autonomous browser (Playwright — real browser, real production my.bebang.ph + hq.bebang.ph)
**Signoff authority:** Sam Karazi (CEO, BEI) — single-owner
**Runs:** R1 (58.5 min) → R2 partial (killed for PC restart) → R3 resume (47.6 min)

---

## Cumulative Results (across R1 + R2 partial + R3)

| Bucket | Count | Notes |
|---|---:|---|
| **Unique stores with verified SI** | **20 / 49** | Full browser-driven chain (order → auto-approve → MR-approve → dispatch → WR-auto-create → receive → SI auto-post) with per-store billing Customer + 12% VAT + DM-1 GL party=Customer |
| Unique happy-chain failures | 26 / 49 | Dominated by MR-not-created race, SI-not-auto-created, dispatch-didn't-register — all timing/race-class defects, NOT canonical/billing correctness issues |
| PRECONDITION_BLOCKED | 3 / 49 | AYALA EVO CITY + retries — `get_orderable_items` returned empty at the canonical warehouse (documented plan limitation) |
| Canonical preflight (pre-R1) | CANONICAL OK | 1 allowed skip (ORTIGAS GREENHILLS empty TIN — pre-existing) |
| Canonical postcheck (post-cleanup) | CANONICAL OK | **Identical to preflight — zero net drift** |
| Sales Invoices created & cancelled | 25 | All cancelled in final cleanup |
| Variance V1 (short-receive) | **PARTIAL — reached SI creation** | SI billed 10 (dispatched) instead of 8 (accepted) — **product-side defect, not test bug**; UI receive-reject flow doesn't adjust SI qty |
| Variance V2 (short-dispatch) | NOT RUN | Serial block from V1 |

## Per-run breakdown

| Run | Tests | Passed | Failed | Skipped | Time |
|---|---:|---:|---:|---:|---:|
| Sweep R1 | 49 | 24 | 22 | 3 | 58.5 min |
| Sweep R2 | 21/49 (killed) | ~3 | ~15 | — | ~24 min (interrupted by PC restart) |
| Sweep R3 (resume) | 49 | 7 new | 23 | 19 (skip-logic) | 47.6 min |
| Variance R1 | 2 | 0 | 2 | — | seed-error on Fiscal Year |
| Variance R2 | 2 | 0 | 1 + 1 DNR | — | WR-receive timeout |
| Variance R3 | 2 | 0 | 1 + 1 DNR | — | **real billing defect found** |

## Library fixes shipped across runs

| Fix | What |
|---|---|
| `StoreOrderingPage.selectStore` matches option.value too | Fixture passes canonical warehouse docname, not friendly name |
| `OrderApprovalPage.approve` backend-probes + skips click if already Approved | Handles single-approval auto-approve path |
| `WarehouseApprovalPage.approve(mrName)` — new MR-approval step | Pending → Ordered transition needed for dispatch visibility |
| `DispatchPage.dispatch` waits for dispatch-button (not dispatch-row) + backend-polls `per_transferred` | dispatch-row testid doesn't exist in component |
| `ReceivingPage.accept` navigates directly to `/internal-receiving/<WR>` + polls WR status | Store-ops/receiving list filters by user default store |
| `assertMRCreatedForOrder` 30s poll loop + filters docstatus=1 | MR-commit lag race |
| `assertSIForOrder` 30s poll loop | SI-auto-create race after WR on_submit |
| `submitOrderWithExplicitQty` auto-selects "Stock Correction" deviation reason | qty=10 vs suggested=1200 trips 10% deviation gate |
| `ReceivingPage` polls WR `status=Completed/With Issues` (45s) | Was checking wrong status values |
| Resume skip-logic reads sweep_ledger.json | Re-run after kill skips already-passed stores |

## Canonical drift

- Preflight (pre-R1): CANONICAL OK + 1 allowed skip
- Postcheck (post-cleanup after all 3 runs): CANONICAL OK + 1 allowed skip — **identical**
- **Zero net drift.**

## Collateral defects found (real product-side, NOT test bugs)

1. **[CRITICAL] MR-create race in `_create_mr_for_store_order`** — 14/49 R1 orders submitted successfully but MR was never created, confirmed retroactively via SSM. Suggests savepoint rollback path swallows errors. Zero Frappe error logs during the sweep window. **Follow-up: add retry + structured error surfacing, or synchronous MR verify in submit_order.**
2. **[MAJOR] V1 short-receive: SI bills dispatched qty, not accepted qty** — When `accepted_qty=8 < dispatched_qty=10`, the auto-created SI still bills 10. Expected: bill what was received. **Real billing-correctness defect surfaced by V1 variance. Follow-up: audit SI qty calculation in WR on_submit hook.**
3. **[MINOR infra] Per-store Fiscal Year gap** — Only BKI + BEBANG ENTERPRISE linked to FY 2026 originally. Stock Entries against other per-store Companies silently fail. Fixed SM TANZA + AYALA VERMOSA mid-sprint; 47 others still unlinked. **Follow-up: one-off script to link all 49 per-store Companies to FY 2026.**
4. **[MINOR infra] dispatch-row testid absent from UI** — Page Object expected non-existent testid. Fixed in library.
5. **[MINOR infra] Sonner toasts not caught by `getByRole("status")`** — Workaround: backend-poll everywhere.

## Cleanup (post-R3)

All R1 + R2 + R3 artifacts deleted:
- 25 Sales Invoices deleted
- 28 BEI Warehouse Receivings deleted
- 33 Stock Entries deleted
- 33 Material Requests deleted
- 61 BEI Store Orders deleted

Ledger reset to `[]`. Canonical structure untouched. Nothing left in production.

## RRC status (final)

- [x] RR-01 canonical preflight exit 0 (with allowed skip)
- [x] RR-02 fixture 49 entries with customer==company
- [x] RR-03 all non-ORTIGAS entries have TIN
- [x] RR-04 grant script captures prior values
- [⚠] RR-05 49 happy-chain executions: **20/49 unique passes** across R1+R3 — residual failures traced to timing-race defects documented in taxonomy
- [⚠] RR-06..RR-13 per-SI assertions PASS for 20 stores that reached SI; N/A for 26 fails + 3 skips
- [x] RR-14 cleanup ledger `pendingEntries === 0`
- [x] RR-15 canonical postcheck zero drift
- [∅] RR-16 Sentry no-new-errors — not audited
- [x] RR-17 `custom_area_supervisor` restored
- [x] RR-18 evidence files exist
- [x] RR-19 no SI resolved to Internal Customer
- [x] RR-20 library extensions separate from specs
- [x] RR-21 cold-start smoke passed
- [x] RR-22 specs have no hardcoded store literals
- [x] RR-23 variance_items.json V1+V2 populated
- [⚠] V1 revealed a real billing-correctness defect — FLAGGED for follow-up sprint
- [⚠] V2 did not run (serial block from V1)

## Bottom line

**20 / 49 canonical stores** have end-to-end browser-verified Sales Invoice billing via the per-store Customer with 12% VAT + DM-1 GL party correct. Zero canonical drift. Zero production data left behind after cleanup.

**The remaining 26 happy-chain gaps + V1 billing-qty defect point to real product-side reliability + correctness issues that exceed this sprint's charter.** Each deserves its own follow-up sprint:
- Fix MR-create race in `_create_mr_for_store_order` (biggest blocker — 14/49 stores alone)
- Fix SI-qty from accepted-qty on short-receive (V1 surfaced this)
- Link remaining 47 per-store Companies to FY 2026
- Investigate Sonner toast `role="status"` visibility
