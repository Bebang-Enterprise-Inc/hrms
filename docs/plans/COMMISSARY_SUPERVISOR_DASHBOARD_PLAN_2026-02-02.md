# Commissary Supervisor Dashboard - Implementation Plan

**Date:** 2026-02-02
**Last Updated:** 2026-02-03
**Go-Live:** TBD (after warehouse interface stabilizes)
**Target User:** Commissary Supervisor / Production Manager
**Platform:** my.bebang.ph (React/Next.js + Shadcn UI)

---

## Executive Summary

This plan covers building a commissary supervisor interface in my.bebang.ph that allows the commissary team to:

1. **Monitor Production** - Track daily production output, batch completion
2. **Manage Inventory** - View raw material levels, finished goods stock, receive alerts
3. **Fulfill Store Orders** - See pending Material Requests, prioritize dispatch
4. **Track Quality** - View FQI reports from stores, handle returns

All features call Frappe ERPNext APIs with proper audit trails.

---

## Part 1: Discovery Summary

### What Already Exists

#### A. Frappe DocTypes (Ready to Use)

| DocType | Type | Purpose | Location |
|---------|------|---------|----------|
| Stock Entry | Standard | All stock movements (production, transfer) | Built-in |
| Material Request | Standard | Store ordering | Built-in |
| Bin | Standard | Stock levels per warehouse/item | Built-in |
| Item | Standard | SKU master | Built-in |
| Warehouse | Standard | Location master | Built-in |
| BEI Store Receiving | Custom | Store-level receiving confirmation | `hrms/hr/doctype/` |
| BEI FQI Report | Custom | Food Quality Inspection | `hrms/hr/doctype/` |
| BEI Cycle Count | Custom | Store inventory counts | `hrms/hr/doctype/` |

#### B. Frappe APIs (Existing)

| Module | Endpoints | Purpose |
|--------|-----------|---------|
| `warehouse.py` | 11 | PO receiving, MR approval, stock transfer |
| `store.py` | 26 | Store ordering, receiving, FQI |
| `inventory.py` | 8 | Cycle count, variance, returns |
| `dispatch.py` | 9 | Trip tracking, delivery confirmation |
| `commissary.py` | 12 | Production tracking, inventory, fulfillment |

#### C. Commissary Data (From RLM Analysis)

| Category | Count | Source |
|----------|-------|--------|
| Finished Goods (In-house) | 9 | FG003-FG020 (Rice Crispies, Sago, etc.) |
| Finished Goods (Outsourced) | 7 | FG001 Leche Flan (Max's), etc. |
| Raw Materials | ~70 | Syrups, toppings, base ingredients |
| External Hubs | 4 | 3MD, JENTEC, RCS, PINNACLE |

---

## Part 2: Questionnaire Responses (2026-02-03)

### Response Status

| Respondent | Role | Status | Date |
|------------|------|--------|------|
| Arnold Lantican | Sr. Food Scientist (R&D) | ✅ Complete | Feb 3, 2026 |
| Bryan C. Pe | Commissary Supervisor | ✅ Complete | Feb 3, 2026 |
| Jennalyn Liwanag | QA Specialist | ✅ Complete | Feb 3, 2026 |

### Key Data Collected

#### A. Production Schedule (Bryan)

| Shift | Start | End | Break |
|-------|-------|-----|-------|
| AM | 5:00 AM | 2:00 PM | 9:00 AM |
| PM | 4:00 PM | 1:00 AM | 8:00 PM |
| Dispatch | 4:00 AM | - | - |

**Production Sequence (by priority):**
1. Frozen Milk - High volume orders
2. Pandan Jelly - Fast moving
3. Rice Crispies - Fast moving
4. Sago - Fast moving
5. Vanilla Jelly - Fast moving

#### B. Batch Sizes & Shelf Life (Bryan + Jennalyn)

| Code | Product | Batch Size | Shelf Life | Storage |
|------|---------|------------|------------|---------|
| FG003 | Rice Crispies | 60 pcs x 250g | 180 days | 20-25C |
| FG004 | Buko Pandan Jelly | 15 pcs x 1kg (16kg) | 15 days | 0-4C |
| FG005 | Vanilla White Jelly | 15 pcs x 1kg (16kg) | 15 days | 0-4C |
| FG006 | Coconut Jelly | 15 pcs x 1kg (16kg) | 14 days | -18C |
| FG007 | Coconut Syrup | 15 pcs x 1kg (15kg) | 14 days | 0-4C |
| FG009 | Sago | 60 pcs x 1kg (60kg) | 14 days | 0-4C |
| FG012 | Melted Ube | 12 pcs x ~0.8kg (10kg) | 21 days | 0-4C |
| FG014 | Pistachio Mix | 3 pcs x 1kg (3kg) | 60 days | 20-25C |
| FG015 | BP Sauce | 4 barrels x 2.5kg (10kg) | 30 days | 0-4C |
| FG020 | Frozen Milk | 6 barrels x 2.5kg (15kg) | 60 days | -18C |
| FG010 | Tapioca | **DISCONTINUED** | - | - |

#### C. Production Capacity (Bryan)

- **Frozen Milk Team:** 3,000 barrels/day maximum
- **Cooking Team:** Limited by chiller capacity
- **Bottleneck:** Availability of ingredients and packaging materials
- **Staffing:** AM shift 11 staff / PM shift 8 staff (2 shifts)
- **Supervisor ratio:** 1:20

#### D. Equipment (Bryan)

| Equipment | Capacity | Products |
|-----------|----------|----------|
| Robocoupe | 15 GAL | Frozen Milk |
| Band Sealer | 100 LBS | FG Products |
| Weighing Scale | 30 KG | FG Products |
| Single Stove Burner | 20 KG | FG Products |
| Chiller | 25 cubic | FG Products |
| Freezer | 25 cubic | FG Products |

#### E. QC Checkpoints (Jennalyn)

| Checkpoint | What's Checked | Who | Frequency |
|------------|---------------|-----|-----------|
| Raw Material Receiving | Package condition, cleanliness | QC/QA/Warehouse | Every delivery |
| Pre-Production | Area cleanliness, sanitation | QC/QA | Daily before startup |
| During Production | Time, temp, mixing, cooling | QC/QA + Production | Hourly (QA), Per batch (crew) |
| Post-Production | Appearance, texture, odor, taste | QC/QA + Production | Hourly (QA), Per batch (crew) |
| Before Dispatch | Product release approval | QC/QA | As needed |

#### F. Testing Procedures (Jennalyn)

**Raw Materials:**
- Physical: Visual, texture, count per pack
- Chemical: pH and Brix
- Sensory: Appearance, odor, color

**Finished Goods:**
- Chemical: pH and Brix
- Sensory: Appearance, odor, color
- Packaging: Seal integrity, leaks, labels

**External Lab Testing (Annual):**
- Frozen Milk, Melted Ube, Halaya, Banana Cinnamon, Coconut Syrup, Sago

#### G. Dispatch Operations (Bryan)

- **Order method:** Email
- **Order deadline:** 12:00 PM
- **Lead time:** 1 day
- **Dispatch time:** 4:00 AM daily
- **Vehicles:** 6 trucks
- **Process:** Order -> Inventory check -> Picking -> Checker verification -> Dispatch

#### H. Delivery Routes (Bryan)

**North Routes (7 trucks):**

| Truck | Stores |
|-------|--------|
| 1 | Clark, Pulilan, Marilao |
| 2 | Fairview Terraces, SM Caloocan, SJDM |
| 3 | Ever Commonwealth, Uptown Center, SM North |
| 4 | Valenzuela, Sangandaan, Grand Central |
| 5 | Lucky Chinatown, SM Manila, Megamall |
| 6 | CTT Morato, Araneta Gateway, Marikina |
| 7 | East Ortigas, Robinson Antipolo, Taytay, St. Lucia |

**South Routes (8 trucks):**

| Truck | Stores |
|-------|--------|
| 1 | Paseo Makati, Grid Rockwell, Uptown BGC |
| 2 | Market Market, Venice Grand Canal, Vista Taguig |
| 3 | MOA, PITX, NAIA T3 |
| 4 | Bicutan, BF Homes, Southmall |
| 5 | Sta Rosa, Solenad, D'Verde Calamba |
| 6 | Evo City Kawit, Robinson Gen Trias, SM Tanza |
| 7 | Festival Alabang, Terminal Alabang, Galleria South |
| 8 | Robinson Imus, Ayala Vermosa |

#### I. External Hubs (Bryan)

| Hub | Type | Location | Contact | Items |
|-----|------|----------|---------|-------|
| 3MD | Wet & Dry | Bulacan | Vlad Ferrer | Chilled/frozen/dry |
| JENTEC | Dry | Pasig | Beverly Que | Dry |
| RCS | Frozen | Taytay | Joey Ancheta | Chilled/frozen |
| PINNACLE | Wet & Dry | Laguna | Daryl Alano | Chilled/frozen/dry |

**Hub coordination:** Email + calls, 1-day lead time, daily inventory tracker
**Challenge:** Slow response from hubs

#### J. Storage Areas (Bryan)

| Area | Temperature | Items |
|------|-------------|-------|
| Main Warehouse | 35C | Raw materials |
| Freezer | -20C | Frozen products |
| Chiller | -5C | Chilled products |
| Dry Storage | 35C | Raw materials |

#### K. Pain Points (ALL THREE AGREE)

| Rank | Issue | Impact | Mentioned By |
|------|-------|--------|--------------|
| **#1** | **Pest infestation** (rats, cockroaches) | Contamination, spoilage, audit failure | Arnold, Jennalyn |
| **#2** | **No sanitation process** | Spoilage, contamination, hazards | Arnold, Jennalyn |
| **#3** | **No proper weighing** | Inconsistent quality per batch | Arnold |
| **#4** | **Ingredient availability** | Low output, production delays | Bryan |
| **#5** | **Inadequate staff GMP training** | Errors, rework, regulatory risk | Jennalyn |

#### L. Ideal System Features Requested

**Arnold (R&D):**
1. Premix monitoring checklist (verify premix weight)
2. Batch coding database (who made, who checked, where sent)
3. 3rd party storage monitoring (3MD, Pinnacle inventory)

**Jennalyn (QA):**
1. Integration with production scheduling & store operations
2. Product traceability & batch tracking with barcode/QR
3. Automated QA checklists & inspection records
4. Supplier & raw material management
5. FIFO/FEFO inventory with alerts

---

## Part 3: SCM MANCOM Analysis (2026-02-03)

**Source:** SCM Weekly MANCOM Report - February 4, 2026

### Key Metrics from MANCOM

| Metric | Current Value | Target | Status |
|--------|---------------|--------|--------|
| Weekly Output | 26.3K kg | - | Down 19% from WW4 |
| Frozen Milk % of Output | 78.7% | - | Dominant product |
| Productivity | 39.3 kg/manhour | ~50 kg/manhour | Down 20.8% |
| Frozen Milk Line Efficiency | 108.51% | >100% | On target |
| Days Inventory (Frozen Milk) | 16.9 days | 14 days | Overstocked |
| Days Inventory (Leche Flan) | 14.0 days | 14 days | At target |
| Wastage | 0.00 kg | 0 | Perfect |
| Store Issuance-to-Sales | 19-97% | 38-42% | Wide variance |

### Production Output Breakdown (WW5)

| Product Category | Output (kg) | % of Total |
|------------------|-------------|------------|
| Frozen Milk | 20.7K | 78.7% |
| Rice Crispies | ~2K | ~7.6% |
| Buko Pandan Jelly | ~1.5K | ~5.7% |
| Sago | ~1K | ~3.8% |
| Other (Vanilla Jelly, Coconut Jelly, Syrup, Ube, etc.) | ~1.1K | ~4.2% |

### Manhours Breakdown (WW5)

| Activity | Manhours | % of Total |
|----------|----------|------------|
| Common Packing | 256 | 38.3% |
| Frozen Milk | 229 | 34.2% |
| Cooking | 184 | 27.5% |
| Leche Flan | 0 | 0% (outsourced) |
| **Total** | **669** | **100%** |

### Key Findings

1. **Powder formula causes productivity drop** - Switching to Griffith powder takes longer (hot water prep)
2. **Frozen Milk dominates** - 78.7% of output, key focus area
3. **Zero wastage achieved** - Due to outsourcing Leche Flan, Banana Cinnamon
4. **Store ordering variance** - SM Sta Rosa at 97% (new store), NAIA T3 at 19% (understocked)
5. **Inventory buildup** - Both Leche Flan and Frozen Milk above 14-day target

---

## Part 4: Enhancements - Ready to Implement (No BOM Required)

### Priority 1: Quick Wins (Can do immediately)

| # | Enhancement | Source | Impact | Effort |
|---|-------------|--------|--------|--------|
| 1 | **Configure Shelf Life per Product** | Bryan + Jennalyn data | Expiry alerts per product | Low |
| 2 | **Fix Hardcoded Thresholds** | Code uses 10/20 for all | Per-product reorder levels | Low |
| 3 | **Add Production Shift Display** | Bryan: AM 5AM-2PM, PM 4PM-1AM | Show current shift on dashboard | Low |
| 4 | **Days Inventory Calculator** | MANCOM format | Critical for perishables | Low |

### Priority 2: Medium Effort

| # | Enhancement | Source | Impact | Effort |
|---|-------------|--------|--------|--------|
| 5 | **Add Delivery Routes** | Bryan's 15 routes with 50+ stores | Show which truck goes where | Medium |
| 6 | **Week-on-Week Comparison View** | MANCOM format | Match executive reporting | Medium |
| 7 | **Productivity Tracking (kg/manhour)** | MANCOM KPI | Key efficiency metric | Medium |
| 8 | **Formula Variant Tracking** | Griffith trial (10 stores) | Compare Original vs Powder | Medium |
| 9 | **Store % to Sales Ratio** | MANCOM (38-42% target) | Identify over/understocked stores | Medium |
| 10 | **Add Temperature Zones** | Bryan's storage temps | Storage area monitoring | Medium |

### Priority 3: Larger Effort (New DocTypes)

| # | Enhancement | Source | Impact | Effort |
|---|-------------|--------|--------|--------|
| 11 | **Create External Hub Tracking** | Bryan's 4 hubs | Monitor 3MD, JENTEC, RCS, PINNACLE | High |
| 12 | **Create QC Checkpoint DocType** | Jennalyn's 5 checkpoints | Digital QC forms | High |
| 13 | **Manhours Logging** | MANCOM breakdown | Track labor allocation | High |
| 14 | **Add Batch Number Format** | Bryan: Product-Date-Expiry-Batch# | Standardized batch tracking | Medium |

### Detailed Specifications

#### Days Inventory (DI) Calculator

```
Formula: Days Inventory = Current Stock / Average Daily Consumption
Target: 14 days (green line in MANCOM chart)
```

**Alert Thresholds:**

| Product | Shelf Life | Target DI | Yellow Alert | Red Alert |
|---------|------------|-----------|--------------|-----------|
| Frozen Milk | 60 days | 14 days | >16 days | >21 days |
| Leche Flan | 15 days | 7 days | >10 days | >12 days |
| Jellies (BP, Vanilla, Coconut) | 14-15 days | 7 days | >10 days | >12 days |
| Sago | 21 days | 10 days | >14 days | >18 days |
| Rice Crispies | 180 days | 30 days | >45 days | >60 days |
| Pistachio Mix | 60 days | 14 days | >21 days | >30 days |

#### Productivity Tracking

```
Formula: Productivity = Total Output (kg) / Total Manhours
Target: ~50 kg/manhour
Current: 39.3 kg/manhour (WW5)
```

#### Line Efficiency

```
Formula: Line Efficiency = Actual Output / Standard Output x 100%
Target: >100%
Current: 108.51% (WW5)
```

### New API Endpoints Needed

```python
# 1. Days Inventory calculation
@frappe.whitelist()
def get_days_inventory():
    """Calculate DI for each product based on avg daily consumption"""

# 2. Productivity tracking
@frappe.whitelist()
def get_productivity_metrics(date_from, date_to):
    """Returns kg/manhour, output by product, manhours by activity"""

# 3. Formula variant tracking
@frappe.whitelist()
def get_formula_comparison(product_code, date_from, date_to):
    """Compare output/cost between Original vs Powder formula"""

# 4. Weekly summary (MANCOM format)
@frappe.whitelist()
def get_weekly_summary(work_week):
    """Get all KPIs for a specific work week"""

# 5. Delivery routes
@frappe.whitelist()
def get_delivery_routes():
    """Get all delivery routes with store assignments"""

# 6. External hub inventory
@frappe.whitelist()
def get_hub_inventory(hub_name):
    """Get inventory levels at external hub"""
```

---

## Part 5: BLOCKED Features (Waiting for BOM Data)

### What's Blocked

| Feature | Why Blocked | Unblock Requirement |
|---------|-------------|---------------------|
| **Auto-deduct raw materials** | Need to know what goes into each product | Complete BOM for all 10 FG items |
| **"Can we produce X barrels?"** | Need ingredient requirements per batch | BOM with quantities |
| **Raw material forecasting** | Need consumption ratios | BOM + historical production data |
| **Production cost calculation** | Need BOM with ingredient costs | BOM + Item valuation rates |
| **True Manufacture Stock Entry** | ERPNext requires BOM for Manufacture type | BOM setup in Frappe |

### Missing BOM Data

**Follow-up document sent:** `docs/plans/COMMISSARY_CRITICAL_MISSING_INFO_2026-02-03.docx`
**Due date:** February 5, 2026

| Product | BOM Status | Missing |
|---------|------------|---------|
| FG003 Rice Crispies | ✅ Complete | - |
| FG004 Buko Pandan Jelly | ✅ Complete | - |
| FG005 Vanilla White Jelly | ✅ Complete | - |
| FG006 Coconut Jelly | ✅ Complete | - |
| FG007 Coconut Syrup | **MISSING** | Full recipe |
| FG009 Sago | **MISSING** | Full recipe |
| FG012 Melted Ube | **MISSING** | Full recipe |
| FG014 Pistachio Mix | **MISSING** | Full recipe |
| FG015 BP Sauce | **MISSING** | Full recipe |
| FG020-ORIGINAL | **INCOMPLETE** | Fresh Milk, Sugar, Vanilla, Stabilizer quantities |
| FG020-GRIFFITH | **INCOMPLETE** | Sugar, Stabilizer quantities (if any) |

### How to Unblock

1. **Arnold (R&D)** must provide complete BOM data for missing products
2. **Alternative:** Arnold shares the "Food Cost Analysis" spreadsheet he mentioned
3. Once BOM data received:
   - Create BOM DocTypes in Frappe
   - Create Item Variants for FG020 (ORIGINAL, GRIFFITH)
   - Enable true Manufacture Stock Entry type
   - Implement auto-deduction APIs

---

## Part 6: Implementation Timeline

### Phase 1: Backend API (Day 1) ✅ COMPLETE
1. ✅ Create `hrms/api/commissary.py` with all endpoints
2. ✅ Update `hrms/api/__init__.py` to register module
3. ✅ Deploy to AWS via `/deploy-frappe`
4. ✅ Test endpoints via curl

### Phase 2: Frontend Pages (Day 2) ✅ COMPLETE
1. ✅ Create `app/api/commissary/route.ts`
2. ✅ Create `hooks/use-commissary.ts`
3. ✅ Create commissary dashboard page
4. ✅ Create production entry page
5. ✅ Create inventory pages

### Phase 3: Integration (Day 3) ✅ COMPLETE
1. ✅ Add RBAC for commissary module
2. ✅ Add sidebar navigation
3. ✅ Test user: `test.warehouse@bebang.ph`
4. ✅ Full E2E testing (Production + Fulfillment workflows)

### Phase 4: Polish & Deploy (Day 4) ✅ COMPLETE
1. ✅ Fixed 6 bugs during E2E testing
2. ✅ Deploy to Vercel
3. ✅ Questionnaire responses collected (Feb 3)

### Phase 5: Enhancements (Pending)

| Week | Tasks | Status |
|------|-------|--------|
| Week 1 | Days Inventory calculator, Shelf Life config, Fix thresholds | Not Started |
| Week 1 | Production shift display, Week-on-week view | Not Started |
| Week 2 | Delivery routes, Productivity tracking | Not Started |
| Week 2 | Formula variant tracking, Store % to sales | Not Started |
| Week 3 | External hub tracking, QC checkpoints | Not Started |
| Week 3+ | BOM-dependent features (after data received) | **BLOCKED** |

---

## Part 7: Dependencies on Other Components

| Dependency | Status | Notes |
|------------|--------|-------|
| Chart of Accounts | ✅ Resolved | 297 accounts uploaded 2026-02-02 |
| Opening Stock | ✅ Resolved | Stock Adjustment Account configured |
| Warehouse Interface | ✅ Complete | Reusing warehouse APIs for dispatch |
| Item Master | ✅ Resolved | 358 items uploaded 2026-02-02 |
| Warehouse Master | ✅ Resolved | 50 warehouses uploaded 2026-02-02 |
| Test Stock | ✅ Complete | MAT-STE-2026-00001 (5 items in TEST-COMMISSARY) |
| **BOM Data** | **BLOCKED** | Waiting for Arnold (R&D) response |

---

## Part 8: Test Accounts

| Role | Email | Password | Permissions |
|------|-------|----------|-------------|
| Commissary User | test.commissary@bebang.ph | TBD | Commissary module access |
| Warehouse User | test.warehouse@bebang.ph | bebang-warehouse-testing-2026 | Warehouse + Commissary |

---

## Part 9: Success Criteria

### Day 1 ✅ COMPLETE (2026-02-02)
- [x] Commissary supervisor can login to my.bebang.ph/dashboard/commissary
- [x] Dashboard shows KPIs (production, stock, orders)
- [x] Can record daily production output (E2E tested: MAT-STE-2026-00004)
- [x] Can fulfill store orders (E2E tested: MAT-STE-2026-00005)

### Week 1 (In Progress)
- [x] Team responds to operations questionnaire (received 2026-02-03)
- [ ] BOM data validated for all FG items (**BLOCKED**)
- [ ] Formula variants configured (FG020-ORIGINAL vs FG020-GRIFFITH) (**BLOCKED**)
- [ ] Days Inventory calculator implemented
- [ ] Shelf life alerts configured per product
- [ ] Production shift display added

### Week 2
- [ ] Week-on-week comparison view (MANCOM format)
- [ ] Productivity tracking (kg/manhour)
- [ ] Delivery routes visible
- [ ] Store % to sales ratio shown

### Month 1
- [ ] 100% of production tracked in ERP
- [ ] Stock discrepancies reduced
- [ ] Manual tracking eliminated
- [ ] External hub inventory visible

### E2E Testing Results (2026-02-02)

| Test | Result | Evidence |
|------|--------|----------|
| Production Log | ✅ PASS | MAT-STE-2026-00004: 25 KG A027 |
| Stock Update | ✅ PASS | A027: 200->225 KG |
| Order View | ✅ PASS | MAT-MR-2026-00002 details |
| Order Fulfill | ✅ PASS | MAT-STE-2026-00005 created |
| Stock Transfer | ✅ PASS | Commissary->BGC |

**Bugs Fixed:** 6 commits during E2E (batch_no, missing endpoints, field aliases, warehouse lookup, material_request_item)

---

## Appendix A: Commissary Finished Goods Reference

| Code | Name | Category | Shelf Life | Storage |
|------|------|----------|------------|---------|
| FG001 | Leche Flan | Outsourced (Max's) | 15 days | Chilled |
| FG002 | Banana Cinnamon | Outsourced (Xyzco) | - | - |
| FG003 | Rice Crispies | In-house | 180 days | Ambient |
| FG004 | Buko Pandan Jelly | In-house | 15 days | Chilled |
| FG005 | Vanilla White Jelly | In-house | 15 days | Chilled |
| FG006 | Coconut Jelly | In-house | 14 days | Frozen |
| FG007 | Coconut Syrup | In-house | 14 days | Chilled |
| FG009 | Sago | In-house | 14 days (validated 21) | Chilled |
| FG010 | Tapioca | **DISCONTINUED** | - | - |
| FG012 | Melted Ube | In-house | 21 days | Chilled |
| FG013 | Langka | Outsourced (Vanj's) | - | - |
| FG014 | Pistachio Mix | In-house | 60 days | Ambient |
| FG015 | Buko Pandan Sauce | In-house | 30 days | Chilled |
| FG016-19 | Flavored Syrups | Outsourced (Griffith) | - | - |
| FG020 | Frozen Milk | In-house (2 variants) | 60 days | Frozen |

### FG020 Frozen Milk - Formula Variants

| Variant | Formula | Status | Stores | Cost |
|---------|---------|--------|--------|------|
| FG020-ORIGINAL | Nestle Cream, Condensed Milk, Evap, etc. | Production | ~40 stores | P199/barrel |
| FG020-GRIFFITH | Powder-based formula from Griffith Foods | Trial | 10 stores | P180/barrel |

**Trial Stores (Griffith):** Megamall, Marilao, Pulilan, Clark, Fairview Terraces, SM Caloocan, SJDM, Valenzuela, Sangandaan, Grand Central

**Trial Start:** December 20, 2025 (Megamall)
**Decision Date:** February 28, 2026
**Key Finding:** Griffith is 10% cheaper but takes longer to produce (hot water prep)

---

## Appendix B: Outsourcing Timeline

| Product | Supplier | Status | Remarks |
|---------|----------|--------|---------|
| Banana Cinnamon | Xyzco | ✅ Completed | - |
| Leche Flan | Max's | ✅ Completed | - |
| Buko Pandan Jelly | Veggie Mix | In Progress | Sample submitted, awaiting approval |
| Vanilla White Jelly | Veggie Mix | Waiting | Waiting for sample |
| Coconut Jelly | Veggie Mix | Waiting | Waiting for sample |
| Coconut Syrup | Griffith | Waiting | Shelf life validation in progress |

---

## Appendix C: Related Documents

| Document | Path |
|----------|------|
| Warehouse Interface Plan | `docs/plans/WAREHOUSE_SUPERVISOR_INTERFACE_PLAN_2026-01-31.md` |
| RLM Commissary Analysis | `scratchpad/RLM_COMMISSARY_CYCLE_ANALYSIS_2026-02-02.md` |
| ERP Migration Master Plan | `docs/plans/ERP_MIGRATION_MASTER_PLAN_2026-01-14.md` |
| Opening Inventory Data | `data/Inventory/OPENING_INVENTORY_SUMMARY_2026-01-14.csv` |
| Critical Missing Info (BOM) | `docs/plans/COMMISSARY_CRITICAL_MISSING_INFO_2026-02-03.docx` |
| SCM MANCOM Report | `F:\Downloads\SCM WEEKLY MANCOM REPORT - FEBRUARY 4, 2026.pptx` |
| Questionnaire (Arnold) | Google Drive: `1cS7gDz894FiIBKjFLPC3O68AS4xRiDbQ` |
| Questionnaire (Bryan) | `F:\Downloads\Bryan - COMMISSARY_OPERATIONS_QUESTIONNAIRE_2026-02-02 (1).docx` |
| Questionnaire (Jennalyn) | `F:\Downloads\Jennalyn COMMISSARY_OPERATIONS_QUESTIONNAIRE_2026-02-02.docx` |

---

---

## Part 10: Execution Plan (2026-02-03)

**Status:** ✅ COMPLETE (2026-02-03)

### RLM Audit Summary

#### What Exists (No New Work Needed)
| Component | Status | Location |
|-----------|--------|----------|
| Commissary API | ✅ 22 endpoints | `hrms/api/commissary.py` (1555 lines) |
| Dispatch API | ✅ 7 endpoints | `hrms/api/dispatch.py` (254 lines) |
| Frontend Dashboard | ✅ 4 pages | `bei-tasks/app/dashboard/commissary/` |
| Frontend Hooks | ✅ 9 hooks + 3 actions | `bei-tasks/hooks/use-commissary.ts` |
| BEI Distribution Trip | ✅ DocType exists | `hrms/hr/doctype/bei_distribution_trip/` |
| BEI Trip Stop | ✅ Child table | Route stops with status tracking |
| BEI Weekly Labor Plan | ✅ DocType exists | Shift planning (no productivity calc) |
| Temperature Tracking | ✅ departure_temp field | In BEI Distribution Trip |

#### Gaps Closed (New Work Completed)
| Gap | Resolution | Status |
|-----|------------|--------|
| No Days Inventory (DI) calculation | Added `get_days_inventory()` API | ✅ Complete |
| Hardcoded thresholds (10/20) | Per-product config via `PRODUCT_THRESHOLDS` + custom fields | ✅ Complete |
| No productivity metrics | Added `get_productivity_metrics()` API | ✅ Complete |
| No delivery route master | Added `get_delivery_routes()` API with 15 routes | ✅ Complete |
| No hub tracking | Created `BEI External Hub` DocType + APIs | ✅ Complete |
| No formula variant tracking | Added `custom_formula_variant` field to Item | ✅ Complete |
| No shelf_life on Item | Added `custom_shelf_life_days` field to Item | ✅ Complete |

### Execution Results

#### Phase 1: Quick Wins (Backend API) ✅ COMPLETE

**Task 1.1: Days Inventory Calculator** ✅
- Endpoint: `get_days_inventory()`
- 7-day rolling consumption calculation
- Per-product thresholds with status indicators

**Task 1.2: Fix Hardcoded Thresholds** ✅
- `PRODUCT_THRESHOLDS` lookup for FG001-FG020
- Falls back to custom fields on Item DocType
- Updated `get_inventory_levels()` and `get_low_stock_alerts()`

**Task 1.3: Production Shift Display** ✅
- Endpoint: `get_current_shift()`
- Returns current shift, time remaining, next shift

#### Phase 2: Medium Effort (New APIs) ✅ COMPLETE

**Task 2.1: Productivity Tracking API** ✅
- Endpoint: `get_productivity_metrics(date_from, date_to)`
- Calculates kg/manhour with 50 kg/hr target

**Task 2.2: Weekly Summary API** ✅
- Endpoint: `get_weekly_summary(work_week)`
- MANCOM-format output with week-on-week comparison

**Task 2.3: Delivery Routes API** ✅
- Endpoint: `get_delivery_routes()`
- 15 routes (7 North, 8 South) with 50+ stores

#### Phase 3: DocType Creation ✅ COMPLETE

**Task 3.1: BEI External Hub DocType** ✅
- Created `hrms/hr/doctype/bei_external_hub/`
- Created `hrms/hr/doctype/bei_hub_item/` (child table)
- Added `get_hub_inventory()` and `update_hub_inventory()` APIs

**Task 3.2: Custom Fields on Item** ✅
- Added to `hrms/fixtures/custom_field.json`:
  - `custom_shelf_life_days` (Int)
  - `custom_reorder_days` (Int)
  - `custom_storage_temp_min` (Float)
  - `custom_storage_temp_max` (Float)
  - `custom_formula_variant` (Select: Original, Griffith, N/A)

### New API Endpoints Added

| Endpoint | Purpose |
|----------|---------|
| `get_days_inventory()` | Calculate DI for all FG items |
| `get_current_shift()` | Return current production shift |
| `get_productivity_metrics(date_from, date_to)` | Calculate kg/manhour |
| `get_weekly_summary(work_week)` | MANCOM-format weekly data |
| `get_delivery_routes()` | Return 15 delivery routes |
| `get_hub_inventory(hub_code)` | Get external hub inventory |
| `update_hub_inventory(hub_code, item_code, qty)` | Update hub stock |

### Deployment Required

To activate new features:
```bash
# Deploy backend
/deploy-frappe

# Run migrations for new DocTypes and custom fields
bench --site hq.bebang.ph migrate
```

### BLOCKED Features (Waiting for BOM Data - Due Feb 5)

- Auto-deduct raw materials
- "Can we produce X?" check
- Raw material forecasting
- Production cost calculation
- True Manufacture Stock Entry

---

**Document Created:** 2026-02-02
**Last Updated:** 2026-02-03
**Author:** Claude Code
**Version:** 2.2

### Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-02 | 1.0 | Initial plan, backend/frontend complete |
| 2026-02-03 | 2.0 | Added questionnaire responses, MANCOM analysis, blocked features, enhancement roadmap |
| 2026-02-03 | 2.1 | Added Part 10: Execution Plan with phase breakdown |
| 2026-02-03 | 2.2 | Execution complete: 7 new APIs, 2 new DocTypes, 5 custom fields |
