```yaml
canonical_sprint_id: S105
status: GO
created_date: 2026-03-24
branch: s105-docker-build-acceleration
lane: single
estimated_work_units: 18
completed_date:
execution_summary:
audit_version: 4
audit_date: 2026-03-24
```

# S105: Full Pipeline Acceleration — 11 min to Under 5 min

## Execution Amendment v4 (2026-03-24) — Validated Build + Deploy Optimization

Previous plan versions proposed a pre-built base image. Real benchmarking proved that unnecessary — the winning approach overlays `git clone --depth 1` on the existing production image and pushes to GHCR with zstd compression.

**Validated build results (5 runs, unique SHAs):**

| Run | Build Time | SHA |
|-----|-----------|-----|
| 1 | 125s (2.1m) | c1cb3be |
| 2 | 135s (2.2m) | 6e3c3ba |
| 3 | 121s (2.0m) | 71877bf |
| 4 | 152s (2.5m) | acf9854 |
| 5 | 148s (2.5m) | adbeb5e |
| **Avg** | **136s (2.3m)** | |

**Current baseline (17 production runs):** Build avg 5m07s + Deploy avg 5m40s = ~11 min total

**Target:** Full pipeline (build + deploy) under 5 minutes.

### Key findings from continuous improvement loop

| Finding | Detail |
|---------|--------|
| Pre-built base image NOT needed | Overlaying on production image works. No separate frappe-base to maintain. |
| GHCR is 7.5x faster than Docker Hub | Same datacenter as GHA runners. Push: 78s to 10s. |
| Zstd compression 4.2x faster export | Layer export: 56s to 13s. |
| gcc/build-essential NOT needed | pip install had zero C compilations. Saves 11s. |
| git clone --depth 1 faster than bench get-app | Direct clone skips bench overhead. Needs explicit yarn install. |
| PWA/roster builds must be skipped | Workbox peer deps missing in overlay builds. PWA deploys via Vercel, not Docker. |
| Single combined layer KILLS push | One layer = 232s push. Separate small layers = 10-78s push. |
| .git dirs stripped by upstream | Cannot git fetch in-place on production images. |
| Deploy has 3 unnecessary SSM rounds | Sentry DSN + Supabase env as separate service updates = 2 extra minutes. |
| Queue wait dominates wall clock | cancel-in-progress: false causes 10-22 min queue for back-to-back merges. |

Iteration log: `output/continuous-improvement/s105-docker-fast-build/ITERATION_LOG.md`

---

## Summary

Cut the full pipeline (build + deploy) from ~11 minutes to under 5 minutes through three changes:

1. **Fast build (validated at 2.3 min):** GHCR push + zstd compression + git clone --depth 1 overlay on production image
2. **Consolidated deploy (target ~2 min):** Combine 3 SSM rounds into 1 + parallel Swarm service updates
3. **Smart concurrency:** Split build/deploy groups so back-to-back merges only build once

## Design Rationale (For Cold-Start Agents)

### Why this exists

Every PR merge triggers a full Docker build (~5 min) + sequential deploy (~6 min) = ~11 min. When multiple PRs merge back-to-back, each queues behind the previous — 3 PRs = 33 min total wait.

### Proven build approach (from 5 iterations of real testing)

The fast build overlays fresh hrms code on the existing production image. No separate base image needed.

```dockerfile
FROM samkarazi/bebang-erpnext-hrms:v15   # existing production image
ARG HRMS_SHA                              # cache-bust per commit
RUN rm -rf apps/hrms \
    && git clone --depth 1 --branch production <url> apps/hrms \
    && yarn install && pip install && bench build --app hrms
```

Pushed to GHCR (same datacenter as GHA runners) with zstd compression. Result: **2.3 min average** (validated 5 runs).

### Deploy bottleneck analysis

Current deploy runs 3 separate SSM commands that each restart Swarm services:

| Round | What | Time |
|-------|------|------|
| 1 | `docker service update --image` (6 services, sequential) | 3m57s |
| 2 | `docker service update --env-add SENTRY_DSN` (4 services) | 1m00s |
| 3 | `docker service update --env-add SUPABASE_*` (4 services) | 1m00s |

Fix: one round with all env vars + parallel service updates.

### Concurrency bottleneck

Current config queues all runs — 3 PRs merged back-to-back = 33 min total.
Fix: separate build and deploy groups. Builds cancel (safe), deploys never cancel (unsafe mid-SSM).

### Source references

- Current workflow: `.github/workflows/build-and-deploy.yml` (638 lines)
- Validated Containerfile: `.github/docker/Containerfile.fast` (on s105 branch)
- Validated workflow: `.github/workflows/build-fast.yml` (on s105 branch)
- Iteration log: `output/continuous-improvement/s105-docker-fast-build/`
- Deploy skill: `.claude/skills/deploy-frappe/SKILL.md`

## Requirements Regression Checklist

- [ ] Does Containerfile.fast use `git clone --depth 1` (NOT `bench get-app`)?
- [ ] Does Containerfile.fast include `HRMS_SHA` build arg for cache-busting?
- [ ] Does Containerfile.fast skip PWA/roster builds (neuter package.json build script)?
- [ ] Does Containerfile.fast NOT install gcc/build-essential?
- [ ] Does Containerfile.fast add `yarn install` after git clone?
- [ ] Does build-fast.yml push to GHCR (NOT Docker Hub)?
- [ ] Does build-fast.yml use zstd compression + OCI mediatypes?
- [ ] Does build-fast.yml use `type=registry` cache with `image-manifest=true`?
- [ ] Does build-fast.yml set `provenance: false` and skip QEMU?
- [ ] Does the consolidated deploy combine image + Sentry + Supabase in ONE `docker service update`?
- [ ] Are all 6 Swarm services updated in parallel (`--detach=true`) then verified once?
- [ ] Does the deploy concurrency group never cancel mid-SSM?
- [ ] Does the build concurrency group allow cancel-in-progress?
- [ ] Are ALL post-deploy steps preserved (nginx fix, Blip proxy, migrations, Redis flush, asset sync, verification)?
- [ ] Does EC2 have Docker 25+ for zstd image pull?
- [ ] Does EC2 have GHCR credentials configured?

## Scope

### In Scope

| Item | Classification |
|------|----------------|
| Fast Containerfile (GHCR + zstd + git clone overlay) | [PROVEN] |
| Fast build workflow (push to GHCR) | [PROVEN] |
| Consolidated deploy (1 SSM round + parallel updates) | [BUILD] |
| Smart concurrency (split build/deploy groups) | [BUILD] |
| EC2 verification (zstd pull + GHCR auth) | [VERIFY] |
| Production swap | [EXTEND] |

### Out of Scope

- Pre-built base image (ABANDONED — unnecessary, adds maintenance burden)
- Self-hosted runners / Docker Build Cloud
- Changing EC2 infrastructure

## Phase A: Deploy Consolidation + Smart Concurrency (8 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| A1 | BUILD | Create consolidated deploy SSM command. Combine image update + Sentry DSN + Supabase env into ONE `docker service update` per service. Update all 6 services in parallel with `--detach=true`, then poll for convergence. Test manually via SSM first (does NOT touch workflow). | 3 |
| A2 | VERIFY | Run the consolidated SSM command on EC2 (manual, not workflow). Verify: (1) all 6 services updated, (2) env vars set, (3) API returns pong, (4) assets load correctly. | 2 |
| A3 | BUILD | Update `build-fast.yml` to add consolidated deploy job (after build succeeds). This makes `build-fast.yml` a full build+deploy test lane. Deploy only to test — does NOT touch production tag. | 2 |
| A4 | VERIFY | Run full pipeline test: trigger `build-fast.yml`, verify build <3 min + deploy <2 min = total <5 min. Verify `hq.bebang.ph` is unaffected. | 1 |

**HARD BLOCKER (A1):** The consolidated deploy MUST preserve ALL post-deploy steps: nginx X-Frappe-Site-Name fix, Blip webhook proxy, migrations, asset sync to frontend container, Redis flush, API verification, asset loading verification. These are NOT optional — every one was added to fix a specific production incident.

**HARD BLOCKER (A1):** `setuptools<71` pin in migration step must be preserved.

## Phase B: EC2 Verification + Production Swap (10 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| B1 | VERIFY | Check EC2 Docker version: must be 25+ for zstd image pull. If <25, upgrade Docker on EC2 first. | 1 |
| B2 | VERIFY | Configure GHCR pull on EC2: `docker login ghcr.io` with credentials. Test pull of test image from GHCR. | 1 |
| B3 | VERIFY | Pull test image on EC2 and verify: (1) bench doctor passes, (2) all DocTypes load, (3) API responds, (4) assets.json has frappe + erpnext + hrms, (5) no missing CSS/JS. | 2 |
| B4 | EXTEND | Swap production workflow. Update `build-and-deploy.yml`: (1) replace build job with Containerfile.fast + GHCR push + zstd, (2) replace deploy job with consolidated SSM (1 round, parallel), (3) split concurrency into build group (cancel-in-progress: true) and deploy group (cancel-in-progress: false), (4) remove Checkout frappe_docker + QEMU steps, (5) add provenance: false, (6) keep ALL post-deploy steps. | 3 |
| B5 | VERIFY | Trigger a real deploy after swap. Monitor: (1) build <3 min, (2) deploy <2 min, (3) hq.bebang.ph responds, (4) assets load, (5) total <5 min. | 1 |
| B6 | BUILD | Closeout: update plan YAML status, SPRINT_REGISTRY.md, `git add -f docs/plans/`, `git add -f output/l3/S105/`, commit and push. Update `/deploy-frappe` skill. Remove temporary push triggers from test workflows. | 2 |

**HARD BLOCKER (B4):** All post-deploy steps MUST remain. Only the deploy round structure changes (3 rounds to 1 round) and the concurrency groups split.

**Rollback procedure:**
1. `git revert HEAD && git push` — reverts workflow
2. Next merge uses old workflow automatically
3. For immediate recovery: `docker service update --image samkarazi/bebang-erpnext-hrms:v15-<previous-sha>` for all 6 services

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| sam@bebang.ph | Run build-fast.yml 5x with different SHAs | All 5 under 3 min, avg ~2.3 min | Build regression |
| sam@bebang.ph | Run consolidated deploy SSM manually | All 6 services updated in <2 min, env vars set | Deploy consolidation broken |
| sam@bebang.ph | Run full pipeline test (build+deploy) | Total <5 min, hq.bebang.ph responds | Pipeline integration issue |
| sam@bebang.ph | Merge a PR after production swap | Build <3 min + deploy <2 min, total <5 min | Swap broke pipeline |
| sam@bebang.ph | Merge 3 PRs within 1 min (batch test) | Only 1 build runs (others cancelled), 1 deploy | Concurrency groups broken |
| sam@bebang.ph | Verify hq.bebang.ph after swap | API pong, assets load, no CSS 404 | Image or deploy broken |

Evidence files:
```
output/l3/S105/build_timing.json           (5 validation runs + production comparison)
output/l3/S105/deploy_timing.json          (consolidated vs current deploy times)
output/l3/S105/deployment_verification.json (EC2 health, Docker version, GHCR pull)
output/l3/S105/checkpoint.md               (phase completion checkpoints)
```

## Autonomous Execution Contract

```yaml
completion_condition:
  - Build step under 3 minutes (validated: 2.3 min avg across 5 runs)
  - Deploy step under 2 minutes (consolidated SSM + parallel services)
  - Total pipeline under 5 minutes (build + deploy)
  - Back-to-back merges produce only 1 build (concurrency groups)
  - Production deploy works after swap (hq.bebang.ph responds)
  - /deploy-frappe skill updated with GHCR + new build times
  - Plan YAML status updated to COMPLETED and pushed
  - SPRINT_REGISTRY.md updated and pushed
  - L3 evidence committed

stop_only_for:
  - EC2 Docker version <25 (cannot pull zstd images)
  - GHCR credentials issue on EC2
  - Consolidated deploy breaks a post-deploy step
  - hq.bebang.ph unresponsive after swap
  - Business decision on GHCR vs Docker Hub for production

blocker_policy:
  - programmatic -> fix and continue
  - EC2 Docker <25 -> upgrade Docker, continue
  - GHCR pull fails -> add credentials, continue
  - consolidated deploy issue -> debug SSM, continue
  - repeated failure x3 -> STOP, present options

max_turns: 30
signoff_authority: single-owner
```

## Agent Boot Sequence

1. Read this plan fully (v4 amendment has validated results).
2. **Create sprint branch:** `git fetch origin production && git checkout -b s105-docker-build-acceleration origin/production`. NEVER write code on production.
3. Read `.github/workflows/build-and-deploy.yml` — understand current deploy steps (638 lines).
4. Read `.github/docker/Containerfile.fast` on the s105 branch — the validated fast Containerfile.
5. Read `output/continuous-improvement/s105-docker-fast-build/ITERATION_LOG.md` — understand what was tried and what works.
6. Start with Phase A (deploy consolidation), then Phase B (EC2 verify + swap).

**Build is already proven.** Do NOT re-test the Containerfile. Focus on deploy consolidation and production swap.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

## Execution Workflow

- Deploy testing: run SSM commands manually first, then add to workflow
- Production swap: modify `build-and-deploy.yml` in Phase B4 only after all verification passes
- Full workflow: `/agent-kickoff`
