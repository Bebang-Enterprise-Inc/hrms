---
sprint: S213
title: FG004 NULL-batch backfill + batch-tracked item audit at BKI warehouses
branch: s213-fg004-batch-backfill
base: production
status: PLANNED
plan_version: v1
plan_date: 2026-04-21
canonical_scope: in
canonical_model_reference: docs/STORE_COMPANY_CANONICAL.md
canonical_preflight: required
depends_on:
  - S212 COMPLETED-PARTIAL (PR #661 + #664 merged) — backend defect fixes + monitor shipped
  - S212 R1 triage evidence proving NULL-batch stock is a data issue, not a code bug
execution_mode: autonomous
signoff_authority: single-owner (Sam, CEO)
execution_summary:
---

# S213 — FG004 NULL-batch Backfill + Batch-Tracked Item Audit at BKI Warehouses

## Registry lock (evidence)

```text
| `S213` | Sprint 213 | `s213-fg004-batch-backfill` (hrms — data-only, SSM script) | TBD | PLANNED 2026-04-21 — FG004 NULL-batch backfill + batch-tracked item audit ... | docs/plans/2026-04-21-sprint-213-fg004-batch-backfill.md |
```

---

## 🟥 Canonical Model Preflight (Mandatory)

```bash
python scripts/verify_canonical_structure.py
```

Accept only these two outcomes:
- `[RESULT] ALL CANONICAL — no action required`
- 1 allowed skip (`BILLING_CUST_TIN_EMPTY` on ORTIGAS GREENHILLS)

Any other `[VIOLATION]` → STOP and ask user.

**Canonical law (summary):** S213 is a DATA cleanup on `tabStock Ledger Entry` + `tabBatch` + `tabStock Reconciliation`. It does NOT touch Company/Warehouse/Customer master data. Scope:
- Reads: `tabStock Ledger Entry`, `tabBin`, `tabBatch`, `tabItem` (filter `has_batch_no=1`)
- Writes: new `Stock Reconciliation` docs to assign batch_no to existing NULL-batch qty
- Does NOT touch: `tabCompany`, `tabWarehouse`, `tabCustomer`, `tabSales Invoice`, `tabMaterial Request`, `tabBEI Store Order`

---

## Canonical Model Binding

| Canonical surface | How S213 uses it |
|---|---|
| `Warehouse.name` | Reads to scope the audit (BKI parent warehouses) |
| `Company` | Read-only (scoped to BKI Company's warehouses) |

S213 does NOT:
- Create / rename / disable Warehouses
- Create / modify Customers or Companies
- Touch any SI, MR, SE, WR, PO created by prior sprints

---

## Design Rationale

### Why this exists

S212 R1 monitored sweep killed at test 8 with same fingerprint `DispatchPage: dispatch did not register for <MR>`. Triage (see `output/l3/s212/TRIAGE_REPORT_R1.md`) identified DEFECT-6:

Evidence (`output/l3/s212/fg004_batch_probe.json`):
- FG004 has `has_batch_no=1` (batch-tracked)
- `tabBin` at PINNACLE COLD STORAGE SOLUTIONS - BKI: `actual_qty=1897`, reserved=0
- `tabBin` at 3MD LOGISTICS - CAMANGYANAN - BKI: `actual_qty=1095`, reserved=0
- `tabStock Ledger Entry` SUM by warehouse+batch_no shows:
  - PINNACLE COLD STORAGE: `batch_no=NULL qty=1897`
  - 3MD LOGISTICS: `batch_no=NULL qty=1095`
- 20 `tabBatch` rows exist for FG004 (all `SYNC-*-FG004`) but NONE are linked to this stock

**Root cause:** somebody posted stock-in entries (likely opening inventory import) without providing a batch_no. Later dispatch tries to consume that stock and ERPNext's `validate_serial_batch_no_bundle` throws `Serial No / Batch No are mandatory for Item FG004`.

This is NOT code. Backend logic correctly enforces batch-tracking rules. The fix is to assign the NULL-qty to a real batch.

### Why this architecture

**Stock Reconciliation, not UPDATE tabStock Ledger Entry.** Frappe treats Stock Ledger Entry as append-only audit trail. Direct SQL mutation breaks fiscal immutability and corrupts the ledger. Stock Reconciliation is the official Frappe doc for qty adjustments — creates compensating SLE rows, preserves history, triggers all downstream hooks (bin recompute, GL).

**Batch naming convention:** `BACKFILL-YYYYMMDD-<item>-<warehouse-short>` — e.g. `BACKFILL-20260421-FG004-PINNACLE`. Grep-friendly, identifiable, won't collide with production `SYNC-*` batches.

**Audit first, then backfill.** Query every `has_batch_no=1` item across all BKI-owned warehouses (3MD, Pinnacle, Commissary - BKI). Identify which items have NULL-batch qty. Generate a fix plan, review, then post reconciliations. Prevents the "fix FG004 only, rerun sweep, discover FG005 has the same issue" anti-pattern.

**Rejected alternative:** Modify `build_bki_store_sale_invoice` to accept items without batches. Would violate BIR traceability requirements (every physical qty must trace to a batch for food safety recalls).

**Rejected alternative:** Ask operations to do it manually. 49 stores × unknown number of batch-tracked items = hundreds of Stock Reconciliation entries. Script is auditable + reruns on new stores.

### Source references

- S212 triage: `F:/Dropbox/Projects/BEI-ERP/output/l3/s212/TRIAGE_REPORT_R1.md`
- FG004 probe: `F:/Dropbox/Projects/BEI-ERP/output/l3/s212/fg004_batch_probe.json`
- Dispatch error (real): `F:/Dropbox/Projects/BEI-ERP/output/l3/s212/real_dispatch_traceback.txt`
- Frappe `Stock Reconciliation` DocType reference

---

## Requirements Regression Checklist

- [ ] RR-01 — Canonical preflight exit 0 (allowed skip only)
- [ ] RR-02 — Audit script emits `output/l3/s213/batch_audit_report.json` listing every (item, warehouse, NULL_qty) tuple for all `has_batch_no=1` items across BKI warehouses
- [ ] RR-03 — Audit confirms FG004 at PINNACLE + 3MD is NOT resolved by any fixed code path (still NULL)
- [ ] RR-04 — Backfill script posts Stock Reconciliation with `purpose='Stock Reconciliation'`, `current_qty=<NULL qty>`, `current_valuation_rate=<valuation>`, `batch_no=BACKFILL-<date>-<item>-<warehouse>`
- [ ] RR-05 — Each new `tabBatch` row has `item=<item_code>`, `batch_qty=<qty>`, `reference_doctype="Stock Reconciliation"`
- [ ] RR-06 — Post-backfill audit: every (item, warehouse, batch_no=NULL) tuple from RR-02 now has `batch_no != NULL`
- [ ] RR-07 — Bin qty unchanged post-backfill (reconciliation should be qty-neutral; only batch assignment changes)
- [ ] RR-08 — S212 monitored sweep rerun on origin/production reaches ≥48/49 (ORTIGAS GREENHILLS allowed skip)
- [ ] RR-09 — V1 (short-receive SM TANZA) passes: SI.qty == 8 (validates S212 DEFECT-2 fix under live flow)
- [ ] RR-10 — V2 (short-dispatch AYALA VERMOSA) passes
- [ ] RR-11 — Canonical postcheck identical to preflight
- [ ] RR-12 — Cleanup ledger `pendingEntries === 0` after rerun
- [ ] RR-13 — Both PRs (data fix + rerun evidence) merged + deployed
- [ ] RR-14 — Plan YAML `COMPLETED` + registry updated

---

## Phase Budget Contract

| Phase | Units | Ceiling |
|---|---:|---|
| Phase 0 — Preflight + audit (scope the data issue) | 4 | ≤12 OK |
| Phase 1 — Backfill script + unit test | 5 | ≤12 OK |
| Phase 2 — Execute backfill on production | 3 | ≤12 OK |
| Phase 3 — Post-backfill audit + canonical postcheck | 3 | ≤12 OK |
| Phase 4 — S212 monitored sweep rerun | 6 | ≤12 OK |
| Phase 5 — Cleanup + closeout | 4 | ≤12 OK |
| **Total** | **25** | ≤80 OK |

---

## Phases

### Phase 0 — Preflight + Batch Audit

1. Checkout `s213-fg004-batch-backfill` from `origin/production`
2. Run canonical preflight → `output/l3/s213/canonical_preflight.txt`
3. Create `scripts/s213_audit_null_batches.py` (SSM-driven). Query:
   ```sql
   SELECT item_code, warehouse, SUM(actual_qty) AS null_qty
   FROM `tabStock Ledger Entry` sle
   JOIN `tabItem` i ON i.item_code = sle.item_code
   WHERE i.has_batch_no = 1
     AND sle.batch_no IS NULL
     AND sle.docstatus = 1
     AND warehouse IN (SELECT name FROM `tabWarehouse`
                       WHERE company IN ('Bebang Kitchen Inc.')
                          OR warehouse_name LIKE '%- BKI')
   GROUP BY item_code, warehouse
   HAVING null_qty > 0
   ORDER BY null_qty DESC
   ```
4. Emit `output/l3/s213/batch_audit_report.json` with every (item, warehouse, null_qty) tuple

### Phase 1 — Backfill script + test

1. Create `scripts/s213_backfill_null_batches.py`:
   - Reads audit report from Phase 0
   - For each tuple: creates `Batch` doc with `batch_id=BACKFILL-<date>-<item>-<wh-short>` if not exists
   - Creates `Stock Reconciliation` entry with items pointing to the new batch
   - Submits; commits
   - Idempotent — re-running skips already-backfilled (item, warehouse)
2. Create `hrms/tests/test_s213_backfill.py` — source-inspection regression test for SR doc structure

### Phase 2 — Execute backfill

1. Run `scripts/s213_backfill_null_batches.py` against production
2. Capture stdout → `output/l3/s213/backfill_run.log`
3. Assert zero errors (any error stops; present to user)

### Phase 3 — Post-backfill audit + canonical postcheck

1. Re-run `scripts/s213_audit_null_batches.py` → `output/l3/s213/batch_audit_after.json`
2. Assert zero tuples remain (all NULL-batch stock now has a batch)
3. Run canonical postcheck → `output/l3/s213/canonical_postcheck.txt`, assert identical to preflight

### Phase 4 — S212 monitored sweep rerun

1. `python scripts/s212_launch_sweep.py --spec tests/e2e/specs/s209-all-stores.spec.ts --log output/l3/s213/sweep_full_run.log --pid-file output/l3/s213/sweep.pid --ledger output/l3/s213/sweep_ledger.json --decision-log output/l3/s213/monitor_decisions.log ...`
2. Expected: ≥48/49 pass. Monitor should NOT kill if DEFECT-6 is the only remaining issue.
3. Launch V1/V2 variance: `python scripts/s212_launch_sweep.py --spec tests/e2e/specs/s209-variance.spec.ts ...`
4. Assert V1.SI.qty == 8 (S212 DEFECT-2 fix validated under live flow), V2.SI.qty == 8

### Phase 5 — Cleanup + closeout

1. `python scripts/s209_cleanup_sweep.py --ledger output/l3/s213/sweep_ledger.json` + direct-SSM nuke pattern
2. Canonical postcheck again
3. Write `output/l3/s213/SWEEP_VERIFICATION_SUMMARY.md`
4. Update plan YAML + SPRINT_REGISTRY
5. Create closeout PR, share PR number, STOP

---

## Stop-only-for

- Canonical preflight violation (other than ORTIGAS GREENHILLS skip)
- Audit finds >10 items with NULL-batch stock → STOP, triage scope with user (might need separate inventory reconciliation sprint)
- Backfill script fails to create Stock Reconciliation (Frappe validation error) → STOP, diagnose
- S212 sweep rerun finds NEW defect class → STOP, triage

---

## Design principles

**Data integrity first.** No direct SQL on stock ledger. Every qty adjustment goes through proper Frappe docs (Stock Reconciliation) so the audit trail is preserved.

**Reversible.** If backfill is wrong, Stock Reconciliations can be cancelled. No hard deletes of batch docs (just disable).

**Blast radius.** S213 only touches FG004 (known problem) + any other items the Phase 0 audit identifies. Does not touch Item, Warehouse, Company masters.

---

*Plan authored 2026-04-21 (Tuesday) PHT by S212 R1 closeout agent after monitor-kill triage. All factual claims trace to S212 evidence files.*
