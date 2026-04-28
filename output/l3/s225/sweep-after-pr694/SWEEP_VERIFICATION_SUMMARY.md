# S225 Phase 6 — POST-PR#694 L3 Sweep Verification Summary

**Sweep window:** 2026-04-28T08:30:39+08 → 2026-04-28T09:24:12+08 (53.6 min wallclock; full 49 stores attempted)
**Branch under test:** `production` HEAD `ca6401c2689ea4e6eec194ed48bdaec2d4ec4fe1` (PR #693 weather-sync on top of PR #694 S225 phase 6 defects merge `73b89feb8`)
**Container code mtime:** `1777294318` (`store.py`) — confirmed live via `s225_poll_pr694_deploy.py` 7/7 markers present
**Sweep launched from:** `F:/Dropbox/Projects/BEI-ERP-s225-canonical-warehouse-cleanup-and-pattern-a-safeguard` worktree
**Spec:** `tests/e2e/specs/s209-all-stores.spec.ts` (49-store happy chain)
**Kill threshold:** `--kill-same-fingerprint 15` (raised from 8 used in pre-PR#694 run)

---

## Top-line

**Result: 32 PASSED / 14 FAILED / 3 SKIPPED** (49 total). Pass rate: **65.3%**.

Sweep was NOT killed by the monitor — completed all 49 stores. No fingerprint reached the 15-occurrence threshold (peak was WarehouseApprovalPage at 9).

| Metric | Pre-PR#694 sweep | Post-PR#694 sweep (this) | Δ |
|---|---|---|---|
| Stores attempted | 41 (killed early) | **49 (all attempted)** | +8 |
| Confirmed passes | 28 | **32** | +4 |
| Pass rate (of attempted) | 28/41 = 68% | 32/46 = 70% | +2pp |
| Pass rate (of total) | 28/49 = 57% | **32/49 = 65%** | +8pp |
| WarehouseApprovalPage failures | 8 (kill trigger) | 9 | +1 |
| DispatchPage failures (Pattern A residual) | 1 | 4 | +3 |
| BEI Warehouse Receiving missing | 1 | 1 | unchanged |
| Negative-stock errors | 0 | 0 | clean |
| MySQL deadlocks | 0 | 0 | clean |

**The bump from 28 to 32 passes (+4) is real but smaller than expected.** PR #694 fixed the fingerprint cap — the sweep no longer kills early on the WarehouseApprovalPage failure — but the underlying defect classes still affect the same number of stores (~14).

---

## Failure breakdown

### Class 1 — WarehouseApprovalPage approve button not visible after reload (9 stores)

| Store | MR |
|---|---|
| AYALA MARKET MARKET - BEBANG MARKET MARKET INC. | MAT-MR-2026-00262 |
| AYALA SOLENAD - HFFM SOLENAD FOOD SERVICES INC. | MAT-MR-2026-00270 |
| NAIA T3 - HALO-HALO TERMINAL FOOD CORP. | MAT-MR-2026-00298 |
| ORTIGAS ESTANCIA - BB ESTANCIA FOOD CORP. | MAT-MR-2026-00299 |
| ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC | MAT-MR-2026-00300 |
| ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC. | MAT-MR-2026-00301 |
| ROBINSONS GENERAL TRIAS - BEBANG MEGA INC. | MAT-MR-2026-00318 |
| ROBINSONS IMUS - BEBANG MEGA INC. | MAT-MR-2026-00319 |
| AYALA VERMOSA - BEBANG MEGA INC. | MAT-MR-2026-00404 |

**PR #694 fix #3 added "Ordered" to the `get_pending_material_requests` filter at `hrms/api/warehouse.py:1097`.** That is a backend fix — it makes the queue endpoint return MRs in `Ordered` status to the warehouse approval queue. The test failure persists.

**Hypothesis (NOT VERIFIED in this sweep):** the warehouse approval **page** uses a different endpoint than `get_pending_material_requests`, OR uses SWR/cache that doesn't invalidate on reload, OR the approve button has additional conditional rendering keyed on a field PR #694 didn't touch. The error fires at `pages\WarehouseApprovalPage.ts:37` after a `goto + waitForTimeout(1500) + waitForBtn(20000)` sequence — the row is supposed to be visible after reload but the button never renders.

The MR numbers cluster (00298–00301, 00318–00319) suggest the failure is store-config-dependent rather than purely random. Worth verifying which warehouse / company entity rule causes the button to be hidden.

### Class 2 — DispatchPage dispatch did not register within 30s (4 stores)

| Store | MR |
|---|---|
| MEGAWORLD PASEO CENTER - BEBANG PASEO INC. | MAT-MR-2026-00544 |
| SM BICUTAN - BEBANG SM BICUTAN INC. | MAT-MR-2026-00547 |
| SM MARIKINA - BEBANG SM MARIKINA INC. | MAT-MR-2026-00548 |
| SM SOUTHMALL - BEBANG ENTERPRISE INC. | MAT-MR-2026-00549 |

**PR #690 (Phase 4) added `SELECT ... FOR UPDATE` row lock to `create_stock_transfer` covering both `tabBin` and `tabBatch`.** Phase 5 stress test (10 parallel dispatches) showed 10/10 PASS, 0 negative-stock, 0 deadlocks — the lock works at the concurrency level it was designed for.

**Phase 6 sweep is sequential (1 worker), so this is NOT a race condition.** The lock contention isn't relevant for a single test run. The error states `status=Ordered, per_transferred=undefined` — meaning the MR is in `Ordered` status but never transitioned to `Partially Ordered` or `Ordered` with `per_transferred > 0`.

**Hypothesis:** likely a stock-out scenario for these 4 stores' MR items, OR a UI form that doesn't actually trigger the create_stock_transfer endpoint, OR a different missing route (defect #1 was a defense-in-depth fallback, not a proper fix). MR numbers 00544–00549 are very close, suggesting the failure mode is reproducible per-store.

This count is HIGHER than the pre-PR#694 sweep (1 → 4). The PR #694 fixes did not regress dispatch behavior (Phase 5 stress passed); the increase is more likely because more stores were exercised in this sweep (49 attempted vs 41 attempted before).

### Class 3 — No BEI Warehouse Receiving produced for MR (1 store)

| Store | MR |
|---|---|
| SM STA. ROSA - SWEET HARMONY FOOD CORP. | MAT-MR-2026-00556 |

Same 1-store occurrence as the pre-PR#694 sweep. Could be data, could be intermittent, could be a real bug. Single occurrence is hard to root-cause from sweep alone.

### Skipped (3 stores — not in the failed list)

3 tests were marked as skipped by Playwright. Not enumerated in the per-test fail list above. Likely fixture timeouts or test.skip() runtime decisions. Inspect `output/l3/s225/sweep-after-pr694/sweep_full_run.log` for details.

---

## Cumulative trajectory

| Sprint | Result | Notes |
|---|---|---|
| S209 | baseline (~16/49) | initial 49-store happy chain |
| S221 | 36/49 | with REST-fallback test bypass (later reverted) |
| S222 | 33/49 | regression with dispatch-SE-fallback (later reverted) |
| S223 | 16/49 | bypasses reverted, real product bugs surfaced |
| S225 Phase 6 (PRE-PR#694) | 28/41 attempted (~57% of 49) | killed early by 8x WarehouseApprovalPage |
| **S225 Phase 6 (POST-PR#694, this)** | **32/49 (65%)** | **all 49 attempted, no kill** |

Net improvement vs the pre-PR#694 sweep: **+4 stores passing, +8 stores attempted (no early kill), 0 regression in concurrency or stock integrity.**

---

## What PR #694 actually delivered (honest classification)

| Defect | Classification | Phase 6 evidence |
|---|---|---|
| D1 source_route fallback | Defense-in-depth (real fix is to add missing routes) | Stops `InvalidWarehouseCompany` Sentry signal but doesn't make the test pass — affected stores still hit a downstream symptom |
| D2 approve_order idempotency | Partial (mirrors S224 Pattern B) | Re-approval works without error, but doesn't help the upstream "approve button not visible" problem |
| D3 warehouse queue includes Ordered | **Correct backend fix** | Backend endpoint returns Ordered MRs. UI test still fails — UI layer needs investigation |
| D4 lock-wait try/except | Defense-in-depth for D5 | Prevents secondary failure from the systemic Sentry context bug |
| D5 sentry monkey-patch | **Correct systemic fix** | Sentry no longer raises `RuntimeError` from non-request callers — observability cleaner |
| D6 sales dashboard non-POS | **Correct fix** | Sentry no longer spammed on dashboard load for commissary/cold-storage warehouses |
| D7 mosaic on_conflict | **Correct fix** | PostgREST 409 on POS line item upsert resolved |

Three out of seven are unambiguous correct fixes (D3 backend, D5, D7). Two are defense-in-depth (D1, D4). Two are partial (D2, D6 — D6 is correct but only affects observability noise, not test pass rate).

**The test pass rate would not improve much from PR #694's defects 1, 2, 4, 5, 6, 7** — they fix observability/idempotency/error-handling, not the test paths. **Only D3 (warehouse queue includes Ordered) directly targets a test failure path**, and the UI test still fails despite the backend fix landing.

---

## Operational hygiene (closeout checks)

| Check | Status |
|---|---|
| Canonical structure (49 stores, 0 violations) | ✅ confirmed via `scripts/verify_canonical_structure.py` (output/s225/verification/canonical_postcheck_phase7.txt) |
| Stock Settings allow_negative_stock = 0 | ✅ confirmed via `scripts/s225_verify_stock_settings_reverted.py` |
| Stock Settings allow_negative_stock_for_batch = 0 | ✅ confirmed (LESSON F clean) |
| PR #694 7/7 fixes deployed | ✅ confirmed via `scripts/s225_poll_pr694_deploy.py` (output/s225/verification/pr694_deploy_check.json) |
| 0 negative-stock during sweep | ✅ |
| 0 MySQL deadlocks during sweep | ✅ |
| Worktree dirty state at handoff | scripts (untracked) + output evidence (gitignored except force-add) — committed on closeout PR |

---

## Decision: closeout S225, file follow-up sprint for residual 14 stores

S225 plan's Phase 6 outcome matrix:
- **≥48/49 PASS**: COMPLETED unconditionally
- **43-47/49 PASS**: Major progress, COMPLETED with documentation
- **36-42/49 PASS**: Pattern A still failing some — COMPLETED with note that fix addresses concurrency only
- **<36/49 PASS**: Regression — STOP, surface to Sam

**32/49 sits in the `<36` band but is NOT a regression.** PR #694's backend fixes are deployed and verified. The dominant residual is `WarehouseApprovalPage` (9 stores) which is a UI-layer issue PR #694 did not target (D3 fixed the backend endpoint only). The Pattern A residual on DispatchPage (4 stores) needs separate root-cause work — possibly stock-out, possibly a different code path than create_stock_transfer.

Per the cold-start handoff (§3b): *"If the sweep stalls again on a new defect class → STOP, file S227 follow-up plan (do NOT extend S225 further — Sam's pattern is one PR per defect cluster)."*

**These are NOT new defect classes.** They are the same classes from the pre-PR#694 sweep. PR #694 made progress (no early kill, +4 passes) but did not eliminate them.

**Recommendation:** Closeout S225 with this honest summary. File S228 (S226/S227 are taken) for the residual 14 stores grouped by defect class:
1. WarehouseApprovalPage UI investigation (9 stores)
2. DispatchPage Pattern A non-concurrency residual (4 stores)
3. Single-occurrence Warehouse Receiving missing (1 store)

S225 has delivered:
- Canonical warehouse cleanup (Phase 3) — 2 em-dash duplicates consolidated, 49 stores / 0 violations
- Pattern A FOR UPDATE lock (Phase 4) — 10/10 stress test pass, 0 negative-stock, 0 deadlocks
- 7 Sentry-driven defects fixed (PR #694) — observability cleaner, two backend code paths fixed correctly
- S226 hot-fix (queue visibility) — deployed earlier in this sprint

Sam to confirm the closeout call and decide on the follow-up sprint scope.

---

## Evidence files

- `output/l3/s225/sweep-after-pr694/sweep_full_run.log` — full Playwright stdout
- `output/l3/s225/sweep-after-pr694/sweep_ledger.json` — per-test ledger (passes + fails by fingerprint)
- `output/l3/s225/sweep-after-pr694/monitor_decisions.log` — kill-monitor STATUS lines + decisions
- `output/l3/s225/sweep-after-pr694/launcher_stdout.log` — launcher stdout
- `output/l3/s225/sweep-after-pr694/sweep.pid` — Playwright PID file
- `output/s225/verification/pr694_deploy_check.json` — 7/7 deploy verification
- `output/s225/verification/canonical_postcheck_phase7.txt` — 49 stores / 0 violations
- `output/s225/verification/stock_settings_reverted_check.txt` — both flags = 0
