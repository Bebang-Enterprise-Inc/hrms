# Tasks: Commissary Phase 2 BOM Implementation & Comprehensive Testing

## Phase 1: Make It Work (POC)

Focus: Validate BOM auto-deduction works end-to-end with real BOMs, 3 new APIs functional, forecasting extensions work. Skip full test suites, accept manual verification.

### 1.1 [BUILD] Create FG020-ORIGINAL BOM via Frappe UI
- **Do**:
  1. Login to hq.bebang.ph as Warehouse User
  2. Navigate to Desk → Manufacturing → Bill of Materials → New
  3. Set Item = FG020-ORIGINAL, Quantity = 15.68, Company = Bebang Enterprise Inc.
  4. Add BOM Items table:
     - RM-CREAM-001 (Nestle Cream): 2kg
     - RM-MILK-CONDENSED-001: 3kg
     - RM-MILK-EVAP-001: 3kg
  5. Set Source Warehouse = TEST-COMMISSARY - BEI for all items
  6. Click Submit (status = Submitted, immutable)
- **Files**: None (Frappe UI-based)
- **Done when**: BOM created, status = Submitted, docstatus = 1
- **Verify**: `frappe.db.exists("BOM", {"item": "FG020-ORIGINAL", "is_active": 1, "docstatus": 1})` returns True via bench console
- **Commit**: `feat(commissary): create FG020-ORIGINAL BOM with 3 raw materials`
- _Requirements: FR-1, AC-1.1, AC-1.4, AC-1.5_
- _Design: Component A - BOM Creation_

### 1.2 [BUILD] Create FG020-GRIFFITH BOM via Frappe UI
- **Do**:
  1. Navigate to Desk → Manufacturing → Bill of Materials → New
  2. Set Item = FG020-GRIFFITH, Quantity = 15.68, Company = Bebang Enterprise Inc.
  3. Add BOM Items table:
     - RM-GRIFFITH-POWDER-001: 4kg
     - RM-WATER-001: 12kg
  4. Set Source Warehouse = TEST-COMMISSARY - BEI for all items
  5. Click Submit (status = Submitted)
- **Files**: None (Frappe UI-based)
- **Done when**: BOM created, status = Submitted, docstatus = 1
- **Verify**: `frappe.db.exists("BOM", {"item": "FG020-GRIFFITH", "is_active": 1, "docstatus": 1})` returns True via bench console
- **Commit**: `feat(commissary): create FG020-GRIFFITH BOM with 2 raw materials`
- _Requirements: FR-1, AC-1.2, AC-1.4_
- _Design: Component A - BOM Creation_

### 1.3 [EXTEND] Add custom fields to Item DocType for packaging cost and safety factor
- **Do**:
  1. Read existing `hrms/fixtures/custom_field.json`
  2. Add two custom fields to Item DocType:
     - Field 1: `packaging_cost_per_batch` (Currency, default: 50, insert_after: standard_rate)
     - Field 2: `lead_time_days` (Int, default: 7, insert_after: min_order_qty)
  3. Test via `/local-frappe` → `bench migrate`
- **Files**: `hrms/fixtures/custom_field.json`
- **Done when**: Fields appear in Item form at hq.bebang.ph
- **Verify**: `frappe.get_meta("Item").get_field("packaging_cost_per_batch")` returns field object
- **Commit**: `feat(commissary): add packaging cost and lead time fields to Item`
- _Requirements: FR-4, FR-6_
- _Design: Component D - Production Cost API, Component F - Forecasting_

### V1 [VERIFY] Quality checkpoint: bench run-tests --app hrms && bench console (validate BOMs exist)
- **Do**: Run quality commands and verify all pass
- **Verify**: BOMs exist, custom fields created, no migration errors
- **Done when**: No lint errors, no type errors, BOMs submitted
- **Commit**: `chore(commissary): pass quality checkpoint Phase 1.1-1.3` (if fixes needed)

### 1.4 [EXTEND] Modify submit_production_output() to auto-deduct raw materials when BOM exists
- **Do**:
  1. Read `hrms/api/commissary.py` → locate `submit_production_output()` function
  2. Before creating Stock Entry, check if BOM exists:
     ```python
     bom = frappe.db.exists("BOM", {"item": item_code, "is_active": 1, "docstatus": 1})
     ```
  3. If BOM exists:
     - Change `stock_entry_type = "Manufacture"` (was "Material Receipt")
     - Set `from_bom = 1`, `bom_no = bom`
     - Call `se.get_items()` to auto-populate raw materials
     - Set source warehouse for RM, target warehouse for FG
  4. If no BOM: Keep existing Material Receipt flow (backwards compatible)
  5. Return extended response with `bom_used`, `raw_materials_deducted` fields
  6. Test via `/local-frappe` → POST to `hrms.api.commissary.submit_production_output`
- **Files**: `hrms/api/commissary.py`
- **Done when**: Stock Entry type = Manufacture when BOM exists, Material Receipt when no BOM
- **Verify**: curl test via `/local-frappe` with FG020-ORIGINAL shows RM deducted
- **Commit**: `feat(commissary): auto-deduct raw materials when BOM exists`
- _Requirements: FR-2, AC-2.1 through AC-2.7_
- _Design: Component B - Auto-Deduction Logic_

### 1.5 [BUILD] Add can_we_produce() API endpoint for capacity check
- **Do**:
  1. Add new function to `hrms/api/commissary.py`:
     ```python
     @frappe.whitelist()
     def can_we_produce(item_code: str, desired_barrels: float) -> dict:
     ```
  2. Get active BOM for item_code
  3. Calculate batches_needed = desired_barrels / 6.27
  4. Query `tabBin` for each raw material stock at commissary warehouse
  5. Calculate max_batches = min(stock / required_qty) for each ingredient
  6. Return JSON: `{can_produce, max_barrels, max_batches, limiting_ingredient, raw_materials[]}`
  7. Test via `/local-frappe` → POST with FG020-ORIGINAL and various barrel quantities
- **Files**: `hrms/api/commissary.py`
- **Done when**: API returns correct capacity based on RM stock
- **Verify**: curl test with sufficient stock → can_produce=true, insufficient stock → can_produce=false
- **Commit**: `feat(commissary): add production capacity check endpoint`
- _Requirements: FR-3, AC-3.1 through AC-3.6_
- _Design: Component C - Capacity Check API_

### 1.6 [BUILD] Add get_production_cost() API endpoint for cost calculation
- **Do**:
  1. Add new function to `hrms/api/commissary.py`:
     ```python
     @frappe.whitelist()
     def get_production_cost(item_code: str, quantity: float = 1) -> dict:
     ```
  2. Get active BOM for item_code
  3. Query `tabBin` for valuation_rate of each raw material
  4. Calculate material cost = sum(qty * valuation_rate)
  5. Get packaging cost from Item field or default to 50
  6. Return JSON: `{cost_per_batch, cost_per_barrel, cost_per_kg, cost_breakdown[], packaging_cost, total_cost}`
  7. Test via `/local-frappe` → POST with FG020-ORIGINAL
- **Files**: `hrms/api/commissary.py`
- **Done when**: API returns cost breakdown matching manual calculation (±1% tolerance)
- **Verify**: curl test → cost_per_barrel = (material_cost + packaging) / 6.27
- **Commit**: `feat(commissary): add production cost calculation endpoint`
- _Requirements: FR-4, AC-4.1 through AC-4.6_
- _Design: Component D - Production Cost API_

### V2 [VERIFY] Quality checkpoint: bench run-tests --app hrms && curl test 3 new endpoints
- **Do**: Run quality commands and verify all pass
- **Verify**: All commands exit 0, 3 new APIs respond correctly
- **Done when**: No lint errors, no type errors, APIs functional
- **Commit**: `chore(commissary): pass quality checkpoint Phase 1.4-1.6` (if fixes needed)

### 1.7 [BUILD] Add get_bill_of_materials() API endpoint for recipe display
- **Do**:
  1. Add new function to `hrms/api/commissary.py`:
     ```python
     @frappe.whitelist()
     def get_bill_of_materials(item_code: str) -> dict:
     ```
  2. Get active BOM for item_code
  3. Query BOM items with current stock from `tabBin`
  4. Calculate yield_info (6.27 barrels, 2.5kg per barrel)
  5. Return JSON: `{bom_no, item_code, item_name, quantity, uom, items[], yield_info}`
  6. Test via `/local-frappe` → POST with FG020-ORIGINAL
- **Files**: `hrms/api/commissary.py`
- **Done when**: API returns BOM recipe with current stock levels
- **Verify**: curl test → items[] contains 3 RM for ORIGINAL, 2 RM for GRIFFITH
- **Commit**: `feat(commissary): add BOM recipe display endpoint`
- _Requirements: FR-5, AC-5.1 through AC-5.5_
- _Design: Component E - BOM Display API_

### 1.8 [EXTEND] Extend get_rm_reorder_alerts() with consumption-based forecasting
- **Do**:
  1. Read `hrms/api/commissary.py` → locate `get_rm_reorder_alerts()` function
  2. Keep existing low stock logic (backwards compatible)
  3. For each alert item, add:
     - Query Stock Entry consumption (last 7 days) for daily_consumption
     - Get lead_time_days from Item custom field (or default 7)
     - Calculate reorder_point = daily_consumption * lead_time * 2.0 (safety_factor)
     - Calculate days_until_stockout = current_stock / daily_consumption
     - Calculate suggested_order_qty = daily_consumption * lead_time * 2
  4. Add new fields to response: `reorder_point, days_until_stockout, daily_consumption, suggested_order_qty, lead_time_days`
  5. Test via `/local-frappe` → POST to endpoint
- **Files**: `hrms/api/commissary.py`
- **Done when**: API returns extended response with forecasting data
- **Verify**: curl test → response includes new forecasting fields
- **Commit**: `feat(commissary): add consumption forecasting to reorder alerts`
- _Requirements: FR-6, AC-6.1 through AC-6.6_
- _Design: Component F - Raw Material Forecasting_

### 1.9 [EXTEND] Bulk update 11 outsourced items with is_sub_contracted_item=1
- **Do**:
  1. Create `scripts/mark_outsourced_items.py`:
     ```python
     import frappe
     outsourced = ["FG001", "FG002", "FG007", "FG009", "FG012", "FG013", "FG014", "FG015", "FG016", "FG017", "FG018", "FG019"]
     for item_code in outsourced:
         if frappe.db.exists("Item", item_code):
             frappe.db.set_value("Item", item_code, "is_sub_contracted_item", 1)
     frappe.db.commit()
     ```
  2. Run via `/local-frappe` → `bench console` → `exec(open("scripts/mark_outsourced_items.py").read())`
  3. Verify field updated in Item master UI
- **Files**: `scripts/mark_outsourced_items.py`
- **Done when**: 11 items marked as outsourced in Item master
- **Verify**: `frappe.db.get_value("Item", "FG001", "is_sub_contracted_item")` returns 1
- **Commit**: `feat(commissary): mark outsourced items to prevent BOM creation`
- _Requirements: FR-7, AC-7.1 through AC-7.4_
- _Design: Component G - Mark Outsourced Items_

### V3 [VERIFY] Quality checkpoint: bench run-tests --app hrms && verify 4 APIs + outsourced items
- **Do**: Run quality commands and verify all pass
- **Verify**: All commands exit 0, 4 APIs functional, 11 items marked
- **Done when**: No lint errors, no type errors, all features working
- **Commit**: `chore(commissary): pass quality checkpoint Phase 1.7-1.9` (if fixes needed)

### 1.10 POC Checkpoint - Validate Phase 2 complete via automated testing
- **Do**:
  1. Via `/local-frappe`, test full production cycle:
     - POST `submit_production_output` with FG020-ORIGINAL, 15.68kg
     - Verify Stock Entry type = Manufacture (not Material Receipt)
     - Verify RM deducted: Cream -2kg, Condensed -3kg, Evap -3kg
     - Verify FG added: FG020-ORIGINAL +15.68kg
  2. Test 3 new APIs:
     - GET `can_we_produce` → verify capacity calculation
     - GET `get_production_cost` → verify cost matches manual calc
     - GET `get_bill_of_materials` → verify recipe display
  3. Test 1 extended API:
     - GET `get_rm_reorder_alerts` → verify forecasting fields present
  4. Verify 11 outsourced items marked
- **Done when**: All automated tests pass with correct values
- **Verify**: All curl tests exit 0, Stock Entry reflects correct deductions
- **Commit**: `feat(commissary): complete Phase 2 BOM implementation POC`

## Phase 2: Refactoring

After POC validated, clean up code structure and add proper error handling.

### 2.1 Extract BOM helper functions to improve code organization
- **Do**:
  1. Read `hrms/api/commissary.py` → identify repeated BOM queries
  2. Extract helper functions:
     - `get_active_bom(item_code)` → Returns BOM doc or None
     - `get_bom_raw_materials(bom_no)` → Returns list of RM with stock
     - `calculate_production_capacity(bom_no, commissary_warehouse)` → Returns max batches
  3. Refactor 4 new endpoints to use helpers
  4. Test via `/local-frappe` → verify no regressions
- **Files**: `hrms/api/commissary.py`
- **Done when**: Code follows DRY principle, no duplication
- **Verify**: `bench run-tests --app hrms` passes, curl tests still work
- **Commit**: `refactor(commissary): extract BOM helper functions`
- _Design: Architecture section - Component extraction_

### 2.2 Add comprehensive error handling for BOM endpoints
- **Do**:
  1. Add try/catch blocks to all 4 new endpoints
  2. Handle errors:
     - BOM not found → Return `{"error": "No BOM found for item"}`
     - Insufficient stock → Raise validation error with details
     - Invalid quantity → Raise validation error
     - Database errors → Log via `frappe.log_error()`, return friendly message
  3. Add validation before Stock Entry creation
  4. Test edge cases via `/local-frappe`
- **Files**: `hrms/api/commissary.py`
- **Done when**: All error paths handled gracefully
- **Verify**: curl tests with invalid inputs return proper error messages
- **Commit**: `refactor(commissary): add error handling for BOM features`
- _Design: Error Handling section_

### V4 [VERIFY] Quality checkpoint: bench run-tests --app hrms && error case testing
- **Do**: Run quality commands and verify all pass
- **Verify**: All commands exit 0, error cases handled properly
- **Done when**: No lint errors, no type errors, tests pass
- **Commit**: `chore(commissary): pass quality checkpoint Phase 2.1-2.2` (if fixes needed)

## Phase 3: Testing

Create comprehensive test suites for backend, frontend, integration, performance, and visual regression.

### 3.1 Create backend unit tests for 27 commissary endpoints
- **Do**:
  1. Create `hrms/api/tests/test_commissary.py`
  2. Import: `from frappe.tests.utils import FrappeTestCase`
  3. Create test class: `class TestCommissaryBOM(FrappeTestCase):`
  4. Write tests for 6 new/extended endpoints:
     - `test_submit_production_with_bom()` → Auto-deduction works
     - `test_submit_production_without_bom()` → Material Receipt fallback
     - `test_can_we_produce_sufficient_stock()` → Returns true
     - `test_can_we_produce_insufficient_stock()` → Returns false, limiting ingredient
     - `test_get_production_cost()` → Cost calculation matches manual
     - `test_get_bill_of_materials()` → Recipe display correct
     - `test_get_rm_reorder_alerts()` → Forecasting fields present
  5. Add error case tests (insufficient stock, invalid BOM, negative qty)
  6. Run via `/local-frappe` → `bench run-tests --app hrms --module commissary`
- **Files**: `hrms/api/tests/test_commissary.py`
- **Done when**: All tests pass, 100% coverage for new endpoints
- **Verify**: `bench run-tests --app hrms --module commissary` exits 0
- **Commit**: `test(commissary): add unit tests for BOM endpoints`
- _Requirements: FR-9, AC-9.1 through AC-9.8_
- _Design: Test Strategy - Unit Tests_

### 3.2 Create integration tests for production → inventory → fulfillment flow
- **Do**:
  1. Create `hrms/api/tests/test_commissary_integration.py`
  2. Write integration test scenarios:
     - **Full Production Cycle:**
       1. Check RM stock before via `get_inventory_levels()`
       2. Log production via `submit_production_output()`
       3. Verify RM deducted, FG added via `get_inventory_levels()`
       4. Verify cost matches via `get_production_cost()`
     - **Store Fulfillment Cycle:**
       1. Create Material Request (store ordering)
       2. Verify appears in `get_pending_store_orders()`
       3. Fulfill via `fulfill_store_order()`
       4. Verify stock transferred
     - **MANCOM Metrics Validation:**
       1. Seed production data (7 days)
       2. Verify `get_days_inventory()` formula correct
       3. Verify `get_productivity_metrics()` formula correct
  3. Run via `/local-frappe` → `bench run-tests --app hrms --module commissary`
- **Files**: `hrms/api/tests/test_commissary_integration.py`
- **Done when**: All integration tests pass
- **Verify**: `bench run-tests --app hrms --module commissary` exits 0
- **Commit**: `test(commissary): add integration tests for full workflows`
- _Requirements: FR-12, AC-12.1 through AC-12.6_
- _Design: Test Strategy - Integration Tests_

### V5 [VERIFY] Quality checkpoint: bench run-tests --app hrms (all backend tests)
- **Do**: Run quality commands and verify all pass
- **Verify**: All commands exit 0, unit + integration tests green
- **Done when**: No lint errors, no type errors, all tests pass
- **Commit**: `chore(commissary): pass quality checkpoint Phase 3.1-3.2` (if fixes needed)

### 3.3 Extend E2E tests for BOM workflows using /test-full-cycle
- **Do**:
  1. Use `/test-full-cycle` skill (Chrome DevTools MCP)
  2. Create new test flow: `/test flow production-bom`
     - Navigate to /dashboard/commissary/production
     - Select FG020-ORIGINAL from dropdown
     - Click "Check Capacity" button → Verify modal shows RM availability
     - Click "Calculate Cost" button → Verify modal shows ₱199/barrel
     - Enter 15.68kg, batch date, submit
     - Wait for success toast
     - Take screenshot
     - Navigate to Inventory page
     - Verify RM stock decreased (Cream: 50→48, Condensed: 80→77, Evap: 70→67)
     - Verify FG stock increased (FG020-ORIGINAL: 0→15.68)
  3. Extend existing page tests:
     - `/test page /dashboard/commissary/inventory` → Verify low stock alerts with forecasting
     - `/test page /dashboard/commissary` → Verify KPIs updated after production
  4. Capture screenshots for evidence
- **Files**: None (skill-based testing)
- **Done when**: 100% pass rate maintained from 2026-02-04 baseline
- **Verify**: `/test-full-cycle` reports all green
- **Commit**: `test(commissary): extend E2E tests for BOM workflows`
- _Requirements: FR-10, AC-10.1 through AC-10.8_
- _Design: Test Strategy - E2E Tests_

### 3.4 Create performance tests for 27 endpoints using locust
- **Do**:
  1. Install locust: `pip install locust`
  2. Create `hrms/tests/performance/test_commissary_load.py`
  3. Define load test scenarios:
     - Dashboard endpoint: <500ms target, 10 concurrent users
     - Production logging: <1s target
     - Inventory levels: <2s target (358 items)
     - Fulfillment: <1s target for 50+ orders
  4. Load profile: 10 users, 100 requests, 2-minute duration
  5. Run via: `locust -f hrms/tests/performance/test_commissary_load.py --host=https://hq.bebang.ph`
  6. Document performance baseline
- **Files**: `hrms/tests/performance/test_commissary_load.py`
- **Done when**: All endpoints meet performance thresholds
- **Verify**: Locust report shows <500ms dashboard, <1s production, <2s inventory
- **Commit**: `test(commissary): add performance tests for 27 endpoints`
- _Requirements: FR-13, AC-13.1 through AC-13.7, NFR-1 through NFR-3_
- _Design: Test Strategy - Performance Tests_

### 3.5 Create visual regression test baseline for 4 pages
- **Do**:
  1. Use Chrome DevTools MCP via `/test-full-cycle`
  2. Capture baseline screenshots for 4 pages:
     - `/dashboard/commissary` → baseline_dashboard.png
     - `/dashboard/commissary/production` → baseline_production.png
     - `/dashboard/commissary/inventory` → baseline_inventory.png
     - `/dashboard/commissary/fulfillment` → baseline_fulfillment.png
  3. Store in `scratchpad/commissary_visual_baseline/`
  4. Create comparison script using ImageMagick
  5. Set threshold: >5% pixel change flags visual regression
- **Files**: `scratchpad/commissary_visual_baseline/`
- **Done when**: Baseline screenshots captured, comparison script ready
- **Verify**: Screenshots exist, comparison script runs successfully
- **Commit**: `test(commissary): create visual regression baseline for 4 pages`
- _Requirements: FR-14, AC-14.1 through AC-14.5_
- _Design: Test Strategy - Visual Regression Tests_

### V6 [VERIFY] Quality checkpoint: /test-full-cycle && locust && visual baseline
- **Do**: Run quality commands and verify all pass
- **Verify**: E2E tests green, performance meets targets, baseline captured
- **Done when**: No test failures, all thresholds met
- **Commit**: `chore(commissary): pass quality checkpoint Phase 3.3-3.5` (if fixes needed)

### 3.6 Create MANCOM metrics validation tests
- **Do**:
  1. Add test methods to `hrms/api/tests/test_commissary_integration.py`:
     - `test_days_inventory_calculation()` → Manual calc vs API output (±1% tolerance)
     - `test_productivity_metrics()` → kg output / manhours (2 shifts)
     - `test_weekly_summary()` → Week-on-week comparison
     - `test_low_stock_alerts()` → Count items below safety_stock
  2. Seed realistic production data (not toy data)
  3. Run via `/local-frappe` → `bench run-tests --app hrms --module commissary`
- **Files**: `hrms/api/tests/test_commissary_integration.py`
- **Done when**: MANCOM metrics match manual calculations
- **Verify**: `bench run-tests --app hrms` exits 0
- **Commit**: `test(commissary): add MANCOM metrics validation tests`
- _Requirements: FR-15, AC-15.1 through AC-15.6_
- _Design: Test Strategy - MANCOM Metrics Validation_

## Phase 4: Quality Gates

### V7 [VERIFY] Full local CI: bench run-tests --app hrms && /test-full-cycle && locust
- **Do**: Run complete local CI suite including E2E and performance
- **Verify**: All commands pass:
  - Unit tests: `bench run-tests --app hrms --module commissary`
  - Integration tests: `bench run-tests --app hrms --module commissary`
  - E2E tests: `/test-full-cycle`
  - Performance: `locust` (all thresholds met)
- **Done when**: Build succeeds, all tests pass, E2E green, performance acceptable
- **Commit**: `chore(commissary): pass local CI` (if fixes needed)

### 4.1 Create PR and verify CI passes
- **Do**:
  1. Verify current branch is a feature branch: `git branch --show-current`
  2. If on default branch, STOP and alert user (should not happen - branch set at startup)
  3. Push branch: `git push -u origin commissary-phase2-bom`
  4. Create PR using gh CLI:
     ```bash
     gh pr create --title "feat(commissary): Phase 2 BOM implementation + comprehensive testing" --body "$(cat <<'EOF'
     ## Summary
     - Created 2 BOMs for FG020 variants (ORIGINAL, GRIFFITH)
     - Extended submit_production_output() to auto-deduct raw materials
     - Added 3 new APIs: can_we_produce, get_production_cost, get_bill_of_materials
     - Extended get_rm_reorder_alerts() with forecasting
     - Marked 11 outsourced items
     - Added comprehensive test suites (unit, integration, E2E, performance, visual regression)

     ## Test Plan
     - [x] Unit tests pass (bench run-tests --app hrms --module commissary)
     - [x] Integration tests pass (production → fulfillment flow)
     - [x] E2E tests pass (/test-full-cycle - 100% pass rate)
     - [x] Performance tests pass (<500ms dashboard, <1s production, <2s inventory)
     - [x] Visual regression baseline captured
     - [x] MANCOM metrics validated

     🤖 Generated with [Claude Code](https://claude.com/claude-code)
     EOF
     )"
     ```
  5. If gh CLI unavailable, use GitHub REST API fallback (see multi-agent-workflow.md)
- **Verify**: Use gh CLI to verify CI:
  - `gh pr checks --watch` (wait for CI completion)
  - Or `gh pr checks` (poll current status)
  - All checks must show ✓ (passing)
- **Done when**: All CI checks green, PR ready for review
- **If CI fails**:
  1. Read failure details: `gh pr checks`
  2. Fix issues locally
  3. Push fixes: `git push`
  4. Re-verify: `gh pr checks --watch`

### V8 [VERIFY] CI pipeline passes
- **Do**: Verify GitHub Actions/CI passes after push
- **Verify**: `gh pr checks` shows all green
- **Done when**: CI pipeline passes
- **Commit**: None

### V9 [VERIFY] AC checklist - Programmatically verify all acceptance criteria met
- **Do**:
  1. Read requirements.md acceptance criteria (AC-1.1 through AC-15.6)
  2. Verify each AC via automated checks:
     - AC-1.1: `frappe.db.exists("BOM", {"item": "FG020-ORIGINAL"})` → True
     - AC-1.2: `frappe.db.exists("BOM", {"item": "FG020-GRIFFITH"})` → True
     - AC-2.1 through AC-2.7: Run `test_submit_production_with_bom()` → Pass
     - AC-3.1 through AC-3.6: Run `test_can_we_produce_*()` → Pass
     - AC-4.1 through AC-4.6: Run `test_get_production_cost()` → Pass
     - AC-5.1 through AC-5.5: Run `test_get_bill_of_materials()` → Pass
     - AC-6.1 through AC-6.6: Run `test_get_rm_reorder_alerts()` → Pass
     - AC-7.1 through AC-7.4: `frappe.db.get_value("Item", "FG001", "is_sub_contracted_item")` → 1
     - AC-9.1 through AC-9.8: `bench run-tests --app hrms --module commissary` → 100% pass
     - AC-10.1 through AC-10.8: `/test-full-cycle` → 100% pass
     - AC-12.1 through AC-12.6: Run integration tests → Pass
     - AC-13.1 through AC-13.7: Locust report → All thresholds met
     - AC-14.1 through AC-14.5: Visual baseline → Screenshots exist
     - AC-15.1 through AC-15.6: MANCOM metrics tests → Pass
- **Verify**: All AC checks return expected values
- **Done when**: All acceptance criteria confirmed met via automated checks
- **Commit**: None

## Notes

### POC Shortcuts Taken (Phase 1)
- Manual BOM creation via UI (not scripted)
- Hardcoded packaging cost fallback (₱50) if Item field empty
- Hardcoded safety factor (2.0) for reorder point
- Manual verification via curl tests (automated tests in Phase 3)
- Water (RM-WATER-001) assumed to have infinite stock (custom handling)

### Production TODOs (Phase 2)
- Make packaging cost configurable per item (Item custom field implemented)
- Make safety factor configurable (Site Config or DocType field)
- Add BOM versioning UI (use Frappe duplicate + resubmit pattern)
- Add multi-warehouse BOM variants (if commissary expands to multiple kitchens)

### Phase 3 Architecture Decision (DEFERRED)
- **Option A: Hub-Based Distribution** (2-3 days effort)
  - Create 4 hub warehouses (North, South, East, West)
  - Build BEI Distribution Trip DocType
  - Refactor create_dispatch_transfer() to route via hub
  - Update get_delivery_routes() to show hub assignments
  - Migrate existing orders to hub-based routing

- **Option B: Direct Dispatch** (0 hours, technical debt)
  - Keep current flow working
  - Document as technical debt in docs/technical_debt.md
  - Create Month 2 ticket for hub-based implementation

**Decision Needed From:** Mae/Bryan

### Test Coverage Summary
- **Backend Unit Tests:** 27 endpoints covered (15 Phase 1 + 6 Phase 2 + 6 Phase 3)
- **Backend Integration Tests:** 3 flows (production cycle, store fulfillment, MANCOM metrics)
- **Frontend E2E Tests:** 4 pages + 1 new flow (production-bom)
- **Performance Tests:** 27 endpoints load tested
- **Visual Regression:** 4 pages baselined
- **MANCOM Metrics:** 4 calculations validated

### Unresolved Questions
- ⚠️ Packaging cost: Hardcoded or from Item? → **RESOLVED: Use custom field, fallback to ₱50**
- ⚠️ Safety factor for reorder point: 1.5x or 2x? → **RESOLVED: 2x (configurable)**
- 🔴 **BLOCKING:** Phase 3 architecture decision (Mae/Bryan)
- ⚠️ If hub-based: Which hub per store? (Need route mapping from Mae)
- ⚠️ If hub-based: Hub inventory ownership? (BEI consignment or hub-owned?)
