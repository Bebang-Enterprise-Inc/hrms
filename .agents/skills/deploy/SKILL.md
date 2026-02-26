---
name: deploy
description: Validator-release workflow for packet integration with strict clean-room gates and production-only deploy.
allowed-tools: Bash, Read, Grep, Edit, Write, Task, Glob
user-invocable: true
---

# /deploy - Validator-Release Integration and Deployment

Use this skill only in the release/orchestrator lane.

Use when builder agents have pushed packet branches and you need to validate, integrate, and deploy safely without touching dirty root worktrees.

## Scope Guard (Mandatory)

Operate only in:

- `F:/Dropbox/Projects/BEI-ERP-orchestrator`

Never mutate from:

- `F:/Dropbox/Projects/BEI-ERP` (root dirty workspace)

Protected paths (read-only during release execution):

- `data/**`
- `archive/worktree-recovery/**`
- `output/worktree-snapshots/**` (except writing new snapshot folders)

## Clean-Room Safety Lock (Run First)

Before processing packets, run:

```powershell
git -C F:/Dropbox/Projects/BEI-ERP-orchestrator status --porcelain
gh run list --repo Bebang-Enterprise-Inc/hrms --workflow build-and-deploy.yml --limit 20 --json databaseId,status,conclusion,headBranch,createdAt,event
```

Required:
1. orchestrator dirty count is `0`
2. no unsafe in-flight deploy from `handoff/*` or `feature/*`

If either check fails, stop integration and resolve lock issues first.

Directory lock check:

```powershell
$repo = "F:/Dropbox/Projects/BEI-ERP-orchestrator"
if ((Resolve-Path .).Path -ne (Resolve-Path $repo).Path) {
  throw "Wrong working directory. Switch to $repo before continuing."
}
```

## Authority Model (Mandatory)

1. Builders can only push `feat/<run-id>/<packet-id>`.
2. Only `validator-release` can touch:
- `integration/*`
- `production`
- deployment workflow files and deploy execution

If a builder modifies deployment workflow files, reject the packet and return `rework`.

All integration and merge operations must be executed from `F:/Dropbox/Projects/BEI-ERP-orchestrator`.
Do not deploy from packet branches.

## Inputs Required Per Packet

- packet manifest entry (`packet_id`, owner, allowed file globs, acceptance tests)
- builder handoff file with:
  - branch
  - commit SHA
  - changed files
  - tests run
  - test result
  - known risks

## Per-Packet Validation Loop

1. Checkout `integration/<run-id>` in orchestrator.
2. Validate handoff completeness.
3. Validate changed files are inside packet `file_globs`.
4. Cherry-pick packet SHA using `-x` for traceability.
5. Run affected-scope gates:
- L1 API checks
- L2 page checks
- L3 workflow checks
6. If gates pass: mark packet `accepted`.
7. If gates fail:
- abort or revert the cherry-pick
- mark packet `rework`
- return to original builder with failure evidence

Command pattern:

```powershell
git switch integration/<run-id>
git cherry-pick -x <packet-sha>
# if conflicts:
git cherry-pick --abort
```

## Release Loop

1. Repeat packet loop until all packets are `accepted`.
2. Run final consolidated test sweep for impacted areas.
3. Open PR `integration/<run-id>` -> `production`.
4. Merge only after checks are green.
5. Deploy from `production` only.
6. Capture deployment evidence to `docs/testing/reports/`.
7. Run snapshot before cleanup.
8. Cleanup merged worktrees/branches only after successful deploy.

Production deploy command:

```powershell
gh workflow run build-and-deploy.yml --repo Bebang-Enterprise-Inc/hrms --ref production
gh run list --repo Bebang-Enterprise-Inc/hrms --workflow build-and-deploy.yml --limit 5 --json databaseId,status,conclusion,headBranch,createdAt,event
```

## Required Artifacts

1. `output/agent-runs/<run-id>/packet-status.md`
2. `output/agent-runs/<run-id>/integration-log.md`
3. `output/agent-runs/<run-id>/release-gate.md`
4. `output/agent-runs/<run-id>/deploy-report.md`

## Fast Reject Conditions

Reject immediately (no cherry-pick) if any are true:

- branch is not `feat/<run-id>/<packet-id>`
- missing handoff fields
- out-of-scope file changes
- builder touched `integration/*`, `production`, or deployment workflows
- packet asks to deploy directly from non-production branch

## Hard Stop Conditions

Stop immediately if any occurs:

- orchestrator working tree becomes dirty unexpectedly
- active deploy run from non-production branch appears
- packet introduces changes under protected data paths
- required L1/L2/L3 evidence is missing

## Completion Criteria

- [ ] all packets accepted or explicitly deferred
- [ ] all required L1/L2/L3 gates passed
- [ ] production deploy successful
- [ ] snapshot created
- [ ] cleanup completed safely
- [ ] clean-room safety lock checks passed before integration
