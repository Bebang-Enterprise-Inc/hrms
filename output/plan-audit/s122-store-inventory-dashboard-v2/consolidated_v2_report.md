# S122 Audit V2 — Consolidated Report
## Date: 2026-03-26
## Focus: Backend connectivity verification + remaining gaps after v1 amendments

---

## Verdict: CONDITIONAL GO — 4 items to fix, then ready

The 7 original blockers from v1 audit are ALL resolved. The v2 audit found 4 new issues, all from the backend connectivity check. These are real and must be fixed before execution.

---

## REMAINING BLOCKERS

### 1. Order History hook/API DOES NOT EXIST [HIGH — requires plan amendment]
**Source:** backend-connectivity M-1, frontend-v2, deployment-qa-v2
**Evidence:** Grep of all 72 hook files in bei-tasks/hooks/ — no `useOrders`, `useOrderHistory`, or `useStoreOrderHistory` exists. The `/api/ordering` route has no `get_store_order_history` action. `useOrderReviewQueue` is the warehouse approval queue with no store filter.
**Impact:** Task A9 (OrderHistoryView) has no data source. The plan claims "no new backend APIs needed" — this is false for A9.
**Fix options:**
- **(A) Add a new API action** to `/api/ordering` route.ts that calls a new Frappe method listing `BEI Store Order` docs filtered by store. This adds 1 backend unit (hrms repo) and changes the "frontend only" claim.
- **(B) Defer A9 to a V2 sprint.** Remove Order History from S122 scope. Mark it as a follow-up. This preserves the "no backend changes" constraint.
- **Recommendation:** Option A. A simple list endpoint is ~30 lines. The order history feature is high-value for stores. Worth the small backend addition.

### 2. WarehouseStockItem has no `uom` field [MEDIUM — plan type spec wrong]
**Source:** backend-connectivity SM-1
**Evidence:** `WarehouseStockItem` interface (use-inventory.ts:171-180) does not include `uom`. Backend SQL in `hrms/api/inventory.py:1409` does not select `stock_uom` from `tabItem`.
**Impact:** Non-orderable items will show blank UOM in cards, table, and CSV export.
**Fix:** Update `StoreInventoryItem` type: `uom: orderableItem?.uom ?? item.stock_uom ?? ""`. For items not in the orderable catalog, UOM is blank. The composite hook should document this. Alternatively, add `stock_uom` to the `get_warehouse_stock` SQL query (1-line backend fix).

### 3. useOrderSchedule wraps result in { schedule } [LOW — documentation fix]
**Source:** backend-connectivity SM-2
**Evidence:** Hook returns `{ schedule: OrderSchedule | null }`, not bare `{ allowed, cutoff_time }`.
**Fix:** Update A5 (OrderWindowBanner) task to specify: `const { schedule } = useOrderSchedule(store); if (schedule?.allowed) ...`. This is a documentation fix, not a code gap.

### 4. useUserStore stores[i].name vs warehouse_name [LOW — documentation fix]
**Source:** backend-connectivity SM-3
**Evidence:** `stores[i].name` = Warehouse docname (e.g., "Store Name - BEI"), `stores[i].warehouse_name` = display label.
**Fix:** Update A0 (composite hook) to specify: `useWarehouseStock(useUserStore().defaultStore)` — `defaultStore` IS the docname. Add comment in plan: "DO NOT use `warehouse_name` as the warehouse param — use `name` (the docname)."

---

## ADVISORY (not blocking)

### 5. Error state L3 scenarios defined in C1 but not in L3 table
**Source:** deployment-qa-v2
**Fix:** Add 2 L3 rows: "Load page with API error simulated → error banner shown" and "Load page for store with 0 items → empty state shown."

### 6. Countdown timer needs server time but no server timestamp in OrderSchedule
**Source:** frontend-v2
**Impact:** If the countdown uses `cutoff_time` (a time string like "14:00") and device clock is wrong, the countdown is wrong. The plan says "uses server time not device time" but doesn't explain how.
**Fix:** Use the Frappe API response header `Date` as server time reference, or fetch server time once on page load via `frappe.utils.now_datetime()`. Add this to A5 task.

### 7. "Reorder This" pre-fill mechanism unspecified
**Source:** frontend-v2
**Fix:** Specify in A6: "Navigate to `/dashboard/store-ops/ordering?prefill=last` with last order items as URL search params or sessionStorage. The ordering page reads prefill and populates quantities."

### 8. Evidence files need "read-only sprint" markers
**Source:** team-orchestration-v2
**Fix:** At closeout, `form_submissions.json` should contain `[{"form": "N/A — read-only dashboard, no mutations", "note": "S122 is a read-only inventory view with no form submissions"}]` to prevent future corrupt-success audits from flagging empty evidence.

---

## SCORECARD

| Check | V1 Status | V2 Status |
|-------|-----------|-----------|
| Data merge strategy | BLOCKED | RESOLVED |
| Component decomposition | BLOCKED | RESOLVED |
| 46-store fan-out | BLOCKED | RESOLVED |
| Card/table field anatomy | BLOCKED | RESOLVED |
| Empty/error states | BLOCKED | RESOLVED |
| Desktop L3 scenarios | BLOCKED | RESOLVED |
| Evidence file repo | BLOCKED | RESOLVED |
| Order History API exists | — | **NEW: BLOCKED** |
| WarehouseStockItem.uom | — | **NEW: MEDIUM** |
| useOrderSchedule wrapper | — | **NEW: LOW** |
| useUserStore field mapping | — | **NEW: LOW** |
| Execution governance (S027/S092/S099/S089/S091) | PASS | PASS |

**V1 had 7 blockers → all resolved. V2 found 4 new (1 HIGH, 1 MEDIUM, 2 LOW).**
After fixing items 1-4, the plan is GO for execution.
