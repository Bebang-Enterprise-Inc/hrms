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
| 1 | 1.0 Rollback SQL | PASS | `tmp/s258/rollback_phase1.sql` — 133+ lines covering A1 (44 Companies) + A2 (L77) + A3 (ROBDA + XMM round_off) + A3.5 (BEI). |
| 1 | 1.1 A1 — default_inventory_account on PARTIAL | PASS (43/44; III deferred D1-3) | `scripts/coa_fix/A1_seed_default_inventory.py` executed. 43 of 44 PARTIAL Companies (excluding BEI + BKI) had pre-existing `Stock In Hand - <ABBR>` accounts; SET tabCompany.default_inventory_account on each. III (root holdco) deferred to Phase 3a (root-cascade blocks REST-API CREATE — same constraint as 1.3.5). `output/s258/A1_summary.json`. |
| 1 | 1.2 A2 — stock_received_but_not_billed on L77 | PASS | `LEGACY77 FOOD CORP.` tabCompany.stock_received_but_not_billed = `Stock Received But Not Billed - L77`. |
| 1 | 1.3 A3 — dedupe ROUND OFF on ROBDA + XMM | PASS (with deviation D1-1) | `scripts/coa_fix/A3_dedupe_round_off.py` executed. **ROBDA**: tabCompany.round_off_account → `Round Off - ROBDA` (Expense canonical); Journal Entry `ACC-JV-2026-00014` submitted transferring 0.80 PHP from legacy Liability dupe to Expense; legacy `2120000 - ROUND OFF - ROBDA` SET disabled=1. **XMM**: tabCompany.round_off_account → `Round Off - XMM`; legacy `2120000 - ROUND OFF - XMM` SET disabled=1 (0 GL → no JE). Deviation D1-1: followed canonical Rule 2 disable-don't-delete instead of plan's DELETE-with-ignore_links (which doesn't work — GL Entry check is a separate validation). |
| 1 | 1.3.5 BEI round_off_account canonicalization | DEFERRED (D1-2) | REST API cannot bypass `ignore_root_company_validation`. BEI's current `round_off_account = "Stock Adjustment - Bebang Enterprise Inc."` (Expense, 0 GL — functional but non-canonical name). Phase 3a's bench-execute root-tree seed loop will create `Round Off - BEI` under canonical tree; Phase 3c will point Company at it. |
| 1 | 1.4 A4 — extract canonical store template | PASS | `data/_FINAL/COA_HEALTHY_REFERENCE.csv` — 114 unique account stems unioned from 6 HEALTHY Companies (AYVER, BMI2, GHO, SMK, BDV, BAG). 82 stems appear in ALL 6. |
| 1 | 1.5 A5 — BFI2→BFT abbr rename | PASS | `scripts/coa_fix/A5_rename_bfi2_to_bft.py` via SSM bench execute. `tabCompany.abbr` BFI2→BFT on BEBANG FT INC.; SEC tax_id `663-440-106-00000` preserved; 0 tabAccount rows with `- BFI2` (BFT had 0 accounts pre-rename); 2 Cost Centers renamed (`BEBANG FT INC. - BFT`, `Main - BFT`); all `cost_center` / `round_off_cost_center` / `depreciation_cost_center` references cascade-updated. |
| 1 | verify_phase1.py | PASS | All 5 subtask groups PASS: A1 43/43, A2 1/1, A3 ROBDA+XMM, A4 csv, A5 abbr+tax+CCs. |
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
