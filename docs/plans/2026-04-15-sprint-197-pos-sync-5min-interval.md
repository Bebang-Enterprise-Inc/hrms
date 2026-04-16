---
sprint: S197
display: "Sprint 197 — POS Sync 5-Minute Interval"
branch: s197-pos-sync-5min-interval
repo: hrms
status: PLANNED
created: 2026-04-15
author: Sam Karazi (CEO directive)
depends_on:
  - S189 (BOM consumption pipeline — triggers on every sync)
registry_row: "| `S197` | Sprint 197 | `s197-pos-sync-5min-interval` (hrms) | hrms#TBD | PLANNED 2026-04-15 — POS Sync 5-Minute Interval"
completed_date: ""
execution_summary: ""
---

# S197: POS Sync 5-Minute Interval

## Problem Statement

BEI currently polls Mosaic POS **once per hour** (10 AM–midnight PHT, 15 runs/day) via `.github/workflows/daily-pos-sync.yml`. This was acceptable for daily analytics, but S189 made consumption data trigger-driven — meaning every new `pos_order_items` row feeds `daily_material_consumption` immediately. With hourly polling, the "real-time" DTL dashboard is effectively 30–60 minutes stale on average.

The superadmin sibling app (`bebang-multistore-dashboard`) polls Mosaic **every 5 minutes** via Laravel scheduler (`orders:dispatch-mosaic-website-sync ->everyFiveMinutes() ->withoutOverlapping()`). That's how its "real-time" Mosaic data actually arrives — webhooks are incidental; polling is the primary data path. Confirmed by reading `bebang-multistore-dashboard/routes/console.php` line 18.

**What this sprint delivers:** A new GitHub Actions workflow (`pos-sync-5min.yml`) that runs every 5 minutes, syncs TODAY's Mosaic data only (narrow window, fast), and uses `cancel-in-progress: true` so a slow run can't clog the queue. The existing hourly workflow stays — it still handles the nightly full-day verify + anomaly detection.

## Design Rationale (For Cold-Start Agents)

### Why a NEW workflow instead of modifying `daily-pos-sync.yml`
- `daily-pos-sync.yml` has 3 responsibilities bundled: POS sync, web sync, materialized-view refresh, anomaly detection, verify-sync, failure-notify. Changing its cron to 5-min would run anomaly detection + verification 288 times/day (wasteful, noisy).
- A separate 5-min workflow is single-purpose (POS sync only, today only) and doesn't need the heavy gates.
- The existing workflow keeps its 10 AM–midnight PHT hourly schedule for backward compatibility + nightly verify at 00:30 PHT.

### Why `cancel-in-progress: true` instead of `false`
- Current `daily-pos-sync.yml` uses `cancel-in-progress: false` to serialize runs. At hourly cadence (and 50-min timeout), queuing is fine.
- At 5-min cadence, a run that takes 7+ minutes would queue the next one. After a few slow runs the backlog grows unbounded.
- `cancel-in-progress: true` means a new 5-min trigger cancels the in-flight run. Safe because: (a) each run is idempotent (PostgREST merge-duplicates upsert), (b) the next run will pick up any orders the previous one was about to write, (c) Supabase row-level state is durable regardless of when the script exits.

### Why "today only" instead of "yesterday" (the `--daily` flag)
- `--daily` syncs yesterday (for catch-all reconciliation).
- 5-min polling should target today's current activity. A date range of `--from YYYY-MM-DD --to YYYY-MM-DD` with today's PHT date does this.
- The hourly `--daily` run still catches yesterday's tail.

### Why NOT add a `--today` flag to the script
- Date computation in bash (`date -u '+%Y-%m-%d'` adjusted for PHT) is simpler than modifying Python flags.
- Keeps `scripts/sync_pos_to_supabase.py` untouched (reduces blast radius; no regression risk for the hourly path).

### Why skip `--refresh-views` and `--store-raw` in 5-min runs
- `--refresh-views` triggers a ~30-second MV refresh. Doing that 288 times/day is wasteful — views only need to be fresh for the hourly report, not for every 5-min sync.
- `--store-raw` doubles Supabase writes (raw JSON + normalized rows). Not needed at 5-min cadence; hourly run still stores raw for audit.

### Key trade-off: Mosaic API load
- 12× increase in outbound requests to Mosaic (45 hourly → 540 at 5-min cadence × 12 credential groups parallel).
- Mosaic's OpenAPI does not document rate limits (verified against `docs/api/MOSAIC_API_OPENAPI_2026-04-14.json`). Superadmin already runs at 5-min cadence against the same Mosaic tenant — if rate limits existed, superadmin would be hitting them.
- Mitigation: Phase 1 T3 adds a timing/error-rate observability check; if Mosaic starts returning 429 or 5xx spikes, Phase 2 rollback is immediate (revert cron to hourly).

## BOM Source of Truth

Not applicable — this is a cron/workflow change only. No data-model changes.

## Duplication Audit

| What | Where | Finding | Classification |
|------|-------|---------|----------------|
| Hourly Mosaic sync | `.github/workflows/daily-pos-sync.yml` | Runs hourly 10 AM–midnight PHT + nightly verify at 00:30 PHT | **[EXTEND]** — keep as nightly backup; add 5-min workflow alongside |
| `sync_pos_to_supabase.py` | `scripts/sync_pos_to_supabase.py` | Already supports `--from/--to`, `--parallel`, `--refresh-views`, `--store-raw` | **[SKIP]** — no script change needed |
| Superadmin 5-min polling | `bebang-multistore-dashboard/routes/console.php:18` | Laravel `everyFiveMinutes()->withoutOverlapping()` already in production | **[REFERENCE]** — proven prior art for cadence feasibility |
| S189 BOM consumption triggers | `supabase/migrations/20260414_s189_realtime_bom_consumption.sql` | Fire on `pos_order_items` INSERT/UPDATE | **[CONSUME]** — will auto-benefit from 5-min sync; no change needed |

---

## Phase 0: Current-State Audit (4 units)

**Goal:** measure before we change. Produce baseline metrics so Phase 2 can detect regressions.

### T0.1 Measure current hourly sync duration + output volume (2 units)

Read the last 7 days of `daily-pos-sync.yml` GH Actions runs:

```bash
GH_TOKEN="" gh run list --repo Bebang-Enterprise-Inc/hrms \
  --workflow daily-pos-sync.yml --limit 100 \
  --json createdAt,conclusion,status \
  --jq '[.[] | select(.conclusion=="success")] | length, (.[0:10] | map({createdAt, conclusion}))'
```

Record in `output/s197/baseline.md`:
- Average run duration (minutes)
- Peak run duration (minutes)
- Success rate (%) over last 7 days
- Orders synced per run (query `pos_orders` aggregated by `updated_at` hour)

**MUST_MODIFY:** `output/s197/baseline.md` (new file)
**MUST_CONTAIN:** table with 5 columns — run_time_pht, duration_min, success, orders_synced, mosaic_errors

### T0.2 Measure Mosaic API rate-limit headroom (2 units)

Call Mosaic `/api/v1/orders` once per credential group (12 groups) capturing headers:

```python
# scripts/s197_measure_mosaic_headroom.py
import requests, csv
for cred in credential_groups:
    token = oauth(cred)
    r = requests.get(f"{MOSAIC_BASE}/api/v1/orders",
                     params={"filter[business_date]": today, "page[size]": 1},
                     headers={"Authorization": f"Bearer {token}"})
    print(cred["group_name"], r.status_code, dict(r.headers))
```

Record any `X-RateLimit-*`, `Retry-After`, or `X-Request-Id` headers. If Mosaic emits explicit rate-limit headers, the Phase 2 monitoring thresholds must respect them.

**MUST_MODIFY:** `scripts/s197_measure_mosaic_headroom.py` (new, one-off)
**MUST_MODIFY:** `output/s197/baseline.md` (append rate-limit findings section)
**MUST_CONTAIN:** At least one line per credential group with `status` and `headers` keys

---

## Phase 1: New 5-Minute Workflow (10 units)

### T1.1 Create `pos-sync-5min.yml` workflow file (4 units)

**File:** `.github/workflows/pos-sync-5min.yml`

Target spec:
```yaml
name: POS Sync (5-Minute Interval)
on:
  schedule:
    - cron: "*/5 * * * *"  # every 5 minutes, 24/7
  workflow_dispatch:
    inputs:
      dry_run:
        description: "Preview only — log plan, skip sync"
        required: false
        type: boolean
        default: false

concurrency:
  group: pos-sync-5min
  cancel-in-progress: true  # slow run yields to newer trigger

env:
  SUPABASE_URL: "https://csnniykjrychgajfrgua.supabase.co"
  SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
  SUPABASE_MGMT_TOKEN: ${{ secrets.SUPABASE_MGMT_TOKEN }}
  MOSAIC_CREDS_CSV: ${{ secrets.MOSAIC_CREDS_CSV }}

jobs:
  sync:
    runs-on: ubuntu-latest
    timeout-minutes: 4  # hard cap below 5-min cadence; next run starts if we're late
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install httpx
      - name: Setup Mosaic credentials
        run: |
          mkdir -p data/POS_Extraction
          echo "${{ secrets.MOSAIC_CREDS_CSV }}" | base64 -d > data/POS_Extraction/MOSAIC_POS_API_KEYS.csv
      - name: Compute today in PHT
        id: today
        run: |
          echo "date=$(TZ=Asia/Manila date '+%Y-%m-%d')" >> "$GITHUB_OUTPUT"
      - name: Dry run check
        if: ${{ inputs.dry_run == true }}
        run: |
          echo "DRY RUN: would sync date=${{ steps.today.outputs.date }} parallel=true"
          exit 0
      - name: Sync today's POS orders
        run: |
          python scripts/sync_pos_to_supabase.py \
            --from "${{ steps.today.outputs.date }}" \
            --to   "${{ steps.today.outputs.date }}" \
            --parallel
```

**HARD BLOCKER:** `timeout-minutes: 4` MUST be < 5 min (the cron interval). If the job hangs, GitHub cancels it so the next scheduled run starts clean. Raising this to 5+ minutes re-creates the queue-clog problem.

**HARD BLOCKER:** `cancel-in-progress: true`. Changing to `false` causes the queue-build failure mode described in the Design Rationale.

**HARD BLOCKER:** Do NOT add `--refresh-views`, `--store-raw`, or verification/anomaly steps. Those belong on the nightly `daily-pos-sync.yml` (kept). The 5-min workflow is single-purpose.

**MUST_MODIFY:** `.github/workflows/pos-sync-5min.yml` (new file)
**MUST_CONTAIN:** `cron: "*/5 * * * *"`
**MUST_CONTAIN:** `cancel-in-progress: true`
**MUST_CONTAIN:** `timeout-minutes: 4`
**MUST_CONTAIN:** `--parallel` flag (12 credential groups in parallel; serial mode exceeds 4-min budget)
**MUST_CONTAIN:** `TZ=Asia/Manila date` (PHT business-date computation)

### T1.2 Verify the new workflow YAML against GitHub Actions syntax (1 unit)

Run actionlint or equivalent validation locally:

```bash
npx -y @rhysd/actionlint .github/workflows/pos-sync-5min.yml
```

Fix any reported issues. **MUST_CONTAIN:** zero actionlint errors at commit time.

### T1.3 Dispatch a one-off `workflow_dispatch` test with `dry_run=true` (2 units)

After PR is merged (or via the branch's `workflow_dispatch` button post-commit), dispatch once with `dry_run=true` to confirm the plumbing works without hitting Mosaic.

Expected output: `DRY RUN: would sync date=2026-04-15 parallel=true` then exit 0.

Record the run URL in `output/s197/dispatch_dryrun.md`.

**MUST_MODIFY:** `output/s197/dispatch_dryrun.md` with the GH Actions run URL + `conclusion: success`.

### T1.4 Add Sentry instrumentation to the sync script (skip — no new whitelist endpoint) (0 units)

This sprint does NOT add a `@frappe.whitelist()` endpoint. The Frappe Sentry rule (DM-7) applies only to whitelist endpoints. No instrumentation task required. Noted for audit traceability.

### T1.5 Update the Mosaic webhook registration reconciler docs (skip — unrelated) (0 units)

S189's `s189-webhook-registration-reconciler.yml` is unrelated to the poll path. No change needed.

### T1.6 Parametric audit: what's the actual 5-min run duration? (3 units)

After 24 hours of 5-min runs, query GH Actions for `pos-sync-5min.yml` durations and compute:
- p50, p95, p99 run duration
- % of runs that were cancelled by `cancel-in-progress`
- % of runs that exceeded 4-min timeout

If p95 > 4 minutes, the script is too slow at 5-min cadence — go to Phase 2 T2.3 (tune `--parallel` batch size or switch to `--stores` subset rotation).

```bash
GH_TOKEN="" gh run list --repo Bebang-Enterprise-Inc/hrms \
  --workflow pos-sync-5min.yml --limit 288 \
  --json createdAt,conclusion,updatedAt
```

**MUST_MODIFY:** `output/s197/duration_audit.md` with p50/p95/p99 stats

---

## Phase 2: Monitoring + Rollback Hardening (7 units)

### T2.1 Add a "5-min freshness" signal to the Supabase health check (2 units)

Extend `scripts/s189_webhook_health_monitor.py` (already runs hourly) with one new check:

```python
def check_pos_sync_freshness(token) -> dict:
    """POS sync 5-min health: newest pos_orders row must be within last 10 min."""
    rows = sql("SELECT MAX(updated_at) AS latest FROM pos_orders", token)
    latest = rows[0].get("latest") if rows else None
    if not latest:
        return {"check": "pos_sync_freshness", "status": "NO_DATA"}
    from datetime import datetime, timezone
    lag_min = (datetime.now(timezone.utc) - datetime.fromisoformat(latest.replace("Z","+00:00"))).total_seconds() / 60
    status = "PASS" if lag_min <= 10 else "WARN" if lag_min <= 30 else "FAIL"
    return {"check": "pos_sync_freshness", "status": status,
            "lag_minutes": round(lag_min, 1), "latest_updated_at": latest}
```

Insert into the existing `main()` check list. The hourly health monitor workflow will pick it up automatically — no new cron needed.

**MUST_MODIFY:** `scripts/s189_webhook_health_monitor.py`
**MUST_CONTAIN:** `check_pos_sync_freshness` function
**MUST_CONTAIN:** integration into `main()` — grep for `check_pos_sync_freshness` finds exactly 2 matches (definition + usage)

### T2.2 Document the rollback procedure (2 units)

**File:** `docs/runbooks/S197_POS_SYNC_5MIN_ROLLBACK.md`

Contents:
- **Symptom:** Mosaic 429s spike, Supabase upsert error rate > 5%, or `pos_sync_freshness` FAIL for > 2 consecutive checks.
- **Immediate action:** disable the workflow via GitHub UI: `Actions → POS Sync (5-Minute Interval) → ••• → Disable workflow`. The hourly `daily-pos-sync.yml` keeps running, so data loss risk is bounded to 1 hour.
- **Permanent rollback:** create a new branch (`fix/s197-rollback`), delete `.github/workflows/pos-sync-5min.yml`, PR + merge.
- **Partial rollback (throttle):** change cron from `*/5 * * * *` to `*/10 * * * *` or `*/15 * * * *`. Push to the same `s197-pos-sync-5min-interval` branch ONLY if it's not yet merged; otherwise new branch per the BEI "every fix = new branch" rule.

**MUST_MODIFY:** `docs/runbooks/S197_POS_SYNC_5MIN_ROLLBACK.md` (new file)
**MUST_CONTAIN:** the three rollback paths labeled "Immediate action", "Permanent rollback", "Partial rollback (throttle)"

### T2.3 Observability wire-up: run-level metrics to Sentry (3 units)

Extend `scripts/sync_pos_to_supabase.py` ONLY if Phase 0 T0.2 found Mosaic rate-limit headers. Otherwise skip.

If needed:
```python
# At top of sync loop
try:
    import sentry_sdk
    sentry_sdk.set_tag("sync.cadence", "5min")
    sentry_sdk.set_tag("sync.date", today_str)
except ImportError:
    pass
```

And capture HTTP 429/5xx from Mosaic as Sentry breadcrumbs.

**HARD BLOCKER:** Only apply this if T0.2 found rate-limit headers worth tracking. Otherwise the instrumentation adds noise without signal. Document the decision in `output/s197/baseline.md` (§"Observability decision").

---

## Phase 3: L3 Workflow Scenarios + Closeout (5 units)

### T3.1 L3 scenarios (see L3 Workflow Scenarios section below) (3 units)

Execute the 5 scenarios in the L3 table. Record evidence in `output/l3/s197/`.

### T3.2 Sprint closeout (2 units)

1. Update this plan's YAML frontmatter:
   - `status: PLANNED` → `status: COMPLETED`
   - `completed_date: <YYYY-MM-DD>`
   - `execution_summary: <one-paragraph summary of actual outcomes vs plan>`
2. Update `docs/plans/SPRINT_REGISTRY.md` row:
   - Status: `PLANNED` → `DEPLOYED` (after merge) → `COMPLETED` (after L3 evidence committed)
   - Fill in hrms PR number
3. Commit both with `git add -f docs/plans/2026-04-15-sprint-197-pos-sync-5min-interval.md docs/plans/SPRINT_REGISTRY.md output/l3/s197/`
4. Push to the reserved branch; create closeout PR.

**MUST_MODIFY:** `docs/plans/2026-04-15-sprint-197-pos-sync-5min-interval.md` (status + completed_date + execution_summary)
**MUST_MODIFY:** `docs/plans/SPRINT_REGISTRY.md` (S197 row status)
**MUST_CONTAIN (plan YAML):** `status: COMPLETED` (replaces PLANNED)

---

## L3 Workflow Scenarios

| # | User / Actor | Action | Expected Outcome | Failure Means |
|---|-----|--------|-------------------|---------------|
| L3-1 | GH Actions scheduler | `pos-sync-5min.yml` cron fires at a :*5 boundary | Workflow starts within 60 seconds, completes with `conclusion=success`, runtime < 4 min | Cron malformed OR `--parallel` slower than cadence |
| L3-2 | Sam (workflow_dispatch) | Dispatch with `dry_run=true` | Workflow logs `DRY RUN: would sync date=<today> parallel=true`, exits 0, does not touch Supabase or Mosaic | `dry_run` gate not wired |
| L3-3 | Script (end-to-end) | First real run at cadence | `MAX(pos_orders.updated_at) ≥ now - 10 min`; no `pos_sync_freshness FAIL` in next hourly health monitor run | Sync not actually writing to Supabase |
| L3-4 | Two concurrent runs | Trigger a second run via `workflow_dispatch` while a scheduled run is already live | GitHub cancels the in-flight run; only the newer one completes. No duplicate rows in pos_orders (merge-duplicates upsert) | `cancel-in-progress: true` not set OR upsert not idempotent |
| L3-5 | Rollback rehearsal | Follow `docs/runbooks/S197_POS_SYNC_5MIN_ROLLBACK.md` "Immediate action" | Workflow shows disabled in Actions UI; next scheduled trigger does not run; hourly `daily-pos-sync.yml` continues | Runbook steps wrong OR workflow can't be disabled via UI |

Evidence contract:
- `output/l3/s197/form_submissions.json` — one entry per scenario with the exact inputs and timestamps
- `output/l3/s197/api_mutations.json` — for L3-3 and L3-4, capture the pos_orders row counts before/after with `updated_at` ranges
- `output/l3/s197/state_verification.json` — for L3-4, the GH Actions API response showing which run was cancelled and which completed
- `output/l3/s197/screenshots/` — L3-5 screenshot of the Disable UI action

**Separate-session recommendation:** At 26 units total, this plan is well under the 40-unit threshold. L3 can run in the same session as execution.

---

## Summary Table

| Phase | Units | Description |
|------:|------:|-------------|
| Phase 0: Baseline audit | 4 | Current sync duration, Mosaic rate-limit headroom |
| Phase 1: New 5-min workflow | 10 | Create `pos-sync-5min.yml`, dispatch test, p95 duration audit |
| Phase 2: Monitoring + rollback | 7 | Freshness check extension, rollback runbook, conditional Sentry wire-up |
| Phase 3: L3 + closeout | 5 | 5 scenarios + plan/registry update |
| **TOTAL** | **26** | Single session, single repo (hrms), no frontend |

---

## Requirements Regression Checklist

The executing agent MUST verify every item before claiming COMPLETED:

- [ ] Is the new workflow file at `.github/workflows/pos-sync-5min.yml` (new, NOT an edit of `daily-pos-sync.yml`)?
- [ ] Is the cron `*/5 * * * *` (every 5 min, 24/7)?
- [ ] Is `concurrency.cancel-in-progress: true`?
- [ ] Is `timeout-minutes: 4` (strictly less than the 5-min cron interval)?
- [ ] Does the workflow call `sync_pos_to_supabase.py --from <today-PHT> --to <today-PHT> --parallel` and nothing else (no `--refresh-views`, no `--store-raw`)?
- [ ] Is today's PHT date computed via `TZ=Asia/Manila date`, not UTC?
- [ ] Is `daily-pos-sync.yml` LEFT UNTOUCHED (still runs hourly 10 AM–midnight PHT + nightly verify)?
- [ ] Is `scripts/sync_pos_to_supabase.py` LEFT UNTOUCHED unless Phase 0 T0.2 required observability additions?
- [ ] Is the freshness check added to `scripts/s189_webhook_health_monitor.py` (extension, not new monitor)?
- [ ] Is the rollback runbook at `docs/runbooks/S197_POS_SYNC_5MIN_ROLLBACK.md`?
- [ ] Are L3 evidence files committed to `output/l3/s197/` with `git add -f`?
- [ ] Has this plan's YAML status been updated to COMPLETED with a completed_date?
- [ ] Has the SPRINT_REGISTRY row been updated with the hrms PR number?

---

## Ground-Truth Lock

- **evidence_sources:**
  - `.github/workflows/daily-pos-sync.yml` → proves current hourly schedule `0 2-16 * * *` + nightly verify `30 16 * * *`
  - `scripts/sync_pos_to_supabase.py` lines 665–698 → proves supported CLI flags (`--daily`, `--from`, `--to`, `--store`, `--store-raw`, `--refresh-views`, `--parallel`)
  - `docs/api/MOSAIC_API_OPENAPI_2026-04-14.json` → proves Mosaic has no documented rate-limit scheme
  - Superadmin `bebang-multistore-dashboard/routes/console.php` line 18 → proves sibling app polls `everyFiveMinutes()->withoutOverlapping()` as prior art
  - `docs/runbooks/S189_BOM_CONSUMPTION.md` → proves S189 triggers consume `pos_order_items` directly, so sync cadence = consumption freshness
- **count_method:** work units estimated per task, sum = 26. Unit ceiling 80 per S089 — well under.
- **authoritative_sections:** Phase 0/1/2/3 tables + Requirements Regression Checklist are authoritative. Design Rationale is context only.
- **unresolved_value_policy:** If T0.2 surfaces Mosaic rate-limit headers, the exact values become HARD BLOCKER constraints in Phase 2 T2.3. Until measured: `[UNVERIFIED — see Phase 0 T0.2]`.
- **normalization_artifacts:** `output/s197/baseline.md` is the normalization artifact — all claims about baseline behavior are derived from it.

---

## Anti-Rewind Protection

- **Surface ownership:**
  - `.github/workflows/pos-sync-5min.yml` — OWNED by S197 (new file)
  - `.github/workflows/daily-pos-sync.yml` — PROTECTED, do not modify
  - `scripts/sync_pos_to_supabase.py` — PROTECTED (skip unless T0.2 demands it)
  - `scripts/s189_webhook_health_monitor.py` — SHARED with S189; S197 adds one function, does not remove any
- **Remote truth baseline:** `origin/production` at the time of branch creation. Record the SHA in the first commit message.
- **Protected adjacent surfaces:** S189 consumption pipeline (Supabase triggers, fn_material_dtl, migrations) — DO NOT touch. S195 delivery schedule — unrelated.
- **Rebase-before-merge rule:** per CLAUDE.md + S161 incident. If `origin/production` advanced after branch creation, rebase and rerun the p95 audit before merge.

---

## Autonomous Execution Contract

- **completion_condition:**
  - `.github/workflows/pos-sync-5min.yml` merged to production
  - At least 24 consecutive successful scheduled runs (confirmed via `gh run list`)
  - `output/s197/baseline.md` + `output/s197/duration_audit.md` + `output/l3/s197/*.json` all present
  - This plan's YAML: `status: COMPLETED` with `completed_date` and `execution_summary`
  - `SPRINT_REGISTRY.md` row updated with hrms PR #
  - 5 L3 scenarios with evidence files
- **stop_only_for:**
  - Mosaic returns HTTP 429 during Phase 0 T0.2 (rate limit detected → pause + escalate to Sam)
  - Supabase upsert error rate > 5% in Phase 1 T1.6 measurement (indicates DB-side bottleneck → pause + escalate)
  - `daily-pos-sync.yml` goes red due to our changes (shared state → pause + fix)
  - GitHub Actions concurrency policy behavior differs from documented (requires human confirmation of workaround)
- **continue_without_pause_through:** phase 0 → phase 1 → phase 2 → phase 3 → closeout
- **blocker_policy:**
  - `programmatic` (YAML lint fail, cron syntax wrong) → fix and continue
  - `environment` (GH Actions UI change) → research, continue
  - `business-data/policy` (Mosaic rate limits discovered) → pause per stop_only_for
- **signoff_authority:** `single-owner` (Sam)
- **canonical_closeout_artifacts:**
  - `.github/workflows/pos-sync-5min.yml`
  - `docs/runbooks/S197_POS_SYNC_5MIN_ROLLBACK.md`
  - `scripts/s189_webhook_health_monitor.py` (extended, not replaced)
  - `output/s197/baseline.md`
  - `output/s197/duration_audit.md`
  - `output/l3/s197/form_submissions.json`
  - `output/l3/s197/api_mutations.json`
  - `output/l3/s197/state_verification.json`
  - This plan file (`status: COMPLETED`)
  - `docs/plans/SPRINT_REGISTRY.md` (S197 row updated)

---

## Zero-Skip Enforcement

**Every task MUST be implemented. No exceptions.** If a task cannot be completed, the agent STOPS and asks Sam.

### Forbidden agent behaviors

- Marking T1.6 as DONE without the p95/p99 numbers actually computed (prose description does not count)
- Skipping the `cancel-in-progress: true` setting because "it's probably fine"
- Increasing `timeout-minutes` above 4 to "give runs more headroom" (that creates the queue-clog problem)
- Adding `--refresh-views` to the 5-min workflow (that defeats the purpose of a lean cadence)
- Editing `daily-pos-sync.yml` (different sprint's surface)
- Editing `scripts/sync_pos_to_supabase.py` unless Phase 0 T0.2 explicitly required it
- Skipping the Phase 0 baseline because "we'll measure later" (we need before/after comparison)

### Verification script (machine-checkable)

Create `output/s197/verify_phase_1.py`:

```python
"""Post-Phase-1 verification — filesystem evidence only."""
import subprocess, re, sys
from pathlib import Path

checks = []

# 1. New workflow exists
p = Path(".github/workflows/pos-sync-5min.yml")
checks.append(("workflow file exists", p.exists()))

if p.exists():
    text = p.read_text(encoding="utf-8")
    checks.append(("cron is */5 * * * *", 'cron: "*/5 * * * *"' in text or "cron: '*/5 * * * *'" in text))
    checks.append(("cancel-in-progress: true", "cancel-in-progress: true" in text))
    checks.append(("timeout-minutes: 4", "timeout-minutes: 4" in text))
    checks.append(("--parallel flag", "--parallel" in text))
    checks.append(("TZ=Asia/Manila", "TZ=Asia/Manila" in text))
    checks.append(("no --refresh-views", "--refresh-views" not in text))
    checks.append(("no --store-raw", "--store-raw" not in text))

# 2. daily-pos-sync.yml UNTOUCHED
r = subprocess.run(["git", "diff", "origin/production", "--name-only",
                    ".github/workflows/daily-pos-sync.yml"],
                   capture_output=True, text=True,
                   creationflags=0x08000000 if sys.platform == "win32" else 0)
checks.append(("daily-pos-sync.yml NOT modified", r.stdout.strip() == ""))

# 3. sync_pos_to_supabase.py UNTOUCHED (unless Phase 0 T0.2 explicitly required)
r = subprocess.run(["git", "diff", "origin/production", "--name-only",
                    "scripts/sync_pos_to_supabase.py"],
                   capture_output=True, text=True,
                   creationflags=0x08000000 if sys.platform == "win32" else 0)
# Allow modification ONLY if observability_decision says so
decision_path = Path("output/s197/baseline.md")
allowed = False
if decision_path.exists() and "Observability decision: MODIFY" in decision_path.read_text(encoding="utf-8"):
    allowed = True
if not allowed:
    checks.append(("sync_pos_to_supabase.py NOT modified unless justified", r.stdout.strip() == ""))

# 4. Rollback runbook exists
rb = Path("docs/runbooks/S197_POS_SYNC_5MIN_ROLLBACK.md")
checks.append(("rollback runbook exists", rb.exists()))

failures = [name for name, ok in checks if not ok]
for name, ok in checks:
    print(f"  [{'OK' if ok else 'FAIL'}] {name}")
if failures:
    print(f"\nFAIL: {len(failures)} check(s) failed")
    sys.exit(1)
print("\nAll checks PASS")
```

The agent MUST run this script at the end of Phase 2 and commit its output to `output/s197/verify_phase_1.txt`. A FAIL aborts progress to Phase 3.

---

## Agent Boot Sequence

1. **Read this plan fully.** All 26 units — do not skim.
2. **Create sprint branch:**
   ```bash
   cd F:/Dropbox/Projects/BEI-ERP
   git fetch origin production
   git checkout -b s197-pos-sync-5min-interval origin/production
   ```
   NEVER commit to `production`.
3. **Read `docs/plans/SPRINT_REGISTRY.md`** — confirm the S197 row exists and no other agent has claimed `s197-pos-sync-5min-interval`.
4. **Read `.github/workflows/daily-pos-sync.yml` in full** before writing the new workflow — match its secret handling and checkout style so secrets map 1:1.
5. **Read `scripts/sync_pos_to_supabase.py` lines 660–698** to confirm CLI flags before calling the script.
6. **Doppler check:** `doppler secrets --project bei-erp --config dev | grep -iE "MOSAIC_CREDS|SUPABASE_(URL|SERVICE|MGMT)"` — confirm secrets present (no need to fetch them; the workflow uses GitHub secrets directly).
7. **Execute phases 0 → 1 → 2 → 3 sequentially.** Do not reorder.
8. **At end of each phase, run the verification script.** A FAIL blocks the next phase.
9. **Create PR to `Bebang-Enterprise-Inc/hrms` with base `production`** after Phase 2 completes. Phase 3 (L3 + closeout) can run either before or after PR merge — agent's call, but evidence must be committed to the same branch.

---

## Execution Authority

This sprint is intended for **autonomous end-to-end execution** by a single agent in a single session. Do not stop for progress-only updates. Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

---

## Failure Response

- **Mode A (Mosaic-side bug):** If Mosaic 429s or 5xxs spike during Phase 0 T0.2, file findings in `output/s197/mosaic_issue.md` and escalate to Sam. Do NOT modify our code to work around a Mosaic outage.
- **Mode B (workflow bug):** If the new workflow fails its own lint/dispatch test, fix the YAML in the same branch, re-push, re-dispatch.
- **Mode C (brittleness/flakiness):** If p95 duration trends toward 4 minutes over the first 24h, go to Phase 2 T2.3 (tune the library: smaller batch size, fewer stores per run, subset rotation). Never raise `timeout-minutes` past 4 — that re-creates the queue-clog bug.

---

## Signoff Model

- **mode:** `single-owner`
- **approver_of_record:** Sam Karazi (CEO)
- **signoff_artifact:** merged hrms PR + this plan's `status: COMPLETED`
- **note:** Single-owner operating model. No synthetic department signoff.
