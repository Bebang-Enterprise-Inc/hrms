# S207 L3 Defects

## Summary

**Sprint goal:** PASS. All 8 executable L3 scenarios pass post-deploy.
**Collateral defects:** 1 deploy-pipeline bug (pre-existing, pre-dated S207), surfaced by S207 testing.

---

## DEFECT: Deploy-script migrate step uses wrong site name

- **Severity:** CRITICAL (pre-existing, not caused by S207)
- **Type:** COLLATERAL (discovered during S207 post-deploy validation, not in S207 scope)
- **Scenario:** S207 post-deploy verification — expected migration patch `hrms.patches.v16_0.s207_labor_allocation_log_bimonthly` to run during deploy; it didn't.
- **Evidence:**
  - GitHub Actions run `24652546811` "Deploy to AWS EC2" job log:
    ```
    docker exec $BACKEND_CONTAINER bench --site hrms.bebang.ph migrate
    ```
  - Actual production site is `hq.bebang.ph`, not `hrms.bebang.ph`.
  - `tabPatch Log` queried via SSM contained zero rows matching `%s207%` before manual repair (migrate never completed).
  - SSM-manual retry of `ALTER TABLE ... DROP COLUMN year/month` + `CREATE UNIQUE INDEX idx_slip_employee` succeeded immediately — proving the patch content was fine; migrate command never reached it.
- **Impact:**
  - Every hrms deploy since this bug was introduced has skipped ALL migration patches.
  - DocType auto-sync still runs (via a different code path) so most deploys appeared to work — columns get added automatically, but column drops, index changes, and custom SQL operations in patches never execute.
  - S206 patch `s206_unique_labor_allocation_log` (2026-04-18) appeared to run because a prior deploy or ad-hoc SSM actually applied it — the migrate-in-deploy path has likely been broken since before that sprint.
  - S207 hit it because S207 drops columns (year, month) which DocType auto-sync cannot do (Frappe's sync is additive only).
- **Root cause:** Hard-coded site name in the deploy workflow's migrate step.
- **Suggested fix:** Replace `hrms.bebang.ph` with `hq.bebang.ph` in the workflow YAML. Better: parameterize via a variable / secret that matches the live site.
- **Workaround used (2026-04-20):**
  1. Manually re-ran the ALTER SQL via SSM (see `scripts/s207_check_migration_errors.py`).
  2. Recorded the patch as done in `tabPatch Log` to prevent future migrate attempts from retrying partial state (see `scripts/s207_record_patch_done.py`).
- **First seen:** 2026-04-20 07:49 PHT (deployment of S207 PR #644 completed; first post-deploy validation revealed the unchanged schema)
- **Blocks:** Nothing right now (workaround applied). Blocks any future sprint that depends on a Frappe patch running during deploy.
- **Ticket / follow-up:** File a separate sprint to fix the deploy workflow. Out of S207 scope per plan + CEO directive.

## No in-scope defects

S207's own code is fully working:
- `preview_allocation` / `post_allocation` / `preview_scheduled` / `posting_date_for_slip` / `PHT` all deployed and functioning.
- Day-guard math (L3-3/4/5) proven correct against UTC/PHT boundary cases.
- Idempotency (L3-6) exercised — no double-posts, zero JEs created on empty-April run.
- Structures 4/4 = Bimonthly, COA coverage 49/49, canonical verifier clean.
