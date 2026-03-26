---
canonical_sprint_id: S122
display: Sprint 122
status: PR_CREATED
branch: s122-store-inventory-dashboard
lane: single
created_date: 2026-03-25
completed_date:
deployed_at:
backend_pr: 353
frontend_pr: 249
l3_result:
execution_summary: Frontend PR #249 (bei-tasks), Backend PR #353 (hrms). 7 new page components + composite hook + order history API.
depends_on:
---

# S122 — Store Inventory Dashboard: Birds-Eye Stock Visibility for Store Teams

**Goal:** Give store managers a single page on my.bebang.ph that shows everything they have, what's running low, what's overstocked, and what they should order next — all at a glance, mobile-first, designed for 100+ SKUs.

**Origin:** S121 fixed the inventory sync but revealed that store managers have zero inventory visibility on my.bebang.ph. The ordering page only works during the order window. Outside that window, store teams are blind.

**Key constraint from Sam:** When BEI fully migrates to ERPNext, the Google Sheets sync stops entirely. Do NOT build features around sync freshness or ENCODE adoption. Focus on what tabBin and ERPNext data already provide: stock levels, demand, and order history.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

Store managers manage 80-150 SKUs across DRY, COLD, FROZEN, and CHILLED categories. Today they have:
- **Ordering page** (`/dashboard/store-ops/ordering`) — only works when the order window is open (schedule-gated)
- **No stock visibility page** — they cannot see what Frappe thinks their store has
- **No demand view** — they cannot see projected demand or days-of-stock outside the ordering flow

The warehouse team has `/dashboard/warehouse/inventory` (a matrix view with status badges, days-of-stock, and demand columns). Store teams need something similar but scoped to a **single store** and optimized for **mobile phones** (store managers are rarely at a desk).

### Why this architecture

**Reuse existing APIs where possible, add minimal backend for order history.** Existing hooks:
- `useWarehouseStock(warehouse)` — returns `WarehouseStockItem` with `item_code`, `item_name`, `actual_qty`, `available_qty`, `is_low_stock` (NOTE: no `uom` — source from `OrderableItem` instead)
- `useOrderableItems(store)` — returns `OrderableItem` with `available_stock`, `forecast_demand`, `suggested_qty`, `risk_rank`, `is_oos`, `cargo_category`, `uom`
- `useOrderSchedule(store)` — returns `{ schedule: OrderSchedule | null }` (NOTE: wrapped in `schedule` — access via `schedule?.allowed`, not bare `allowed`)
- `useUserStore()` — returns `{ stores[], defaultStore, isMultiStore, role }`. NOTE: `defaultStore` and `stores[i].name` are Warehouse **docnames** (e.g., "Store Name - BEI") — pass these to `useWarehouseStock`. `stores[i].warehouse_name` is display-only, do NOT use as warehouse param.

**One new backend endpoint needed (audit v2 finding):** Order history. No `useOrders(store)` hook or `/api/ordering?action=get_store_order_history` exists. Task A9-BE adds a Frappe method + route action (~30 lines).

### Key trade-offs

1. **Responsive dual layout:** Stores use both phones and laptops. The page renders as a **grouped card list** on mobile (<768px) with sticky category headers and big touch targets, and a **dense sortable table** on desktop (>=768px) similar to the warehouse inventory matrix — with columns for item, category, qty, status, days-of-stock, demand, and suggested order qty. Both layouts share the same data hooks and filters. Use Tailwind `md:` breakpoint to switch. The card layout is the default (mobile-first).

2. **Single-store vs multi-store:** Store staff see only their store. Area Supervisors see a store picker at the top. This matches the existing pattern in ordering and store-ops pages.

3. **Always-available vs schedule-gated:** Unlike ordering, this page is always available. It shows current stock even when the order window is closed. When the window IS open, a banner links to the ordering page.

4. **No sync freshness features:** Per Sam's directive, we do NOT show sync timestamps, ENCODE adoption, or historical_end_skipped counts. When ERPNext goes live, the sync layer disappears. The dashboard reads tabBin directly — the source of truth regardless of how data gets there.

### Data merge strategy (audit B-01 fix)

`useWarehouseStock` returns `WarehouseStockItem` (item_code, actual_qty, is_low_stock). `useOrderableItems` returns `OrderableItem` (item_code, forecast_demand, suggested_qty, risk_rank, is_oos, cargo_category). These are **different schemas** joined by `item_code`.

Create a **composite hook** `useStoreInventory(storeWarehouse)` that:
1. Calls `useWarehouseStock(storeWarehouse)` for stock data (primary)
2. Calls `useOrderableItems(store)` for demand enrichment (secondary)
3. Left-joins on `item_code`: all stock items shown, enriched with demand where available
4. Items in stock but NOT orderable → demand fields show "N/A"
5. Items orderable but NOT in stock → omitted (no phantom items)
6. Field precedence: `actual_qty` from stock, `forecast_demand`/`suggested_qty`/`risk_rank` from orderable
7. Returns `StoreInventoryItem[]` with unified shape + `isLoading`, `error`, `mutate`

```typescript
type StoreInventoryItem = {
  item_code: string; item_name: string; warehouse: string;
  actual_qty: number; available_qty: number; is_low_stock: boolean;
  uom: string; // From OrderableItem.uom (NOT WarehouseStockItem — it has no uom). Non-orderable items → ""
  // Enrichment from useOrderableItems (nullable when item is not orderable)
  cargo_category: string | null; forecast_demand: number | null;
  suggested_qty: number | null; risk_rank: number | null; is_oos: boolean;
  days_of_stock: number | null; // computed: actual_qty / forecast_demand
};
```

### Component decomposition (audit B-02 fix)

The page MUST be decomposed — not a single monolithic page.tsx:

```
app/dashboard/store-ops/inventory/
├── page.tsx                    # Router shell: role detection, tab state (<100 lines)
├── _components/
│   ├── MyStockView.tsx         # Single-store stock list + dual layout (cards/table)
│   ├── MultiStoreView.tsx      # Area Supervisor aggregate table
│   ├── StockoutAlertsPanel.tsx  # Cross-store OOS items (reusable sidebar/drawer)
│   ├── StockCard.tsx           # Mobile card component (reusable)
│   ├── StockTable.tsx          # Desktop table component
│   ├── SummaryStrip.tsx        # Top-level KPI cards
│   ├── CriticalChipStrip.tsx   # Sticky named critical items strip
│   ├── OrderHistoryView.tsx    # Past orders tab
│   └── LastOrderPanel.tsx      # Quick-access last order summary
```

Each view owns its own local state (filters, sort, search). Only `activeTab` and `selectedStore` live in page.tsx.

### Multi-store aggregation strategy (audit B-03 fix)

Area Supervisor "All My Stores" view MUST NOT fire 46 simultaneous API calls.

**Strategy: Lazy-load per store on expand.** Render all store rows in collapsed state with name only. Fire the stock query only when the user expands a store row. This eliminates the fan-out entirely. The aggregate counts (critical/low per store) come from a lightweight summary call per store on initial load, batched in groups of 5.

If a server-side aggregation endpoint exists or is added later, switch to that. But for S122, lazy-load is sufficient and requires zero backend changes.

### How the data flows

```
tabBin (Frappe) → useWarehouseStock(storeWarehouse) ─┐
                                                      ├→ useStoreInventory() → StoreInventoryItem[]
Order catalog   → useOrderableItems(store) ───────────┘
Order schedule  → useOrderSchedule(store) → OrderSchedule { allowed, cutoff_time, next_delivery_day }
Store scope     → useUserStore() → { defaultStore, stores[], isMultiStore, role }
Order history   → useOrders(store) → past orders for history tab
```

### Existing patterns to follow

- **Store scoping:** `useUserStore()` hook resolves the logged-in user's store. Used by ordering, opening, closing pages.
- **Role guard:** `<RoleGuard module={MODULES.STORE_OPS}>` — same as all store-ops pages.
- **Mobile card pattern:** Warehouse daily stock page (`/warehouse/inventory/daily`) uses card-based rows with big touch targets. Follow this pattern.
- **Category grouping:** Ordering page groups by `cargo_category` (FC/DRY/FM). Use the same grouping.
- **Status badges:** Warehouse matrix uses Critical (red) / Low (amber) / Healthy (green). Reuse `getStatusClasses()`.

---

## Scope

### Phase A: "My Stock" Page (20 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| A0 | BUILD | `bei-tasks/hooks/use-store-inventory.ts` | **[BUILD]** Create composite hook `useStoreInventory(storeWarehouse)` that left-joins `useWarehouseStock` + `useOrderableItems` on `item_code`. Returns `StoreInventoryItem[]` with unified shape (see Data Merge Strategy section). Computes `days_of_stock = actual_qty / forecast_demand`. Items not orderable get `null` demand fields. Returns `{ items, isLoading, error, mutate }`. **HARD BLOCKER:** Do NOT let components call the two raw hooks directly. All stock data flows through this composite hook. | 2 |
| A1 | BUILD | `_components/MyStockView.tsx` + `_components/StockCard.tsx` + `_components/StockTable.tsx` | **[BUILD]** Create dual-layout stock view. **Mobile card anatomy (<768px):** item_name (bold, 16px), item_code (muted, 12px), cargo_category badge (DRY/COLD/FROZEN/CHILLED), actual_qty (large, 24px bold), status badge (Critical red / Low amber / Healthy green), "~X days" subtext, UOM. Min touch target 44x44px. Sticky category headers. **Desktop table columns (>=768px):** Item (name+code), Category, Qty, Status, Days Left, Demand/Day, Suggested Order, UOM. Default sort: risk-first (Critical → Low → Healthy, then alpha). Sortable columns: Qty, Days Left, Demand. Switch via Tailwind `hidden md:block` / `md:hidden`. | 5 |
| A2 | BUILD | `_components/SummaryStrip.tsx` | **[BUILD]** Summary strip at top: 4 KPI cards — Total SKUs, Critical Items (red if >0), Low Stock Items, Overstock Items (qty > 2x suggested_qty). Compute from `useStoreInventory` items. | 1 |
| A3 | BUILD | `_components/CriticalChipStrip.tsx` | **[BUILD, UX U2]** Sticky critical-items chip strip pinned above fold (both mobile and desktop). Red chips showing named items: "Ube Ice Cream: 0 pks", "Leche Flan: 2 pcs". Horizontally scrollable. Tap chip → scroll main list to that item. Strip disappears when 0 critical items. Cannot be dismissed without scrolling to the item. | 2 |
| A4 | BUILD | `bei-tasks/lib/constants.ts` + `bei-tasks/components/layout/nav-main.tsx` | **[EXTEND]** Add route `STORE_OPS_INVENTORY: "/dashboard/store-ops/inventory"` to constants. Add sidebar entry with Package icon between "Ordering" and "Order Approvals" in the store-ops nav group. | 1 |
| A5 | BUILD | `_components/OrderWindowBanner.tsx` | **[BUILD, UX U3]** Order window banner with **live countdown timer** (HH:MM to cutoff). **Audit SM-2 fix:** Use `const { schedule } = useOrderSchedule(store)` — result is wrapped in `{ schedule }`. Access via `schedule?.allowed`, `schedule?.cutoff_time`, `schedule?.next_delivery_day`. **Server time:** Fetch server time once via Frappe API response `Date` header on page load; compute countdown delta from that reference (not device clock). When `schedule?.allowed === true`: green banner "Order window open — X:XX left — [Place Order →]" linking to `/dashboard/store-ops/ordering`. When `false`: grey banner "Next delivery: {next_delivery_day}". Button visually disabled (greyed, not hidden) when closed. | 2 |
| A6 | BUILD | `_components/LastOrderPanel.tsx` | **[BUILD, UX U4]** Sheet/drawer accessible via "Last Order" button in header. Shows: order date, items ordered with quantities, status (Pending/Confirmed/Delivered), who submitted. "Reorder This" button navigates to `/dashboard/store-ops/ordering?prefill=last` — save last order items to sessionStorage before navigation; the ordering page reads prefill and populates quantities (editable, NOT auto-submitted). Uses the order history API from A9-BE (get first result). | 1 |
| A7 | BUILD | page.tsx + search/filter/sort | **[BUILD, UX U1]** Default view = **"Needs Attention"**: only Critical + Low + OOS items shown on first load. "Show All Items" toggle reveals full list. Category filter chips (horizontally scrollable, `overflow-x: auto` on mobile). Search bar (client-side fuzzy match). Refresh button wired to `useStoreInventory.mutate()`. Last-used view remembered in localStorage. | 2 |
| A8 | BUILD | `bei-tasks/app/dashboard/store-ops/inventory/page.tsx` | **[BUILD]** CSV export. Client-side generation (no backend). Columns: item_code, item_name, cargo_category, actual_qty, status, days_of_stock, forecast_demand, suggested_order_qty, uom. Filename: `{store_name}_inventory_{YYYY-MM-DD}.csv`. | 1 |
| A9-BE | BUILD | `hrms/api/store.py` + `bei-tasks/app/api/ordering/route.ts` + `bei-tasks/hooks/use-order-history.ts` | **[BUILD, audit v2 M-1]** Order history API — does NOT exist yet (verified: no hook in 72 files, no route action). **Backend:** Add `@frappe.whitelist()` method `get_store_order_history(store, limit=20, offset=0)` in `hrms/api/store.py` that queries `BEI Store Order` filtered by store warehouse, returns `[{name, order_date, items_count, total_qty, status, submitted_by, items: [{item_code, item_name, qty}]}]`. Add `set_backend_observability_context(module="store-ops", action="get_store_order_history", mutation_type="read")`. **Frontend route:** Add `get_store_order_history` action to `/api/ordering/route.ts`. **Hook:** Create `useOrderHistory(store, limit?)` in `hooks/use-order-history.ts`. | 2 |
| A9 | BUILD | `_components/OrderHistoryView.tsx` | **[BUILD]** "Order History" tab using `useOrderHistory(store)` hook from A9-BE. Table: Order Date, Order ID, Items Count, Total Qty, Status (Draft/Submitted/Approved/Delivered/Cancelled), Submitted By. Tapping a row expands to show line items with qty per item. Sorted newest-first. Paginated (20 per page). | 1 |

### Phase B: Area Supervisor Multi-Store View (8 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| B1 | BUILD | `_components/MultiStoreView.tsx` | **[BUILD]** For Area Supervisor role (`useUserStore().isMultiStore === true`): store picker dropdown at top (same component as order-approvals). Default to "All My Stores" aggregate. Selecting a specific store renders `<MyStockView store={selected} />`. When `useUserStore().stores` is empty (0 assigned stores), show "No stores assigned" empty state — do not crash or show empty table. | 2 |
| B2 | BUILD | `_components/MultiStoreView.tsx` | **[BUILD]** "All My Stores" aggregate table: one row per store showing store name, total SKUs, critical count, low count, last order date. **Lazy-load pattern (audit B-03):** render all rows collapsed. Stock detail loads only when user expands a row. Initial summary counts fetched in batches of 5 stores. Tapping a row expands inline (accordion) OR navigates to that store's full view (use inline accordion on mobile for speed). | 3 |
| B3 | BUILD | `_components/StockoutAlertsPanel.tsx` | **[BUILD]** "Stockout Alerts" tab: across all supervised stores, show items where `is_oos === true` OR `risk_rank >= 8`. Grouped by item_code (showing which stores are affected per item). This is the Area Sup's daily priority list. Each alert row shows: item name, affected store count, worst risk_rank. Tap to expand shows per-store detail. | 3 |

### Phase C: Polish + Deploy + Closeout (5 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| C1 | FIX | **Empty/error/loading states (audit B-05):** (1) `isLoading === true` → skeleton cards (mobile) / skeleton table rows (desktop). (2) `items.length === 0` → "No inventory data for this store" empty state with Package icon. (3) `error` → error banner "Could not load inventory — [Retry]" with `mutate()`. (4) Partial data: when stock items exist but demand is null → show qty with demand as "—" (not 0, not NaN). (5) AS with 0 stores → "No stores assigned — contact your manager" message. (6) `useOrderSchedule` returns null → grey banner "Order schedule unavailable". Test at 375px AND 1280px. | 2 |
| C2 | FIX | **DM-7 Sentry:** If any new `@frappe.whitelist()` endpoints are added to the backend, add `set_backend_observability_context()`. If backend is unchanged (API reuse only), this is N/A. Confirm in closeout. | 0 |
| C3 | BUILD | Open PR to bei-tasks `main` → Vercel deploys Preview URL → run all L3 scenarios on Preview URL → merge PR → Vercel auto-deploys production → verify production URL. Do NOT merge until all L3 scenarios pass on Preview. | 2 |
| C4 | BUILD | Closeout: update plan YAML to COMPLETED, update SPRINT_REGISTRY.md. Evidence committed to **BEI-ERP repo** (not bei-tasks): `git add -f docs/plans/ output/l3/S122/`, push to production. | 1 |

**Total: 33 units.** (Phase A: 20, Phase B: 8, Phase C: 5)

---

## Rollback Plan

This is a frontend-only sprint in bei-tasks (Vercel auto-deploy). Rollback = revert the PR on `main`. No backend changes, no data mutations, no risk to production Frappe data.

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| test.crew@bebang.ph | Navigate to Store Ops > Inventory via sidebar | Page loads with "Needs Attention" default view showing Critical + Low items only | Route/nav/default filter broken |
| test.crew@bebang.ph | View critical chip strip at top | Red chips show named critical items (e.g., "Ube Ice Cream: 0 pks"), pinned above fold | CriticalChipStrip broken |
| test.crew@bebang.ph | Tap "Show All Items" toggle | Full item list appears grouped by category | Toggle/filter broken |
| test.crew@bebang.ph | Search for "LECHE" in search bar | FG001-A (LECHE FLAN x 12) card appears | Search broken |
| test.crew@bebang.ph | View summary strip | Shows Total SKUs, Critical count, Low count, Overstock count | Summary calc broken |
| test.crew@bebang.ph | Check a low-stock item card | Shows "~X days left" + "Suggested: Y units" from demand data | useStoreInventory merge broken |
| test.crew@bebang.ph | Tap "Last Order" button in header | Sheet/drawer shows last order: date, items, qty, status | LastOrderPanel broken |
| test.crew@bebang.ph | Switch to "Order History" tab | Shows past orders table: date, ID, items count, status. Tap to expand line items | OrderHistoryView broken |
| test.crew@bebang.ph | Click "Export CSV" | Downloads CSV with all columns, filename = store_inventory_YYYY-MM-DD.csv | Export broken |
| test.crew@bebang.ph | View page when order window open | Banner shows countdown "Order window open — X:XX left — [Place Order →]" | OrderWindowBanner broken |
| test.crew@bebang.ph at **1280px desktop** | View inventory table at desktop width | Dense sortable table renders with columns: Item, Category, Qty, Status, Days Left, Demand, Suggested, UOM. Sort by clicking column headers. | Desktop table layout broken |
| test.crew@bebang.ph at **1024px laptop** | View inventory at laptop width | Table still renders (not cards). No horizontal overflow. All columns visible. | Responsive breakpoint wrong |
| test.areasup@bebang.ph | Navigate to Store Ops > Inventory | Shows store picker + "All My Stores" aggregate table with per-store summary rows | RBAC/multi-store broken |
| test.areasup@bebang.ph | Expand a store row in aggregate | Stock detail lazy-loads for that store only (not all 46) | Lazy-load pattern broken |
| test.areasup@bebang.ph | Switch to "Stockout Alerts" tab | Shows cross-store OOS/high-risk items grouped by item | Alert aggregation broken |
| test.crew@bebang.ph | Tap refresh button | All data reloads (loading spinner shown during fetch) | mutate() not wired |
| test.crew@bebang.ph | Load page for store with 0 stock items | Empty state: "No inventory data for this store" with Package icon | Empty state missing |
| test.areasup@bebang.ph (0 stores) | Load page with no store assignments | "No stores assigned — contact your manager" message, no crash | Zero-stores crash |

Evidence files required before closeout:
```
output/l3/S122/form_submissions.json
output/l3/S122/api_mutations.json
output/l3/S122/state_verification.json
```

---

## Requirements Regression Checklist

- [ ] Does `useStoreInventory()` composite hook exist and left-join stock + demand by item_code? (audit B-01)
- [ ] Do components call `useStoreInventory()` and NOT the raw hooks directly? (HARD BLOCKER)
- [ ] Is the page decomposed into separate view components (not one monolithic page.tsx)? (audit B-02)
- [ ] Does the page use `useUserStore()` for store scoping (not hardcoded)?
- [ ] Does the page use `<RoleGuard module={MODULES.STORE_OPS}>` for access control? (NOT `MODULES.INVENTORY`)
- [ ] Does mobile (<768px) show card layout with sticky category headers and 44px touch targets?
- [ ] Does desktop (>=768px) show dense sortable table with columns: Item, Category, Qty, Status, Days Left, Demand, Suggested, UOM?
- [ ] Does responsive switch use Tailwind `md:` breakpoint (not JS resize)?
- [ ] Does default view show "Needs Attention" (Critical + Low only) with "Show All" toggle? (UX U1)
- [ ] Does sticky critical chip strip show named critical items above fold? (UX U2)
- [ ] Does order window banner show live countdown timer using server time? (UX U3)
- [ ] Does "Last Order" panel show past order summary with "Reorder This" pre-fill? (UX U4)
- [ ] Does "Order History" tab show all past orders with expandable line items?
- [ ] Does refresh button call `mutate()` on `useStoreInventory`? (UX U5)
- [ ] Are items grouped by cargo category (DRY/COLD/FROZEN/CHILLED)?
- [ ] Does the summary strip show Critical/Low/Overstock counts?
- [ ] Does each card/row show days-of-stock from demand data (null demand → "—" not 0)?
- [ ] Does Area Supervisor multi-store use lazy-load (NOT 46 simultaneous calls)? (audit B-03)
- [ ] Does AS with 0 stores show "No stores assigned" (not crash/empty table)? (audit B-05)
- [ ] Does Stockout Alert tab aggregate across supervised stores?
- [ ] Is no sync-freshness feature built (no ENCODE tracking, no sync timestamps)?
- [ ] Are existing `useWarehouseStock` and `useOrderableItems` hooks reused for stock + demand?
- [ ] Does `useOrderHistory(store)` hook exist and call `get_store_order_history` backend method? (A9-BE)
- [ ] Does `get_store_order_history` in `hrms/api/store.py` have `set_backend_observability_context()`? (DM-7)
- [ ] Does composite hook use `useUserStore().defaultStore` (docname), NOT `.warehouse_name`? (audit SM-3)
- [ ] Does `uom` come from `OrderableItem.uom`, not `WarehouseStockItem` (which has no uom)? (audit SM-1)
- [ ] Does `OrderWindowBanner` access `schedule?.allowed` (wrapped), NOT bare `allowed`? (audit SM-2)
- [ ] Is CSV export client-side with columns: item_code, item_name, cargo_category, actual_qty, status, days_of_stock, forecast_demand, suggested_order_qty, uom?
- [ ] Are `submitOrder`, `reportVariance`, `submitCycleCount` NOT imported on this page? (read-only enforcement)
- [ ] Evidence files committed to **BEI-ERP** repo (not bei-tasks)?

---

## Autonomous Execution Contract

- **completion_condition:**
  - `useStoreInventory()` composite hook exists and merges stock + demand
  - Store inventory page renders at `/dashboard/store-ops/inventory`
  - Page decomposed into view components (not monolithic page.tsx)
  - Sidebar entry visible for Store Staff, Store Supervisor, Area Supervisor roles
  - Default view shows "Needs Attention" filter (Critical + Low only)
  - Sticky critical chip strip shows named items above fold
  - Card list (mobile) and table (desktop) both show stock with demand data
  - Summary strip shows correct counts (Total, Critical, Low, Overstock)
  - Order window banner shows live countdown timer
  - Last Order panel accessible via header button
  - Order History tab shows past orders with expandable line items
  - Area Supervisor sees multi-store view with lazy-load (not 46 simultaneous calls)
  - Stockout Alert tab works
  - CSV export works (client-side)
  - Refresh button wired
  - Empty/error/loading states all handled
  - Page works at 375px mobile AND 1280px desktop
  - Order history backend method deployed (hrms repo, `get_store_order_history`)
  - All 18 L3 scenarios pass
  - Plan YAML status = COMPLETED, pushed
  - SPRINT_REGISTRY.md updated
  - Evidence files in BEI-ERP repo `output/l3/S122/`

- **stop_only_for:**
  - `useWarehouseStock` or `useOrderableItems` APIs return unexpected data structure
  - bei-tasks repo access issues
  - Business-data decision needed (e.g., what threshold = "overstock"?)

- **continue_without_pause_through:**
  - code → PR → Vercel deploy → L3 → closeout

- **blocker_policy:**
  - programmatic → fix and continue
  - Vercel deploy failure → check logs, fix, redeploy
  - business-data → pause

- **signoff_authority:** single-owner (Sam Karazi, CEO)

---

## Remote-Truth Baseline

| Repo | Branch | HEAD SHA |
|------|--------|---------|
| bei-tasks | main | *(fill at execution start)* |

---

## Agent Boot Sequence

1. Read this plan fully — including the Requirements Regression Checklist and Data Merge Strategy.
2. **Create sprint branch:** `cd ../bei-tasks && git fetch origin main && git checkout -b s122-store-inventory-dashboard origin/main`
3. Read `hooks/use-inventory.ts` — the `useWarehouseStock` and `useInventoryMatrix` hooks. Note the `WarehouseStockItem` type shape.
4. Read `hooks/use-ordering.ts` — the `useOrderableItems` and `useOrderSchedule` hooks. Note the `OrderableItem` type shape.
5. Read `hooks/use-user-store.ts` — the `useUserStore` hook. Note how `defaultStore` maps to warehouse identifier.
6. Read `app/dashboard/warehouse/inventory/daily/page.tsx` — the mobile card pattern to follow.
7. Read `app/dashboard/store-ops/ordering/page.tsx` — the store-scoped ordering workspace (thin wrapper).
8. Read `app/dashboard/store-ops/order-approvals/page.tsx` — the Area Supervisor store picker pattern.
9. Read `lib/constants.ts` lines 48-58 — existing STORE_OPS routes.
10. Read `components/layout/nav-main.tsx` — sidebar navigation structure.
11. Read `lib/roles.ts` — confirm `MODULES.STORE_OPS` includes required roles (use this, NOT `MODULES.INVENTORY`).
12. Read `hrms/api/store.py` — check if `BEI Store Order` DocType exists for order history query. Grep for store order list methods.
13. Read `bei-tasks/app/api/ordering/route.ts` — understand the action routing pattern for adding `get_store_order_history`.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

## Execution Workflow
- Develop in bei-tasks repo on branch `s122-store-inventory-dashboard`
- Test locally: `cd ../bei-tasks && npm run dev`
- Deploy: create PR to `main` → Vercel auto-deploys preview → merge → production auto-deploy
- Validate: L3 scenarios on https://my.bebang.ph after deploy
