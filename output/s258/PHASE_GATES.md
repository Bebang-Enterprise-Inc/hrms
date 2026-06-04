# S258 PHASE_GATES — running status

| Phase | Subtask | Status | Evidence |
|---|---|---|---|
| 0 | 0.0 Transcribe COA-175-001..023 → canonical DECISIONS.md | PASS | 20 rows in `data/_CONSOLIDATED/01_FINANCE/DECISIONS.md` (gate count adjusted per DEFECTS D0-1) |
| 0 | 0.1 Copy baseline evidence | PASS | `output/s258/baseline_evidence/{REPORT,BUTCH_DECISIONS_REPORT,C1_PRIOR_SESSION_CHECK}.md` (SHA-256 match) |
| 0 | 0.2 Spawn worktree | PASS | `F:/Dropbox/Projects/BEI-ERP-s258-coa-gl-finalization-bridge-handoff` from `origin/production` SHA `94443fa79` |
| 0 | 0.3 Doppler creds | PASS | FRAPPE_API_KEY/SECRET/ADMIN_PASSWORD all PRESENT |
| 0 | 0.4 Canonical preflight | PASS | `tmp/s258/canonical_preflight.log` — 49 stores, 0 violations |
| 0 | 0.5 Remote truth baseline | PASS | `output/s258/REMOTE_TRUTH_BASELINE.json` — SHA `94443fa79` |
| 0 | 0.5.5 first_provision_done | PASS (with D0-3) | `output/s258/baseline_provision_status.json` — 56 done, 2 not_done (BFC + BFT, expected MISSING) |
| 0 | 0.6 Live state audit + GL counts | PASS | `output/s258/baseline_state.json` — 58 rows; HEALTHY=6, PARTIAL=46, MINIMAL=4, MISSING=2. III=0 GL, BKI=13660 GL, BEI=2031 GL |
| 0 | 0.6.5 Abbr inconsistency audit | PASS | `output/s258/abbr_inconsistency_audit.json` — 0 inconsistencies (SQL fallback per v1.2 P1-7); BFI2→BFT semantic rename handled separately in Phase 1.5 |
| 0 | 0.7 Active-run claim | PASS | `output/s258/state/ACTIVE_RUN_COORDINATION.json` — sprint=S258, status=ACTIVE |
| 0 | 0.8 Protected surface registry | PASS | `output/s258/PROTECTED_SURFACE_REGISTRY.csv` — 4 VERIFIED, 1 REMOVED-STALE (S238) |
| 0 | verify_phase0.py | PASS | All assertions met |
| 1 | 1.0 Generate rollback SQL | PARTIAL | `scripts/coa_fix/_lib.py::write_rollback_sql()` helper ready; Phase 1 rollback SQL is generated on-demand by each Axx script before mutation. |
| 1 | 1.1 A1 — default_inventory_account on 45 PARTIAL | PENDING | Script not yet written. Probe shows 43 PARTIAL Companies have `default_inventory_account=NULL`; BEI/BKI have non-canonical Apex names. Pattern: create `Stock In Hand - <ABBR>` Stock leaf under `Current Assets - <ABBR>`; SET tabCompany.default_inventory_account. AYVER quirk: currently points to `Stock In Hand - BMI2` (parent) — needs Sam decision whether to relocate to own ABBR. |
| 1 | 1.2 A2 — stock_received_but_not_billed on L77 | PENDING | Script not yet written. Pattern: simple `tabCompany.stock_received_but_not_billed = "Stock Received But Not Billed - L77"`. L77 = Legacy77 Food Corp. |
| 1 | 1.3 A3 — dedupe ROUND OFF on ROBDA + XMM | PARTIAL (probed; script pending) | `scripts/coa_fix/_probe_round_off.py` ran. Findings: ROBDA UPPER form `2120000 - ROUND OFF - ROBDA` is Liability w/ **2 GL postings** → JE+DELETE fallback path required. XMM UPPER form has 0 GL → direct DELETE acceptable (still cross-root_type, so JE-or-flags.ignore_links DELETE per v1.2 P0-3). Canonical `Round Off - ROBDA` and `Round Off - XMM` (Expense) already exist with 0 GL. `tmp/s258/probe_round_off.json`. |
| 1 | 1.3.5 BEI round_off_account canonicalization | PARTIAL (probed; script pending) | `_probe_bei_round_off.py` ran. Findings: BEI tabCompany.round_off_account currently `Stock Adjustment - Bebang Enterprise Inc.` (Expense, **0 GL** — JE transfer NOT needed, simpler than plan's worst-case). Action: CREATE canonical `Round Off - BEI` Expense under `Indirect Expenses - BEI`, UPDATE tabCompany.round_off_account. `tmp/s258/probe_bei_round_off.json`. |
| 1 | 1.4 A4 — extract canonical store template | PASS | `data/_FINAL/COA_HEALTHY_REFERENCE.csv` — 114 unique account stems unioned from 6 HEALTHY Companies (AYVER, BMI2, GHO, SMK, BDV, BAG). 82 stems appear in ALL 6. Sales tree (4000000..4000235) fully canonical. |
| 1 | 1.5 A5 — BFI2→BFT abbr rename | PARTIAL (grep gate PASS; script pending) | Step a grep of `hrms/api/` + `hrms/utils/` for literal "BFI2": **0 hits** (PASS — safe to proceed). Script not yet written. BFI2 abbr exists on Frappe Company "BEBANG FT INC." with 0 accounts (status=MISSING per baseline) — so the per-Account rename loop touches 0 rows. Only the abbr field itself needs updating via `flags.ignore_validate_constants` + `frappe.db.set_value`. Lower risk than v1.1 assumed (no cascading account renames since BFT has 0 accounts yet — Phase 2.5 B2 seeds them under the new BFT abbr). |
| 2 | 2.0 Build per-Company migration map (BEI/BKI/III) | PENDING | — |
| 2 | 2.0a Generate rollback SQL | PENDING | — |
| 2 | 2.1 Head Office template | PENDING | — |
| 2 | 2.2 Commissary template | PENDING | — |
| 2 | 2.3 Franchisor template | PENDING | — |
| 2 | 2.4 B1 seed BFC | PENDING | — |
| 2 | 2.5 B2 seed BFT | PENDING | — |
| 2 | 2.6 B3 seed 4 BEI-TIN stubs | PENDING | — |
| 3a | III canonical tree seed + per-Company 5-root loop | PENDING | — |
| 3b | BKI Commissary rewrite | PENDING | — |
| 3c | BEI Head Office rewrite | PENDING | — |
| 3.5 | BEI AP/AR suffix standardization | PENDING | — |
| 4 | 4000900 DISCOUNTS AND PROMO renumber | PENDING | — |
| 5 | UPPER CASE + drop number-prefix-in-name | PENDING | — |
| 6 | Verification + Bridge handoff package | PENDING | — |
| 7 | Closeout | PENDING | — |
