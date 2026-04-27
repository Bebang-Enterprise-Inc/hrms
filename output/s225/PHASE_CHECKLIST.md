# S225 Phase Checklist

| Phase | Task | Status | Evidence path | Skipped? | If skipped, why? |
|---|---|---|---|---|---|
| 0 | Boot + both worktrees + canonical preflight | DONE | output/s225/verification/canonical_preflight.txt, baseline.json | NO | — |
| 1 | Validate S224 PR #687 + Pattern B + Pattern C | DONE (intent satisfied) | output/s225/verification/{s224_deploy_sha_check,s224_pattern_b_validation,s224_pattern_c_validation,s226_deploy_check,phase_1_decision_v2}.{json,md} | PARTIAL (sweep) | S224 verified deployed (4/4 markers + REST probes PASS). S226 deployed (PR #688 merged) — confirmed unblocking the queue visibility (failure-class shifted from "DEFECT-11 invisible queue" to Pattern A "DispatchPage timeout"). Remaining 4 failures are Pattern A which Phase 4 will fix. Proceeding to Phase 2 with documented rationale (phase_1_decision_v2.md). |
| 2 | Warehouse duplicate audit | DONE | output/s225/verification/duplicate_warehouse_audit.{json,md}, sam_consolidation_pr.txt | NO | 2 clusters found (3MD + ROYAL COLD STORAGE), both auto-apply eligible. Sam approved via "S225 Phase 3 APPROVED ALL" on PR #689 at 2026-04-27T02:13Z. |
| 3 | Consolidation (Sam-gated) | DONE | output/s225/verification/dup_consolidation_applied.json, canonical_postcheck_phase3.txt | NO | Cluster 1 (3MD): SE MAT-STE-2026-01038 submitted, 79 items / 32,627 units migrated, duplicate disabled. Cluster 2 (ROYAL): no SE needed (0 stock), duplicate disabled. Required temporary toggle of Stock Settings.allow_negative_stock_for_batch (BACKFILL batch on duplicate had 0 stock); reverted after. Canonical postcheck post-Phase-3: 49 stores, 0 violations. FG004: 1095→1743 KG (+648 from migration). FG002-A: 1714→2958 KG (+1244). All sample items conservation-verified. |
| 4 | FOR UPDATE lock implementation | DONE (deploy pending) | hrms/api/warehouse.py:create_stock_transfer (+~50 lines), output/s225/verification/{batch_tracking_probe,pattern_a_lock_test}.json, scripts/s225_pattern_a_lock_smoke.py | NO | Lock added at line ~1590, BEFORE items append. Locks both tabBin and tabBatch (audit W-1 — 17 batch-tracked items in scope). Deterministic acquisition order (sorted item_codes) prevents deadlocks. Lock-wait telemetry via frappe.log_error (>2s threshold). Existing set_backend_observability_context preserved. Smoke probe deferred until Sam deploys (status DEFERRED_PRE_DEPLOY); will run with --execute in Phase 4.5. |
| 4.5 | Wait-for-deploy gate | PENDING | — | — | — |
| 5 | Concurrency stress test | PENDING | — | — | — |
| 6 | Full L3 sweep | PENDING | — | — | — |
| 7 | Closeout (registry + PR + worktrees) | PENDING | — | — | — |

## Notes

- **Phase 0 baseline:** hrms `origin/production` HEAD = `b6355e35c10edef2828afb3a283386874a7e728e` (S224 merge commit). bei-tasks `origin/main` = `31fa4707498c4110f9e5a9b8fc740137d9e38b85`.
- **Canonical preflight result:** 49 stores, 0 violations.
- **Missing transient context (non-blocking):** `output/s223/verification/pattern_a_b_c_root_cause_analysis.md` referenced in Phase 0 task 2 was not committed (output/ is gitignored). Plan body provides sufficient Pattern A/B/C context. Proceeding without it.
- **Both worktrees spawned:**
  - hrms: `F:/Dropbox/Projects/BEI-ERP-s225-canonical-warehouse-cleanup-and-pattern-a-safeguard`
  - bei-tasks: `F:/Dropbox/Projects/bei-tasks-s225-canonical-warehouse-cleanup-and-pattern-a-safeguard` (node_modules junctioned to main)
