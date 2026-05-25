# Phase 0 Checklist — Boot + Baseline

| Task | Status | Evidence | Skipped? |
|---|---|---|---|
| 0.1 Read plan + references | DONE | Plan read in full; v3.9 source confirmed 95K bytes | NO |
| 0.2 Verify worktree on branch | DONE | Rebased onto origin/production `93757da1e` | NO |
| 0.3 Record baseline SHA | DONE | `output/s256/baseline_sha.txt` = `93757da1e2a3381fb5419e6231f34f876d8c4e13` | NO |
| 0.4 Backup v3.9 source | DONE | `output/s256/script_source_backup_v39.gs` (95,031 bytes) | NO |
| 0.5 PAUSE Cloud Scheduler | DONE | `output/s256/cloud_scheduler_pause_log.json` — state=PAUSED | NO |
| 0.6 AP Master grid snapshot | DONE | `output/s256/baseline_state.json` — 19 tabs | NO |
| 0.7 Denise PP snapshot | DONE | `output/s256/denise_pp_baseline.json` — 16 ACL, 3 Bridge | NO |
| 0.8 Upstream ACLs snapshot | DONE | `output/s256/upstream_acl_baseline.json` — all 5 sheets have Bridge | NO |
| 0.9 Verify /finance-ap skill | DONE | 22 Bridge hits across all 3 mirrors | NO |
| 0.10 Ownership matrix | DONE | `output/s256/S256_SURFACE_OWNERSHIP_MATRIX.csv` (15 rows) | NO |
| 0.11 verify_phase0.py | DONE | Exit 0 — ALL PASS | NO |
