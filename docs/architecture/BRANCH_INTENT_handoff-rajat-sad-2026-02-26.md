# Branch Intent - handoff/rajat-sad-2026-02-26

**Last Updated:** 2026-02-26  
**Owner:** Sam Karazi  
**Branch:** `handoff/rajat-sad-2026-02-26`  
**Purpose:** Remote onboarding handoff package for Rajat (Tech Lead), centered on architecture truth, hosting/repo inventories, flow coverage catalog, and documentation drift gates.

## Why This Branch Exists

This branch isolates documentation handoff work from ongoing feature, deployment, and data-migration changes in the main working tree.
It is intended to be shared with Rajat for onboarding and system understanding.

## In Scope

1. SAD and architecture baseline docs.
2. Hosting/domain, repo, and infrastructure inventories.
3. Flow catalog and monthly architecture snapshot.
4. Documentation truth checker and CI workflow gate.

## Out of Scope

1. Feature development or bug fixes in `hrms/api` or frontend code.
2. Data migration scripts, scratchpad assets, or ad hoc experiments.
3. Any unrelated cleanup of existing dirty workspace files.

## Agent Guardrails (Read Before Editing)

1. Keep this branch doc-only unless explicitly instructed otherwise.
2. Do not add unrelated modified/untracked files from the workspace.
3. If you need to change runtime code, open a separate branch.
4. Preserve evidence-only policy: no assumptions, cite source files.

## Recommended Commit Prefixes

- `docs(handoff): ...`
- `docs(truth-gate): ...`

## Exit Criteria for Handoff

1. Rajat can open all linked docs remotely (GitHub).
2. `documentation_truth_check.py` passes in CI.
3. Handoff message with read order is sent to Rajat's `! Blip Notifications` space.
