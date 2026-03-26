# S122 Audit Consolidated Report
## Date: 2026-03-25
## Agents: frontend (4.5/10), design-review (54/100), deployment-qa (NO-GO), ux-improvement (8P1+6P2+5P3)

## Verdict: CONDITIONAL GO — 7 blockers must be fixed, 8 UX features should be added

---

## TOP BLOCKERS (must fix before execution)

### B-01: Data merge strategy undefined [CRITICAL]
`useWarehouseStock` returns `WarehouseStockItem` (actual_qty, is_low_stock). `useOrderableItems` returns `OrderableItem` (forecast_demand, suggested_qty, risk_rank). These are different schemas joined by item_code. No merge rule is specified.
**Fix:** Define a `useStoreInventory()` composite hook that left-joins stock items with demand data. Specify: join key = item_code, stock fields are primary, demand fields are enrichment, items in stock but not orderable show demand as "N/A".

### B-02: God-component anti-pattern [CRITICAL]
All 3 views (My Stock, Multi-Store, Stockout Alerts) in one page.tsx = 800+ line file.
**Fix:** Decompose into: `page.tsx` (router shell, <100 lines) + `MyStockView.tsx` + `MultiStoreView.tsx` + `StockoutAlertsPanel.tsx`. Each view owns its hooks.

### B-03: Area Supervisor 46-store fan-out [CRITICAL]
"All My Stores" view would fire 46 simultaneous API calls. Browser connection limit = 6. Will time out.
**Fix:** Either (a) add a server-side aggregation endpoint, or (b) lazy-load per store on expand, or (c) load 5 stores at a time with "load more".

### B-04: Card/table field anatomy not specified [HIGH]
No card fields, no table columns, no sort keys defined. Agent will invent 6+ arbitrary decisions.
**Fix:** Specify exact card anatomy (mobile) and column list (desktop) in the plan.

### B-05: Empty/error/partial data states missing [HIGH]
Zero specification for: API down, empty store, partial demand data, loading states.
**Fix:** Define skeleton states, empty states, error banners, and partial-data fallback rendering.

### B-06: Desktop L3 scenarios missing [HIGH]
All 10 L3 scenarios test mobile. No desktop table layout coverage.
**Fix:** Add 2+ desktop L3 scenarios (1280px table, 1024px laptop edge case).

### B-07: Evidence file repo unspecified [MEDIUM]
`output/l3/S122/` — goes to bei-tasks or BEI-ERP?
**Fix:** Specify BEI-ERP repo for evidence (consistent with all other sprints).

---

## UX IMPROVEMENTS TO ADD (from ux-improvement agent)

### Add to S122 (Priority 1 — 5 features that fit within scope)

| # | Feature | Anti-Abuse Angle | Units |
|---|---------|-----------------|-------|
| U1 | **"Needs Attention" default view** — load with only Critical + Low items shown, "Show All" toggle for the rest | Managers can't claim they didn't see critical items | 1 |
| U2 | **Sticky critical-items chip strip** — red chips pinned above fold showing named critical items, tap to scroll to item | Harder to ignore "Ube Ice Cream: 0 packs" than the number "3" | 1 |
| U3 | **Order window countdown timer** — live HH:MM countdown, disabled "Submit" when closed (visible, not hidden) | "I didn't know the deadline" eliminated | 0 (already in A5, just enhance) |
| U4 | **Last Order summary panel** — one-tap from header, shows last order items/qty/status, "Reorder this" pre-fills form | Prevents double orders, lazy reorders still go through count confirmation | 1 |
| U5 | **Refresh button** — manual refresh CTA wiring mutate() on all hooks | Standard on inventory dashboards, currently missing | 0 (trivial) |

### Defer to V2 Sprint (Priority 2 — need backend changes)

| # | Feature | Why Defer |
|---|---------|-----------|
| D1 | Alert acknowledgement with audit log | Needs new Frappe DocType (stock_alert_acknowledgements) |
| D2 | Count confirmation gate before ordering | Needs order flow modification + new fields |
| D3 | "Flag for physical count" quick action | Needs tabBin field addition |
| D4 | Audit log tab (manager-visible) | Depends on D1/D2/D3 data |
| D5 | Store vs store benchmarks (Area Sup) | Needs aggregation endpoint |
| D6 | Print-friendly count sheet | CSS print stylesheet, moderate effort |
| D7 | Daily workflow checkpoint prompts | Needs server-side cron + store hours config |
| D8 | Damaged stock quick-report | Needs new DocType + approval flow |

---

## AMENDED SCOPE RECOMMENDATION

| Phase | Original | Amended | Delta |
|-------|----------|---------|-------|
| A | 13 units | 15 units | +2 (composite hook, component decomposition) |
| B | 6 units | 8 units | +2 (lazy-load pattern, multi-store aggregation) |
| C | 4 units | 5 units | +1 (desktop L3 + error state L3) |
| **Total** | **23** | **28** | **+5** |

Still well under 80-unit ceiling. Single-session executable.
