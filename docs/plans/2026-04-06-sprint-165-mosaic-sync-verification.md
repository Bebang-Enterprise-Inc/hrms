---
canonical_sprint_id: S165
display: Sprint 165
status: PR_CREATED
branch: s165-mosaic-sync-verification
lane: single
created_date: 2026-04-06
completed_date:
deployed_at:
backend_pr: 466
frontend_pr:
l3_result: T4.1-T4.4 PASS, T5.1-T5.2 PASS, verify_s165.py all PASS
execution_summary: >
  Verify script + sync_verification table + hourly cron + nightly verify job.
  Apr 2-3 backfilled (Holy Week low counts are legitimate).
  PR #466 ready for merge.
depends_on:
---

# S165 — Mosaic POS Sync Verification + Hourly Sync Schedule

**Goal:** Prevent silent Mosaic sync failures by (1) verifying every store-day against Mosaic's own `meta.total` count nightly, auto-healing discrepancies, and alerting once a day after midnight; and (2) switching the sync schedule from twice daily to hourly from 10 AM–midnight PHT for near-real-time dashboards.

**Origin:** The Apr 5 weekend sales report exposed that Apr 5 POS data had only 610 orders synced instead of ~10K. Root cause was a `sync_progress` CHECK constraint rejecting the `partial` status used for today's date, combined with threads silently skipping work after exceptions. The partial sync was then marked `complete`, locking in bad data. Without Sam's manual review, the business would have operated on silently-wrong sales data for days. Apr 2 (3,263) and Apr 3 (2,321) POS order counts are still suspiciously low and likely affected by the same bug.

**Source of truth:** Mosaic POS API is now the only source of truth for all channels (POS walk-in, FoodPanda, GrabFood — and Website soon). There is no independent cross-check possible. The only reliable verification signal is calling Mosaic directly and comparing its count against Supabase.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

The detect_anomalies.py script at `scripts/detect_anomalies.py` catches **statistical outliers** (a store with 0 orders vs its P10 baseline) but cannot distinguish:

- **Real zero** — store closed, no sales
- **Sync failure** — Mosaic has the data but our sync missed it
- **Partial sync** — our sync pulled some but not all orders

The Apr 5 incident was only caught because Sam manually questioned the numbers during the weekend sales report. Without human review, broken data would have persisted silently.

**Incident timeline (2026-04-06):**
- Apr 5 midnight sync (`run 24005949243` at 16:46 UTC) ran `--daily` with date range `2026-04-05 to 2026-04-06`
- Constraint violation on `sync_progress_status_check` blocked every `"partial"` write for Apr 6 across all stores
- Apr 5 partial data got marked as `complete` for some stores (~610 orders), then subsequent runs skipped Apr 5 because `get_completed_store_days()` returned it as complete
- The workflow showed status "failure" due to the anomaly-detection step (missing `hrms` module), but POS and Web sync jobs reported "success" despite the silent data loss

The CEO's directive: "Make sure it will not fail again."

### Why this architecture

**Ground-truth verification, not cross-channel:** Because FoodPanda orders already flow through Mosaic (since Mar 25, 2026 via `pos_orders.channel`) and Website orders are migrating next, there is no independent data source to cross-check against. The only reliable verification is calling Mosaic itself and asking "how many orders do you have for this store-day?" then comparing against our database.

**Mosaic has `meta.total` in every page response** — confirmed in `docs/api/MOSAIC_API.md:103`:
```json
"meta": { "current_page": 1, "last_page": 1, "total": 2 }
```

A single `GET /api/v1/orders?filter[location_id]=X&filter[business_date]=Y&page[size]=1` call returns `meta.total` without having to paginate through any orders. This makes verification extremely cheap: 45 stores × 7 days = 315 calls per nightly run.

**Auto-heal by default:** Most sync gaps are transient (Mosaic API hiccup, rate limit, aborted thread). Re-calling `sync_store_day()` for a specific location+date is idempotent (the existing upsert on `pos_orders.id` handles duplicates safely). Auto-heal silently resolves most issues; only truly stuck ones escalate to Chat alerts.

**Once-a-day batched alerts:** Per CEO preference, alerts should NOT fire per-hour during the day. The verification runs once at 00:30 PHT after all hourly syncs complete and sends a single consolidated Chat message listing any unresolved discrepancies.

**Hourly sync from 10 AM – midnight PHT:** Current twice-daily sync leaves dashboards stale for most of the operating window. The CEO wants near-real-time visibility. The existing `--daily` logic already handles incremental re-sync correctly (completed store-days are skipped via `get_completed_store_days()`, in-progress days get re-fetched). No changes to the sync script are required — only the cron schedule.

### Key trade-off decisions

1. **Standalone script vs integrated `--verify` flag on sync script** — Chose standalone `scripts/verify_mosaic_pos_sync.py`. Cleaner separation, easier to run ad-hoc for debugging, separate GH Actions job with its own retry/timeout behavior. Slight cost: must import functions from `sync_pos_to_supabase.py`.

2. **Verification window: 1 day vs 7 days vs 14 days** — Chose **7 days rolling**. Catches silent drift across a week while keeping costs low (315 Mosaic calls, ~60 seconds wall time). 14 days was considered but offers diminishing returns — by that point operators have typically noticed issues via dashboards.

3. **Auto-heal vs alert-only** — Chose **auto-heal + alert if still broken**. Most transient failures self-heal silently in one re-sync attempt. Only persistent mismatches escalate to Chat, keeping signal-to-noise high.

4. **Total count vs paid-only count** — Chose **total row count** (no `payment_status` filter) because Mosaic's `meta.total` includes all orders regardless of payment state. Comparing paid-only would require paginating through Mosaic to filter, defeating the cheap-call benefit. A gross row-count mismatch is the correct signal; payment state drift is caught by finance reconciliation elsewhere.

5. **Alert destination** — Chose the existing anomaly-detection Chat space `spaces/AAQA3NVVR6c`. All sync-related alerts in one place, operators already monitor it, no new space to configure.

6. **Verification cadence: hourly vs once nightly** — Chose **once nightly at 00:30 PHT**. Hourly verification would flag today's in-progress orders as "missing" (Mosaic register-to-API propagation takes a few minutes), causing false positives. The authoritative time to verify is after the day closes and all hourly syncs have completed.

7. **Workflow job placement** — Parallel with `anomaly-detection`, both depending on `refresh-sales-dashboard-views`. They are independent consumers of refreshed data. Verification cannot block anomaly detection because the two solve different problems.

### Known limitations

- **`fetch_all_orders()` at `scripts/sync_pos_to_supabase.py:354`** — not used here; we call Mosaic directly with `page[size]=1`. Reference only.
- **`sync_store_day()` at `scripts/sync_pos_to_supabase.py:499`** — called for auto-heal. HARD BLOCKER: must clear `sync_progress` row first so it re-runs instead of skipping.
- **`get_completed_store_days()` at `scripts/sync_pos_to_supabase.py:241`** — filters by `status = 'complete'`. The auto-heal path must delete or update the existing row before calling sync_store_day.
- **Rate limiting (1.2s per call, per credential group)** — applies to verification calls too. 45 stores / 12 credential groups ≈ 4 stores/group × 7 days = 28 calls per group ≈ 34 seconds per group. Parallelize across groups to stay under 1 minute total.
- **Token refresh** — `ensure_token()` caches for 55 minutes. The verify script uses the same pattern, so tokens won't expire mid-run.
- **`sync_progress_status_check` constraint** — The constraint was already updated in a prior session to allow `'partial'` status. It currently allows: `pending`, `in_progress`, `complete`, `partial`, `error`. Verified via direct query against Supabase on 2026-04-06.

### Source references

- Mosaic API schema: `docs/api/MOSAIC_API.md:55-103` (confirms `meta.total` presence)
- Sync script: `scripts/sync_pos_to_supabase.py`
- Anomaly detection pattern: `scripts/detect_anomalies.py:360-387` (Google Chat send)
- Credentials CSV: `data/POS_Extraction/MOSAIC_POS_API_KEYS.csv` (12 credential groups, 45 stores)
- Sentry observability rule: `.claude/rules/sentry-observability.md` (DM-7)
- Apr 5 incident log: `run 24005949243` (GitHub Actions run ID for the failed midnight sync)
- Current Supabase order counts by date (verified 2026-04-06):
  - Apr 2: 3,263 (suspected incomplete)
  - Apr 3: 2,321 (suspected incomplete)
  - Apr 4: 9,710 (complete)
  - Apr 5: 10,606 (healed via manual re-sync)

---

## Ground-Truth Lock

- **evidence_sources:**
  - `scripts/sync_pos_to_supabase.py` → proves reusable function signatures and rate-limit semantics
  - `scripts/detect_anomalies.py` → proves Google Chat send pattern and Chat space ID
  - `docs/api/MOSAIC_API.md` → proves Mosaic `meta.total` field presence
  - `data/POS_Extraction/MOSAIC_POS_API_KEYS.csv` → proves 45 stores × 12 credential groups
  - `.github/workflows/daily-pos-sync.yml` → proves current job structure and secrets
- **count_method:**
  - metric: `orders per store per day`
  - basis: `Mosaic meta.total (from page[size]=1 call) vs SELECT COUNT(*) FROM pos_orders`
  - method: `single HTTP call per store-day + single SQL COUNT query per store-day`
- **authoritative_sections:** Sections "Files to Create", "Files to Modify", "L3 Workflow Scenarios", and "Verification" are authoritative for execution. Amendment history is traceability only.
- **normalization_required:** If any task changes counts, paths, or store IDs, update all authoritative sections in the same edit.
- **unresolved_value_policy:** Any uncertain value becomes `[UNVERIFIED — requires resolution]`; no best-guess in operator-facing output.

---

## Phase Budget Contract

| Phase | Description | Units |
|-------|-------------|-------|
| Phase 0 | Pre-flight audit (constraint, filter probe, cancellation probe, Sentry DSN, env check) | 5 |
| Phase 1 | Create `sync_verification` table + migration | 2 |
| Phase 2 | Build `scripts/verify_mosaic_pos_sync.py` (13 tasks) | 10 |
| Phase 3 | Update `.github/workflows/daily-pos-sync.yml` (concurrency, cron, gating, CB1 fixes) | 6 |
| Phase 4 | L3 verification (unit, heal path, full nightly, Chat, backup/restore, skip test) | 8 |
| Phase 5 | Backfill Apr 2-3 via verification run | 2 |
| Phase 6 | Closeout (verify script, git add explicit, PR, registry, plan status) | 5 |
| **Total** | | **38** |

Hard limit 15 per phase respected. Total 38 units — still well under 80-unit plan ceiling. Increased from 28 after applying audit amendments (5 CRITICAL + 4 HIGH WARNING + 10 MEDIUM WARNING) — no features deferred, no scope cut.

---

## Requirements Regression Checklist

Before writing any code, the executing agent MUST verify every item below:

### Script structure
- [ ] Is the new script created at `scripts/verify_mosaic_pos_sync.py` (not in `scripts/verify_mosaic/` or elsewhere)?
- [ ] Does the script use `import sync_pos_to_supabase as sps` (NOT `from sync_pos_to_supabase import ...`) so module globals can be mutated? See CB3.
- [ ] Does it import `MOSAIC_ORDERS_URL`, `REQUEST_INTERVAL`, `MAX_RETRIES`, `RATE_LIMIT_WAIT`, `RETRY_WAIT`, `fetch_orders_page` from the aliased module (in addition to `load_credentials`, `ensure_token`, `sync_store_day`, `set_sync_progress`)?
- [ ] **CB3 — Does the verify script set `sps.SUPABASE_KEY` and `sps.SUPABASE_MGMT_TOKEN` on the imported module BEFORE calling any function that touches Supabase?** Empty globals produce 401 on every heal.
- [ ] **MW1 — Does the verify script reinstall its own SIGINT handler after import** (because `sync_pos_to_supabase.py:102` registers one at import time)?

### Mosaic API usage
- [ ] Does the verification call use `page[size]=1` to get only `meta.total` (not paginate through orders)?
- [ ] **MW2 — Does `fetch_mosaic_count` reuse the full retry/429/5xx loop from `fetch_orders_page` (sync_pos_to_supabase.py:310-351)** or faithfully copy its retry logic (3 retries, 65s wait on 429, 10s wait on 5xx)?
- [ ] **MW10 — Is there a one-line comment referencing `sync_pos_to_supabase.py:315` as the known-working precedent for httpx bracket-encoded `filter[location_id]` params?**
- [ ] Does the script send ONE consolidated Chat alert at the end, NOT per-discrepancy alerts?
- [ ] Does the Chat alert go to `spaces/AAQA3NVVR6c` (same as anomaly detection)?

### Date windowing
- [ ] **HW4 — Does the default verification window END at YESTERDAY (PHT), not today?** `end_date = datetime.now(PHT).date() - timedelta(days=1)`. A midnight run must not verify the day that just started.
- [ ] Does the default verification window cover 7 days (`start_date = end_date - timedelta(days=6)`)?

### Auto-heal
- [ ] **HW2 — Does auto-heal call `set_sync_progress(..., status='pending')` BEFORE `sync_store_day()` (NOT DELETE the row)?** `sync_store_day()` does not consult `sync_progress`, so DELETE is unnecessary — the pending marker is for audit trail only.
- [ ] Is every write to `sync_verification.status` one of: `ok`, `missing`, `extra`, `healed`, `unresolved`, `api_error`?
- [ ] Does the verification script compare **total row count** (not paid-only) to match Mosaic `meta.total` semantics?

### Observability
- [ ] **CB5 — Does the script fail-fast with `sys.exit(2)` if `SENTRY_DSN_BEI_HRMS` is missing or empty?** Silent Sentry disablement is a DM-7 violation.
- [ ] Does `sentry_sdk.init()` set `module=sync_verification`, `action=verify_mosaic_pos_sync` tags?

### Exit semantics
- [ ] **MW9 — Does the script exit 0 when discrepancies are handled (alerted) and exit non-zero ONLY on infra failure** (Mosaic unreachable, Supabase unreachable, Sentry DSN missing)? Prevents dual alerting from `notify-failure` + verify script.

### Workflow YAML
- [ ] **CB1 — Does every gating `if:` use `inputs.skip_verify != 'true'` and `inputs.skip_anomaly != 'true'`** (NOT `!inputs.skip_verify`)? GH Actions booleans are strings — the negation form silently skips on manual dispatch.
- [ ] **CB1 — Are `skip_verify` and `skip_anomaly` declared as `type: boolean, default: false` in `workflow_dispatch.inputs`?**
- [ ] **CB1 — Is the pre-existing `anomaly-detection` job gate also fixed in the same PR** (it's in the same file, currently has the same latent bug, and is explicitly in-scope since the plan touches this file)?
- [ ] **CB2 — Is there a workflow-level `concurrency: { group: daily-pos-sync, cancel-in-progress: false }` block at the top of the workflow?**
- [ ] **CB2 — Is `pos-sync.timeout-minutes` reduced from 180 → 50** so a stuck run cannot overlap the next hour?
- [ ] Does the hourly sync cron use `0 2-16 * * *` (02:00–16:00 UTC = 10 AM–midnight PHT)?
- [ ] Are `anomaly-detection` and `verify-sync` gated with `(github.event_name == 'workflow_dispatch' || github.event.schedule == '30 16 * * *')` so they DO NOT run 15 times a day on the hourly cron?
- [ ] **MW3 — Is the decision to keep `refresh-sales-dashboard-views` UNGATED (runs every hour for dashboard freshness) explicitly documented in the workflow file and in the plan?**

### L3 evidence commit
- [ ] **MW8 — Does the Phase 6 git commit include `git add -f output/l3/s165/form_submissions.json output/l3/s165/api_mutations.json output/l3/s165/state_verification.json output/l3/s165/verification_run.log output/l3/s165/verify_s165.py` explicitly** (not just `docs/plans/...`)?
- [ ] Does `git diff --name-only origin/production..HEAD` include all 5 `output/l3/s165/*` evidence files?

---

## Autonomous Execution Contract

- **completion_condition:**
  - `sync_verification` table created and populated for last 7 days across all 45 stores
  - `scripts/verify_mosaic_pos_sync.py` exists, imports work, CLI flags functional, module globals `sps.SUPABASE_KEY` / `sps.SUPABASE_MGMT_TOKEN` set explicitly before any heal call (CB3)
  - `.github/workflows/daily-pos-sync.yml` updated with: (a) hourly cron + nightly cron, (b) workflow-level `concurrency:` group (CB2), (c) `pos-sync.timeout-minutes: 50` (CB2), (d) `verify-sync` job, (e) `skip_verify` and `skip_anomaly` both using `!= 'true'` pattern (CB1), (f) `skip_verify`/`skip_anomaly` declared `type: boolean, default: false` (CB1)
  - Apr 2-3 backfilled — both dates show > 7K POS orders after the run (with SELECT pre/post captured in `state_verification.json`)
  - Sentry fail-fast check active: script exits 2 if `SENTRY_DSN_BEI_HRMS` empty (CB5)
  - Filter isolation probe confirmed: `meta.total` differs between two different `location_id` values in the same credential group (CB4)
  - L3 evidence files present in `output/l3/s165/` AND committed to branch via `git add -f` (MW8)
  - PR created, plan YAML updated to `COMPLETED`, SPRINT_REGISTRY row updated, both pushed to production
  - Verification script `output/l3/s165/verify_s165.py` passes all checks
- **stop_only_for:**
  - Mosaic API returns unexpected schema (e.g., `meta.total` missing or renamed)
  - **Phase 0 T0.2 filter-isolation probe shows identical `meta.total` for two different location_ids in the same credential group** (filter is being ignored → approach is invalid, escalate to Sam) (CB4)
  - Supabase migration SQL rejected
  - `sync_progress_status_check` constraint incompatibility (already fixed, but re-verify in T0.1)
  - `SENTRY_DSN_BEI_HRMS` secret missing from Doppler or GitHub Actions secrets (CB5)
  - Destructive approval needed (should never happen in this plan)
- **continue_without_pause_through:** audit → execute → PR creation → L3 → closeout
- **blocker_policy:**
  - programmatic → fix and continue
  - Mosaic API error → retry 3x with backoff, then skip with `api_error` status and continue
  - Constraint mismatch → STOP and present fix options
- **signoff_authority:** single-owner (Sam)
- **canonical_closeout_artifacts:**
  - `output/l3/s165/form_submissions.json`
  - `output/l3/s165/api_mutations.json`
  - `output/l3/s165/state_verification.json`
  - `output/l3/s165/verification_run.log`
  - `docs/plans/2026-04-06-sprint-165-mosaic-sync-verification.md` (status → COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (S165 row → COMPLETED with PR references)

---

## Files to Create

### 1. `scripts/verify_mosaic_pos_sync.py` (NEW, ~400 lines)

**MUST_MODIFY:** `scripts/verify_mosaic_pos_sync.py` (new file)
**MUST_CONTAIN:** `def fetch_mosaic_count(` — proves the count-only fetcher exists
**MUST_CONTAIN:** `"meta"]["total"]` — proves we parse Mosaic's count field
**MUST_CONTAIN:** `import sync_pos_to_supabase as sps` — proves we use the module-alias pattern so globals can be mutated (CB3)
**MUST_CONTAIN:** `sps.SUPABASE_KEY =` — proves we propagate the Supabase key to the imported module (CB3)
**MUST_CONTAIN:** `sps.SUPABASE_MGMT_TOKEN =` — proves we propagate the management token (CB3)
**MUST_CONTAIN:** `sync_verification` — proves we write to the new table
**MUST_CONTAIN:** `spaces/AAQA3NVVR6c` — proves we use the correct Chat space
**MUST_CONTAIN:** `sentry_sdk.init` — proves Sentry is initialized for error capture
**MUST_CONTAIN:** `sys.exit(2)` — proves fail-fast on missing Sentry DSN (CB5)
**MUST_CONTAIN:** `signal.signal(signal.SIGINT` — proves own SIGINT handler is reinstalled after import (MW1)
**MUST_CONTAIN:** `datetime.now(PHT).date() - timedelta(days=1)` — proves window ends at yesterday (HW4)
**MUST_CONTAIN:** `content-range` — proves PostgREST count=exact pattern is used (HW1)

**CLI flags (argparse):**
```
--date YYYY-MM-DD    # Specific single date (overrides --days)
--days N             # Verify last N days (default: 7, ENDING at yesterday PHT)
--store LOC_ID       # Single store (for debug)
--no-heal            # Detect but don't auto-resync
--no-chat            # Skip Chat alert
--dry-run            # Print, don't write
```

**Module import + global propagation (CB3 — HARD BLOCKER):**
```python
# HARD BLOCKER: must use `import ... as` form so the verify script can mutate
# globals on the imported module. `from sync_pos_to_supabase import sync_store_day`
# binds the function name but does NOT propagate later SUPABASE_KEY writes.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))  # add scripts/ to path

import sync_pos_to_supabase as sps
from sync_pos_to_supabase import (
    load_credentials,
    ensure_token,
    sync_store_day,
    set_sync_progress,
    fetch_orders_page,       # reused for retry/rate-limit pattern (MW2)
    MOSAIC_ORDERS_URL,       # MW4 — explicit import
    REQUEST_INTERVAL,
    MAX_RETRIES,
    RATE_LIMIT_WAIT,
    RETRY_WAIT,
    CREDENTIALS_CSV,
    SUPABASE_URL,
)

# CB3: Propagate secrets to imported module BEFORE calling any function that touches Supabase
sps.SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
sps.SUPABASE_MGMT_TOKEN = os.environ["SUPABASE_MGMT_TOKEN"]

# MW1: Reinstall own SIGINT handler (sync_pos_to_supabase.py:102 registers its own at import)
_shutdown = False
def _handle_sigint(signum, frame):
    global _shutdown
    _shutdown = True
    print("Shutdown requested — finishing current store-day then exiting.", flush=True)
signal.signal(signal.SIGINT, _handle_sigint)
```

**Sentry fail-fast (CB5):**
```python
import sentry_sdk

_sentry_dsn = os.environ.get("SENTRY_DSN_BEI_HRMS", "").strip()
if not _sentry_dsn:
    print("ERROR: SENTRY_DSN_BEI_HRMS is missing/empty — refusing to run without observability.", file=sys.stderr)
    sys.exit(2)  # CB5: observability sprint cannot silently disable observability

sentry_sdk.init(
    dsn=_sentry_dsn,
    environment="production",
    release="s165-mosaic-sync-verification",
    traces_sample_rate=0.0,
    server_name="verify_mosaic_pos_sync",
)
sentry_sdk.set_tag("module", "sync_verification")
sentry_sdk.set_tag("action", "verify_mosaic_pos_sync")
```

**Date window (HW4 — must END at yesterday PHT):**
```python
from datetime import datetime, timedelta, timezone

PHT = timezone(timedelta(hours=8))

def compute_window(args) -> list[str]:
    """Return list of YYYY-MM-DD strings to verify. Window ENDS at yesterday PHT."""
    if args.date:
        return [args.date]  # explicit single date override
    end_date = datetime.now(PHT).date() - timedelta(days=1)  # HW4: yesterday, not today
    start_date = end_date - timedelta(days=args.days - 1)
    return [(start_date + timedelta(days=i)).isoformat() for i in range(args.days)]
```

**Core function `fetch_mosaic_count` (MW2 — reuses retry/rate-limit from `fetch_orders_page`):**

```python
def fetch_mosaic_count(client, cred, location_id, business_date) -> int:
    """Return Mosaic's meta.total for a store-day. Reuses the full retry/429/5xx
    pattern from sync_pos_to_supabase.fetch_orders_page (line 310-351).

    httpx bracket-encoding of filter[location_id] is known-working — see
    sync_pos_to_supabase.py:315-320 for the existing production call pattern. (MW10)
    """
    token = ensure_token(client, cred)
    # Reuse fetch_orders_page with page[size] forced to 1 — we only want meta.total.
    # This inherits the 3-retry loop, 65s 429 wait, 10s 5xx wait, and connection-error retry.
    # Temporarily override MOSAIC_PAGE_SIZE via direct params (we pass page=1 + size=1).
    data = _fetch_page_size_1(client, token, location_id, business_date)
    return int(data.get("meta", {}).get("total", 0))

def _fetch_page_size_1(client, token, location_id, business_date) -> dict:
    """Count-only fetch using fetch_orders_page's retry semantics with size=1."""
    import time
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    params = {
        "filter[business_date]": business_date,
        "filter[location_id]": location_id,
        "page[number]": 1,
        "page[size]": 1,  # count-only, no data rows needed
    }
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = client.get(MOSAIC_ORDERS_URL, headers=headers, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                time.sleep(RATE_LIMIT_WAIT)
                continue
            if r.status_code >= 500:
                time.sleep(RETRY_WAIT)
                continue
            raise RuntimeError(f"Mosaic API error {r.status_code}: {r.text[:200]}")
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT)
                continue
            raise
    raise RuntimeError("Max retries exceeded fetching count")
```

**Supabase count via PostgREST (HW1 — MW5 inlined):**
```python
import requests

def supabase_count(location_id: int, business_date: str) -> int:
    """Return SELECT COUNT(*) FROM pos_orders WHERE location_id=X AND business_date=Y
    via PostgREST count=exact header (cheaper than Management SQL, no rate limit concern).
    """
    headers = {
        "apikey": os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        "Authorization": f"Bearer {os.environ['SUPABASE_SERVICE_ROLE_KEY']}",
        "Prefer": "count=exact",
        "Range-Unit": "items",
        "Range": "0-0",  # return 0 rows, only the count header
    }
    params = {
        "location_id": f"eq.{location_id}",
        "business_date": f"eq.{business_date}",
        "select": "id",
    }
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/pos_orders",
        headers=headers, params=params, timeout=15,
    )
    r.raise_for_status()
    # Content-Range header format: "0-0/NNN" where NNN is the total row count
    content_range = r.headers.get("content-range", "0-0/0")
    return int(content_range.split("/")[-1])
```

**Main loop (parallel across 12 credential groups via `ThreadPoolExecutor`):**

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def _process_group(cred, dates, args):
    """Worker: one thread per credential group. Owns its own httpx.Client."""
    import httpx, time
    results = []  # list of rows to upsert to sync_verification
    unresolved = []

    client = httpx.Client(timeout=30)
    try:
        for loc in cred["locations"]:
            loc_id = loc["location_id"]
            store_name = loc["store_name"]
            for ds in dates:
                if _shutdown:
                    break
                row = {
                    "location_id": loc_id,
                    "business_date": ds,
                    "heal_attempted": False,
                }
                try:
                    mosaic_total = fetch_mosaic_count(client, cred, loc_id, ds)
                    time.sleep(REQUEST_INTERVAL)  # MW2: per-request rate limit sleep
                    sb_total = supabase_count(loc_id, ds)
                except Exception as e:
                    row.update(status="api_error", mosaic_total=None, supabase_total=None, error_message=str(e)[:500])
                    results.append(row)
                    unresolved.append((store_name, ds, row))
                    continue

                row.update(mosaic_total=mosaic_total, supabase_total=sb_total)

                if mosaic_total == sb_total:
                    row["status"] = "ok"
                elif mosaic_total > sb_total:
                    if args.no_heal:
                        row["status"] = "missing"
                        unresolved.append((store_name, ds, row))
                    else:
                        # HW2: use set_sync_progress(..., 'pending') NOT DELETE.
                        # sync_store_day does not consult sync_progress, so this is for audit trail only.
                        set_sync_progress(client, loc_id, ds, "pending")
                        try:
                            sync_store_day(client, cred, loc_id, store_name, ds)
                            row["heal_attempted"] = True
                            new_sb = supabase_count(loc_id, ds)
                            row["supabase_total"] = new_sb
                            if new_sb == mosaic_total:
                                row["status"] = "healed"
                            else:
                                row["status"] = "unresolved"
                                unresolved.append((store_name, ds, row))
                        except Exception as e:
                            row["status"] = "unresolved"
                            row["heal_attempted"] = True
                            row["error_message"] = str(e)[:500]
                            unresolved.append((store_name, ds, row))
                else:  # mosaic_total < sb_total
                    row["status"] = "extra"  # flag for investigation (see HW3 below)
                    unresolved.append((store_name, ds, row))

                results.append(row)
    finally:
        client.close()
    return results, unresolved

def main(args):
    creds = load_credentials(CREDENTIALS_CSV)
    dates = compute_window(args)

    all_results = []
    all_unresolved = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        futures = {ex.submit(_process_group, cred, dates, args): cred for cred in creds}
        for fut in as_completed(futures):
            try:
                results, unresolved = fut.result()
                all_results.extend(results)
                all_unresolved.extend(unresolved)
            except Exception as e:
                sentry_sdk.capture_exception(e)
                print(f"Credential group failed: {e}", file=sys.stderr)

    # Upsert to sync_verification
    if not args.dry_run:
        upsert_verification_rows(all_results)

    # Build and send Chat alert
    if not args.no_chat:
        if all_unresolved:
            send_chat_alert(all_unresolved, total_verified=len(all_results))
        else:
            send_chat_summary(total_verified=len(all_results), window=dates)

    # MW9: Exit semantics — exit 0 if alerts were handled successfully, exit non-zero only on infra failure
    # Unresolved discrepancies are NOT an infra failure; they are expected output that the Chat alert handles.
    # The script exits non-zero ONLY if Sentry DSN missing (CB5) or if a credential group completely failed.
    return 0
```

**Chat alert (MW6 — inlined, not "copy from file X"):**
```python
def send_chat_alert(unresolved, total_verified):
    """Post consolidated discrepancy list to the anomaly Chat space."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds_path = Path(__file__).resolve().parents[1] / "credentials" / "task-manager-service.json"
    creds = service_account.Credentials.from_service_account_file(
        str(creds_path),
        scopes=["https://www.googleapis.com/auth/chat.bot"],
    )
    chat = build("chat", "v1", credentials=creds)

    lines = [
        f"🔴 Sync Verification — {datetime.now(PHT).strftime('%Y-%m-%d %H:%M')} PHT",
        f"Verified: {total_verified} store-days",
        f"Unresolved: {len(unresolved)}",
        "",
        "DISCREPANCIES:",
    ]
    for store_name, ds, row in unresolved[:30]:  # cap to 30 lines
        m = row.get("mosaic_total")
        s = row.get("supabase_total")
        status = row["status"]
        if status == "api_error":
            lines.append(f"  {store_name} {ds}: API ERROR — {row.get('error_message', '')[:80]}")
        else:
            lines.append(f"  {store_name} {ds}: Mosaic={m}, Supabase={s}, status={status}")
    if len(unresolved) > 30:
        lines.append(f"  ... and {len(unresolved) - 30} more")

    chat.spaces().messages().create(
        parent="spaces/AAQA3NVVR6c",  # same as anomaly detection
        body={"text": "\n".join(lines)},
    ).execute()

def send_chat_summary(total_verified, window):
    """Post green summary when all OK."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds_path = Path(__file__).resolve().parents[1] / "credentials" / "task-manager-service.json"
    creds = service_account.Credentials.from_service_account_file(
        str(creds_path),
        scopes=["https://www.googleapis.com/auth/chat.bot"],
    )
    chat = build("chat", "v1", credentials=creds)
    chat.spaces().messages().create(
        parent="spaces/AAQA3NVVR6c",
        body={"text": f"✅ Sync verification: all {total_verified} store-days OK (window {window[0]} → {window[-1]})"},
    ).execute()
```

**Sentry integration (CB5 note):**
This is a standalone CLI, NOT a `@frappe.whitelist()` endpoint, so `set_backend_observability_context()` does not apply per `.claude/rules/sentry-observability.md` (DM-7). Instead:
- `sentry_sdk.init()` at script startup (with fail-fast if DSN missing)
- Tagged `module=sync_verification, action=verify_mosaic_pos_sync`
- Unhandled exceptions surface in the `bei-hrms` Sentry project automatically
- Credential-group-level failures are captured via `sentry_sdk.capture_exception(e)` in the main loop

**Known limitations (documented per S091 cold-start rule):**
- `sync_pos_to_supabase.py:102` registers a SIGINT handler at import time. The verify script MUST reinstall its own handler after import (done at the top of the script, see MW1 snippet above).
- `sync_pos_to_supabase.SUPABASE_KEY` and `SUPABASE_MGMT_TOKEN` are module-level globals initialized to empty string. The verify script MUST mutate them via `sps.SUPABASE_KEY = ...` after import and BEFORE calling any function that talks to Supabase (CB3).
- `sync_store_day()` does NOT consult `sync_progress` before running; the `skip-if-complete` logic is in `sync_credential_group()` at line 594, which the verify script does NOT call. Therefore the heal path does NOT need to delete the stale row — calling `set_sync_progress(..., 'pending')` before heal is for audit trail only (HW2).

### 2. `data/supabase/migrations/2026-04-06-create-sync-verification.sql` (NEW)

**MUST_MODIFY:** `data/supabase/migrations/2026-04-06-create-sync-verification.sql`
**MUST_CONTAIN:** `CREATE TABLE IF NOT EXISTS sync_verification`
**MUST_CONTAIN:** `CHECK (status IN ('ok', 'missing', 'extra', 'healed', 'unresolved', 'api_error'))`

```sql
CREATE TABLE IF NOT EXISTS sync_verification (
    location_id    INT NOT NULL,
    business_date  DATE NOT NULL,
    mosaic_total   INT,
    supabase_total INT,
    delta          INT GENERATED ALWAYS AS (COALESCE(mosaic_total,0) - COALESCE(supabase_total,0)) STORED,
    status         TEXT NOT NULL CHECK (status IN ('ok', 'missing', 'extra', 'healed', 'unresolved', 'api_error')),
    verified_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    heal_attempted BOOL DEFAULT FALSE,
    error_message  TEXT,
    PRIMARY KEY (location_id, business_date, verified_at)
);

CREATE INDEX idx_sync_verification_status_recent
  ON sync_verification(status, verified_at DESC)
  WHERE status IN ('missing', 'unresolved', 'api_error');

CREATE INDEX idx_sync_verification_date
  ON sync_verification(business_date DESC);

COMMENT ON TABLE sync_verification IS
  'Ground-truth reconciliation of Mosaic POS vs Supabase pos_orders. Written nightly at 00:30 PHT by scripts/verify_mosaic_pos_sync.py. See S165.';
```

**Status semantics:**
| Status | Meaning |
|--------|---------|
| `ok` | Mosaic count equals Supabase count |
| `missing` | Supabase < Mosaic, heal not attempted (`--no-heal` mode) |
| `extra` | Supabase > Mosaic (unusual; flag for investigation — possibly a cancelled order) |
| `healed` | Was missing, re-sync recovered the orders |
| `unresolved` | Still missing after one heal attempt — surfaces in Chat alert |
| `api_error` | Mosaic or Supabase call failed — surfaces in Chat alert |

---

## Files to Modify

### 1. `.github/workflows/daily-pos-sync.yml`

**MUST_MODIFY:** `.github/workflows/daily-pos-sync.yml`
**MUST_CONTAIN:** `0 2-16 * * *` — proves hourly cron is set
**MUST_CONTAIN:** `verify-sync:` — proves the new job exists
**MUST_CONTAIN:** `verify_mosaic_pos_sync.py` — proves the new job runs the script
**MUST_CONTAIN:** `github.event.schedule == '30 16 * * *'` — proves gating on nightly cron
**MUST_CONTAIN:** `concurrency:` — proves workflow-level concurrency is set (CB2)
**MUST_CONTAIN:** `inputs.skip_verify != 'true'` — proves CB1 boolean fix
**MUST_CONTAIN:** `inputs.skip_anomaly != 'true'` — proves CB1 boolean fix applied to existing bug
**MUST_CONTAIN:** `timeout-minutes: 50` — proves CB2 timeout reduction
**MUST_CONTAIN:** `type: boolean` — proves CB1 declared types

**Change 1 — Workflow-level concurrency + cron schedules (CB2 + cron update):**

Add at the TOP of the file (before `jobs:`):
```yaml
name: Daily POS Sync

on:
  schedule:
    # Hourly POS sync, 10 AM to midnight PHT (02:00-16:00 UTC, 15 runs/day)
    - cron: "0 2-16 * * *"
    # Nightly verification + anomaly detection (00:30 PHT = 16:30 UTC)
    - cron: "30 16 * * *"
  workflow_dispatch:
    inputs:
      target_date:
        description: "Override sync date (YYYY-MM-DD). Leave blank for yesterday."
        type: string
      skip_anomaly:
        description: "Skip anomaly detection step"
        type: boolean
        default: false
      skip_verify:
        description: "Skip sync verification step"
        type: boolean
        default: false

# CB2: Serialize all runs of this workflow so hourly and nightly cannot overlap.
# With hourly cron + 50-min timeout, a slow run would otherwise collide with the
# next hour's run AND the 16:30 verify run, re-introducing the partial-sync bug
# this sprint is meant to eliminate. cancel-in-progress=false lets long runs
# finish and queues newer ones.
concurrency:
  group: daily-pos-sync
  cancel-in-progress: false

jobs:
  pos-sync:
    # ... existing pos-sync job body, BUT:
    timeout-minutes: 50  # CB2: was 180, reduced to fit under 1-hour cron boundary
    # (3 retries × ~15 min worst-case = ~45 min budget)
```

**Change 2 — Fix `anomaly-detection` gating (CB1 — fix pre-existing boolean bug in same PR):**

The pre-existing `anomaly-detection.if` uses `!inputs.skip_anomaly` which is a latent bug: `workflow_dispatch` inputs are strings, and `!"false" == false`, silently skipping the job on manual dispatch. Fix in this PR since we're already touching the file:
```yaml
  anomaly-detection:
    # ... existing job body ...
    if: >-
      ${{ inputs.skip_anomaly != 'true' &&
          (github.event_name == 'workflow_dispatch' ||
           github.event.schedule == '30 16 * * *') }}
```

Otherwise `anomaly-detection` would run 15 times a day on the hourly cron and spam the Chat space.

**Change 3 — New `verify-sync` job** (add after `refresh-sales-dashboard-views`, parallel with `anomaly-detection`):
```yaml
  verify-sync:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    needs: [refresh-sales-dashboard-views]
    # CB1: use `!= 'true'` form. Do NOT use `!inputs.skip_verify` — GH Actions
    # inputs are strings, and `!"false" == false` silently skips the job.
    if: >-
      ${{ inputs.skip_verify != 'true' &&
          (github.event_name == 'workflow_dispatch' ||
           github.event.schedule == '30 16 * * *') }}

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: pip install httpx requests google-auth google-api-python-client sentry-sdk
      - name: Fail-fast if Sentry DSN missing (CB5)
        run: |
          if [ -z "${{ secrets.SENTRY_DSN_BEI_HRMS }}" ]; then
            echo "::error::SENTRY_DSN_BEI_HRMS secret not set — refusing to run observability sprint without observability"
            exit 1
          fi
      - name: Decode Mosaic credentials
        run: |
          mkdir -p data/POS_Extraction
          echo "${{ secrets.MOSAIC_CREDS_CSV }}" | base64 -d > data/POS_Extraction/MOSAIC_POS_API_KEYS.csv
      - name: Setup Google credentials
        run: |
          mkdir -p credentials
          echo "${{ secrets.GOOGLE_SERVICE_ACCOUNT_JSON }}" | base64 -d > credentials/task-manager-service.json
      - name: Run sync verification
        env:
          SUPABASE_URL: https://csnniykjrychgajfrgua.supabase.co
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          SUPABASE_MGMT_TOKEN: ${{ secrets.SUPABASE_MGMT_TOKEN }}
          SENTRY_DSN_BEI_HRMS: ${{ secrets.SENTRY_DSN_BEI_HRMS }}
        run: |
          if [ -n "${{ inputs.target_date }}" ]; then
            python scripts/verify_mosaic_pos_sync.py --date "${{ inputs.target_date }}"
          else
            python scripts/verify_mosaic_pos_sync.py --days 7
          fi
```

**Change 4 — `notify-failure` job: include `verify-sync` in `needs`, keep `always() && contains(... 'failure')` semantics intact:**
```yaml
  notify-failure:
    # ... existing body
    needs: [pos-sync, web-sync, foodpanda-sync, foodpanda-item-sync, refresh-sales-dashboard-views, anomaly-detection, verify-sync]
    if: ${{ always() && contains(needs.*.result, 'failure') }}
    # `skipped` results do NOT match 'failure', so hourly runs (where anomaly-detection
    # and verify-sync are skipped) will not trigger notify-failure. Only actual job
    # failures trigger it.
```

**Change 5 — MW3: Decision on `refresh-sales-dashboard-views` cadence:**

**Decision: `refresh-sales-dashboard-views` runs every hour (UNGATED) for dashboard freshness.** The whole point of hourly sync is near-real-time dashboards, so the materialized view refresh must also run hourly. The refresh takes ~20 seconds per view (5 views × 20s = 100s worst case) which is negligible on a 15-runs/day budget.

Do NOT gate `refresh-sales-dashboard-views` with `github.event.schedule == '30 16 * * *'` — leave its existing `needs: [pos-sync, web-sync, foodpanda-sync, foodpanda-item-sync]` unchanged so it runs on every cron trigger (hourly AND nightly).

**Change 6 — I2 / cold-start note on Chat space consistency:**

The workflow already posts `notify-failure` alerts to `spaces/AAQABiNmpBg` (workflow failure space). The new `verify-sync` script posts discrepancy alerts to `spaces/AAQA3NVVR6c` (anomaly detection space). These are intentionally different — do NOT merge them. Add a comment in the workflow YAML to prevent a future cold-start agent from "fixing" the mismatch:
```yaml
# notify-failure posts to spaces/AAQABiNmpBg (workflow-level alerts)
# verify-sync script posts to spaces/AAQA3NVVR6c (anomaly detection space, same as detect_anomalies.py)
# These are intentionally separate — do not merge.
```

---

## Sentry Observability Instrumentation

Per `.claude/rules/sentry-observability.md` (DM-7):

- **Backend rule (`@frappe.whitelist()` endpoints in `hrms/api/*.py`)**: NOT applicable. This plan touches NO `@frappe.whitelist()` endpoints. The verify script is a standalone CLI.
- **Frontend rule (`bei-tasks/app/api/*/route.ts`)**: NOT applicable. No frontend routes touched.
- **Script-level Sentry**: ADDED via vanilla `sentry-sdk.init()` at the top of `verify_mosaic_pos_sync.py`. Project: `bei-hrms` (python). DSN from `SENTRY_DSN_BEI_HRMS` Doppler secret. Tagged `module=sync_verification, action=verify_mosaic_pos_sync`. Unhandled exceptions surface in the Sentry dashboard for the `bei-hrms` project.

---

## Agent Boot Sequence

1. **Read this plan fully.**
2. **Create the sprint branch:** `git fetch origin production && git checkout -b s165-mosaic-sync-verification origin/production`. NEVER write code on production.
3. **Verify the Supabase constraint is still fixed (T0.1):**
   ```bash
   python -c "import subprocess, requests; t=subprocess.check_output(['doppler','secrets','get','SUPABASE_MGMT_TOKEN','--plain','--project','bei-erp','--config','dev'],text=True).strip(); r=requests.post('https://api.supabase.com/v1/projects/csnniykjrychgajfrgua/database/query', headers={'Authorization':f'Bearer {t}','Content-Type':'application/json'}, json={'query':\"SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='sync_progress_status_check'\"}, timeout=30); print(r.json())"
   ```
   Must show `'partial'` in the allowed values. If missing, STOP and add it before proceeding.
4. **CB4 — Filter isolation probe (T0.2, HARD GATE):** Call Mosaic with TWO DIFFERENT `location_id` values from the SAME credential group on the same past date. Confirm `meta.total` DIFFERS between the two calls. This proves `filter[location_id]` is honored by Mosaic and the whole verification approach is sound.
   ```python
   # Example: pick two stores from the first credential group in MOSAIC_POS_API_KEYS.csv
   from scripts.sync_pos_to_supabase import load_credentials, ensure_token, MOSAIC_ORDERS_URL, CREDENTIALS_CSV
   import httpx, json
   creds = load_credentials(CREDENTIALS_CSV)
   cred = creds[0]  # first group
   assert len(cred["locations"]) >= 2, "probe requires a credential group with 2+ stores"
   client = httpx.Client(timeout=30)
   token = ensure_token(client, cred)
   results = {}
   for loc in cred["locations"][:2]:
       r = client.get(MOSAIC_ORDERS_URL,
                      headers={"Authorization": f"Bearer {token}"},
                      params={"filter[location_id]": loc["location_id"],
                              "filter[business_date]": "2026-04-04",
                              "page[size]": 1, "page[number]": 1},
                      timeout=15)
       results[loc["location_id"]] = r.json()["meta"]["total"]
   print(json.dumps(results, indent=2))
   # Write results to tmp/s165_filter_probe.json
   # HARD BLOCKER: If both values are identical, filter[location_id] is being ignored.
   # STOP the sprint and escalate to Sam before writing any code.
   ```
5. **HW3 — Cancelled order probe (T0.2b):** Optional but recommended. Check whether Mosaic's `meta.total` decreases when an order is cancelled. This determines the `extra` status tolerance policy:
   - If cancellations decrease `meta.total`: expect small ongoing `extra` flags for busy stores (acceptable, document it)
   - If cancellations do NOT decrease `meta.total`: `extra` status should never fire on a healthy store — any `extra` is a real anomaly worth investigating
   Record the finding in `tmp/s165_cancellation_probe.md`.
6. **Read files in this order:**
   - `scripts/sync_pos_to_supabase.py` (lines 1-100, 240-310, 354-400, 499-560, 730-780)
   - `scripts/detect_anomalies.py` (lines 1-100, 360-390)
   - `docs/api/MOSAIC_API.md` (lines 1-110)
   - `.github/workflows/daily-pos-sync.yml` (full file)
7. **Start Phase 0** (pre-flight audit) and proceed sequentially.

---

## L3 Workflow Scenarios

**Note:** This sprint's "UI" is the verification script. L3 scenarios test the CLI end-to-end on production data.

| Agent | Action | Expected Outcome | Failure Means |
|-------|--------|-------------------|---------------|
| Builder | `python scripts/verify_mosaic_pos_sync.py --date 2026-04-04 --store 2338 --dry-run` | Prints one line: `SM Megamall (2338) 2026-04-04: Mosaic=X, Supabase=X, OK`. No writes to `sync_verification`. | `--dry-run` flag broken, or `fetch_mosaic_count` not working |
| Builder | `python scripts/verify_mosaic_pos_sync.py --date 2026-04-03 --no-heal --dry-run` | Reports most stores flagged as `missing` because Apr 3 has 2,321 orders (expected ~8K+). | Statistical comparison logic broken, or SQL COUNT query broken |
| Builder | `python scripts/verify_mosaic_pos_sync.py --date 2026-04-03` (live heal) | Discrepancies detected, `sync_store_day()` called for each, stores heal to `healed` status. Re-run shows all `ok`. | Auto-heal logic broken, or `sync_progress` row not cleared before re-sync |
| Builder | SQL query: `SELECT status, COUNT(*) FROM sync_verification WHERE business_date = '2026-04-03' GROUP BY status;` | Returns majority `healed` + remaining `ok`. | Rows not being written to `sync_verification` |
| Builder | SQL query: `SELECT COUNT(*), SUM(original_gross_sales) FROM pos_orders WHERE business_date = '2026-04-03' AND payment_status = 'PAID';` | Shows ~8K+ orders, ~PHP 4.5M+ gross (was 2,321 / PHP 1.49M before heal). | Auto-heal didn't actually fetch orders from Mosaic |
| Builder | `python scripts/verify_mosaic_pos_sync.py --days 7` (full nightly run) | Completes in <90 seconds. All 315 rows (45 stores × 7 days) in `sync_verification`. Mix of `ok`, `healed`, `unresolved`. | Parallelism broken or rate limiting too aggressive |
| Builder | **MW7 backup step** — Before any destructive test: `CREATE TABLE temp_s165_backup_2338_20260404 AS SELECT * FROM pos_orders WHERE location_id = 2338 AND business_date = '2026-04-04';` Verify row count matches production. | Backup table created with correct row count. | Backup step missing = destructive test would be unsafe |
| Builder | Artificially break: `DELETE FROM pos_orders WHERE location_id = 2338 AND business_date = '2026-04-04';` then `python scripts/verify_mosaic_pos_sync.py --date 2026-04-04 --store 2338 --no-heal` | Chat message delivered to `spaces/AAQA3NVVR6c` listing SM Megamall as unresolved. | Chat send pattern broken, or alert batching broken |
| Builder | After test, heal: `python scripts/verify_mosaic_pos_sync.py --date 2026-04-04 --store 2338` | Status changes to `healed`, `pos_orders` row count restored to match backup. | Auto-heal regression |
| Builder | **MW7 rollback verification** — `SELECT COUNT(*) FROM pos_orders WHERE location_id = 2338 AND business_date = '2026-04-04'` matches `SELECT COUNT(*) FROM temp_s165_backup_2338_20260404`. If mismatch, restore from backup: `INSERT INTO pos_orders SELECT * FROM temp_s165_backup_2338_20260404 ON CONFLICT (id) DO NOTHING;`. Then drop backup table. | Row counts match exactly. Backup table dropped after verification. | Heal path did not restore all rows — indicates sync_store_day bug |
| Builder | Trigger `daily-pos-sync.yml` via `workflow_dispatch` with `target_date=2026-04-04` | `pos-sync` → `refresh-sales-dashboard-views` → `verify-sync` runs in that order. `verify-sync` logs show 7-day verification. `notify-failure` does NOT fire. | Workflow YAML syntax error, or job dependency broken |
| Builder | Trigger `daily-pos-sync.yml` via `workflow_dispatch` with `skip_verify=true` | `verify-sync` job shows `skipped`. Other jobs run normally. Proves CB1 boolean fix works. | CB1 boolean bug not actually fixed |
| Builder | **CB3 heal 401 check** — Before deploy: run `python scripts/verify_mosaic_pos_sync.py --date 2026-04-03 --store 2338` locally. Verify the heal path successfully upserts rows (not 401). | Heal completes, sync_verification row status = `healed` or `ok`. | CB3 module-global propagation missing → 401 on every heal |
| Builder | Monitor first 24h of hourly schedule after merge | 15 runs of `pos-sync` between 02:00-16:00 UTC. `refresh-sales-dashboard-views` runs on every hourly trigger (15x). `anomaly-detection` and `verify-sync` run ONLY on 16:30 UTC schedule. Zero duplicate orders in `pos_orders`. `concurrency:` group prevents overlap. | Cron schedule wrong, or gating `if` broken, or concurrency group missing |
| Builder | **C3 hourly skip sanity** — Inspect any 11:00 UTC hourly run in Actions UI: `pos-sync` + `web-sync` + `foodpanda-sync` + `foodpanda-item-sync` + `refresh-sales-dashboard-views` show `success`; `anomaly-detection` and `verify-sync` show `skipped`; `notify-failure` shows `skipped` (no failures). | As described. | Gating `if` misconfigured, notify-failure fires on skip |

**L3 Evidence Files Required (committed via `git add -f` before closeout):**
- `output/l3/s165/form_submissions.json` — CLI invocations + arguments
- `output/l3/s165/api_mutations.json` — Mosaic calls made + Supabase writes
- `output/l3/s165/state_verification.json` — Before/after SQL counts for Apr 3, Apr 4, and MW7 backup/restore verification
- `output/l3/s165/verification_run.log` — Full stdout of the 7-day run
- `output/l3/s165/verify_s165.py` — The verification script itself
- `output/l3/s165/filter_probe.json` — Results of CB4 filter-isolation probe
- `output/l3/s165/cancellation_probe.md` — Results of HW3 cancellation probe (if performed)

---

## Zero-Skip Enforcement

Every task in this plan MUST be implemented. The agent is FORBIDDEN from:

- Skipping a task silently
- Marking partial work as "done"
- Replacing a task with a simpler version without user approval
- Saying "deferred to next sprint"
- Combining tasks and dropping features in the merge
- Implementing happy path only, skipping edge cases (e.g., the `extra` / `api_error` branches)

**Verification script** (agent MUST write and run this before claiming COMPLETED):

File: `output/l3/s165/verify_s165.py`
```python
#!/usr/bin/env python3
"""S165 machine-verifiable phase gate. Runs from filesystem, not self-report."""
import subprocess, sys, pathlib

REPO = pathlib.Path(__file__).resolve().parents[3]

def check_contains(path, needles):
    p = REPO / path
    if not p.exists():
        return f"FAIL: {path} does not exist"
    text = p.read_text(encoding='utf-8')
    missing = [n for n in needles if n not in text]
    return f"FAIL: {path} missing: {missing}" if missing else f"PASS: {path}"

def check_diff_includes(branch, files):
    out = subprocess.run(["git", "diff", "--name-only", f"origin/production..{branch}"],
                         capture_output=True, text=True, cwd=REPO)
    diff = out.stdout.split()
    missing = [f for f in files if f not in diff]
    return f"FAIL: branch diff missing: {missing}" if missing else f"PASS: branch diff includes all required files"

results = [
    check_contains("scripts/verify_mosaic_pos_sync.py", [
        # Core function
        "def fetch_mosaic_count(",
        '"meta"]["total"]',
        "sync_verification",
        "spaces/AAQA3NVVR6c",
        # CB3: module-alias import + global propagation
        "import sync_pos_to_supabase as sps",
        "sps.SUPABASE_KEY =",
        "sps.SUPABASE_MGMT_TOKEN =",
        # CB5: Sentry fail-fast
        "sentry_sdk.init",
        "sys.exit(2)",
        # MW1: reinstall SIGINT
        "signal.signal(signal.SIGINT",
        # HW4: window ends at yesterday
        "datetime.now(PHT).date() - timedelta(days=1)",
        # HW1: PostgREST count=exact pattern
        "content-range",
        # CLI flags
        "--days",
        "--no-heal",
        "--dry-run",
        # MW2: retry pattern for count-only fetch
        "MAX_RETRIES",
        "RATE_LIMIT_WAIT",
    ]),
    check_contains("data/supabase/migrations/2026-04-06-create-sync-verification.sql", [
        "CREATE TABLE IF NOT EXISTS sync_verification",
        "healed", "unresolved", "api_error",
    ]),
    check_contains(".github/workflows/daily-pos-sync.yml", [
        "0 2-16 * * *",
        "30 16 * * *",
        "verify-sync:",
        "verify_mosaic_pos_sync.py",
        "github.event.schedule == '30 16 * * *'",
        # CB1: boolean fix
        "inputs.skip_verify != 'true'",
        "inputs.skip_anomaly != 'true'",
        "type: boolean",
        # CB2: concurrency + timeout
        "concurrency:",
        "group: daily-pos-sync",
        "timeout-minutes: 50",
    ]),
    check_diff_includes("s165-mosaic-sync-verification", [
        "scripts/verify_mosaic_pos_sync.py",
        "data/supabase/migrations/2026-04-06-create-sync-verification.sql",
        ".github/workflows/daily-pos-sync.yml",
        # MW8: L3 evidence files must be committed
        "output/l3/s165/form_submissions.json",
        "output/l3/s165/api_mutations.json",
        "output/l3/s165/state_verification.json",
        "output/l3/s165/verification_run.log",
        "output/l3/s165/verify_s165.py",
    ]),
]

for r in results:
    print(r)

if any(r.startswith("FAIL") for r in results):
    sys.exit(1)
print("\n✅ All S165 verification checks passed.")
```

The agent MUST run this script after each phase and fix any FAIL before proceeding.

---

## Phases & Tasks

### Phase 0 — Pre-flight audit (5 units)

- **T0.1** — Verify `sync_progress_status_check` constraint still allows `'partial'`. Run the query from Agent Boot Sequence step 3. **HARD BLOCKER:** If constraint is stale, STOP and present options.
- **T0.2 (CB4)** — **Filter isolation probe.** Call Mosaic with TWO DIFFERENT `location_id` values from the SAME credential group on Apr 4. Write results to `tmp/s165_filter_probe.json` AND `output/l3/s165/filter_probe.json`. **HARD BLOCKER:** If `meta.total` is identical for both calls, `filter[location_id]` is being ignored → STOP, escalate to Sam. The whole verification approach depends on this filter working.
- **T0.3 (HW3)** — **Cancellation behavior probe (optional).** If time permits, cancel a test order via Mosaic and observe whether `meta.total` decreases. Document finding in `tmp/s165_cancellation_probe.md` and `output/l3/s165/cancellation_probe.md`. This informs the `extra` status tolerance policy.
- **T0.4** — Confirm `SENTRY_DSN_BEI_HRMS` is in BOTH Doppler (`doppler secrets get SENTRY_DSN_BEI_HRMS --project bei-erp --config dev`) AND GitHub Actions secrets. Two separate stores must both be populated. **HARD BLOCKER:** If missing from either, STOP — the sprint cannot ship without observability.
- **T0.5** — Confirm `SUPABASE_SERVICE_ROLE_KEY` and `SUPABASE_MGMT_TOKEN` are accessible via `os.environ` when the GH Actions workflow runs. Add explicit workflow step to check both before running the script.

### Phase 1 — Schema migration (2 units)

- **T1.1** — Create `data/supabase/migrations/2026-04-06-create-sync-verification.sql` with the full SQL from the "Files to Create" section.
- **T1.2** — Apply the migration via Supabase Management API. Verify: `SELECT column_name FROM information_schema.columns WHERE table_name = 'sync_verification'`. Confirm all 8 columns present (including generated `delta`).

### Phase 2 — Build verify script (10 units)

- **T2.1** — Create `scripts/verify_mosaic_pos_sync.py` skeleton. Include:
  - argparse flags (`--date`, `--days`, `--store`, `--no-heal`, `--no-chat`, `--dry-run`)
  - Path-based imports: `sys.path.insert(0, str(Path(__file__).parent))` then `import sync_pos_to_supabase as sps`
  - Explicit imports: `load_credentials, ensure_token, sync_store_day, set_sync_progress, fetch_orders_page, MOSAIC_ORDERS_URL, REQUEST_INTERVAL, MAX_RETRIES, RATE_LIMIT_WAIT, RETRY_WAIT, CREDENTIALS_CSV, SUPABASE_URL`
- **T2.2 (CB3, HARD BLOCKER)** — Immediately after imports, propagate secrets to the imported module:
  ```python
  sps.SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
  sps.SUPABASE_MGMT_TOKEN = os.environ["SUPABASE_MGMT_TOKEN"]
  ```
  **HARD BLOCKER:** WITHOUT THIS, every call to `sync_store_day()` → `supabase_upsert()` will 401 because the module globals stay empty. Using `from sync_pos_to_supabase import sync_store_day` form does NOT work — must use `import as alias`.
- **T2.3 (CB5, HARD BLOCKER)** — Add Sentry fail-fast after imports:
  ```python
  dsn = os.environ.get("SENTRY_DSN_BEI_HRMS", "").strip()
  if not dsn:
      sys.exit(2)
  sentry_sdk.init(dsn=dsn, ...)
  ```
- **T2.4 (MW1)** — Reinstall SIGINT handler after import (sync_pos_to_supabase.py:102 already registered one at import time).
- **T2.5 (MW2)** — Implement `fetch_mosaic_count(client, cred, location_id, business_date)` with full retry/429/5xx loop (copy from `fetch_orders_page` at `sync_pos_to_supabase.py:310-351`, force `page[size]=1`). Include the per-call `time.sleep(REQUEST_INTERVAL)` in the caller loop.
- **T2.6 (HW1, MW5)** — Implement `supabase_count(location_id, business_date)` using **PostgREST `count=exact`** (NOT Management SQL API). Use the full code block in the "Files to Create" section. Parse `content-range` header to extract the count.
- **T2.7 (HW4)** — Implement `compute_window(args)` function that returns a list of date strings. **HARD BLOCKER:** Window MUST end at `datetime.now(PHT).date() - timedelta(days=1)` (yesterday), NOT today. Include this in MUST_CONTAIN assertions.
- **T2.8** — Implement `_process_group(cred, dates, args)` worker function. Each worker owns its own `httpx.Client`. Main loop iterates (store × date) with `time.sleep(REQUEST_INTERVAL)` between calls.
- **T2.9 (HW2)** — Implement auto-heal branch: call `set_sync_progress(..., 'pending')` BEFORE `sync_store_day()` (NOT DELETE — the pending marker is for audit trail only; `sync_store_day()` does not consult `sync_progress`). After heal, re-query `supabase_count` and set status `healed` if match, `unresolved` if still missing.
- **T2.10 (MW6)** — Inline `send_chat_alert(unresolved, total)` and `send_chat_summary(total, window)` functions using the Google Chat service account pattern. Space ID: `spaces/AAQA3NVVR6c`. Credentials path: `credentials/task-manager-service.json`.
- **T2.11** — Implement `upsert_verification_rows(rows)` — POST to `sync_verification` table via PostgREST with `Prefer: return=minimal, resolution=merge-duplicates`.
- **T2.12** — Implement `main(args)` with `ThreadPoolExecutor(max_workers=12)`, one future per credential group. Collect results + unresolved lists.
- **T2.13 (MW9)** — Exit semantics: return 0 if alerts were handled via Chat; non-zero ONLY on infra failure (Sentry DSN missing → 2, all credential groups failed → 3). Unresolved discrepancies are expected output, NOT failures.

### Phase 3 — Workflow updates (6 units)

- **T3.1 (CB2)** — Add workflow-level `concurrency: { group: daily-pos-sync, cancel-in-progress: false }` block at the top of `.github/workflows/daily-pos-sync.yml`.
- **T3.2 (CB2)** — Reduce `pos-sync.timeout-minutes` from 180 → 50.
- **T3.3** — Update cron schedules: add `0 2-16 * * *` (hourly 10 AM–midnight PHT), keep `30 16 * * *` (nightly verification).
- **T3.4 (CB1)** — Fix pre-existing `anomaly-detection.if` from `!inputs.skip_anomaly` to `inputs.skip_anomaly != 'true' && (...)`. Declare `skip_anomaly` as `type: boolean, default: false` in inputs.
- **T3.5 (CB1)** — Add `verify-sync` job with `inputs.skip_verify != 'true' && (...)` gating. Declare `skip_verify` as `type: boolean, default: false`.
- **T3.6 (CB5)** — Add pre-flight Sentry DSN check as a workflow step in `verify-sync`: fails the job if `secrets.SENTRY_DSN_BEI_HRMS` is empty.
- **T3.7 (MW3)** — Document in the workflow YAML comments that `refresh-sales-dashboard-views` is intentionally UNGATED (runs every hour for dashboard freshness).
- **T3.8** — Add `verify-sync` to `notify-failure.needs`, keep `if: always() && contains(needs.*.result, 'failure')` unchanged so skipped jobs don't trigger notifications.

### Phase 4 — L3 verification (8 units)

- **T4.1** — Run `--dry-run --store 2338 --date 2026-04-04`. Verify no writes to `sync_verification`. Capture stdout to `output/l3/s165/form_submissions.json`.
- **T4.2** — Run `--date 2026-04-03 --no-heal --dry-run`, confirm most stores flagged `missing` (because Apr 3 has only 2,321 orders).
- **T4.3** — Run `--date 2026-04-03` (live heal). Confirm Apr 3 order count jumps from 2,321 to ~8K+. Capture before/after to `output/l3/s165/state_verification.json`.
- **T4.4 (CB3 heal verification)** — Specifically verify no 401 errors in heal path. If 401s appear, the module-global propagation is missing — STOP and fix T2.2.
- **T4.5** — Run `--days 7` full nightly run. Capture wall time (<90s expected) and row counts.
- **T4.6 (MW7)** — Destructive test with backup/restore:
  ```sql
  -- Step 1: Backup
  CREATE TEMPORARY TABLE temp_s165_backup AS
  SELECT * FROM pos_orders WHERE location_id = 2338 AND business_date = '2026-04-04';

  -- Step 2: Capture pre-delete count to state_verification.json
  SELECT COUNT(*) FROM temp_s165_backup;

  -- Step 3: Delete
  DELETE FROM pos_orders WHERE location_id = 2338 AND business_date = '2026-04-04';

  -- Step 4: Run verify with --no-heal, confirm Chat alert fired
  -- (python scripts/verify_mosaic_pos_sync.py --date 2026-04-04 --store 2338 --no-heal)

  -- Step 5: Run verify with heal, confirm status = healed
  -- (python scripts/verify_mosaic_pos_sync.py --date 2026-04-04 --store 2338)

  -- Step 6: Verify row count restored
  SELECT COUNT(*) FROM pos_orders WHERE location_id = 2338 AND business_date = '2026-04-04';
  -- Must equal COUNT from Step 2

  -- Step 7: If mismatch, restore from backup (rollback)
  -- INSERT INTO pos_orders SELECT * FROM temp_s165_backup ON CONFLICT (id) DO NOTHING;

  -- Step 8: DROP TABLE temp_s165_backup;
  ```
  Capture all SQL and their outputs to `output/l3/s165/state_verification.json`.
- **T4.7 (CB1 skip test)** — Trigger `daily-pos-sync.yml` via `workflow_dispatch` with `skip_verify=true`. Confirm `verify-sync` job shows `skipped` (proves CB1 boolean fix works).
- **T4.8** — Trigger `daily-pos-sync.yml` via `workflow_dispatch` with `target_date=2026-04-04`. Confirm `verify-sync` runs, logs look clean, `notify-failure` does not fire.

### Phase 5 — Apr 2-3 backfill (2 units)

- **T5.1** — Run `python scripts/verify_mosaic_pos_sync.py --date 2026-04-02` on the branch. Confirm Apr 2 heals to ~8K+ orders. Capture before/after order counts to `output/l3/s165/state_verification.json`.
- **T5.2** — Same for Apr 3 if not already healed in Phase 4.

### Phase 6 — Closeout (5 units)

- **T6.1** — Run the verification script `output/l3/s165/verify_s165.py` — all checks must PASS. If any FAIL, fix and re-run before proceeding.
- **T6.2 (MW8)** — Stage and commit ALL evidence files with explicit paths:
  ```bash
  git add -f \
    scripts/verify_mosaic_pos_sync.py \
    data/supabase/migrations/2026-04-06-create-sync-verification.sql \
    .github/workflows/daily-pos-sync.yml \
    docs/plans/2026-04-06-sprint-165-mosaic-sync-verification.md \
    docs/plans/SPRINT_REGISTRY.md \
    output/l3/s165/form_submissions.json \
    output/l3/s165/api_mutations.json \
    output/l3/s165/state_verification.json \
    output/l3/s165/verification_run.log \
    output/l3/s165/verify_s165.py \
    output/l3/s165/filter_probe.json
  # Cancellation probe is optional — add if T0.3 was performed:
  # output/l3/s165/cancellation_probe.md
  ```
  **HARD BLOCKER:** Do NOT use `git add -A` or `git add .` — explicit file list only, to avoid committing stray files. Per `.claude/rules/core-governance.md` Git Safety Protocol.
- **T6.3** — Create PR: `GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms --base production --head s165-mosaic-sync-verification --title "S165: Mosaic Sync Verification + Hourly Sync" --body "..."`. PR body MUST include:
  - Task-by-task checklist (every T#.# from above marked ✓)
  - L3 evidence file list with commit SHAs
  - Pre-deploy verification results (CB3 heal 401 check, CB4 filter probe, CB5 Sentry DSN, CB1 skip test)
- **T6.4** — Update plan YAML: `status: COMPLETED`, `completed_date: 2026-04-06`, `backend_pr: <PR#>`, `execution_summary: <summary>`. Update `docs/plans/SPRINT_REGISTRY.md` S165 row with PR reference and COMPLETED status. Commit and push.
- **T6.5** — STOP. Per PR-HANDOFF rule, the agent does NOT merge. Post PR number to Sam and exit.

---

## Execution Workflow

- Test Python changes locally: `/local-frappe` (NOT needed — this script has no Frappe dependencies)
- Run the verify script directly: `python scripts/verify_mosaic_pos_sync.py --dry-run`
- Full workflow: `/agent-kickoff` (reads required skills automatically)
- E2E testing: Use the L3 scenarios above — no separate E2E framework needed

---

## Anti-Rewind / Concurrent-Run Protection Contract

- **Ownership matrix:** This sprint owns exclusively:
  - `scripts/verify_mosaic_pos_sync.py` (NEW)
  - `data/supabase/migrations/2026-04-06-create-sync-verification.sql` (NEW)
  - `.github/workflows/daily-pos-sync.yml` (MODIFIED — cron + new job + gating)
  - `sync_verification` table (NEW)
- **Protected surfaces (DO NOT TOUCH):**
  - `scripts/sync_pos_to_supabase.py` — import only, do NOT modify (unless a bug is found that blocks verification; if so, STOP and ask)
  - `scripts/detect_anomalies.py` — reference only for Chat send pattern
  - `sync_progress` table — can DELETE rows during heal path, but do NOT alter schema
  - `pos_orders`, `pos_order_items` tables — sync_store_day writes to these; verify script only reads
- **Remote truth baseline:**
  - repo: `Bebang-Enterprise-Inc/hrms`
  - release_branch: `production`
  - release_head_sha: to be captured at Phase 0 start
- **Freshness gate:** Before creating the PR, `git fetch origin production && git rebase origin/production`. If conflicts in `.github/workflows/daily-pos-sync.yml` (high-contention file), resolve by preserving both the hourly cron AND any other sprint's changes.

---

## Status Reconciliation Contract

When any of the following change, update all authoritative surfaces in the same commit:
1. Phase task status
2. L3 evidence file presence
3. PR number
4. Plan YAML `status` field
5. `docs/plans/SPRINT_REGISTRY.md` S165 row

---

## Signoff Model

- **Mode:** single-owner
- **Approver of record:** Sam (CEO)
- **Signoff artifact:** PR review + merge by Sam

---

## Out of Scope (Explicitly NOT in This Plan)

- **Changing Web sync schedule** — `web-sync` cron is a separate concern
- **Refactoring `sync_pos_to_supabase.py` into a shared library** — cleaner but enlarges scope; reuse via `import as alias` + global propagation instead
- **Dashboarding `sync_verification` results** — the table is queryable ad-hoc, dashboard can come later
- **Real-time mid-day alerts** — per CEO preference, alerts are once daily after midnight
- **Modifying `sync_pos_to_supabase.py` constraint/status logic** — was addressed in a prior session; verified still in place
- **Modifying `detect_anomalies.py`** — unrelated module, imports lazily for Chat

**No scope was cut during audit amendments.** All original features remain:
- ✓ Ground-truth verification via Mosaic `meta.total`
- ✓ Auto-heal path with re-verification
- ✓ 7-day rolling verification window
- ✓ Single consolidated Chat alert at 00:30 PHT
- ✓ Hourly sync cron from 10 AM–midnight PHT (15 runs/day)
- ✓ `sync_verification` table with 6 status values
- ✓ Apr 2-3 backfill as part of sprint
- ✓ Sentry instrumentation

Amendments ADDED reliability hardening (CB1-CB5, HW1-HW4, MW1-MW10). No deferrals to future sprints.

---

## Amendment History

### 2026-04-06 — Audit amendments applied (5 CRITICAL + 4 HIGH WARNING + 10 MEDIUM WARNING)

**Source:** `/audit-plan-bei-erp` run — 4 parallel domain auditors (system-arch, backend, deployment-qa, cold-start/zero-skip). Consolidated findings in `output/plan-audit/s165-mosaic-sync-verification/blockers_consolidated.md`.

**Summary of changes (no scope cuts, no deferrals):**

| ID | Severity | Fix applied in |
|----|----------|----------------|
| CB1 | CRITICAL | Workflow `inputs.skip_verify != 'true'` + `inputs.skip_anomaly != 'true'`, `type: boolean, default: false`, also fixes pre-existing `anomaly-detection` latent bug in same PR |
| CB2 | CRITICAL | Workflow `concurrency: { group: daily-pos-sync, cancel-in-progress: false }` + `pos-sync.timeout-minutes: 50` |
| CB3 | CRITICAL | Script uses `import sync_pos_to_supabase as sps` + `sps.SUPABASE_KEY = ...` before any heal call; added to MUST_CONTAIN assertions |
| CB4 | CRITICAL | Agent Boot Sequence step 4 + Phase 0 T0.2 now explicitly probes filter[location_id] isolation with two different location_ids from same credential group |
| CB5 | CRITICAL | Script fail-fast `sys.exit(2)` if Sentry DSN empty; workflow pre-flight step checks GH Actions secret |
| HW1 | HIGH | Inlined `supabase_count()` using PostgREST `count=exact` pattern; no Management SQL API dependency |
| HW2 | HIGH | Heal path calls `set_sync_progress(..., 'pending')` instead of DELETE; documented why in Known Limitations |
| HW3 | HIGH | Phase 0 T0.3 added optional cancellation probe; informs `extra` status tolerance policy |
| HW4 | HIGH | `compute_window()` function explicitly ends at `yesterday PHT`, not today; MUST_CONTAIN assertion added |
| MW1 | MEDIUM | Script reinstalls own SIGINT handler after import; documented in Known Limitations |
| MW2 | MEDIUM | `fetch_mosaic_count` inherits full retry/429/5xx loop from `fetch_orders_page`; per-call `time.sleep(REQUEST_INTERVAL)` in main loop |
| MW3 | MEDIUM | Decision documented: `refresh-sales-dashboard-views` runs every hour (UNGATED) for dashboard freshness; added workflow comment |
| MW4 | MEDIUM | `MOSAIC_ORDERS_URL` explicitly added to import list |
| MW5 | MEDIUM | `supabase_count()` full code block inlined (not "copy from file X") |
| MW6 | MEDIUM | `send_chat_alert` + `send_chat_summary` full code blocks inlined |
| MW7 | MEDIUM | L3 destructive test T4.6 now has backup (CREATE TEMPORARY TABLE) + restore procedure + row count verification |
| MW8 | MEDIUM | Phase 6 T6.2 spells out explicit `git add -f` file list including all `output/l3/s165/*` evidence |
| MW9 | MEDIUM | Exit semantics: 0 on handled-via-alert, 2 on Sentry DSN missing, 3 on all credential groups failed; prevents dual alerting with notify-failure |
| MW10 | MEDIUM | One-line comment in `fetch_mosaic_count` references `sync_pos_to_supabase.py:315` as known-working precedent for httpx bracket encoding |

**Phase budget impact:** 28 → 38 units (+10). Still within 80-unit single-session ceiling. Phase distribution: 0(5), 1(2), 2(10), 3(6), 4(8), 5(2), 6(5). No phase exceeds 15-unit hard limit.

**No features cut. No deferrals. Every finding closed in-plan.**
