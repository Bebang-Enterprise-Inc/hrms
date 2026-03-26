# S122 Store Inventory Dashboard — Frontend Audit Findings

**Auditor:** Frontend Architecture Review
**Date:** 2026-03-25
**Plan Summary:** Phase A (My Stock, dual layout), Phase B (Area Supervisor multi-store), Phase C (Polish + Sentry). 23 units, route `/dashboard/store-ops/inventory`.

---

## Audit Score: 4.5 / 10

**Status: NOT SAFE TO BUILD as specified.** Too many gaps would force an agent to invent architecture, which is the primary shell-risk pattern. Findings below are categorized by severity.

---

## 1. Dual-Layout Specification (Cards Mobile / Table Desktop)

**Rating: INSUFFICIENT — Shell Risk: HIGH**

The plan states "responsive dual layout — cards on mobile, sortable table on desktop" without specifying:

- **Breakpoint:** No Tailwind breakpoint defined (`sm:`, `md:`, `lg:`?). The existing `use-mobile.ts` hook uses a threshold — the plan must say whether to use that hook or pure CSS. Inconsistency here creates divergent behavior in mid-range viewport widths (tablets in landscape).
- **Card anatomy:** No fields listed per card. The `WarehouseStockItem` interface has `item_code`, `item_name`, `warehouse`, `actual_qty`, `reserved_qty`, `available_qty`, `reorder_point`, `is_low_stock`. Which of these appear on the mobile card? The agent will invent a layout.
- **Table columns:** Not specified. Column order, sortable vs non-sortable columns, and default sort key are all undefined.
- **Sticky header on mobile:** Whether the summary strip (Critical/Low/Overstock counts) is sticky on scroll is not addressed (see §6).
- **Touch target minimum:** No mention of 44px minimum touch targets on mobile cards or filter chips.

**Agent risk:** An agent building both layouts will make 6+ arbitrary decisions, producing inconsistent UX that requires a full redesign pass.

---

## 2. CTA Wiring Completeness

**Rating: PARTIALLY SPECIFIED — Shell Risk: MEDIUM**

| CTA | Specified? | Finding |
|-----|-----------|---------|
| CSV export | Named | No column list, no filename convention, no role gate (should Area Supervisor get store-level or aggregate CSV?) |
| Filter chips (category) | Named | No chip values listed. `useWarehouseStock` accepts `itemGroup` param — are chip values item groups from Frappe, or hardcoded? |
| Search | Named | Client-side or server-side? `useWarehouseStock` does not expose a query param — client filter only. Not stated. |
| Sort | Named | No sort keys listed, no default sort, no sort direction toggle spec |
| Order banner link | Named | Target route not specified. Should link to `/dashboard/store-ops/ordering` or the active order's detail? If `useOrderSchedule.allowed === false`, does the banner still link? |
| Store picker (Phase B) | Named | No specified behavior when Area Supervisor selects "all stores" vs one — does the table aggregate or paginate? |
| Stockout tab | Named | No definition of "stockout" threshold. `WarehouseStockItem.available_qty <= 0`? Or `is_low_stock === true`? These are different conditions. |
| Refresh/mutate button | Missing | Plan does not mention a manual refresh CTA. All three hooks (`useWarehouseStock`, `useOrderableItems`, `useOrderSchedule`) return `mutate` — a refresh button is standard on inventory dashboards but absent from spec. |

**Anti-pattern flagged:** The CSV export CTA is named but no library is specified. `papaparse` vs browser `Blob` vs a backend export endpoint — this is a cost-model decision if a backend endpoint is needed. The plan says "no new backend APIs" which constrains CSV to client-side generation, but this is implicit, not stated.

---

## 3. Dependency Hook Mapping

**Rating: PARTIALLY CORRECT — Shell Risk: MEDIUM**

Verified hooks exist in codebase:

| Hook | Exists | Signature Notes |
|------|--------|-----------------|
| `useWarehouseStock(warehouse, itemGroup, includeZeroStock)` | YES (`hooks/use-inventory.ts:430`) | Takes warehouse string, NOT store name. Plan must specify how store name maps to warehouse identifier. |
| `useOrderableItems(store?, date?)` | YES (`hooks/use-ordering.ts:163`) | Returns `OrderableItem[]` with demand/forecast fields — **different schema** than `WarehouseStockItem`. |
| `useOrderSchedule(store?, date?, deliveryDate?)` | YES (`hooks/use-ordering.ts:190`) | Returns `OrderSchedule` with `allowed`, `cutoff_time`, `next_delivery_day`. |
| `useUserStore(surface?)` | YES (`hooks/use-user-store.ts`) | Returns `stores[]`, `defaultStore`, `isMultiStore`, `role`. |

**Critical gap — `useWarehouseStock` takes a warehouse identifier, not a store name.** `useUserStore` returns `StoreInfo.name` (warehouse name as string). The plan assumes these connect directly, but the mapping is not guaranteed. If `StoreInfo.name` is a Frappe Warehouse docname, it works. If it is a display label, it breaks silently. The plan must specify the exact field chain: `useUserStore().defaultStore → useWarehouseStock(defaultStore)`.

**Missing hook:** `useOrderableItems` is named in the plan but it is the **demand/ordering catalog hook**, not a stock level hook. The plan describes merging it with `useWarehouseStock` to produce the displayed table. No merge strategy is defined (see §5).

---

## 4. Empty / Error / Partial Data States

**Rating: NOT SPECIFIED — Shell Risk: HIGH**

The plan does not describe any loading, empty, or error state. Current hook behavior:

- `useWarehouseStock`: returns `items: []` on error (silent empty). If `warehouse` param is falsy, SWR key is `null` (no fetch, no error, no loading — just empty). An agent unaware of this will display an empty table with no user feedback if `useUserStore` is still loading.
- `useOrderableItems`: similarly returns `items: []` on error.
- `useOrderSchedule`: returns `schedule: null` on error or loading. The plan says to show an "order window banner" — if `schedule` is `null`, what renders? Nothing? A skeleton? An error message?

**Partial data scenario (the most dangerous gap):**

> `useOrderableItems` returns 50 items with demand data, but `useWarehouseStock` returns 0 items (warehouse not yet synced or wrong identifier).

The plan provides no guidance. An agent might:
1. Show an empty table (data loss — user sees nothing)
2. Show only the orderable items with no stock qty (fabricated merge)
3. Show an error banner (blocks the page)

This scenario is **production-likely** since store warehouse sync can lag.

**Recommended spec additions:**
- Show skeleton cards/rows during any hook `isLoading === true`
- Show "No stock data available" empty state with last-sync timestamp when items is empty
- Show `useOrderSchedule` banner as "Order window unavailable" (grey, non-linking) when `schedule === null`
- When `useWarehouseStock` is empty but `useOrderableItems` has items, show items with stock qty as "—" (not 0)

---

## 5. Data Merge Strategy

**Rating: UNDEFINED — Shell Risk: CRITICAL**

This is the most architecturally dangerous gap. The plan says "useWarehouseStock + useOrderableItems merged" but provides zero specification.

**The two hook schemas are incompatible:**

`WarehouseStockItem` (from `useWarehouseStock`):
```typescript
{ item_code, item_name, warehouse, actual_qty, reserved_qty, available_qty, reorder_point, is_low_stock }
```

`OrderableItem` (from `useOrderableItems`):
```typescript
{ item_code, item_name, uom, packaging_description, cargo_category, suggested_qty, recommended_qty,
  risk_rank, lane, source_warehouse, available_stock, available_to_promise, forecast_demand,
  safety_buffer, is_oos, last_order_qty, unit_price }
```

**Note:** `OrderableItem.available_stock` and `WarehouseStockItem.actual_qty` represent overlapping concepts but are sourced differently. Using both without a merge rule will produce columns that contradict each other visibly.

**Required spec additions:**
- Define the join key: `item_code` (confirmed present in both)
- Define which fields win when both have a value for the same concept (e.g., available qty)
- Define what to do with items in `useOrderableItems` but NOT in `useWarehouseStock` (demand exists, no stock record)
- Define what to do with items in `useWarehouseStock` but NOT in `useOrderableItems` (stock exists, not orderable)
- Specify whether the merged list is the union or the intersection of both item sets
- Specify the `useMemo` dependency array to avoid stale closures on filter/sort

**Suggested merge contract:**
```typescript
// left join: all warehouse stock items, enriched with ordering demand where available
const mergedItems = useMemo(() => {
  const demandMap = new Map(orderableItems.map(i => [i.item_code, i]));
  return stockItems.map(s => ({ ...s, demand: demandMap.get(s.item_code) ?? null }));
}, [stockItems, orderableItems]);
```
Without this or equivalent being specified, two agents building this independently will produce different merge behaviors.

---

## 6. Mobile Interaction Model

**Rating: INCOMPLETE — Shell Risk: MEDIUM**

- **Sticky headers:** Not specified. The summary strip (Critical/Low/Overstock counts) should likely be sticky on mobile scroll, but this is not stated. Standard pattern for this type of dashboard is `position: sticky; top: 0; z-index: 10` within the scroll container, but it must be specified.
- **Touch targets:** No minimum size specified. Filter chips and sort controls must be at least 44x44px on mobile; Shadcn `Badge` components used as filter chips are typically 24px tall — an agent will use the default.
- **Scroll behavior:** The plan does not address whether the filter chip row is horizontally scrollable on mobile (overflow-x: auto) or wraps. With 6+ categories, wrapping breaks the layout. Horizontal scroll is the correct pattern but must be stated.
- **Swipe-to-reveal actions on cards:** Not specified (neither present nor absent). If stockout items need a quick-order action, swipe-to-reveal is the expected mobile pattern.
- **Pull-to-refresh:** Not mentioned. Standard on mobile inventory views. Hooks expose `mutate` — wiring is straightforward but must be called out.
- **Empty state illustration/icon:** Not specified for mobile card view.

---

## 7. Anti-Abuse / Inventory Manipulation Controls

**Rating: ABSENT — Shell Risk: LOW (this is a read-only view, but with a gap)**

The plan describes a read-only inventory dashboard with a CSV export. Controls to assess:

- **CSV export rate limiting:** Not mentioned. A Store Staff user exporting inventory data repeatedly (competitor intelligence risk) has no rate limit or audit trail in the spec.
- **Store picker (Phase B, Area Supervisor):** The `useUserStore.isMultiStore` flag controls visibility. The plan does not specify whether the store picker dropdown is filtered to the Area Supervisor's assigned stores or shows all stores. `useUserStore` returns only the user's assigned stores, so this is implicitly safe — but it should be explicit in the spec.
- **Read-only enforcement:** The plan correctly calls for no write operations on this page. However, the plan should explicitly state that `submitOrder`, `reportVariance`, and `requestShelfExtension` from `useInventory` are NOT imported or called — to prevent an agent from wiring order submission to the inventory cards (a common agent drift pattern when both hooks are in scope).
- **No stock count submission:** The plan should state that cycle count submission is disabled (it already is in `useInventory` — `submitCycleCount` returns a disabled error). Explicit call-out prevents agent confusion.

---

## 8. RBAC Verification

**Rating: CORRECT — No Issues**

`MODULES.STORE_OPS` in `roles.ts` includes `Store Staff`, `Store Supervisor`, `Area Supervisor`, `System Manager`, `Administrator`. This matches the plan's stated roles. `RoleGuard` component is already used in the store-ops hub page — the same pattern should be specified for the inventory sub-route.

**Gap:** The plan does not specify whether `MODULES.INVENTORY` (which also includes `Warehouse User`) should be used instead of or in addition to `MODULES.STORE_OPS`. `MODULES.INVENTORY` grants access to Warehouse Users who should NOT see the store-ops inventory dashboard. `MODULES.STORE_OPS` is the correct guard — but the plan should explicitly name the guard module.

---

## 9. Route Registration

**Rating: NOT VERIFIED IN PLAN**

The route `/dashboard/store-ops/inventory` does not exist yet (directory `app/dashboard/store-ops/inventory/` is absent). The plan must specify:
- Whether this is `page.tsx` (standard) or a `layout.tsx` + `page.tsx` structure
- Whether it appears in `ROUTES` constants (the existing `store-ops/page.tsx` imports from `@/lib/constants`)
- Whether the route needs a `loading.tsx` file for Suspense boundaries

---

## Summary of Findings

| Area | Rating | Shell Risk |
|------|--------|-----------|
| Dual-layout specification | Insufficient | HIGH |
| CTA wiring | Partially specified | MEDIUM |
| Hook mapping | Partially correct | MEDIUM |
| Empty/error/partial data states | Not specified | HIGH |
| Data merge strategy | Undefined | CRITICAL |
| Mobile interaction model | Incomplete | MEDIUM |
| Anti-abuse controls | Absent (mostly N/A) | LOW |
| RBAC | Correct | None |
| Route registration | Not verified | LOW |

**Blocking items before agent build:**
1. Define the merge strategy (join key, field precedence, union vs intersection, `useMemo` shape)
2. Define all empty/error/partial states for all three hooks
3. Define card anatomy (which fields, in what order) for mobile view
4. Define table columns, sort keys, and default sort for desktop view
5. Specify `useWarehouseStock` warehouse param sourcing from `useUserStore`
6. Clarify CSV export column list and client-side vs backend generation
7. Clarify "stockout" threshold definition for the stockout tab

**Safe to build as-is:** RBAC guard selection (use `MODULES.STORE_OPS`), `useOrderSchedule` banner presence/absence logic (show only when `schedule.allowed === true`), Phase B store picker wiring via `useUserStore.isMultiStore`.
