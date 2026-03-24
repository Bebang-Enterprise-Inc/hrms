```yaml
canonical_sprint_id: S105
status: "AUDIT: 4 BLOCKERS CLOSED, GO"
created_date: 2026-03-24
branch: s105-docker-build-acceleration
lane: single
estimated_work_units: 22
completed_date:
execution_summary:
audit_version: 3
audit_date: 2026-03-24
audit_agents: docker-researcher, deployment-qa, system-arch, team-orchestration, code-verifier
audit_verdict: GO (all blockers closed by amendment)
```

# S105: Docker Build Acceleration — 6 min Build to Under 3 min

## Audit Amendment v3 (2026-03-24) — Multi-Domain Audit

Full parallel audit by 5 agents: Docker best practices researcher (web search), deployment-qa, system architecture (4/5 score), team orchestration (80% compliance), and code verifier (8/10 confirmed, 2 stale, 5 new gaps). All CRITICAL blockers closed by amendment below.

### Blockers Found and Closed

| # | Severity | Finding | Source | Resolution |
|---|----------|---------|--------|------------|
| B-01 | **CRITICAL** | `bench get-app --depth 1` flag does not exist | code-verifier | **CLOSED:** Replaced with `bench config set-common-config -c shallow_clone 1` before `bench get-app`. See A3. |
| B-02 | **CRITICAL** | Upstream Containerfile defaults diverged (Python 3.14, Node 24, version-16) | code-verifier | **CLOSED:** Containerfile.base MUST hardcode `ARG PYTHON_VERSION=3.11.6`, `ARG NODE_VERSION=20.19.2`, `ARG FRAPPE_BRANCH=version-15`. See A1. |
| B-03 | **CRITICAL** | Mutable base image tag — no rollback/traceability | system-arch C1 | **CLOSED:** Base images tagged immutably as `frappe-base:v15-YYYYMMDD`. Floating `v15` alias kept. Containerfile.fast references dated tag. See A1, A2. |
| B-04 | **CRITICAL** | No max_turns specified | team-orchestration C1 | **CLOSED:** Added `max_turns: 30` to execution contract. |

### Warnings Addressed

| # | Finding | Source | Resolution |
|---|---------|--------|------------|
| W-01 | Cleanup job may prune base image | system-arch W5 | Added to B4: exclude `frappe-base` from prune commands |
| W-02 | Cache type mismatch test vs prod | system-arch W3 | Aligned: both use `type=gha,mode=max` |
| W-03 | L3 evidence files wrong for infra sprint | team-orchestration W3 | Replaced with `build_timing.json`, `image_manifest.json`, `deployment_verification.json` |
| W-04 | No automated staleness detection | system-arch W1, deploy-qa D-04 | Added to A2: weekly cron check of upstream HEAD SHAs |
| W-05 | `bench build --app hrms` unvalidated | system-arch W4 | Added validation step in B2: compare assets.json completeness |
| W-06 | No rollback procedure | deploy-qa D-07 | Documented in Phase B section |

### Improvements from Docker Research

| # | Improvement | Impact |
|---|------------|--------|
| I-01 | Remove QEMU setup step (single-platform only) | Saves 15-30s per build |
| I-02 | Add `provenance: false` to build-push-action | Saves 10-20s per build |
| I-03 | Use BuildKit cache mounts for pip/yarn (`--mount=type=cache`) | Avoids re-downloads even on layer invalidation |
| I-04 | Use `type=gha,mode=max` (not `type=inline`) | Caches ALL intermediate layers, not just final |

Full audit findings: `output/plan-audit/s105-docker-build-acceleration/`

---

## Audit Amendment v2 (2026-03-24) — Build Time Verification

This plan was audited against the actual GHA build logs and the `/deploy-frappe` operational skill. Key corrections applied:

| Original Claim | Actual (from GHA logs, last 4 runs) |
|----------------|-------------------------------------|
| Build step: 15-20 min | **5m31s – 5m52s** (consistently ~6 min) |
| Deploy step: included above | **5m34s – 5m57s** (consistently ~6 min) |
| Total wall clock: 15-20 min | **12-25 min** (variance is concurrency queue wait, not build time) |
| Target: under 5 min total | **Target: build step under 3 min** (deploy step unchanged) |

**Phase A (GHA Cache Fix) was DELETED.** It would have reintroduced a known production incident (stale code deployment, discovered 2026-01-29, documented in `/deploy-frappe` skill). `CACHE_BUST` and `no-cache: true` exist for a reason — Docker cannot detect git repo content changes inside a cached `bench init` layer.

**HRMS cache-busting added to Containerfile.fast.** Without `HRMS_SHA=${{ github.sha }}`, the `bench get-app hrms` layer would be cached across builds and serve stale code — the exact same problem `CACHE_BUST` was created to solve.

**Build tools gap addressed.** The upstream `backend` stage inherits from `base` (which has git, node, yarn) but lacks gcc/build-essential needed for pip install of C-extension deps. Containerfile.fast must install build deps or use a multi-stage pattern.

---

## Summary

Cut the Docker **build step** from ~6 minutes to under 3 minutes by pre-baking a base image (frappe + erpnext + payments) and only rebuilding the BEI hrms layer on each merge. Zero risk to production — the new pipeline runs in parallel as a test lane until proven, then swaps in.

**Net effect:** Total pipeline (build + deploy) drops from ~12 min to ~9 min per merge.

## Design Rationale (For Cold-Start Agents)

### Why this exists

Every PR merge to production triggers a full Docker image build where `bench init` clones and installs frappe, erpnext, payments, and hrms from scratch. The build step takes ~6 min consistently:

- **`bench init`** clones all 4 apps + pip install + bench build in the `builder` stage
- **Docker push** to Docker Hub

frappe, erpnext, and payments haven't changed in months (all pinned to `version-15`). They rebuild from scratch every time because the upstream Containerfile puts everything in one monolithic `bench init` layer, and `no-cache: true` + `CACHE_BUST` (correctly) prevent stale code.

### Why not just fix caching? (original Phase A was deleted)

`CACHE_BUST=${{ github.sha }}` and `no-cache: true` on push events were added after a **production incident on 2026-01-29** where cached builds deployed stale code. Docker layer caching cannot detect when a git repo's branch HEAD has new commits — it sees the same `RUN bench init` instruction and serves the cached layer. Removing these protections would reintroduce stale code deployments.

The pre-built base image approach is better because it **structurally separates** the static apps (frappe/erpnext/payments) from the changing app (hrms). Each gets its own cache lifecycle:
- Base image: rebuilt manually when upstream releases security patches (tagged immutably per rebuild)
- hrms layer: rebuilt on every merge with SHA-based cache busting

### Upstream Containerfile stages (verified 2026-03-24)

```
base     → python:3.11-slim + git, node, yarn, nginx, wkhtmltopdf, frappe-bench CLI
builder  → FROM base + gcc, build-essential, libmariadb-dev → bench init (all apps)
backend  → FROM base + COPY frappe-bench from builder → production CMD (gunicorn --preload)
```

**Key fact:** The `base` stage HAS git, node, and yarn. The `backend` stage inherits from `base`. So `bench get-app` and `bench build --app hrms` CAN run in a container based on the backend image — but `pip install` of C-extension deps requires gcc (only in `builder` stage).

**CAUTION (audit v3 finding):** Upstream defaults have DIVERGED: Python 3.14.2, Node 24.13.0, FRAPPE_BRANCH=version-16. BEI MUST pin `PYTHON_VERSION=3.11.6`, `NODE_VERSION=20.19.2`, `FRAPPE_BRANCH=version-15` in Containerfile.base.

### Key trade-offs

- **Base image staleness**: If Frappe releases a critical security patch, we need to rebuild the base. Mitigated by: (1) manual `workflow_dispatch` trigger, (2) weekly cron job that checks upstream HEAD SHAs and alerts if changed.
- **Two workflows to maintain**: `build-and-deploy.yml` (production, untouched) and `build-fast.yml` (test lane). Once proven, `build-fast.yml` replaces the old one.
- **Docker Hub storage**: Two image families (`frappe-base` and `bebang-erpnext-hrms`). Minimal cost impact.
- **EC2 disk**: Base image adds ~2 GB permanent resident. Cleanup job updated to never prune `frappe-base` images.

### Source references

- Current workflow: `.github/workflows/build-and-deploy.yml` (638 lines)
- Apps config: `.github/helper/apps.json` (3 apps: erpnext, payments, hrms)
- Upstream Containerfile: `frappe/frappe_docker/images/custom/Containerfile` (3 stages: base, builder, backend)
- EC2 instance: `i-026b7477d27bd46d6` (ap-southeast-1)
- Docker image: `samkarazi/bebang-erpnext-hrms:v15`
- Deploy skill: `.claude/skills/deploy-frappe/SKILL.md` (stale cache incident documented)
- Audit findings: `output/plan-audit/s105-docker-build-acceleration/` (5 agent reports)

### Verified build times (2026-03-24, last 4 runs)

| Run ID | Event | Build Step | Deploy Step | Wall Clock |
|--------|-------|-----------|-------------|------------|
| 23476267170 | push | 5m46s | 5m37s | 12m24s |
| 23475670689 | push | 5m31s | 5m57s | 20m10s* |
| 23475198819 | push | 5m52s | 5m34s | 25m02s* |
| 23468362683 | dispatch | 5m43s | 5m35s | 24m11s* |

*Wall clock inflated by concurrency queue wait (multiple PRs merging back-to-back).

## Requirements Regression Checklist

- [ ] Does the production workflow (`build-and-deploy.yml`) remain COMPLETELY UNTOUCHED until Phase B?
- [ ] Does the test workflow (`build-fast.yml`) only trigger on `workflow_dispatch` (never on push)?
- [ ] Does the test workflow push to a test tag (`v15-fast-test`), NOT to the production tag (`v15`)?
- [ ] Does the base image include frappe version-15, erpnext version-15, and payments version-15?
- [ ] Does the base Containerfile hardcode `PYTHON_VERSION=3.11.6`, `NODE_VERSION=20.19.2`, `FRAPPE_BRANCH=version-15`?
- [ ] Does the fast Containerfile use `bench build --app hrms` (not `bench build` for all apps)?
- [ ] Does the fast Containerfile include `HRMS_SHA` build arg for cache-busting the hrms layer?
- [ ] Does the fast Containerfile install gcc/build-essential for pip install, OR use multi-stage build?
- [ ] Does the fast Containerfile use `bench config set-common-config -c shallow_clone 1` (NOT `--depth 1` flag)?
- [ ] Does the base image rebuild workflow exist as a manual trigger?
- [ ] Is the base image tagged immutably (e.g., `v15-20260324`), not just overwriting `v15`?
- [ ] Is the test image verified on EC2 before swapping the production pipeline?
- [ ] Does Phase B preserve all deploy steps (SSM, Sentry DSN, Supabase env, nginx fix, Blip proxy, migrations, Redis flush, asset sync, verification, cleanup)?
- [ ] Does Phase B verify `bench build --app hrms` produces a complete `assets.json`?
- [ ] Does Phase B cleanup job exclude `frappe-base` from pruning?
- [ ] Are all 6 Swarm services (backend, frontend, websocket, queue-short, queue-long, scheduler) still using the same image?

## Scope

### In Scope

| Item | Classification |
|------|----------------|
| Pre-built base image (`samkarazi/frappe-base:v15-YYYYMMDD`) | [BUILD] |
| Fast Containerfile that extends base with hrms-only rebuild | [BUILD] |
| Test workflow (`build-fast.yml`, manual-only) | [BUILD] |
| Base image rebuild workflow (`build-base.yml`, manual + staleness cron) | [BUILD] |
| EC2 verification of test image | [VERIFY] |
| Production swap (replace old workflow with fast one) | [EXTEND] |
| Build-push-action optimizations (remove QEMU, provenance: false) | [FIX] |

### Out of Scope

- ~~GHA cache fix on existing workflow (original Phase A — DELETED, would reintroduce stale code)~~
- Changing the deploy steps (SSM commands, Sentry, Supabase, nginx — all stay identical)
- Self-hosted runners
- Docker Build Cloud
- Changing the EC2 infrastructure

## Phase A: Pre-Built Base Image + Fast Containerfile (12 units)

Build the base image and fast Containerfile in parallel — production pipeline is untouched.

| Task | Type | Description | Units |
|------|------|-------------|-------|
| A1 | BUILD | Create `.github/docker/Containerfile.base` — builds `samkarazi/frappe-base:v15-YYYYMMDD` with frappe + erpnext + payments baked in. Based on upstream `frappe_docker/images/custom/Containerfile` with apps hardcoded. **MUST hardcode:** `ARG PYTHON_VERSION=3.11.6`, `ARG NODE_VERSION=20.19.2`, `ARG FRAPPE_BRANCH=version-15` (upstream defaults have DIVERGED to 3.14/24/v16). Must include `bench build` for all three apps, wkhtmltopdf, nginx. The final image is the `backend` stage (production-ready). | 4 |
| A2 | BUILD | Create `.github/workflows/build-base.yml` — manual `workflow_dispatch` trigger that builds and pushes `samkarazi/frappe-base:v15-YYYYMMDD` (immutable dated tag) AND updates floating alias `frappe-base:v15`. Includes Docker Hub login, buildx setup, single-platform (linux/amd64), `provenance: false`. **Remove QEMU step** (not needed for single-platform). Add weekly cron job that checks HEAD SHAs of `frappe/frappe:version-15`, `frappe/erpnext:version-15`, `frappe/payments:version-15` and opens an issue if any changed since last base build. Expected build time: ~6 min (same as current, one-time). | 2 |
| A3 | BUILD | Create `.github/docker/Containerfile.fast` — extends `samkarazi/frappe-base:v15` (floating alias), adds ONLY hrms. Must accept `HRMS_SHA` build arg for cache-busting (see HARD BLOCKERS below). Steps: (1) install gcc/build-essential/libmariadb-dev for pip, (2) `bench config set-common-config -c shallow_clone 1` then `bench get-app https://github.com/Bebang-Enterprise-Inc/hrms.git --branch production` (**NOT** `--depth 1` — that flag does not exist on `bench get-app`), (3) `bench build --app hrms` (assets for hrms only), (4) clean up build deps. Use BuildKit cache mounts: `RUN --mount=type=cache,target=/root/.cache/pip` for pip install. **HARD BLOCKER:** Must use `bench build --app hrms`, not `bench build`. | 4 |
| A4 | BUILD | Create `.github/workflows/build-fast.yml` — test workflow, `workflow_dispatch` ONLY (no push trigger). Builds using `Containerfile.fast`, pushes to `samkarazi/bebang-erpnext-hrms:v15-fast-test` (NOT the production tag). Must pass `HRMS_SHA=${{ github.sha }}` as build arg. Cache: `type=gha,mode=max`. `provenance: false`. **Remove QEMU step.** No deploy steps — build only. | 2 |

**Checkpoint:** After A1+A2 (6 units), write status to `output/l3/S105/checkpoint.md`.

**HARD BLOCKER (cache-busting):** `Containerfile.fast` MUST include:
```dockerfile
ARG HRMS_SHA
RUN bench config set-common-config -c shallow_clone 1 \
    && bench get-app https://github.com/Bebang-Enterprise-Inc/hrms.git --branch production \
    && echo "hrms_sha=${HRMS_SHA}"
```
Without `HRMS_SHA`, Docker will cache the `bench get-app` layer and serve stale hrms code on every build. This is the EXACT same problem that `CACHE_BUST=${{ github.sha }}` solves in the current workflow — but now it only invalidates the hrms layer (~2 min) instead of all layers (~6 min).

**HARD BLOCKER (bench get-app --depth):** The `bench get-app` CLI does **NOT** have a `--depth` flag. Bench uses `shallow_clone` as a site config setting internally. Use `bench config set-common-config -c shallow_clone 1` before calling `bench get-app`. Do NOT pass `--depth 1` to bench.

**HARD BLOCKER (version pinning):** Upstream Containerfile now defaults to Python 3.14.2, Node 24.13.0, FRAPPE_BRANCH=version-16. Containerfile.base MUST hardcode BEI's versions: `PYTHON_VERSION=3.11.6`, `NODE_VERSION=20.19.2`, `FRAPPE_BRANCH=version-15`. Failure to pin = incompatible base image.

**HARD BLOCKER (build tools):** The `backend` stage inherits from `base` which has git/node/yarn but NOT gcc/build-essential. If any hrms pip dependency requires C compilation, `pip install` will fail. The fast Containerfile must install build deps, run pip install, then remove build deps (adds ~30s).

**HARD BLOCKER (base image):** The base Containerfile must produce a `backend` stage image that includes `/home/frappe/frappe-bench` with all three apps installed, pip deps resolved, and assets built. The fast Containerfile's `bench get-app hrms` must work without re-running `bench init`.

## Phase B: Test + Swap (10 units)

Verify the fast-built image works, then swap the production pipeline.

| Task | Type | Description | Units |
|------|------|-------------|-------|
| B1 | VERIFY | Run `build-base.yml` via `workflow_dispatch`. Verify: base image pushes to Docker Hub with immutable dated tag, size is reasonable (~1.5-2 GB), has frappe/erpnext/payments installed. Check `bench version --format json` shows correct versions. | 2 |
| B2 | VERIFY | Run `build-fast.yml` via `workflow_dispatch`. Verify: (1) build step completes in under 3 minutes, (2) image pushes to `v15-fast-test` tag, (3) GHA cache works on second run. **Validate `bench build --app hrms`:** compare `assets.json` in the fast image against production image — must contain entries for frappe, erpnext, AND hrms. No "missing module" errors in build log. | 2 |
| B3 | VERIFY | Pull `v15-fast-test` on EC2 and run alongside production. Pre-check: verify >6 GB free disk before pull. Verify: (1) `bench --site hrms.bebang.ph doctor` passes, (2) all BEI DocTypes load, (3) API endpoints respond, (4) assets match (no missing CSS/JS). Clean up: `docker rmi` the test tag after verification. | 2 |
| B4 | EXTEND | Once verified: update `build-and-deploy.yml` to use `Containerfile.fast` instead of upstream Containerfile. Changes: (1) `context` from `frappe_docker` to `.github/docker`, (2) `file` to `.github/docker/Containerfile.fast`, (3) replace `CACHE_BUST=${{ github.sha }}` with `HRMS_SHA=${{ github.sha }}`, (4) remove `APPS_JSON_BASE64` build-arg, (5) remove `Checkout frappe_docker` step, (6) remove `Prepare apps.json` step, (7) remove `Set up QEMU` step, (8) add `provenance: false`, (9) change `no-cache` to `false`, (10) change `cache-to` to `type=gha,mode=max`. Update cleanup job: add `frappe-base` to prune exclusion list. **Verify all 6 Swarm services still use the same image tag.** Keep ALL deploy steps (Sentry DSN, Supabase env, nginx, Blip, migrations, asset sync, Redis flush, verification) IDENTICAL — diff the deploy job to confirm zero changes. `setuptools<71` pin in migration step must be preserved. | 2 |
| B5 | BUILD | Closeout: update plan YAML status, SPRINT_REGISTRY.md, `git add -f docs/plans/`, `git add -f output/l3/S105/`, commit and push. Update `/deploy-frappe` skill to document new build architecture and updated build times. | 2 |

**Checkpoint:** After B2 (16 total units), write Phase A results (build time, image size, layer count, assets.json validation) to `output/l3/S105/checkpoint.md`. Verify build time <3 min before proceeding to B3.

**HARD BLOCKER (B4):** When swapping, the deploy job and ALL post-deploy steps must remain IDENTICAL. Only the build job changes. Run `git diff` on the deploy job section — must have zero changes.

**NOTE (B4):** After swap, `no-cache: false` is safe because:
- Base layers (FROM frappe-base:v15) are static — no stale code risk
- hrms layer is invalidated by `HRMS_SHA=${{ github.sha }}` — guaranteed fresh code
- This is structurally different from the current monolithic `bench init` where caching = stale code

**Rollback procedure (if fast build fails post-swap):**
1. Revert the `build-and-deploy.yml` change: `git revert HEAD && git push`
2. The next merge to production will use the old workflow (full build from upstream Containerfile)
3. For immediate recovery: `docker service update --image samkarazi/bebang-erpnext-hrms:v15-<previous-sha> frappe_backend` (and all 6 services)
4. Previous images are retained (4 most recent builds)

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| sam@bebang.ph | Run `build-base.yml` via workflow_dispatch | Base image builds and pushes with dated tag (~6 min) | Base Containerfile broken |
| sam@bebang.ph | Run `build-fast.yml` via workflow_dispatch | Fast image builds in <3 min, pushes to `v15-fast-test` | Fast Containerfile broken |
| sam@bebang.ph | Run `build-fast.yml` a second time | Build completes in ~2 min (GHA cache hit on base pull layer) | Cache not configured |
| sam@bebang.ph | Pull `v15-fast-test` on EC2, run health check | Container starts, bench commands work, API responds, assets complete | Missing deps or broken bench |
| sam@bebang.ph | Merge a PR to production after swap | Build step <3 min, deploy succeeds, hq.bebang.ph responds | Swap broke pipeline |
| sam@bebang.ph | Verify build time in GHA logs | Build step <3 min (down from ~6 min) | Not effective |
| sam@bebang.ph | Base staleness cron fires (weekly) | Issue opened if upstream HEAD changed | Cron broken |

Evidence files required:
```
output/l3/S105/build_timing.json       (before/after build times from GHA logs)
output/l3/S105/image_manifest.json     (layer sizes, total size, Python/Node versions)
output/l3/S105/deployment_verification.json  (EC2 health checks, bench doctor, API pong)
output/l3/S105/checkpoint.md           (phase completion checkpoints)
```

## Autonomous Execution Contract

```yaml
completion_condition:
  - Phase A: Base image built and pushed with immutable tag, fast Containerfile tested
  - Phase B: Fast build verified on EC2, production pipeline swapped
  - Build step under 3 minutes for hrms-only changes (measured from GHA logs)
  - Production deploy still works after swap (hq.bebang.ph responds)
  - assets.json verified complete (frappe + erpnext + hrms entries)
  - /deploy-frappe skill updated with new architecture and build times
  - Plan YAML status updated to COMPLETED and pushed (git add -f docs/plans/)
  - SPRINT_REGISTRY.md row updated to COMPLETED and pushed
  - L3 evidence committed: git add -f output/l3/S105/

stop_only_for:
  - Docker Hub credentials missing or expired
  - Base image build fails due to upstream frappe_docker changes
  - EC2 verification shows missing functionality in fast-built image
  - pip install fails in backend stage due to missing C build tools (test before committing)
  - bench build --app hrms produces incomplete assets.json
  - Business decision: whether to accept slightly stale frappe/erpnext (base rebuilt manually)

continue_without_pause_through:
  - Phase A (base + fast build)
  - Phase B (test + swap)
  - closeout

blocker_policy:
  - programmatic -> fix and continue
  - upstream Containerfile changed -> adapt Containerfile.base, continue
  - pip install needs build tools -> add gcc/build-essential to Containerfile.fast, continue
  - bench get-app shallow clone fails -> fall back to full clone, continue
  - repeated failure x3 -> STOP, present options

max_turns: 30
signoff_authority: single-owner
```

## Agent Boot Sequence

1. Read this plan fully (including both Audit Amendment sections).
2. **Create sprint branch:** `git fetch origin production && git checkout -b s105-docker-build-acceleration origin/production`. NEVER write code on production.
3. Read `.github/workflows/build-and-deploy.yml` — understand current build pipeline (638 lines).
4. Read `.github/helper/apps.json` — the 3 apps being built.
5. Fetch the upstream Containerfile: `curl -s https://raw.githubusercontent.com/frappe/frappe_docker/main/images/custom/Containerfile` — understand the 3 stages (base -> builder -> backend). **CRITICAL:** Note upstream defaults have DIVERGED (Python 3.14, Node 24, version-16). BEI MUST pin 3.11.6/20.19.2/version-15.
6. **DO NOT** use `bench get-app --depth 1` — that flag does not exist. Use `bench config set-common-config -c shallow_clone 1` instead.
7. Start with Phase A (base image + fast Containerfile), checkpoint at 6 units, then proceed to Phase B (test + swap).

**DO NOT** attempt to remove `CACHE_BUST` or `no-cache` from the existing workflow. These exist to prevent a known stale-code incident (2026-01-29). The pre-built base approach makes them unnecessary only AFTER the swap in Phase B4.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

## Execution Workflow

- Test workflow changes: trigger `workflow_dispatch` on the test workflow
- Deploy changes: modify `build-and-deploy.yml` only in Phase B after verification
- Full workflow: `/agent-kickoff`
