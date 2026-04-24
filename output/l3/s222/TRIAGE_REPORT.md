# S222 Triage Report — **REGRESSION to 33/49, below S221's 36/49**

**Sweep date:** 2026-04-24 PHT
**Pass rate:** 33/49 (67.3% of 49, 71.7% of 46 attempted) — **-3 stores vs S221's 36/49**
**Handoff rule triggered:** *"Below 36/49 (regression) — STOP, ask Sam before re-patching."*
**Iteration rule triggered:** *"Plateau = stop. Do NOT write a 3rd hypothesis-driven fix."*

---

## Bottom line

PR #447 (DispatchPage SE-existence fallback) did NOT unblock DEFECT-8. Trace-first inspection revealed **3 distinct failure patterns**, not the single "dispatch observability" issue S222 hypothesized. Worse, S222 also regressed 3 previously-passing stores.

No new fix attempted — per handoff rules, stop at plateau/regression and escalate.

---

## The 3 failure patterns (trace-first findings)

### Pattern A — "Create Warehouse Transfer" modal click never completes (6 stores)

**Evidence:** Trace-zip `error-context.md` shows the dialog with all fields populated, source warehouse set, items listed, AND the dialog is still OPEN when the 30s dispatch poll expires. The inner "Create Transfer" button click (ref=e29) either never fires or fires without resolving.

**Affected stores:**
- AYALA SOLENAD (original DEFECT-8)
- AYALA VERMOSA **(NEW regression — was PASS in S221)**
- SM GRAND CENTRAL (original DEFECT-8)
- SM BICUTAN (original DEFECT-8)
- CTTM TOMAS MORATO (original DEFECT-8)
- SM MARIKINA (original DEFECT-8)

**Why PR #447 didn't help:**
PR #447 added `query Stock Entry Detail where material_request=X` as a secondary success signal. But if the modal submit never completes, NO Stock Entry is ever created, so neither the primary signal (`per_transferred > 0`) NOR the new fallback signal has anything to observe. The fix addresses observability; the real bug is that the modal's "Create Transfer" click isn't reaching the backend.

**Source warehouses:** `PINNACLE COLD STORAGE SOLUTIONS - BKI` and `3MD LOGISTICS - CAMANGYANAN - BKI`. Both BKI intercompany sources.

### Pattern B — "Approve Warehouse Requests" page stuck, wrong MR displayed (4 stores)

**Evidence:** Trace shows the Warehouse Approval page only rendering an old MR (MAT-MR-2026-00120 for SM Tanza from a prior sweep day), not the MR the test just created. Test's `clickApprove(mrName)` times out because the expected MR isn't in the list.

**Affected stores:**
- SM STA. ROSA (original DEFECT-8)
- ROBINSONS IMUS **(NEW regression — was PASS in S221)**
- SM SOUTHMALL **(NEW regression — was PASS in S221)**
- ROBINSONS ANTIPOLO (original DEFECT-8)

This is the SAME class of UI-rendering bug that S221 fixed for the Order Approval page (DEFECT-11). The Warehouse Approval page has the same narrowing issue — client-side rendering drops MRs that the backend queue returned.

**Why PR #447 didn't help:** This failure happens BEFORE dispatch. The test never reaches DispatchPage. #447's scope doesn't include the approval step.

### Pattern C — MR never created (order stuck at delivery approval) (3 stores)

**Evidence:** Trace shows Store Order detail page with `Delivery: 2026-04-25` text. The order was submitted but not yet routed through dual approval to create an MR. Ledger has only `order-create` for these stores, no `mr-create`.

**Affected stores:**
- NAIA T3 (carried from S221 FAIL@MR)
- ORTIGAS ESTANCIA (carried from S221 FAIL@MR)
- ORTIGAS GREENHILLS (was ALLOWED SKIP in S221 — the skip-guard may have lapsed)

ORTIGAS GREENHILLS with `allowEmptyTin: True` fixture flag should have been skipped before reaching order submission. In S222 it attempted the submit flow and got stuck — possibly the skip logic in the spec doesn't fire for ORTIGAS GREENHILLS anymore, or the fixture interpretation changed.

---

## Regression analysis

| Store | S221 state | S222 state | Pattern |
|---|---|---|---|
| AYALA VERMOSA | PASS | FAIL@dispatch | A (modal stuck) |
| ROBINSONS IMUS | PASS | FAIL@dispatch | B (approval stuck) |
| SM SOUTHMALL | PASS | FAIL@dispatch | B (approval stuck) |
| ORTIGAS GREENHILLS | SKIP | FAIL@MR | C (skip lapsed) |

3 regressions from previously-passing stores + 1 skip-became-fail = net −4 from S221 pass rate. The +1 gain (nothing new passed that wasn't in S221) does not offset.

**Likely cause of regressions:** S222 PR #447 adds polling overhead to DispatchPage. Combined with Playwright's 2-3 worker parallelism, this extends total execution time per store, putting timing-marginal stores over the test's 30s dispatch window. In other words, #447 is additive and harmless on its own, but the cost amplifies cross-test contention.

**Not verified:** Did not revert #447 and re-run to confirm it's the cause. Handoff rule says "ask Sam before re-patching."

---

## What the library learned

- **Observability-layer fixes don't fix UI-click-layer bugs.** S222's hypothesis (Pattern B from `LIBRARY_IMPROVEMENTS.md`) assumed the SE was being created but the poll couldn't see it. Trace evidence says no SE is created — the click itself isn't landing.
- **Multiple failure patterns were hidden inside "DEFECT-8".** S209→S221 only observed "FAIL@dispatch" as a coarse classification. S222's failure revealed 2 sub-patterns (A, B) that look identical at the ledger level but require different fixes.
- **The skip-guard for ORTIGAS GREENHILLS is no longer sufficient.** Something in the spec or fixture interpretation changed so `allowEmptyTin` doesn't trigger an early skip.

---

## Options for Sam (decision required)

### Option 1 — Revert PR #447, accept 36/49 plateau
- Pros: Reverts the 3 regression stores. Returns to known-good S221 state.
- Cons: DEFECT-8 is still unfixed. No progress on 48/49 goal.
- Effort: 5 min revert + 55 min rerun to confirm.

### Option 2 — Keep PR #447, plan 3 new sprints for A/B/C
- Pros: #447 is correct for its narrow scope; removing it doesn't help. New sprints can address each pattern surgically.
- Cons: Regressions stay broken until the new sprints ship. 3 sprints = ~3 weeks cadence.
- S223 scope: Pattern A (modal submit never completes — requires DOM-event inspection or console.log capture during the Create Transfer click)
- S224 scope: Pattern B (approval page narrowing — extend S221 REST-fallback pattern to `WarehouseApprovalPage`)
- S225 scope: Pattern C (skip-guard for empty TIN + NAIA/ESTANCIA delivery-approval state)

### Option 3 — Keep PR #447, ship only S224 (Pattern B) next
- Pros: Biggest marginal win. Pattern B is well-understood (same class as S221 DEFECT-11 fix). 4 stores unblocked = 40/49 projected.
- Cons: Leaves Pattern A (6 stores) and Pattern C (3 stores) unaddressed.
- Effort: ~1 sprint.

### Recommendation

Option 3. S224 = WarehouseApprovalPage REST-fallback (mirror S221 pattern). Gets to 40/49 with least risk. Then plan A and C separately after Pattern B data proves the approach.

But this is a Sam call. Nothing auto-patched from this agent.

---

## Evidence paths

- **This sweep's artifacts:** `F:/Dropbox/Projects/BEI-ERP-s222-sweep/output/l3/s222/` (committed to `s222-sweep` branch)
- **Playwright trace zips:** `C:/Users/Sam/AppData/Local/Temp/bei-pw-artifacts/specs-s209-all-stores-*`
- **Key trace zip to view interactively:** `specs-s209-all-stores-S209-26df0--SOLENAD-FOOD-SERVICES-INC--chromium/trace.zip` — open with `npx playwright show-trace` to replay the Create Transfer click step
- **S221 baseline:** `output/l3/s221/SWEEP_VERIFICATION_SUMMARY.md` (36/49)

## Canonical check

Preflight == postcheck (only CommandId differs). Zero canonical drift across 46-attempt sweep that created 155 test artifacts. All cleaned via s209 + s222 cleanup probes.
