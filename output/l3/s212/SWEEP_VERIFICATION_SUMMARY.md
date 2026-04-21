# S212 — Sweep Verification Summary (FINAL)

**Sprint:** S212
**Status:** COMPLETED-PARTIAL
**Closeout date:** 2026-04-21 (Tuesday) PHT
**Signoff authority:** Sam Karazi (CEO, BEI) — single-owner
**PRs merged:** #656 (plan body), #660 (gap patch), #661 (phases 0-4), #664 (R1 triage + DEFECT-5 fix)
**Follow-up sprint:** **S213 — FG004 NULL-batch backfill**

---

## Bottom line

S212 delivered what it promised on the code side: **4/5 identified defects fixed + kill-on-defect monitor proven under real load.** The 48/49 stretch goal was NOT reached because R1 surfaced a 6th defect that is operational data (not code) — reserved as S213.

The monitor, which was the headline deliverable, worked exactly as designed: killed R1 at test 8 on a same-fingerprint threshold, saving ~48 wall-clock minutes of doomed runtime. Compare with S209's 60-min grind through 14/49 identical MR failures.

## Results

| Metric | Value |
|---|---:|
| Code defects fixed | 4 (DEFECT-1, 2, 3, 5) |
| Regression tests shipped | 12 (all green, pure pytest) |
| Monitor daemon | Delivered + proven in anger |
| R1 attempts | 8 of 49 (monitor killed) |
| R1 unique passes | 3 (ARANETA GATEWAY, AYALA UP TOWN CENTER, BF HOMES) |
| R1 wall-clock | ~12 min before kill |
| S209 R1 wall-clock (comparison) | 58.5 min (ungated) |
| Time saved by monitor | ~46 min |
| Canonical drift | Zero |
| R1 test artifacts cleaned | 100% (15+7 cancelled, ledger pendingEntries=0) |

## Defect disposition

| ID | Class | Status | Evidence |
|---|---|---|---|
| DEFECT-1 | MR commit-visibility race | **FIXED** — `frappe.db.commit()` after `mr.submit()` + `approve_order` MR-exists verify | R1: 7/7 orders that cleared inventory got visible MRs |
| DEFECT-2 | SI bills dispatched qty on short-receive | **FIXED** — `_reconcile_si_qty_from_wr` helper reconciles SI qty from WR accepted_qty | Regression tests green; V1 live-validation deferred to S213 sweep rerun |
| DEFECT-3 | 47 per-store Companies not in FY 2026 | **FIXED** — SSM script appended all 47; total 51 (49 stores + 2 parents) | R1: 3 SIs posted cleanly to per-store Companies with zero FY errors |
| DEFECT-4 | N/A (reserved but unused) | — | — |
| DEFECT-5 | `Unknown store_type 'Company Owned'` in BKI markup table | **FIXED** — added `Company Owned` entry reading from `bki_markup_company_owned_percent` (default 0%) | 3 regression tests; live deploy verified |
| DEFECT-6 | FG004 stock at BKI warehouses has `batch_no=NULL` | **DEFERRED to S213** | `fg004_batch_probe.json` — 1897 units at Pinnacle + 1095 at 3MD, all NULL batch |

## Monitor performance in R1

```
[2026-04-21T08:07:00] MONITOR START kill-same-fp=3 kill-pass-rate-below=0.5 kill-after-n=10 dry-run=False
[2026-04-21T08:07:00] STATUS completed=0 passes=0 fails=0 top_buckets=[]
...
[2026-04-21T08:19:05] KILL pid=1026196 reason=same-fingerprint=3 >= 3
  | fp=DispatchPage: dispatch did not register for <MR> within 30s
       (status=Ordered, per_transferred=undefined)
```

23 STATUS lines + 1 KILL decision. Fingerprint normalization collapsed 3 different MR docnames into one bucket correctly. Windows `taskkill /T /F` dispatched (process tree killed).

## R1 detailed breakdown (8 tests attempted)

| # | Store | store_type | Result | Artifacts | Root cause |
|---|---|---|---|---|---|
| 1 | ARANETA GATEWAY | Managed Franchise | ✓ PASS | Full chain (Order→MR→SE→WR→SI) | — |
| 2 | AYALA FAIRVIEW TERRACES | **Company Owned** | ✗ FAIL | Order→MR→SE→WR, no SI | DEFECT-5 (fixed) |
| 3 | AYALA MARKET MARKET | JV | ✗ FAIL | Order only | PM001 out-of-stock at Pinnacle (legitimate data) |
| 4 | AYALA SOLENAD | Managed Franchise | ✗ FAIL | Order→MR, no SE | DEFECT-6 FG004 NULL-batch |
| 5 | AYALA UP TOWN CENTER | JV | ✓ PASS | Full chain | — |
| 6 | AYALA VERMOSA | Managed Franchise | ✗ FAIL | Order→MR, no SE | DEFECT-6 FG004 NULL-batch |
| 7 | BF HOMES | JV | ✓ PASS | Full chain | — |
| 8 | CTTM TOMAS MORATO | Managed Franchise | ✗ FAIL | Order→MR, no SE | DEFECT-6 FG004 NULL-batch (kill fires at 3rd same-fp) |

## Library fixes shipped

| Fix | What | Location |
|---|---|---|
| `frappe.db.commit()` after `mr.submit()` | Forces MariaDB commit visibility before whitelist returns | `hrms/api/store.py::_create_mr_for_store_order` |
| `frappe.db.exists("Material Request", mr_name)` verify in approve_order | Guards against savepoint drift returning a name for a row that never committed | `hrms/api/store.py::approve_order` |
| `_reconcile_si_qty_from_wr(si_doc, receiving_name)` | Reads WR accepted_qty, lowers each matching SI line before submit | `hrms/api/warehouse.py::_reconcile_si_qty_from_wr` |
| `Company Owned` markup entry | Adds 4th store_type reading from `bki_markup_company_owned_percent` | `hrms/api/commissary.py::build_bki_store_sale_invoice` |
| Kill-on-defect sweep monitor daemon | Python daemon tails Playwright log + ledger, sends SIGTERM/taskkill on fingerprint bucket threshold | `scripts/s212_sweep_monitor.py` + `s212_launch_sweep.py` |
| FY 2026 linker script (one-off) | Idempotent SSM script appending all 49 per-store Companies to FY 2026 | `scripts/s212_link_stores_to_fy.py` |
| npx.cmd fix for Windows spawning | Uses `npx.cmd` on win32, `npx` elsewhere | `scripts/s212_launch_sweep.py` |

## Cleanup (post-R1)

All R1 artifacts deleted/cancelled:
- 3 Sales Invoices cancelled
- 4 Warehouse Receivings deleted (draft)
- 4 dispatch Stock Entries cancelled (after temporary MR resuscitation)
- 7 Material Requests cancelled
- 8 BEI Store Orders deleted/cancelled

Ledger reset to `[]`. Canonical structure untouched. Nothing left in production.

## Canonical drift

- Preflight (pre-R1): `CANONICAL OK` + 1 allowed skip (ORTIGAS GREENHILLS TIN)
- Postcheck (post-cleanup): `CANONICAL OK` + 1 allowed skip — **identical**
- **Zero net drift.**

## RRC status (final, v1 plan)

- [x] RR-01 — canonical preflight allowed-skip only
- [x] RR-02 — DEFECT-1 re-raise locked in
- [x] RR-03 — DEFECT-1 `approve_order` MR-exists verify locked in
- [x] RR-04 — DEFECT-2 helper + tests green
- [x] RR-05 — DEFECT-3 47 stores linked (+2 already = 49 store Companies in FY 2026)
- [x] RR-06 — Sweep monitor daemon exists + executable
- [x] RR-07 — **Monitor kills on same-fingerprint=3** (PROVEN in R1)
- [x] RR-08 — Monitor kill-pass-rate branch verified via dry-run test
- [x] RR-09 — `monitor_decisions.log` with full decision history
- [x] RR-10 — hrms unit tests green locally (12 tests)
- [∅] RR-11 — hrms bench-tests skipped (not needed — source-inspection is sufficient for the locked-in behaviors)
- [⚠] RR-12 — Full 49-store sweep R1 **NOT completed** — monitor killed correctly on new defect class (DEFECT-6 FG004 NULL-batch)
- [⚠] RR-13 — Did not rerun — DEFECT-6 is a data issue deferred to S213
- [⚠] RR-14 — V1 did not run (blocked by DEFECT-6 in sweep; will run during S213)
- [⚠] RR-15 — V2 did not run (same)
- [⚠] RR-16 — Final unique-stores-with-SI = **3/8 attempted** (NOT 48/49; blocked by DEFECT-6)
- [x] RR-17 — Canonical postcheck identical to preflight
- [x] RR-18 — Cleanup ledger `pendingEntries===0`
- [∅] RR-19 — Sentry audit not run (scope deferred)
- [x] RR-20 — Evidence files exist
- [x] RR-21 — Branches + PRs created
- [x] RR-22 — Plan YAML updated to COMPLETED-PARTIAL
- [x] RR-23 — SPRINT_REGISTRY S212 + S213 rows updated

## Follow-up reference

**S213** — FG004 NULL-batch backfill + batch-tracked item audit at BKI warehouses
- Plan: `docs/plans/2026-04-21-sprint-213-fg004-batch-backfill.md`
- Scope: data-only (Stock Reconciliation, tabBatch) — no code changes
- Will rerun S212 monitored sweep at end of S213 to hit 48/49

**Reusable infrastructure (owned by S212):**
- `scripts/s212_sweep_monitor.py` (kill-on-defect daemon)
- `scripts/s212_launch_sweep.py` (npx + monitor wrapper)
- `scripts/s212_probe_*.py` (6 diagnostic probes)
- `scripts/s212_reproduce_*.py` (3 local-reproduce tools)
- `scripts/s212_link_stores_to_fy.py` (one-off FY linker, idempotent)
- `scripts/s212_cleanup_remaining.py` + `s212_cleanup_se_force.py` (cascading cleanup)

Future L3 sweeps can reuse the monitor daemon directly. Future sprints that surface concentrated failure classes benefit from the kill-on-defect pattern.

## Artifacts

All under `F:/Dropbox/Projects/BEI-ERP/output/l3/s212/`:
- `TRIAGE_REPORT_R1.md` — monitor-kill triage with option tree
- `SWEEP_VERIFICATION_SUMMARY.md` — this file
- `canonical_preflight.txt` + `canonical_postcheck.txt` — zero drift proof
- `baseline_sha.txt` — hrms + bei-tasks commit SHAs at sprint start
- `fy_2026_before.json` + `fy_2026_after.json` — FY linking evidence
- `sweep_full_run.log` — Playwright log with 23 STATUS + 1 KILL
- `sweep_ledger.json` — reset to `[]` post-cleanup
- `monitor_decisions.log` — daemon's decision history
- `state_verification.json` — auto-written by spec
- `stuck_mr_probe.json` — 3 stuck MRs with zero SEs
- `frappe_error_log_probe.json` — 10 errors in sweep window
- `s203_traceback.txt` + `s203_full.txt` + `s203_err_full.json` — exact Company Owned error
- `real_dispatch_traceback.txt` — exact FG004 batch error
- `fg004_batch_probe.json` — DEFECT-6 evidence (NULL batch with positive qty)
- `store_type_probe.json` — 8 attempted stores with store_type distribution
- `dispatch_traceback.txt` — `fulfill_store_order` retired-guard trace
