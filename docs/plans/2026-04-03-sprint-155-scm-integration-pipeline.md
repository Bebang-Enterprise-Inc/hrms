---
canonical_sprint_id: S155
display: Sprint 155
status: IN_PROGRESS
branch: s155-scm-integration-pipeline
lane: single
created_date: 2026-04-03
execution_started: 2026-04-03
completed_date:
deployed_at:
backend_pr: "#425"
frontend_pr: "BEI-Tasks#314"
l3_result:
execution_summary:
depends_on: S154
---

# S155 — SCM Integration: Complete S154 + Unify Schedule/Route/Demand

**Goal:** Fix everything S154 broke or skipped, then integrate delivery schedule + route planner + BOM demand pipeline into one unified SCM workflow where schedule drives routes, BOM drives demand projections, and stores see real suggested quantities.

**Origin:** S154 honest audit (2026-04-03) found 36% actual completion rate — 14/39 tasks truly done, 10 partial, 5 broken, 10 never executed. CEO review identified disconnected features and fabricated data (TRUCK_CAPACITY=15).

**Audit source:** `tmp/s154_honest_audit.md`

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

S154 built scripts that were never run, referenced Custom Fields that don't exist in the database, and created two SCM features (delivery schedule + route planner) that don't talk to each other. The store ordering page is broken because `custom_store_category` crashes the SQL. The demand pipeline has zero data. The delivery schedule has zero entries.

### Why integrate schedule + route planner + demand

Currently:
- **Delivery Schedule** sets WHICH stores get deliveries on which days — but has no awareness of truck capacity or order volume
- **Route Planner** optimizes HOW to deliver — but doesn't read from the schedule and can't auto-load stores for a day
- **BOM Demand** projects HOW MUCH each store needs — but was never run, so all demand = 0

The integrated flow should be:
1. SCM sets weekly schedule (which stores, which days, COLD/DRY)
2. BOM pipeline runs nightly, writes demand snapshots per store per item
3. When Route Planner opens for a day, it auto-loads stores from the published schedule + their projected demand weight from BOM snapshots
4. Route optimizer groups stores into trucks based on real projected kg (not arbitrary store count)
5. Store ordering page shows real suggested quantities based on BOM demand + delivery coverage window

### Key decisions

- **TRUCK_CAPACITY is weight-based, not store count.** The route planner already has truck profiles (L300=800kg, 2T=1500kg, 4T=3000kg, 6W=4500kg). The Daily Route View should show weight utilization per truck, not "2/15 stores."
- **Full rebuild required.** Custom Fields (`custom_store_category` on Item, `custom_territory_cluster` on Warehouse) exist in fixtures but need `bench migrate`. This sprint MUST start with a full Docker rebuild (`skip_build=false`).
- **Pipeline must EXECUTE, not just exist.** Scripts were written in S154 but never run. This sprint runs them for real and verifies the data appears in the ordering page.
- **Emergency triple approval chain must be IMPLEMENTED.** S154 left a comment. This sprint writes the actual approval logic.

### Source references

- S154 honest audit: `tmp/s154_honest_audit.md`
- Truck profiles: `hrms/api/route_planner_data.py` — L300/2T/4T/6W with kg_limit + m3_limit
- Route planner API: `hrms/api/route_planner.py` — `get_store_orders_for_date()`, `optimize_route()`, `recommend_truck()`
- BOM pipeline: `scripts/build_demand_snapshots.py`
- Delivery schedule APIs: `hrms/api/store.py` lines 5985-6442
- Store ordering: `hrms/api/store.py` `get_orderable_items()` line 2205
- Truck capacity research: `tmp/research_truck_capacity.md`

---

## Scope (72 units)

### Phase 0: Full Rebuild + Custom Field Migration (4 units)

| Task | Type | Description | Units | MUST_VERIFY |
|------|------|-------------|-------|-------------|
| R0 | DEPLOY | **Request full rebuild (skip_build=false).** User (Sam) triggers. Agent verifies by calling `get_orderable_items` API and confirming no `custom_store_category` SQL crash. | 2 | `curl hq.bebang.ph/api/method/hrms.api.store.get_orderable_items?store=...` returns 200 |
| R0b | VERIFY | **Verify both Custom Fields exist in DB.** Query: `SELECT fieldname FROM tabCustom Field WHERE dt='Item' AND fieldname='custom_store_category'` and same for Warehouse `custom_territory_cluster`. | 2 | Both queries return 1 row |

**HARD BLOCKER:** Phase 1+ cannot start until R0 confirms Custom Fields exist. If the rebuild hasn't happened, STOP and tell the user.

### Phase 1: Fix S154 Broken Backend (10 units)

| Task | Type | File | Description | Units | MUST_MODIFY | MUST_CONTAIN |
|------|------|------|-------------|-------|-------------|--------------|
| FX1 | FIX | `store.py` | **[FIX] Remove has_field() workaround.** After R0 confirms fields exist, revert the `has_field()` checks added in PRs #422-#424 back to direct field references. **Must remove ALL 3 instances:** line 2208 (`custom_store_category`), line 6056 (`custom_territory_cluster`), line 6432 (`custom_territory_cluster`). | 2 | `hrms/api/store.py` | No `has_field("custom_store_category")` AND no `has_field("custom_territory_cluster")` — fields are now guaranteed to exist |
| FX2 | FIX | `store.py` | **[FIX] F10 triple approval chain — IMPLEMENT, not comment.** Three modifications required: (1) `_resolve_order_approval_routing` (line 1022) currently receives `is_emergency` but ignores it — must add chain logic returning 3 approvers when `is_emergency=True`. (2) Replace the comment block at line 2583 with actual chain creation code using `BEI Approval Queue`. (3) Fix `is_emergency: False` hardcoded literal at line 2766 — must use `bool(is_emergency_flag)`. All 3 approvers must approve: Area Supervisor, Regional Manager (Edlice), SCM. | 3 | `hrms/api/store.py` | `approval_chain` OR `BEI Approval Queue` in the emergency block (not just a comment) AND `_resolve_order_approval_routing` uses `is_emergency` parameter AND no hardcoded `"is_emergency": False` |
| FX3 | FIX | `store.py` | **[FIX] `copy_week` needs savepoint (DM-2).** Wrap destructive entries clear + save in `frappe.db.savepoint()`. | 1 | `hrms/api/store.py` | `frappe.db.savepoint("copy_week")` |
| FX4 | FIX | `store.py` | **[FIX] `get_weekly_schedule` needs permission check.** Currently no auth — any user can see all stores. Add read-level SCM role check. | 1 | `hrms/api/store.py` | `check_scm_permission` in `get_weekly_schedule` |
| FX5 | FIX | `route.ts` | **[FIX] API route input validation.** Add allowlist for action params. Validate POST body has expected keys. Return 401 if no auth. | 2 | `bei-tasks/app/api/delivery-schedule/route.ts` | `if (!action \|\| !GET_METHODS[action])` AND auth check |
| FX6 | FIX | `page.tsx` | **[FIX] Replace `window.prompt()` with Shadcn Dialog for unpublish reason.** | 1 | `bei-tasks/app/dashboard/scm/delivery-schedule/page.tsx` | `Dialog` OR `AlertDialog` (not `prompt(`) |
| FX7 | VERIFY | `store.py` | **[VERIFY] `_is_orderable_store` receives dict at all call sites.** PRs #419-#424 fixed this but FX1 cleanup may reintroduce the bug. Grep for all `_is_orderable_store(` calls and verify each passes a dict/row, not `wh.name` string. | 1 | `hrms/api/store.py` | All `_is_orderable_store(` calls pass a dict (not `.name` string) |

### Phase 2: Execute Pipeline + Seed Data (12 units)

| Task | Type | Description | Units | MUST_VERIFY |
|------|------|-------------|-------|-------------|
| EX1 | DATA | **[DATA] Run item classification script.** Execute `python scripts/s154_classify_store_items.py` against production. Verify items have `custom_store_category` values. | 2 | `curl .../api/resource/Item?filters=[["custom_store_category","!=",""]]&limit=5` returns items with categories |
| EX1b | DATA | **[DATA] Run store-consumption BOM loader.** Execute `python scripts/s154_load_store_boms.py` against production. Verify BOM records exist for the 15 POS products. This is S154 D2 which was never run. | 2 | `curl .../api/resource/BOM?filters=[["custom_bom_type","=","Store Consumption"]]&limit=5` returns BOMs |
| EX3 | DATA | **[DATA] Run delivery schedule seed.** Execute `python scripts/s154_seed_delivery_schedule.py`. Verify schedule entries exist and first week is published. **Must run before EX2a — the pipeline needs schedule data to compute per-store coverage.** | 2 | `curl .../api/method/hrms.api.store.get_weekly_schedule?week_start=2026-03-31` returns `entry_count > 0` |
| EX2a | FIX | **[FIX] Pipeline must read delivery schedule for coverage window.** `build_demand_snapshots.py` line 541 hardcodes `coverage = coverage_override or 3` for ALL stores. This defeats the schedule→ordering integration. Modify to query `BEI Delivery Schedule Entry` for each store's actual delivery frequency per cargo type (COLD/DRY). Stores with daily delivery should get coverage=1, weekly stores coverage=7, etc. **HARD BLOCKER: Without this fix, suggested_qty will be wrong for ~80% of stores.** **Requires EX3 to have seeded the schedule first.** | 2 | Verify: run pipeline for 2 stores with different delivery frequency → coverage_window_days differs between them |
| EX2b | DATA | **[DATA] Run BOM demand pipeline for ALL stores.** Execute `python scripts/build_demand_snapshots.py`. Verify `BEI Inventory Risk Snapshot` records exist. **Execution order: EX1b → EX3 → EX2a → EX2b.** | 4 | `curl .../api/resource/BEI Inventory Risk Snapshot?limit=5` returns records with `avg_daily_demand > 0` AND varying `coverage_window_days` per store |
| EX4 | VERIFY | **[VERIFY] Ordering page shows real demand.** Open ordering page for Araneta Gateway. Verify `avg_daily_demand > 0` for at least 5 items. Verify `suggested_qty > 0` for items with demand. Verify delivery banner shows dates from published schedule (not defaults). | 4 | Playwright: open ordering page, check demand values are non-zero, banner shows real delivery dates |

**HARD BLOCKER on EX2:** Requires Supabase credentials from Doppler (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`) and Frappe API credentials (`FRAPPE_API_KEY`, `FRAPPE_API_SECRET`). If credentials fail, STOP.

### Phase 3: Integrate Schedule → Route Planner (14 units)

| Task | Type | File | Description | Units | MUST_MODIFY | MUST_CONTAIN |
|------|------|------|-------------|-------|-------------|--------------|
| INT1 | BUILD | `route_planner.py` | **[BUILD] `get_stores_for_delivery_date` — reads published schedule.** New function: given a date + goods_type (cold/dry), return stores scheduled for delivery that day from `BEI Delivery Schedule Entry`. Falls back to `get_store_orders_for_date` if no schedule exists. **HARD BLOCKER — STORE NAME NORMALIZATION REQUIRED:** The schedule stores Warehouse names (`"ARANETA CITY - BEI"`) but `STORE_DATA` in `route_planner_data.py` uses display names (`"Araneta City"`). This function MUST normalize warehouse names to STORE_DATA keys (strip ` - BEI` suffix + title-case) or the lookup at `store_data.get(s["store"])` in `optimize_route` will return `{}` for every store, producing default coordinates (0,0). Also fix the hardcoded `datetime(2026, 4, 1)` at line 273 in `_generate_option` to use `datetime.now()`. | 3 | `hrms/api/route_planner.py` | `def get_stores_for_delivery_date` AND `BEI Delivery Schedule` AND warehouse-to-display name normalization |
| INT2 | BUILD | `route_planner.py` | **[BUILD] `get_projected_load_for_store` — reads BOM demand.** New function: given store + date, query `BEI Inventory Risk Snapshot` for all items, sum projected weight using the EXISTING `_get_sku_weights()` at line 45. **Do NOT recreate this function — it already exists and reads from the embedded SKU_MASTER seed.** Returns total_kg, total_m3, item_count. Must use the same warehouse name normalization from INT1 when matching snapshot warehouse to STORE_DATA. | 3 | `hrms/api/route_planner.py` | `def get_projected_load_for_store` AND `BEI Inventory Risk Snapshot` AND `_get_sku_weights()` call |
| INT3 | BUILD | `route_planner.py` | **[BUILD] `load_orders_from_schedule` — combine schedule + demand.** Replaces manual store selection. Called when "Load Orders" is clicked: reads schedule for the day → for each store, gets projected load → returns store list with projected kg/m3. | 4 | `hrms/api/route_planner.py` | `def load_orders_from_schedule` |
| INT4 | BUILD | `route_planner.py` | **[BUILD] Update `optimize_route` to use projected weight.** When stores come from schedule+demand (not manual selection), use projected kg for truck recommendation instead of actual order line items. | 2 | `hrms/api/route_planner.py` | `projected_kg` OR `projected_load` in optimize_route |
| INT5 | BUILD | `page.tsx` | **[BUILD] Daily Route View reads from route planner truck profiles.** Replace hardcoded `TRUCK_CAPACITY=15` (line 330 in delivery-schedule/page.tsx) with real truck profile data from route planner API. Show weight utilization (projected_kg / truck_kg_limit) instead of store count. **NOTE: TRUCK_CAPACITY=15 is in the FRONTEND file, NOT in store.py.** | 2 | `bei-tasks/app/dashboard/scm/delivery-schedule/page.tsx` | No `TRUCK_CAPACITY = 15` — removed. Contains weight-based utilization display |

### Phase 4: Unified SCM Page (14 units)

| Task | Type | File | Description | Units | MUST_MODIFY | MUST_CONTAIN |
|------|------|------|-------------|-------|-------------|--------------|
| UX1 | BUILD | `page.tsx` | **[BUILD] Daily Route View reads real truck data.** Replace `TRUCK_CAPACITY=15` / `2/15` display with weight-based utilization from route planner API. Show `projected_kg / truck_kg_limit` per route. E.g., "850kg / 1,500kg (57%)" instead of "2/15". | 4 | `bei-tasks/app/dashboard/scm/delivery-schedule/page.tsx` | No `TRUCK_CAPACITY` constant. Contains `projected_kg` OR `kg_limit` |
| UX2 | BUILD | `page.tsx` | **[BUILD] "Load into Route Planner" button on Daily Route View.** When viewing a day, button opens Route Planner pre-filled with that day's stores + goods type from the schedule. Deep link: `/dashboard/scm/route-planner?date={date}&goods_type={type}&from_schedule=1`. | 2 | `bei-tasks/app/dashboard/scm/delivery-schedule/page.tsx` | `route-planner` link with `from_schedule` |
| UX3 | BUILD | `route-planner page` + `route.ts` | **[BUILD] Route Planner auto-loads from schedule.** When URL has `from_schedule=1`, call `load_orders_from_schedule` API instead of showing manual store selection. Show projected weight per store. "Optimize Routes" uses projected kg. **Must also add 3 new entries to METHOD_MAP in `bei-tasks/app/api/route-planner/route.ts`:** `load_orders_from_schedule`, `get_stores_for_delivery_date`, `get_projected_load_for_store` — without these, the API proxy returns `{ error: "Unknown method" }` for all INT1-INT3 calls. | 4 | `bei-tasks/app/dashboard/scm/route-planner/page.tsx` AND `bei-tasks/app/api/route-planner/route.ts` | `from_schedule` AND `load_orders_from_schedule` in page.tsx AND 3 new METHOD_MAP entries in route.ts |
| UX4 | BUILD | `page.tsx` | **[BUILD] Store card shows projected demand summary.** In the Store Card slide-out, show total projected kg for COLD and DRY based on BOM demand. E.g., "Projected COLD load: 480kg (2-Ton fits)". | 2 | `bei-tasks/app/dashboard/scm/delivery-schedule/page.tsx` | `projected` AND `kg` in StoreCardPanel |
| UX5 | FIX | nav | **[FIX] SCM section UX — both features accessible from same place.** Delivery Schedule and Route Planner are in the same sidebar section. Add breadcrumb linking between them. | 2 | `bei-tasks/components/layout/nav-main.tsx` | Both `Delivery Schedule` AND `Route Planner` in SCM section (already done — verify) |

### Phase 5: Ordering Page Demand Verification (8 units)

| Task | Type | Description | Units | MUST_VERIFY |
|------|------|-------------|-------|-------------|
| VF1 | VERIFY | **[VERIFY] Open ordering page in Playwright.** Login as test.crew1@bebang.ph. Navigate to Store Ordering. Verify: (a) page loads without error, (b) category tabs show with real categories (not all "Other"), (c) at least 5 items have `avg_daily_demand > 0`, (d) `suggested_qty > 0` for items with demand, (e) delivery banner shows real dates from schedule. | 4 | Playwright screenshot + console log |
| VF2 | VERIFY | **[VERIFY] Open delivery schedule in Playwright.** Login as sam@bebang.ph. Navigate to Delivery Schedule. Verify: (a) all 47 stores visible, (b) seed data shows COLD/DRY toggles, (c) click toggle works, (d) publish works. | 2 | Playwright screenshot |
| VF3 | VERIFY | **[VERIFY] Route Planner loads from schedule.** Open Route Planner with `?from_schedule=1&date=2026-04-07&goods_type=cold`. Verify stores auto-load from schedule with projected weight. | 2 | Playwright screenshot |

### Phase 6: Closeout (2 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| CL1 | DOC | Update plan YAML + SPRINT_REGISTRY.md + S154 plan status to COMPLETED_WITH_DEFECTS. Push. | 1 |
| CL2 | DOC | Update S154 plan with honest completion status referencing this sprint. Verify all 7 deferred features are tracked in S156 plan (`docs/plans/2026-04-03-sprint-156-s154-deferred-ux-polish.md`): 4 UX polish items + 3 manual route override tools. | 1 |

**Total: 74 units** (4 rebuild + 10 fixes + 14 pipeline + 14 integration + 14 UX + 8 verification + 2 closeout + 8 buffer)

> **Note:** Phase 2 increased from 12→14 units after audit added EX2a (pipeline coverage fix). EX2 was split into EX2a (fix) + EX2b (run). Execution order: EX1 → EX1b → EX3 → EX2a → EX2b → EX4.

---

## Requirements Regression Checklist

- [ ] Does the ordering page load without SQL crash? (R0)
- [ ] Do both Custom Fields exist in the DB? (R0b)
- [ ] Are ALL 3 `has_field()` workarounds removed (lines 2208, 6056, 6432)? (FX1)
- [ ] Does `_resolve_order_approval_routing` use `is_emergency` to return 3 approvers? (FX2)
- [ ] Is `is_emergency: False` literal at line 2766 fixed to use `bool(is_emergency_flag)`? (FX2)
- [ ] Does emergency order create 3 approval queue entries? (FX2 — not a comment)
- [ ] Does `copy_week` use savepoint? (FX3)
- [ ] Does `get_weekly_schedule` have permission check? (FX4)
- [ ] Are items classified into 6 categories in production? (EX1)
- [ ] Does `build_demand_snapshots.py` read delivery schedule for per-store coverage window? (EX2a — not hardcoded 3)
- [ ] Do BEI Inventory Risk Snapshot records have varying `coverage_window_days` per store? (EX2b)
- [ ] Does the published schedule have entries for this week? (EX3)
- [ ] Does the ordering page show `avg_daily_demand > 0` for items with POS sales? (EX4)
- [ ] Does `get_stores_for_delivery_date` normalize warehouse names to STORE_DATA display names? (INT1 — CRITICAL)
- [ ] Does Route Planner have `get_stores_for_delivery_date` reading from schedule? (INT1)
- [ ] Does `get_projected_load_for_store` call existing `_get_sku_weights()` (not a duplicate)? (INT2)
- [ ] Does Route Planner have `get_projected_load_for_store` reading BOM snapshots? (INT2)
- [ ] Is hardcoded `datetime(2026, 4, 1)` in `_generate_option` fixed to `datetime.now()`? (INT1/INT4)
- [ ] Is TRUCK_CAPACITY=15 removed from `bei-tasks` delivery schedule page.tsx (NOT store.py)? (INT5/UX1)
- [ ] Does Daily Route View show weight utilization (kg/kg_limit) not store count? (UX1)
- [ ] Does "Load into Route Planner" button exist on Daily Route View? (UX2)
- [ ] Does Route Planner auto-load from schedule when `from_schedule=1`? (UX3)
- [ ] Are 3 new methods added to METHOD_MAP in `bei-tasks/app/api/route-planner/route.ts`? (UX3)
- [ ] Does every modified `@frappe.whitelist()` call `set_backend_observability_context()`? (Sentry)
- [ ] Has Playwright verified ordering page shows real demand? (VF1)
- [ ] Has Playwright verified delivery schedule works end-to-end? (VF2)

---

## Machine-Verifiable Phase Gates

Each phase MUST produce a verification script run. The agent writes the script BEFORE starting the phase and runs it AFTER. See `output/s155/verify_phase{N}.py`.

Evidence must come from the filesystem and live API responses, not from the agent's self-report.

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| sam@bebang.ph | Open ordering page | Page loads, items have real category tabs, demand > 0 | Pipeline not run or Custom Fields missing |
| sam@bebang.ph | Check SAGO demand | `avg_daily_demand > 0`, `suggested_qty > 0` | BOM pipeline broken |
| sam@bebang.ph | Check delivery banner | Shows real COLD/DRY dates from schedule (not "default") | Schedule not seeded or not published |
| sam@bebang.ph | Open delivery schedule | 47 stores visible with COLD/DRY toggles from seed data | Seed script not run |
| sam@bebang.ph | Toggle a cell | Cell toggles without error | check_scm_permission or other backend bug |
| sam@bebang.ph | Publish week | Schedule published, ordering page reflects it | Publish API broken |
| sam@bebang.ph | Open Daily Route, check capacity | Shows "850kg / 1,500kg (57%)" not "2/15" | TRUCK_CAPACITY still hardcoded |
| sam@bebang.ph | Click "Load into Route Planner" | Route Planner opens with schedule stores pre-loaded | Integration not wired |
| sam@bebang.ph | Click Emergency Order | Warning dialog with triple approval chain, order created | F10 still a comment |

Evidence files: `output/l3/S155/form_submissions.json`, `api_mutations.json`, `state_verification.json`

---

## Zero-Skip Enforcement

Every task MUST be implemented. If a task cannot be completed, the agent STOPS and asks the user. The agent is FORBIDDEN from: marking partial as done, deferring to next sprint, writing comments instead of code, extending interfaces instead of modifying component files, writing scripts and never executing them.

**S154 lesson:** 7 scripts were written but never run. "Deferred to after deployment" is not DONE. The pipeline MUST execute and the data MUST appear in the API response.

---

## Explicitly Deferred to S156 (NOT in scope — do NOT implement)

These S154 features are intentionally deferred. They are not forgotten — they are descoped with rationale.

**4 features → S156** (`docs/plans/2026-04-03-sprint-156-s154-deferred-ux-polish.md`):

| Feature | Original Task | Why Deferred |
|---------|--------------|--------------|
| Colored left borders (red/amber/green) on ordering items | S154 F2 | Cosmetic polish — demand accuracy is higher priority |
| SCM Order Review page (qty_dispatched display) | S154 F11 | Backend field + API exist. Frontend page on branch PR #309. Needs separate deploy. |
| Store metadata on hover in weekly grid | S154 S3 | Requires additional API data. Lower priority than schedule/route integration. |
| Collapsible warehouse groups in weekly grid | S154 S3 | UX polish — groups already show as headers. |

**3 features → S156** (manual route override tools — semi-automatic: optimizer suggests, SCM decides):

| Feature | Original Task | Why Deferred |
|---------|--------------|--------------|
| Drag-and-drop stores between routes | S154 S4 | Manual override for automated route optimization. SCM needs ability to rebalance routes after optimizer suggests. |
| "Assign Route" dropdown on Daily Route View | S154 S4 | Manual assignment for unassigned stores. Works alongside "Load into Route Planner" auto-load. |
| "Add/remove truck" buttons on Daily Route View | S154 S4 | Manual truck management. `optimize_route` recommends, SCM adds/removes trucks based on real-world judgment. |

---

## Autonomous Execution Contract

- **completion_condition:** Ordering page shows real BOM demand (avg_daily_demand > 0 for items with POS sales). Delivery schedule has seed data (200+ entries). Route planner loads from schedule with projected weight (not store count). All Playwright verifications pass. Plan YAML updated to COMPLETED. SPRINT_REGISTRY.md updated.
- **stop_only_for:** Supabase credentials not available. Full rebuild not done (R0 blocker). Frappe API returns unexpected schema change.
- **signoff_authority:** single-owner (Sam Karazi, CEO)
- **canonical_closeout_artifacts:**
  - `output/s155/RUN_STATUS.json`
  - `output/s155/RUN_SUMMARY.md`
  - `output/s155/verify_phase1.py` through `verify_phase5.py` (all PASS)
  - `docs/plans/2026-04-03-sprint-155-scm-integration-pipeline.md` (status: COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (S155 row updated)

---

## Agent Boot Sequence

1. Read this plan fully — especially Phase 0 HARD BLOCKER and the "Deferred to S156" section.
2. **bei-tasks repo location:** `F:\Dropbox\Projects\bei-tasks` (or `../bei-tasks` from bei-erp root).
3. **Verify full rebuild happened:** `curl hq.bebang.ph/api/method/hrms.api.store.get_orderable_items?store=Araneta+Gateway` must return 200 with items, not SQL crash.
4. If rebuild not done → STOP. Tell user: "Phase 0 requires full Docker rebuild (skip_build=false) to create Custom Fields."
5. Create branch: `git fetch origin production && git checkout -b s155-scm-integration-pipeline origin/production`
6. Read `hrms/api/store.py` — delivery schedule APIs (lines 5985-6442), ordering (lines 2205-2280), `_is_orderable_store()` (line 1737)
7. Read `hrms/api/route_planner.py` — `get_store_orders_for_date()` (line 461), `optimize_route()` (line 324), `recommend_truck()` (line 76), `_get_truck_profiles()` (line 51)
8. Read `hrms/api/route_planner_data.py` — `TRUCK_PROFILES` (L300=800kg, 2T=1500kg, 4T=3000kg, 6W=4500kg)
9. Read `tmp/s154_honest_audit.md` — understand what's broken and why
10. **Supabase tables used by BOM pipeline:** `pos_order_items` (join to `pos_orders` via `pos_orders.id`), `daily_weather`. Credentials: Doppler keys `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` (project `bei-erp`, config `dev`).
11. **Frappe API credentials:** Doppler keys `FRAPPE_API_KEY` + `FRAPPE_API_SECRET` (project `bei-erp`, config `dev`).
12. Verify `_is_orderable_store` receives a dict (not string) at all call sites — PRs #419-#424 fixed this but verify after FX1 cleanup.
13. Execute Phase 0-6 in order.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

**CORRECT OVER FAST RULE:** When fixing an error, ask: "Am I removing the feature or fixing the feature?" If the fix involves deleting, commenting out, or removing code/fields/features that were in the plan, STOP. That is not a fix — it is a regression.

---

## Audit Amendment Log

### v1.1 — Plan Audit (2026-04-03)

**Audit:** 7-agent audit focused on 3-feature integration (Route Planner ↔ Delivery Schedule ↔ Ordering). 8 verified blockers found, all addressable within S155 scope. Full report: `output/plan-audit/s155-scm-integration-pipeline/verified_blockers.md`

**Amendments applied:**

| # | Blocker | Amendment |
|---|---------|-----------|
| B1 | Store name mismatch (Warehouse vs display names) | Added HARD BLOCKER to INT1: must normalize warehouse names to STORE_DATA keys |
| B2 | Emergency approval is comment-only + is_emergency:False bug | Expanded FX2: must modify `_resolve_order_approval_routing` (line 1022) + fix literal (line 2766) |
| B3 | Pipeline hardcodes coverage=3 | Split EX2 into EX2a (fix pipeline) + EX2b (run pipeline). Reordered: EX3 → EX2a → EX2b |
| B4 | INT5 wrong MUST_MODIFY target | Corrected from `hrms/api/store.py` to `bei-tasks/app/dashboard/scm/delivery-schedule/page.tsx` |
| B5 | get_weekly_schedule no permission check | Already covered by FX4 — confirmed real gap |
| B6 | copy_week no savepoint | Already covered by FX3 — confirmed real gap |
| B7 | METHOD_MAP missing 3 entries | Added to UX3: must update `bei-tasks/app/api/route-planner/route.ts` |
| B8 | UX2/UX3 both greenfield | Already covered — confirmed expected new work |

**Additional fixes:** FX1 scope expanded to all 3 has_field instances. INT2 notes existing `_get_sku_weights()`. INT1/INT4 notes hardcoded `datetime(2026,4,1)` fix. Total units: 72→74.
