# S182 — L3 session mode decision

**Decision:** Phase 9 (L3 browser scenarios) will run in a **separate fresh
Claude Code session** per the S092 rule for plans > 40 units.

## Why

- Total plan: 67 units (frontend 56u + backend 11u). Above the 40u threshold.
- This executor has motivated reasoning about whether the work passes — fresh
  L3 session mitigates corrupt-success risk (S092 incident, ~70% drop in
  corrupt-success rate per arXiv 2603.03116).
- Backend rebuild via `build-and-deploy.yml` is a hard prerequisite for the
  L3 scenarios that exercise per-channel columns + sparkline (L3-182-13 and
  L3-182-13a). Sam dispatches the workflow with `skip_build=false` and
  `no_cache=true` BEFORE the L3 session can start.

## Sequencing

1. **Now (this session):** Frontend + backend code committed on S182 branches,
   verify_s182.py PASS, both branches pushed, both PRs created. Status →
   `READY_FOR_REVIEW`.
2. **Sam:** Reviews the two PRs, dispatches build-and-deploy.yml from the
   hrms PR with `skip_build=false, no_cache=true` so the new
   `_get_store_channel_split_map` / `_get_store_website_split_map` symbols
   ship to production.
3. **Fresh L3 session:** Sam runs `/l3-v2-bei-erp s182` against
   hq.bebang.ph + the deployed bei-tasks preview. Evidence lands in
   `output/l3/s182/` and is committed onto the hrms branch (Phase 9.7
   evidence push gate).
4. **Closeout:** L3 session updates plan YAML to `status: COMPLETED`, fills
   in execution_summary, and updates SPRINT_REGISTRY.md with both PR numbers
   + L3 result.

## What this session leaves on disk

| Artifact | Path |
|---|---|
| Baseline | `output/s182/BASELINE.md` |
| MV column verification | `output/s182/mv_column_verification.md` |
| Phase B completion record | `output/s182/phase_B_completion.md` |
| Backend timing measurement plan | `output/s182/backend_timing.md` |
| Filesystem verifier | `output/s182/verify_s182.py` |
| Verifier output | `output/s182/verify_output.txt` |
| L3 session mode decision (this file) | `output/s182/l3_session_mode.md` |

## What the L3 session needs to produce

- `output/l3/s182/evidence/L3-182-{01..20,13a}.json` — 21 evidence files
- `output/l3/s182/form_submissions.json`
- `output/l3/s182/api_mutations.json`
- `output/l3/s182/state_verification.json`
- `output/l3/s182/SUMMARY.md` (PASS/FAIL per scenario + completion table)
- `output/l3/s182/artifacts/*.png` + `trace.zip`
- `output/s182/viewport_proof/desktop_1366x768.png` (Rule 5A)
- `output/s182/viewport_proof/mobile_390x844.png` (Rule 5C)
- `scripts/testing/l3_s182_store_drilldown.mjs` (the runner script)

After all 21 scenarios PASS or DEFECT-PASS, commit evidence to the
`s182-store-rankings-per-channel` branch, push, request PR re-review.
