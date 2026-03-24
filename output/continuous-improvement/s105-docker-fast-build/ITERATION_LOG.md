# S105 Docker Fast Build — Iteration Log

## Baseline (Iteration 0): 334s (5.6 min)
- FROM samkarazi/bebang-erpnext-hrms:v15
- apt-get install gcc/build-essential (11s)
- bench remove-app hrms (8s)
- bench get-app --skip-assets hrms (47s)
- pip install (3.5s)
- bench build --app hrms with PWA skip (3.6s)
- apt-get purge gcc (1s)
- Push to Docker Hub (56s)
- **Result: 334s (5.6 min)**

## Iteration 1: FAILED
- Change: git fetch+reset in-place (skip bench remove+get-app)
- Error: `fatal: not a git repository` — upstream Containerfile strips .git dirs
- Learning: Cannot use git pull, must clone fresh

## Iteration 2: 371s (6.2 min) — REGRESSION
- Change: Single combined RUN layer, skip gcc
- Error: Push exploded to 232s (vs 56s baseline)
- Learning: One large layer = massive push. Separate small layers = efficient push
- **Decision: REVERT** (single layer approach abandoned)

## Iteration 3: FAILED
- Change: git clone --depth 1 (skip bench get-app), no gcc, separate layers
- Error: `Could not resolve "html2canvas"` — missing node deps
- Learning: Need yarn install after clone (bench get-app does this automatically)

## Iteration 4: 237s (4.0 min) — 29% improvement
- Change: Added yarn install after git clone
- Breakdown: pull 40s + clone+yarn 52s + pip 3.4s + build 4s + export 56s + push 78s
- Learning: Build work = 60s (fast!). Docker overhead = 174s (74% of total)
- **Decision: KEEP**

## Iteration 5: 129s (2.1 min) — 61% improvement, TARGET MET
- Change: Push to GHCR instead of Docker Hub + zstd compression
- Breakdown: pull 43s + clone+yarn 52s + pip 3.5s + build 3.7s + export 13s + push 10s
- Key wins: Export 56s→13s (zstd 4.2x faster), Push 78s→10s (GHCR 7.5x faster)
- **Decision: KEEP — TARGET MET**

## Summary

| Iteration | Time | Delta | Key Change | Status |
|-----------|------|-------|-----------|--------|
| Baseline | 334s (5.6m) | — | Full rebuild | Measured |
| 1 | FAIL | — | git fetch in-place | .git stripped |
| 2 | 371s (6.2m) | +37s | Single layer | REGRESSION |
| 3 | FAIL | — | git clone no yarn | Missing node deps |
| 4 | 237s (4.0m) | -97s (29%) | git clone + yarn | KEEP |
| 5 | 129s (2.1m) | -205s (61%) | GHCR + zstd | TARGET MET |

## Key Learnings

1. **Layer count matters for push**: One big layer = slow push. Small separate layers = fast push (unchanged layers skip)
2. **GHCR vs Docker Hub**: GHCR is 7.5x faster for push from GHA runners (same datacenter)
3. **zstd vs gzip**: zstd compression is 4.2x faster for layer export
4. **Build work is fast**: Actual code operations (clone+yarn+pip+build) = 60s. Docker overhead dominates
5. **.git dirs stripped by upstream**: Cannot use git fetch/pull in-place on production images
6. **yarn install required**: bench get-app runs yarn automatically; manual clone needs explicit yarn install
