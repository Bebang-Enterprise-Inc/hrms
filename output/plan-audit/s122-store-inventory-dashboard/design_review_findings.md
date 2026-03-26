# S122 Store Inventory Dashboard — Design Review Findings
**Audit Date:** 2026-03-25
**Plan:** S122 — Store Inventory Dashboard (`/dashboard/store-ops/inventory`)
**Reviewer:** Design Review Specialist
**Score: 54 / 100 — CONDITIONAL PASS (6 findings, 3 critical)**

---

## Summary

The plan is buildable as specified but contains three architectural decisions that will produce compounding technical debt by Phase C. The god-component pattern, unspecified merge strategy, and fan-out API design are not cosmetic issues — they will force a rewrite of the Area Supervisor view under real load conditions (46 stores × 150 SKUs = 6,900 rows without pagination). The remaining three findings are lower severity but should be addressed before Phase B begins.

---

## Finding 1 — GOD-COMPONENT ANTI-PATTERN [CRITICAL]

**Dimension:** Component Decomposition
**Severity:** Critical (will block Phase B extension)

**Issue:** All three views (My Stock list, multi-store Area Supervisor matrix, stockout alerts panel) are planned to live in a single `page.tsx`. The plan notes all Phase A (13 units), Phase B (6 units), and Phase C (4 units) tasks target "the same page.tsx file."

**Why this fails:**
- Phase A alone produces dual layout (table + card view), category filter, search, sort, and store picker — that is 5+ distinct UI concerns in one file.
- Phase B adds a fundamentally different data shape (multi-store aggregation vs. single-store line items). These two views do not share rendering logic; forcing them into one component means the file will carry dead conditional branches for each user role.
- At 23 units of work across 3 phases, the component will exceed 800–1,000 lines before polish begins. That crosses the threshold where adding a feature requires reading the whole file to avoid breaking another view.

**Expected outcome without change:** Phase B is implemented as a nested `if (isAreaSup)` block inside a file already managing My Stock state. Developers will begin passing props 3–4 levels deep to share the category filter between views.

**Recommendation:**
Decompose into a thin router shell and three focused view components:
```
page.tsx                        (role detection, tab routing only — <100 lines)
  MyStockView.tsx               (single-store stock list + dual layout)
  MultiStoreView.tsx            (area sup aggregation matrix)
  StockoutAlertsPanel.tsx       (shared between both views as a sidebar or drawer)
```
Each view owns its own hooks. `StockoutAlertsPanel` becomes the first reusable primitive. This decomposition does not add scope — it reorganizes the same 23 units across files rather than piling them into one.

---

## Finding 2 — UNSPECIFIED HOOK MERGE STRATEGY [CRITICAL]

**Dimension:** Data Flow
**Severity:** Critical (will cause silent data mismatches in production)

**Issue:** `useWarehouseStock` and `useOrderableItems` return items with different shapes. The plan does not specify a merge key, merge timing, or which source is authoritative when the same SKU appears in both with conflicting `quantity` or `unit_cost` values.

**Known shape divergence risks:**
- `useWarehouseStock` likely returns warehouse-side quantity (physical count). `useOrderableItems` likely returns orderable quantity (approved ordering workspace items). These are different numbers for the same SKU.
- If merged by `item_code` without a defined strategy, a component receiving the merged object cannot know which `qty` field is the physical stock count vs. the orderable quantity.
- If `useOrderSchedule` is also merged into the same object, a third `qty` variant (scheduled order quantity) enters the same namespace.

**Expected outcome without change:** Developers will independently implement ad-hoc merge logic at the component level. By Phase C, there will be at least two different merge implementations in the codebase that produce different results for edge cases (items present in one hook but not the other, items with zero quantity in one source).

**Recommendation:**
Define a canonical `StoreInventoryItem` type before writing any hook. Specify:
1. The merge key (presumably `item_code` or `item_name` — confirm uniqueness).
2. Which field from which source wins for `quantity` (warehouse physical count wins; orderable qty becomes a separate field `orderable_qty`).
3. How to handle items present in one source but not the other (treat missing orderable entry as `orderable: false`, not as a missing item).
4. Write the merge in a single `useStoreInventory` composite hook that wraps the two raw hooks. Components never call the raw hooks directly.

---

## Finding 3 — CONCURRENT API FAN-OUT FOR AREA SUPERVISOR VIEW [CRITICAL]

**Dimension:** Performance
**Severity:** Critical (will produce visible load failures in the field)

**Issue:** Area Supervisor role covers up to 46 stores. The plan does not specify how the "All My Stores" view fetches data. The default implementation path — one API call per store, all fired simultaneously — produces 46 concurrent requests on page load.

**Quantified impact:**
- 46 stores × ~150 SKUs each = 6,900 rows minimum in memory simultaneously.
- On a mobile browser (Area Supervisors are field staff on phones), 46 simultaneous requests will exhaust the browser's per-origin connection limit (typically 6 connections), causing a request queue backlog that takes 15–30 seconds to resolve.
- Frappe's built-in rate limiter may begin dropping requests from the same session if 46 `/api/resource/` calls arrive within seconds of each other.
- MariaDB will receive 46 near-simultaneous queries for large result sets — this is the primary risk on a Docker-hosted single-instance DB.

**Expected outcome without change:** The Area Supervisor view will time out or appear to load indefinitely on the first real production test with a 20+ store supervisor.

**Recommendation (in order of preference):**
1. **Server-side aggregation endpoint (preferred):** Add a single `GET /api/method/hrms.api.store_inventory.get_multi_store_stock` that accepts `store_ids[]` and returns aggregated data in one response. The server does the fan-out and join in Python, which is 10× more efficient than 46 client-initiated queries.
2. **Paginated store loading (acceptable):** Load 5 stores at a time with a "load more" control. Keeps the UI responsive and gives the user immediate partial results.
3. **Lazy per-store accordion (minimum viable):** Render all store rows in collapsed state; fire each store's query only when the user expands it. Eliminates the fan-out entirely at the cost of UX convenience.

Option 1 also enables future dashboard analytics (cross-store stockout rates, low-stock heatmaps) without client-side aggregation.

---

## Finding 4 — EXCESSIVE LOCAL STATE IN ONE COMPONENT [MEDIUM]

**Dimension:** State Management
**Severity:** Medium (manageable if Finding 1 decomposition is adopted; critical if not)

**Issue:** The plan implies the following state values all live in one component: `searchQuery`, `selectedCategory`, `sortField`, `sortDirection`, `layoutMode` (table/card), `selectedStore` (store picker for area sup), and possibly `activeTab` (My Stock / Multi-store / Alerts). That is 7–8 `useState` calls in a single component before any async state from hooks is included.

**Why this matters beyond line count:**
- `selectedStore` is only meaningful for the Area Supervisor view. Keeping it in a shared component means the My Stock view must receive and ignore it, creating a coordination surface where none is needed.
- When `selectedCategory` changes, it should trigger a re-filter of the stock list. If the category state is in the parent and the list is a child, the re-render propagates through the entire page tree instead of being isolated to `MyStockView`.
- `layoutMode` (table vs. card) is purely presentational and should be local to `MyStockView` — it has no meaning outside that view.

**Recommendation:**
If Finding 1 decomposition is adopted: each view owns its own local state. Only `activeTab` and `selectedStore` (for area sup context) need to live at the page level. This reduces page-level state from 8 values to 2.

If decomposition is deferred: use `useReducer` with a typed action union instead of 7 separate `useState` calls. This at minimum makes state transitions auditable and prevents partial-update bugs when category + search change simultaneously.

---

## Finding 5 — REUSABILITY NOT PLANNED FOR STOCK CARDS AND STATUS BADGES [LOW]

**Dimension:** Reusability
**Severity:** Low (missed opportunity, not a correctness issue)

**Issue:** The plan references "existing patterns: warehouse inventory matrix, warehouse daily stock cards, ordering workspace" but does not specify whether S122 will consume existing stock card components or create new ones. If new stock card and status badge components are written for this page, there will be two independent implementations of the same visual primitive within 3–6 weeks.

**Evidence of divergence risk:**
- Warehouse daily stock cards already display item name, quantity, and status (low/normal/critical). The store inventory stock card will need the same three fields plus orderable flag.
- Status badges (Low Stock / Out of Stock / Normal) will be needed in both the store view and any future warehouse comparison view.

**Recommendation:**
Before Phase A begins, audit `components/warehouse/` (or equivalent) for existing `StockCard` and `StockStatusBadge` components. If they exist, extend them with an optional `orderable` prop rather than creating store-specific versions. If they do not exist, create them in `components/shared/inventory/` from the start so both warehouse and store views can import from the same source.

This is a 1-hour audit task that prevents a 4-hour deduplication effort in Sprint 130+.

---

## Finding 6 — PHASE BOUNDARIES DO NOT ENFORCE INTEGRATION CHECKPOINTS [LOW]

**Dimension:** Actionability
**Severity:** Low (process risk, not a code risk)

**Issue:** Phase A (13 units) delivers My Stock view. Phase B (6 units) adds multi-store and alerts. Phase C (4 units) is polish + deploy. There is no specified integration checkpoint between Phase A and Phase B.

**Risk:** If the merge strategy (Finding 2) and API fan-out design (Finding 3) are deferred to "when we start Phase B," Phase A will be built on assumptions about data shape that Phase B then violates. Retrofitting the merge strategy after 13 units of Phase A are complete is more expensive than defining it before Phase A starts.

**Recommendation:**
Add an explicit gate between Phase A and Phase B:
- Gate condition: `useStoreInventory` composite hook is written, typed, and tested against real store data before any Phase A rendering work begins.
- This does not add sprint units — it reorders existing work (hook definition moves to the front of Phase A rather than being implied).

---

## Score Breakdown

| Dimension | Max | Score | Verdict |
|---|---|---|---|
| Component Decomposition | 20 | 8 | FAIL — god-component confirmed |
| Data Flow | 20 | 9 | FAIL — merge strategy undefined |
| State Management | 20 | 13 | MARGINAL — salvageable with decomposition |
| Performance | 20 | 8 | FAIL — fan-out not addressed |
| Reusability | 20 | 16 | PASS — minor gap only |
| **Total** | **100** | **54** | **CONDITIONAL PASS** |

---

## Required Actions Before Phase A Code Is Written

| # | Action | Owner | Blocks |
|---|---|---|---|
| R1 | Define `StoreInventoryItem` canonical type + merge strategy | Architect | Phase A hook work |
| R2 | Decompose page.tsx into 3 view components (shell + MyStock + MultiStore + Panel) | Lead dev | Phase A UI work |
| R3 | Design multi-store aggregation endpoint or choose paginated/lazy strategy | Backend | Phase B |
| R4 | Audit existing warehouse stock card components for reuse | Any dev | Phase A card rendering |

Actions R1 and R2 are prerequisites for Phase A. R3 can be designed in parallel with Phase A but must be resolved before Phase B begins. R4 is a 1-hour task that should be done before writing any card component.
