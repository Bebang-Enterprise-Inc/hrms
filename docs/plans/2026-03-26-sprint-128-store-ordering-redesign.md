---
canonical_sprint_id: S129
display: Sprint 129
status: PR_CREATED
branch: s128-store-ordering-redesign
lane: single
created_date: 2026-03-26
completed_date:
deployed_at:
backend_pr: "hrms#367"
frontend_pr: "BEI-Tasks#262"
l3_result:
execution_summary: "Phase 1-3 implemented. Backend: B1 zero-history guard, B2 store picker filter, B3 warehouse_type migration, B4 Sentry, B5 UOM-aware rounding. Frontend: F1-F10 full redesign with composite hook, summary strip, table/card dual layout, Fill Suggested, Last Order, review sheet, offline queue. Awaiting merge+deploy+L3."
depends_on: S122
---

# S128 — Store Ordering Page Redesign

**Goal:** Redesign the store ordering page to match the S122 inventory dashboard pattern — summary strip, category filters, table/card dual layout, inline editable quantities — while fixing 3 data bugs (store picker showing 3PLs, identical demand values, fractional suggested quantities).

**Origin:** CEO review of Store Ordering page (2026-03-26) identified 4 issues: wrong stores in picker, bugged recommended qty (all 4.45), terrible UX (241-item scroll), and fractional quantities that need rounding.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

The Store Ordering page at `app/dashboard/store-ops/ordering/` (backed by `app/dashboard/inventory/ordering/page.tsx`) is the primary interface for store crews to place daily replenishment orders from the commissary. Current state:

1. **Store picker shows 3PL warehouses** — sam@bebang.ph sees "Jentec Storage Inc.", "Pinnacle Cold Storage", "Royal Cold Storage" instead of real stores. Root cause: `get_user_store()` returns all warehouses under "Stores - BEI" where user is `custom_area_supervisor`, but 3PLs sit in the same parent with no `warehouse_type` filter.

2. **Recommended qty = 4.45 for all items** — The `_build_recommendation_contract()` in `hrms/api/store.py` (line ~1393) calculates demand from order history. When a store has NO prior orders, `last_order_qty=0` and the formula falls back to a baseline of 1.0, producing demand=3.45 and recommended=4.45 for every item. This happens for 3PL warehouses (which never place orders) and new stores.

3. **241 items in a flat scroll** — No summary strip, no category grouping beyond accordion, no status badges, no "needs attention" filter. The S122 inventory page solved all of these — the ordering page should follow the same pattern.

4. **Fractional suggested quantities** — `suggested_qty=4.45` displayed as-is. Stores can't order 4.45 items — must be rounded up with `Math.ceil()`.

### Key decisions

- **D1: Reuse S122 component patterns** — SummaryStrip, CriticalChipStrip, search, category filters, dual layout. The ordering page adds editable quantity inputs, deviation tracking, and a submit flow.
- **D2: Backend demand fix uses minimum-order heuristic** — When `last_order_qty=0` AND `order_count=0`, the backend should return `suggested_qty=0` (no recommendation) rather than the misleading 4.45 default. Items with no history show "No history" instead of a fake number.
- **D3: Store picker filters by warehouse_type** — Add `warehouse_type="Store"` to all real stores in Frappe, then filter the picker query. 3PLs get `warehouse_type="3PL"`.
- **D4: Frontend rounds with Math.ceil()** — All displayed suggested/recommended quantities are rounded up to the nearest whole number. The raw float is preserved for backend submission.
- **D5: "Bird's eye" layout** — The new layout shows: stock on hand (from `get_store_stock`), recommended qty (from `get_orderable_items`), commissary available (ATP), projected demand (days of stock) — all in a single table row per item, with inline editable order qty.
- **D6: No MOQ for store orders** — `suggested_qty=0` for zero-history items is correct. MOQ applies only to supplier POs, not internal commissary → store transfers. (CEO decision 2026-03-26)
- **D7: 10% deviation threshold** — Any deviation > 10% from suggested requires a mandatory reason dropdown. Options: Expected Event, Weather Demand, Promo, Stock Correction, Other. (CEO decision 2026-03-26)
- **D8: Offline-first ordering (P0)** — The ordering page must work offline. Cache catalog + stock in IndexedDB. Queue orders when offline. Show "Pending" until uploaded. Sticky warning banner while orders are pending — crew must NOT close laptop thinking order is submitted. Sync on reconnect. (CEO decision 2026-03-26)
- **D9: No cross-store order copying** — Removed from scope. Stores have different demand patterns. (CEO decision 2026-03-26)
- **D10: "Fill Suggested" + "Last Order" bulk actions** — Two pre-fill buttons to reduce manual entry from 30 inputs to 5 adjustments. Highest-ROI UX feature per UX audit.
- **D11: Bottom sheet review (not slide-out)** — Mobile uses bottom sheet pattern (Grab/GCash) for order review. Desktop uses fixed sidebar. Requires explicit "Confirm & Submit" — no single-tap fire. (UX audit recommendation)

### Source references
- Store ordering workspace: `bei-tasks/app/dashboard/inventory/ordering/page.tsx`
- Ordering hooks: `bei-tasks/hooks/use-ordering.ts`
- User store hook: `bei-tasks/hooks/use-user-store.ts`
- Backend orderable items: `hrms/api/store.py` lines 1783-1920 (`get_orderable_items`)
- Demand calculation: `hrms/api/store.py` lines 1393-1430 (`_build_recommendation_contract`)
- Store stock API: `hrms/api/store.py` lines 5341-5396 (`get_store_stock`)
- S122 inventory components: `bei-tasks/app/dashboard/store-ops/inventory/_components/`

---

## Scope Size Warning

Total scope is **60 units** across 4 phases. This is under the 80-unit ceiling but large for one session. Recommended execution order: Phase 1 (backend, 10u) + Phase 2 (frontend, 36u) in one session, Phase 3 (offline, 12u) in a follow-up session if context is strained.

## Scope (60 units)

### Phase 1: Data Fixes (Backend — 10 units)

| Task | Type | Repo | File | Description | Units |
|------|------|------|------|-------------|-------|
| B1 | FIX | bei-erp | `hrms/api/store.py` | **[FIX] Demand fallback for zero-history items.** Add an early-return guard in `_build_recommendation_contract()` BEFORE the baseline calculation: `if flt(last_order_qty) <= 0 and flt(order_count) <= 0: return all-zero contract with has_order_history=False`. This bypasses the `baseline = max(1.0, ...)` fallback that currently produces 4.45 for zero-history items. **HARD BLOCKER:** Do NOT change the formula for items that DO have order history — only the zero-history fallback. The guard must check BOTH `last_order_qty=0 AND order_count=0`. Items with `order_count > 0` but `last_order_qty=0` still use the heuristic. | 3 |
| B2 | FIX | bei-erp | `hrms/api/store.py` | **[FIX] Store picker warehouse filter.** In `get_user_store()` / the warehouse list query, filter warehouses where `warehouse_type != '3PL'` or `is_group = 0`. Add a new function `_is_orderable_store(warehouse)` that returns False for 3PLs, cold storage, commissary, and test warehouses. | 3 |
| B3 | DATA | bei-erp | Frappe Warehouse | **[DATA] Set warehouse_type for all 52 stores.** Update Warehouse records: real stores → `warehouse_type='Store'`, 3PLs (Jentec, Pinnacle, Royal Cold Storage) → `warehouse_type='3PL'`, commissary → `warehouse_type='Commissary'`. Script via API, not manual. | 2 |
| B4 | FIX | bei-erp | `hrms/api/store.py` | **[FIX] Sentry observability.** Add `set_backend_observability_context(module="ordering", action="get_orderable_items")` to the get_orderable_items function if not already present. | 1 |
| B5 | FIX | bei-erp | `hrms/api/store.py` | **[FIX] Round suggested_qty server-side — INTEGER UOMs ONLY.** Define `INTEGER_UOMS = {"Nos", "Pcs", "Box", "Pack", "Bag", "Piece", "Dozen", "Set", "Unit", "Bundle", "Roll", "Can", "Bottle", "Sack", "Gallon"}`. For items with `stock_uom in INTEGER_UOMS`: `suggested_qty = math.ceil(raw)`. For fractional UOMs (KG, L, G, etc.): `suggested_qty = round(raw, 3)`. Add `raw_suggested_qty` and `raw_recommended_qty` to the `_build_recommendation_contract()` return dict BEFORE ceiling. **HARD BLOCKER:** Do NOT ceil KG/L/G items — `math.ceil(0.3 kg) = 1 kg` causes 3x over-ordering. | 2 |

### Phase 2: Frontend Redesign (bei-tasks — 36 units)

| Task | Type | Repo | File | Description | Units |
|------|------|------|------|-------------|-------|
| F1 | BUILD | bei-tasks | `hooks/use-store-ordering.ts` | **[BUILD] Composite ordering hook.** New hook that merges `useOrderableItems` + `useStoreStock` (same pattern as `useStoreInventory`) to produce `StoreOrderItem[]` with: `item_code`, `item_name`, `actual_qty` (store stock), `available_to_promise` (commissary), `suggested_qty` (rounded), `forecast_demand`, `days_of_stock`, `status`, `has_order_history`, `cargo_category`, `uom`. | 4 |
| F2 | BUILD | bei-tasks | `_components/OrderSummaryStrip.tsx` | **[BUILD] Summary strip for ordering.** 5 KPI cards: Total Items, Need Reorder (stock=0 or low), Sufficient (healthy), OOS at Commissary, Your Edits (items where qty != suggested). Plus "Already Ordered Today" boolean badge if store has submitted today. | 2 |
| F2.5 | BUILD | bei-tasks | `_components/OrderCriticalStrip.tsx` | **[BUILD] Sticky OOS chip strip.** Horizontal scrollable banner showing items with `actual_qty=0` as tappable chips. Tapping a chip auto-fills `order_qty = suggested_qty` for that item AND scrolls to it. Same pattern as S122 `CriticalChipStrip` but with auto-fill behavior. | 2 |
| F3 | BUILD | bei-tasks | `_components/OrderItemTable.tsx` | **[BUILD] Desktop table (>=768px).** Sortable columns: Item Name, Code, Category, On Hand, Status, Days Left, Demand/Day, Commissary ATP, Suggested Qty, **Order Qty** (editable input). Order Qty defaults to 0 (crew fills via "Fill Suggested" or manually). Highlighted yellow if edited. Green left-border "done" state when qty entered. **Deviation >10% triggers mandatory reason dropdown** (options: Expected Event, Weather Demand, Promo, Stock Correction, Other). **HARD BLOCKER:** Editable qty input MUST be `type="number"` with `min=0` and `step=1`. No fractional orders. Sticky category headers. | 6 |
| F4 | BUILD | bei-tasks | `_components/OrderItemCard.tsx` | **[BUILD] Mobile card (<768px).** Status-colored backgrounds (red=OOS, amber=low, green=healthy, blue=overstock) matching S122 `StockCard`. Item name + code at top, stock on hand, suggested qty. Expandable detail section for secondary info (demand, ATP, days left, risk rank). Green checkmark when qty entered. | 4 |
| F4.5 | BUILD | bei-tasks | `_components/QtyStepperInput.tsx` | **[BUILD] Qty stepper for mobile.** `[-] [qty] [+]` buttons flanking number input. 44x44px touch targets. Step=1 for discrete UOMs, step=0.1 for KG/L. Long-press for fast increment. Standard PH e-commerce pattern (Shopee/Lazada/Grab). Used inside F4 cards. | 2 |
| F5 | EXTEND | bei-tasks | Ordering page | **[EXTEND] Replace flat scroll with filtered layout.** Search input (debounced 300ms), category filters (FC/DRY/FM), "Need Reorder" toggle (**default ON** — show only items needing reorder). Dual layout (cards < md, table >= md). Remove old accordion item list. Keep order window banner. Sticky category headers. | 5 |
| F5.5 | BUILD | bei-tasks | Ordering page | **[BUILD] "Fill Suggested" bulk action.** Button in the controls bar that pre-fills `order_qty = suggested_qty` for all currently visible (filtered) items. Reduces 30 manual inputs to 5 adjustments. Crew taps "Fill Suggested" then adjusts the few items they disagree with. This is the single highest-ROI UX feature. | 2 |
| F5.6 | BUILD | bei-tasks | Ordering page | **[BUILD] "Last Order" pre-fill.** Button that loads the store's most recent order via `get_store_order_history` and pre-fills quantities. Covers the ~80% case where today's order is similar to yesterday's. | 1 |
| F6 | BUILD | bei-tasks | `_components/OrderReviewSheet.tsx` | **[BUILD] Order review bottom sheet (mobile) / fixed sidebar (desktop).** Mobile: full-screen bottom sheet sliding up with scrollable order summary, per-item "edit" link, total estimated cost, delivery date. Desktop: fixed right sidebar (replaces the 320px column currently wasted on store picker — picker moves to page header). "Confirm & Submit" button (not just "Submit"). Success screen with order number + "View Order" link. **HARD BLOCKER:** Submit requires explicit "Confirm & Submit" tap — no single-tap fire. | 4 |
| F7 | FIX | bei-tasks | Store picker | **[FIX] Filter 3PLs from store dropdown.** The `useUserStore` hook or store picker filters out warehouses where `warehouse_type` is not 'Store'. | 1 |
| F8 | BUILD | bei-tasks | PR + deploy | **[BUILD] Create PR, push. Vercel auto-deploys.** Single PR for all Phase 2 tasks. | 1 |
| F9 | BUILD | bei-tasks | Ordering page | **[BUILD] Order history banner.** Before item list, show dismissible banner if store has already submitted an order today: "You submitted Order #SO-xxx at 8:45 AM today. Submitting again creates an additional order for Area Supervisor review." Uses `get_store_order_history` data. | 1 |
| F10 | PERF | bei-tasks | Ordering page | **[PERF] List virtualization.** Virtualize the 241-item list with `@tanstack/react-virtual`. Only render items in viewport + 5-item buffer. Memoize item rows with `React.memo`. Critical for low-end Android devices. Hide sticky bottom bar when input is focused (prevents keyboard overlap). | 1 |

### Phase 3: Offline Ordering (bei-tasks — 12 units)

| Task | Type | Repo | File | Description | Units |
|------|------|------|------|-------------|-------|
| O1 | BUILD | bei-tasks | `lib/offline/order-queue.ts` | **[BUILD] Offline order queue with idempotency.** IndexedDB store for pending orders. Generate `crypto.randomUUID()` per order on creation (not submission). Status enum: `pending_upload`, `sync_failed`, `rejected_by_server`, `uploaded`. Retry on `navigator.onLine` for retryable errors (503, 429, timeout). Terminal errors (400, 422) transition to `sync_failed` with server rejection reason. Expose `usePendingOrders()` hook. **HARD BLOCKER:** Backend must deduplicate by order UUID — add `idempotency_key` to `submit_order` endpoint. Disable Submit button while any order is `pending_upload`. Surface `sync_failed` errors in UI with edit+resubmit option. | 4 |
| O2 | BUILD | bei-tasks | `lib/offline/catalog-cache.ts` | **[BUILD] Catalog cache with 24h TTL.** On SWR `onSuccess`, explicitly write response to IndexedDB with timestamp. On load, if network fails AND cache age < 24h, serve cached data with "Cached data from {time}" banner. If cache > 24h, show "Catalog too old — connect to internet" error. Do NOT cache catalog at the service worker layer — use IndexedDB only as the persistence layer. SWR reads IndexedDB as `fallbackData`. On reconnect, SWR revalidation must also refresh the IndexedDB copy. | 3 |
| O3 | BUILD | bei-tasks | `_components/OfflineBanner.tsx` | **[BUILD] Connection status banner + pending indicator.** Sticky banner: "No internet connection — ordering from cached data. Your order will upload when connected." When pending orders exist: amber banner "1 order pending upload — stay connected." On successful sync: green toast "Order uploaded successfully." **HARD BLOCKER:** The banner must be impossible to dismiss while orders are pending. Crew must NOT close the laptop thinking the order is submitted when it's still pending. | 3 |
| O4 | BUILD | bei-tasks | Service worker | **[BUILD] Service worker via Serwist.** Use `@serwist/next` (App Router-compatible successor to next-pwa). Cache ordering page shell (HTML/JS/CSS) for offline load. Do NOT cache catalog API at SW layer (O2 handles via IndexedDB). **Pre-build spike required:** Register a no-op SW in dev, verify it activates in Chrome DevTools. If Serwist fails with Next.js 16 + Turbopack, fall back to raw Workbox with manual registration in `app/layout.tsx`. | 3 |

### Phase 4: Closeout (2 units)

| Task | Type | Repo | Description | Units |
|------|------|------|-------------|-------|
| C1 | L3 | both | Run L3 scenarios **in a fresh agent session** (60 units exceeds 40-unit L3 threshold). Commit evidence with `git add -f output/l3/S128/`. | 1 |
| C2 | DOC | bei-erp | Update plan YAML, SPRINT_REGISTRY.md. Push to production. | 1 |

**Total: 62 units** (11 backend + 36 frontend + 13 offline + 2 closeout)

*+2 units from audit amendments: B5 expanded to 2u (UOM whitelist), O1 expanded to 4u (idempotency + error states)*

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| test.crew1@bebang.ph | Open ordering page | Summary strip visible with 5 KPIs. "Need Reorder" ON by default (not all 241 items). No 3PL stores in picker. | Layout or store filter broken |
| test.crew1@bebang.ph | Check item with no order history | Shows suggested=0 with "No history" indicator — NOT 4.45 | B1 demand fallback not fixed |
| test.crew1@bebang.ph | Check item with stock > 0 | Suggested qty is a whole number (rounded up), store stock visible in same row | B5 rounding or F1 merge broken |
| test.crew1@bebang.ph | Tap "Fill Suggested" button | All visible items get order_qty = suggested_qty pre-filled. "Your Edits" count stays 0 (matching suggested). | F5.5 bulk fill broken |
| test.crew1@bebang.ph | Edit order qty to 15% above suggested for an item | Mandatory reason dropdown appears (>10% deviation). Select "Promo". Deviation badge shows "+15%". | F3 deviation threshold broken |
| test.crew1@bebang.ph | Tap OOS chip on critical strip | Auto-fills suggested qty for that item AND scrolls to it in the list | F2.5 critical strip broken |
| test.crew1@bebang.ph | Tap "Review Order" | Bottom sheet (mobile) or sidebar (desktop) shows: items with qty>0, estimated cost, delivery date. "Confirm & Submit" button visible. | F6 review sheet broken |
| test.crew1@bebang.ph | Tap "Confirm & Submit" | Order submits. Success screen with order number. "Already Ordered Today" badge appears in summary. | Submit flow broken |
| test.crew1@bebang.ph | Tap "Last Order" pre-fill | Quantities from most recent order populate. Crew can adjust. | F5.6 last order broken |
| test.area@bebang.ph | Open ordering, check store picker | Shows only real stores, NOT Jentec/Pinnacle/RCS | B2/B3 store filter broken |
| test.crew1@bebang.ph | Disconnect network, try to order | Page shows cached data with "No internet" banner. Order queues as "Pending upload". Amber warning "Stay connected." | O1-O3 offline broken |
| test.crew1@bebang.ph | Reconnect network | Pending order syncs. Green toast "Order uploaded." Banner clears. | O1 sync broken |

Evidence files:
```
output/l3/S128/form_submissions.json
output/l3/S128/api_mutations.json
output/l3/S128/state_verification.json
```

---

## Requirements Regression Checklist

- [ ] Does the store picker exclude 3PLs, cold storage, and commissary warehouses? (D3)
- [ ] Does `suggested_qty` display as a whole number via Math.ceil? (D4)
- [ ] Do items with zero order history show suggested_qty=0, NOT 4.45? (D2, D6)
- [ ] Is there NO minimum order quantity for store orders? MOQ is supplier POs only. (D6)
- [ ] Is `has_order_history` flag present in the API response? (B1)
- [ ] Does the ordering table show store stock on hand alongside suggested qty? (D5)
- [ ] Does the ordering table show commissary ATP? (D5)
- [ ] Does the ordering table show days of stock? (D5)
- [ ] Is the editable Order Qty input type="number" with min=0 and step=1? (F3)
- [ ] Does deviation > 10% trigger a mandatory reason dropdown? (D7)
- [ ] When suggested_qty=0 (zero-history), is the deviation check SKIPPED entirely? (no division by zero)
- [ ] Are reason options: Expected Event, Weather Demand, Promo, Stock Correction, Other? (D7)
- [ ] Does "Need Reorder" default to ON (not Show All)? (F5)
- [ ] Does "Fill Suggested" pre-fill all visible items? (F5.5, D10)
- [ ] Does "Last Order" pre-fill from most recent order? (F5.6, D10)
- [ ] Does the critical strip auto-fill qty when chip is tapped? (F2.5)
- [ ] Is order review a bottom sheet (mobile) / sidebar (desktop), NOT a slide-out? (D11)
- [ ] Does submit require "Confirm & Submit" — no single-tap fire? (D11)
- [ ] Does the page show "Already Ordered Today" banner if applicable? (F9)
- [ ] Does offline ordering work — cached catalog, queued orders, pending indicator? (D8)
- [ ] Does the pending banner persist until order uploads — crew cannot dismiss it? (D8, O3)
- [ ] Is the existing `submit_order` backend unchanged (no breaking changes)?
- [ ] Does every new/modified `@frappe.whitelist()` call `set_backend_observability_context()`? (B4)

---

## Autonomous Execution Contract

- **completion_condition:**
  - Store picker shows only real stores (no 3PLs)
  - Items with no history show suggested_qty=0
  - All suggested quantities rounded to whole numbers
  - New table/card layout live with editable quantities
  - L3 scenarios pass
  - Plan YAML status = COMPLETED
  - SPRINT_REGISTRY.md updated
  - Evidence committed: `git add -f output/l3/S128/ docs/plans/ && git push`

- **stop_only_for:**
  - Serwist/SW spike fails on Next.js 16 (O4 pre-build gate)
  - Business decision: what catalog TTL is acceptable for offline ordering? (default: 24h)
  - Backend idempotency key implementation blocked by Frappe constraint

- **continue_without_pause_through:**
  - Phase 1 backend → backend PR → user merge+deploy → Phase 2 frontend → frontend PR → user merge+deploy → Phase 3 offline → PR → closeout

- **phase_sequencing:**
  - Phase 1 backend PR must be merged and deployed BEFORE Phase 2 frontend begins (frontend tests against live backend)
  - Phase 3 offline can begin after Phase 2 PR is created (doesn't need deploy)

- **governor_feedback_loop:**
  | User Decision | Builder Response |
  |---|---|
  | APPROVE + Merge | Proceed to next phase |
  | REJECT | Read PR comment, fix, push to same branch |
  | NEEDS_FIX | Apply suggested fix, push |
  | Merge Conflict | `git fetch origin && git rebase origin/production`, resolve, force-push |
  | Deploy Failure | Check deploy logs, fix if code issue, push |

- **confidence_note:** 60-unit plan with large diff. Reviews with confidence < 0.80 pause auto-merge. Recommend splitting PR per phase for cleaner reviews.

- **signoff_authority:** single-owner (Sam Karazi, CEO)

---

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch (bei-erp):** `git fetch origin production && git checkout -b s128-store-ordering-redesign origin/production` for backend fixes.
3. **Create sprint branch (bei-tasks):** `cd ../bei-tasks && git fetch origin main && git checkout -b s128-store-ordering-redesign origin/main` for frontend.
4. Read `hrms/api/store.py` — the `_build_recommendation_contract()` function (~line 1393) and `get_orderable_items()` (~line 1783).
5. Read `bei-tasks/hooks/use-ordering.ts` and `bei-tasks/hooks/use-user-store.ts`.
6. Read `bei-tasks/app/dashboard/store-ops/inventory/_components/` for the S122 patterns to replicate.
7. Execute Phase 1 (backend), then Phase 2 (frontend).
8. **Commit evidence:** `git add -f output/l3/S128/ && git push` (required by release manager gate).

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.
