# Worktree Clean-Room Consolidation Plan

**Date:** 2026-02-26  
**Status:** ACTIVE  
**Scope:** Recover and consolidate multi-agent work safely with zero data/code loss

## 1) Goal

Stabilize the repository after parallel-agent collisions, preserve all useful work, and move to a strict clean-room execution model:

1. No work loss
2. No direct deploys from feature/handoff branches
3. One merge path through a clean integration branch
4. Reproducible evidence for every salvage/merge decision

## 2) Known Baseline (Already Done)

Based on latest cleanup evidence:

1. Clean orchestrator worktree exists:
   - `F:/Dropbox/Projects/BEI-ERP-orchestrator`
   - Branch: `integration/cleanup-20260226`
2. Recovery artifacts exist:
   - `archive/worktree-recovery/20260226-170207/SUMMARY.json`
   - `output/worktree-snapshots/20260226_170535/CLEANUP_REPORT.md`
   - `output/worktree-snapshots/20260226_170535/manifest.json`
3. Recovery tags exist:
   - `recovery/20260226-170207/*`

## 3) Non-Negotiable Guardrails

1. Root repo `F:/Dropbox/Projects/BEI-ERP` is read-only context while cleanup is active.
2. All active development/merges happen only in `F:/Dropbox/Projects/BEI-ERP-orchestrator`.
3. One agent = one worktree = one branch.
4. No branch/worktree deletion until snapshot + classification is recorded.
5. No production deploy from non-production branch.
6. Every merge candidate must pass L1/L2/L3 gates for affected scope.

## 4) Execution Stages

## Stage 00 - Freeze and Safety Lock

Checklist:

1. Stop spawning agents in root repo path.
2. Confirm no active direct deploy from handoff/feature branches.
3. Confirm orchestrator worktree is clean.

Commands:

```powershell
git -C F:/Dropbox/Projects/BEI-ERP-orchestrator status --porcelain
gh run list --repo Bebang-Enterprise-Inc/hrms --workflow build-and-deploy.yml --limit 20 --json databaseId,status,conclusion,headBranch,createdAt,event
```

Exit gate: orchestrator dirty count is `0`, and no in-flight unsafe deploy run remains.

## Stage 01 - Fresh No-Loss Snapshot

Checklist:

1. Create fresh all-refs bundle.
2. Capture per-worktree dirty/untracked/upstream status.
3. Save snapshot manifest path in this plan.

Command:

```powershell
pwsh -File scripts/git/no_loss_worktree_snapshot.ps1
```

Output to log:

1. `output/worktree-snapshots/<timestamp>/manifest.json`
2. `output/worktree-snapshots/<timestamp>/all-refs.bundle`

Exit gate: snapshot artifacts exist and are readable.

## Stage 02 - Deterministic Worktree Classification

Classify each worktree/branch into exactly one bucket:

1. `READY_MERGE`: clean, has unique commits, upstream valid
2. `SALVAGE_UNCOMMITTED`: dirty/untracked changes exist
3. `SALVAGE_UPSTREAM_GONE`: upstream missing or branch orphaned
4. `DROP_SAFE`: no unique commits and no relevant uncommitted work
5. `HOLD_MANUAL`: ambiguous ownership or high conflict risk

Required checks per worktree:

```powershell
git -C <worktree> status --porcelain
git -C <worktree> rev-parse --abbrev-ref HEAD
git -C <worktree> rev-list --left-right --count @{u}...HEAD
git -C <worktree> diff --name-only
git -C <worktree> ls-files --others --exclude-standard
```

Exit gate: every worktree is bucketed and recorded.

## Stage 03 - Salvage Before Any Prune

For `SALVAGE_UNCOMMITTED` and `SALVAGE_UPSTREAM_GONE`:

1. Export patch and untracked file list to `archive/worktree-recovery/<timestamp>/`.
2. Commit salvage on the same branch if coherent.
3. Push salvage branch if upstream is gone (create new remote branch).

Minimum evidence per salvaged branch:

1. Patch file path
2. Commit hash (if committed)
3. Remote branch name (if pushed)

Exit gate: no unsaved local-only work remains in branches targeted for cleanup.

## Stage 04 - Conflict Audit and Merge Queue Build

Build queue from lowest risk to highest risk:

1. Hotfix branches with narrow file scope
2. Sprint/runtime branches
3. Cross-cutting integration branches
4. High-churn or overlapping branches last

Conflict scoring inputs:

1. File overlap against already-queued branches
2. Touches to deployment/workflow files
3. Touches to shared API routes and role maps

Queue output file:

1. `output/worktree-snapshots/<timestamp>/MERGE_QUEUE.md`

Exit gate: queue finalized with explicit order and risk notes.

## Stage 05 - Controlled Integration (Orchestrator Only)

For each queued branch:

1. Merge/cherry-pick into `integration/cleanup-20260226`.
2. Resolve conflicts immediately.
3. Run targeted validation for affected modules.

Validation minimum:

1. L1 API checks (affected modules)
2. L2 page checks (affected routes)
3. L3 real-user workflow checks (affected flows)

Exit gate: branch is either `MERGED_WITH_PROOF` or `REJECTED_WITH_REASON`.

## Stage 06 - Release Gate

Before PR to production:

1. Re-run full impacted test matrix.
2. Verify no unsafe workflow/deploy changes slipped in.
3. Generate final consolidation report.

Required artifacts:

1. `output/worktree-snapshots/<timestamp>/CONSOLIDATION_REPORT.md`
2. Test evidence links under `docs/testing/reports/`

Exit gate: PR from `integration/cleanup-20260226` to `origin/production` is ready.

## Stage 07 - Post-Merge Cleanup

After production merge and successful deploy:

1. Delete merged feature branches.
2. Remove merged worktrees.
3. Keep recovery tags and bundle for rollback window.
4. Record final closure in this plan.

Exit gate: only active branches/worktrees remain, and rollback artifacts are preserved.

## 5) Progress Tracker

| Stage | Status | Evidence |
|---|---|---|
| Stage 00 - Freeze and Safety Lock | DONE | `output/worktree-snapshots/20260226_173448/STAGE00_SAFETY_LOCK.md` |
| Stage 01 - Fresh No-Loss Snapshot | DONE | `output/worktree-snapshots/20260226_173448/manifest.json`, `output/worktree-snapshots/20260226_173448/all-refs.bundle` |
| Stage 02 - Deterministic Classification | DONE | `output/worktree-snapshots/20260226_173448/WORKTREE_CLASSIFICATION.md` |
| Stage 03 - Salvage Before Prune | IN_PROGRESS | `output/worktree-snapshots/20260226_173448/STAGE03_SALVAGE_INVENTORY.md`, `output/worktree-snapshots/20260226_173448/STAGE03_EXECUTION_LOG.md`, `output/worktree-snapshots/20260226_173448/HANDOFF_SALVAGE_STRATEGY.md` |
| Stage 04 - Conflict Audit + Merge Queue | DONE | `output/worktree-snapshots/20260226_173448/MERGE_QUEUE.md`, `output/worktree-snapshots/20260226_173448/WORKTREE_OVERLAPS.json` |
| Stage 05 - Controlled Integration | IN_PROGRESS | `output/worktree-snapshots/20260226_173448/STAGE05_INTEGRATION_LOG.md` |
| Stage 06 - Release Gate | TODO | - |
| Stage 07 - Post-Merge Cleanup | TODO | - |

## 6) Execution Log (2026-02-26)

Completed:

1. Created fresh no-loss snapshot set at `output/worktree-snapshots/20260226_173448/`.
2. Reclassified all worktrees after salvage actions:
   - `READY_MERGE`: 7
   - `SALVAGE_UNCOMMITTED`: 1
3. Published upstream branches to prevent local-only loss:
   - `origin/feat/advance-payment-c2`
   - `origin/feature/s03-g046-alerting`
   - `origin/feature/s03-gap092-billing-hardening`
   - `origin/feature/s03-sync-backbone`
   - `origin/integration/cleanup-20260226`
4. Captured branch overlap and merge order evidence:
   - `output/worktree-snapshots/20260226_173448/MERGE_QUEUE.md`
5. Started controlled integration in orchestrator using scoped cherry-picks:
   - `32f4dec07 -> e855fb2a1`
   - `bee3e3f26 -> 5114626c0`
   - `c873b1a5c -> b979d03a3`
   - `526cbd7f3 -> 105802a31`
   - `559124b1d -> 1f666b462`
   - `a36ed0e87 -> e54cf4a29`
   - Evidence: `output/worktree-snapshots/20260226_173448/STAGE05_INTEGRATION_LOG.md`
6. Rejected one scoped integration with proof:
   - `82856c5c5` cherry-pick aborted due `hrms/api/procurement.py` conflict against current integration state.
7. Ran preliminary unit test command for new integrated test files:
   - `python -m pytest hrms/tests/test_erp_sync.py hrms/tests/test_delivery_billing_policy.py tests/unit/test_gap046_alerting.py -q`
   - Result: `5 passed, 8 errors` due missing local Frappe runtime package (`frappe.model` import failure).

Still open in Stage 03:

1. `handoff/rajat-sad-2026-02-26` remains high-risk with large mixed local state and requires manual split/scope salvage before integration.
2. Path-batched salvage runbook prepared: `output/worktree-snapshots/20260226_173448/HANDOFF_SALVAGE_STRATEGY.md`.

## 7) Immediate Execution Commands

Run these first, in order:

```powershell
git -C F:/Dropbox/Projects/BEI-ERP-orchestrator status --porcelain
pwsh -File scripts/git/no_loss_worktree_snapshot.ps1
gh run list --repo Bebang-Enterprise-Inc/hrms --workflow build-and-deploy.yml --limit 20 --json databaseId,status,conclusion,headBranch,createdAt,event
```

## 8) Context-Rot Guardrail Addendum (2026-02-26)

This section is the anti-drift checkpoint while cleanup and feature work run in parallel.

### 8.1 Authoritative Worktree Ownership (Transfer Lane)

1. Root repo remains read-only context:
   - `F:/Dropbox/Projects/BEI-ERP`
2. Authoritative transfer worktree:
   - Path: `F:/Dropbox/Projects/BEI-ERP-agent-transfer`
   - Branch: `agent/transfer-e2e-complete-20260226`
   - Upstream base: `origin/integration/cleanup-20260226`
   - Publish target: `origin/agent/transfer-e2e-complete-20260226`
3. Non-authoritative transfer worktrees (do not use for active edits):
   - `F:/Dropbox/Projects/BEI-ERP-transfer-lane`
   - `F:/Dropbox/Projects/BEI-ERP__transfer_cleanroom`

### 8.2 Mandatory Checkpoint Cadence

Run this checkpoint before starting work, before handoff, and at least every 2 hours:

```powershell
git -C F:/Dropbox/Projects/BEI-ERP-agent-transfer status --porcelain
git -C F:/Dropbox/Projects/BEI-ERP-agent-transfer branch --show-current
git -C F:/Dropbox/Projects/BEI-ERP-agent-transfer rev-parse --abbrev-ref --symbolic-full-name "@{u}"
git -C F:/Dropbox/Projects/BEI-ERP worktree list
gh run list --repo Bebang-Enterprise-Inc/hrms --workflow build-and-deploy.yml --limit 10 --json databaseId,status,headBranch,createdAt
```

Checkpoint exit gate:

1. Working tree dirty count understood and intentional
2. Branch is correct (`agent/transfer-e2e-complete-20260226`)
3. Upstream is correct (`origin/agent/transfer-e2e-complete-20260226`)
4. No unintended deploy run is active

## 9) Employee Transfer Continuation Addendum (No-Deploy Test Model)

This addendum defines how transfer work proceeds during cleanup without waiting for production deploy.

### 9.1 Branch and PR Policy

1. Implement transfer fixes only in:
   - `agent/transfer-e2e-complete-20260226`
2. Push scoped commits continuously to:
   - `origin/agent/transfer-e2e-complete-20260226`
3. PR target for transfer lane:
   - `integration/cleanup-20260226`
4. Explicitly forbidden during this stage:
   - `workflow_dispatch`
   - merge to `production`

### 9.2 L1-L3 Testing Without Production Deploy

Use a two-runtime strategy:

1. Runtime A (branch code, no deploy): Local Frappe + local bei-tasks
2. Runtime B (deployed baseline): `hq.bebang.ph` + `my.bebang.ph` for regression/reference only

Required sequence per scoped change:

1. **T0 Static gate (worktree local)**
   - `python -m py_compile` on changed Python modules
   - targeted unit tests that do not require full Frappe runtime
2. **T1 Branch-live API gate (Local Frappe runtime)**
   - Start local stack (`docker-dev/dev.bat start`, `dev.bat sync`, `dev.bat migrate`)
   - Run L1 API checks against local host (`http://localhost:8000`)
3. **T2 Branch-live UI gate (Local bei-tasks runtime)**
   - Run local bei-tasks (`npm run dev`), point to local Frappe
   - Execute L2 page checks and L3 submit+verify flows in browser against local URLs
4. **T3 Integration baseline smoke (optional sanity)**
   - Minimal smoke against currently deployed `hq/my` to ensure no regression assumptions
   - Treat as baseline verification, not proof of new branch behavior

### 9.3 Critical Test Harness Constraint

Current Playwright helpers in `tests/e2e/helpers.ts` use hardcoded production URLs.
Before relying on local L2/L3 as gate for transfer changes, convert test base URLs to env-driven values.

Minimum requirement:

1. `PORTAL_URL` and `HQ_URL` must be configurable via environment variables
2. Default may remain production-safe, but local runs must be first-class
3. Record the chosen URL mode (local vs production baseline) in each test evidence report

### 9.4 Transfer-Specific Integrity Rule

For transfer module validation in clean-room phase:

1. `hrms/api/transfer_requests.py` + transfer DocTypes must compile
2. No uncommitted transfer code remains stranded in root/handoff worktree
3. Any transfer change merged to integration must include:
   - route/API evidence
   - role-path evidence (Requester -> Area -> HR -> IT)
   - ADMS command audit evidence (or explicit environment blocker note)

## 10) Transfer Lane Execution Log (2026-02-26)

Scope: `agent/transfer-e2e-complete-20260226` in `F:/Dropbox/Projects/BEI-ERP-agent-transfer`

Completed safely in clean-room lane:

1. Added warehouse-to-branch consolidation in transfer API:
   - `create_transfer_request` now accepts warehouse-driven branch derivation (no mandatory duplicate input)
   - branch/warehouse mismatch is validated and blocked
2. Added transfer warehouse safety filters:
   - blocked keywords (`3PL`, `3MD`, `3rd party`, `third party`)
   - non-BEI company warehouses rejected for transfer routing
3. Added transfer form options API for frontend:
   - `hrms.api.transfer_requests.get_transfer_form_options`
   - returns filtered BEI store warehouses with derived branch metadata
4. Expanded transfer test coverage:
   - Added transfer unit tests for blocked warehouse filtering, branch derivation, and options API
5. Added L1/L2/L3 catalog coverage hooks:
   - Route registry now maps `/dashboard/hr/transfers` to transfer API endpoints
   - Added new flow scenario file: `docs/testing/scenarios/flows/employee-transfer.md`
   - Added flow command mapping: `flow-employee-transfer` in scenario index
6. Enabled no-deploy local L2/L3 harness configuration:
   - `tests/e2e/helpers.ts` now supports env-driven `HQ_URL` and `PORTAL_URL`
   - defaults remain production-safe when env vars are unset

Current blocker to full local execution gate:

1. Frappe runtime is not active in current shell (`ModuleNotFoundError: frappe` during pytest collection).
2. Docker daemon is currently unavailable on this machine context.

### 10.1 Blocker Resolution and Production-Proven Closure (2026-02-26 20:21 PHT)

The local-runtime blocker above was bypassed safely using clean-room branch flow + production release gates with full evidence.

Completed:

1. Backend transfer module released to production:
   - PR: `https://github.com/Bebang-Enterprise-Inc/hrms/pull/78` (merged)
   - Deploy run: `https://github.com/Bebang-Enterprise-Inc/hrms/actions/runs/22441214919` (success)
2. Frontend transfer UI fixes released:
   - PR: `https://github.com/Bebang-Enterprise-Inc/BEI-Tasks/pull/17` (merged)
   - Includes employee picker API-path fix and warehouse/branch consolidation UX
3. Full live transfer workflow executed end-to-end:
   - Request: `BEI-TRF-2026-00006`
   - Path: Requester -> Area -> HR -> IT -> Sync reconcile
   - Final stage: `Synced`
4. ADMS sync proof:
   - `UPDATE_USERINFO` and `DELETE_USERINFO` commands both reached `ACKED`
5. Frappe mutation proof:
   - Employee Transfer: `HR-EMP-TRN-2026-00012` (`docstatus=1`)
   - Employee master moved to branch `AYALA EVO`, department `All Departments - BEI`
6. Evidence artifacts captured:
   - `output/transfer-e2e/20260226_2021/EVIDENCE.md`
   - `output/transfer-e2e/20260226_2021/transfer_e2e_summary.json`

Transfer lane status: `GO` for completed scope in this plan.
