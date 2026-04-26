# S225 Phase Checklist

| Phase | Task | Status | Evidence path | Skipped? | If skipped, why? |
|---|---|---|---|---|---|
| 0 | Boot + both worktrees + canonical preflight | DONE | output/s225/verification/canonical_preflight.txt, baseline.json | NO | — |
| 1 | Validate S224 PR #687 + Pattern B + Pattern C | **BLOCKED — STOP for Sam decision** | output/s225/verification/{s224_deploy_sha_check,s224_pattern_b_validation,s224_pattern_c_validation,phase_1_decision}.{json,md}, output/l3/s225/sweep_ledger.json | PARTIAL | Sweep returned 2/6 PASS (both flaky). Per plan ≤4/6 = STOP. **S224 IS deployed (REST probes pass + 4/4 markers).** Sweep failures are S223 DEFECT-11 reappearance (auto-promoted MR not in SCM queue), unrelated to S224. See phase_1_decision.md. |
| 2 | Warehouse duplicate audit | PENDING | — | — | — |
| 3 | Consolidation (Sam-gated) | PENDING | — | — | — |
| 4 | FOR UPDATE lock implementation | PENDING | — | — | — |
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
