# Continuous Improvement: S105 Docker Fast Build

## Loop Contract

| Field | Value |
|-------|-------|
| target_artifact | `.github/docker/Containerfile.fast` |
| artifact_type | infrastructure/Dockerfile |
| goal_metric | GHA build step time < 300s (5 min) |
| fixed_harness | `build-fast.yml` on s105-docker-build-acceleration branch |
| eval_set | GHA run step timing (Build and push fast image step) |
| binary_assertions | build succeeds, image pushes to Docker Hub, time < 300s |
| qualitative_review_method | EC2 smoke test after target met |
| keep_threshold | time_new < time_previous AND build succeeds |
| revert_conditions | build fails OR time increases |
| risk_class | low (test lane only, production untouched) |
| promotion_rule | Build under 300s with successful image |
| stop_rule | target met OR 5 iterations with no improvement |

## Baseline

| Metric | Value |
|--------|-------|
| Current full build avg | 343s (5m43s) |
| Iteration 0 (fast build v1) | 334s (5m34s) — only 3% faster |
| Target | <300s (5m00s) |
| Gap to close | 34s minimum |

## Mutable

- `.github/docker/Containerfile.fast` only

## Fixed (never change during loop)

- `.github/workflows/build-fast.yml` (harness)
- Production workflow `build-and-deploy.yml`
- Base image `samkarazi/bebang-erpnext-hrms:v15`
- Docker Hub credentials
- GHA runner type (ubuntu-latest)

## Optimization Hypotheses (research-backed)

1. **Skip remove+re-add cycle** — git pull in-place instead of bench remove + bench get-app
2. **Skip gcc/build-essential** — base image already has pip deps; only needed if hrms added NEW C deps
3. **Combine RUN layers** — fewer layers = less overhead
4. **Skip bench build entirely** — use esbuild directly for desk assets
5. **Use --mount=type=cache for apt** — avoid re-downloading packages
6. **Parallel pip+yarn** — run pip install and yarn install concurrently
