# BKI→Store Billing Sweep — Summary

**Date:** 2026-05-11
**Trigger:** Post-S243/S238 (PR #735, #738, #740, #741, #742) Company/Warehouse changes
**Scope:** 49 buyer Company candidates exercised end-to-end via the saved S238 smoke-test pattern (create + submit BKI SI → assert paired Draft PI on store books → cancel + cascade verify → force-delete SI)
**Cleanup status:** Production restored to pre-sweep — leftover SI=0, leftover PI=0, orphan PI=0 (verified via `aftermath_result.json`)

## Headline

- **0/49 stores work end-to-end as the canonical PI design intended.** The 13 stores marked PASS pass only because their `Company.enable_perpetual_inventory=0` makes ERPNext skip the auto-stock-accounting logic that the design relies on.
- **3 distinct defect classes discovered**, none fixable by the originally-planned 4-store cost_center patch (S245). See `DEFECTS.md` for full detail.
- **CEO chose "park as documented findings"** — no fix PR opened. Next step is a finance/Denise-led review of canonical PI design before committing to one of the 3 architectural options.

## Verdict counts

| Verdict | Count |
|---|---|
| PASS (caveats — see DEFECT D) | 13 |
| FAIL — no PI created | 30 |
| FAIL — PI created with wrong expense_account | 2 |
| DEFECT_CONFIRMED — S243-fixed stores miss cost_center | 4 |

## Discovered defects (full detail in `DEFECTS.md`)

| ID | Affected stores | Root cause | Severity |
|---|---|---|---|
| A | 4 (ROA, SMM, SMMM, SMS) | Missing `Company.cost_center` after S243 | CRITICAL |
| B | 32 | Missing `Company.stock_received_but_not_billed` when `enable_perpetual_inventory=1` | CRITICAL |
| C | 2 visible (potentially all 32 once B unblocked) | ERPNext `set_expense_account(for_validate=True)` overrides `1104210 - Inventory-from-Commissary` with `Warehouse.account` | CRITICAL |
| D | 13 "PASS" stores | `enable_perpetual_inventory=0` silently drops design intent — PIs create but post zero stock GL | INFORMATIONAL |

## Architectural decision needed

Three viable paths (see DEFECTS.md):

1. **Disable perpetual everywhere** — fast, but design intent lost on all stores.
2. **Set SRBNB + Warehouse.account=1104210 per store** — ERPNext-canonical, more data fixes.
3. **Redesign generator** to `update_stock=0` + separate Stock Entry — clean separation, larger sprint.

**Pending decision from Sam + Denise (head of finance).**

## Methodology

1. **Per-store readiness probe** (`probe_result.json`) — read-only. Confirmed all 45 canonical stores have Customer/Warehouse/accounts/PHP currency/cost_center (4 stores excepted for DEFECT A).
2. **BEI Store Order resolution** (`order_probe_result.json`) — found real existing orders per store to populate SI's `custom_bei_store_order` link.
3. **Live-fire sweep** (`sweep_result.json`) — created+submitted+verified+cancelled+force-deleted 49 test SIs. Each iteration tracked via in-memory ledger; finally block force-cleans any artifact left behind.
4. **Aftermath probe** (`aftermath_result.json`) — confirmed 0 leftover SIs, 0 leftover PIs, 0 orphan PIs.
5. **Single-failure deep dive** (`one_failure_result.json`) — ran one failing store (AFT) with full-traceback capture, bypassing the generator's savepoint catch to see ERPNext's raw error.
6. **Per-Company config audit** (`perp_result.json`) — read `enable_perpetual_inventory`, `stock_received_but_not_billed`, `stock_adjustment_account` per Company. Pattern PASS=0, FAIL=1 was clean and total — perpetual inventory flag is the sole differentiator.

## What was NOT done (per Sam's decision)

- ❌ No fix PR opened
- ❌ No master-data UPDATE to Company.cost_center / SRBNB / Warehouse.account
- ❌ S245 sprint (4-store cost_center fix) NOT executed
- ❌ Cleanup of historical 839 test BKI SIs NOT performed (still a separate follow-up)

## Test artifacts (in this PR)

- `output/l3/billing-sweep-2026-05-11/SUMMARY.md` (this file)
- `output/l3/billing-sweep-2026-05-11/DEFECTS.md`
- `output/l3/billing-sweep-2026-05-11/GAP_ANALYSIS.md`
- `output/l3/billing-sweep-2026-05-11/evidence/probe_result.json` (per-store readiness)
- `output/l3/billing-sweep-2026-05-11/evidence/order_probe_result.json`
- `output/l3/billing-sweep-2026-05-11/evidence/sweep_result.json`
- `output/l3/billing-sweep-2026-05-11/evidence/aftermath_result.json`
- `output/l3/billing-sweep-2026-05-11/evidence/one_failure_result.json`
- `output/l3/billing-sweep-2026-05-11/evidence/perp_result.json`
- `scripts/billing_sweep/multi_store_smoke.py` (reusable runner)
- `scripts/billing_sweep/probe_per_store_readiness.py`
- `scripts/billing_sweep/probe_perpetual_inventory.py`
- `scripts/billing_sweep/run_*.py` (SSM wrappers — all use the same gzip+base64 file exfil pattern)

## Follow-up sprint candidates (in order of urgency)

1. **S245-A** (post-decision) — implement Option 1, 2, or 3 from the architectural choice
2. **S246** — cleanup of 839 historical test BKI SIs (sliced from the S238 build phase)
3. **S247** — extend `verify_canonical_structure.py` to assert `enable_perpetual_inventory + SRBNB + cost_center + Warehouse.account` triad per store
4. **S248** — finance review checkpoint with Denise on the ICT-003 GL model before deploying any of the above
