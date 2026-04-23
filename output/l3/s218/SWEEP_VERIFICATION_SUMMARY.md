# S218 — L3 Sweep Iteration #4 (post-DEFECT-10/11 test-side fixes)

**Sprint:** S218 — qty cap 20→5 + input visibility timeout 8s→30s
**Status:** COMPLETED — NO IMPROVEMENT over S217
**Sweep date:** 2026-04-22 (Wednesday) PHT
**Wallclock:** 55.2 min

---

## Bottom line

**31/49 PASS (63%)** — identical to S217. My DEFECT-10/-11 fixes (qty cap 20→5, input visibility timeout 8s→30s) did not move the needle. Real root causes surfaced in this run are different from my hypothesis: failures cluster at the **order approval UI visibility** step, not the item-qty hydration step.

## Progression (no change from S217)

| Sprint | Pass | % |
|---|---|---|
| S209 baseline | 20/49 | 41% |
| S217 R1 | 31/49 | 63% |
| **S218 R1** | **31/49** | **63%** (no change) |

## What actually changed

- Pass list 30/31 identical to S217
- 1 swap: SM SOUTHMALL (S217 FAIL → S218 PASS), AYALA MARKET MARKET (S217 PASS → S218 FAIL)
- Net zero movement

## Why the fix didn't help

### DEFECT-10 was a misdiagnosis

I assumed `locator.waitFor: Timeout 30000ms exceeded` was the item-qty input hydration timeout. Trace inspection of S218 log shows the real line:

```
at pages\OrderApprovalPage.ts:26
  > 26 |     await byText.waitFor({ state: "visible", timeout: 30_000 });
```

The timeout is on `OrderApprovalPage.openOrder` — waiting for the order ID text to be visible on the approval list. 4 stores consistently hit this (FESTIVAL MALL, MEGAWIDE PITX, MEGAWORLD VENICE, NAIA T3). Extending the item-qty timeout had zero impact because the failure was at a different locator.

### Real root cause: auto-approved orders disappear from approval list

Backend probe of failing stores shows two patterns:

**Pattern A — Already Approved** (SM BICUTAN, SM GRAND CENTRAL, SM MARIKINA):
- `status=Approved`, `approved_at` populated ~10s after creation
- The OrderApprovalPage backend-probe check for "already Approved" runs too early (before the auto-approval timestamp is committed)
- Test falls through to UI loop; UI only shows "Pending Approval" → list empty for this order → final openOrder times out
- BUT — these actually got past approval eventually (I see wr-create + si-create in ledger for some)

Wait — re-checking the ledger for S218:
- SM BICUTAN: has `order-create`, probably failed dispatch (DEFECT-8)
- SM GRAND CENTRAL: similar

So Pattern A-ish failures are actually DEFECT-8 dispatch issues, NOT approval issues.

**Pattern B — Stuck at "Pending Approval"** (ORTIGAS ESTANCIA, ROBINSONS ANTIPOLO, SM STA. ROSA):
- `status=Pending Approval`, `approved_by=null`, `approved_at=null`
- `approval_stage=Single Approval` but submit didn't auto-approve
- test.area IS the area supervisor (per s209_grant_test_area_access snapshot)
- UNKNOWN why auto-approve didn't fire for these specific stores

**DEFECT-10 correct form (4 stores — FESTIVAL MALL et al):**
- Order created with status still Pending AND test.area can't find the order text in approval UI
- Likely same Pattern B — auto-approve didn't fire AND UI filters don't show the order

## Failure breakdown after S218

| Class | Count | Stores |
|---|---|---|
| **DEFECT-8 dispatch-not-registered** (3) | AYALA SOLENAD, AYALA VERMOSA, CTTM TOMAS MORATO |
| **DEFECT-11 approval-not-auto-firing** (7) | FESTIVAL MALL, MEGAWIDE PITX, MEGAWORLD VENICE, NAIA T3, ORTIGAS ESTANCIA, ROBINSONS ANTIPOLO, SM STA. ROSA |
| **DEFECT-8-ish dispatch-not-registered** (3) | SM BICUTAN, SM GRAND CENTRAL, SM MARIKINA |
| **DEFECT-7-ish inventory shortage** (1) | AYALA MARKET MARKET (PM001 again) |
| Allowed skip | ORTIGAS GREENHILLS (empty TIN) |

## What would actually push the pass rate

### For DEFECT-11 (approval-not-auto-firing, 7 stores)

Root cause: test.area's submit doesn't trigger auto-approval for these specific stores. Hypothesis: either
1. These 7 stores have a specific `approval_config` on the Warehouse master that overrides self-approval, OR
2. `submit_order` has a branch that skips auto-approve for certain warehouse types

**Fix requires backend investigation.** Too complex for a test-side patch.

### For DEFECT-8 (dispatch-not-registered, 6 stores)

Root cause unknown. Same 3 stores consistently (AYALA SOLENAD/VERMOSA/CTTM TOMAS MORATO) + 3 new (SM BICUTAN/GRAND CENTRAL/MARIKINA).

**Fix requires Playwright trace-zip inspection** showing what the dispatch dialog did.

### For AYALA MARKET MARKET (inventory)

S217 passed, S218 failed. Flip-flop suggests a TEST-RUN-ORDER dependency (stock depleted by earlier test). qty=5 didn't help.

## Recommendation

Stop the iteration loop here. **31/49 (63%) is the stable plateau** for cheap test-side fixes. The remaining 15 failures require:

1. **Backend investigation** of why auto-approve doesn't fire for certain stores (DEFECT-11) — 7 stores affected
2. **Playwright trace inspection** of dispatch-not-registered cases (DEFECT-8) — 6 stores
3. **Inventory reseeding** or a smarter fixture that dynamically caps at bin-actual — 1 store
4. **ORTIGAS TIN data-fill** — 1 store (long-deferred)

Each of these is a proper sprint of its own. S219 could tackle DEFECT-11 (the biggest blocker); S220 for DEFECT-8; S221 for inventory reseeding.

## Cleanup + canonical

- All S218 artifacts cancelled (46 orders / 37 MRs / 31 SEs / 31 SIs)
- Canonical preflight == postcheck (zero drift)
- Ledger reset to `[]`

## Artifacts

- `output/l3/s218/SWEEP_VERIFICATION_SUMMARY.md` (this file)
- `output/l3/s218/sweep_full_run.log` (49 tests, 31 pass, 15 fail, 3 skip)
- `output/l3/s218/sweep_ledger.json` (reset)
- `output/l3/s218/monitor_decisions.log` (no kills)
- `output/l3/s218/canonical_preflight.txt` + `canonical_postcheck.txt`
