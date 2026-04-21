# S213 — Sweep Verification Summary (FINAL)

**Sprint:** S213 — FG004 NULL-batch backfill at BKI warehouses
**Status:** COMPLETED-PARTIAL
**Closeout date:** 2026-04-21 (Tuesday) PHT
**Signoff:** Sam Karazi (CEO, BEI)

---

## Bottom line

S213 delivered the code+data fix for DEFECT-6 (NULL-batch stock at BKI warehouses). Backfill assigned real batch_no to 22,904 units of stock across 36 (item, warehouse) tuples. Net result: **47% pass rate (7/15)**, up from S212 R1's 37% (3/8).

The 48/49 goal was NOT reached because the sweep exposed **DEFECT-7 (inventory shortages)** — legitimate data state where raw materials (PM001, PM007, KL004, PLASTIC 8x11) at Pinnacle Cold Storage don't have enough Bin qty for the test fixture's suggested order quantities.

## What DEFECT-6 fixed

**Before S213 backfill (S212 R1):**
- 3 stuck MRs (AYALA SOLENAD, AYALA VERMOSA, CTTM TOMAS MORATO) failed because FG004 at PINNACLE had `batch_no=NULL` in Stock Ledger — ERPNext blocks dispatch.
- 36 (item, warehouse) tuples had this issue across 11 items and 4 BKI warehouses.
- 22,904 units of stock affected.

**After S213 backfill:**
- All 36 tuples have real batch_no (auto-generated `BACKFILL-20260421-<item>-<wh-short>`).
- 22,904 units now properly batch-tracked.
- 7/15 sweep attempts pass (up from 3/8 baseline).
- AYALA FAIRVIEW TERRACES (Company Owned store_type) now passes via S212 DEFECT-5 fix — proof that DEFECT-5 is working in prod.

## Results table

| Metric | S212 R1 | S213 R1 |
|---|---|---|
| Attempted | 8 | 15 |
| PASS | 3 (37%) | 7 (47%) |
| FAIL — MR-create (inventory) | 1 | 5 |
| FAIL — dispatch-not-registered | 3 | 3 |
| FAIL — WR-receive timeout | 0 | 1 |
| FAIL — SI creation (S203) | 1 | 0 (DEFECT-5 fixed) |
| Monitor kill fingerprint | DispatchPage | MR-create |
| Monitor kill threshold | same-fp=3 | same-fp=5 |

## Passing stores in S213 R1

1. ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC (Managed Franchise)
2. AYALA FAIRVIEW TERRACES - BEBANG FT INC. (**Company Owned — NEW PASS, validates DEFECT-5**)
3. AYALA UP TOWN CENTER - BEBANG UP TOWN CENTER INC. (JV)
4. BF HOMES - BEBANG BF HOMES INC. (JV)
5. **EVER COMMONWEALTH - DLS DESSERT CRAFT INC.** (NEW PASS after batch backfill)
6. **LUCKY CHINATOWN - BEBANG LCT INC.** (NEW PASS after batch backfill)
7. **MEGAWORLD PASEO CENTER - BEBANG PASEO INC.** (NEW PASS after batch backfill)

## DEFECT-7 (NEW, data) — Inventory shortages at Pinnacle Cold Storage

The Frappe Error Log during the sweep window shows 5 explicit S163-gate throws:

```
MR Creation Error for Store Order BEI-ORD-2026-00400
  Stock decreased between resolution and dispatch —
  SCM must re-resolve order line for PM001 (have 99.0, need 1438.0) at Pinnacle Cold Storage Solutions - BKI.

MR Creation Error for Store Order BEI-ORD-2026-00408
  ... PM007 (have 475.0, need 1148.0) at Pinnacle ...

MR Creation Error for Store Order BEI-ORD-2026-00410
  ... PM007 (have 475.0, need 767.0) at Pinnacle ...

MR Creation Error for Store Order BEI-ORD-2026-00412
  ... PM007 (have 475.0, need 1144.0) at Pinnacle ...

MR Creation Error for Store Order BEI-ORD-2026-00413
  ... KL004 (have 0.0, need 1.0) at Pinnacle ...
```

This is the S163 audit-fix inventory gate firing **correctly**. The actual Bin qty is less than what the test fixture's `get_orderable_items` suggested. Not a code bug.

**Remediation options for S214:**
1. **Data:** operations replenishes PM001/PM007/KL004/PLASTIC 8x11 at Pinnacle
2. **Fixture:** `s209_generate_fixture.py` should cap suggested_qty to min(suggested, bin_actual)
3. **Both** (recommended)

## DEFECT-8 (NEW, investigation) — Remaining dispatch mysteries

3 stores still fail at dispatch-not-registered AFTER S213 backfill:
- AYALA SOLENAD - HFFM SOLENAD FOOD SERVICES INC.
- AYALA VERMOSA - BEBANG MEGA INC.
- CTTM TOMAS MORATO - B CUBED VENTURES CORP.

Direct reproduction showed 1 of 3 threw `Not enough stock: PLASTIC 8x11 CALYPSO` (another inventory shortage). The other 2 completed silently in repro — suggesting a race or UI-level issue that differs between real sweep and direct repro. Needs deeper investigation (S214 scope).

## DEFECT-9 (NEW) — WR receive timeout

D'VERDE CALAMBA - TAJ FOOD CORP. completed order → MR → SE → WR creation but WR never reached status=Completed within the test's 45s window. May be a stock-reservation race or a post-submit hook slow-path. Needs S214 investigation.

## Monitor performance

```
[2026-04-21T11:55:52] MONITOR START kill-same-fp=5 kill-pass-rate-below=0.5 kill-after-n=10 dry-run=False
...
[2026-04-21T12:22:30] KILL pid=1684952 reason=same-fingerprint=5 >= 5
  | fp=Material Request for order <ORDER> (polled 30000ms, last=0)
```

- Kill threshold tuned from 3 (S212) to 5 (S213) for more tolerance.
- Killed at 26 minutes in (still saving wall-clock vs unmonitored 60-min run).
- Correctly normalized 5 different order docnames into one bucket.

## Canonical drift

Preflight + postcheck identical (only CommandId differs — SSM timestamp).
`[RESULT] VIOLATIONS FOUND` shows only the allowed ORTIGAS GREENHILLS TIN skip.
**Zero net drift.**

## Cleanup

- 16 orders, 11 MRs, 8 SEs, 8 WRs, 7 SIs created during sweep.
- All cleaned: SIs cancelled (7), WRs deleted/cancelled (8), SEs cancelled via MR resuscitate pattern (8), MRs re-cancelled (11), orders cancelled (16).
- Ledger reset to `[]`.
- Test area access reverted (49 warehouses, 0 changes — snapshot unchanged).

## RRC status

- [x] RR-01 — Canonical preflight (allowed skip only)
- [x] RR-02 — Audit emits 36 NULL-batch tuples across 4 BKI warehouses
- [x] RR-03 — Audit confirms FG004 specifically at PINNACLE + 3MD
- [x] RR-04 — Backfill creates Batch + updates SLE + recomputes batch_qty
- [x] RR-05 — All new `tabBatch` rows have `item`, `batch_qty`
- [x] RR-06 — Post-backfill audit: 0 NULL-batch tuples
- [x] RR-07 — Bin qty unchanged (labeling, not moving)
- [⚠] RR-08 — S212 sweep rerun hit 7/15 (47%), NOT 48/49 — blocked by DEFECT-7
- [⚠] RR-09 — V1 did not run (monitor killed sweep first)
- [⚠] RR-10 — V2 did not run
- [x] RR-11 — Canonical postcheck identical to preflight
- [x] RR-12 — Cleanup ledger `pendingEntries === 0`
- [x] RR-13 — PRs created (closeout)
- [x] RR-14 — Plan YAML `COMPLETED-PARTIAL` + registry updated

## Follow-up reference (S214)

**S214** — Inventory replenishment + fixture cap + dispatch-mystery investigation
- DEFECT-7: Replenish PM001, PM007, KL004, PLASTIC 8x11 at Pinnacle OR cap fixture qty at Bin actual
- DEFECT-8: Investigate AYALA SOLENAD / AYALA VERMOSA / CTTM TOMAS MORATO dispatch-not-registered
- DEFECT-9: Investigate D'VERDE CALAMBA WR timeout
- Rerun monitored sweep after fixes

## Reusable infrastructure (owned by S213)

- `scripts/s213_audit_null_batches.py` — audit batch-tracked items at BKI warehouses (idempotent, re-runnable)
- `scripts/s213_backfill_null_batches.py` — assign batches via direct SLE UPDATE (safe for labeling, not qty-moving)
- `scripts/s213_cleanup_remaining_ses.py` — SE cancel via MR-resuscitate pattern for ledger MRs
- `scripts/s213_probe_errors.py` — Frappe error log scoped to sweep window

All reusable by future L3 sprints on batch-tracked items.
