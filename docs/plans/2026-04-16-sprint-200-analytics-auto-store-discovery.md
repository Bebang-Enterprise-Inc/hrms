---
sprint: S200
display: Sprint 200 — Analytics Auto-Store Discovery
branch: s200-analytics-auto-store-discovery
repo: hrms
status: BLOCKED (waiting for PR #596 merge to production)
created: 2026-04-16
depends_on:
  - S199 (ALL CAPS Store-First Naming — COMPLETED)
  - S191 (FP Completeness Guard — DEPLOYED)
  - PR #596 (Structural Warehouse Filter — must be merged to production first)
completed_date:
backend_pr:
execution_summary:
registry_row: |
  | `S200` | Sprint 200 | `s200-analytics-auto-store-discovery` (hrms) | TBD | PLANNED 2026-04-16 |
---

# Sprint 200 — Analytics Auto-Store Discovery

## TL;DR

When a Company gets `mosaic_location_id` set in Frappe, it should appear in Analytics within 30 seconds. Today it doesn't — 3 layers of stale caching cause wrong store names and missing stores until a manual `bench restart`. This sprint fixes all 3 layers.

**BLOCKING NOTE (2026-04-16 Audit):** PR #596 (Structural Warehouse Filter) must be merged to production BEFORE S200 work begins. The filter is part of the requirements and already validated in the codebase.

## Design Rationale (For Cold-Start Agents)

**Why this exists:** After S199 renamed all Companies to ALL CAPS store-first, the Analytics Store Leaderboard still showed wrong names — corp names (TAJ FOOD CORP.), old warehouse formats (Bebang Mega Inc. - SM Tanza), and holding company names (TUNGSTEN CAPITAL HOLDINGS OPC). Sam's question: "Why isn't this automatic? Why do you need to do it manually?"

**Root cause — 3 layers of staleness:**

1. **Python LRU cache (permanent, never invalidates):** `hrms/utils/sales_location_mapping.py:21` uses `@lru_cache(maxsize=1)`. Once `load_sales_location_mapping()` runs, the result is cached for the **lifetime of the Gunicorn worker** (days/weeks). No hook clears it on Company/Warehouse changes. Adding a Company or setting `mosaic_location_id` has zero effect until `bench restart`.

2. **Supabase `stores` table (stale fallback):** The MV `sales_dashboard_daily_store_metrics` at `supabase/migrations/20260315_sales_dashboard_daily_metrics.sql:116` joins `stores.store_name` via `location_id`. When the primary Frappe lookup fails (because of stale LRU cache), `sales_dashboard.py:1966,2786,3386` falls back to `row.get("store_name")` from Supabase — which has pre-rename names.

3. **Display uses `warehouse_name`, not Company store prefix:** The leaderboard shows `Warehouse.warehouse_name` field (`sales_dashboard.py:1966,2786`), not the Company's store prefix. After renames, `warehouse_name` often has old mixed-case or corp-first format. The Company docname IS the SSOT — the display should derive from it.

**Why TTL cache instead of removing cache entirely:** `load_sales_location_mapping()` queries Company + Warehouse tables and builds a dictionary. Without caching, every Analytics API call would hit the DB. A 30-second TTL means: max 30s staleness after changes, max 2 DB queries per minute per worker.

**Why Company store prefix instead of warehouse_name:** The Company docname follows the `<STORE> - <CORP>` convention enforced by S199. Extracting the prefix (everything before ` - `) always gives the clean store name. The `warehouse_name` field is a stale copy that breaks on every rename.

## Requirements Regression Checklist

- [ ] Does `load_sales_location_mapping()` use a TTL cache (not permanent `@lru_cache`)?
- [ ] Is the TTL ≤ 30 seconds?
- [ ] Does the mapping return Company store prefix as `warehouse_name`, not `Warehouse.warehouse_name`?
- [ ] Does `hooks.py` register `on_update` for Company and Warehouse to clear the cache?
- [ ] Does `_filter_sales_warehouses` still log unmapped warehouses via `frappe.log_error()`?
- [ ] Does adding a new Company with `mosaic_location_id` auto-appear in Analytics within 30s (no restart)?
- [ ] Are holding companies / non-store entities excluded (entity_category filter)?
- [ ] **HARD BLOCKER:** `load_sales_location_mapping_by_id()` must also use TTL cache (not permanent).
- [ ] **HARD BLOCKER:** Structural warehouse names (Work In Progress, Finished Goods, Stores, etc.) must be filtered out of the mapping.

## Phase Budget Contract

| Phase | Units | Description |
|-------|-------|-------------|
| Phase 1 | 6 | Replace LRU cache + derive store name from Company + add hooks |
| Phase 2 | 2 | Commit + PR + closeout |
| **Total** | **8** | |

## Phase 1 — Code Changes (6 units)

| Task | Description | MUST_MODIFY |
|------|-------------|-------------|
| P1-T1 | Replace `@lru_cache(maxsize=1)` on `load_sales_location_mapping()` (line 21) and `load_sales_location_mapping_by_id()` (line 110) with a TTL cache (30 seconds). Add `clear_cache()` function. Use `time.time()` + module-level dict — no external dependency. | `hrms/utils/sales_location_mapping.py` |
| P1-T2 | In `load_sales_location_mapping()`, change `warehouse_name` payload to use Company store prefix instead of `Warehouse.warehouse_name`. Extract via `company.split(" - ", 1)[0]` for store Companies. **HARD BLOCKER:** Keep structural warehouse filter (`_STRUCTURAL_NAMES`). | `hrms/utils/sales_location_mapping.py` |
| P1-T3 | Add `on_update` hook for Company and Warehouse in `hooks.py` `doc_events` dict. Handler: `hrms.utils.sales_location_mapping.clear_cache`. This clears the TTL cache immediately on any Company/Warehouse save. | `hrms/hooks.py` |
| P1-T4 | Add `clear_cache()` function to `sales_location_mapping.py` that resets the TTL cache globals. Called by the hook in P1-T3. | `hrms/utils/sales_location_mapping.py` |
| P1-T5 | Add entity_category filter to the Company query in `load_sales_location_mapping()` — only include Companies with `entity_category in ("Store", "Commissary")` AND `operational_status in ("Active", "Pre-Opening", "Temporarily Closed", "Pipeline")`. This prevents holding companies (TUNGSTEN CAPITAL HOLDINGS OPC, BEBANG MEGA INC.) from appearing. **HARD BLOCKER:** Holding companies must NOT appear in Analytics. | `hrms/utils/sales_location_mapping.py` |
| P1-T6 | Update `hrms/tests/test_sales_location_mapping.py` — test `clear_cache()`, TTL behavior, and store prefix extraction. | `hrms/tests/test_sales_location_mapping.py` |

### Functions that MUST NOT break

| Function | File:Line | Callers | Constraint |
|----------|-----------|---------|------------|
| `lookup_location_id()` | `sales_location_mapping.py:96` | `sales_dashboard.py:504` | Return type `int \| None` unchanged |
| `lookup_sales_location()` | `sales_location_mapping.py:86` | `sales_dashboard.py` (indirect) | Return shape `dict` unchanged |
| `load_sales_location_mapping()` | `sales_location_mapping.py:22` | `marketing_giveaways.py:1096` | Return shape `dict[str, dict]` unchanged |
| `lookup_store_name_by_location_id()` | `sales_location_mapping.py:118` | various | Return type `str \| None` unchanged |
| `_filter_sales_warehouses()` | `sales_dashboard.py:501` | `sales_dashboard.py:580` | Return shape unchanged |

## Phase 2 — Commit + PR + Closeout (2 units)

| Task | Description |
|------|-------------|
| P2-T1 | Commit, push to `s200-analytics-auto-store-discovery`, create PR to production. |
| P2-T2 | Update plan YAML `status: COMPLETED`, update SPRINT_REGISTRY.md. `git add -f docs/plans/`. |

## Autonomous Execution Contract

- **completion_condition:** TTL cache replacing LRU cache. Company store prefix as display name. `on_update` hooks registered. Tests passing. PR created. Plan + registry updated.
- **stop_only_for:** Missing credentials. Destructive action requiring Sam approval.
- **continue_without_pause_through:** All phases.
- **signoff_authority:** single-owner (Sam)

## Zero-Skip Enforcement

Every task MUST be implemented. No silent skips. If a task cannot be completed, STOP and ask the user.

**Verification script (run after Phase 1):**
```bash
# P1-T1: TTL cache replaces LRU
grep -c "lru_cache" hrms/utils/sales_location_mapping.py  # expect: 0
grep -c "_CACHE_TTL\|_cache_ts" hrms/utils/sales_location_mapping.py  # expect: >= 2

# P1-T2: Company store prefix used
grep -c "company.*split.*-" hrms/utils/sales_location_mapping.py  # expect: >= 1

# P1-T3: Hook registered
grep -c "sales_location_mapping" hrms/hooks.py  # expect: >= 1

# P1-T4: clear_cache exists
grep -c "def clear_cache" hrms/utils/sales_location_mapping.py  # expect: 1

# P1-T5: entity_category filter
grep -c "entity_category" hrms/utils/sales_location_mapping.py  # expect: >= 1
```

## Agent Boot Sequence

1. Read this plan fully.
2. `git fetch origin production && git checkout -b s200-analytics-auto-store-discovery origin/production`
3. Read `hrms/utils/sales_location_mapping.py` (the primary file being modified).
4. Read `hrms/hooks.py:174-280` (the `doc_events` dict where hooks are registered).
5. Read `hrms/api/sales_dashboard.py:501-515` (`_filter_sales_warehouses`).
6. Start Phase 1.
