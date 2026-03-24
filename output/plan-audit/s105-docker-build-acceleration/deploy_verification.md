# S105 Deploy Verification — Workflow Audit

**Source:** `.github/workflows/build-and-deploy.yml`
**Audited:** 2026-03-24

---

## Claim-by-Claim Verification

### 1. "Exactly 3 separate SSM rounds for deploy (image update, Sentry DSN, Supabase env)"

**CORRECT.** The deploy job has 3 SSM `send-command` calls for service updates:
1. **Image update** (lines 187-238) — "Deploy via Docker Swarm" step
2. **Sentry DSN** (lines 252-267) — "Set Sentry DSN on services" step
3. **Supabase env** (lines 283-298) — "Set Supabase runtime env on services" step

### 2. "The image update round updates 6 services sequentially with --detach=false"

**CORRECT.** Lines 216-221, all with `--detach=false`:
1. `frappe_backend`
2. `frappe_frontend`
3. `frappe_websocket`
4. `frappe_queue-short`
5. `frappe_queue-long`
6. `frappe_scheduler`

### 3. "The Sentry DSN round updates 4 services"

**CORRECT.** Lines 257-260, each with `--detach=false`:
1. `frappe_backend`
2. `frappe_queue-short`
3. `frappe_queue-long`
4. `frappe_scheduler`

### 4. "The Supabase env round updates 4 services"

**CORRECT.** Line 288-289, via a `for SERVICE in` loop:
1. `frappe_backend`
2. `frappe_queue-short`
3. `frappe_queue-long`
4. `frappe_scheduler`

### 5. "There are post-deploy steps: nginx fix, Blip proxy, migrations, asset sync, Redis flush, API verification, asset verification"

**CORRECT.** All 7 post-deploy steps exist:
1. **Fix nginx site header** (lines 309-338)
2. **Configure Blip webhook proxy** (lines 340-398)
3. **Run migrations** (lines 400-429) — conditional on `run_migrate != 'false'`
4. **Sync assets to frontend container** (lines 431-463) — conditional on `run_migrate != 'false'`
5. **Flush Redis cache** (lines 465-490)
6. **Verify deployment** (lines 492-513) — API ping check with retry loop
7. **Verify login page assets loading** (lines 515-537) — asset URL HTTP checks

### 6. "There is a setuptools<71 pin in the migration step"

**CORRECT.** Line 414:
```
docker exec $BACKEND_CONTAINER /home/frappe/frappe-bench/env/bin/pip install -q "setuptools<71"
```

### 7. "The cleanup job keeps 4 most recent images"

**CORRECT.** Line 560 comment: "keep latest 4 builds". Line 577: `tail -n +5` (skips first 4, removes the rest).

### 8. "The concurrency group is `frappe-production-deploy` with `cancel-in-progress: false`"

**CORRECT.** Lines 5-7:
```yaml
concurrency:
  group: frappe-production-deploy
  cancel-in-progress: false
```

### 9. "Count exactly how many separate SSM send-command calls exist in the deploy job"

**Total SSM `send-command` calls in the deploy job: 8**

| # | Step | SSM Call | Poll/Max |
|---|------|----------|----------|
| 1 | Deploy via Docker Swarm (image update) | Yes | 15s / 80 attempts |
| 2 | Set Sentry DSN | Yes | 10s / 60 attempts |
| 3 | Set Supabase runtime env | Yes | 10s / 60 attempts |
| 4 | Fix nginx site header | Yes | 10s / 40 attempts |
| 5 | Configure Blip webhook proxy | Yes | 10s / 40 attempts |
| 6 | Run migrations | Yes | 15s / 80 attempts |
| 7 | Sync assets to frontend | Yes | 10s / 40 attempts |
| 8 | Flush Redis cache | Yes | 10s / 40 attempts |

**Note:** The cleanup job has 1 additional SSM call (30s / 20 attempts), but that's in a separate job, not the deploy job.

The Verify deployment and Verify login page assets steps do NOT use SSM — they run `curl` directly from the GitHub runner.

---

## Additional Analysis

### Which services get what?

| Service | Image Update | Sentry DSN | Supabase Env |
|---------|:---:|:---:|:---:|
| `frappe_backend` | Yes | Yes | Yes |
| `frappe_frontend` | Yes | No | No |
| `frappe_websocket` | Yes | No | No |
| `frappe_queue-short` | Yes | Yes | Yes |
| `frappe_queue-long` | Yes | Yes | Yes |
| `frappe_scheduler` | Yes | Yes | Yes |

### Services that ONLY need image update (no env vars):
- `frappe_frontend` — only serves static assets via nginx
- `frappe_websocket` — only handles WebSocket connections

### SSM Timeout Configuration

All SSM calls use `ssm_wait_and_assert.sh` with two parameters: **poll interval (seconds)** and **max attempts**.

| Step | Poll Interval | Max Attempts | Max Wait Time |
|------|:---:|:---:|:---:|
| Image update | 15s | 80 | 20 min |
| Sentry DSN | 10s | 60 | 10 min |
| Supabase env | 10s | 60 | 10 min |
| Nginx fix | 10s | 40 | 6.7 min |
| Blip proxy | 10s | 40 | 6.7 min |
| Migrations | 15s | 80 | 20 min |
| Asset sync | 10s | 40 | 6.7 min |
| Redis flush | 10s | 40 | 6.7 min |
| Cleanup (separate job) | 30s | 20 | 10 min |

**Theoretical maximum deploy time (all steps sequential, max wait):** ~80 min for deploy job + 10 min cleanup = ~90 min worst case.

### Consolidation Opportunity Summary

The Sentry DSN and Supabase env rounds target the **exact same 4 services** (`backend`, `queue-short`, `queue-long`, `scheduler`). Each round causes those 4 services to restart with `--detach=false`. Consolidating these into the image update round (using `--env-add` flags on the same `docker service update` command) would eliminate 8 unnecessary service restarts (4 services x 2 rounds) and 2 SSM round-trips.
