# S105 Docker Fast Build — Complete Iteration Log

## Final Winner: Iteration 8 — 54s average (0.9 min), 84% faster than baseline

## All Iterations

| Iter | Time | Key Change | Outcome | Learning |
|------|------|------------|---------|----------|
| 0 | 334s (5.6m) | Baseline | Measured | Build=173s layers + Docker overhead |
| 1 | FAIL | git fetch in-place | .git stripped | Upstream Containerfile runs `find -path "*/.git" \| xargs rm -fr` |
| 2 | 371s (6.2m) | Single combined RUN layer | REGRESSION +37s | One big layer = 232s push. Separate layers = 56s push. Layer count matters for push. |
| 3 | FAIL | git clone --depth 1, no yarn | Missing html2canvas | bench get-app runs yarn automatically; manual clone needs explicit yarn install |
| 4 | 237s (4.0m) | git clone + yarn, no gcc | -29% | gcc not needed (0 C compilations). Build work = 60s, Docker overhead = 174s (74%). |
| 5 | 129s (2.1m) | GHCR push + zstd | -61% | GHCR push 7.5x faster than Docker Hub (same datacenter). Zstd export 4.2x faster. |
| 6 | 112s (1.9m) | GHCR base pull | -66% | GHCR pull SLOWER than Docker Hub (65s vs 43s) because image was bigger. But export+push faster due to registry cache dedup. |
| 7 | 81s (1.4m) | Preserve node_modules | -76% | Skip yarn install by keeping existing node_modules. Source update: 26s to 3s. |
| **8** | **54s (0.9m)** | **Docker Hub base + preserve nm + GHCR push** | **-84%** | **Best of both registries: Docker Hub for pull (40s), GHCR for push (0.3s).** |
| 4-core | UNAVAILABLE | ubuntu-latest-4-cores | Not on plan | BEI GitHub plan doesn't include larger runners. |

## Iteration 8 Validation (5 runs, unique SHAs)

| Run | Time | SHA |
|-----|------|-----|
| 1 | 50s | a0ebf91 |
| 2 | 55s | e9b495d |
| 3 | 55s | dab5d58 |
| 4 | 62s | 84a50bf |
| 5 | 47s | 08e4345 |
| **Avg** | **54s** | |
| Std Dev | 5s | |
| Min | 47s | |
| Max | 62s | |

## Iteration 8 Layer Breakdown

| Layer | Time | % of Total |
|-------|------|-----------|
| Base image pull (Docker Hub) | 40.2s | 78% |
| Source code update (preserve node_modules) | 2.2s | 4% |
| pip install | 2.3s | 4% |
| bench build --app hrms | 2.7s | 5% |
| Export + push (GHCR, zstd) | 3.9s | 8% |
| **Total** | **51.3s** | |

## Winning Configuration

```
FROM: samkarazi/bebang-erpnext-hrms:v15 (Docker Hub — 40s pull)
PUSH TO: ghcr.io/bebang-enterprise-inc/... (GHCR — 0.3s push)
COMPRESSION: zstd level 3 (4.2x faster export than gzip)
CACHE: type=registry on GHCR with image-manifest=true
CODE UPDATE: git clone --depth 1, copy source only, preserve node_modules
BUILD: bench build --app hrms (skip PWA/roster)
NO gcc/build-essential needed
```

## Approaches Researched but Not Tested

| Approach | Expected | Reason Not Tested |
|----------|----------|-------------------|
| Depot.dev | 45s-1.2m | Requires paid account ($20/mo) |
| Docker Build Cloud | 1.0-1.5m | Requires signup |
| 4-core runner | 35-40s est | Not on BEI GitHub plan |
| Volume mount deploy | 5-15s | Frappe docs warn against it. State drift risk. |
| rsync hot-reload | 10-30s | Dev-only. No rollback mechanism. |
| Gunicorn SIGHUP | 2-5s | Blocked by --preload flag |
| bench update in container | 60-120s | Frappe explicitly says don't do this in production |
| Layer squashing | Neutral | Counterproductive — destroys cache granularity |
| Kaniko/ko | Same | No speed benefit over buildx |

## Deploy Consolidation

| Metric | Current | Consolidated |
|--------|---------|-------------|
| SSM rounds | 3 (image + Sentry + Supabase) | 1 (combined) |
| Service restarts | 14 (4 services x 3 rounds + 2 x 1) | 6 (1 per service) |
| Time | 357s (5.9m) | 41s (0.7m) |
| Speedup | — | 8.7x |

## Full Pipeline Projection

| Phase | Current | Optimized |
|-------|---------|-----------|
| Build | 307s (5.1m) | 54s (0.9m) |
| Deploy | 340s (5.7m) | 41s (0.7m) |
| Post-deploy | 80s (1.3m) | 80s (1.3m) |
| **Total** | **727s (12.1m)** | **175s (2.9m)** |
| **Improvement** | — | **76%** |

## Key Learnings

1. **Use each registry for what it's fastest at** — Docker Hub for pull (closer CDN or better caching), GHCR for push (same datacenter as GHA runners).
2. **Layer count matters for push, not build** — One big layer = slow push. Small layers = fast push (unchanged layers skip).
3. **Preserve what hasn't changed** — node_modules, pip packages. Don't rm -rf and reinstall.
4. **zstd compression is a free win** — 4.2x faster export with similar compression ratio.
5. **Base image pull dominates** — 78% of build time on ephemeral runners. Only fixable with persistent cache (Depot/Build Cloud) or larger runners.
6. **Deploy consolidation is the biggest win** — 8.7x speedup by combining 3 SSM rounds into 1 with parallel service updates.
7. **Test with real infrastructure** — The pre-built base image approach (original plan) showed 0% improvement because Docker overhead dominated. Only real benchmarks revealed the actual bottlenecks.
