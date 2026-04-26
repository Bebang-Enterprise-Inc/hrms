# S223 Phase 7B — UI-only L3 Sweep Verification Summary

**Sprint:** S223 — Real product fixes for L3 store-chain failures (Phase 7B verification)
**Sweep date:** 2026-04-26 PHT (~13:19 → 14:05 PHT, ~46 min)
**Mode:** UI-only — S221 REST `approve_order` fallback REMOVED, S222 SE-existence fallback REMOVED
**Status:** KILLED at test 33/49 (same-fingerprint=5 on Pattern A DispatchPage timeout)

---

## Bottom line

**16 PASS / 30 attempted (53.3% of attempted) / 16 of 49 (32.7% of all stores)** — the monitor killed the sweep at test 33/49 when the Pattern A DispatchPage timeout hit 5 same-fingerprint occurrences.

This is BELOW the S221 baseline (36/49 with REST fallback) and BELOW the projected ~43/49 best-case. The DEFECT-11 fix did NOT solve the order-approval narrowing for stores that S221 was masking — at least one previously-passing store (ARANETA GATEWAY) now fails because the fallback was its safety net.

## PR + deploy state at sweep time

- hrms PR #684 merged at 03:25 UTC (S223 backend ordering.py change + ORTIGAS TIN data fix). Deployment confirmed live via REST probe before sweep.
- bei-tasks PR #452 merged at 03:25 UTC (frontend selectedDate="" + fallback reverts). Vercel auto-deploy.

## Final 16 PASS stores

| # | Store |
|---|---|
| 1 | AYALA MARKET MARKET - BEBANG MARKET MARKET INC. |
| 2 | BF HOMES - BEBANG BF HOMES INC. |
| 3 | D'VERDE CALAMBA - TAJ FOOD CORP. |
| 4 | EVER COMMONWEALTH - DLS DESSERT CRAFT INC. |
| 5 | FESTIVAL MALL ALABANG - BEBANG FESTIVAL INC. |
| 6 | LUCKY CHINATOWN - BEBANG LCT INC. |
| 7 | MEGAWIDE PITX - BEBANG PITX INC. |
| 8 | MEGAWORLD PASEO CENTER - BEBANG PASEO INC. |
| 9 | MEGAWORLD VENICE GRAND CANAL - BEBANG VENICE GRAND CANAL INC. |
| 10 | ROBINSONS GALLERIA SOUTH - TUNGSTEN CAPITAL HOLDINGS OPC |
| 11 | ROBINSONS GENERAL TRIAS - BEBANG MEGA INC. |
| 12 | SM CALOOCAN - TAJ FOOD CORP. |
| 13 | SM CLARK - RED TALDAWA FOODS OPC |
| 14 | SM EAST ORTIGAS - BEBANG SMEO INC. |
| 15 | SM MALL OF ASIA - BEBANG SMOA INC. |
| 16 | SM MANILA - BEBANG ENTERPRISE INC. |

## 14 FAIL (attempted) — categorized by failure pattern

| Store | Failure pattern | Layer |
|---|---|---|
| ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC | OrderApprovalPage: order not in approval queue | Stage 1 approval (DEFECT-11 fix did NOT unblock — see analysis below) |
| AYALA SOLENAD - HFFM SOLENAD FOOD SERVICES INC. | DispatchPage timeout | Pattern A (modal stuck) |
| AYALA VERMOSA - BEBANG MEGA INC. | DispatchPage timeout | Pattern A (modal stuck) |
| AYALA FAIRVIEW TERRACES - BEBANG FT INC. | OrderApprovalPage: order not in queue OR WarehouseApprovalPage button not visible | DEFECT-11 / Pattern B |
| AYALA UP TOWN CENTER - BEBANG UP TOWN CENTER INC. | OrderApprovalPage / WarehouseApprovalPage | DEFECT-11 / Pattern B |
| CTTM TOMAS MORATO - B CUBED VENTURES CORP. | DispatchPage timeout | Pattern A (modal stuck) |
| NAIA T3 - HALO-HALO TERMINAL FOOD CORP. | Material Request never created (polled 30000ms, last=0) | Pattern C |
| ORTIGAS ESTANCIA - BB ESTANCIA FOOD CORP. | Material Request never created | Pattern C |
| ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC | Material Request never created | Pattern C (TIN apply did NOT unblock — different root cause) |
| ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC. | OrderApprovalPage / WarehouseApprovalPage | Pattern B |
| ROBINSONS IMUS - BEBANG MEGA INC. | OrderApprovalPage / WarehouseApprovalPage | Pattern B |
| SM BICUTAN - BEBANG SM BICUTAN INC. | DispatchPage timeout | Pattern A (modal stuck) |
| SM GRAND CENTRAL - BEBANG GRAND CENTRAL INC. | DispatchPage timeout | Pattern A (modal stuck) |
| SM MARIKINA - BEBANG SM MARIKINA INC. | DispatchPage timeout | Pattern A (modal stuck) |

Pattern A confirmed: 6 stores match S222 trace findings.
Pattern C confirmed: NAIA T3 + ORTIGAS ESTANCIA + ORTIGAS GREENHILLS (TIN apply was necessary but not sufficient).

## 19 NOT ATTEMPTED (sweep killed)

The following stores never started because the monitor killed Playwright at test 33/49:
- SM MARILAO and 18 others (alphabetically after SM MARILAO).

Pre-existing observation: SM STA. ROSA, SM SOUTHMALL (plan's Pattern B set) were among the not-attempted set.

## DEFECT-11 fix analysis — why it didn't unblock

**Hypothesis under test (per plan):** `selectedDate = useState(todayStr())` narrowed the approval queue to today-only. Fix: default to `""` + backend treats empty date as no filter.

**REST probe pre-sweep confirmed deploy:** `curl /api/method/hrms.api.ordering.get_order_review_queue?date=` returned 19 orders across multiple dates (March-April), proving the backend supports empty date.

**Sweep evidence:** ARANETA GATEWAY (and AYALA FAIRVIEW TERRACES, AYALA UP TOWN CENTER) still hit "order did not appear in the approval queue after 6 navigation attempts". The S223 error message we wrote into OrderApprovalPage.approve fires explicitly.

**Probable real root cause (re-investigation needed):**
- The order is in `tabBEI Store Order` with status="Pending Approval", correctly assigned to test.area (since `s209_grant_test_area_access.py` set custom_area_supervisor=test.area).
- BUT the page's SWR cache may be stale across navigation. `useOrderReviewQueue` uses `revalidateOnFocus: false` — page navigation may not re-fetch.
- OR: the order's `assigned_approver` in `tabBEI Approval Queue` differs from `current_user` because of timing between the access-grant + submit_order + queue-creation chain.

The plan's pre-loaded hypothesis (`selectedDate = todayStr()` is the culprit) was PARTIALLY correct — fixing the date filter was necessary but not sufficient. There's a SECOND narrowing layer that S221's REST fallback was bypassing.

## ORTIGAS GREENHILLS analysis — TIN fix necessary, not sufficient

The TIN data fix (Phase 5) resolved the canonical violation (0 violations now). But ORTIGAS GREENHILLS still fails the L3 sweep with "Material Request never created" — same Pattern C as NAIA T3 and ORTIGAS ESTANCIA. So TIN was a precondition but not the root cause of the chain failure.

## Failure pattern aggregate (from monitor `top_buckets` final tally)

| Bucket | Count |
|---|---|
| `OrderApprovalPage.approve: order <ORDER> did not appear in the approval queue after 6 navigation attempts` | 4 |
| `DispatchPage: dispatch did not register for <MR> within 30s` | 5 |
| `Material Request for order <ORDER> (polled 30000ms, last=0)` | 3 |
| `WarehouseApprovalPage: Approve button for <MR> not visible after reload` | 1 |
| Other (mixed) | 1 |

Pattern A (DispatchPage) hit the same-fingerprint=5 kill threshold first → sweep terminated.

## Canonical drift

Preflight pre-sweep: 0 violations (Phase 5 TIN apply already in effect).
Postcheck after sweep + cleanup: **0 violations**.
Cleanup: per `scripts/s209_cleanup_sweep.py` — all test artifacts cancelled/deleted via MR-resuscitate cascade. 

## Comparison to the trajectory

| Sprint | Pass | % | Delta from baseline | Fallback status |
|---|---|---|---|---|
| S209 baseline | 20/49 | 41% | — | none (raw) |
| S217 R1 | 31/49 | 63% | +22pp | none |
| S221 R1 | 36/49 | 73.5% | +32.5pp | S221 REST approve fallback |
| S222 R1 | 33/49 | 67.3% | -3 vs S221 | S221 + S222 SE fallback |
| **S223 7B** | **16/30 (53.3%)** | **32.7% of 49** | **−20 vs S221** | **NO fallbacks** |

The drop is partly because the sweep didn't complete (19 stores not attempted). If we extrapolate the 53.3% pass rate to all 49 stores: ~26/49 expected. Still below S217 baseline.

## Key takeaway

**Removing S221 + S222 fallbacks exposed THREE distinct unaddressed bugs:**
1. **Pattern A** (Dispatch modal stuck) — 6 stores, NOT fixed by S223
2. **Pattern B** (Warehouse approval narrowing) — 4+ stores, NOT fixed by S223
3. **DEFECT-11 v2** (Order approval narrowing — beyond date filter) — 4+ stores, NOT fully fixed by S223 (the date filter fix was insufficient — there's another narrowing layer)
4. **Pattern C** (MR never created) — 3 stores, NOT fixed by S223

S223 shipped DEFECT-11 partial fix + ORTIGAS TIN + reverted fallbacks. The fallbacks were the safety net; without them AND without the underlying bugs fixed, pass rate dropped.

## Recommended next steps

1. **Open S224 follow-up sprint** for live-browser investigation of:
   - Pattern A (Dispatch modal) — needs DevTools network capture during failed click
   - Pattern B (Warehouse approval) — needs SWR cache + backend filter trace
   - DEFECT-11 v2 (Order approval narrowing beyond date) — confirm whether SWR cache or assigned_approver mismatch
   - Pattern C (MR creation) — paused at canonical resolver boundary; needs Sam approval

2. **Sam decision:** either
   - (a) Roll back S221+S222 fallback reverts (keep them as safety net while real fixes ship), OR
   - (b) Accept the 16/49 baseline and ship Pattern A/B/C fixes incrementally in S224-226

3. **Alternative:** invoke `/l3-v2-bei-erp` against SM STA. ROSA, SM SOUTHMALL specifically (the not-attempted Pattern B stores from the plan) to see if they also fail — confirms Pattern B reproducibility.

## Evidence files (all on s223-l3-sweep branch)

- `output/l3/s223/sweep_full_run.log` — Playwright reporter output (49 tests planned, 33 attempted, 16 PASS)
- `output/l3/s223/sweep_ledger.json` — 85 ledger entries (30 order-create / 23 mr-create / 16 wr-create / 16 si-create)
- `output/l3/s223/monitor_decisions.log` — 50+ STATUS ticks + 1 KILL decision
- `output/s223/verification/canonical_postcheck_phase7b.txt` — 0 violations after sweep
- `output/s223/verification/sweep_7b_start.txt` / `sweep_7b_end.txt` — UTC window timestamps
- Trace zips for failed tests in `C:/Users/Sam/AppData/Local/Temp/bei-pw-artifacts/specs-s209-all-stores-*` (will be wiped on next Playwright run; capture if needed for Sam analysis)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
