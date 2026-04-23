# S219 — Force is_edited fix for approval queue visibility

**Sprint:** S219 — Test-side fix: force `is_edited=1` to trigger approval queue entry creation
**Status:** COMPLETED — hypothesis WRONG, same 31/49 result
**Sweep date:** 2026-04-22 PHT
**Wallclock:** 56.8 min (full 49-store run)

---

## Bottom line

**31/49 PASS (63%)** — identical to S217 and S218. Third consecutive iteration with same result. My hypothesis that forcing `is_edited=1` would unblock the 7 approval-list-invisible stores was **wrong**. Same failure list.

## My hypothesis (wrong)

I theorized that `submit_order`'s `requires_manual_approval` flag (which triggers approval queue entry creation) required `edited_lines_count > 0`, and that failing stores had `is_edited=0` on every line → no queue → invisible in UI.

Patch: forced qty to deviate from `recommended_qty` on every line (ceil(suggested/2) capped at 5, never equal to suggested).

Result: 30 same passing stores + same 15 failures. 1 store flipped (AYALA MARKET MARKET was borderline). Net zero.

## Why the hypothesis was wrong (likely)

Looking at the 15 failing stores in S219 vs S217 — the list is nearly identical. If my fix had worked for the 7 "approval-list-invisible" stores, they should have moved to PASS. They didn't. Possibilities:

1. **Backend isn't computing `is_edited=1` from my test payload.** The test sends the pick data; backend computes recommended. If the recommended snapshot differs slightly (fractional, unit conversion), my "forced deviation" may have accidentally matched the backend's recomputed recommended → still `is_edited=0`.

2. **The UI visibility issue is NOT about queue entry creation.** There's a different filter I missed.

3. **The orders pass through an entirely different code path** that I haven't inspected.

Without a backend trace of a SINGLE failing order's state, I can't disambiguate. Further test-side iteration is wasted effort.

## Sweep iteration history

| Sprint | Pass | Δ | Key fix | Outcome |
|---|---|---|---|---|
| S209 baseline | 20/49 | — | ungated manual run | 41% |
| S212 R1 | 3/8 | — | DEFECT-1/2/3 backend | kill early |
| S213 R1 | 7/15 | — | DEFECT-6 BKI batches | kill early |
| S216 R1 | 9/17 | — | DEFECT-7 qty cap + broader backfill | Playwright cutoff |
| S217 R1 | 31/49 | +22pp | `--max-failures=0` (full run) | **63%** |
| S218 R1 | 31/49 | 0pp | qty cap 20→5 + timeout 8s→30s | hypothesis wrong |
| S218 R1 | 31/49 | 0pp | (duplicate — same cfg) | same |
| **S219 R1** | **31/49** | **0pp** | **force is_edited=1** | **hypothesis wrong** |

**31/49 is a genuine plateau for test-side fixes** after S217's baseline.

## What's actually blocking the remaining 15 stores

Based on the consistent failure pattern across 3 iterations:

| Count | Pattern | Best guess root cause |
|---|---|---|
| 3 | AYALA SOLENAD/VERMOSA/CTTM TOMAS MORATO — dispatch-not-registered | DEFECT-8: UI dispatch dialog race, PINNACLE/3MD source specific |
| 3 | SM BICUTAN/GRAND CENTRAL/MARIKINA — dispatch-not-registered | Same DEFECT-8 pattern |
| 4 | FESTIVAL MALL/MEGAWIDE PITX/MEGAWORLD VENICE/NAIA T3 — locator.waitFor OrderApprovalPage | DEFECT-11: UI filter excludes order from approval list (root cause unknown — hypothesis #1 disproven) |
| 3 | ORTIGAS ESTANCIA/ROBINSONS ANTIPOLO/SM STA. ROSA — MR polled 30s | Same DEFECT-11 approval-invisibility OR inventory shortage OR MR-create race |
| 1 | AYALA MARKET MARKET — MR polled 30s | Inventory shortage flip-flop (PM001 at Pinnacle, depleted by prior tests) |
| 1 | ORTIGAS GREENHILLS | Allowed skip (empty TIN) |

## Recommendation — STOP test-side iteration, pivot to backend investigation

Further test-side patches (different cap values, different timeouts, different deviation logic) will not move the needle. The remaining failures require:

### S220 — Backend trace of one Pending-Approval failing store
- Submit an order via API exactly as test.area would
- Dump the created Order's full backend state (DocType fields, queue entries, tabs)
- Dump what `get_order_review_queue` returns for test.area after submit
- Compare failing (FESTIVAL MALL) vs passing (ARANETA) outputs side by side
- Find the actual filter condition that differs

### S221 — Playwright trace-zip for DEFECT-8 (6 stores)
- Extract trace.zip from a failing dispatch-not-registered run
- Use `npx playwright show-trace trace.zip`
- Observe which UI event fires / doesn't fire in the dispatch dialog
- Identify the UI-level defect

### S222 — Inventory reseeding OR dynamic fixture
- Smart fixture that queries Bin qty per item per warehouse before picking
- OR operations reseed PM001/PM007/KL004 at PINNACLE

**Estimated impact:** If S220 identifies the backend root cause for the 7-store DEFECT-11 cluster, that alone should push pass rate to 38+/49 (77%+). S221 could reach 44+/49 (89%). Adding inventory fix gets to 45/49 (92%). With 1 allowed ORTIGAS skip, realistic target is 45/49.

## Cleanup

- 46 orders, 37 MRs, 31 SEs cancelled (s217_cleanup_cascaded + s218_final_cleanup_probe)
- Ledger reset to `[]`
- Canonical preflight == postcheck (zero drift)

## Lessons learned (for future test-iteration loops)

1. **Don't iterate without backend traces.** S218 + S219 were both wrong-hypothesis test-side patches. The correct next step at S218 was a backend trace, not another test-side patch.
2. **Pass-rate plateau signal.** When 2 consecutive iterations don't move pass rate, stop and investigate — don't patch again.
3. **"Same failure list" means same root cause.** If 14 of 15 failing stores match across iterations, the fix isn't addressing the right thing.

## PRs touched this chain

- bei-tasks PR #443 (S218 cap/timeout) — merged
- bei-tasks PR #444 (S219 force is_edited) — **should be closed unmerged** since fix didn't help
- hrms PR #678 (S218 closeout) — open

## Artifacts

Under `F:/Dropbox/Projects/BEI-ERP/output/l3/s219/`:
- `SWEEP_VERIFICATION_SUMMARY.md` (this file)
- `sweep_full_run.log` — 49 tests, 31 pass, 15 fail, 3 skip
- `sweep_ledger.json` — reset
- `monitor_decisions.log` — no kills (all buckets stayed <12)
- `canonical_preflight.txt` + `canonical_postcheck.txt`
