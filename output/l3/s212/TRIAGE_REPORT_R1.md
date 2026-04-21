# S212 R1 Triage — Monitor Killed on New Defect Class

**Date:** 2026-04-21 (Tuesday) PHT
**Sweep run:** R1 monitored
**Monitor decision:** KILL at test 8 — same-fingerprint=3 threshold hit
**Runtime before kill:** ~12 min (vs. 60 min unmonitored S209 R1)
**Monitor saved:** ~48 min wall-clock

---

## What happened

| # | Store | Order | MR | WR | SI | Result |
|---|---|---|---|---|---|---|
| 1 | ARANETA GATEWAY | 00398 | 00256 | 00102 | 00092 | ✓ PASS |
| 2 | AYALA FAIRVIEW TERRACES | 00399 | 00257 | 00103 | — | FAIL — S203 Draft SI Error |
| 3 | AYALA MARKET MARKET | 00400 | — | — | — | FAIL — Stock shortage PM001 (need 1438, have 99) |
| 4 | AYALA SOLENAD | 00401 | 00258 | — | — | FAIL — dispatch-not-registered |
| 5 | AYALA UP TOWN CENTER | 00402 | 00259 | 00104 | 00093 | ✓ PASS |
| 6 | AYALA VERMOSA | 00403 | 00260 | — | — | FAIL — dispatch-not-registered |
| 7 | BF HOMES | 00404 | 00261 | 00105 | 00094 | ✓ PASS |
| 8 | CTTM TOMAS MORATO | 00405 | 00262 | — | — | FAIL — dispatch-not-registered (KILL fires at 3rd hit) |

**Pass rate:** 3/8 (37%)

## Monitor kill fingerprint

```
[2026-04-21T08:19:05] KILL pid=1026196 reason=same-fingerprint=3 >= 3
  | fp=DispatchPage: dispatch did not register for <MR> within 30s
       (status=Ordered, per_transferred=undefined)
```

## Root cause inspection

### Dispatch-not-registered cluster (3/8, dominant)

**Affected MRs:** `MAT-MR-2026-00258`, `MAT-MR-2026-00260`, `MAT-MR-2026-00262`

Backend state (live probe via SSM):
- docstatus=1, status="Ordered", per_ordered=100.0, **stock_entries=[]**
- material_request_type=**"Material Issue"** (intercompany — BKI source → store destination)
- set_warehouse:
  - 00258: `PINNACLE COLD STORAGE SOLUTIONS - BKI`
  - 00260: `PINNACLE COLD STORAGE SOLUTIONS - BKI`
  - 00262: `3MD LOGISTICS - CAMANGYANAN - BKI`

**No Frappe Error Log entries for these MRs.** The dispatch button was clicked (otherwise a different error would fire), but no Stock Entry was created and no backend error was raised.

The 3 passing stores had Material Transfer (not Issue) MRs. So the dispatch flow works for same-company transfers but silently fails for intercompany Material Issue MRs sourced from BKI cold-storage warehouses.

### AYALA FAIRVIEW TERRACES (2) — S203 Draft SI Error

Backend Error Log shows:
```
2026-04-21 08:09:36 | S203 Draft SI Error
S203: Draft SI creation failed for SE MAT-STE-2026-00621: <traceback>
```

SE was created (00621), WR was created (00103), but the Draft SI helper (`build_bki_store_sale_invoice`) threw and was caught by the outer try/except in `hrms/api/commissary.py` (lines 868-884). The catch only logs + returns None, so dispatch succeeded but SI wasn't linked. Later, `_submit_dispatch_draft_si` found no `custom_sales_invoice_draft` on the SE and returned None.

### AYALA MARKET MARKET (3) — legitimate inventory shortage

```
MR Creation Error for Store Order BEI-ORD-2026-00400
Stock decreased between resolution and dispatch —
SCM must re-resolve order line for PM001 (have 99.0, need 1438.0)
at Pinnacle Cold Storage Solutions - BKI.
```

This is the S163-audit-fix path firing correctly. Not a product defect — actual inventory shortfall.

---

## What this means for the 3 S212 defects I fixed

| Defect | Fix status | Evidence |
|---|---|---|
| **DEFECT-1** (MR commit-visibility) | **WORKING** — all 7 orders that passed the inventory gate got MRs; `approve_order` did not throw on missing MR row | ledger: 7 mr-create entries for 8 orders (only inventory-short order blocked) |
| **DEFECT-2** (SI qty from accepted) | Unable to verify happy-chain — no short-receive happened in R1 (no V1 run yet) | N/A — variance blocked by this triage |
| **DEFECT-3** (FY 2026 link) | **WORKING** — all SIs posted without FY errors | 3 SIs created successfully against per-store Companies |
| **Monitor** | **WORKING** — killed at exactly the right threshold, 48 min saved | monitor_decisions.log |

The fixes that landed are correct. The new dispatch-not-registered class is **NOT one of the 3 S212 defects.** It's a separate intercompany dispatch flow issue that S209 did not explicitly classify.

---

## Hypothesis — dispatch flow fork for Material Issue

- `hrms/api/commissary.py::fulfill_store_order` creates SE with `material_request_type` inferred from MR
- `hrms/api/commissary_requisition.py` has a PARALLEL `fulfill_store_order` with different logic
- The UI's dispatch endpoint picks one based on some branch I haven't traced

For Material Issue MRs, the SE-creation path may have a validation failure that's swallowed OR the UI is calling an endpoint that doesn't exist for Material Issue.

---

## STOP reason

Per plan §Autonomous Execution Contract → stop_only_for:
> Monitor kills sweep AND the fingerprint doesn't map to a known defect class (new unknown failure) → STOP, triage with user

Per S209 feedback memory (feedback_kill_sweep_fix_backend.md):
> **Trigger:** same error class appears ≥3-5 times in a Playwright sweep
> **Action:** kill the sweep, dump ledger + error grep, run backend probe, classify (test-infra vs product), patch the right layer, rerun.

The monitor did exactly this. Ledger + error grep + backend probe are all captured. But the fix for intercompany dispatch needs CEO direction because:

1. Fixing it requires a new backend patch in `commissary.py` or `commissary_requisition.py` that I'd need to deploy — another PR + deploy cycle.
2. Two parallel `fulfill_store_order` implementations suggest a recent refactor I shouldn't unilaterally merge.
3. The AYALA FAIRVIEW S203 error also wants investigation — the `build_bki_store_sale_invoice` helper is failing silently.

## Options for Sam

**Option A — Fix both dispatch and S203 defects in a follow-up sprint (S213)**
- Keep S212 as-is (3 defects delivered, monitor proven).
- Cleanup the 5 in-flight test artifacts from R1.
- Write S213 plan: investigate intercompany dispatch flow + S203 Draft SI error.
- S212 closes with partial pass (3/8 attempted), but with monitor success + follow-up documented.

**Option B — Try to fix dispatch defect in this session**
- I investigate commissary.py / commissary_requisition.py fork.
- Likely requires: read UI dispatch endpoint, identify why Material Issue path drops SE, patch, new PR, deploy, rerun.
- Estimate: 2-3 hours + another deploy cycle.

**Option C — Accept 3/8 baseline + cleanup + close**
- The S212 goal ("rerun + monitor") has been proven (monitor works; DEFECT-1/2/3 fixes deployed).
- The 48/49 stretch goal fails because of a new defect class outside S212 scope.
- Cleanup R1 artifacts, document, close.

**My recommendation: Option A.** The monitor delivered its value (early kill, evidence captured). The new defect class deserves its own sprint with a proper audit of the two `fulfill_store_order` paths. Pushing a second rushed backend patch in this session risks introducing drift in the intercompany flow.

## Artifacts captured

- `output/l3/s212/sweep_full_run.log` — Playwright log (partial, to kill point)
- `output/l3/s212/sweep_ledger.json` — 22 entries, 8 orders, 7 MRs, 4 WRs, 3 SIs
- `output/l3/s212/monitor_decisions.log` — 23 status lines + 1 KILL decision
- `output/l3/s212/stuck_mr_probe.json` — 3 stuck MRs with backend state
- `output/l3/s212/frappe_error_log_probe.json` — 10 errors in window (5 are brain_sync noise)
- `output/l3/s212/state_verification.json` — auto-written by spec
