# S225 Phase 1 — Validation Decision (BLOCKER for Sam)

**Generated:** 2026-04-27 PHT
**Branch:** `s225-canonical-warehouse-cleanup-and-pattern-a-safeguard`

## Summary

Per the Phase 1 outcome decision matrix in the plan, the targeted L3 sweep result **≤4/6 PASS → STOP. Surface to Sam.**

However, the sweep failures are **not Pattern B or Pattern C errors** — they are the "S223 DEFECT-11 reappearance" pattern (order does not appear in approval queue) plus 2 browser-closed timeouts. **S224 deployment IS independently verified working via direct REST probes.**

This requires your judgement on whether to proceed with Phase 2 or pause to investigate the sweep failures.

## What we know works (S224 IS deployed and functioning)

### 1. Container code SHA check (`output/s225/verification/s224_deploy_sha_check.json`)

All 4 markers present in the deployed Docker container:

| Marker | Status |
|---|---|
| `already_approved` in `approve_material_request` | ✓ FOUND at warehouse.py:1254 |
| `current_status == "Ordered"` idempotency block | ✓ FOUND at warehouse.py:1250 |
| `Ambiguous store identifier` in `resolve_warehouse` | ✓ FOUND at store.py:301 |
| `S224: case-insensitive substring fallback` comment | ✓ FOUND at store.py:273 |

`apps/hrms` mtime: `1777207450 = 2026-04-26 13:24:10 PHT` (right after S224 PR merge at 12:42 UTC).

### 2. Pattern B REST probe (`output/s225/verification/s224_pattern_b_validation.json`)

- Found existing Ordered MR: `MAT-MR-2026-00135`
- Built `approved_items` from MR's actual items (audit B-6 fix)
- Called `approve_material_request()` as `test.scm@bebang.ph`
- Response: `{"success": True, "already_approved": True}` ✓

### 3. Pattern C REST probe (`output/s225/verification/s224_pattern_c_validation.json`)

- `resolve_warehouse("Estancia")` → `ORTIGAS ESTANCIA - BB ESTANCIA FOOD CORP.` ✓
- `resolve_warehouse("ESTANCIA")` → same ✓
- `resolve_warehouse("ortigas estancia")` → same ✓
- `resolve_warehouse("Bebang")` → throws "Ambiguous store identifier" with 5 candidates ✓

**Conclusion: S224 PR #687 is fully deployed and Pattern B + C fixes are operational against live production.**

## What failed (the targeted L3 sweep)

Sweep target: 6 stores via `--grep "ROBINSONS ANTIPOLO|ROBINSONS IMUS|AYALA FAIRVIEW TERRACES|AYALA UP TOWN CENTER|NAIA T3|ORTIGAS ESTANCIA"`.

Final tally:

| Store | Result | Failure mode |
|---|---|---|
| AYALA FAIRVIEW TERRACES | FAIL (both attempts) | `OrderApprovalPage.approve` — page closed before approval queue render. Then on retry: `ReceivingPage.accept` — accept-delivery-button never visible. |
| AYALA UP TOWN CENTER | FLAKY (passed on retry) | First attempt: `page.screenshot — Target page, context or browser has been closed`. Retry: PASSED. |
| NAIA T3 | FAIL (both attempts) | `Test timeout 60s` then on retry: "OrderApprovalPage.approve: order BEI-ORD-2026-00408 did not appear in the approval queue after 6 navigation attempts. **S223 DEFECT-11 fix should make this path visible**". |
| ORTIGAS ESTANCIA | FAIL (both attempts) | `Test timeout 60s` then on retry: same "S223 DEFECT-11" message for BEI-ORD-2026-00410. |
| ROBINSONS ANTIPOLO | FAIL (both attempts) | `Test timeout 60s` then on retry: same "S223 DEFECT-11" message for BEI-ORD-2026-00412. |
| ROBINSONS IMUS | FLAKY (passed on retry) | First attempt: same "S223 DEFECT-11" message for BEI-ORD-2026-00413. Retry: PASSED with auto-approval idempotency. |

**Pass count:** 2/6 (both flaky — passed on retry but failed on first attempt). 4/6 hard failed.

**Failure classification:**
- 0/6 failed for Pattern B reason ("already been approved")
- 0/6 failed for Pattern C reason ("Could not find Store: ...")
- 4/6 failed for the **S223 DEFECT-11 reappearance pattern**: order is created and area-approved, but does not appear in the SCM approval queue when the test navigates there
- 2/6 failed first attempt for browser/page lifecycle issues but passed on retry

The test message itself states: *"S223 DEFECT-11 fix should make this path visible — check date filter and backend get_order_review_queue."* The backend was supposed to surface these orders for SCM approval, but they're not appearing.

## What this means

S224 (Pattern B + Pattern C) is **deployed and working** — REST probes prove it directly against the live production code.

The sweep is detecting a **separate issue** related to S223 DEFECT-11 / `get_order_review_queue`. Possibilities:
1. S223 DEFECT-11 fix did not fully resolve the date filter / queue visibility problem
2. A new regression was introduced post-S223
3. The sweep auto-promotes orders past the approval state (because the BEI on_submit hook auto-promotes store-order MRs to "Ordered"), so by the time the test navigates to the SCM queue, the order is no longer in "needs approval" state

Possibility (3) is interesting — looking at the sweep log, we see lines like:

```
[OrderApprovalPage.approve] BEI-ORD-2026-00404 already approved (status=Approved); skipping UI click.
```

The Page Object recognizes the order is already approved (Pattern B working). But then the SECOND `.approve()` call (SCM stage) cannot find the order in the SCM queue — likely because it auto-promoted past the SCM step too.

**This is a real production behavior question, not a test bug.** It's the same root cause that S224 Pattern B addressed (auto-promotion creates idempotency requirements). The test infrastructure needs to handle this auto-promotion path explicitly.

## Decision required from Sam

Per plan literal (Phase 1 outcome matrix): ≤4/6 PASS → STOP, surface to Sam.

**Three options:**

**A) Trust the REST probes as primary deploy evidence; classify sweep failures as a separate finding; proceed to Phase 2 audit**
- Rationale: S224 deployment is verified independently. Sweep is supplementary "real user path" check that requires test-infra updates to handle the auto-promotion fully (a Page Object change to handle the case where the order skipped past SCM queue too).
- Risk: we don't have a clean L3 baseline for the cumulative S225 effect at Phase 6.
- Estimated cost: zero — proceed immediately.

**B) Pause to investigate sweep failures (likely test infra or a separate backend issue around `get_order_review_queue` for already-promoted orders)**
- Rationale: clean L3 baseline before mutating master data. The "S223 DEFECT-11 reappearance" message strongly suggests there's a real issue worth understanding before adding more change.
- Risk: defers the canonical warehouse cleanup (which has 648 stranded units of FG004 per S223 Sentry root-cause).
- Estimated cost: 30 min - 2 hours (probe `get_order_review_queue` for an auto-promoted order; either fix the Page Object or file a backend bug as separate sprint).

**C) Accept current state and proceed; document gap**
- Same as A but with explicit "we know the sweep is blocked" annotation in the closeout.

**My recommendation: Option A** — the REST probes are stronger evidence than the sweep for S224 specifically (they directly call the changed functions). The sweep failure is a separate concern about a different code path (`get_order_review_queue` for auto-promoted orders) that S225 doesn't touch. Filing it as S226 follow-up is appropriate.

If you choose A, I proceed immediately with Phase 2 (read-only canonical warehouse audit) and stop again at the Phase 2→3 gate (Sam approval token on the audit PR).

If you choose B or C, please tell me which.

## Evidence files

- `output/s225/verification/s224_deploy_sha_check.json` — container code grep
- `output/s225/verification/s224_pattern_b_validation.json` — REST probe (PASS)
- `output/s225/verification/s224_pattern_c_validation.json` — REST probe (PASS)
- `output/l3/s225/sweep_ledger.json` — full ledger of test docs created/cancelled
- `tmp/s225/s224_targeted_sweep.log` — full Playwright output (verbose)
