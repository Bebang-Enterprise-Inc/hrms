# Root Surgical Cleanup Implementation Plan

> **Execution Model:** validator-release pipeline with 4 builder worktrees.  
> **Core Rule:** Builders only push `feat/<run-id>/<packet-id>`; only validator-release can integrate/deploy.

**Goal:** Clean `F:/Dropbox/Projects/BEI-ERP` surgically (no blind purge), preserve all company data, and restore root repo usability without losing work.  
**Architecture:** Use clean-room orchestration from `F:/Dropbox/Projects/BEI-ERP-orchestrator`, split cleanup into packetized branches, preserve Git-worthy artifacts to integration branch, preserve local-only company data with explicit backup evidence, then apply allowlist-only cleanup in root.  
**Tech Stack:** Git worktrees, GitHub (`gh`), PowerShell, no-loss snapshot script (`scripts/git/no_loss_worktree_snapshot.ps1`).  
**Base Branch/Commit:** `origin/integration/cleanup-20260226` @ `0f11ef636`.

## 1) Run Metadata

- `run_id`: `root-cleanup-20260226`
- `validator session`: `validator-release`
- `builder sessions`: `builder-1`, `builder-2`, `builder-3`, `builder-4`
- `orchestrator repo`: `F:/Dropbox/Projects/BEI-ERP-orchestrator`
- `read-only context repo`: `F:/Dropbox/Projects/BEI-ERP`

### Backup Checkpoint (Completed)

- `status`: `COMPLETED`
- `backup destination`: `F:/BEI-ERP-BACKUPS/BEI-ERP_full_local_20260226_192709`
- `method`: `robocopy full copy + incremental pass`
- `log pass 1`: `F:/BEI-ERP-BACKUPS/logs/robocopy_20260226_192709.log`
- `log pass 2`: `F:/BEI-ERP-BACKUPS/logs/robocopy_20260226_192709_pass2.log`
- `backup report`: `F:/BEI-ERP-BACKUPS/BEI-ERP_full_local_20260226_192709_BACKUP_REPORT.md`
- `validation`: destination byte total matches source after pass 2.

## 2) Safety Rules (Non-Negotiable)

1. Never run `git clean -fdx` in root.
2. Never delete `data/**`, `archive/**`, or `output/worktree-snapshots/**`.
3. Root repo (`F:/Dropbox/Projects/BEI-ERP`) is read-only except explicit surgical cleanup commands in this plan.
4. One agent = one worktree = one branch.
5. Every destructive step requires pre-step evidence artifact.

## 3) Packet Manifest

| packet_id | owner | branch | worktree_path | file_globs | acceptance_tests |
|---|---|---|---|---|---|
| `p1-freeze-snapshot` | `builder-1` | `feat/root-cleanup-20260226/p1-freeze-snapshot` | `F:/Dropbox/Projects/BEI-ERP-cleanup-b1` | `docs/plans/**`, `output/worktree-snapshots/**` | root/orchestrator lock checks + fresh snapshot proof |
| `p2-git-preserve` | `builder-2` | `feat/root-cleanup-20260226/p2-git-preserve` | `F:/Dropbox/Projects/BEI-ERP-cleanup-b2` | `docs/**`, `.agents/skills/**` | targeted Git-preservation commits pushed to integration |
| `p3-local-data-protect` | `builder-3` | `feat/root-cleanup-20260226/p3-local-data-protect` | `F:/Dropbox/Projects/BEI-ERP-cleanup-b3` | `output/worktree-snapshots/**`, `output/agent-runs/**` | `data/**` protection report + hash manifest exists |
| `p4-surgical-clean` | `builder-4` | `feat/root-cleanup-20260226/p4-surgical-clean` | `F:/Dropbox/Projects/BEI-ERP-cleanup-b4` | `output/agent-runs/**`, `docs/plans/**` | tracked/untracked cleanup by allowlist + root clean gate |

## 4) Worktree Topology

1. Create all 4 worktrees from the same base commit (`0f11ef636`).
2. Builders work only in assigned worktrees.
3. `validator-release` integrates packets into `integration/root-cleanup-20260226`.

Setup commands:

```powershell
$ORCH = "F:/Dropbox/Projects/BEI-ERP-orchestrator"
git -C $ORCH fetch origin --prune
git -C $ORCH switch integration/cleanup-20260226

git -C $ORCH worktree add "F:/Dropbox/Projects/BEI-ERP-cleanup-b1" -b "feat/root-cleanup-20260226/p1-freeze-snapshot" 0f11ef636
git -C $ORCH worktree add "F:/Dropbox/Projects/BEI-ERP-cleanup-b2" -b "feat/root-cleanup-20260226/p2-git-preserve" 0f11ef636
git -C $ORCH worktree add "F:/Dropbox/Projects/BEI-ERP-cleanup-b3" -b "feat/root-cleanup-20260226/p3-local-data-protect" 0f11ef636
git -C $ORCH worktree add "F:/Dropbox/Projects/BEI-ERP-cleanup-b4" -b "feat/root-cleanup-20260226/p4-surgical-clean" 0f11ef636
```

## 5) Handoff Contract (Mandatory)

Each builder writes:

- `output/agent-runs/root-cleanup-20260226/handoffs/<packet_id>.md`

Required fields:

1. branch
2. commit SHA
3. changed files
4. tests run
5. test result
6. known risks

## 6) Task Plan

### Task 1: Freeze + Snapshot Gate

**Packet:** `p1-freeze-snapshot`  
**Owner:** `builder-1`

**Files**
- Create: `output/agent-runs/root-cleanup-20260226/lock-check.md`
- Create: `output/agent-runs/root-cleanup-20260226/snapshot-proof.md`
- Modify: `docs/plans/2026-02-26-root-surgical-cleanup-execution-plan.md`
- Test: `output/worktree-snapshots/<timestamp>/manifest.json`

**Step 1: Write failing test**
- Command:
```powershell
git -C F:/Dropbox/Projects/BEI-ERP status --porcelain | Measure-Object
```
- Expected: root dirty count is non-zero (currently high), proving cleanup is required.

**Step 2: Implement minimal code**
- Command:
```powershell
pwsh -File scripts/git/no_loss_worktree_snapshot.ps1
```
- Expected: new snapshot folder created under `output/worktree-snapshots/`.

**Step 3: Re-run targeted test**
- Command:
```powershell
Test-Path output/worktree-snapshots/<timestamp>/manifest.json
Test-Path output/worktree-snapshots/<timestamp>/all-refs.bundle
```
- Expected: both return `True`.

**Step 4: Run scoped regression checks**
- Command:
```powershell
git -C F:/Dropbox/Projects/BEI-ERP-orchestrator status --porcelain
gh run list --repo Bebang-Enterprise-Inc/hrms --workflow build-and-deploy.yml --limit 20 --json databaseId,status,conclusion,headBranch
```
- Expected: orchestrator clean, no unsafe in-flight non-production deploy.

**Step 5: Commit**
- Command:
```powershell
git add output/agent-runs/root-cleanup-20260226/lock-check.md output/agent-runs/root-cleanup-20260226/snapshot-proof.md docs/plans/2026-02-26-root-surgical-cleanup-execution-plan.md
git commit -m "chore(cleanup): lock and snapshot gates for root surgical cleanup"
```
- Expected: commit SHA generated.

### Task 2: Preserve Git-Worthy Artifacts First

**Packet:** `p2-git-preserve`  
**Owner:** `builder-2`

**Files**
- Create: `output/agent-runs/root-cleanup-20260226/git-preserve-candidates.md`
- Create: `output/agent-runs/root-cleanup-20260226/git-preserve-result.md`
- Modify: `.agents/skills/deploy/SKILL.md` (if drift found)
- Test: `docs/plans/2026-02-26-worktree-clean-room-consolidation-plan.md`

**Step 1: Write failing test**
- Command:
```powershell
git -C F:/Dropbox/Projects/BEI-ERP status --porcelain -- docs .agents/skills
```
- Expected: non-empty output (untracked/modified candidates exist).

**Step 2: Implement minimal code**
- Command:
```powershell
# prepare candidate list from root, then cherry-pick or copy into orchestrator branch
```
- Expected: Git-worthy docs/skill changes moved into clean-room branch only.

**Step 3: Re-run targeted test**
- Command:
```powershell
git -C F:/Dropbox/Projects/BEI-ERP-orchestrator log --oneline -n 20 integration/root-cleanup-20260226 -- docs .agents/skills
```
- Expected: preservation commits visible.

**Step 4: Run scoped regression checks**
- Command:
```powershell
git -C F:/Dropbox/Projects/BEI-ERP-orchestrator status --porcelain
```
- Expected: clean after commit/push.

**Step 5: Commit**
- Command:
```powershell
git add output/agent-runs/root-cleanup-20260226/git-preserve-candidates.md output/agent-runs/root-cleanup-20260226/git-preserve-result.md
git commit -m "docs(cleanup): preserve git-worthy artifacts before root cleanup"
```
- Expected: commit SHA generated.

### Task 3: Protect Local-Only Company Data

**Packet:** `p3-local-data-protect`  
**Owner:** `builder-3`

**Files**
- Create: `output/agent-runs/root-cleanup-20260226/local-data-protection.md`
- Create: `output/agent-runs/root-cleanup-20260226/local-data-hash-manifest.txt`
- Create: `output/agent-runs/root-cleanup-20260226/local-data-restore-test.md`
- Test: `data/**`, `data/Audits/**`

**Step 1: Write failing test**
- Command:
```powershell
git -C F:/Dropbox/Projects/BEI-ERP ls-files -- data/Audits | Measure-Object
```
- Expected: `0` tracked files for most of data tree, proving Git is not backup for company data.

**Step 2: Implement minimal code**
- Command:
```powershell
# generate hash manifest for protected local folders
Get-ChildItem -Path data -Recurse -File | Get-FileHash -Algorithm SHA256 | ForEach-Object { "$($_.Hash)  $($_.Path)" } | Set-Content output/agent-runs/root-cleanup-20260226/local-data-hash-manifest.txt
```
- Expected: hash manifest created.

**Step 3: Re-run targeted test**
- Command:
```powershell
Test-Path output/agent-runs/root-cleanup-20260226/local-data-hash-manifest.txt
Get-Content output/agent-runs/root-cleanup-20260226/local-data-hash-manifest.txt -TotalCount 5
```
- Expected: file exists and contains hashes.

**Step 4: Run scoped regression checks**
- Command:
```powershell
Test-Path data
Test-Path data/Audits
```
- Expected: both `True`.

**Step 5: Commit**
- Command:
```powershell
git add output/agent-runs/root-cleanup-20260226/local-data-protection.md output/agent-runs/root-cleanup-20260226/local-data-hash-manifest.txt output/agent-runs/root-cleanup-20260226/local-data-restore-test.md
git commit -m "docs(cleanup): add local-only company data protection evidence"
```
- Expected: commit SHA generated.

### Task 4: Surgical Root Cleanup (Allowlist-Only)

**Packet:** `p4-surgical-clean`  
**Owner:** `builder-4`

**Files**
- Create: `output/agent-runs/root-cleanup-20260226/delete-allowlist.txt`
- Create: `output/agent-runs/root-cleanup-20260226/delete-execution-log.md`
- Create: `output/agent-runs/root-cleanup-20260226/root-clean-gate.md`
- Test: root Git status output

**Step 1: Write failing test**
- Command:
```powershell
git -C F:/Dropbox/Projects/BEI-ERP status --porcelain | Measure-Object
```
- Expected: non-zero dirty count.

**Step 2: Implement minimal code**
- Command:
```powershell
# only explicit path cleanup; no wildcard purge, no -fdx
# examples:
# git -C F:/Dropbox/Projects/BEI-ERP restore --worktree --staged -- docs/plans/<obsolete-file>.md
# git -C F:/Dropbox/Projects/BEI-ERP clean -fd -- <explicit-temp-path>
```
- Expected: dirty count drops without touching protected paths.

**Step 3: Re-run targeted test**
- Command:
```powershell
git -C F:/Dropbox/Projects/BEI-ERP status --porcelain
```
- Expected: empty or only explicitly approved keep-local residues.

**Step 4: Run scoped regression checks**
- Command:
```powershell
Test-Path data
Test-Path data/Audits
Test-Path output/worktree-snapshots
```
- Expected: all `True`.

**Step 5: Commit**
- Command:
```powershell
git add output/agent-runs/root-cleanup-20260226/delete-allowlist.txt output/agent-runs/root-cleanup-20260226/delete-execution-log.md output/agent-runs/root-cleanup-20260226/root-clean-gate.md
git commit -m "docs(cleanup): execute root surgical cleanup with allowlist controls"
```
- Expected: commit SHA generated.

## 7) Validator Integration Loop

1. Create `integration/root-cleanup-20260226` from `integration/cleanup-20260226`.
2. Read each packet handoff file.
3. Reject packet if changed files are outside declared `file_globs`.
4. Cherry-pick one packet SHA at a time with `-x`.
5. After each packet, run cleanup validation gates:
   - lock checks still pass
   - protected data paths remain intact
   - no unsafe deploy run
6. If gate fails, abort/revert packet and mark `rework`.

## 8) Release Gate

1. Merge `integration/root-cleanup-20260226` -> `production` only after all packets pass.
2. Deploy from `production` only.
3. Rollback plan required in `release-gate.md`:
   - previous production SHA
   - revert strategy
   - post-rollback verification checks

## 9) Snapshot + Cleanup Contract

1. Run fresh snapshot immediately before final root cleanup execution.
2. Run fresh snapshot immediately after final root cleanup gate passes.
3. Keep both snapshots for rollback window.

## 10) GO/NO-GO Criteria

**GO only if all are true:**

1. Local backup checkpoint in this plan exists and is verified.
2. Root `git status --porcelain` is empty or explicitly approved residuals documented.
3. `data/**` and `data/Audits/**` verified present after cleanup.
4. Clean-room branch contains all preservation commits.
5. Deploy history shows no non-production unsafe deployment.
6. Snapshot-before and snapshot-after artifacts both exist.

**NO-GO if any are true:**

1. Backup destination is missing or unreadable.
2. Any `git clean -fdx` usage in logs.
3. Any missing protected path after cleanup.
4. Any packet missing handoff fields.
5. Any out-of-scope packet change accepted.

## 11) Required Output Files

1. `docs/plans/2026-02-26-root-surgical-cleanup-execution-plan.md`
2. `output/agent-runs/root-cleanup-20260226/RUN_MANIFEST.md`
3. `output/agent-runs/root-cleanup-20260226/PACKET_TEMPLATE.md`
4. `output/agent-runs/root-cleanup-20260226/HANDOFF_TEMPLATE.md`
5. `output/agent-runs/root-cleanup-20260226/packet-status.md`
6. `output/agent-runs/root-cleanup-20260226/integration-log.md`
7. `output/agent-runs/root-cleanup-20260226/release-gate.md`
8. `output/agent-runs/root-cleanup-20260226/deploy-report.md`

## 12) Execution Update (2026-02-26)

### Completed

1. Startup lock checks confirmed:
   - root branch: `handoff/rajat-sad-2026-02-26`
   - orchestrator branch: `integration/cleanup-20260226`
2. Fresh no-loss snapshot captured:
   - `output/worktree-snapshots/20260226_194947/manifest.json`
   - `output/worktree-snapshots/20260226_194947/all-refs.bundle`
3. Tracked drift neutralized safely in root:
   - tracked dirty: `548 -> 0`
   - tracked diffs preserved in snapshot:
     - `root_tracked_worktree.diff`
     - `root_tracked_staged.diff`
4. Surgical transient cleanup executed (explicit allowlist only):
   - allowlist: `output/agent-runs/root-cleanup-20260226/delete-allowlist.txt`
   - execution log: `output/agent-runs/root-cleanup-20260226/delete-execution-log.md`
5. Protected path checks passed:
   - `data/**`
   - `data/Audits/**`
   - `output/worktree-snapshots/**`

### Current Gate

1. `tracked changes`: `0` (PASS)
2. `untracked residuals`: `112` (TRIAGE PENDING)
3. gate status: `PARTIAL_PASS`

Reference:
- `output/agent-runs/root-cleanup-20260226/lock-check.md`
- `output/agent-runs/root-cleanup-20260226/snapshot-proof.md`
- `output/agent-runs/root-cleanup-20260226/root-clean-gate.md`

### Remaining

1. Triage the 112 untracked residuals into:
   - `promote_to_git`
   - `keep_local_ignored`
   - `archive_and_remove`
2. Run post-triage snapshot (`snapshot-after`) and finalize GO/NO-GO.
