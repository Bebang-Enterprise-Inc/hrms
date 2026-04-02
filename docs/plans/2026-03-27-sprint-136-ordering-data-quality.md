---
canonical_sprint_id: S136
display: Sprint 136
status: COMPLETED
branch: s136-ordering-data-quality
lane: single
created_date: 2026-03-27
completed_date: 2026-04-02
deployed_at: 2026-03-28
backend_pr: 378, 381, 404, 407
frontend_pr: 273
l3_result: Superseded by S154
execution_summary: All 10 data quality defects fixed across multiple PRs. Route map, RBAC, stock display, demand calculation all corrected. Superseded by S154 which rebuilds the ordering page on top of these fixes.
depends_on: S129
---

# S136 — Store Ordering Data Quality Fixes

**Goal:** Fix the 10 defects found during S133 L3 testing that make the store ordering page untrustworthy: wrong stock on hand, absurd suggested quantities, inflated demand, misleading labels, polluted store picker, and circular source warehouse routing.

**Origin:** L3 testing on 2026-03-27 as sam@bebang.ph against Araneta Gateway. Full defect report: `output/l3/S133/DEFECTS.md`. API data dump: `output/l3/S133/full_api_dump.json`.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

S129 redesigned the store ordering UI but the underlying data is broken:

1. **On Hand = 0 for ALL items** despite the store having 86 items with real stock. The frontend composite hook `useStoreOrdering` merges `useStoreStock` + `useOrderableItems` but the merge fails — orderable items don't carry store stock, and the hook may not be matching item_codes correctly between the two sources.

2. **Suggested qty = 1670 for SCOTCH BRIGHT** (a cleaning supply). The heuristic formula uses `last_order_qty=538.06` (suspiciously high) × 3-day coverage window × safety buffer. With ATP=0 (no source stock to subtract), the full demand becomes the suggestion.

3. **Demand/Day = 1452.5** — the API returns `forecast_demand` which is a 3-day TOTAL, not daily. The `avg_daily_demand` field (484.26) exists but the frontend reads the wrong field.

4. **"Commissary" column is wrong** — items source from 3MD Logistics (FROZEN) or from the store itself (DRY). The label should say "Source Stock" and show available qty at the source warehouse, not "Commissary."

5. **DRY items source from the store itself** — `_resolve_store_order_source_warehouse()` falls back to the store warehouse when no BEI Route exists for DRY lane. This makes ATP = store stock, which is circular. DRY items should route to Jentec (per `docs/scm/SCM_PROCESS_MASTER.md`).

6. **Store picker shows 115 entries** including 34 "Finished Goods", 34 "Work In Progress", and test stores. Only ~46 are real stores.

### Key decisions

- **D1:** Demand/Day column shows `avg_daily_demand` field (per-item, already returned by API), not `forecast_demand` (multi-day total).
- **D2:** Suggested qty formula: do NOT change the coverage_window multiplier — it's intentional for reorder quantity. But the formula should subtract actual store stock from the suggested qty so that items already in stock get lower suggestions.
- **D3:** "Commissary" column renamed to "Source Avail." with the source warehouse short name in a tooltip.
- **D4:** DRY default source warehouse = Jentec (Pasig). This must be configurable via BEI Route DocType, but we add a hardcoded fallback for now and log a data task to create proper routes.
- **D5:** Store picker filter expanded with "Finished Goods", "Work In Progress", "Raw Materials", "TEST-STORE" in the name blocklist.

### Source references

- Defect report: `output/l3/S133/DEFECTS.md`
- API data dump: `output/l3/S133/full_api_dump.json`
- Demand heuristic: `hrms/api/store.py:1553` (`_estimate_projected_sales_and_bom`)
- Source warehouse routing: `hrms/utils/supply_chain_contracts.py:321` (`resolve_route_source_warehouse`)
- Store order source: `hrms/api/store.py:1256` (`_build_orderable_source_stock_context`)
- Frontend hook: `bei-tasks/hooks/use-store-ordering.ts`
- SCM process: `docs/scm/SCM_PROCESS_MASTER.md` (north→3MD, south→Pinnacle, DRY→Jentec)

---

## Scope (28 units)

### Phase 1: Backend Data Fixes (12 units)

| Task | Type | Repo | File | Description | Units |
|------|------|------|------|-------------|-------|
| B1 | FIX | bei-erp | `hrms/api/store.py` | **[FIX] Store picker: block Finished Goods, WIP, Raw Materials, TEST-STORE.** Add `"Finished Goods"`, `"Work In Progress"`, `"Raw Materials"` to `_NON_ORDERABLE_NAME_PATTERNS` and `"TEST-STORE"` as a prefix check. **HARD BLOCKER:** Do NOT block "Finished Goods - BK" if it's a valid BK warehouse — check warehouse tree first. | 1 |
| B2 | FIX | bei-erp | `hrms/api/store.py` | **[FIX] Subtract store stock from suggested qty.** In `get_orderable_items()`, after computing the recommendation contract, look up the store's actual_qty for the item (via tabBin query already available in the function scope or add one) and set `suggested_qty = max(0, suggested_qty - store_actual_qty)`. This prevents suggesting 1670 when the store already has 500. **HARD BLOCKER:** Only subtract store stock, NOT source warehouse stock (ATP). ATP subtraction is already done in the formula. | 3 |
| B3 | FIX | bei-erp | `hrms/api/store.py` | **[FIX] Add `store_actual_qty` field to orderable item response.** Query `tabBin` for the store warehouse + item_code and include `store_actual_qty` in each item returned by `get_orderable_items()`. This allows the frontend to show On Hand correctly even if the composite hook merge fails. | 2 |
| B4 | FIX | bei-erp | `hrms/api/store.py` | **[FIX] DRY fallback source warehouse = Jentec.** In `_build_orderable_source_stock_context()`, when `_resolve_store_order_source_warehouse()` returns the store itself (circular), replace with Jentec for DRY items. Add constant `_DRY_FALLBACK_SOURCE = "Jentec Storage Inc. - Bebang Enterprise Inc."`. Log a warning when the fallback is used so we know which stores need BEI Route records. **HARD BLOCKER:** Only apply fallback when source_warehouse == store_warehouse (circular). If a real route exists, use it. | 3 |
| B5 | FIX | bei-erp | `hrms/api/store.py` | **[FIX] Add `source_warehouse_short` field to response.** Strip " - Bebang Enterprise Inc." from source_warehouse for display. Return as `source_warehouse_short` (e.g., "3MD Logistics – Camangyanan", "Jentec Storage Inc."). | 1 |
| B6 | INVESTIGATE | bei-erp | `hrms/api/store.py` | **[INVESTIGATE] Audit last_order_qty anomalies.** Query the 10 items with highest `last_order_qty` for Araneta Gateway. Check if the source BEI Store Order records are real or test data. Write findings to `output/l3/S136/last_order_audit.json`. If test orders are inflating values, document for manual cleanup. | 2 |

### Phase 2: Frontend Fixes (10 units)

| Task | Type | Repo | File | Description | Units |
|------|------|------|------|-------------|-------|
| F1 | FIX | bei-tasks | `hooks/use-store-ordering.ts` | **[FIX] On Hand: read `store_actual_qty` from orderable API.** The composite hook currently tries to merge stock API + orderable API by item_code, but the merge fails (orderable dominates). Instead, read the new `store_actual_qty` field directly from the orderable item response (added by B3). Set `actual_qty = oi.store_actual_qty ?? si?.actual_qty ?? 0`. | 3 |
| F2 | FIX | bei-tasks | `_components/OrderItemTable.tsx` | **[FIX] Demand/Day: show `avg_daily_demand` not `forecast_demand`.** Change the Demand/Day column to read `item.forecast_demand` → `item.avg_daily_demand`. If `avg_daily_demand` is not on the `StoreOrderItem` type, add it to the interface and populate from the API. Display with 1 decimal place. | 2 |
| F3 | FIX | bei-tasks | `_components/OrderItemTable.tsx` | **[FIX] Rename "Commissary" → "Source Avail."** Change the column header. Show `item.available_to_promise` value. Add a tooltip or subtitle showing `item.source_warehouse_short` (new field from B5) so crew knows which warehouse the stock comes from. | 2 |
| F4 | FIX | bei-tasks | `_components/OrderSummaryStrip.tsx` | **[FIX] Rename "OOS Commissary" KPI → "OOS at Source".** The count is still meaningful but the label is misleading. | 1 |
| F5 | FIX | bei-tasks | `hooks/use-store-ordering.ts` | **[FIX] Add `avg_daily_demand` and `source_warehouse_short` to StoreOrderItem interface.** Read from orderable item API response. | 1 |
| F6 | FIX | bei-tasks | `_components/OrderItemCard.tsx` | **[FIX] Mobile card: show avg_daily_demand, rename Commissary.** Same changes as F2/F3 but for the mobile card view. | 1 |

### Phase 3: L3 Retest + Closeout (6 units)

| Task | Type | Repo | File | Description | Units |
|------|------|------|------|-------------|-------|
| T1 | L3 | both | — | **[L3] Re-run as sam@bebang.ph.** Verify: (a) picker shows ~46 real stores only, (b) On Hand matches real stock, (c) Demand/Day is daily not multi-day, (d) Suggested is reasonable, (e) "Source Avail." column shows warehouse name, (f) no circular source=store for DRY items. Run in fresh session. | 4 |
| C1 | DOC | bei-erp | — | Update plan YAML + SPRINT_REGISTRY.md. Push. | 1 |
| C2 | DOC | bei-erp | — | Update S129 plan status to COMPLETED if all L3 pass. | 1 |

**Total: 28 units**

---

## Scope Size Warning

28 units across 3 phases is well within the 80-unit ceiling and comfortable for a single session.

---

## Requirements Regression Checklist

- [ ] Does the store picker exclude Finished Goods, WIP, Raw Materials, TEST-STORE? (B1)
- [ ] Does `suggested_qty` subtract store's actual stock? (B2)
- [ ] Does the API return `store_actual_qty` per item? (B3)
- [ ] Does the DRY fallback source warehouse = Jentec (not the store itself)? (B4)
- [ ] Does the API return `source_warehouse_short`? (B5)
- [ ] Does the frontend On Hand column show real store stock? (F1)
- [ ] Does Demand/Day show `avg_daily_demand` not `forecast_demand`? (F2)
- [ ] Is the "Commissary" column renamed to "Source Avail." with warehouse tooltip? (F3)
- [ ] Is the KPI renamed from "OOS Commissary" to "OOS at Source"? (F4)
- [ ] Does the mobile card also show the corrected demand and source labels? (F6)
- [ ] Does every new/modified `@frappe.whitelist()` call `set_backend_observability_context()`?
- [ ] Is `last_order_qty` still used correctly for items that have it? (B2 — do NOT break with-history path)

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| sam@bebang.ph | Open ordering page | Store picker shows ~46 real stores, NO "Finished Goods", "WIP", "TEST-STORE" | B1 filter broken |
| sam@bebang.ph | Select Araneta Gateway | On Hand shows real values (PM001=1, OS001=6, FG002-A=10 from Bin) | B3 or F1 broken |
| sam@bebang.ph | Check Demand/Day for SCOTCH BRIGHT | Shows ~484 (avg_daily_demand) not 1452 (forecast_demand) | F2 wrong field |
| sam@bebang.ph | Check Suggested for SCOTCH BRIGHT | Shows a reasonable number (suggested - store stock) not 1670 | B2 store stock subtraction broken |
| sam@bebang.ph | Check Source Avail. column | Shows "OOS" or a number with tooltip "3MD Logistics" or "Jentec" — NOT "Commissary" | F3 label or B5 broken |
| sam@bebang.ph | Check DRY item source | source_warehouse_short shows "Jentec" not "Araneta Gateway" | B4 fallback broken |
| test.crew1@bebang.ph | Open ordering page | Single store, items load, On Hand shows real values | B3/F1 regression |

Evidence files:
```
output/l3/S136/form_submissions.json
output/l3/S136/api_mutations.json
output/l3/S136/state_verification.json
```

---

## Autonomous Execution Contract

- **completion_condition:**
  - Store picker shows only real stores (~46)
  - On Hand matches tabBin data
  - Demand/Day shows daily values (not multi-day totals)
  - Suggested qty is reasonable (accounts for store stock)
  - Source column shows warehouse name, not "Commissary"
  - DRY items source from Jentec, not the store
  - All L3 scenarios pass
  - Plan + registry updated

- **stop_only_for:**
  - B4: Jentec warehouse name in Frappe doesn't match the constant — need to verify exact name
  - B6: If last_order_qty audit reveals test data that needs manual cleanup — document and continue
  - BEI Route data creation (creating DRY routes for all stores) is out of scope — only the fallback is in scope

- **phase_sequencing:**
  - Phase 1 backend PR first → Sam merges → Phase 2 frontend PR → Sam merges → Phase 3 L3 retest

- **signoff_authority:** single-owner (Sam Karazi, CEO)

---

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch (bei-erp):** `git fetch origin production && git checkout -b s136-ordering-data-quality origin/production`
3. **Create sprint branch (bei-tasks):** `cd ../bei-tasks && git fetch origin main && git checkout -b s136-ordering-data-quality origin/main`
4. Read `hrms/api/store.py` — `get_orderable_items()` (~line 1840), `_build_orderable_source_stock_context()` (~line 1256), `_is_orderable_store()` (~line 1491).
5. Read `bei-tasks/hooks/use-store-ordering.ts` — the composite merge logic.
6. Read `output/l3/S133/DEFECTS.md` for full defect details.
7. Read `output/l3/S133/full_api_dump.json` for API data evidence.
8. Execute Phase 1 (backend), then Phase 2 (frontend).

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.
