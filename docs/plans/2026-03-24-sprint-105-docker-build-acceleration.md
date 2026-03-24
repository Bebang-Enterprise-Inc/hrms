```yaml
canonical_sprint_id: S105
status: GO
created_date: 2026-03-24
branch: s105-docker-build-acceleration
lane: single
estimated_work_units: 16
completed_date:
execution_summary:
```

# S105: Full Pipeline Acceleration — 12 min to 3 min

## Design Rationale (For Cold-Start Agents)

### What this sprint does

Cuts the full CI/CD pipeline (build + deploy + post-deploy) from ~12 minutes to ~3 minutes. Also eliminates 10-22 min queue wait from back-to-back merges.

### What was proven (read this before writing any code)

8 iterations of real benchmarking were run on GHA. The winning configuration (iteration 8) was validated across 5 builds with unique SHAs:

| Run | Build Time | SHA |
|-----|-----------|-----|
| 1 | 50s | a0ebf91 |
| 2 | 55s | e9b495d |
| 3 | 55s | dab5d58 |
| 4 | 62s | 84a50bf |
| 5 | 47s | 08e4345 |
| **Avg** | **54s (0.9m)** | |

Deploy consolidation was tested on EC2: **41s** (vs current 357s).

Full iteration history: `output/continuous-improvement/s105-docker-fast-build/ITERATION_LOG.md`

### Why this approach won (and what failed)

| Approach | Result | Why |
|----------|--------|-----|
| Pre-built base image (original plan) | 334s — 0% improvement | Docker pull+push overhead dominated. Base image didn't help. |
| Single combined RUN layer | 371s — REGRESSION | One big layer = 232s push. Separate layers = 56s push. |
| git fetch in-place | FAILED | Upstream Containerfile strips .git dirs from apps |
| git clone without yarn | FAILED | Missing node deps (html2canvas) |
| GHCR base pull | 112s — slower than Docker Hub | GHCR image was larger (extra overlay layers). Docker Hub = 40s, GHCR = 65s. |
| **Docker Hub pull + GHCR push + preserve node_modules** | **54s — WINNER** | Best of both registries. Skip yarn by preserving existing node_modules. |

### How the winning build works

```dockerfile
FROM samkarazi/bebang-erpnext-hrms:v15    # Pull base from Docker Hub (40s)
ARG HRMS_SHA                               # Cache-bust per commit

# Clone fresh source, keep node_modules from base image
RUN git clone --depth 1 --branch production URL /tmp/hrms-fresh \
    && rm -rf apps/hrms/hrms && cp -r /tmp/hrms-fresh/hrms apps/hrms/hrms \
    && cp /tmp/hrms-fresh/setup.py /tmp/hrms-fresh/package.json apps/hrms/ \
    && rm -rf /tmp/hrms-fresh

RUN pip install -e apps/hrms              # Fast — deps already installed
RUN bench build --app hrms                # Skip PWA (neuter package.json)
# Push to GHCR with zstd (0.3s push)
```

Key design decisions:
- **Docker Hub for pull** (40s) because it has faster CDN than GHCR for this image
- **GHCR for push** (0.3s) because same datacenter as GHA runners
- **Preserve node_modules** — the base image already has them. Skip yarn install entirely.
- **No gcc/build-essential** — pip install had zero C compilations across all test runs
- **Skip PWA/roster builds** — they have missing workbox peer deps in overlay builds, and deploy via Vercel, not Docker
- **Separate RUN layers** — small layers push faster than one big layer (Docker only uploads changed layers)
- **zstd compression** — 4.2x faster layer export than gzip

### How the consolidated deploy works

Current deploy runs 3 SSM rounds (14 container restarts). Consolidated runs 1 round (6 restarts):

```bash
# Backend services: image + Sentry DSN + Supabase env in ONE update
for svc in backend queue-short queue-long scheduler; do
  docker service update --detach=true --update-failure-action=rollback \
    --image $IMAGE \
    --env-add SENTRY_DSN=$SENTRY_DSN \
    --env-add SUPABASE_URL=$SUPABASE_URL \
    --env-add SUPABASE_SERVICE_ROLE_KEY=$KEY \
    frappe_$svc
done
# Frontend/websocket: image only
for svc in frontend websocket; do
  docker service update --detach=true --image $IMAGE frappe_$svc
done
# Wait for all to converge
for svc in backend frontend websocket queue-short queue-long scheduler; do
  docker service update --detach=false frappe_$svc
done
```

Tested on EC2: all 6 services converged in 41s. API returns pong, assets load.

### How smart concurrency works

```yaml
# Build job — safe to cancel mid-build
concurrency:
  group: frappe-build
  cancel-in-progress: true

# Deploy job — NEVER cancel mid-SSM
concurrency:
  group: frappe-deploy
  cancel-in-progress: false
```

3 PRs merging in 1 minute = 1 build + 1 deploy (not 3 of each). Git HEAD always has all merged code.

### Infrastructure facts (verified 2026-03-24)

- EC2 Docker version: **28.2.2** (supports zstd, no upgrade needed)
- EC2 disk: 99 GB free of 146 GB
- EC2 instance: `i-026b7477d27bd46d6` (ap-southeast-1)
- All 6 Swarm services: 1/1 replicas healthy
- Production image: `samkarazi/bebang-erpnext-hrms:v15`
- GHCR test image: `ghcr.io/bebang-enterprise-inc/bebang-erpnext-hrms:v15-fast-test`

### Source references

- Proven Containerfile: `.github/docker/Containerfile.fast` (on this branch)
- Proven workflow: `.github/workflows/build-fast.yml` (on this branch)
- Current production workflow: `.github/workflows/build-and-deploy.yml` (638 lines)
- Iteration log: `output/continuous-improvement/s105-docker-fast-build/ITERATION_LOG.md`
- Build evidence: `output/l3/S105/build_timing.json`
- Deploy evidence: `output/l3/S105/deploy_timing.json`
- EC2 verification: `output/l3/S105/deployment_verification.json`
- Risk assessment: `output/plan-audit/s105-docker-build-acceleration/risk_assessment_v4.md`

## Requirements Regression Checklist

- [ ] Containerfile.fast uses `git clone --depth 1` with source-only copy (preserves node_modules)
- [ ] Containerfile.fast includes `HRMS_SHA` build arg for cache-busting
- [ ] Containerfile.fast skips PWA/roster builds (neuters package.json build script)
- [ ] Containerfile.fast does NOT install gcc/build-essential
- [ ] build-fast.yml pushes to GHCR with zstd + OCI mediatypes
- [ ] build-fast.yml uses `type=registry` cache with `image-manifest=true`
- [ ] build-fast.yml sets `provenance: false` and skips QEMU
- [ ] Consolidated deploy combines image + Sentry + Supabase in one `docker service update`
- [ ] Backend services (4) get env vars, frontend/websocket (2) get image only
- [ ] All services use `--detach=true` then convergence polling with `--detach=false`
- [ ] Each service update includes `--update-failure-action=rollback`
- [ ] SSM command sets explicit `executionTimeout: 600`
- [ ] Build concurrency group: `cancel-in-progress: true`
- [ ] Deploy concurrency group: `cancel-in-progress: false`
- [ ] ALL post-deploy steps preserved: nginx fix, Blip proxy, migrations (with setuptools<71 pin), asset sync, Redis flush, API verification, asset verification
- [ ] GHCR credentials configured on EC2 (long-lived PAT, direct `docker login`)
- [ ] Last Docker Hub image SHA recorded before swap (Tier 2 rollback target)

## Scope

| Item | Classification |
|------|----------------|
| Containerfile.fast (proven, on branch) | [PROVEN] |
| build-fast.yml (proven, on branch) | [PROVEN] |
| GHCR credentials on EC2 | [SETUP] |
| Consolidated deploy SSM | [PROVEN on same-image, needs new-image test] |
| Full end-to-end pipeline test | [VERIFY] |
| Production workflow swap | [EXTEND] |
| Skill updates (deploy-frappe, build, ship, write-plan, audit-plan, execute-plan) | [DOCS] |

Out of scope: Pre-built base image (abandoned), self-hosted runners, Docker Build Cloud, EC2 infrastructure changes.

## Phase A: GHCR Setup + Full Pipeline Validation (6 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| A1 | SETUP | Configure GHCR on EC2. Create long-lived GitHub PAT with `read:packages` scope. Run `docker login ghcr.io` directly on EC2 via SSM (NOT via `--with-registry-auth` — avoids Swarm credential expiry bug moby/moby #24940). Verify: `docker pull ghcr.io/bebang-enterprise-inc/bebang-erpnext-hrms:v15-fast-test` succeeds. | 1 |
| A2 | VERIFY | Test full consolidated deploy with the GHCR test image (a REAL new image, not same-image redeploy). Run the consolidated SSM command from the Design Rationale section with `DEPLOY_IMAGE=ghcr.io/.../v15-fast-test`. Verify all 6 services converge, env vars set, API pong, assets load. This tests the real deploy path. | 2 |
| A3 | VERIFY | Run ALL post-deploy steps after consolidated deploy: nginx X-Frappe-Site-Name fix, Blip webhook proxy, migrations (with setuptools<71 pin), asset sync to frontend container, Redis flush, API verification, asset loading verification. These MUST work after the 1-round deploy just as they do after the current 3-round deploy. | 2 |
| A4 | VERIFY | Record last Docker Hub image SHA before any swap: `docker images samkarazi/bebang-erpnext-hrms --format '{{.Tag}} {{.Digest}}'`. This is the Tier 2 rollback target. Write to `output/l3/S105/rollback_baseline.json`. | 1 |

**HARD BLOCKER (A2):** The test must use a genuinely different image from what is currently running. The previous 41s test used the same image (no container restart with `--preload`). A new image forces container recreation which may take longer.

**HARD BLOCKER (A3):** Every post-deploy step was added to fix a specific production incident. If ANY step fails after consolidated deploy, the consolidation approach must be revised. Do not skip steps.

## Phase B: Production Swap + Skill Updates (10 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| B1 | EXTEND | Update `build-and-deploy.yml`: (1) Replace build job — use Containerfile.fast, push to GHCR with zstd, remove Checkout frappe_docker, remove QEMU, remove Prepare apps.json, add provenance: false, replace CACHE_BUST with HRMS_SHA, change cache-to to type=registry on GHCR. (2) Replace deploy job — consolidated SSM (1 round, parallel --detach=true, convergence polling). (3) Split concurrency — build group cancel-in-progress:true, deploy group cancel-in-progress:false. (4) Keep ALL post-deploy steps identical. (5) Keep cleanup job but exclude GHCR images from prune. | 3 |
| B2 | VERIFY | First real production deploy. Merge a PR to production. Monitor: (1) build <1.5 min, (2) deploy <2 min, (3) post-deploy completes, (4) hq.bebang.ph responds, (5) assets load, (6) total pipeline <5 min. If it fails: `git revert HEAD && git push` to restore old workflow. | 2 |
| B3 | VERIFY | Second production deploy (validates consistency). Merge another PR. Confirm similar timing. If possible, merge 2 PRs within 30s to test concurrency group cancel behavior. | 1 |
| B4 | DOCS | Update skills. Each skill update is a separate commit. | 3 |
| B5 | BUILD | Closeout: plan YAML status to COMPLETED, SPRINT_REGISTRY.md, deploy-frappe skill, `git add -f docs/plans/ output/l3/S105/`, commit, push. Remove temporary push triggers from build-fast.yml and build-base.yml. Delete build-fast-4core.yml (test artifact). | 1 |

**HARD BLOCKER (B1):** The deploy job post-deploy steps (nginx, Blip, migrations, asset sync, Redis, verification) MUST have zero changes. Only the service update round structure changes.

### B4 Skill Updates Detail

| Skill | What Changes |
|-------|-------------|
| `/deploy-frappe` | New build times (54s avg). GHCR as push registry. Consolidated deploy SSM. New Containerfile location. Updated quick reference table. New concurrency groups. |
| `/build` (`/agent-kickoff`) | Updated build time expectations in any timing references. |
| `/ship-bei-erp` | Updated deploy flow (1 round not 3). GHCR image reference. |
| `/write-plan-bei-erp` | Updated build time estimates for plan budgeting (54s not 5m). |
| `/audit-plan-bei-erp` | Updated deployment-qa checklist (GHCR, zstd, consolidated deploy). |
| `/execute-plan-bei-erp` | Updated deploy timing expectations. GHCR image references. |

**Rollback procedure (3 tiers):**

| Tier | Scenario | Action |
|------|----------|--------|
| 1 | Bad code in latest deploy | `docker service update --image ghcr.io/.../v15-fast-test-<previous-sha>` for all 6 services |
| 2 | GHCR outage or zstd issue | `docker service update --image samkarazi/bebang-erpnext-hrms:v15` (Docker Hub, last known SHA from A4) |
| 3 | Full pipeline rollback | `git revert HEAD && git push` — next merge uses old workflow |

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| sam@bebang.ph | Pull GHCR test image on EC2 | Image pulls successfully (zstd decompression works) | GHCR auth or Docker version issue |
| sam@bebang.ph | Deploy GHCR test image with consolidated SSM | All 6 services updated <2 min, API responds | Consolidation broken with real new image |
| sam@bebang.ph | Run all post-deploy steps after consolidated deploy | nginx, Blip, migrations, assets, Redis all pass | Post-deploy incompatible with 1-round deploy |
| sam@bebang.ph | Merge PR after production swap | Build <1.5 min + deploy <2 min, hq.bebang.ph works | Swap broke pipeline |
| sam@bebang.ph | Merge 2 PRs within 30s | Only 1 build runs, 1 deploy, both PRs deployed | Concurrency groups broken |
| sam@bebang.ph | Verify hq.bebang.ph after swap | API pong, assets load, no CSS 404 | Image or deploy broken |

Evidence files:
```
output/l3/S105/build_timing.json           (5 validation runs)
output/l3/S105/deploy_timing.json          (consolidated deploy test)
output/l3/S105/deployment_verification.json (EC2 health checks)
output/l3/S105/rollback_baseline.json      (last Docker Hub SHA)
output/l3/S105/checkpoint.md               (phase completion)
```

## Autonomous Execution Contract

```yaml
completion_condition:
  - GHCR configured on EC2 and pull verified
  - Full consolidated deploy tested with real new image on EC2
  - All post-deploy steps pass after consolidated deploy
  - Production workflow swapped and first real deploy succeeds
  - Total pipeline under 5 minutes (measured from GHA logs)
  - All 6 skills updated (deploy-frappe, build, ship, write-plan, audit-plan, execute-plan)
  - Plan YAML status COMPLETED, SPRINT_REGISTRY.md updated, pushed
  - L3 evidence committed

stop_only_for:
  - GHCR credentials issue (need GitHub PAT creation)
  - Consolidated deploy breaks a post-deploy step
  - hq.bebang.ph unresponsive after swap
  - Business decision on GHCR vs Docker Hub

blocker_policy:
  - programmatic -> fix and continue
  - GHCR pull fails -> fix credentials, continue
  - consolidated deploy issue -> debug SSM, continue
  - post-deploy step fails -> fix and retest, continue
  - repeated failure x3 -> STOP, present options

max_turns: 30
signoff_authority: single-owner
```

## Agent Boot Sequence

1. Read this plan fully. The Design Rationale section has everything you need.
2. **Create sprint branch:** `git checkout s105-docker-build-acceleration` (already exists with proven artifacts).
3. Read the proven Containerfile: `.github/docker/Containerfile.fast` on this branch.
4. Read the proven workflow: `.github/workflows/build-fast.yml` on this branch.
5. Read the iteration log: `output/continuous-improvement/s105-docker-fast-build/ITERATION_LOG.md`.
6. Read the current production workflow: `.github/workflows/build-and-deploy.yml` (638 lines).
7. **DO NOT re-test the build.** It is proven at 54s avg across 5 runs. Focus on Phase A (GHCR setup + deploy validation).

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.
