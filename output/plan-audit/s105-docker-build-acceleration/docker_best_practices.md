# Docker Best Practices Research (2025-2026)
## Date: 2026-03-24

---

### Topic 1: Multi-Stage Build Optimization

**Best Practices:**

1. **Pre-built base images:** The dominant pattern in 2025-2026 is to maintain a pre-built "base" image containing OS packages, language runtimes, and system dependencies that change infrequently. This base image is rebuilt on a schedule (weekly/monthly) and tagged as `base:latest` or `base:YYYY-MM-DD`. Application builds then use `FROM myorg/base:latest` instead of rebuilding system dependencies every time.

2. **Layer ordering matters:** Docker caches layers sequentially. Place the most stable layers first (OS packages, system libs, language runtimes) and the most volatile last (application code, `COPY . .`). The frappe_docker Containerfile already follows this pattern with `base -> builder -> backend` stages.

3. **Separate dependency installation from code copying:** Install language dependencies (pip, npm) from lock files BEFORE copying application source code. This means `COPY requirements.txt .` + `RUN pip install` before `COPY . .`. This prevents dependency reinstallation when only application code changes.

4. **Use `--mount=type=cache` for package managers (BuildKit):** Since Docker 18.09+ with BuildKit, you can persist package manager caches across builds:
   ```dockerfile
   RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt
   RUN --mount=type=cache,target=/home/frappe/.cache/yarn yarn install
   ```
   This avoids re-downloading packages that haven't changed even when the layer is invalidated.

5. **Multi-stage COPY --from for minimal final images:** Copy only the built artifacts from builder stages into the final runtime image. The current Containerfile does this correctly with `COPY --from=builder`.

6. **Squash unnecessary layers:** Combine related `RUN` commands with `&&` to reduce layer count. Each layer adds overhead. The current Containerfile already does this well.

**Relevance to S105:**

The current `build-and-deploy.yml` rebuilds the entire Containerfile from scratch on every push to production (`no-cache: true` for push events). The biggest opportunity is a **pre-built base image strategy**:

- **Current pain:** The `base` stage (apt-get, nvm, wkhtmltopdf, pip install frappe-bench) takes ~3-5 minutes and NEVER changes between HRMS deploys. The `builder` stage (apt-get dev packages, `bench init`, `bench get-app` for erpnext, payments, hrms) takes ~8-15 minutes, but erpnext and payments versions rarely change.
- **Acceleration path:** Pre-build a `bei-base:v15` image containing the `base` + `builder` stages with erpnext and payments pre-installed. On HRMS-only changes, start from this pre-built image and only run `bench get-app hrms` (or a targeted update). This could reduce build time from ~15-20 minutes to ~3-5 minutes.
- **BuildKit cache mounts** for pip/yarn would help even without a pre-built base.

---

### Topic 2: GHA Docker Cache

**Best Practices:**

1. **`type=gha` (GitHub Actions cache):**
   - Uses GitHub's native Actions cache (10 GB limit per repo).
   - Pros: Zero configuration, fast for same-runner builds, works across workflow runs.
   - Cons: 10 GB limit is tight for large images; cache eviction is LRU with 7-day TTL; cache is scoped per branch (PRs can read base branch cache).
   - `mode=max` exports all layers (including intermediate); `mode=min` exports only final layers.
   - **Best for:** Small-to-medium images where you don't need cross-repo sharing.

2. **`type=registry` (Registry cache):**
   - Stores cache layers as a manifest in the container registry (Docker Hub, GHCR, ECR).
   - Pros: No size limit (registry storage), shared across all runners and repos, survives cache eviction.
   - Cons: Requires push/pull from registry (network I/O), needs authentication.
   - `mode=max` is strongly recommended to cache all intermediate layers.
   - **Best for:** Large images, multi-platform builds, or when GHA cache limit is insufficient.
   - Pattern: Use a dedicated cache tag like `myimage:buildcache` separate from release tags.

3. **`type=local` (Local filesystem cache):**
   - Stores cache on the runner's filesystem.
   - Pros: Fastest I/O (no network).
   - Cons: Lost when runner is recycled (GitHub-hosted runners are ephemeral), only useful for self-hosted runners with persistent storage.
   - **Best for:** Self-hosted runners only.

4. **`type=inline` (Inline cache metadata):**
   - Embeds cache metadata directly into the pushed image.
   - Pros: Simplest setup, no extra cache storage needed.
   - Cons: Only caches the final image layers (equivalent to `mode=min`), cannot cache intermediate build stages.
   - **Best for:** Simple builds where you mainly want to cache the final image.

5. **Cache key strategies:**
   - Use content-based keys: `key: docker-${{ hashFiles('requirements.txt', 'package.json') }}` for dependency layers.
   - Use branch-scoped keys with fallback: `key: docker-${{ github.ref }}-${{ github.sha }}` with `restore-keys: docker-${{ github.ref }}-`.
   - For Frappe builds, key on `apps.json` content hash since that determines which app versions get installed.

6. **`mode=max` vs `mode=min`:**
   - `mode=max`: Caches ALL layers including intermediate build stages. Essential for multi-stage builds where you want to reuse the `base` and `builder` stages.
   - `mode=min`: Only caches the layers in the final target stage. Useless for multi-stage builds where the expensive work is in earlier stages.
   - **Always use `mode=max` for multi-stage Dockerfiles.**

**Relevance to S105:**

The current workflow uses:
```yaml
no-cache: true  # For push events (ALWAYS rebuilds from scratch)
cache-from: type=registry,ref=samkarazi/bebang-erpnext-hrms:v15  # Only for manual dispatch
cache-to: type=inline  # Only caches final layers
```

This is the **worst possible caching configuration** for the use case:
- `no-cache: true` on push events means production builds NEVER use cache.
- `type=inline` only caches the final `backend` stage, not the expensive `base` or `builder` stages.
- Even when cache is enabled (manual dispatch), it can only restore the final layers.

**Recommended fix:**
```yaml
cache-from: type=registry,ref=samkarazi/bebang-erpnext-hrms:buildcache,mode=max
cache-to: type=registry,ref=samkarazi/bebang-erpnext-hrms:buildcache,mode=max
```
- Remove `no-cache: true` for push events (use `CACHE_BUST` ARG to invalidate only the HRMS layer).
- Switch from `type=inline` to `type=registry` with `mode=max` to cache ALL intermediate stages.
- Use a dedicated `buildcache` tag to avoid polluting release tags.

---

### Topic 3: Frappe Docker Custom App Builds

**Best Practices:**

1. **The `apps.json` pattern:** Frappe Docker's standard approach is to define all apps in `apps.json` with their Git URLs and branches. The `bench init` command in the Containerfile reads this file and installs all apps during the build. This is the approach BEI currently uses.

2. **Known issue: Full rebuild on any app change:** Because `bench init --apps_path` installs ALL apps in a single `RUN` command, changing ANY app (even just HRMS) forces reinstallation of ALL apps (frappe, erpnext, payments, hrms). This is the single biggest build time bottleneck.

3. **Community workaround: Layered Containerfile:** The frappe_docker repo includes an alternative `images/layered/Containerfile` that installs each app in a separate `RUN` layer. This allows Docker to cache unchanged apps and only rebuild the changed one. The BEI `build_image.yml` workflow already references this file but the primary `build-and-deploy.yml` uses `images/custom/Containerfile`.

4. **`bench get-app` in existing bench:** For updating a single app in an existing bench installation (e.g., inside a running container), `bench get-app <url> --branch <branch>` works but has caveats:
   - It clones the entire repo, which is slow for large repos.
   - Use `--resolve-deps` flag to handle dependency conflicts.
   - `bench setup requirements` must be run after to install Python/Node dependencies.
   - `bench build` must be run to rebuild assets.

5. **Git shallow clone optimization:** Use `--depth 1` for all `bench get-app` / `git clone` calls in Dockerfiles. The current Containerfile does NOT explicitly set shallow clone depth for apps.json installations.

6. **Separate Python deps from JS build:** The most time-consuming parts of a Frappe app build are (a) `pip install` for Python dependencies and (b) `yarn install` + `bench build` for JavaScript assets. If Python deps haven't changed, cache that layer.

**Relevance to S105:**

The biggest win is switching from `images/custom/Containerfile` to either:

**Option A: Use the layered Containerfile.** The `images/layered/Containerfile` in frappe_docker installs each app separately, allowing Docker layer caching to skip unchanged apps. Since erpnext and payments rarely change, only the HRMS layer would rebuild.

**Option B: Pre-built base with HRMS overlay.** Build a `bei-base:v15` image containing frappe + erpnext + payments (rebuilt weekly). The deploy workflow starts `FROM bei-base:v15` and only adds HRMS. Build time drops from ~15-20 min to ~3-5 min.

**Option C: HRMS_SHA cache-bust pattern.** Keep the current Containerfile but add an `ARG HRMS_SHA` before the `bench get-app hrms` step. Docker caches everything up to that ARG, and only the HRMS installation layer rebuilds when the SHA changes. This requires a modified Containerfile but minimal workflow changes.

---

### Topic 4: Docker Image Layer Invalidation

**Best Practices:**

1. **ARG-based cache busting:** Docker invalidates all subsequent layers when an `ARG` value changes. Place a `CACHE_BUST` or content-hash ARG immediately before the layer you want to invalidate:
   ```dockerfile
   # Everything above this line is cached
   ARG HRMS_SHA=abc1234
   RUN bench get-app hrms --branch production
   ```
   When `HRMS_SHA` changes, only layers from this point forward rebuild. All prior layers (base, builder, erpnext, payments) remain cached.

2. **Content-hash ARGs vs timestamp ARGs:**
   - **Content hash** (e.g., `HRMS_SHA=${{ github.sha }}`) is idempotent: same content = same hash = cached. This is the best practice.
   - **Timestamp** (e.g., `CACHE_BUST=$(date)`) always invalidates, even if content hasn't changed. Avoid this.
   - The current workflow uses `CACHE_BUST=${{ github.sha }}` which is a content hash (good) BUT it's placed as a build-arg to the entire Containerfile, and with `no-cache: true` it has no effect anyway.

3. **Granular layer splitting:** Instead of one monolithic `RUN bench init --apps_path`, split into multiple `RUN` commands:
   ```dockerfile
   RUN bench init --frappe-branch=v15 /home/frappe/frappe-bench
   ARG ERPNEXT_SHA=...
   RUN bench get-app erpnext --branch version-15
   ARG PAYMENTS_SHA=...
   RUN bench get-app payments --branch version-15
   ARG HRMS_SHA=...
   RUN bench get-app hrms --branch production
   RUN bench build  # JS assets
   ```
   Now changing HRMS only rebuilds from `ARG HRMS_SHA` onward.

4. **Cache-from with ARG ordering:** When using `cache-from: type=registry`, Docker matches layers by their build context + command hash. If an ARG changes, all subsequent layers miss cache. This makes ARG placement critical.

5. **BuildKit inline cache limitations:** `type=inline` cache only stores the final stage's layers. For multi-stage builds, intermediate stages are NOT cached inline. This means `cache-from` with `type=inline` cannot restore the `builder` stage. Use `type=registry,mode=max` instead.

**Relevance to S105:**

The current `CACHE_BUST=${{ github.sha }}` ARG is defined but:
1. It's passed to the Containerfile which doesn't use it in a targeted way (it's not referenced between specific layers).
2. With `no-cache: true` on push events, it's moot anyway.

The recommended pattern for S105:
- Remove `no-cache: true` for push events.
- Switch to `type=registry,mode=max` caching.
- Use a modified Containerfile (or the layered variant) that places `ARG HRMS_SHA` before only the HRMS installation step.
- Pass `HRMS_SHA=${{ github.sha }}` as a build-arg. Everything before HRMS (base, erpnext, payments) uses cache.

---

### Topic 5: Docker build-push-action v6

**Best Practices:**

1. **v6 features (released 2024, stable through 2026):**
   - Full BuildKit integration with all cache backends.
   - `provenance` and `sbom` generation for supply chain security (can be disabled for faster builds with `provenance: false`).
   - Native `platforms` parameter for multi-platform builds.
   - `outputs` parameter for fine-grained control over build outputs.
   - `annotations` support for OCI image annotations.

2. **Single-platform builds:** For single-platform deployments (like BEI's `linux/amd64` only), skip QEMU and multi-platform setup:
   ```yaml
   - name: Set up Docker Buildx
     uses: docker/setup-buildx-action@v3
     # No QEMU needed for single platform

   - name: Build and push
     uses: docker/build-push-action@v6
     with:
       platforms: linux/amd64  # Explicit single platform
       provenance: false       # Skip attestation for speed
   ```
   Removing QEMU saves ~15-30 seconds. Disabling provenance saves another ~10-20 seconds.

3. **Cache configuration in v6:**
   ```yaml
   cache-from: type=registry,ref=myimage:buildcache
   cache-to: type=registry,ref=myimage:buildcache,mode=max
   ```
   v6 supports all BuildKit cache types. `mode=max` is essential for multi-stage builds.

4. **Build secrets in v6:** Use `secrets` parameter instead of build-args for sensitive values:
   ```yaml
   secrets: |
     github_token=${{ secrets.GITHUB_TOKEN }}
   ```
   Then in Dockerfile: `RUN --mount=type=secret,id=github_token ...`

5. **Attestation overhead:** By default, v6 generates SLSA provenance attestations. For internal/private builds where supply chain attestation isn't needed, `provenance: false` and `sbom: false` skip this overhead.

6. **Load vs Push:** `load: true` loads the image into the local Docker daemon (useful for testing). `push: true` pushes to registry. They are mutually exclusive with multi-platform builds but both work for single-platform.

**Relevance to S105:**

Current workflow improvements for v6:
1. **Remove QEMU setup step** -- not needed for `linux/amd64` only builds. Saves ~15-30s.
2. **Add `provenance: false`** -- skip attestation generation. Saves ~10-20s.
3. **Fix cache configuration** -- the biggest win. Switch from `type=inline` to `type=registry,mode=max`.
4. The workflow already correctly uses `docker/build-push-action@v6` and `docker/setup-buildx-action@v3`.

---

### Key Recommendations for S105

1. **Switch cache strategy (biggest impact, ~10-15 min savings):** Replace `no-cache: true` + `type=inline` with `type=registry,mode=max` using a dedicated `buildcache` tag. This single change enables Docker to reuse cached base, builder, erpnext, and payments layers across builds.

2. **Use the layered Containerfile or a custom variant (biggest structural improvement):** Switch from `images/custom/Containerfile` to either `images/layered/Containerfile` or a custom variant that separates app installations into individual `RUN` layers with `ARG <APP>_SHA` cache-bust points. This ensures only the changed app (HRMS) is rebuilt.

3. **Pre-built base image strategy (optional, for maximum speed):** Build a `bei-base:v15` image weekly containing frappe + erpnext + payments. Deploy workflow starts `FROM bei-base:v15` and only installs HRMS. Reduces HRMS-only deploys from ~15-20 min to ~3-5 min.

4. **Remove QEMU step and disable provenance:** Quick wins saving ~30-50 seconds per build since BEI only targets `linux/amd64`.

5. **Use BuildKit cache mounts for pip/yarn:** Add `--mount=type=cache,target=/root/.cache/pip` and similar for yarn to avoid re-downloading packages even when layers are invalidated.

6. **Content-hash cache busting:** Replace the blanket `CACHE_BUST=${{ github.sha }}` with targeted `HRMS_SHA=${{ github.sha }}` placed only before the HRMS installation layer. Pass erpnext/payments SHAs separately so they only rebuild when those repos actually change.

7. **Estimated build time improvement:**
   | Scenario | Current | With S105 Optimizations |
   |----------|---------|------------------------|
   | HRMS-only code change | ~15-20 min | ~3-5 min |
   | ERPNext version bump | ~15-20 min | ~8-12 min |
   | Base image change (Python, Node) | ~15-20 min | ~15-20 min (expected, rare) |

---

### References

- Docker BuildKit cache documentation: https://docs.docker.com/build/cache/
- docker/build-push-action v6: https://github.com/docker/build-push-action
- frappe_docker repository: https://github.com/frappe/frappe_docker
- GitHub Actions cache limits: https://docs.github.com/en/actions/using-workflows/caching-dependencies-to-speed-up-workflows
