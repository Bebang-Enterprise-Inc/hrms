# S122 Store Inventory Dashboard — Frontend Audit v2 Findings

Audited plan: `docs/plans/2026-03-25-sprint-122-store-inventory-dashboard.md`
Audit date: 2026-03-26

---

## Check 1: useStoreInventory hook spec completeness

**Status: MOSTLY COMPLETE — one ambiguity remains**

The spec is detailed enough to implement in most respects:
- Input parameter (`storeWarehouse`) is named.
- Both source hooks are named (`useWarehouseStock`, `useOrderableItems`).
- Join key (`item_code`), join direction (left on stock), and field precedence are all explicit.
- `days_of_stock` computation is given (`actual_qty / forecast_demand`).
- Return shape (`StoreInventoryItem[]` + `isLoading`, `error`, `mutate`) is defined.
- Division-by-zero guard: NOT specified. When `forecast_demand === 0`, `actual_qty / forecast_demand` produces `Infinity`. The spec says null demand → "N/A" but does NOT address `forecast_demand === 0` (which is a valid orderable-item state meaning "no historical demand"). An implementor may silently produce `Infinity` days-of-stock and display garbage. The spec must say: "if `forecast_demand` is 0 or null, `days_of_stock = null`."
- The `storeWarehouse` vs `store` parameter mismatch is present: `useWarehouseStock` takes `storeWarehouse` (a warehouse identifier), but `useOrderableItems` takes `store` (a store identifier). The composite hook receives `storeWarehouse` but must derive or receive `store` separately to call the second hook. This mapping is not explained and an implementor will not know where to get the `store` value from inside the composite hook. This is a gap — state whether `useUserStore().defaultStore` provides the `store` value, or add `store` as a second parameter.

---

## Check 2: StockCard mobile fields and StockTable desktop columns

**Status: COMPLETE**

Task A1 lists both explicitly.

Mobile card fields (from A1): item_name (bold 16px), item_code (muted 12px), cargo_category badge, actual_qty (24px bold), status badge (Critical/Low/Healthy), "~X days" subtext, UOM. Touch target 44x44px. Sticky category headers. All anatomically sufficient.

Desktop table columns (from A1): Item (name+code), Category, Qty, Status, Days Left, Demand/Day, Suggested Order, UOM. Sortable columns: Qty, Days Left, Demand. Default sort: risk-first then alpha. Fully specified.

No gaps in field/column anatomy.

---

## Check 3: "Needs Attention" default view filtering rule

**Status: MOSTLY COMPLETE — threshold for inclusion not fully locked**

Task A7 states: "only Critical + Low + OOS items shown on first load."

The filtering rule maps to: `is_low_stock === true OR is_oos === true`. This is derivable from the `StoreInventoryItem` type. However, "Critical" and "Low" are status badges driven by `is_low_stock` and presumably a threshold, but the plan does not define what distinguishes "Critical" from "Low" within the `StoreInventoryItem` type. The warehouse matrix uses `getStatusClasses()` which implies a separate classification function, but no Critical/Low split field exists in the `StoreInventoryItem` type as defined. If `is_low_stock` is the only boolean, an implementor cannot distinguish Critical from Low for the default filter without knowing the classification logic. The spec should either add a `status: "critical" | "low" | "healthy"` field to `StoreInventoryItem` or explicitly state how Critical is detected (e.g., `risk_rank >= 8` or `actual_qty === 0`).

The `stop_only_for` contract lists "what threshold = overstock?" as a business-data pause trigger but does NOT list the Critical/Low boundary as a stop trigger — meaning an implementor could guess and continue, producing the wrong default filter behavior.

---

## Check 4: Order History tab (A9) — API wiring

**Status: GAP — hook name and endpoint unspecified**

Task A9 says "Uses existing order list API" but does not name the hook. The data flow diagram in the Design Rationale section shows `useOrders(store) → past orders for history tab`, but `useOrders` is not referenced anywhere in the Agent Boot Sequence read list and is not verified to exist. There is no instruction to read a `hooks/use-orders.ts` or equivalent file before starting.

An implementor has no confirmed hook signature, no confirmed return type (field names for Order Date, Order ID, Items Count, Total Qty, Status, Submitted By), and no confirmed endpoint. If `useOrders` does not exist or has a different name, the implementor hits a blocker with no guidance on what to stop for (it is not listed in `stop_only_for`).

**Required fix:** Add `hooks/use-orders.ts` (or equivalent) to the Agent Boot Sequence read list (step X after step 8). Confirm the return type contains the fields required by the `OrderHistoryView` table, or specify them explicitly in A9.

---

## Check 5: Last Order panel (A6) — API wiring

**Status: GAP — data source not confirmed, "Reorder This" handler undefined**

Task A6 says `LastOrderPanel` shows the last order's date, items, quantities, status, and submitter, and has a "Reorder This" button. Two issues:

1. The data source is not named. The data flow diagram shows `useOrders(store)` for the history tab but does not explicitly say `LastOrderPanel` uses it. An implementor may assume it reads the same `useOrders` hook (sorted, take first), but this is not stated. If the hook is paginated (A9 says 20/page), taking the first result is correct only if sorted newest-first server-side. Not confirmed.

2. "Reorder This" is described as "navigates to ordering, does NOT auto-submit" and "pre-fills the ordering page with last order quantities." There is no specification of how pre-fill is achieved — no URL param scheme, no shared state mechanism (URL query params? localStorage? context?), no mention of which field in the ordering page accepts pre-filled quantities. This CTA is named but its wiring mechanism is entirely undefined. The ordering page (`app/dashboard/store-ops/ordering/page.tsx`) is in the Boot Sequence read list but the plan does not state what pre-fill interface (if any) that page exposes.

**Required fix:** Name the hook used for last-order data. Specify the pre-fill mechanism (e.g., "navigate to `/dashboard/store-ops/ordering?prefill=<order_id>` and the ordering page reads `?prefill` on mount to pre-populate quantities").

---

## Check 6: Lazy-load pattern for multi-store (B2) — initial vs expand clarity

**Status: MOSTLY CLEAR — one gap in batch summary call**

Task B2 states:
- All store rows render collapsed with name only.
- Stock detail fires only on row expand.
- Initial summary counts (critical/low per store, last order date) come from "a lightweight summary call per store on initial load, batched in groups of 5."

The expand-on-demand pattern is clear. The gap is in the initial batch summary call: no hook or endpoint is named for the per-store summary. `useStoreInventory` returns full item arrays, not counts. If no lightweight summary endpoint exists, the implementor must either call `useStoreInventory` for all stores at once (violating the fan-out rule) or compute counts from a different source. The plan says "if a server-side aggregation endpoint exists or is added later, switch to that" — but gives no guidance on what to call for the summary in S122. An implementor forced to call `useStoreInventory` per store in batches of 5 still fires up to 46 calls total, just staggered, which is the fan-out problem in slow motion.

**Required fix:** Either name the hook/endpoint used for per-store summary counts, or acknowledge that summary counts are also lazy (shown only after expand) and the collapsed row shows store name only with no counts until expanded.

---

## Check 7: CTAs named but not wired to handlers

**Status: TWO UNRESOLVED CTAs**

1. **"Reorder This" (A6):** Named, described behaviorally ("pre-fills ordering page"), but no wiring mechanism defined. Detailed in Check 5 above.

2. **"Retry" in error banner (C1):** The plan says error banner includes "[Retry]" wired to `mutate()`. This is sufficiently specified — `mutate()` is a known SWR/hook pattern. Not a gap.

3. **"Place Order" link in OrderWindowBanner (A5):** Navigates to `/dashboard/store-ops/ordering`. Route exists per A4 context. Not a gap.

4. **Chip strip tap-to-scroll (A3):** "Tap chip → scroll main list to that item." No implementation guidance on scroll mechanism (e.g., `document.getElementById(item_code).scrollIntoView()` or a ref-based approach). On mobile this requires the target element to have a stable DOM ID. Neither the StockCard spec nor the CriticalChipStrip spec mentions assigning IDs. This is a minor gap that will surface at implementation time but will likely be solved programmatically. Low severity but worth noting.

**High-severity unwired CTA: "Reorder This" in LastOrderPanel.** No pre-fill protocol specified.

---

## Check 8: Countdown timer (A5) — server-time implementation

**Status: GAP — mechanism not specified**

Task A5 says the countdown uses "server time not device time" and shows "HH:MM to cutoff." The plan does not specify:

1. How server time is obtained. Options: (a) `useOrderSchedule` returns a `server_now` timestamp alongside `cutoff_time`; (b) a separate `/api/server-time` endpoint; (c) compute offset at mount by comparing `Date.now()` against a server-returned timestamp. None of these are specified.
2. What `useOrderSchedule` actually returns. The data flow diagram shows `OrderSchedule { allowed, cutoff_time, next_delivery_day }` but does not include a server timestamp field.
3. How the client-side interval is initialized — no mention of `useEffect` + `setInterval` pattern or a specific timer utility.

If `useOrderSchedule` does not return a server timestamp, an implementor has no way to implement server-time-accurate countdown without adding a field to the hook response or calling a second endpoint — which may require a backend change, contradicting the "100% frontend" sprint claim.

**Required fix:** Either confirm `useOrderSchedule` returns a `server_now` or `cutoff_epoch` field sufficient to drive a countdown without a new backend call, or add a note that the implementor should read `hooks/use-order-schedule.ts` to check what is available and fall back to device time with a comment if server time is not exposed.

---

## Summary Table

| Check | Item | Severity | Status |
|-------|------|----------|--------|
| 1 | Hook spec: division-by-zero in days_of_stock | Medium | GAP |
| 1 | Hook spec: storeWarehouse vs store param mismatch | Medium | GAP |
| 2 | StockCard fields + StockTable columns | — | COMPLETE |
| 3 | "Needs Attention" filter: Critical vs Low boundary undefined | Medium | GAP |
| 4 | Order History (A9): hook/endpoint not named | High | GAP |
| 5 | Last Order (A6): data source not confirmed | Medium | GAP |
| 5 | "Reorder This" CTA: pre-fill mechanism undefined | High | GAP |
| 6 | Multi-store lazy-load: batch summary hook unnamed | Medium | GAP |
| 7 | "Reorder This" CTA unwired | High | (same as 5) |
| 7 | Chip tap-to-scroll: DOM ID assignment not specified | Low | GAP |
| 8 | Countdown timer: server-time source not specified | High | GAP |

**Remaining high-severity gaps: 3**
- A9 Order History hook/endpoint unnamed
- A6 "Reorder This" pre-fill mechanism undefined
- A5 Countdown server-time source not specified

These three gaps will produce implementation blockers or incorrect behavior that the L3 scenarios will catch. They should be resolved in the plan before handing off to an execution agent.
