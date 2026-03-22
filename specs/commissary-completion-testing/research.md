---
spec: commissary-completion-testing
phase: research
created: 2026-02-06T14:00:00+08:00
---

# Research: Commissary Completion & Comprehensive Testing

## Executive Summary

Commissary module is **60% complete** with Phase 1 fully deployed (22 APIs, 4 frontend pages, 100% E2E tested). Phase 2 BOM implementation is **dramatically simpler than expected** - only 1 product (FG020 Frozen Milk with 2 variants) needs BOM vs original assumption of 10+ complex BOMs. Phase 2 now estimated at **2-3 hours** (was 2-3 days). Phase 3 requires **architecture decision** on hub-based distribution (correct but higher effort) vs direct dispatch (simpler but technical debt). Testing strategy: extend existing Frappe pytest patterns for backend + Chrome DevTools MCP for frontend.

## External Research

### Best Practices - Frappe BOM Implementation

**BOM DocType Structure** ([Bill Of Materials - Frappe Docs](https://docs.frappe.io/erpnext/user/manual/en/bill-of-materials)):
- Main fields: Item (finished good), Quantity (output), Company, Currency
- Items table: Raw materials with quantities, source warehouse, scrap %, "Include Item in Manufacturing" checkbox
- Operations section: Manufacturing operations + workstation assignments
- Scrap section: By-products with rate (if saleable)
- Status: Submitted BOMs are immutable (must duplicate + resubmit to change)

**Stock Entry Auto-Deduction** ([Stock Entry Purpose - ERPNext Docs](https://docs.erpnext.com/docs/v12/user/manual/en/stock/stock-entry)):
- Stock Entry type "Manufacture" created from Work Orders
- Raw materials + production items fetched from BOM
- On submission: Auto-deducts from Source Warehouse (WIP)
- Multiple consumption entries allowed per Work Order
- Target warehouse receives finished goods

**Production Cost Calculation** ([Measuring Manufacturing Costs - Ambibuzz](https://www.ambibuzz.com/blog-post/measuring-manufacturing-costs-accurately-with-erpnext)):
- Material cost: BOM auto-updates from Valuation Rate, Price List Rate, or last purchase
- Operating costs: Fuel, electricity, rent stored in Workstation form
- Labor costs: Job Cards track actual time (start/stop timer)
- Costing methods: FIFO, LIFO, weighted average
- ERPNext v16 (2026): Flexible valuation control per industry

### Best Practices - Warehouse Hierarchy

**Distribution Hub Modeling** ([Warehouse - ERPNext Docs](https://docs.erpnext.com/docs/v13/user/manual/en/stock/warehouse)):
- Tree View: Multi-level hierarchy (rooms, rows, shelves, bins)
- Parent Warehouse: Creates sub-warehouses under group nodes
- "Is Group" checkbox: Non-stock-holding parent nodes
- ERPNext v15: Drag-drop warehouse nodes, capacity limits per location
- Warnings before exceeding designated limits

**Transfer Workflows** ([Moving Material Between Warehouses - GitHub](https://github.com/frappe/erpnext/issues/8197)):
- Stock Entry type "Material Transfer"
- From Warehouse → To Warehouse
- Transfer logs ensure traceability
- Multi-warehouse support: Single platform for multiple zones

### Best Practices - Testing Patterns

**Frappe Backend Testing** ([Testing - Frappe Docs](https://docs.frappe.io/framework/user/en/testing)):
- Framework: Python unittest (built-in)
- Test classes inherit from `FrappeTestCase`
- File naming: `test_*.py` (anywhere in repo)
- Setup/teardown: `setUpClass()`, `tearDownClass()`
- Run: `bench run-tests --app hrms --module commissary`
- Auto-generated stubs for new DocTypes
- Handles Frappe-specific flags, DB transactions

**Frontend Testing** (Chrome DevTools MCP):
- BEI uses Chrome DevTools MCP via `/test-full-cycle` skill
- Browser automation: navigate, click, fill forms, take screenshots
- Evidence capture: Screenshots for each step
- 100% pass rate achieved for Projects module (2026-02-04)

### Pitfalls to Avoid

| Pitfall | Impact | Mitigation |
|---------|--------|------------|
| Assuming complex BOMs | 2-3 days wasted effort | Validate with users first (Sam confirmed: "We mostly mix finished goods") |
| Implementing hub distribution without approval | Technical debt or rework | Get Mae/Bryan decision before building |
| Testing only happy path | Production bugs | Test error cases, RBAC, edge cases |
| Hardcoding thresholds in code | Maintenance burden | Use Item custom fields (already in progress) |
| Skipping cost validation | Incorrect pricing | Verify production cost matches manual calculations |

## Codebase Analysis

### Existing Patterns - Backend

**Location:** `hrms/api/commissary.py` (1,555 lines)

| Pattern | Usage | Notes |
|---------|-------|-------|
| `get_commissary_warehouse()` | Handles TEST vs PROD warehouse | Smart auto-switching based on stock |
| `@frappe.whitelist()` | API endpoint decorator | All 22 endpoints use this |
| Dashboard aggregation | Counts + SQL aggregates | Low stock uses product-specific thresholds |
| Hardcoded routes | 15 routes in dict | TODO: Move to DocType |
| Stub APIs | FQI, hub inventory | Return defaults if DocType not exists |

**Test Infrastructure:**
- Existing: 100+ test files in `hrms/*/doctype/*/test_*.py`
- Pattern: `class TestCommissary(FrappeTestCase):`
- Coverage: ~85% of DocTypes have test stubs
- **Gap:** No tests for `hrms/api/commissary.py` yet

### Existing Patterns - Frontend

**Location:** bei-tasks repo (separate, not found in scan)

**From Master Plan:**
- 4 pages: Dashboard, Production, Inventory, Fulfillment
- Built: React + Next.js + Shadcn UI
- Deployed: Vercel (my.bebang.ph)
- Testing: Chrome DevTools MCP (100% pass on 2026-02-04)

### Dependencies

**Can Leverage:**
- Stock Entry DocType (standard Frappe)
- BOM DocType (standard ERPNext)
- Warehouse DocType (already configured)
- Item DocType (358 items uploaded)
- Material Request DocType (store ordering)

**Need to Create:**
- FG020-ORIGINAL BOM
- FG020-GRIFFITH BOM
- BEI External Hub DocType (Phase 3, optional)
- BEI Distribution Trip DocType (Phase 3, optional)

### Constraints

**Technical:**
- Frappe BOM limitation: Immutable after submission (must duplicate to change)
- Stock Entry must link to BOM for auto-deduction
- Valuation Rate affects cost calculation (ensure accurate)

**Operational:**
- Production happens 5am-2pm + 4pm-1am (2 shifts)
- Dispatch at 4am (orders by 12pm previous day)
- Only 4 raw materials to track (not 50+)
- Test stock exists in TEST-COMMISSARY - BEI

**Business:**
- Architecture decision needed: Hub-based vs direct dispatch
- Mae approval required for >500K POs (affects hub setup)
- MANCOM metrics: Days Inventory target = 14 days for perishables

## Feasibility Assessment

| Aspect | Assessment | Notes |
|--------|------------|-------|
| **Phase 2 Technical Viability** | ✅ High | Standard Frappe BOM + Stock Entry patterns. Simpler than expected (1 product vs 10). |
| **Phase 2 Effort Estimate** | ✅ S (2-3 hours) | Create 2 BOMs (30m), update API (45m), "can produce?" endpoint (30m), cost calc (15m), forecasting (30m), mark outsourced (10m), test (20m). |
| **Phase 2 Risk Level** | 🟢 Low | Well-documented patterns, test stock available, no complex dependencies. |
| **Phase 3 Technical Viability** | ⚠️ Medium | Hub-based: Need 4 hub warehouses, transfer workflow, route reassignment. Direct dispatch: Keep current (technical debt). |
| **Phase 3 Effort Estimate** | ⚠️ M-L (2-3 days hub / 0 hours direct) | Hub: Create warehouses, transfer DocType, update routes, migrate orders. Direct: No work but future migration needed. |
| **Phase 3 Risk Level** | 🟡 Medium | Decision risk: Wrong choice = rework. Implementation risk: Low (standard warehouse patterns). |
| **Testing Viability** | ✅ High | Proven patterns: Frappe pytest (backend) + Chrome DevTools MCP (frontend). E2E already 100% pass. |
| **Testing Effort** | ✅ M (4-6 hours) | Backend tests (2h), frontend E2E (2h), integration tests (1-2h). |

## Recommendations for Requirements

### Phase 2 BOM Features (IMMEDIATE - 2-3 hours)

1. **Create BOMs in Frappe UI** (not code)
   - Use Frappe Desk → Manufacturing → BOM
   - FG020-ORIGINAL: 3 raw materials (Nestle Cream 2kg, Condensed 3kg, Evap 3kg) → 15.68kg
   - FG020-GRIFFITH: 2 raw materials (Griffith Powder 4kg, Water 12kg) → 15.68kg
   - Yield: 6.27 barrels @ 2.5kg each

2. **Update `submit_production_output()` API**
   - Check if item has BOM: `frappe.db.exists("BOM", {"item": item_code, "is_active": 1})`
   - If yes: Create Stock Entry type "Manufacture" (not "Material Receipt")
   - Auto-deduct from Source Warehouse (TEST-COMMISSARY - BEI)
   - Add finished goods to Target Warehouse

3. **Add "Can we produce?" endpoint** (`get_production_capacity()`)
   - Query: `SELECT actual_qty FROM tabBin WHERE item_code IN (raw_materials) AND warehouse = commissary`
   - Calculate: `max_batches = min(stock / required_qty for each ingredient)`
   - Return: `{"max_barrels": max_batches * 6.27, "limiting_ingredient": item_code}`

4. **Add production cost endpoint** (`get_production_cost()`)
   - Query: `SELECT valuation_rate FROM tabBin WHERE item_code = raw_material`
   - Sum: `total = sum(qty * valuation_rate for each ingredient)`
   - Add packaging cost (hardcoded or from Item)
   - Return: `{"cost_per_batch": total, "cost_per_barrel": total / 6.27}`

5. **Raw material forecasting** (`get_raw_material_forecast()`)
   - Track 4 ingredients: Cream, Condensed, Evap, Griffith Powder
   - Calculate daily consumption: `sum(production_qty * bom_qty for last 7 days) / 7`
   - Reorder point: `daily_consumption * lead_time * safety_factor`
   - Alert if: `actual_qty < reorder_point`

6. **Mark outsourced items**
   - Set `is_sub_contracted_item = 1` for: FG001, FG002, FG013, FG016-FG019, FG007, FG009, FG012, FG014, FG015
   - Prevents accidental BOM creation
   - Flags for procurement vs production

### Phase 3 Architecture Decision (DECISION NEEDED)

**Option A: Hub-Based Distribution (Correct Architecture)**

Pros:
- Matches actual operations (4 external hubs)
- Scalable (can optimize routes per hub)
- Accurate inventory tracking per hub
- Supports FEFO per hub

Cons:
- 2-3 days effort
- Requires data migration
- Need to update existing orders

**Option B: Direct Dispatch (Temporary Technical Debt)**

Pros:
- Zero effort now
- Current flow works
- Can defer until post-go-live

Cons:
- Future migration needed
- Inaccurate inventory view (hub stock hidden)
- Route optimization harder

**Recommendation:** Ask Mae/Bryan preference. If time-constrained pre-go-live, use Option B and plan Phase 3 for Month 2.

### Comprehensive Testing Strategy

**Backend (Frappe pytest):**

1. Create `hrms/api/tests/test_commissary.py`
2. Test all 22 endpoints:
   - Dashboard: KPIs, alerts, summary
   - Production: Log output, wastage, batches, history
   - Inventory: Levels, low stock, days inventory
   - Fulfillment: Orders, detail, fulfill
   - Metrics: Productivity, weekly summary
   - Logistics: Routes, ready for pickup
   - Hubs: Inventory, updates
   - BOM: Auto-deduction, cost calc, forecasting

3. Test cases:
   - Happy path: Create production, check stock deducted
   - Error cases: Insufficient stock, invalid BOM
   - RBAC: Warehouse User permissions
   - Edge cases: Wastage >100%, negative stock

**Frontend (Chrome DevTools MCP via `/test-full-cycle`):**

1. Dashboard page:
   - Navigation
   - KPI display
   - Low stock alerts
   - Quick actions

2. Production page:
   - Log output form
   - Wastage tracking
   - Batch creation
   - History view

3. Inventory page:
   - Stock levels table
   - Days inventory calculation
   - Low stock highlighting
   - Item group filtering

4. Fulfillment page:
   - Pending orders list
   - Order detail modal
   - Dispatch action
   - Status updates

**Integration Testing:**

1. Full production cycle:
   - Check stock before: `GET /api/method/hrms.api.commissary.get_inventory_levels`
   - Log production: `POST /api/method/hrms.api.commissary.submit_production_output`
   - Verify stock deducted: Check raw materials decreased, FG increased
   - Verify cost: Match manual calculation

2. Store fulfillment cycle:
   - Create Material Request (store ordering)
   - Appear in pending orders
   - Fulfill order
   - Verify stock transferred

3. MANCOM metrics:
   - Days inventory: Current stock / avg daily consumption
   - Productivity: kg output / manhours
   - Week-on-week comparison

**Test Accounts:**

| Role | Email | Password |
|------|-------|----------|
| Warehouse User | test.warehouse@bebang.ph | BeiTest2026 |
| Commissary User | test.commissary@bebang.ph | (Create if needed) |

## Open Questions

### Phase 2
- ✅ BOM data received (2026-02-06)
- ✅ Raw materials confirmed (4 ingredients only)
- ⚠️ Packaging cost: Hardcoded or from Item? (Ask Bryan)
- ⚠️ Safety factor for reorder point: 1.5x or 2x lead time? (Ask Arnold)

### Phase 3
- 🔴 **BLOCKING:** Hub-based distribution or direct dispatch? (Mae/Bryan decision)
- ⚠️ If hub-based: Which hub per store? (Need route mapping)
- ⚠️ If hub-based: Hub inventory ownership? (BEI consignment or hub-owned?)

### Testing
- ⚠️ Test data: Use TEST-COMMISSARY stock or seed new? (Existing stock OK)
- ⚠️ Frontend testing: Run in bei-tasks repo or via deployed my.bebang.ph? (Deployed OK)

## Quality Commands

**Backend (Frappe):**
```bash
# Run commissary tests
bench run-tests --app hrms --module commissary

# Run all HRMS tests
bench run-tests --app hrms

# Coverage report
bench run-tests --app hrms --coverage
```

**Frontend (bei-tasks repo - separate):**
```bash
# Not in current repo - bei-tasks has own package.json
# Testing via Chrome DevTools MCP (/test-full-cycle skill)
```

**Local Development:**
```bash
# Start Frappe (via /local-frappe skill)
bench start

# Test API endpoint
curl -X POST https://hq.bebang.ph/api/method/hrms.api.commissary.get_commissary_dashboard \
  -H "Authorization: token API_KEY:API_SECRET"
```

## Related Specs

**Discovery:** Scanned `./specs/` directory. Found 2 specs:

| Spec | Relationship | May Need Update |
|------|--------------|-----------------|
| `hello-world` | None - Example spec | No |
| `commissary-completion-testing` | **This spec** | N/A |

**Notes:**
- No overlapping specs found
- Commissary is greenfield (no prior specs)
- Projects module (referenced in PROGRESS_INDEX) was built ad-hoc without spec
- Procurement module (referenced in PROGRESS_INDEX) was built ad-hoc without spec

**Recommendation:** Create specs for future modules (Warehouse Supervisor Interface, Store Operations) using this pattern.

## Implementation Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **BOM cost mismatch** | Medium | High | Validate cost calc vs manual before production use |
| **Stock deduction error** | Low | Critical | Test with TEST-COMMISSARY stock first, verify before prod |
| **Hub decision delay** | High | Medium | Proceed with Phase 2, defer Phase 3 decision to Mae/Bryan |
| **Test coverage gaps** | Medium | Medium | Focus on critical paths: production, fulfillment, cost |
| **Frontend/backend API mismatch** | Low | High | Integration tests verify contract |

## Sources

**External:**
- [Bill Of Materials - Frappe Docs](https://docs.frappe.io/erpnext/user/manual/en/bill-of-materials)
- [Stock Entry Purpose - ERPNext Docs](https://docs.erpnext.com/docs/v12/user/manual/en/stock/stock-entry)
- [Measuring Manufacturing Costs - Ambibuzz](https://www.ambibuzz.com/blog-post/measuring-manufacturing-costs-accurately-with-erpnext)
- [Warehouse - ERPNext Docs](https://docs.erpnext.com/docs/v13/user/manual/en/stock/warehouse)
- [Moving Material Between Warehouses - GitHub](https://github.com/frappe/erpnext/issues/8197)
- [Testing - Frappe Docs](https://docs.frappe.io/framework/user/en/testing)
- [Automated Testing - Frappe Docs](https://docs.frappe.io/framework/user/en/guides/automated-testing)

**Internal:**
- `docs/plans/COMMISSARY_MASTER_PLAN_2026-02-06.md` - Current state, Phase 1 complete, Phase 2/3 pending
- `data/Commissary/BOM_COMMISSARY_ACTUAL_2026-02-06.md` - BOM recipes (FG020 variants)
- `hrms/api/commissary.py` - Backend implementation (22 endpoints, 1,555 lines)
- `data/04_Project_Management/Import_Log/PROGRESS_INDEX.md` - Progress tracking
- `docs/MY_BEBANG_PH_COMPLETE_REFERENCE.md` - Frontend reference

---

**Next Steps:**
1. **User Approval** - Review research findings, approve Phase 2 scope, decide Phase 3 architecture
2. **Requirements Phase** - Detailed specs for BOM features, testing checklist
3. **Implementation** - 2-3 hours for Phase 2, TBD for Phase 3
