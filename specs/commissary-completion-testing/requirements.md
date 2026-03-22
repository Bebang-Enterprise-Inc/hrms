# Requirements: Commissary Phase 2 & Comprehensive Testing

## Goal
Complete commissary BOM implementation and validate all 27 APIs + 4 pages through comprehensive testing to ensure production readiness for Feb 2026 go-live.

## User Stories

### Phase 2: BOM Implementation

#### US-1: Create BOM for FG020 Variants **[BUILD]**
**As a** commissary supervisor
**I want to** create BOMs for FG020-ORIGINAL and FG020-GRIFFITH in Frappe UI
**So that** production batches auto-deduct raw materials

**Acceptance Criteria:**
- [ ] AC-1.1: FG020-ORIGINAL BOM exists with 3 raw materials (Nestle Cream 2kg, Condensed 3kg, Evap 3kg) yielding 15.68kg
- [ ] AC-1.2: FG020-GRIFFITH BOM exists with 2 raw materials (Griffith Powder 4kg, Water 12kg) yielding 15.68kg
- [ ] AC-1.3: Both BOMs show 6.27 barrels output @ 2.5kg each
- [ ] AC-1.4: BOMs marked as Active and submitted (immutable)
- [ ] AC-1.5: Source warehouse = TEST-COMMISSARY - BEI for testing

#### US-2: Auto-Deduct Raw Materials on Production **[EXTEND]**
**As a** commissary supervisor
**I want to** have raw materials automatically deducted when I log production
**So that** inventory stays accurate without manual adjustments

**Acceptance Criteria:**
- [ ] AC-2.1: `submit_production_output()` checks if item has active BOM
- [ ] AC-2.2: If BOM exists, Stock Entry type = "Manufacture" (not "Material Receipt")
- [ ] AC-2.3: Raw materials deducted from TEST-COMMISSARY - BEI warehouse
- [ ] AC-2.4: Finished goods added to TEST-COMMISSARY - BEI warehouse
- [ ] AC-2.5: Error if insufficient raw material stock
- [ ] AC-2.6: Stock Entry linked to BOM for traceability
- [ ] AC-2.7: Backwards compatible: Items without BOM still work (Material Receipt)

#### US-3: Check Production Capacity **[BUILD]**
**As a** commissary supervisor
**I want to** check if we have enough raw materials to produce X barrels
**So that** I don't start production that can't be completed

**Acceptance Criteria:**
- [ ] AC-3.1: New endpoint `GET /api/method/hrms.api.commissary.can_we_produce`
- [ ] AC-3.2: Takes `item_code` and `desired_barrels` as parameters
- [ ] AC-3.3: Returns `{"can_produce": true/false, "max_barrels": float, "limiting_ingredient": "item_code"}`
- [ ] AC-3.4: Queries `tabBin` for raw material stock at commissary warehouse
- [ ] AC-3.5: Calculation: `max_batches = min(stock / required_qty)` for each ingredient
- [ ] AC-3.6: Returns 0 if item has no BOM

#### US-4: Calculate Production Cost **[BUILD]**
**As a** commissary supervisor
**I want to** see production cost before starting a batch
**So that** I can verify COGS matches expectations

**Acceptance Criteria:**
- [ ] AC-4.1: New endpoint `GET /api/method/hrms.api.commissary.get_production_cost`
- [ ] AC-4.2: Takes `item_code` and `quantity` as parameters
- [ ] AC-4.3: Returns `{"cost_per_batch": float, "cost_per_barrel": float, "cost_breakdown": [{ingredient, qty, rate, total}]}`
- [ ] AC-4.4: Uses valuation_rate from `tabBin` for each raw material
- [ ] AC-4.5: Includes packaging cost (configurable or hardcoded)
- [ ] AC-4.6: Returns 0 if item has no BOM

#### US-5: Get BOM Recipe Display **[BUILD]**
**As a** commissary supervisor
**I want to** view the recipe/formula for FG020 items
**So that** I know what raw materials are needed

**Acceptance Criteria:**
- [ ] AC-5.1: New endpoint `GET /api/method/hrms.api.commissary.get_bill_of_materials`
- [ ] AC-5.2: Takes `item_code` as parameter
- [ ] AC-5.3: Returns BOM items with: `{item_code, item_name, qty, stock_uom, warehouse, current_stock}`
- [ ] AC-5.4: Returns null if no BOM exists
- [ ] AC-5.5: Shows only active BOMs

#### US-6: Raw Material Forecasting **[EXTEND]**
**As a** procurement user
**I want to** get alerts when raw materials need reordering
**So that** production doesn't stop due to stockouts

**Acceptance Criteria:**
- [ ] AC-6.1: Extend `get_rm_reorder_alerts()` with forecasting logic
- [ ] AC-6.2: Track 4 ingredients: Nestle Cream, Condensed, Evap, Griffith Powder
- [ ] AC-6.3: Calculate daily consumption = sum(production_qty * bom_qty last 7 days) / 7
- [ ] AC-6.4: Reorder point = daily_consumption * lead_time * safety_factor
- [ ] AC-6.5: Alert if actual_qty < reorder_point
- [ ] AC-6.6: Returns `{item_code, current_stock, reorder_point, days_until_stockout, suggested_order_qty}`

#### US-7: Mark Outsourced Items **[EXTEND]**
**As a** system administrator
**I want to** mark outsourced items in Item master
**So that** they're flagged for procurement vs production

**Acceptance Criteria:**
- [ ] AC-7.1: Bulk update 11 items: FG001, FG002, FG007, FG009, FG012-FG019
- [ ] AC-7.2: Set `is_sub_contracted_item = 1` on Item DocType
- [ ] AC-7.3: Prevents accidental BOM creation for outsourced items
- [ ] AC-7.4: Visible in Item master UI

### Phase 3: Architecture Decision **[DEFER]**

#### US-8: Decide Distribution Architecture
**As a** Mae/Bryan (decision makers)
**I want to** choose between hub-based distribution or direct dispatch
**So that** implementation aligns with operational model

**Acceptance Criteria:**
- [ ] AC-8.1: Document Option A: Hub-based distribution (4 external hubs, 2-3 days effort)
- [ ] AC-8.2: Document Option B: Direct dispatch (0 hours effort, technical debt)
- [ ] AC-8.3: Decision recorded in requirements with rationale
- [ ] AC-8.4: If Option B chosen, create technical debt ticket for Month 2

### Comprehensive Testing

#### US-9: Backend API Test Suite **[BUILD]**
**As a** QA engineer
**I want to** run pytest suite for all commissary endpoints
**So that** backend APIs are validated before production

**Acceptance Criteria:**
- [ ] AC-9.1: Test file created: `hrms/api/tests/test_commissary.py`
- [ ] AC-9.2: Tests all 27 endpoints (15 Phase 1 + 6 Phase 2 + 6 Phase 3)
- [ ] AC-9.3: Happy path: Create production, verify stock deducted
- [ ] AC-9.4: Error cases: Insufficient stock, invalid BOM, missing fields
- [ ] AC-9.5: RBAC: Warehouse User permissions enforced
- [ ] AC-9.6: Edge cases: Wastage >100%, negative stock, zero quantity
- [ ] AC-9.7: Run via `bench run-tests --app hrms --module commissary`
- [ ] AC-9.8: 100% pass rate achieved

#### US-10: Frontend E2E Test Extension **[EXTEND]**
**As a** QA engineer
**I want to** extend existing E2E tests for BOM workflows
**So that** frontend changes don't break production

**Acceptance Criteria:**
- [ ] AC-10.1: Extend 2026-02-04 E2E baseline (4 pages already passing)
- [ ] AC-10.2: Test Dashboard: KPIs load, alerts display, quick actions work
- [ ] AC-10.3: Test Production: Log output with BOM auto-deduction, wastage tracking
- [ ] AC-10.4: Test Inventory: Stock levels table, days inventory calculation, low stock highlighting
- [ ] AC-10.5: Test Fulfillment: Pending orders list, dispatch action, status updates
- [ ] AC-10.6: Use Chrome DevTools MCP via `/test-full-cycle` skill
- [ ] AC-10.7: Screenshot evidence for each step
- [ ] AC-10.8: 100% pass rate maintained

#### US-11: Component Unit Tests **[BUILD]**
**As a** QA engineer
**I want to** create Jest tests for React components
**So that** component logic is validated in isolation

**Acceptance Criteria:**
- [ ] AC-11.1: Test suite in bei-tasks repo (separate from this repo)
- [ ] AC-11.2: Tests for: MetricCard, ProductionForm, InventoryTable, OrderList components
- [ ] AC-11.3: Use React Testing Library
- [ ] AC-11.4: Coverage >80% for commissary components
- [ ] AC-11.5: Run via `npm test` in bei-tasks repo

#### US-12: Integration Test Suite **[BUILD]**
**As a** QA engineer
**I want to** test full production → inventory → fulfillment flow
**So that** end-to-end workflow is validated

**Acceptance Criteria:**
- [ ] AC-12.1: Test file: `hrms/api/tests/test_commissary_integration.py`
- [ ] AC-12.2: Full production cycle: Check stock before → log production → verify stock deducted → verify cost matches
- [ ] AC-12.3: Store fulfillment cycle: Create Material Request → appear in pending orders → fulfill order → verify stock transferred
- [ ] AC-12.4: MANCOM metrics: Days inventory = current stock / avg daily consumption, Productivity = kg output / manhours
- [ ] AC-12.5: Uses TEST-COMMISSARY - BEI warehouse for testing
- [ ] AC-12.6: Runs on test.warehouse@bebang.ph account

#### US-13: Performance Test Suite **[BUILD]**
**As a** QA engineer
**I want to** load test commissary endpoints under production volume
**So that** performance regressions are caught

**Acceptance Criteria:**
- [ ] AC-13.1: Load test all 27 endpoints with production data volume
- [ ] AC-13.2: Dashboard: <500ms response time with 10 concurrent users
- [ ] AC-13.3: Production logging: <1s response time
- [ ] AC-13.4: Inventory levels: <2s response time (358 items)
- [ ] AC-13.5: Fulfillment: <1s response time for 50+ pending orders
- [ ] AC-13.6: Use locust or similar tool
- [ ] AC-13.7: Performance baseline documented

#### US-14: Visual Regression Test Suite **[BUILD]**
**As a** QA engineer
**I want to** compare screenshots before/after changes
**So that** UI regressions are caught

**Acceptance Criteria:**
- [ ] AC-14.1: Baseline screenshots for 4 pages (Dashboard, Production, Inventory, Fulfillment)
- [ ] AC-14.2: Automated screenshot comparison on each deployment
- [ ] AC-14.3: Flags visual differences >5% pixel change
- [ ] AC-14.4: Uses Chrome DevTools MCP for screenshot capture
- [ ] AC-14.5: Evidence stored in test report

#### US-15: MANCOM Metrics Validation **[BUILD]**
**As a** QA engineer
**I want to** validate MANCOM metrics calculations
**So that** executive reports show accurate data

**Acceptance Criteria:**
- [ ] AC-15.1: Test Days Inventory: Current stock / (sum production last 7 days / 7)
- [ ] AC-15.2: Test Productivity: kg output / manhours (2 shifts: 5am-2pm, 4pm-1am)
- [ ] AC-15.3: Test Week-on-week comparison: Current week vs previous week
- [ ] AC-15.4: Test Low Stock Alerts: Count items below safety stock
- [ ] AC-15.5: Manual calculation matches API output
- [ ] AC-15.6: Test with realistic production data (not toy data)

## Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria | Tag |
|----|-------------|----------|---------------------|-----|
| FR-1 | BOM DocTypes exist for FG020 variants | High | 2 BOMs created via Frappe UI, active and submitted | **[BUILD]** |
| FR-2 | Auto-deduct raw materials on production | High | Extends `submit_production_output()`, Stock Entry type = Manufacture | **[EXTEND]** |
| FR-3 | Check if enough stock to produce | High | New endpoint `can_we_produce()`, returns max_barrels | **[BUILD]** |
| FR-4 | Calculate production cost before batch | High | New endpoint `get_production_cost()`, uses valuation_rate | **[BUILD]** |
| FR-5 | Display BOM recipe | Medium | New endpoint `get_bill_of_materials()`, shows raw materials | **[BUILD]** |
| FR-6 | Raw material reorder alerts | Medium | Extends `get_rm_reorder_alerts()`, forecasts stockouts | **[EXTEND]** |
| FR-7 | Mark outsourced items | Low | Bulk update 11 items, `is_sub_contracted_item=1` | **[EXTEND]** |
| FR-8 | Architecture decision documented | High | Option A or B chosen, rationale recorded | **[DEFER]** |
| FR-9 | Backend API tests pass | High | 27 endpoints tested, 100% pass rate | **[BUILD]** |
| FR-10 | Frontend E2E tests pass | High | 4 pages tested, extends 2026-02-04 baseline | **[EXTEND]** |
| FR-11 | Component unit tests pass | Medium | React components tested, >80% coverage | **[BUILD]** |
| FR-12 | Integration tests pass | High | Production → fulfillment flow validated | **[BUILD]** |
| FR-13 | Performance tests pass | Medium | <500ms dashboard, <1s production, <2s inventory | **[BUILD]** |
| FR-14 | Visual regression tests pass | Low | 4 pages baseline captured, <5% change threshold | **[BUILD]** |
| FR-15 | MANCOM metrics validated | High | Days Inventory, Productivity calculations match manual | **[BUILD]** |

## Non-Functional Requirements

| ID | Requirement | Metric | Target |
|----|-------------|--------|--------|
| NFR-1 | Performance | Dashboard load time | <500ms (10 concurrent users) |
| NFR-2 | Performance | Production logging response | <1s |
| NFR-3 | Performance | Inventory levels query | <2s (358 items) |
| NFR-4 | Reliability | Test pass rate | 100% before production deployment |
| NFR-5 | Compatibility | Frappe version | Compatible with current Frappe 15.x |
| NFR-6 | Data Integrity | Stock deduction accuracy | 100% (no manual adjustments needed) |
| NFR-7 | Test Coverage | Backend API coverage | 100% (all 27 endpoints) |
| NFR-8 | Test Coverage | Frontend E2E coverage | 100% (all 4 pages + workflows) |
| NFR-9 | Security | RBAC enforcement | Warehouse User permissions required |
| NFR-10 | Maintainability | BOM immutability | Submitted BOMs cannot be edited (Frappe standard) |

## Glossary
- **BOM**: Bill of Materials - Recipe/formula showing raw materials needed for finished goods
- **Stock Entry**: Frappe DocType for recording inventory movements
- **Manufacture**: Stock Entry purpose that auto-deducts raw materials based on BOM
- **Material Receipt**: Stock Entry purpose that adds stock without deducting raw materials
- **Valuation Rate**: Average cost per unit from `tabBin` (stock ledger)
- **tabBin**: Frappe table storing real-time stock levels per item+warehouse
- **FG020-ORIGINAL**: Frozen milk variant using Nestle brand ingredients
- **FG020-GRIFFITH**: Frozen milk variant using Griffith powder
- **TEST-COMMISSARY - BEI**: Test warehouse for safe testing before production
- **MANCOM**: Management Committee - executives receiving weekly KPI reports
- **Days Inventory**: Current stock / average daily consumption (target: 14 days for perishables)
- **Productivity**: kg output / manhours (tracked per shift: 5am-2pm, 4pm-1am)

## Out of Scope
- Creating BOMs for items other than FG020 (confirmed: "We mostly mix finished goods")
- Work Orders and scheduling (not needed for commissary operations)
- Advanced job costing with labor tracking (basic cost calc only)
- Multi-warehouse BOM variants (single commissary warehouse)
- BOM versioning UI (use Frappe duplicate + resubmit pattern)
- Real-time hub inventory tracking (Phase 3 deferred)
- Hub-based distribution workflow (Phase 3 deferred pending decision)
- Mobile app for production logging (web UI sufficient)
- Barcode scanning for raw materials (manual entry sufficient)
- Multi-currency costing (PHP only)

## Dependencies
- Frappe standard BOM DocType (no customization needed)
- Frappe standard Stock Entry DocType (extend purpose field)
- Frappe standard Item DocType (add `is_sub_contracted_item` custom field)
- TEST-COMMISSARY - BEI warehouse exists with test stock
- 358 items already uploaded to Item master
- 27 existing commissary APIs deployed to production
- 4 frontend pages deployed to my.bebang.ph (Vercel)
- Chrome DevTools MCP for frontend testing
- bei-tasks repo (separate from this repo) for frontend component tests

## Success Criteria
- Phase 2 complete in 2-3 hours (measured: research 30m, API 45m, endpoints 1h, testing 20m, mark outsourced 10m)
- All 27 commissary endpoints have passing pytest tests
- All 4 frontend pages pass E2E tests (100% pass rate maintained from 2026-02-04 baseline)
- Production logging with BOM auto-deducts raw materials correctly (validated via integration test)
- Production cost calculation matches manual calculation (within ±1% tolerance)
- MANCOM metrics (Days Inventory, Productivity) validated against manual calculation
- Phase 3 architecture decision documented with Mae/Bryan approval
- Zero production bugs during Feb 2026 go-live related to commissary BOM

## Unresolved Questions
- Packaging cost: Hardcoded or from Item custom field? (Ask Bryan)
- Safety factor for reorder point: 1.5x or 2x lead time? (Ask Arnold)
- Phase 3 decision: Hub-based distribution or direct dispatch? (Mae/Bryan decision)
- If hub-based: Which hub per store route mapping? (Need from Mae)
- If hub-based: Hub inventory ownership model? (BEI consignment or hub-owned?)
- Test data: Use existing TEST-COMMISSARY stock or seed new? (Existing stock OK per research)
- Frontend testing: Run in bei-tasks repo or via deployed my.bebang.ph? (Deployed OK per research)

## Next Steps
1. User approval: Review user stories, approve Phase 2 scope, decide Phase 3 architecture
2. Design phase: Technical design for BOM auto-deduction, API contracts, test plan
3. Implementation: 2-3 hours for Phase 2, 1-2 days for comprehensive testing
4. Deployment: Merge to production branch, trigger GitHub Actions, verify via `/test-full-cycle`
