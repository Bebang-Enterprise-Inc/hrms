# S122 Backend Connectivity Audit
# Generated: 2026-03-26

## Summary

Verified 5 hooks, 4 API routes: 4 hooks connected, 1 missing (order history), 3 shape mismatches.

---

## Hook Verification

### 1. useWarehouseStock(warehouse, itemGroup?, includeZeroStock?)

- **File:** `F:\Dropbox\Projects\bei-tasks\hooks\use-inventory.ts` (line 430)
- **EXISTS:** Yes
- **Signature:** `useWarehouseStock(warehouse: string, itemGroup: string = "", includeZeroStock = false)`
- **API call:** `GET /api/inventory?action=warehouse_stock&warehouse=...`
- **Returns:** `{ items: WarehouseStockItem[], isLoading, error, mutate }`

**WarehouseStockItem interface (actual, lines 171-180):**
```typescript
interface WarehouseStockItem {
  item_code: string;
  item_name: string;    // EXISTS -- plan assumption valid
  warehouse: string;
  actual_qty: number;
  reserved_qty: number;
  available_qty: number;
  reorder_point: number;
  is_low_stock: boolean;
  // uom: MISSING -- not in this interface
}
```

**SHAPE MISMATCH (SM-1):** `uom` is NOT present in `WarehouseStockItem`. The plan's `StoreInventoryItem` type requires `uom` (used in card anatomy, table columns, and CSV export). The `uom` field only exists in `OrderableItem` (from `useOrderableItems`). The composite hook `useStoreInventory` must source `uom` from `OrderableItem.uom`, but items in stock that are NOT orderable will have `uom = null`. The plan does not address this gap.

Backend SQL confirmation (`hrms/api/inventory.py` line 1409): The `get_warehouse_stock` query does NOT select `stock_uom` from `tabItem`. Only: `item_code, item_name, item_group, warehouse, actual_qty, reserved_qty, available_qty, reorder_point, is_low_stock`. UOM is absent at the source.

---

### 2. useOrderableItems(store?, date?)

- **File:** `F:\Dropbox\Projects\bei-tasks\hooks\use-ordering.ts` (line 163)
- **EXISTS:** Yes
- **Signature:** `useOrderableItems(store?: string, date?: string)`
- **API call:** `GET /api/ordering?action=get_orderable_items&store=...`

**NOTE — Action name discrepancy:** The hook calls `action=get_orderable_items` (with `get_` prefix). The `/api/inventory` route (legacy) uses `action=orderable_items` (no prefix). These are DIFFERENT routes: the hook hits `/api/ordering`, not `/api/inventory`. The ordering route handler correctly maps `get_orderable_items` -> `ORDERING_GET_METHOD_MAP.get_orderable_items`. This is correct, not a bug.

**OrderableItem interface (actual, lines 13-31):**
```typescript
interface OrderableItem {
  item_code: string;
  item_name: string;
  uom: string;                 // EXISTS
  packaging_description: string;
  cargo_category: string;      // EXISTS -- plan needs this for grouping
  suggested_qty: number;       // EXISTS
  recommended_qty: number;
  risk_rank: number;           // EXISTS
  lane: "Frozen" | "Dry" | string;
  source_warehouse?: string;
  available_stock: number;
  available_to_promise: number;
  forecast_demand: number;     // EXISTS
  safety_buffer: number;
  is_oos: boolean;             // EXISTS
  last_order_qty: number;
  unit_price: number;
}
```

**All plan-required fields verified present:** `item_code`, `forecast_demand`, `suggested_qty`, `risk_rank`, `is_oos`, `cargo_category`. No shape mismatches for this hook.

---

### 3. useOrderSchedule(store?, date?, deliveryDate?)

- **File:** `F:\Dropbox\Projects\bei-tasks\hooks\use-ordering.ts` (line 190)
- **EXISTS:** Yes
- **Signature:** `useOrderSchedule(store?: string, date?: string, deliveryDate?: string)`
- **API call:** `GET /api/ordering?action=validate_order_schedule&store=...`

**Returns:** `{ schedule: OrderSchedule | null, isLoading, error, mutate }`

**OrderSchedule interface (actual, lines 33-40):**
```typescript
interface OrderSchedule {
  allowed: boolean;
  reason?: string;
  message?: string;
  cutoff_time?: string;
  next_delivery_day?: string;
  requires_dual_approval?: boolean;
}
```

**SHAPE MISMATCH (SM-2):** The plan claims `useOrderSchedule` returns `{ allowed, cutoff_time, next_delivery_day }` directly on the hook return. ACTUAL: the hook wraps these in `{ schedule: OrderSchedule | null }`. Callers must use `schedule.allowed`, `schedule.cutoff_time`, `schedule.next_delivery_day` — not destructure them from the top level. Components building `<OrderWindowBanner>` must access `schedule?.allowed` not `allowed` directly.

---

### 4. useUserStore(surface?)

- **File:** `F:\Dropbox\Projects\bei-tasks\hooks\use-user-store.ts` (line 37)
- **EXISTS:** Yes
- **Signature:** `useUserStore(surface?: string)`
- **API call:** `GET /api/store/user-store`
- **Backend:** `hrms.api.store.get_user_store` (confirmed at store.py line 1598)

**Returns (actual):**
```typescript
{
  stores: StoreInfo[];     // StoreInfo = { name: string, warehouse_name: string }
  defaultStore: string | undefined;
  isMultiStore: boolean;
  role: string | null;
  isLoading: boolean;
  error: Error | null;
  refresh: () => void;    // NOTE: named "refresh", not "mutate"
}
```

**SHAPE MISMATCH (SM-3):** The plan's data flow diagram names the return as `{ defaultStore, stores[], isMultiStore, role }`. These field names ARE correct. However:

1. The `stores` array items have shape `{ name: string, warehouse_name: string }`. The `name` field contains the Frappe Warehouse docname (e.g., "Store Name - BEI"), NOT a store/branch label. This IS the string that `useWarehouseStock(warehouse)` accepts — so the data linkage works: `useWarehouseStock(defaultStore)` will pass the Warehouse docname correctly.
2. `stores[i].warehouse_name` is a display label (e.g., "Store Name"), not the docname. The composite hook `useStoreInventory(storeWarehouse)` should use `stores[i].name` (the docname), not `warehouse_name`, as the `warehouse` parameter.
3. The hook returns `refresh` not `mutate`. This is not a bug but components must use `.refresh()` not `.mutate()`.

**Backend `get_user_store` return shape confirmed** (store.py line 1607):
```python
{
    "stores": [{"name": "Store Name - BEI", "warehouse_name": "Store Name"}],
    "default_store": "Store Name - BEI",
    "is_multi_store": false,
    "role": "Store Staff"
}
```

---

### 5. Order History Hook (A9: "existing order list API")

- **Plan claim:** A9 uses "existing order list API" for past store orders.
- **Searched:** `hooks/use-ordering.ts`, `hooks/use-order-review.ts`, all 72 hook files in `/hooks/`.
- **Result: NO HOOK EXISTS for store order history.**

`use-order-review.ts` contains `useOrderReviewQueue(date, status)` — this is the WAREHOUSE TEAM approval queue, not the store's own past orders. It is not appropriate for A9.

The `/api/ordering` GET handler supports `get_order_review_queue` and `get_order_detail` but there is NO action for listing a store's own past orders by store name.

**MISSING (M-1):** There is no `useOrders(store)` hook and no `/api/ordering?action=get_store_order_history` (or equivalent). The plan's `OrderHistoryView.tsx` (task A9) has no backing hook or API to call. This requires either:
  - A new Frappe backend method (contradicts "no new backend APIs needed")
  - A new action in `/api/ordering` that calls Frappe doctype list for `BEI Store Order` filtered by store
  - Reuse of `useOrderReviewQueue` with store filter (but it has no store param, only date+status)

This is the most significant gap: the plan says "no new backend APIs needed" but A9 has no data source.

---

## API Route Verification

### /api/inventory?action=warehouse_stock

- **File:** `F:\Dropbox\Projects\bei-tasks\app\api\inventory\route.ts` (line 183)
- **EXISTS:** Yes
- **Backend method:** `hrms.api.inventory.get_warehouse_stock`
- **Params forwarded:** `warehouse`, `item_group`
- **NOTE:** `include_zero_stock` param IS handled in the hook URL builder but NOT forwarded in the route handler (the route only forwards `warehouse` and `item_group`, not `include_zero_stock`). Minor gap but not blocking for S122 since the dashboard shows real stock.

### /api/ordering?action=get_orderable_items

- **File:** `F:\Dropbox\Projects\bei-tasks\app\api\ordering\route.ts` (line 211)
- **EXISTS:** Yes
- **Backend method:** via `ORDERING_GET_METHOD_MAP.get_orderable_items`
- **Fully connected.**

### /api/ordering?action=validate_order_schedule

- **File:** `F:\Dropbox\Projects\bei-tasks\app\api\ordering\route.ts` (line 230)
- **EXISTS:** Yes
- **Backend method:** via `ORDERING_GET_METHOD_MAP.validate_order_schedule`
- **Fully connected.**

### Order History API

- **EXISTS:** No. No route action exists for fetching a store's own past orders.
- **Closest candidate:** `get_order_review_queue` (warehouse approval queue, no store filter param).
- **Status: MISSING — backend work required for A9.**

---

## Data Shape: StoreInventoryItem Buildability

The plan defines:
```typescript
type StoreInventoryItem = {
  item_code: string;        // from WarehouseStockItem -- OK
  item_name: string;        // from WarehouseStockItem -- OK
  warehouse: string;        // from WarehouseStockItem -- OK
  actual_qty: number;       // from WarehouseStockItem -- OK
  available_qty: number;    // from WarehouseStockItem -- OK
  is_low_stock: boolean;    // from WarehouseStockItem -- OK
  uom: string;              // PROBLEM: not in WarehouseStockItem; only in OrderableItem
  cargo_category: string | null;  // from OrderableItem -- OK (nullable when not orderable)
  forecast_demand: number | null; // from OrderableItem -- OK
  suggested_qty: number | null;   // from OrderableItem -- OK
  risk_rank: number | null;       // from OrderableItem -- OK
  is_oos: boolean;          // from OrderableItem -- OK
  days_of_stock: number | null;   // computed -- OK
};
```

**Buildable with one caveat:** `uom` cannot come from `WarehouseStockItem`. It can only come from `OrderableItem.uom`. For items in stock but not orderable, `uom` will be unavailable unless a separate Item master lookup is made (new API call). The composite hook author must handle `uom: orderableItem?.uom ?? ""` and accept that non-orderable items will show blank UOM.

---

## Issues Summary

| ID | Severity | Description |
|----|----------|-------------|
| SM-1 | MEDIUM | `WarehouseStockItem` has no `uom`. Non-orderable items will have blank UOM in CSV export and cards. |
| SM-2 | LOW | `useOrderSchedule` wraps result in `{ schedule }`. Callers must use `schedule?.allowed`, not top-level destructuring. |
| SM-3 | LOW | `useUserStore` stores items use `name` (docname) as warehouse identifier, `warehouse_name` is display-only. Composite hook must use `.name` not `.warehouse_name` as the param to `useWarehouseStock`. |
| M-1 | HIGH | No order history hook or API exists. Task A9 (`OrderHistoryView`) has no data source. Plan claim "no new backend APIs needed" is FALSE for A9. Requires new Frappe method + route action, or explicit scoping of A9 out of S122. |

---

## Files Read

- `F:\Dropbox\Projects\bei-tasks\hooks\use-inventory.ts`
- `F:\Dropbox\Projects\bei-tasks\hooks\use-ordering.ts`
- `F:\Dropbox\Projects\bei-tasks\hooks\use-order-review.ts`
- `F:\Dropbox\Projects\bei-tasks\hooks\use-user-store.ts`
- `F:\Dropbox\Projects\bei-tasks\app\api\inventory\route.ts`
- `F:\Dropbox\Projects\bei-tasks\app\api\ordering\route.ts`
- `F:\Dropbox\Projects\bei-tasks\app\api\store\user-store\route.ts`
- `F:\Dropbox\Projects\bei-tasks\hooks\` (directory listing — 72 files, no order history hook found)
- `F:\Dropbox\Projects\BEI-ERP\hrms\api\inventory.py` (lines 1376-1435, get_warehouse_stock SQL)
- `F:\Dropbox\Projects\BEI-ERP\hrms\api\store.py` (lines 1598-1680, get_user_store return shape)
- `F:\Dropbox\Projects\BEI-ERP\docs\plans\2026-03-25-sprint-122-store-inventory-dashboard.md`
