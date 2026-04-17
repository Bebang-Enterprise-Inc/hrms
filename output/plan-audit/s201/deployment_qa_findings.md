# S201 Deployment & QA Audit — Findings Report

**Auditor:** Deployment & QA Domain Agent
**Plan:** `docs/plans/2026-04-17-sprint-201-per-store-employee-billing-foundation.md`
**Patches audited:**
- `hrms/patches/v16_0/s201_rename_branches.py`
- `hrms/patches/v16_0/s201_backfill_employee_company.py`
**Audit date:** 2026-04-17 PHT
**PR status at audit time:** PR #603 MERGED 2026-04-16 23:22 PHT, PR #604 MERGED 2026-04-17 00:34 PHT

---

## Finding 1 — Dry-Run Default Is Safe, But Deploy Workflow Bypasses the Manual Apply Step

**Severity:** [CRITICAL]

**Evidence:**
The patches implement dry-run correctly: `_apply_mode()` checks `os.environ.get("S201_APPLY", "")`. When `bench migrate` runs automatically, `S201_APPLY` is not set, so patches execute in dry-run mode — writing a report to `site/private/files/` and returning without mutating data. This part is safe.

However, the GHA `build-and-deploy.yml` migration step (lines 388, ~374-410) runs:
```
docker exec $BACKEND_CONTAINER bench --site $FRAPPE_SITE migrate
```
No `S201_APPLY=1` is injected. The workflow has no step, no input parameter, and no manual hook for re-running the patches in apply mode. The plan's PR body (step 5) says:
> S201_APPLY=1 bench --site hq.bebang.ph execute hrms.patches.v16_0.s201_rename_branches.execute

This requires **direct SSH access to the EC2 instance and manual bench execution** — which is outside the automated deploy workflow entirely. The plan does not document this as a manual step that must occur after the GHA workflow finishes, nor does it tell Sam how to confirm the SSM-dispatched `bench migrate` has completed and where to find the dry-run report before proceeding.

**Recommended amendment:**
Add an explicit Phase 7.5 or Phase 8 (see also Finding 12) documenting:
1. After GHA deploy + migrate completes, the patches have run in dry-run mode.
2. How to retrieve the report: `aws ssm start-session --target <EC2_INSTANCE_ID>` then `docker exec $BACKEND bench --site hq.bebang.ph execute hrms.patches.v16_0.s201_rename_branches.execute` — **or** locate the report at `site/private/files/branch_rename_report_*.json` via the Frappe file manager.
3. How Sam signals approval (e.g., replies to the PR comment or runs a specific one-liner).
4. The exact command for the apply run with `S201_APPLY=1`.

---

## Finding 2 — Idempotency on Re-Migrate Is Safe by Frappe Patch Tracking

**Severity:** [INFO]

**Evidence:**
Frappe records executed patches in `tabPatchLog`. Once `s201_rename_branches` and `s201_backfill_employee_company` have executed (even in dry-run mode), Frappe will NOT re-execute them on subsequent `bench migrate` calls unless `--force` is used. The patches themselves are also idempotent by design: `s201_rename_branches.py` skips rows where `old == new` with `"already canonical"` reason; `s201_backfill_employee_company.py` skips employees where `target == current`.

However, there is a subtle interaction: the dry-run execution IS recorded in `tabPatchLog` as "executed." When Sam later wants to run the patch in apply mode (`S201_APPLY=1`), he **cannot use `bench migrate`** — he must use `bench execute` directly. This is correct behavior and the PR body documents it, but the plan body does not. This is a documentation gap, not a code gap.

**Recommended amendment:**
Add a note in the deploy sequence: "After dry-run executes via `bench migrate`, subsequent `bench migrate` calls will skip these patches. Apply mode MUST use `bench execute`, not `bench migrate`."

---

## Finding 3 — S201_APPLY Env Var Will NOT Propagate Through GHA/SSM/Docker

**Severity:** [CRITICAL]

**Evidence:**
The GHA workflow dispatches commands via AWS SSM `send-command` with a hardcoded `commands=[...]` array. There is no mechanism in `.github/workflows/build-and-deploy.yml` to inject `S201_APPLY=1` into this command array — not as a workflow input, not as a secret, not as an environment variable. Even if an operator sets `S201_APPLY=1` in their local shell, it does not reach the `docker exec` call inside the SSM-dispatched command on EC2.

The patches check `os.environ.get("S201_APPLY")` inside the Python process running inside the Docker container. To propagate the env var, the command must be:
```bash
docker exec -e S201_APPLY=1 $BACKEND_CONTAINER bench --site hq.bebang.ph execute \
  hrms.patches.v16_0.s201_rename_branches.execute
```
The `-e S201_APPLY=1` flag is **not** documented anywhere in the plan, the PR body, or the GHA workflow. The PR body step 5 shows a bare `S201_APPLY=1 bench ...` command that assumes a shell where the env var is pre-set, which is not how `docker exec` works — the env var will not be visible inside the container unless explicitly passed with `-e`.

**Recommended amendment:**
Update all apply-mode instructions to use `docker exec -e S201_APPLY=1 $BACKEND_CONTAINER bench ...`. Add this to the plan and to a runbook entry. Also consider whether the GHA workflow needs a `apply_s201` boolean input that injects `-e S201_APPLY=1` when true.

---

## Finding 4 — Rollback Contract Has Orphaned Salary Slip Gap

**Severity:** [WARNING]

**Evidence:**
The Rollback Contract (plan lines 239-244) and the PR body rollback SQL both reset `Employee.company` back to `BEBANG ENTERPRISE INC.` but do not address `Salary Slip` documents created after the backfill. A Salary Slip in Frappe snapshots `company` at generation time and stores it as a static field. After backfill:
- Salary Slips created = `company = SM MEGAMALL - BEBANG ENTERPRISE INC.`
- Rollback resets `Employee.company` back to BEI parent
- The Salary Slips still carry the store Company name

In submitted/paid state, these Slips cannot be edited without cancellation. If the payroll run has been submitted and a GL Entry has been posted against the store Company's books, rolling back the Employee record does not undo the GL entries. The rollback SQL alone creates an inconsistency between `tabEmployee.company` and existing `tabSalary Slip.company`.

**Recommended amendment:**
Add to Rollback Contract:
1. State explicitly: "If any Salary Slips have been created post-backfill, they must be cancelled before Employee rollback, or accepted as-is and the rollback declared partial."
2. Add a pre-rollback check query: `SELECT name, company, status FROM \`tabSalary Slip\` WHERE company != 'BEBANG ENTERPRISE INC.' AND docstatus IN (0,1) ORDER BY creation DESC LIMIT 50`.
3. Distinguish between: (a) rollback before any payroll run (safe), (b) rollback after payroll run (requires GL reversal — escalate to Sam).

---

## Finding 5 — L3 Evidence Contract Has No Playwright Script and No Capture Mechanism

**Severity:** [CRITICAL]

**Evidence:**
The plan (line 212) states: "Run these in a fresh Playwright session. Record each in `output/l3/s201/`." The PR body repeats this. However:
1. No Playwright script file exists for S201. `ls scripts/testing/` shows L3 scripts for s094, s101-s108, s122, s126, s134-s135, s152, s166 — but no `l3_s201_*.py` or `l3_s201_*.mjs`.
2. `output/l3/s201/` does not exist on disk.
3. The three required evidence files (`form_submissions.json`, `api_mutations.json`, `state_verification.json`) do not exist.
4. The plan does not name a script file to run, does not specify who writes the script, and does not specify in what format the evidence files should be structured.

"Run these in a fresh Playwright session" implies a script exists and just needs to be invoked. No such script exists. This means L3 is currently blocked on script authoring, not just execution.

**Recommended amendment:**
Either (a) author `scripts/testing/l3_s201_company_billing.mjs` as part of Phase 8 (see Finding 12), specifying the six scenarios and the evidence output format, or (b) add an explicit Phase 8 task: "Author L3 script covering scenarios L3-1 through L3-6. Script must produce `output/l3/s201/{form_submissions,api_mutations,state_verification}.json`."

---

## Finding 6 — L3-6 Salary Slip Test Has No Payroll Fixture and Is Environment-Dependent

**Severity:** [WARNING]

**Evidence:**
L3-6 requires: "Generate Salary Slip for store employee (post-backfill) for April 2026 cutoff." Generating a Salary Slip in Frappe requires:
1. A `Salary Structure` assigned to the employee.
2. A `Payroll Entry` or direct Salary Slip creation for April 2026.
3. The Payroll Period for April 2026 to exist.

The plan provides no fixture for any of these. If HR has not created the April 2026 Payroll Entry, L3-6 will fail with a Frappe validation error, not a useful test failure. The plan does not specify a test employee with a known Salary Structure, nor does it specify whether to use a test employee (from `memory/testing-accounts.md`) or a real employee.

Additionally, since the backfill must run before L3-6 is meaningful, L3-6 has a strict ordering dependency on the apply-mode execution of the backfill patch — which itself is blocked by Sam's approval of the dry-run report (Finding 1). The plan does not call this ordering dependency out.

**Recommended amendment:**
1. Specify a test employee by ID with a known Salary Structure (or document how to create a minimal test fixture).
2. Specify: "If no April 2026 Payroll Entry exists, create a single Salary Slip directly for the test employee via Frappe desk."
3. Add explicit note: "L3-6 MUST run after the backfill patch has been applied in apply mode, not just dry-run."
4. Document how to clean up the test Salary Slip post-verification (cancel + delete).

---

## Finding 7 — Plan YAML status=GO After Merge, No Post-Merge Update Path

**Severity:** [WARNING]

**Evidence:**
The plan YAML header has `status: GO`. PR #603 was merged 2026-04-16 23:22 PHT. The plan was committed as part of PR #603 (per `gh pr view 603 --json files` output showing `docs/plans/2026-04-17-sprint-201-per-store-employee-billing-foundation.md`). The SPRINT_REGISTRY.md was also updated in PR #603.

Phase 9 Closeout says to set `status: COMPLETED` and update the registry, but Phase 9 is marked as pending (L3 has not run). The plan is now on the `production` branch with `status: GO` — a status that implies "approved to execute" rather than "in progress" or "deployed." There is no intermediate status defined (e.g., `DEPLOYED_PENDING_L3`).

The governor PR handoff workflow (per `memory/pr-handoff-workflow.md`) has the governor disabled — Sam merges. But no one is tracking the plan status update to COMPLETED after L3 passes. Phase 9 step says `git add -f docs/plans/*.md output/s201/ output/l3/s201/ ...` — but this requires a new commit on production branch (or a new PR), which is not explicit.

**Recommended amendment:**
Add a `DEPLOYED_PENDING_L3` intermediate status to the plan governance vocabulary, or explicitly say: "After PR #603 merge, update plan status to `DEPLOYED` and commit directly to production. After L3 passes, update to `COMPLETED`."

---

## Finding 8 — Governor Feedback Loop: REJECT/NEEDS_FIX/Deploy Failure Handlers Are Not Specified

**Severity:** [WARNING]

**Evidence:**
The plan has `stop_only_for` (lines 26-30) listing four valid stop triggers. However, the S027 governor contract also requires handlers for:
- REJECT: what should the executing agent do if the governor rejects the code review?
- NEEDS_FIX: which file/line does the agent go back to?
- Merge Conflict during rebase onto production: which commits to keep?
- Deploy Failure: what constitutes a deploy failure vs. a transient SSM timeout?

`stop_only_for` lists "Merge conflict on production during rebase" as a stop condition — but does not say what the agent should present to Sam when it stops (options, context, recommended resolution).

For REJECT and NEEDS_FIX, the plan does not reference any handler. Given PR #604 was also needed (BGC employee fix) post-merge, this gap was live in practice.

**Recommended amendment:**
Add a `governor_handlers` block to the plan YAML or a "Governor Response Protocol" section:
```yaml
governor_handlers:
  REJECT: "Identify failing check, create new branch fix/<issue>, fix and resubmit"
  NEEDS_FIX: "Apply amendment, push to current branch, governor re-reviews"
  merge_conflict: "Stop. Present conflict file list to Sam. Ask which version to keep."
  deploy_failure: "Check SSM output for error. If transient, retry once. If persistent, stop and present error."
```

---

## Finding 9 — PR #603 Merged Without L3 Evidence: Release Gate Correctly Skipped (NOT a violation)

**Severity:** [INFO]

**Evidence:**
The release gate in `scripts/merge_governor/release_gate.py::find_sprint_plan()` identifies sprint PRs by matching `s0?(\d{2,3})` in the **branch name**. PR #603's branch is `s201-per-store-employee-billing` — this matches the pattern. The gate would have looked for `output/l3/s201/form_submissions.json` in the branch.

However, `scripts/merge_governor/merge_serializer.py:1052` skips the gate when `det_result.skip_reason` is set. Examining `release_gate.py` line 60 context: the gate returns `skip_reason` when the branch name does not match the sprint pattern OR when no plan file is found. Since the plan WAS committed to this branch, the gate should have attempted to enforce L3 evidence.

`output/l3/s201/` does not exist in the branch (not in PR #603 files list). The gate should have BLOCKED this merge. Whether it was actually enforced depends on whether the governor was running at merge time. Per `memory/pr-handoff-workflow.md`: "governor disabled, agents create PRs and STOP, Sam merges." Sam merged PR #603 directly — bypassing the automated gate.

This is not a plan violation: Sam as CEO has authority to merge directly. But it means L3 evidence is now a post-merge obligation rather than a merge pre-condition, and the plan does not explicitly acknowledge this.

**Recommended amendment:**
Add a note to Phase 9 / L3 section: "Because Sam merged PR #603 directly (governor in PR-Handoff mode), L3 evidence was not a gate condition. L3 remains a completion obligation. Plan status cannot move to COMPLETED until L3 evidence files are committed to production."

---

## Finding 10 — Large Diff (1,463 Lines, 10 Files, New Module + Hook + Patch) Not Acknowledged in Plan

**Severity:** [WARNING]

**Evidence:**
S027-3c requires plans to note when a diff is large/complex enough to trigger <0.80 confidence in the governor's AI review. PR #603 introduced:
- 2 new utility modules (`company_lookup.py`, `non_store_billing.py`)
- 1 new override module (`overrides/employee_master.py`)
- 1 hooks.py modification
- 2 new patch files
- 3 new test files
- Modified `transfers.py`, `patches.txt`
- 2 CSV data seed files

The plan has no `confidence_note`, no `complexity_warning`, and no acknowledgment that the reviewer should apply extra scrutiny given the surface area. The governor's confidence calculation (per S101) applies a penalty for diffs >500 lines — a 1,463-line diff would likely trigger the <0.80 threshold.

The plan was effectively self-approved (Sam merged directly), so this gap did not block delivery. But it is a governance gap for future reference.

**Recommended amendment:**
Add to plan YAML:
```yaml
complexity_note: "Large diff: ~1,463 lines, 10 files, new module + validate hook + 2 patches. Governor confidence may fall below 0.80 threshold. Extra review recommended for company_lookup.py cache invalidation and non_store_billing.py rule ordering."
```

---

## Finding 11 — Preflight Dry-Run Approval Has No Actionable Trigger Mechanism

**Severity:** [CRITICAL]

**Evidence:**
Phase 7 states: "HARD BLOCKER: patch must be `--dry-run` first. No direct execution without Sam approval confirming dry-run report."

The actual execution sequence is:
1. `bench migrate` runs automatically (via GHA or manually) → patches run in dry-run mode → report written to `site/private/files/backfill_report_<timestamp>.json`.
2. Sam must review the report.
3. Sam must trigger re-execution in apply mode.

But there is no documented mechanism for step 3. The plan does not say:
- How Sam retrieves the report (Frappe file manager URL? SSH to EC2? `aws s3 cp`?).
- How Sam signals approval (comment on PR? Slack message? Direct SSH?).
- Who executes the apply command and where.
- What command to run exactly (and with correct `docker exec -e S201_APPLY=1` syntax — see Finding 3).

The PR body (step 5) gives the bare command but not the Docker wrapper, and does not describe the triggering mechanism. Phase 7 HARD BLOCKER is therefore unactionable as written.

**Recommended amendment:**
Add an explicit "Phase 7.5 — Dry-Run Review & Apply Authorization" section:
1. How to locate the dry-run report (Frappe > File Manager > search `backfill_report_`).
2. What Sam should verify in the report (before/after counts match expected ~510 store, ~45 HO, ~44 BKI).
3. Sam authorizes by replying on PR #603 thread or Slack `#erp-deploy` with "DRY-RUN APPROVED".
4. Exact apply command:
   ```bash
   BACKEND=$(docker ps --filter name=frappe_backend --format "{{.Names}}" | head -1)
   docker exec -e S201_APPLY=1 $BACKEND bench --site hq.bebang.ph execute \
     hrms.patches.v16_0.s201_rename_branches.execute
   docker exec -e S201_APPLY=1 $BACKEND bench --site hq.bebang.ph execute \
     hrms.patches.v16_0.s201_backfill_employee_company.execute
   ```

---

## Finding 12 — Phase 8 Is Missing (Gap Between Phase 7 and Phase 9 Closeout)

**Severity:** [WARNING]

**Evidence:**
Plan headings go: Phase 0, 1, 2, 3, 4, 5, 6, 7, then "Phase 9 — Closeout." There is no Phase 8. The PR body under "Phase status" table shows `P8 | L3 scenarios | Paused — Runs in fresh session post-deploy`. Phase 8 exists conceptually in the PR but not as a plan section.

This is not just a numbering typo — the absence means there is no Phase 8 section specifying:
- Who authors the Playwright script.
- What the script filename is.
- What the prerequisite state is (apply-mode must have run).
- What "fresh session" means operationally (new Claude Code session? New browser context?).
- Acceptance criteria for Phase 8 completion.

**Recommended amendment:**
Add Phase 8 between Phase 7 and Phase 9:

```markdown
## Phase 8 — L3 Evidence Capture (4u)

**Prerequisite:** Apply-mode patches have run. Employee counts verified per Phase 7.

- [ ] Author `scripts/testing/l3_s201_company_billing.mjs` covering scenarios L3-1 through L3-6.
- [ ] Run script in fresh Playwright session (new browser context, authenticated as test HR Manager).
- [ ] Confirm `output/l3/s201/{form_submissions,api_mutations,state_verification}.json` created.
- [ ] `git add -f output/l3/s201/` && commit to production.
```

---

## Finding 13 — L3-4 Transfer Test Requires Real Store Employee on SM Megamall; No Fixture Specified

**Severity:** [WARNING]

**Evidence:**
L3-4 says: "Pick store employee on SM MEGAMALL - BEI. Transfer to branch=SM MOA." This requires a real active employee currently assigned to SM MEGAMALL. After the backfill runs, any SM MEGAMALL employee will have `company = SM MEGAMALL - BEBANG ENTERPRISE INC.` — correct precondition.

However:
1. The plan does not specify which employee to use (employee ID, name).
2. Using a real production employee for a Transfer test creates a real Transfer record in Frappe (even if cancelled afterward), which may appear in HR audit logs.
3. If the test Transfer is submitted and approved, it changes the real employee's branch — requiring a manual reversal.
4. The plan does not include a cleanup step for test Transfers.

L3-5 at least specifies a bio ID (`bio 9000037`) for the roving employee test. L3-4 has no equivalent anchor.

**Recommended amendment:**
Either (a) specify a test employee ID (from `memory/testing-accounts.md`) assigned to SM MEGAMALL, or (b) create a test employee fixture with `designation=CASHIER, branch=SM MEGAMALL, dept=Operations` at the start of the L3 session and delete at the end. Add a cleanup step to the L3 script for all test employees and cancelled Transfer records created during the run.

---

## Summary

**CRITICAL: 4, WARNING: 6, INFO: 3**

| # | Severity | Finding |
|---|---|---|
| 1 | CRITICAL | Dry-run default safe but deploy workflow has no mechanism to trigger apply-mode |
| 2 | INFO | Idempotency safe; patch tracking means apply must use `bench execute`, not `bench migrate` |
| 3 | CRITICAL | `S201_APPLY=1` will not propagate through `docker exec` without `-e` flag |
| 4 | WARNING | Rollback contract does not address orphaned Salary Slips created post-backfill |
| 5 | CRITICAL | No Playwright L3 script exists; no capture mechanism; evidence directory absent |
| 6 | WARNING | L3-6 Salary Slip test has no payroll fixture and requires ordering dependency on apply-mode |
| 7 | WARNING | Plan YAML `status: GO` post-merge; no intermediate `DEPLOYED` status or update path |
| 8 | WARNING | Governor REJECT/NEEDS_FIX/deploy failure handlers not specified in plan |
| 9 | INFO | PR #603 merged without L3 evidence — release gate correctly bypassed (Sam direct merge); acknowledged as post-merge obligation |
| 10 | WARNING | 1,463-line diff not acknowledged; confidence threshold gap not documented |
| 11 | CRITICAL | Phase 7 HARD BLOCKER is unactionable — no mechanism to retrieve report or trigger apply run |
| 12 | WARNING | Phase 8 entirely absent from plan (exists in PR body only) |
| 13 | WARNING | L3-4 Transfer test uses unspecified real employee with no cleanup contract |

**CRITICAL: 4, WARNING: 6, INFO: 3**
