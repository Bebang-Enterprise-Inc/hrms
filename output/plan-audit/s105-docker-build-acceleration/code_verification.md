# Code Verification Report
## Plan: S105 Docker Build Acceleration
## Date: 2026-03-24

### Verification Summary
| # | Claim | Status | Evidence |
|---|-------|--------|----------|
| 1 | CACHE_BUST on line 135 | CONFIRMED | Line 135: `CACHE_BUST=${{ github.sha }}` |
| 2 | no-cache on line 138 | CONFIRMED | Line 138: `no-cache: ${{ github.event_name == 'push' \|\| github.event.inputs.no_cache == 'true' }}` |
| 3 | 3 apps in apps.json (erpnext, payments, hrms) | CONFIRMED | `.github/helper/apps.json` contains exactly 3 entries: erpnext (version-15), payments (version-15), hrms (production) |
| 4 | Upstream Containerfile: 3 stages (base, builder, backend); base has git/node/yarn but NOT gcc | CONFIRMED | Stages: `base` (python slim + git, node via nvm, yarn, NO gcc), `builder` (adds gcc, build-essential, etc.), `backend` (copies from builder) |
| 5 | `bench build --app hrms` is valid | CONFIRMED | `.github/helper/install.sh:105` uses `bench build --app frappe`, confirming `--app` flag is valid |
| 6 | `bench get-app --depth` flag exists | STALE | `bench get-app` has NO `--depth` CLI flag. Bench uses `shallow_clone` config internally (`git fetch --depth=1`), but this is not exposed as a `get-app` argument |
| 7 | Deploy job has all listed post-deploy steps | CONFIRMED | All present: SSM deploy (line 174), Sentry DSN (line 247), Supabase env (line 278), nginx fix (line 309), Blip proxy (line 340), migrations (line 400), Redis flush (line 465), asset sync (line 431), verification (lines 492+515), cleanup (line 539 separate job) |
| 8 | Docker Swarm `docker service update` commands | CONFIRMED | Line 216-221: `docker service update --detach=false --with-registry-auth --image $DEPLOY_IMAGE` for 6 services: frappe_backend, frappe_frontend, frappe_websocket, frappe_queue-short, frappe_queue-long, frappe_scheduler |
| 9 | Workflow file is 639 lines | STALE | Actual line count: 638 lines (off by 1; line 639 is blank/EOF not counted by `wc -l`) |
| 10 | Python 3.11.6 / Node 20.19.2 in build-args | CONFIRMED | Line 132: `PYTHON_VERSION=3.11.6`, Line 133: `NODE_VERSION=20.19.2` |

### CONFIRMED Claims (8 of 10)

1. **CACHE_BUST** - `build-and-deploy.yml:135`: `CACHE_BUST=${{ github.sha }}`
2. **no-cache** - `build-and-deploy.yml:138`: `no-cache: ${{ github.event_name == 'push' || github.event.inputs.no_cache == 'true' }}`
3. **apps.json** - `.github/helper/apps.json`: 3 apps (erpnext version-15, payments version-15, hrms production)
4. **Containerfile stages** - Upstream has 3 stages: `base` (python-slim + git, curl, nginx, nvm/node/yarn, wkhtmltopdf, frappe-bench; NO gcc/build-essential), `builder` (adds gcc, build-essential, libmariadb-dev, etc. + runs `bench init`), `backend` (copies built bench from builder)
5. **`bench build --app`** - Valid flag, confirmed by usage in `.github/helper/install.sh:105`
7. **Deploy steps** - All 10 listed post-deploy steps confirmed present in order
8. **Docker Swarm** - Uses `docker service update` for 6 Swarm services
10. **Python/Node versions** - 3.11.6 and 20.19.2 confirmed in build-args

### STALE Claims (2 of 10)

6. **`bench get-app --depth`** - No such CLI flag exists. Bench internally uses `--depth 1` via `self.bench.shallow_clone` config, but this is a bench site config setting, not a `get-app` argument. The plan cannot use `bench get-app --depth 1 <url>`. Instead, the plan should set `shallow_clone: true` in bench config or use `git clone --depth 1` directly.

9. **639 lines** - File is 638 lines per `wc -l`. Trivial difference (likely the file ended with a newline that the plan counted as line 639). Not material.

### NEW GAPS (Issues the Plan May Have Missed)

1. **Upstream default versions diverged significantly** - The upstream Containerfile now defaults to `PYTHON_VERSION=3.14.2` and `NODE_VERSION=24.13.0` (and `FRAPPE_BRANCH=version-16`). BEI pins 3.11.6/20.19.2/version-15. If S105 creates a base image from upstream without pinning these ARGs, it will get the wrong versions. The plan MUST ensure the base image build passes the same `PYTHON_VERSION`, `NODE_VERSION`, and `FRAPPE_BRANCH` build-args.

2. **Asset sync step depends on migration step** - Both asset sync (line 431) and migrations (line 400) share the same `if` condition (`run_migrate != 'false'`). If the plan splits build from deploy, it must preserve this coupling -- assets must be synced after migration runs.

3. **6 Swarm services, not just "backend"** - The deploy updates 6 services (backend, frontend, websocket, queue-short, queue-long, scheduler). A two-layer image strategy must ensure ALL 6 services use the same final image, since they all currently share one image tag.

4. **`setuptools<71` pin in migration step** - Line 414 pins `setuptools<71` before migration. If the base image pre-installs a different setuptools version, this step may conflict or become unnecessary. The plan should note this dependency.

5. **no-cache is ALWAYS true on push events** - Line 138 forces `no-cache: true` for all `push` events (not just workflow_dispatch). This means every merge to production currently does a full uncached build. The S105 plan's goal of caching the base layer is partially undermined by this -- the plan must change this line to allow cache hits on the base layer while still busting the app layer cache.
