# S105 Risk Assessment v4

**Sprint:** S105 — Full Pipeline Acceleration (Docker Build + Deploy)
**Assessed:** 2026-03-24
**Assessor:** DevOps Risk Audit (Claude Opus 4.6)
**Plan Version:** v4 (Validated Build + Deploy Optimization)

---

## Risk Matrix

| # | Risk | Severity | Likelihood | Impact | Mitigation Status |
|---|------|----------|------------|--------|-------------------|
| R1 | GHCR outage blocks deploys | Medium | Low | High | INADEQUATE |
| R2 | EC2 Docker <25 cannot pull zstd images | High | Medium | Critical | PLANNED (B1) |
| R3 | Consolidated SSM command timeout | Medium | Medium | Medium | ADEQUATE |
| R4 | Cancelled build leaves partial GHCR image | Low | Low | Low | ADEQUATE |
| R5 | PWA/roster assets missing from Docker image | Low | Low | Low | ADEQUATE |
| R6 | Rollback complexity with GHCR + zstd stack | Medium | Low | High | PARTIAL |
| R7 | git clone --depth 1 misses bench get-app hooks | High | Medium | High | INADEQUATE |

---

## Detailed Analysis

### R1: Image Registry Migration Risk (GHCR Outage)

**Scenario:** GHCR experiences an outage. EC2 cannot pull images. Deploys fail.

**Current state:** Production uses Docker Hub (`samkarazi/bebang-erpnext-hrms:v15`). The plan migrates entirely to GHCR. There is no dual-push strategy and no fallback registry.

**EC2 credential impact:** EC2 currently authenticates to Docker Hub. After swap, it needs `docker login ghcr.io` with a GitHub PAT (or GITHUB_TOKEN). Plan task B2 covers this, but if the PAT expires or is revoked, EC2 silently loses pull access.

**GHCR reliability:** GitHub's status page shows GHCR has had multiple incidents in the past year (2025), though most lasted under 1 hour. For a single-tenant ERP system that deploys a few times per week, this is acceptable risk -- but the plan has no documented fallback.

**Assessment:** The plan should document a manual fallback: "If GHCR is down, push to Docker Hub as backup and deploy from there." The existing Docker Hub credentials remain on EC2 (they are not removed), so the fallback path exists mechanically but is not documented.

**Verdict: INADEQUATE** -- needs a documented fallback procedure (1 paragraph, not a full feature).

---

### R2: Zstd Compatibility Risk (EC2 Docker Version)

**Scenario:** EC2 runs Docker <25. Zstd-compressed images cannot be pulled. Deploy fails silently or with a cryptic error.

**Current state:** Unknown. The plan correctly identifies this as a hard blocker and includes task B1 to verify/upgrade. However, upgrading Docker on a running Swarm node is non-trivial:
- Docker daemon restart kills all containers temporarily
- Swarm services should auto-restart, but a misconfigured upgrade could break the Swarm cluster
- The EC2 instance runs a single-node Swarm -- there is no secondary node for failover during upgrade

**If upgrade fails:** The entire production stack (hq.bebang.ph) goes down. The plan's blocker_policy says "EC2 Docker <25 -> upgrade Docker, continue" -- this underestimates the blast radius of a failed Docker upgrade on a production single-node Swarm.

**Recommended mitigation:**
1. Check Docker version FIRST (before any other S105 work)
2. If upgrade needed, schedule a maintenance window (off-peak hours PHT)
3. Take an EC2 AMI snapshot before upgrading Docker
4. Test Swarm recovery after upgrade before proceeding

**Verdict: PLANNED but severity is underestimated.** The plan treats Docker upgrade as routine. On a single-node production Swarm, it requires a maintenance window and AMI backup.

---

### R3: Deploy Consolidation Risk (SSM Timeout / Resource Contention)

**Scenario:** The consolidated SSM command (1 long round instead of 3 short rounds) exceeds SSM timeout, or parallel `docker service update --detach=true` commands cause resource contention on the single-node Swarm.

**Current state:** The existing workflow uses 3 SSM rounds with timeouts of 80s, 60s, 60s respectively (total budget: 200s). The consolidated approach puts everything into 1 round. The current `ssm_wait_and_assert.sh` is called with `15 80` for the deploy step (15s poll interval, 80 iterations = 20 min max).

**Resource contention analysis:** Current deploys update 6 services sequentially (`--detach=false`). The plan proposes `--detach=true` for all 6 then poll for convergence. On a single-node Swarm, all 6 services pull from the same already-cached image, so the actual resource pressure is:
- 6 containers starting simultaneously (moderate CPU/memory spike)
- All 6 doing health checks concurrently
- This is manageable -- Docker Swarm handles this natively with `update_parallelism`

**Env var consolidation:** Currently, Sentry DSN and Supabase env require separate `docker service update` calls that each restart containers. Combining image + env in one update means each service restarts only ONCE instead of 3 times. This is strictly better.

**SSM timeout:** The consolidated command is actually shorter than the current 3-round approach because it eliminates 2 rounds of container restarts. SSM default timeout is 3600s; the plan's poll budget of 20 min is generous.

**Verdict: ADEQUATE.** The consolidated deploy is strictly better than the current 3-round approach. Less total restart churn, less total time.

---

### R4: Concurrency Group Split Risk (Cancelled Build + Partial Image)

**Scenario:** `cancel-in-progress: true` for the build group cancels a build mid-push. GHCR receives a partial/corrupt image. The deploy job then pulls this broken image.

**Analysis:** This cannot happen due to workflow mechanics:
1. `cancel-in-progress: true` cancels the ENTIRE workflow run, not just the build step
2. When a build is cancelled, the deploy job never starts (it depends on `needs: build` with `result == 'success'`)
3. GHCR uses content-addressable storage -- a partial push does not create a valid manifest. The image simply does not exist until the push completes.
4. Even if a partial push somehow succeeded, the deploy step uses the digest (`@sha256:...`) from `build_push.outputs.digest`, which is only set on successful completion

**Edge case:** If the runner is terminated mid-push, GHCR may have orphaned layers but no manifest. These are garbage-collected by GHCR automatically. No broken image is pullable.

**Verdict: ADEQUATE.** The combination of GitHub Actions job dependencies, content-addressable storage, and digest-based deploys makes this risk negligible.

---

### R5: PWA Build Skip Risk (Missing Frontend Assets)

**Scenario:** Production pages depend on PWA/roster frontend assets that are built during `bench build --app hrms`. Skipping them causes 404s or broken UI.

**Analysis from the plan and Containerfile:**
- The Containerfile.fast replaces the `build` script in `package.json` with `echo skip-pwa-roster` before running `bench build --app hrms`
- `bench build --app hrms` builds Frappe desk assets (JS/CSS bundles for the admin UI). The PWA build is a separate step triggered by the `build` script in `package.json`
- The plan states "PWA deploys via Vercel, not Docker" -- the PWA is the my.bebang.ph app in the bei-tasks repo
- The "roster" frontend is the legacy Vue/Ionic app in `frontend/` -- this is also not served from the Docker image

**What bench build DOES produce:** `assets.json` entries for `frappe`, `erpnext`, and `hrms` -- the desk bundle CSS/JS. These are the assets verified by the "Verify login page assets loading" step.

**What bench build does NOT need:** The PWA workbox build, which requires peer dependencies (`workbox-*`) that are missing in the overlay build. Skipping it is correct.

**Verdict: ADEQUATE.** The PWA and roster frontends are deployed independently. Only desk assets are needed in the Docker image, and those are produced by `bench build --app hrms` regardless of the package.json `build` script.

---

### R6: Rollback Complexity

**Scenario:** After the swap (Phase B4), a deploy breaks production. The team needs to rollback.

**Plan's rollback procedure:**
1. `git revert HEAD && git push` -- reverts workflow, next merge uses old workflow
2. For immediate recovery: `docker service update --image samkarazi/bebang-erpnext-hrms:v15-<previous-sha>` for all 6 services

**Issues identified:**

1. **Registry mismatch after swap:** After B4, builds push to GHCR. If rollback requires pulling the LAST GOOD image, that image is on GHCR. But the rollback procedure references `samkarazi/` (Docker Hub). The last Docker Hub image will be stale (from before the swap). This is fine for emergency "go back to pre-swap state" but not for "go back to the previous GHCR build."

2. **Zstd rollback:** If EC2 was upgraded to Docker 25+ and the zstd image is corrupt, the rollback image (also on GHCR with zstd) may also be corrupt. The fallback is Docker Hub with gzip, which requires knowing the last Docker Hub SHA.

3. **Missing rollback runbook:** The plan has a 3-line rollback. For a change touching registry, compression, deploy orchestration, and concurrency, the rollback should cover:
   - Which registry has the last known good image
   - How to revert EC2 GHCR credentials if they are the problem
   - How to revert Docker version if zstd is the problem (answer: you don't -- this is irreversible)

**Verdict: PARTIAL.** The basic rollback mechanism works, but the runbook does not cover registry-specific or compression-specific failure modes. Recommend documenting: "Last known good Docker Hub image: `samkarazi/bebang-erpnext-hrms:v15-<sha>`" before the swap, so it can be used as an emergency fallback.

---

### R7: git clone --depth 1 vs bench get-app (Missing Hooks)

**Scenario:** `bench get-app` does more than clone a repo. The manual `git clone --depth 1 + yarn install + pip install -e` approach misses bench-specific setup steps, causing runtime failures.

**What bench get-app does (source: frappe/bench codebase):**

1. `git clone` the repo -- **COVERED** by `git clone --depth 1`
2. `pip install -e ./app` -- **COVERED** by `pip install -e apps/hrms`
3. `yarn install` (if package.json exists) -- **COVERED** by explicit `yarn install --check-files`
4. Updates `sites/apps.txt` (registers the app with Frappe) -- **NOT NEEDED** (hrms is already registered in the base image; only the code is replaced)
5. Runs `setup.py` / `pyproject.toml` hooks -- **COVERED** by `pip install -e` (pip runs setup hooks)
6. Installs app fixtures -- **NOT NEEDED** at build time (fixtures are applied during `bench migrate` at deploy time)
7. `bench build --app hrms` -- **COVERED** by explicit `bench build --app hrms`

**What could go wrong:**
- If hrms adds a new Python dependency in a future commit, `pip install -e` will install it (correct)
- If hrms adds a new JS dependency, `yarn install` will install it (correct)
- If hrms adds a `post_install` hook in `hooks.py`, it runs during `bench migrate`, not during `bench get-app` (so this is fine)
- If hrms changes its `apps.txt` entry name (extremely unlikely), the clone approach would break -- but this would also break the base image

**The iteration log confirms:** Iteration 3 failed because `yarn install` was missing. Iteration 4 added it and succeeded. The 5 validation runs in Iteration 5 confirm the approach works end-to-end with real production code.

**Remaining gap:** `bench get-app` also runs `bench setup requirements` which ensures system-level dependencies (like wkhtmltopdf) are present. The overlay approach inherits these from the base image, so this is fine -- unless hrms adds a NEW system dependency. This is an edge case that would also break the current build (since the Frappe Docker base image pins system deps).

**Verdict: INADEQUATE (downgraded to LOW after analysis).** The theoretical risk exists but is mitigated by the fact that (a) 5 validation runs passed, (b) `apps.txt` is inherited from the base image, and (c) system deps are inherited. However, the plan should document the assumption: "If hrms adds a new system-level dependency (apt package), the base image must be rebuilt." This is a documentation gap, not a functional gap.

**Revised verdict: ADEQUATE with documentation caveat.** The approach is functionally correct for the current codebase. The risk is that a future hrms change adds a system dependency -- but this is equally true of the current build approach.

---

## Summary of Findings

| # | Risk | Final Severity | Mitigation Status | Action Required |
|---|------|---------------|-------------------|-----------------|
| R1 | GHCR outage | Medium | INADEQUATE | Document fallback to Docker Hub (5 min task) |
| R2 | EC2 Docker version | High | PLANNED | Add AMI snapshot before upgrade, schedule maintenance window |
| R3 | SSM timeout | Low | ADEQUATE | None |
| R4 | Partial image on cancel | Negligible | ADEQUATE | None |
| R5 | Missing PWA assets | Negligible | ADEQUATE | None |
| R6 | Rollback complexity | Medium | PARTIAL | Document last known good Docker Hub SHA before swap |
| R7 | bench get-app hooks | Low | ADEQUATE | Document system-dep assumption |

**Blocking risks:** 0
**Risks requiring action before execution:** 3 (R1, R2, R6 -- all documentation/planning tasks, not code changes)
**Risks adequately mitigated:** 4 (R3, R4, R5, R7)

---

## GO/NO-GO Recommendation

**CONDITIONAL GO.**

The plan is technically sound. The build approach is validated with 5 real runs. The deploy consolidation is strictly better than the current 3-round approach. The concurrency split is safe due to GitHub Actions job dependency mechanics.

Three items must be addressed before Phase B execution (not before Phase A):

1. **R1 (GHCR fallback):** Add a 1-paragraph fallback procedure to the plan: "If GHCR is down, manually push to Docker Hub and deploy from there using existing credentials."

2. **R2 (Docker upgrade):** Before upgrading Docker on EC2, take an AMI snapshot. Schedule the upgrade during off-peak hours (2-5 AM PHT). Do not treat this as a routine `apt upgrade`.

3. **R6 (Rollback baseline):** Before executing B4 (production swap), record the last known good Docker Hub image tag and SHA. This is the emergency fallback if both GHCR and zstd prove problematic.

Phase A (deploy consolidation + smart concurrency) can proceed immediately -- it does not touch the registry or compression stack.

**Overall risk level: MODERATE.** The plan changes three infrastructure layers simultaneously (registry, compression, deploy orchestration). Each change individually is low-risk, but the combination increases rollback complexity. The phased approach (A then B) correctly sequences the risk, and the plan's existing verification gates (B1-B3) catch most failure modes before the production swap (B4).
