# S139: SCM Route Planner — Smart Delivery Optimizer

```yaml
id: S139
type: feature
status: IN_PROGRESS
created: 2026-04-01
execution_started: 2026-04-01
branch: s139-route-planner
pr: —
registry_row: "S139 | Sprint 139 | s139-route-planner | — | PLANNED"
depends_on: S138 (warehouse routing data integrity — clean route data)
owner: Sam Karazi (CEO)
estimated_units: 72
completed_date:
execution_summary:
```

## Executive Summary

Build a route planning tool in my.bebang.ph that helps the SCM team plan optimized delivery routes. The system takes store orders as input, calculates the best truck type and route sequence based on weight, volume, traffic, and cost, and displays the route on an interactive map with pins per store.

## Design Rationale (For Cold-Start Agents)

### Why This Exists
BEI's SCM team currently plans routes manually. Analysis of March 2026 data revealed:
- 25% of reefer trucks run at <25% capacity (114 of 449 cold deliveries)
- 92% of dry deliveries carry <200 kg (281 of 304)
- No visibility into traffic-adjusted delivery times
- No tool to compare route options by cost

The existing `BEI Route` and `BEI Distribution Trip` DocTypes (S138) handle route templates and trip tracking, but there is NO route optimization or recommendation engine.

### Why This Architecture
- **Frontend (bei-tasks):** Leaflet.js map (already installed: `leaflet@1.9.4`, `react-leaflet@5.0.0`), existing `location-map.tsx` as reference
- **Backend (Frappe):** New API endpoints extending `hrms/api/dispatch.py` (2,164 lines of existing dispatch logic)
- **External API:** Google Maps Directions API for route polylines + traffic-adjusted ETAs
- **Data:** Pre-computed distance matrix (47×47 stores, built today), SKU weight+volume table, provider rate cards

### Key Trade-off Decisions
1. **Leaflet over Google Maps JS** — Free, open-source, no API key per page load. Google Maps JS charges per load.
2. **Static pins + zoom only** — User explicitly requested no interactive features except zoom. No drag, no click handlers, no info popups.
3. **Google Directions API for routes** — We need actual driving route polylines and traffic-adjusted ETAs. OpenStreetMap's OSRM is free but has no Manila traffic data.
4. **Dual measurement: kg + m³** — Weight alone doesn't capture bulky items (cups, lids, plastics). The recommender must check both weight AND volume against truck limits.
5. **Pre-trained data over real-time** — Historical traffic patterns (by hour of day) are sufficient. No need for live tracking.

### Known Limitations
- Google Directions API costs ~$5-10/1000 requests. At ~50 route plans/day, monthly cost ~$7-15.
- Volume (m³) estimates for SKUs need warehouse team input — initial estimates from carton dimensions.
- The tool recommends but doesn't enforce — SCM team can override any suggestion.

### Source References
- Existing dispatch API: `hrms/api/dispatch.py` (2,164 lines)
- Existing route DocTypes: `hrms/hr/doctype/bei_route/`, `bei_distribution_trip/`
- Existing map component: `bei-tasks/components/attendance/location-map.tsx`
- SCM routes in constants: `bei-tasks/lib/constants.ts` (SCM, SCM_DELAYED_DELIVERIES, etc.)
- RBAC roles: `bei-tasks/lib/roles.ts` (SCM, DISPATCH, WAREHOUSE_ROUTES)
- Distance matrix: `data/Logistics/Q1_Delivery_Downloads/optimization/distance_matrix_full.csv`
- Store geocoded data: `data/Logistics/Q1_Delivery_Downloads/optimization/store_geocoded.csv`
- Provider rates: `.claude/skills/logistics-bei-erp/references/provider-rates.md`
- Truck capacity data: Built in this sprint (Phase 0)

## Ground-Truth Lock

| Evidence Source | What It Proves |
|----------------|----------------|
| `bei-tasks/package.json` | Leaflet + React-Leaflet already installed |
| `bei-tasks/components/attendance/location-map.tsx` | Working map component exists as reference |
| `hrms/api/dispatch.py` | 2,164 lines of dispatch logic to extend |
| `optimization/store_geocoded.csv` | 47 stores geocoded with lat/lng |
| `optimization/distance_matrix_full.csv` | Hub-to-store distances with traffic |
| `optimization/store_volume_profiles.csv` | Per-store daily volume data |
| `optimization/sku_weight_table.csv` | 103 SKUs with weight estimates |

## Phase Overview

| Phase | Description | Units | Deliverable |
|-------|-------------|-------|-------------|
| **0** | Data preparation: SKU volume table, truck capacity profiles, rate matrix seeding | 10 | Seed data in Frappe + static files |
| **1** | Backend API: route optimization engine + Google Directions integration | 15 | `/api/route-planner/*` endpoints |
| **2** | Frontend: route planner page with store selector + results display | 15 | `/dashboard/scm/route-planner` page |
| **3** | Map visualization: Leaflet map with static pins, route polylines, ETA labels | 12 | Map component embedded in planner |
| **4** | Multi-option cost comparison + truck recommender | 12 | Options table with metrics |
| **5** | Testing, integration, closeout | 8 | L3 scenarios, PR, registry update |
| **Total** | | **72** |

---

## Phase 0: Data Preparation (10 units)

### Objective
Build the SKU volume table and truck capacity profiles that the route optimization engine needs.

### Tasks

| # | Task | Method | Output |
|---|------|--------|--------|
| 0.1 | **Build SKU weight table** | Use the verified weight table from the logistics skill (`optimization/sku_weight_table.csv`). Convert to JSON for frontend consumption. Volume (m³) is NOT required for launch — the system launches with weight-only mode. Volume is added later when warehouse team measures actual carton dimensions for the top 20 bulky SKUs (cups, lids, plastics, bundles). | `sku_master.json` static file in bei-tasks |
| 0.2 | **Define truck capacity profiles** | Document weight AND volume limits per truck type. L300: 800kg / 3m³. 2T: 1,500kg / 8m³. 4T: 3,000kg / 16m³. 6W: 4,500kg / 24m³. | `truck_profiles.json` static file |
| 0.3 | **Seed provider rate matrix** | Convert provider rate cards into structured JSON. Rates by: provider × route × truck_type × goods_type. Source: `.claude/skills/logistics-bei-erp/references/provider-rates.md` | `provider_rates.json` static file |
| 0.4 | **Seed store geocode data** | Convert `store_geocoded.csv` to JSON with lat/lng + hub assignment + delivery window + truck restriction per store | `store_data.json` static file |
| 0.5 | **Seed distance matrix** | Convert `distance_matrix_full.csv` to JSON lookup: `{origin}_{destination} → {distance_km, duration_min, traffic_duration_min}` | `distance_matrix.json` static file |
| 0.6 | **Seed store-to-store distances** | Convert `store_clusters.csv` to JSON for route sequencing | `store_pairs.json` static file |

### Completion Criteria
- All 6 JSON seed files created and importable by the frontend
- SKU volume table covers all 103 items
- Truck profiles include BOTH weight AND volume limits

---

## Phase 1: Backend API — Route Optimization Engine (15 units)

### Objective
Build the API that accepts a list of stores + items, and returns optimized route options with cost estimates.

### Tasks

| # | Task | Method | Output |
|---|------|--------|--------|
| 1.1 | **New endpoint: `optimize_route`** | Accept: `{stores: [{store, items: [{sku, qty}]}], goods_type: 'cold'|'dry', departure_time: 'HH:MM'}`. Return: list of route options ranked by cost. | `hrms/api/route_planner.py` |
| 1.2 | **Route sequencing algorithm** | Nearest-neighbor heuristic: start from hub, pick closest unvisited store, repeat. Respect delivery windows (skip stores whose window hasn't opened). | Function in route_planner.py |
| 1.3 | **Truck size recommender** | Calculate total_kg and total_m3 from items × SKU table. Check BOTH against truck profiles. Recommend smallest truck that fits. If volume-constrained but weight-light, flag it. | Function in route_planner.py |
| 1.4 | **Cost calculator** | For each route option, apply provider rates based on: route region (north/south), truck type, goods type. Calculate per-stop incremental cost (3MD: +₱600/stop). | Function in route_planner.py |
| 1.5 | **Multi-option generator** | Generate 3 options: (A) Best cost, (B) Fastest delivery, (C) Fewest trucks. Rank by configurable metric. | Function in route_planner.py |
| 1.6 | **Google Directions API integration** | Call Directions API with waypoints (hub → store1 → store2 → ...) to get: route polyline (encoded), per-leg duration with traffic, total distance. Use `departure_time` for historical traffic. | `hrms/api/google_maps.py` |
| 1.7 | **Endpoint: `get_store_orders_for_date`** | Pull today's approved store orders from `BEI Store Order` DocType. Return per-store item list with qty. This feeds the optimizer automatically. | Function in route_planner.py |
| 1.8 | **Endpoint: `get_route_options`** | Wrapper that calls optimize_route + Google Directions, returns formatted options with polylines for the map. | Function in route_planner.py |
| 1.9 | **Sentry observability** | Add `set_backend_observability_context(module='scm', action='optimize_route')` to all new endpoints. | All new endpoints |

### API Response Shape
```json
{
  "options": [
    {
      "rank": 1,
      "label": "Best Cost",
      "truck_type": "2T",
      "provider": "Coolitz",
      "estimated_cost": 6500,
      "total_kg": 1240,
      "total_m3": 4.2,
      "truck_utilization_weight": 0.83,
      "truck_utilization_volume": 0.53,
      "stops": [
        {"store": "SM Southmall", "sequence": 1, "eta": "09:15", "kg": 620, "m3": 2.1, "items": 14},
        {"store": "Festival Mall", "sequence": 2, "eta": "10:00", "kg": 620, "m3": 2.1, "items": 12}
      ],
      "total_distance_km": 42.3,
      "total_duration_min": 95,
      "polyline": "encoded_polyline_string",
      "hub": "Pinnacle Calamba"
    },
    { "rank": 2, "label": "Fastest", ... },
    { "rank": 3, "label": "Fewest Trucks", ... }
  ],
  "warnings": [
    "SM MOA: 4-wheeler trucks only (no 4T)",
    "NAIA T3: delivery window 2-5 PM only"
  ]
}
```

### Metrics for Options Ranking

| Metric | Description | Weight |
|--------|-------------|--------|
| **Estimated Cost (₱)** | Provider rate for this route + truck type | Primary for "Best Cost" |
| **Delivery Duration (min)** | Total time hub → last store, with traffic | Primary for "Fastest" |
| **Truck Count** | Number of trucks needed | Primary for "Fewest Trucks" |
| **Weight Utilization (%)** | total_kg / truck_kg_limit | Secondary — flag if <30% |
| **Volume Utilization (%)** | total_m3 / truck_m3_limit | Secondary — flag if <30% or >90% |
| **Cost per kg (₱/kg)** | Efficiency metric | Comparison |
| **Stops per truck** | 4-5 is optimal | Flag if <2 or >6 |

---

## Phase 2: Frontend — Route Planner Page (15 units)

### Objective
Build the SCM route planner page with store selector, auto-load from orders, and results display.

### Tasks

| # | Task | Method | Output |
|---|------|--------|--------|
| 2.1 | **Create route `/dashboard/scm/route-planner`** | New page in App Router. Add to constants.ts as `SCM_ROUTE_PLANNER`. Add to roles.ts for SCM role. | Route + page component |
| 2.2 | **Store selector component** | Multi-select dropdown of 47 stores. Grouped by hub (3MD North / Pinnacle South). Show today's pending orders count per store. | `components/scm/store-selector.tsx` |
| 2.3 | **Auto-load from orders** | "Load Today's Orders" button pulls approved store orders for selected date. Pre-fills store list + item quantities. | Integration with `get_store_orders_for_date` |
| 2.4 | **Manual item entry** | Allow SCM to manually add/remove items per store if orders aren't in the system yet. SKU autocomplete from master list. | Item editor component |
| 2.5 | **Goods type selector** | Toggle: Cold / Dry / Both. "Both" runs two separate optimizations (cold and dry never combined on same truck). | Filter component |
| 2.6 | **Departure time picker** | Time selector defaulting to 5:00 AM (cold) or 8:00 AM (dry). Affects traffic estimation. | Time picker |
| 2.7 | **"Optimize" button** | Calls backend `get_route_options`, shows loading state, displays results. | Action button |
| 2.8 | **Results display — options cards** | Show 3 option cards side-by-side: Best Cost, Fastest, Fewest Trucks. Each shows: truck type, cost, duration, stops, utilization bars (weight + volume). | `components/scm/route-option-card.tsx` |
| 2.9 | **Stop sequence table** | Per option: ordered list of stops with ETA, kg, m³, items count, delivery window status (green=within window, red=outside). | Table component |
| 2.10 | **Warnings panel** | Display truck restrictions, delivery window conflicts, volume-constrained alerts. Gold background per BEI brand. | Warning component |
| 2.11 | **Navigation integration** | Add "Route Planner" to SCM sidebar. Icon: truck or route icon. | Sidebar update |

### Shell Prevention Gates

| Gate | Status |
|------|--------|
| `gate_route_contract_defined` | `/dashboard/scm/route-planner` owned by SCM module |
| `gate_action_wiring_complete` | Optimize button → backend API → response → display |
| `gate_dependency_map_complete` | Requires: store_data.json, sku_dimensions.json, provider_rates.json, distance_matrix.json |
| `gate_navigation_placement_defined` | SCM sidebar, after "Reallocation" |
| `gate_empty_error_states_defined` | No orders: "No approved orders for this date", API error: retry, No stores selected: disable button |
| `gate_mutation_outcomes_defined` | Read-only — no mutations. Display only. |
| `gate_mobile_layout_defined` | Stack cards vertically on mobile. Map below options. |

---

## Phase 3: Map Visualization (12 units)

### Objective
Display the optimized route on a Leaflet map with color-coded pins, route polylines, and ETA labels.

### Tasks

| # | Task | Method | Output |
|---|------|--------|--------|
| 3.1 | **Route map component** | Leaflet + React-Leaflet. OpenStreetMap tiles (free, no API key). Disable all interactions EXCEPT zoom (no drag, no click, no popups). `dragging: false, doubleClickZoom: true, scrollWheelZoom: true, touchZoom: true` | `components/scm/route-map.tsx` |
| 3.2 | **Hub pin (start point)** | Large green pin (3MD) or gold pin (Pinnacle) at hub location. Label: "START: [Hub Name]". | Custom Leaflet marker |
| 3.3 | **Store pins (drops)** | Numbered pins (1, 2, 3...) matching stop sequence. Color by hub zone: green pins for 3MD stores, gold for Pinnacle stores. Each pin has text label: "[#] Store Name". | Custom numbered markers |
| 3.4 | **Route polyline** | Decode Google Directions encoded polyline. Draw on map as colored line (green for cold route, gold for dry route). Arrow indicators showing direction. | Polyline layer |
| 3.5 | **ETA labels** | Small label at each pin showing estimated arrival time: "ETA: 09:15 AM". Color: green if within delivery window, red if outside. | Label overlays |
| 3.6 | **Legend** | Static legend in corner: green pin = 3MD store, gold pin = Pinnacle store, green line = cold route, gold line = dry route. | Legend component |
| 3.7 | **Auto-fit bounds** | Map auto-zooms to fit all pins + route on screen. | `fitBounds()` on load |
| 3.8 | **Option toggle** | When user clicks a different option card (Best Cost vs Fastest), the map updates to show that option's route. | State management |

### Map Interaction Rules (HARD BLOCKER)
- **ALLOWED:** Zoom in/out (scroll wheel, pinch, +/- buttons)
- **NOT ALLOWED:** Pan/drag, click on pins, info popups, right-click menu, keyboard navigation
- Pins, routes, and labels are static renders — not interactive elements

---

## Phase 4: Multi-Option Cost Comparison + Truck Recommender (12 units)

### Objective
The recommendation engine that generates multiple options and explains the trade-offs.

### Tasks

| # | Task | Method | Output |
|---|------|--------|--------|
| 4.1 | **Option A: Best Cost** | Optimize for lowest total ₱. Use cheapest provider for each route. Maximize stops per truck (up to 5). Use smallest truck that fits. | Algorithm |
| 4.2 | **Option B: Fastest Delivery** | Optimize for shortest total delivery time. Sequence stops by proximity + delivery window. May use multiple trucks to parallelize. | Algorithm |
| 4.3 | **Option C: Fewest Trucks** | Minimize number of trucks. Pack maximum stops per truck (up to 5-6). May use bigger trucks even if not full. | Algorithm |
| 4.4 | **Split detection** | If total load exceeds largest truck (4T: 3,000 kg / 16 m³), automatically split into 2 routes. Show split reason (weight or volume). | Split logic |
| 4.5 | **Volume-constrained alert** | When total_m3 > truck_m3_limit but total_kg < truck_kg_limit, show: "Truck full by VOLUME (cups/lids are bulky). Consider splitting dry packaging from food items." | Alert logic |
| 4.6 | **Comparison table** | Side-by-side comparison of all 3 options with all metrics. Highlight the "Best" value in each row with green. | Comparison component |
| 4.7 | **Cost breakdown** | Per option: show base rate + per-stop surcharge + estimated toll. Source rates from provider_rates.json. | Cost detail |
| 4.8 | **Truck utilization visualization** | Horizontal bar charts showing weight utilization (%) and volume utilization (%) per truck. Green <75%, gold 75-90%, red >90%. | Bar chart component |
| 4.9 | **Provider comparison** | If multiple providers can serve the same route, show: "Coolitz: ₱6,500 vs Suzuyo: ₱14,600 (55% cheaper)". | Provider compare |
| 4.10 | **Historical benchmark** | Show "Average cost for this route in March: ₱X" from the Q1 billing data. Let SCM see if the recommendation beats history. | Benchmark display |

### Truck Recommender — Two Modes

**Mode 1 (Launch):** Weight-only. Volume field exists in the data model but defaults to null. Recommender uses kg only.

```
total_kg = sum(qty × sku_weight_kg for each item)
recommended_truck = smallest truck where truck.kg_limit >= total_kg
```

**Mode 2 (After warehouse measures top 20 bulky SKUs):** Weight + volume. When `sku_volume_m3` is populated for an item, the recommender checks both:

```
total_kg = sum(qty × sku_weight_kg for each item)
total_m3 = sum(qty × sku_volume_m3 for each item where volume is known)

weight_truck = smallest truck where truck.kg_limit >= total_kg
volume_truck = smallest truck where truck.m3_limit >= total_m3

recommended_truck = max(weight_truck, volume_truck)

if weight_truck != volume_truck:
    warning = "Volume-constrained: {bulky_items} take more space than weight suggests"
```

**The volume field is optional at launch. The UI shows a "Volume data pending" note for items without measurements. This is NOT a launch blocker.**

---

## Phase 5: Testing, Integration, Closeout (8 units)

### Tasks

| # | Task | Method | Output |
|---|------|--------|--------|
| 5.1 | L2 page check | Load route planner page, verify all components render | L2 evidence |
| 5.2 | L3 workflow scenarios | Execute all scenarios below | L3 evidence |
| 5.3 | Create PR (bei-tasks + hrms) | `gh pr create` for both repos | PR numbers |
| 5.4 | Update sprint registry | SPRINT_REGISTRY.md → COMPLETED with PR refs | Registry |
| 5.5 | Update plan metadata | Status → COMPLETED, add execution_summary | Plan file |

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| test.warehouse@bebang.ph | Open /dashboard/scm/route-planner | Page loads with store selector, date picker, goods type toggle | Route or RBAC broken |
| test.warehouse@bebang.ph | Select 3 stores (SM Southmall, Festival Mall, Terminal Alabang), goods_type=Cold, click Optimize | 3 option cards appear: Best Cost, Fastest, Fewest Trucks. Map shows route with 3 numbered pins. | Backend API or map rendering broken |
| test.warehouse@bebang.ph | Click "Load Today's Orders" for a date with approved orders | Store list auto-populates with items and quantities from BEI Store Order | Order integration broken |
| test.warehouse@bebang.ph | Select 5 stores with heavy dry items (cups, lids = high volume), click Optimize | System recommends 2T NOT L300 due to volume constraint. Warning shows "Volume-constrained: cups and lids are bulky" | Volume calculation broken |
| test.warehouse@bebang.ph | Click Option B (Fastest) card | Map updates to show Option B route. ETA labels change. | Map option toggle broken |
| test.warehouse@bebang.ph | Select SM MOA in store list, click Optimize | Warning appears: "SM MOA: 4-wheeler trucks only" | Truck restriction check broken |

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s139-route-planner origin/production`. NEVER write code on production.
3. Read `docs/plans/SPRINT_REGISTRY.md` for cross-sprint context.
4. Read existing dispatch API: `hrms/api/dispatch.py` — understand current route/trip/stop model.
5. Read existing map component: `bei-tasks/components/attendance/location-map.tsx` — reference for Leaflet patterns.
6. Read `bei-tasks/lib/constants.ts` and `bei-tasks/lib/roles.ts` for route and RBAC setup.
7. Read `.claude/skills/logistics-bei-erp/references/provider-rates.md` for rate data.
8. Confirm all Phase 0 seed data files exist before starting Phase 1.

## Execution Workflow
- Test Python changes: `/local-frappe`
- Deploy changes: `/deploy-frappe`
- Full workflow: `/agent-kickoff`
- E2E testing: `/e2e-test` or `/test-full-cycle`

## Autonomous Execution Contract

```yaml
completion_condition:
  - All phases completed
  - L2 + L3 scenarios pass
  - PRs created for both repos (bei-tasks + hrms)
  - Sprint registry updated to COMPLETED
  - Plan status updated to COMPLETED

stop_only_for:
  - Google Maps API key missing or quota exceeded
  - Missing store geocode data
  - Frappe DocType schema conflict with S138

continue_without_pause_through:
  - phase execution
  - PR creation
  - L2/L3 testing

blocker_policy:
  - programmatic → fix and continue
  - API error → retry with backoff, then flag
  - Missing seed data → create from available CSVs

signoff_authority: single-owner (Sam Karazi, CEO)
```

## Requirements Regression Checklist

### Map
- [ ] Is the map using Leaflet + OpenStreetMap (NOT Google Maps JS)?
- [ ] Are ALL interactions disabled EXCEPT zoom?
- [ ] Are pins static (no click, no drag, no popups)?
- [ ] Are pin colors: green for 3MD stores, gold for Pinnacle stores?
- [ ] Does each pin show store name + sequence number as text label?
- [ ] Does the map show the start point (hub) as a distinct larger pin?

### Truck Recommender
- [ ] Does the recommender check BOTH weight (kg) AND volume (m³)?
- [ ] Does it flag volume-constrained loads (bulky cups/lids)?
- [ ] Does it respect per-store truck restrictions (SM MOA = 4W only)?
- [ ] Does it show utilization bars for both weight and volume?

### Route Options
- [ ] Are exactly 3 options generated (Best Cost, Fastest, Fewest Trucks)?
- [ ] Does each option show: truck type, cost, duration, stops, utilization?
- [ ] Does clicking an option card update the map to show that route?
- [ ] Are delivery window conflicts flagged (red if outside window)?

### Data
- [ ] Are cold and dry routes ALWAYS separate (never combined)?
- [ ] Are provider rates from verified contract data (not estimates)?
- [ ] Are distances from Google Maps API (not straight-line)?
- [ ] Is SM Pampanga absent from all data (does not exist)?
- [ ] Is the SKU volume table included for all 103 items?

### Integration
- [ ] Can the planner auto-load from BEI Store Order (approved orders)?
- [ ] Is the page accessible via SCM sidebar navigation?
- [ ] Is RBAC enforced (SCM role only)?
- [ ] Are all new endpoints instrumented with Sentry context?
