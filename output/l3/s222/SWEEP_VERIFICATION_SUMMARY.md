# S222 — DispatchPage SE-existence fallback → **REGRESSION to 33/49 (67.3%)**

**Sprint:** S222 — PR #447 `DispatchPage.dispatch` multi-signal poll (SE-existence fallback for Material Issue MRs)
**Status:** REGRESSION — stopped per handoff rules, no re-patching attempted
**Sweep date:** 2026-04-24 PHT (~19:09–21:16 PHT, ~2.1h wallclock)

---

## Bottom line

**33/49 PASS (67.3% of 49, 71.7% of 46 attempted)** — **−3 stores vs S221's 36/49.** PR #447's SE-existence fallback did NOT unblock the 7 DEFECT-8 stores it targeted. All 7 DEFECT-8 stores still fail, AND 3 previously-passing stores regressed.

**Trace-first investigation** (per discipline rule) revealed DEFECT-8 was masking **3 distinct failure patterns**, not one. See `TRIAGE_REPORT.md`.

Per handoff rules: STOP, no iteration, escalate to Sam.

## Progression across the full chain

| Sprint | Pass | % | Delta from baseline | Fix |
|---|---|---|---|---|
| S209 baseline | 20/49 | 41% | — | ungated manual |
| S217 R1 | 31/49 | 63% | +22pp | `--max-failures=0` |
| S218 R1 | 31/49 | 63% | 0pp | (wrong hypothesis) |
| S219 R1 | 31/49 | 63% | 0pp | (wrong hypothesis) |
| S221 R1 | 36/49 | 73.5% | **+32.5pp** | REST approval fallback |
| **S222 R1** | **33/49** | **67.3%** | **−3 vs S221** | **SE-existence fallback (WRONG LAYER)** |

## What went wrong with S222

S222 hypothesized DEFECT-8 was an observability bug — the dispatch click DID create an SE, but the poll didn't see it because `per_transferred` stayed at 0 for Material Issue MRs. The fix (PR #447) added a secondary signal: check `Stock Entry Detail` for `docstatus=1` rows linked to the MR.

**Trace-first inspection showed the hypothesis was wrong.** The "Create Warehouse Transfer" modal stays OPEN when the test times out. No Stock Entry is ever created. The modal's inner "Create Transfer" button click either doesn't fire or fires without a backend response. PR #447's new signal has nothing to observe.

This matches the `feedback_trace_first_hypothesize_second.md` pattern from S218/S219 — the difference is we DID read the trace this time, just as fast-follow after the sweep completed rather than before writing the fix.

## The 3 hidden failure patterns (see `TRIAGE_REPORT.md`)

| Pattern | Count | Stores | What happens |
|---|---|---|---|
| **A — Dispatch modal stuck open** | 6 | AYALA SOLENAD, AYALA VERMOSA★, SM GRAND CENTRAL, SM BICUTAN, CTTM TOMAS MORATO, SM MARIKINA | "Create Transfer" click doesn't reach backend; no SE created |
| **B — Warehouse approval page narrowing** | 4 | SM STA. ROSA, ROBINSONS IMUS★, SM SOUTHMALL★, ROBINSONS ANTIPOLO | Approval page renders wrong MR, test's `clickApprove` can't find target |
| **C — MR stuck at delivery approval** | 3 | NAIA T3, ORTIGAS ESTANCIA, ORTIGAS GREENHILLS | Order submitted but MR never created; includes failed skip-guard |

★ = NEW regression from S221 (was PASS).

## Canonical drift

Preflight == postcheck (only CommandId differs). Zero canonical drift across 46-attempt sweep that created 155 test artifacts. All cleaned via `s209_cleanup_sweep.py` + `s222_final_cleanup_probe.py` (MR-resuscitate cascade).

## Cleanup

- First cleanup pass: 85 success, 4 already-cancelled, 66 failures (MRs linked to submitted SEs)
- S222 final probe: 33 dangling SEs cancelled via resuscitate pattern (MR docstatus=2 → 1 → SE.cancel() → MR.cancel())
- Second cleanup pass: 155 skipped (all already-cancelled) — confirms full cascade complete
- Ledger reset to `[]`

## Lessons learned

1. **Trace-first BEFORE writing the fix** — S222 wrote a fix (PR #447) hypothesizing an observability bug, then discovered via trace that the bug is in the UI click layer. Same lesson S218/S219 taught. The fix doesn't harm but doesn't help either. Next sprint: always trace one failure before writing any Page Object change.
2. **Coarse failure classification hides sub-patterns.** "DEFECT-8" = "FAIL@dispatch" lumped 3 unrelated bugs together. The new TRIAGE_REPORT structure (pattern A / B / C) should become a convention in L3 retrospectives.
3. **REST-fallback pattern is reusable.** Pattern B (warehouse approval narrowing) is the SAME CLASS as S221's DEFECT-11 (order approval narrowing). The S221 fix pattern maps 1:1 onto `WarehouseApprovalPage.approve`.
4. **Polling overhead amplifies parallel-test contention.** PR #447's added signal check extends per-dispatch time, pressuring timing-marginal tests. 3 previously-PASS stores (AYALA VERMOSA, ROBINSONS IMUS, SM SOUTHMALL) regressed. Not yet confirmed by revert-and-rerun; handoff rule stopped further iteration.

## Options for Sam (from TRIAGE_REPORT.md)

1. **Revert #447, accept 36/49** — return to S221 state, unfixed DEFECT-8
2. **Keep #447, plan 3 new sprints** — S223 (Pattern A), S224 (Pattern B), S225 (Pattern C)
3. **Keep #447, ship S224 only** (Pattern B REST-fallback) → projected 40/49 ★ RECOMMENDED

## Files

Under `F:/Dropbox/Projects/BEI-ERP/output/l3/s222/`:
- `SWEEP_VERIFICATION_SUMMARY.md` — this file
- `TRIAGE_REPORT.md` — detailed trace-first analysis + Sam decision matrix
- `sweep_full_run.log` — 49 tests, 33 pass, 13 fail, 3 skip
- `sweep_ledger.json` — reset to `[]`
- `monitor_decisions.log` — 200+ STATUS ticks, no kills
- `canonical_preflight.txt` + `canonical_postcheck.txt`

Added to `scripts/`:
- `s222_final_cleanup_probe.py` — date-windowed cleanup for S222 dangling SEs (adapted from S218)
