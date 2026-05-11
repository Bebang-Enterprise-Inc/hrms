# S246 Closeout Summary (audit + decision only)

**Sprint:** S246 — BKI→Store Billing Redesign — Comprehensive Audit + CEO Decision Gate
**Plan version:** v1.1 (audit-amended; 10 CRITICAL + 14 WARNING applied inline)
**Phases executed:** 0, 1A, 1B, 2 (of planned 0-7)
**Phases deferred to S247:** 3A, 3B, 3C, 4a, 4b, 5, 6, 7
**Status:** PR_OPEN — closing as audit + decision only per Scope Size Warning split
**Decision date:** 2026-05-11
**Decision authority:** Sam Karazi (CEO, single-owner signoff)
**Chosen option:** Option 3-corrected (Stock Entry + Purchase Invoice split with SRBNB GR/IR clearing)

---

## What S246 delivered

### Phase 0 — Boot + baseline state
- Worktree spawned at `F:/Dropbox/Projects/BEI-ERP-s246-bki-store-billing-redesign` from `origin/production @ 40f22c07c`
- PR #745 merge verified (HARD GATE)
- Sprint-collision check passed (no other active sprints touching same surfaces)
- Canonical preflight: 49 stores checked, 0 violations
- State files: `REMOTE_TRUTH_BASELINE.json`, `SURFACE_OWNERSHIP_MATRIX.csv`, `ACTIVE_RUN.json`

### Phase 1A — Canonical Store Master-Data Spec + Extended Verifier
- **Spec document:** `output/l3/s246/audit/CANONICAL_STORE_SPEC.md` (54 REQUIRED + 12 RECOMMENDED + 6 DEFAULTED fields across Company / Warehouse / Customer / Internal Customer / Account / BKI Trade Supplier / BEI Settings / Custom Fields / doc_events).
- **Extended verifier:** `scripts/verify_canonical_structure.py` now supports `--mode v2` which delegates to `scripts/s246/run_v2_verifier.py`.
- **49-store gap report:**
  - `output/l3/s246/verification/verify_canonical_v2_before.json` (raw JSON)
  - `output/l3/s246/audit/per_store_gap.csv` (per-store, per-field gap matrix)
- **Headline:** 0 of 49 stores are fully canonical today.

### Phase 1B — 7-item audit + 30-day Error Log sweep
- **Probe script:** `scripts/s246/audit_7_items_probe.py` runs all 7 audits in one SSM pass.
- **Raw data:** `output/l3/s246/audit/p1b_audit_raw.json`
- **Synthesized report:** `output/l3/s246/audit/audit_report.md`
- **Findings (top):**
  - BKI's GL is healthy (₱10.48M Dr=Cr balanced across 2,215 entries from 839 SIs)
  - **0 paired Submitted PIs exist** in production — Input VAT has NEVER been claimed on store books from any BKI sale
  - **13 "PASS" stores all have ZERO stock GL** entries from the BKI flow (DEFECT D fully confirmed; design intent silently dropped on 100% of stores)
  - **40 S238-related errors in past 30 days** — ongoing silent failures since PR #738 deploy
  - **0 cross-Company Material Transfers** in the recent sample — no architectural collision with dual-doc design

### Phase 2 — CEO Decision Gate
- Decision signed off in-session: **Option 3-corrected**
- Decision artifact: `output/l3/s246/DECISION.md`

---

## What S247 will deliver (when written)

All implementation work from S246 v1.1's Phases 3A/3B/3C/4a/4b/5/6/7. Roughly 70 work units. The architectural premise is frozen in `output/l3/s246/DECISION.md`. The S247 plan should reuse most of S246 v1.1's task content verbatim, with these specifics baked in:

- Option 3-corrected (SE + PI split with SRBNB GR/IR)
- `perpetual_inventory_consistency: yes` (set all 49 to perpetual=1)
- Hook STRING→LIST conversion explicit
- Cancel cascade order: SE first, PI second
- Atomicity: savepoint isolation + reconciliation cron follow-up

---

## Evidence files (committed to PR)

```
output/l3/s246/
├── SUMMARY.md                          (this file)
├── DECISION.md                          (Phase 2 outcome)
├── audit/
│   ├── CANONICAL_STORE_SPEC.md          (Phase 1A.1-1A.3)
│   ├── audit_report.md                  (Phase 1B.8)
│   ├── p1b_audit_raw.json               (Phase 1B raw probe data)
│   └── per_store_gap.csv                (Phase 1A.5 gap matrix)
├── verification/
│   ├── verify_canonical_v1_baseline.txt (Phase 0.5)
│   └── verify_canonical_v2_before.json  (Phase 1A.5)
└── state/
    ├── ACTIVE_RUN.json
    ├── REMOTE_TRUTH_BASELINE.json
    └── SURFACE_OWNERSHIP_MATRIX.csv

scripts/s246/
├── verify_canonical_v2_probe.py         (Phase 1A.4 — v2 verifier inner)
├── run_v2_verifier.py                   (Phase 1A.4 — SSM wrapper)
├── audit_7_items_probe.py               (Phase 1B inner)
└── run_p1b_audit.py                     (Phase 1B SSM wrapper)

scripts/verify_canonical_structure.py    (Phase 1A — added --mode v2 flag)
```

---

## What was NOT done (deliberately, per Phase 2 split decision)

- ❌ No PI generator code refactor
- ❌ No SE generator created
- ❌ No `hrms/hooks.py` changes
- ❌ No BEI Settings field additions
- ❌ No master-data UPDATEs (cost_center / SRBNB / Warehouse.account / Supplier.accounts)
- ❌ No 49-store L3 sweep with new generators
- ❌ No 839 historical SI cleanup

All of the above moves to S247.

---

## Follow-up sprint candidates (for the registry)

1. **S247 — Implementation of Option 3-corrected** (the big one — ~70 units)
2. **S248 — Reconciliation cron for half-paired SIs** (post-S247, safety net)
3. **S249 — G-046 dashboard update to query `bki_si_reference`** (post-S247, reporting layer)
