# Sprint S138 — Warehouse Routing Data Integrity

```yaml
sprint_id: S138
display: Sprint 138
slug: warehouse-routing-data-integrity
branch: s138-warehouse-routing-data-integrity
status: PLANNED
planned_date: 2026-03-27
completed_date: null
depends_on: [S136, S134, S135]
total_units: 18
backend_pr: null
frontend_pr: null
l3_result: null
execution_summary: null
```

**Registry Lock Evidence:**
```
| S138 | Sprint 138 | s138-warehouse-routing-data-integrity | — | PLANNED — Warehouse routing data integrity | docs/plans/2026-03-27-sprint-138-warehouse-routing-data-integrity.md |
```

**Goal:** Fix the disconnected warehouse architecture that causes the low stock API to query empty warehouses, POs to ship to meta warehouses, and BEI Route to be full of test junk — so that inventory data is accurate, synced, and reflects real stock at real 3PL warehouses.

**Depends on:** S136 (route map merged via hrms#381), S134 (PO ship_to default), S135 (low stock API)

**Impact:**
- Luwi: Low stock dashboard shows REAL low-stock items at the 3PLs where stock actually lives (3MD, Pinnacle, Jentec) — not the empty "Stores - BEI"
- Ian: PO ship_to defaults to the correct 3PL receiving warehouse based on route map
- Operations: BEI Route DocType cleaned of 95+ test records, seeded with proper store→3PL mappings for all 47 stores × 3 cargo types

---

## Autonomous Execution Contract

```yaml
completion_condition: |
  - All 3 phases implemented and deployed
  - BEI Route has ≤10 records (clean) + 141 new records (47 stores × 3 cargo types)
  - Low stock API returns items from real 3PL warehouses
  - Plan YAML status updated to COMPLETED
  - SPRINT_REGISTRY.md updated with final status
  - L3 evidence committed to branch
stop_only_for:
  - missing_access: credentials/session not available
  - destructive_approval: deleting production data (BEI Route cleanup needs confirmation)
  - business_policy: unclear store→3PL mapping for a specific store
  - direct_overwrite: conflicting active work on same files (S136 store.py)
signoff_authority: single-owner (Sam)
deploy_handoff: PR creation → share PR# → STOP (user merges)
governor_feedback_loop: |
  REJECT: read PR comment, fix, push
  NEEDS_FIX: apply fix, push
  Merge Conflict: rebase against production, resolve, force-push
  Deploy Failure: check logs, fix if code issue
release_manager_gate: |
  git add -f output/l3/S138/ && git push after L3
confidence_threshold: reviews with confidence < 0.80 pause auto-merge
```

---

## Ownership Matrix

| File/Surface | Owner | Protected? |
|---|---|---|
| `hrms/api/procurement.py` (get_low_stock_items only) | S138 | Shared — modify only the low stock function |
| `hrms/api/procurement.py` (ship_to default) | S138 | Shared — modify only the ship_to default logic |
| `scripts/testing/setup_s138_route_cleanup.py` (new) | S138 | No — new file |

**Protected surfaces (DO NOT TOUCH):**
- Store ordering (S136 — `hrms/api/store.py`, `hrms/utils/supply_chain_contracts.py`)
- CEO approval flow (S132)
- Quick Receive / Auto-Invoice dialog (S134)
- Stock Alerts widget / dashboard (S135 frontend)
- Batch approve / duplicate (S128)

---

## Phase A: BEI Route Data Cleanup + Seeding (8 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| A1 | DATA | **Clean BEI Route junk.** Delete all BEI Route records where `route_name` contains "S026", "S027", "S037", "Codex", "probe", "Hacked", or "TEST" (95+ records). Keep only the 5 real GAP003 routes (BEI-ROUTE-0001 through 0005). Execute via `bench console` through SSM with preview-before-delete protocol. **HARD BLOCKER:** Preview the delete list and get confirmation before executing. List must be written to `tmp/s138_route_cleanup_preview.json` first. | 2 |
| A2 | DATA | **Seed proper BEI Route records.** Create 141 BEI Route records (47 stores × 3 cargo types: FC, DRY, FM) mapping each store to its correct 3PL source warehouse based on the S136 hardcoded route map in `hrms/api/store.py` (lines 1251-1322). Source warehouses: `3MD Logistics – Camangyanan - Bebang Enterprise Inc.` (~40 stores), `Pinnacle Cold Storage Solutions - Bebang Enterprise Inc.` (~30 stores), `Jentec Storage Inc. - Bebang Enterprise Inc.` (Shaw only). Each route gets a BEI Route Stop child record with the store warehouse name. **HARD BLOCKER:** Use exact warehouse names from Frappe (verify each exists before inserting). | 4 |
| A3 | DATA | **Cancel test Material Issue entries.** Cancel MAT-STE-2026-00345, MAT-STE-2026-00346, MAT-STE-2026-00347 via `bench console` to restore stock in "Stores - BEI". These were test entries created during S135 L3 testing. | 0.5 |
| A4 | VERIFY | **Verify BEI Route state.** After cleanup + seeding: count active routes (should be 141 + 5 GAP003 = 146), verify each store has FC+DRY+FM mappings, verify source warehouses are valid Frappe Warehouse names. | 1.5 |

## Phase B: Fix Low Stock API (6 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| B1 | EXTEND | **Update `get_low_stock_items()` to use real warehouses.** Remove hardcoded "Stores - BEI" default. New logic: (1) If `warehouse` param is provided, use it directly. (2) If `store` param is provided, call `resolve_route_source_warehouse(store, cargo_type)` to find the correct 3PL. (3) If neither, aggregate across ALL major source warehouses — query `SELECT DISTINCT source_warehouse FROM tabBEI Route WHERE active=1` to get the list (should be 3MD, Pinnacle, Jentec). Run the stock/consumption query against each, merge results, deduplicate by item_code (keep lowest days_remaining). **HARD BLOCKER:** The function signature must remain backward-compatible — existing callers that pass `warehouse="Stores - BEI"` must still work. Add `store` as new optional parameter. | 3 |
| B2 | EXTEND | **Update frontend dashboard API route.** Add `store` parameter to the `/dashboard/low-stock` route in `bei-tasks/app/api/procurement/[...slug]/route.ts` so the widget can optionally query per-store. The default (no store param) should trigger the aggregate mode. | 1 |
| B3 | VERIFY | **Verify low stock returns real data.** Call API with no params → should return items from 3MD/Pinnacle/Jentec with real stock and consumption data. Call with specific store → should return items from that store's source warehouse only. Sentry instrumentation on modified endpoint. | 2 |

## Phase C: Fix PO ship_to Default + Deploy (4 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| C1 | EXTEND | **Update PO ship_to to use route map.** In `create_purchase_order()`, after the existing "Stores - BEI" default, add an override: if the PO has a `delivery_warehouse` or `for_store` field, call `resolve_route_source_warehouse()` to find the correct receiving 3PL. If no store context, keep "Stores - BEI" as the centralized receiving point. **HARD BLOCKER:** Do NOT remove the "Stores - BEI" fallback — it's correct for POs without store context (general procurement). Only override when a specific store is known. | 1.5 |
| C2 | DEPLOY | Create PR for hrms targeting production. Share PR numbers with user. Update SPRINT_REGISTRY.md with PR number. | 0.5 |
| C3 | L3 | Generate L3 handoff prompt for fresh session testing. | 0.5 |
| C4 | CLOSEOUT | Update plan YAML status. Update SPRINT_REGISTRY.md. `git add -f` for docs/ and output/l3/S138/. | 1.5 |

---

## L3 Workflow Scenarios

| # | Type | User | Action | Expected Outcome | Failure Means |
|---|------|------|--------|-------------------|---------------|
| L3-1 | happy | sam@bebang.ph | GET `/api/method/hrms.api.procurement.get_low_stock_items` with no params | Returns items from 3MD/Pinnacle/Jentec warehouses (not "Stores - BEI"). `items` array has entries with `warehouse` field showing real 3PL names. | Low stock API still hardcoded to "Stores - BEI" |
| L3-2 | happy | sam@bebang.ph | GET low-stock with `warehouse=3MD Logistics – Camangyanan - Bebang Enterprise Inc.` | Returns items ONLY from 3MD. All items have `warehouse` = 3MD. Count > 0 (3MD has 151 items with stock). | Warehouse filter not working |
| L3-3 | happy | test.hr@bebang.ph | Navigate to procurement dashboard → Stock Alerts widget | Widget shows low-stock items from real warehouses. Items have actual stock quantities (not 0). | Frontend not passing correct params or API broken |
| L3-4 | adversarial | sam@bebang.ph | GET low-stock with `warehouse=NONEXISTENT-WAREHOUSE` | Returns empty items array, status 200. No crash. | Missing error handling |
| L3-5 | happy | sam@bebang.ph | Count active BEI Route records via API | Total active routes ≥ 141. Each of the 47 stores has FC+DRY+FM entries. Source warehouses are only 3MD/Pinnacle/Jentec. | Route seeding incomplete |
| L3-6 | happy | sam@bebang.ph | GET low-stock with threshold 3, 7, 30 (aggregated mode) | count(3d) ≤ count(7d) ≤ count(30d). Monotonicity verified with real data. Response fields: item_code, current_stock, daily_consumption, days_remaining all present. | Aggregation or dedup broken |

---

## Design Rationale (For Cold-Start Agents)

1. **Why this exists.** S134/S135 L3 testing (2026-03-27) discovered that "Stores - BEI" — the default warehouse for POs and low stock — has 31 qty of test data while real inventory (700K+ qty across 51 warehouses) lives in "- Bebang Enterprise Inc." suffix warehouses like `3MD Logistics – Camangyanan - Bebang Enterprise Inc.`. The S136 fix (hrms#381) added a hardcoded route map for store ordering but the BEI Route DocType had 100 records — 95+ being test junk from S026/S027/S037 sprints.

2. **Why clean BEI Route instead of just using the hardcoded map.** The hardcoded map in `store.py` is a fallback. The intended architecture is BEI Route DocType as the SSOT for store→3PL mappings. Cleaning junk and seeding proper records makes the DocType authoritative, which means future features (expected deliveries, route optimization) can query it directly.

3. **Why aggregate across 3PLs for low stock.** "Stores - BEI" is a meta/transit warehouse — physical stock lives at 3MD (~40 stores, 151 items), Pinnacle (~30 stores, 69 items), and Jentec (Shaw only, 4 items). The low stock API must query WHERE THE STOCK IS, not where POs are addressed. Aggregating across all 3PLs with dedup gives the procurement team a single view of what's running low.

4. **Why keep "Stores - BEI" as PO ship_to fallback.** For general procurement (no store context), "Stores - BEI" is the centralized receiving point. Only when a PO is for a specific store should the route map override to the correct 3PL. Removing the default entirely would break existing PO creation.

5. **Store→3PL mapping source.** The mapping comes from the Central Warehouse Excel ("MARCH 2026 Central WHSE Inventory Monitoring_BEI.xlsx") already hardcoded in S136's `store.py` lines 1251-1322. This sprint extracts that into BEI Route records so it's queryable, not hardcoded.

---

## Requirements Regression Checklist

- [ ] Does `get_low_stock_items()` query real 3PL warehouses (3MD, Pinnacle, Jentec) — NOT "Stores - BEI"?
- [ ] Is the function signature backward-compatible (existing `warehouse` param still works)?
- [ ] Is there a new `store` param that uses `resolve_route_source_warehouse()`?
- [ ] Does the aggregate mode (no params) query all active BEI Route source warehouses?
- [ ] Are BEI Route test records deleted (S026/S027/S037 junk)?
- [ ] Are proper BEI Route records created (47 stores × 3 cargo types)?
- [ ] Do BEI Route records use EXACT Frappe warehouse names (verified before insert)?
- [ ] Is "Stores - BEI" still the fallback for POs without store context?
- [ ] Does PO ship_to override to 3PL only when store context exists?
- [ ] Are test Material Issue entries (MAT-STE-2026-00345/346/347) cancelled?
- [ ] Does every new/modified `@frappe.whitelist()` endpoint call `set_backend_observability_context()`?
- [ ] Are module and action parameters correct for Sentry project `bei-hrms`?
- [ ] Does the plan NOT touch `hrms/api/store.py` or `hrms/utils/supply_chain_contracts.py` (S136 protected)?

---

## Evidence Sources

| Source | What It Proves |
|--------|----------------|
| `tmp/warehouse-routing-investigation.md` | Full investigation findings (2026-03-27) |
| `hrms/api/store.py:1251-1322` | Hardcoded route map from Central Warehouse Excel |
| `hrms/api/procurement.py:6642-6728` | Current low stock API with "Stores - BEI" default |
| `docs/erp/WAREHOUSE_TREE_2025-12-31.csv` | Canonical warehouse structure (43 stores, 4 3PLs) |
| Frappe `tabBEI Route` | Current state: 100 records, 95+ test junk |
| Frappe `tabBin` | Stock distribution: 51 BEI warehouses with stock, 0 per-store company warehouses |

---

## Execution Workflow
- Test Python changes: `/local-frappe`
- Deploy changes: `/deploy-frappe`
- Full workflow: `/agent-kickoff`
- E2E testing: `/e2e-test` or `/test-full-cycle`

---

## Agent Boot Sequence
1. Read this plan fully.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s138-warehouse-routing-data-integrity origin/production`. NEVER write code on production.
3. Read `docs/plans/SPRINT_REGISTRY.md` for cross-sprint context.
4. Read `tmp/warehouse-routing-investigation.md` for the full warehouse investigation.
5. Read `hrms/api/store.py` lines 1251-1322 for the hardcoded route map (source data for BEI Route seeding).
6. Confirm S136 (hrms#381) is merged before starting.

## Execution Authority
This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

---

## Revision History

- **v1 (2026-03-27):** Initial plan. Scope from warehouse routing investigation during S134/S135 L3 testing. 18 units across 3 phases. Depends on S136 route map fix (hrms#381, merged 2026-03-27).
