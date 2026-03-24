# S105 Decision: TARGET MET

## Result

| Metric | Baseline | Final | Change |
|--------|----------|-------|--------|
| Build step time | 334s (5.6 min) | 129s (2.1 min) | -61% |
| Total pipeline | ~12 min | ~8 min | -33% |

## Target: <180s (3.0 min) — ACHIEVED at 129s (2.1 min)

## Winning Configuration

1. **Base image**: `samkarazi/bebang-erpnext-hrms:v15` (existing production image)
2. **Code update**: `git clone --depth 1` + `yarn install` (not bench get-app)
3. **Build tools**: None (no gcc needed — pip has no C compilations)
4. **Asset build**: `bench build --app hrms` with PWA/roster skip
5. **Push target**: GHCR (`ghcr.io/bebang-enterprise-inc/...`)
6. **Compression**: zstd (OCI mediatypes)
7. **Cache**: `type=registry` with `image-manifest=true` for layer dedup
8. **Layers**: Separate small layers (not combined — push efficiency)

## Next Steps

To promote to production pipeline (`build-and-deploy.yml`):
1. Apply the same Containerfile pattern (git clone instead of bench init)
2. Switch push from Docker Hub to GHCR
3. Update EC2 deploy to pull from GHCR
4. Add zstd compression + registry cache
5. Keep Docker Hub as secondary tag (for backward compatibility)

## Risk Assessment

- **GHCR dependency**: If GHCR has outage, builds/deploys fail. Mitigate: keep Docker Hub as fallback
- **zstd compatibility**: Requires Docker 25+ on EC2. Verify EC2 Docker version before swap
- **PWA skip**: PWA/roster builds are skipped. If they're needed in Docker image, this breaks them
- **No gcc**: If a future hrms pip dep needs C compilation, builds will fail. Monitor pip install output
