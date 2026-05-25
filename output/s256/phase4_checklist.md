# Phase 4 (a+b+c) Checklist — Source-of-Truth Redesign

## Phase 4a — Procurement App SOA seed

| Task | Status | Evidence |
|---|---|---|
| 4a.1 PROCUREMENT_APP_ID const | DONE | Line ~48 in v3.10 |
| 4a.2 seedFromProcurementApp_ function | DONE | ~130 lines; reads PO tab, filters approved, maps to 19-col schema, dedup via existingIndex |
| 4a.3 Wired into doRefreshAllTabs_v3_ | DONE | After FPM seed, before Denise PP seed |
| 4a.4 SOURCE='Procurement App' rows target Suppliers SOA | DONE | Covered by existing 4-tab forEach |
| 4a.5 Banner unaffected | DONE | Banner iterates ALL rows; SOURCE doesn't affect totals |
| 4a.6 verify_phase4a.py | DONE | ALL PASS |

## Phase 4b — Denise PP opening-balance-only

| Task | Status | Evidence |
|---|---|---|
| 4b.1 Cutover documented | DONE | `output/s256/payment_plan_mirror_cutover_v2_runbook.md` |
| 4b.2 denise_pp_seed_disabled flag | DONE | Const at line ~71; early-exit with `{seed_disabled: true}` |
| 4b.3 Dual-source documented | DONE | Runbook requires 3+ consecutive cycles before cutover |

## Phase 4c — 05-AP Opening Balance HO wiring

| Task | Status | Evidence |
|---|---|---|
| 4c.1 HO_OPENING_BALANCE_ID const | DONE | Line ~49 |
| 4c.2 seedHoOpeningBalanceOnce_ function | DONE | ~95 lines; reads opening file, dedup, appends to HO, creates flag tab |
| 4c.3 Idempotency via _ho_opening_loaded flag tab | DONE | Checks existence before running; creates after first load |
| 4c.4 CAPEX wiring | DONE (no-op) | Current CAPEX tab on AP Master already serves as opening balance; no separate seed needed |
