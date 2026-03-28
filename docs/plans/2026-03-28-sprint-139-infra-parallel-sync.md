# Sprint S139 — Infrastructure Upgrade + Parallel Inventory Sync

```yaml
sprint: S139
branch: s139-infra-parallel-sync
status: IN_PROGRESS
plan_file: docs/plans/2026-03-28-sprint-139-infra-parallel-sync.md
depends_on: S138
registry_row: "| S139 | Sprint 139 | s139-infra-parallel-sync | — | IN_PROGRESS — Phase B+C code complete, Phase A blocked on cost approval. |"
execution_started: 2026-03-28
completed_date:
execution_summary: "Phase B (parallel sync code) and Phase C (infra docs) complete. Phase A (EC2 resize, worker scaling, MariaDB tuning) blocked on Sam's approval."
```

## Goal

Fix the store inventory sync to complete in under 5 minutes for all 46 stores. Upgrade the EC2 instance to handle 25-30 concurrent users at go-live. Document the entire infrastructure so no agent ever has to guess what's running on the server.

## Design Rationale (For Cold-Start Agents)

### Why this sprint exists

S138 moved 3PL warehouses to BKI and fixed the Stock Reconciliation Opening Entry issue. But the store inventory shadow sync still takes 15+ minutes for 46 stores because:

1. **1 RQ long worker** — all 46 stores serialize through one worker
2. **No per-warehouse commit** — fixed in PR #386, but still sequential
3. **22,000 DB queries** — 6 valuation rate lookups per item × 3,680 rows, uncached
4. **Sequential Google Sheet downloads** — 46 HTTP calls × ~3.5s each
5. **Gunicorn has only 2 workers** — max 2 concurrent API requests

The EC2 instance is t3.large (8GB RAM, 2 vCPU). At go-live with 25-30 concurrent users + POS sync + inventory sync, this will be insufficient.

### Current server state (investigated 2026-03-28)

**Instance:** t3.large, ap-southeast-1, 8GB RAM, 2 vCPU
**RAM at idle (9:30 AM, no users):** 3.9GB used / 3.5GB available

| Service | RAM | Purpose | Essential? |
|---------|-----|---------|------------|
| frappe_queue-long | 1.4GB (bloated) | Background jobs | Yes — restart reclaims 1.3GB |
| sheets-receiver | 486MB | Google Sheets webhook sync + POS XLSX processing | Yes |
| MariaDB | 484MB | Database (innodb_buffer_pool=128MB — untuned) | Yes |
| frappe_backend (Gunicorn) | 307MB (2 workers only) | API server | Yes — needs more workers |
| Documenso + Postgres | 422MB | E-signatures | Yes — keeping |
| ADMS (DB + API + nginx) | 133MB | Biometric attendance | Yes |
| Blip (sentinel + assistant) | 115MB | AI chatbot + monitoring | Yes |
| Others (redis, scheduler, websocket, frontend, analytics) | ~200MB | Supporting services | Yes |
| **Total** | **~3.5GB** (after queue restart) | | |

**Workers:**
- Gunicorn: 2 workers × 4 threads = 8 concurrent requests max (should be 4-8 workers)
- Queue-long: 1 worker (should be 5-8)
- Queue-short: 1 worker (adequate)

**Scheduled sync jobs (37 total in hooks.py):**
- 7:00 AM PHT: store inventory shadow sync + demand snapshot + biometric digest (all compete for 1 long worker)
- Every 10 min: shadow sync watchdog
- Sheets-receiver internal: 6h full sync, 7AM daily baseline, 2min POS processing

### Sync path map (13 active sync paths)

| Source | Trigger | Code Path | Destination | Status |
|--------|---------|-----------|-------------|--------|
| 46 store Google Sheets | Daily 7AM cron | shadow_sync → erp_sync.sync_inventory | tabBin (Stock Reconciliation) | SLOW — 15+ min |
| Ian's warehouse sheet | sheets-receiver webhook | erp_sync.sync_inventory | tabBin (Stock Reconciliation) | Working |
| Procurement sheets (7) | sheets-receiver daily baseline | erp_sync.sync_* | BEI PO, PR, GR, Supplier, etc. | Working |
| AR Aging | sheets-receiver | erp_sync.sync_ar_aging | BEI AR records | Working |
| COA + Banks | sheets-receiver | erp_sync.sync_coa/banks | Chart of Accounts | Working |
| AP Opening (Supplier SOA) | sheets-receiver | erp_sync.sync_ap_opening | Purchase Invoice | Working |
| POS daily files | sheets-receiver (scan every 30min) | POS XLSX processor | Supabase (not Frappe) | Working |
| Mosaic POS API | GHA cron 12:30AM | scripts/mosaic_daily_sync | Supabase | Working |
| ADMS checkins | GHA cron every 5min | Frappe ADMS integration | Attendance | Working |
| Weather | Frappe cron 5x/day | weather_service.collect_all | Weather cache | Working |
| Store demand snapshot | Daily 7AM cron | erp_sync.enqueue_store_demand_snapshot | Demand records | Working |

**Critical: None of these syncs should be disrupted by this sprint.**

## Scope (~18 units)

### Phase A: Infrastructure Upgrade (5 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| A1 | INFRA | **Upgrade EC2 to t3.xlarge** (16GB RAM, 4 vCPU). Stop instance → change type → start. Zero data loss (EBS volume persists). Downtime: ~2 minutes. Cost: +$61/month ($121 total). **REQUIRES SAM'S APPROVAL.** | 1 |
| A2 | INFRA | **Scale Gunicorn to 4 workers.** Update the Docker image entrypoint or site config to use `--workers=4` instead of 2. This doubles concurrent API capacity (4 workers × 4 threads = 16 concurrent). | 1 |
| A3 | INFRA | **Scale queue-long to 5 replicas.** `docker service scale frappe_queue-long=5`. This enables 5 parallel background jobs. With t3.xlarge (16GB), 5 × 300MB = 1.5GB is safe. | 1 |
| A4 | INFRA | **Tune MariaDB.** Set `innodb_buffer_pool_size=2G` (currently default 128MB on a production ERP). Set `max_connections=200`. This alone will speed up all DB queries. | 1 |
| A5 | INFRA | **Restart bloated queue-long worker.** `docker service update --force frappe_queue-long` to reclaim 1.3GB from memory leak. | 1 |

**HARD BLOCKER A1:** Sam must approve the $61/month cost increase before proceeding.
**HARD BLOCKER A3/A5:** Server-side Docker commands require deploy password.

### Phase B: Parallel Inventory Sync (8 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| B1 | BUILD | **Parallel batch enqueue.** Update `enqueue_scheduled_store_inventory_shadow_sync()` to split 46 stores into N batches (default 10) and enqueue each as a separate background job with unique `job_id`. Each batch processes ~5 stores independently. With 5 queue-long workers, 2 rounds × ~90s = ~3 min total. | 2 |
| B2 | BUILD | **Pre-fetch Item attributes.** Before the per-row loop in `_sync_inventory_rows`, bulk-fetch all Item records: `frappe.get_all("Item", fields=["name", "has_batch_no", "has_serial_no"], limit=0)` → build a dict. Eliminates ~15,000 redundant queries (3 per row × 5,000 rows). | 2 |
| B3 | BUILD | **Cache valuation rates.** Pre-fetch all Bin valuation rates: `frappe.get_all("Bin", fields=["item_code", "warehouse", "valuation_rate"], limit=0)` → build lookup dict. Eliminates ~22,000 cascade queries in `_resolve_inventory_valuation_rate()`. | 2 |
| B4 | BUILD | **Pass `store_codes` from enqueue to runner.** Update `run_scheduled_store_inventory_shadow_sync()` to accept and forward `store_codes` parameter so batched jobs only process their assigned stores. | 1 |
| B5 | VERIFY | **L3: Trigger parallel sync, verify all 46 stores have Bins with stock.** Compare Bin counts against Google Sheet row counts per store. | 1 |

**HARD BLOCKER B1:** Must not break the existing scheduled cron at 7AM PHT. The cron calls `enqueue_scheduled_store_inventory_shadow_sync()` — the new parallel version must be backward compatible. The `store_demand_snapshot_sync` runs at the same 7AM slot — it must NOT be bundled into the parallel store sync batches. Keep it as a separate single job.

**HARD BLOCKER B2/B3:** The `_sync_inventory_rows` function is shared by ALL sync paths (warehouse, store, AP opening, sheets-receiver). The pre-fetch/cache must include a fallback — if the bulk query returns empty or errors, fall back to the existing per-row query behavior. Never remove the per-row path entirely. Add Sentry context to the batch orchestration path.

**HARD BLOCKER B5:** After sync, validate that no store's Bin values differ by >20% from Google Sheet values. If they do, flag as a defect — the cache may have produced wrong valuation rates.

## Audit Amendments (2026-03-28)

### Amendment 1: Downtime Coordination
A1 (EC2 resize) and A4 (MariaDB tune) both require downtime. They MUST be done together in a single maintenance window at **2-3 AM PHT** (lowest activity, between cron cycles). Communicate to the team before the window.

### Amendment 2: Active Job Check Before Scaling
A3 (scale queue-long) and A5 (restart queue-long) MUST verify no active RQ jobs before proceeding:
```python
frappe.get_all("RQ Job", filters={"status": "started"})
```
If any jobs are running, wait for completion or schedule during the maintenance window.

### Amendment 3: Protected Sync Verification
D1 MUST verify these syncs still work after ALL changes:
- [ ] Sheets-receiver procurement sync (PR/PO/GR/Supplier)
- [ ] Sheets-receiver AP Opening sync
- [ ] Sheets-receiver COA/Banks sync
- [ ] ADMS checkin sync (GHA every 5 min)
- [ ] Mosaic POS daily sync (GHA)
- [ ] Weather sync (Frappe cron)
- [ ] Store demand snapshot (7AM cron — must be separate from parallel store sync)
- [ ] Biometric digest (7AM cron)

### Amendment 4: Rollback Plan
If B2/B3 (pre-fetch cache) causes wrong stock values:
1. Revert `_sync_inventory_rows` to per-row queries (git revert)
2. Re-run sync to correct Bin values
3. The parallel enqueue (B1) is independent and can stay

### Phase C: Infrastructure Documentation (3 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| C1 | DOCS | **Create `docs/infra/SERVER_INVENTORY.md`** — complete server inventory document. Every container, every service, RAM usage, worker counts, ports, volumes, health checks, scheduled jobs. This is the document I should have had before making claims. | 1 |
| C2 | DOCS | **Create `docs/infra/SYNC_MAP.md`** — master sync path diagram. Every data flow: source → trigger → code → destination. Dependencies between syncs. What breaks if a sync fails. | 1 |
| C3 | DOCS | **Create `docs/infra/SCALING_GUIDE.md`** — how to scale workers, upgrade instance, tune MariaDB, add containers. Include cost table, RAM budget, and safe limits per instance type. | 1 |

### Phase D: Verification + Closeout (2 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| D1 | VERIFY | After all changes: trigger full 46-store sync, verify completes in <5 min, all stores have stock, no existing syncs broken (procurement, AP, COA still work). | 1 |
| D2 | BUILD | Closeout: update plan + registry. `git add -f docs/plans/ docs/infra/` | 1 |

## L3 Workflow Scenarios

| # | Action | Expected | Failure Means |
|---|--------|----------|---------------|
| L3-1 | Call `enqueue_scheduled_store_inventory_shadow_sync(force=True)` | 10 background jobs enqueued (5 stores each). All complete within 5 minutes. | Parallel enqueue broken |
| L3-2 | Check Bin counts for all 46 stores | Every enabled store has Bins with stock > 0 | Store sync still failing for some stores |
| L3-3 | Open store ordering page for 5 different stores | On Hand shows real values, Source Avail shows 3PL stock | Sync data not reaching the ordering API |
| L3-4 | Trigger sheets-receiver procurement sync | AP, COA, Supplier, PR, PO, GR syncs still work | Infra changes broke existing syncs |
| L3-5 | Load test: 10 concurrent API requests to hq.bebang.ph | All respond within 5s (was timing out with 2 workers) | Gunicorn workers not scaled |

## Requirements Regression Checklist

- [ ] Does `enqueue_scheduled_store_inventory_shadow_sync()` split stores into parallel batches?
- [ ] Does `_sync_inventory_rows` pre-fetch Item attributes in bulk?
- [ ] Does `_sync_inventory_rows` cache valuation rates?
- [ ] Does `frappe.db.commit()` run after each SR submit?
- [ ] Is Gunicorn running with 4+ workers?
- [ ] Are there 5+ queue-long workers?
- [ ] Is `innodb_buffer_pool_size >= 1G`?
- [ ] Are procurement/AP/COA syncs unbroken after changes?
- [ ] Is store_demand_snapshot_sync kept as a SEPARATE job (not bundled into parallel batches)?
- [ ] Do B2/B3 pre-fetch functions have fallback to per-row queries on empty/error?
- [ ] Was the maintenance window (A1+A4) done at 2-3 AM PHT with no active jobs?
- [ ] Does the parallel enqueue have Sentry context on the orchestration path?
- [ ] Does `docs/infra/SERVER_INVENTORY.md` exist with all containers listed?
- [ ] Does `docs/infra/SYNC_MAP.md` exist with all sync paths?

## Agent Boot Sequence

1. Read this plan fully.
2. `git fetch origin production && git checkout -b s139-infra-parallel-sync origin/production`
3. Read `docs/plans/SPRINT_REGISTRY.md`
4. **STOP for Phase A** — infrastructure changes require Sam's deploy password and cost approval.
5. After Sam confirms A1-A5: proceed to Phase B (code changes).
6. Phase C: write documentation from investigation files at `tmp/infra-investigation.md` and `tmp/sync-paths-audit.md`.

## Autonomous Execution Contract

- **completion_condition:** All 46 stores synced in <5 min, infra docs written, existing syncs verified working
- **stop_only_for:** A1 cost approval, A3/A5 deploy password, any sync regression
- **signoff_authority:** single-owner (Sam)
- **canonical_closeout_artifacts:**
  - `docs/infra/SERVER_INVENTORY.md`
  - `docs/infra/SYNC_MAP.md`
  - `docs/infra/SCALING_GUIDE.md`
  - `output/l3/S139/` evidence files
  - Plan + registry updated

## Files Touched

**hrms repo:**
- `hrms/api/erp_sync.py` — parallel enqueue, item pre-fetch, valuation cache (B1-B4)

**Server (deploy password required):**
- EC2 instance type change (A1)
- `docker service scale frappe_queue-long=5` (A3)
- MariaDB config (A4)
- Worker restart (A5)

**Documentation (new files):**
- `docs/infra/SERVER_INVENTORY.md` (C1)
- `docs/infra/SYNC_MAP.md` (C2)
- `docs/infra/SCALING_GUIDE.md` (C3)
