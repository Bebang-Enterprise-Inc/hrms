# Commissary Completion Plan - Updated 2026-02-06

**Date:** 2026-02-02
**Last Updated:** 2026-02-06 (v3.0 - BOM Unblocked + Agent Team Execution)
**Go-Live:** Phase 5 Enhancements ready for implementation
**Target User:** Commissary Supervisor / Production Manager / QA Specialist
**Platform:** my.bebang.ph (React/Next.js + Shadcn UI) + hq.bebang.ph (Frappe)

---

## Executive Summary

The commissary dashboard (Phases 1-4) is **COMPLETE** and deployed. This update focuses on:

1. **BOM Data Received** - Arnold's response unblocks production workflow (was BLOCKED since Feb 3)
2. **Raw Materials Master** - Bryan provided 12 RM items with suppliers and reorder levels
3. **QC Forms Digitization** - Jennalyn confirmed 8 paper forms ready for digitization
4. **Agent Team Execution** - Phase 5 enhancements will be built by a coordinated agent team

### What Changed Since v2.2

| Item | v2.2 (Feb 3) | v3.0 (Feb 6) | Impact |
|------|---------------|---------------|--------|
| BOM Data | **BLOCKED** (5 products missing) | **UNBLOCKED** (7/10 BOMs received) | Can build Manufacture workflow |
| Raw Materials Master | Unknown | 12 items with supplier/reorder | Can build RM alerts |
| QC Forms | Identified | 8 forms catalogued, all shareable | Can digitize QC |
| Outsourced Products | Known | Lead times + min order qty confirmed | Can build PO automation |
| Storage Areas | Approximate | Exact temps + capacities confirmed | Can build cold chain alerts |
| Execution Method | Single agent | **Agent Team (7 teammates)** | 3x faster parallel execution |

---

## Part 1: BOM Data - NOW AVAILABLE

### Previously Blocked, Now Unblocked

**Source:** `F:\Downloads\COMMISSARY_CRITICAL_MISSING_INFO_2026-02-03.docx`
**Extracted to:** `scratchpad/commissary_completion_questionnaire_raw.txt`

### Complete BOM Inventory

| Code | Product | BOM Status | Yield | Key Ingredients |
|------|---------|------------|-------|-----------------|
| FG003 | Rice Crispies | **NEW** | 30 pcs x 500g | Rice Crispies 15kg |
| FG004 | Buko Pandan Jelly | Existing (v2.0) | 12.5 kg | Water, Buko Pandan Crystal Gulaman |
| FG005 | Vanilla White Jelly | Existing (v2.0) | 13.06 kg | (Inferred: Water, Crystal Gulaman Clear) |
| FG006 | Coconut Jelly | Existing (v2.0) | 13.06 kg | (Inferred: Water, Crystal Gulaman Clear) |
| FG007 | Coconut Syrup | **NEW** | 0.465 kg | Coconut Milk 400g, Sugar 65g, Cornstarch 10g |
| FG009 | Sago | **NEW** | 41.414 kg | Water 42.7kg, Sago 6kg, Sugar 1.5kg, Guar, Preservatives |
| FG012 | Melted Ube | **NEW** | 13 kg | Ube Halaya 10kg, Water 4kg, Preservatives |
| FG014 | Pistachio Mix | **NEW** | 2.94 kg | Cashew 2kg, Pistachio 1kg |
| FG015 | BP Sauce | **DISCONTINUED** | N/A | No longer produced in commissary |
| FG020-ORIGINAL | Frozen Milk (Traditional) | **NEW** | 15.68 kg / 6.27 barrels | Nestle Cream 2kg, Condensed 3kg, Evap 3kg, Water 8kg |
| FG020-GRIFFITH | Frozen Milk (Powder) | **NEW** | 15.68 kg / 6.27 barrels | Griffith Powder 4kg, Water 12kg |

### BOM Status Summary

| Status | Count | Products |
|--------|-------|----------|
| Complete BOM (new) | 7 | FG003, FG007, FG009, FG012, FG014, FG020-ORIG, FG020-GRIF |
| Complete BOM (existing) | 1 | FG004 |
| Inferred (Crystal Gulaman variants) | 2 | FG005, FG006 |
| Discontinued | 1 | FG015 (remove from system) |
| Outsourced (no BOM needed) | 5 | FG001, FG002, FG013, FG016-19 |

### Still Missing (Low Priority)

- FG005 Vanilla White Jelly exact recipe (likely Crystal Gulaman Clear + Water - confirm with Arnold)
- FG006 Coconut Jelly exact recipe (likely Crystal Gulaman Clear + Water - confirm with Arnold)
- Fresh Milk entry in RM master has no data (blank stock, reorder, supplier)

---

## Part 2: Raw Materials Master - NOW AVAILABLE

**Source:** Bryan's response in DOCX, Section 2

### 12 Raw Materials with Full Data

| # | Raw Material | Unit | Current Stock | Reorder Level | Supplier | Used In |
|---|-------------|------|---------------|---------------|----------|---------|
| 1 | Nestle Cream | BOX | 108 | 1 Day | RGSOI | FG020-ORIG |
| 2 | Condensed Milk | BOX | 87 | 1 Day | CLAYACE | FG020-ORIG |
| 3 | Evaporated Milk | BOX | 213 | 1 Day | 121 | FG020-ORIG |
| 4 | Fresh Milk | - | - | - | - | Unknown |
| 5 | Refined Sugar | SACK | 4 | 1 Day | MANA SUPER FOOD | FG007, FG009 |
| 6 | Vanilla Extract | GAL | 18 | 1 Day | CARANDANG | FG020-ORIG |
| 7 | Crystal Gulaman Clear | BOX | 11 | 1 Day | 121 | FG005, FG006 |
| 8 | Crystal Gulaman Pandan | BOX | 111 | 1 Day | 121 | FG004 |
| 9 | Coconut Milk | BOX | 16 | 1 Day | MOLINA | FG007 |
| 10 | Griffith Ice Milk Powder | SACK | 166 | 1 Day | Griffith | FG020-GRIF |
| 11 | Rice Crispies (raw) | SACK | 48 | 1 Day | GREEN DISTRICT | FG003 |
| 12 | PE Laminated Bags | BUNDLE | 166 | 1 Day | UNNITED POLYRECENT | All FG |

**Key Insight:** All reorder levels are "1 Day" consumption - meaning Bryan orders daily. This means:
- RM alerts should fire at **< 2 days** stock (gives 1 day buffer before stockout)
- Daily PO generation is the norm, not exception

---

## Part 3: QC Forms - Ready for Digitization

**Source:** Jennalyn's response in DOCX, Section 5

### 8 Forms to Digitize

| # | Form | Frequency | Currently | Priority | Effort |
|---|------|-----------|-----------|----------|--------|
| 1 | GMP Checklist | Daily | Paper | P2 | Medium |
| 2 | Area Temperature Verification | Every 4 hours | Paper | P1 | Low |
| 3 | Storage Temperature Monitoring | Every 4 hours | Paper | P1 | Low |
| 4 | Cooking Verification | Every hour | Paper | P2 | Medium |
| 5 | Mixing Monitoring | Every hour | Paper | P2 | Medium |
| 6 | Packaging Monitoring Report | Every hour | Paper | P2 | Medium |
| 7 | Disposition Paper | As needed | Digital | P3 | Low |
| 8 | Suppliers Feedback Report | As needed | Digital | P3 | Low |

**Implementation approach:** Create a single `BEI QC Form` DocType with `form_type` field (Select). Temperature forms (2, 3) are highest priority because they happen 6x/day and are audit-critical.

---

## Part 4: Outsourced Products - Lead Times Confirmed

**Source:** Bryan's response in DOCX, Section 4

| Product | Supplier | Lead Time | Min Order Qty | Delivery Frequency |
|---------|----------|-----------|---------------|-------------------|
| FG001 Leche Flan | Max's | 2 weeks | 30,000 pcs | Twice a month |
| FG002 Banana Cinnamon | Xyzco | 2 weeks | 3,000 pcs | 3x per week |
| FG013 Langka | Vanj's | 2 weeks | 2,000 pcs | 2x per week |
| FG016-19 Sauces | Griffith | 2 weeks | 1,000 pcs | Once a month |

**Action:** Configure these as Purchase Order items with auto-reorder rules in Frappe.

---

## Part 5: Storage Areas - Confirmed Specs

**Source:** Bryan's response in DOCX, Section 3

| Area | Temperature | Capacity | Items | Custom Field Value |
|------|-------------|----------|-------|-------------------|
| Main Warehouse (Dry) | 25-35°C | 20 Pallets | Dry ingredients | `storage_temp_min=25, max=35` |
| Chiller 1 | 0-4°C | 1,400 L | Chilled products | `storage_temp_min=0, max=4` |
| Freezer 1 | -18°C | 1,400 L | Coconut Jelly | `storage_temp_min=-18, max=-18` |

**Note:** v2.2 had slightly different temps (Bryan said -20C freezer, -5C chiller). The DOCX data is authoritative: **-18°C freezer, 0-4°C chiller**.

---

## Part 6: Duplication Audit Results

### Code Audit (2026-02-06)

**Source:** Full codebase exploration by Explore agent

| Component | Exists | Count | Status |
|-----------|--------|-------|--------|
| Backend APIs (commissary.py) | Yes | 50+ endpoints | 95% complete |
| Backend APIs (dispatch.py) | Yes | 7 endpoints | 100% complete |
| DocTypes | Yes | 14 commissary-specific | 90% complete |
| Frontend Pages | Yes | 10 React pages | 100% complete |
| Custom Fields (Item) | Yes | 5 fields | 100% complete |
| BOM Integration | Partial | Read-only queries | 40% complete |
| QI Workflow | Partial | Create/read only | 60% complete |

### Classification Summary

| Classification | Count | Items |
|----------------|-------|-------|
| **EXTEND** | 8 | BOM CRUD, QI rejection, hub sync, production shift, RM alerts, batch expiry workflow, fulfillment consolidation, inventory consolidation |
| **BUILD** | 6 | BEI Production DocType, BEI QC Form DocType, BOM seed data (10 BOMs), RM master seed data, outsourced product auto-PO, production planning dashboard |
| **DELETE** | 3 | `create_dispatch_transfer()` (duplicate of fulfill), internal helpers from public API, FG015 BP Sauce (discontinued) |

### Cost Savings from Audit

| Metric | Without Audit | With Audit | Savings |
|--------|---------------|------------|---------|
| New DocTypes | 8 | 2 | **6 DocTypes** (reuse existing 14) |
| New API Endpoints | 25 | 8 | **17 endpoints** (extend existing 50+) |
| New Frontend Pages | 6 | 0 | **6 pages** (all 10 already built) |
| **Estimated Effort** | **4 weeks** | **1.5 weeks** | **2.5 weeks** |
| **Duplication Risk** | **60%** | **0%** | **Eliminated** |

---

## Part 7: Implementation Tasks

### Phase 5A: BOM Setup (CRITICAL - Unblocks Production Workflow)

| # | Task | Type | Effort | Dependencies |
|---|------|------|--------|-------------|
| 5A.1 | Build BOM CRUD API (`create_bom`, `update_bom`, `get_bom_detail`) | EXTEND | 3h | None |
| 5A.2 | Seed 10 BOMs from questionnaire data into Frappe | BUILD | 2h | 5A.1 |
| 5A.3 | Switch production from Material Receipt to Manufacture type | EXTEND | 2h | 5A.2 |
| 5A.4 | Build "Can we produce X?" pre-check API | BUILD | 1.5h | 5A.2 |
| 5A.5 | Build auto-deduct RM on production completion | EXTEND | 2h | 5A.3 |
| 5A.6 | Add FG020 formula variant selection to production form | EXTEND | 1h | 5A.2 |

### Phase 5B: Raw Materials & Procurement

| # | Task | Type | Effort | Dependencies |
|---|------|------|--------|-------------|
| 5B.1 | Seed 12 RM items with supplier/reorder data | BUILD | 1h | None |
| 5B.2 | Enhance RM reorder alerts (2-day threshold) | EXTEND | 1h | 5B.1 |
| 5B.3 | Configure outsourced products auto-PO rules | BUILD | 2h | 5B.1 |
| 5B.4 | Build RM consumption forecast from BOM + orders | BUILD | 2h | 5A.2, 5B.1 |

### Phase 5C: Quality & Compliance

| # | Task | Type | Effort | Dependencies |
|---|------|------|--------|-------------|
| 5C.1 | Create BEI QC Form DocType (8 form types) | BUILD | 3h | None |
| 5C.2 | Build QC form submission API (temperature, cooking, GMP) | BUILD | 2h | 5C.1 |
| 5C.3 | Build QI rejection disposition workflow (auto-scrap) | EXTEND | 2h | None |
| 5C.4 | Create QI templates per FG item (pH, Brix, sensory) | BUILD | 1.5h | None |
| 5C.5 | Build QC form frontend page | BUILD | 3h | 5C.1, 5C.2 |

### Phase 5D: Consolidation & Cleanup

| # | Task | Type | Effort | Dependencies |
|---|------|------|--------|-------------|
| 5D.1 | Remove FG015 BP Sauce from system (discontinued) | DELETE | 0.5h | None |
| 5D.2 | Deprecate `create_dispatch_transfer()` | DELETE | 0.5h | None |
| 5D.3 | Remove internal helpers from @whitelist | DELETE | 0.5h | None |
| 5D.4 | Update storage temps to confirmed values (-18°C, 0-4°C) | EXTEND | 0.5h | None |
| 5D.5 | Update custom field defaults from questionnaire | EXTEND | 0.5h | None |

### Phase 5E: Production Analytics (Enhancement)

| # | Task | Type | Effort | Dependencies |
|---|------|------|--------|-------------|
| 5E.1 | Create BEI Production DocType (batch metadata) | BUILD | 4h | 5A.3 |
| 5E.2 | Build shift-based production tracking | EXTEND | 2h | 5E.1 |
| 5E.3 | Build production planning dashboard API | EXTEND | 3h | 5A.4, 5B.4 |
| 5E.4 | Build batch expiry alert scheduled job | BUILD | 2h | None |
| 5E.5 | Enhance hub inventory sync (bi-directional) | EXTEND | 3h | None |

### Total Effort

| Phase | Tasks | Effort | Priority |
|-------|-------|--------|----------|
| 5A: BOM Setup | 6 | 11.5h | **CRITICAL** |
| 5B: Raw Materials | 4 | 6h | HIGH |
| 5C: Quality | 5 | 11.5h | HIGH |
| 5D: Cleanup | 5 | 2.5h | MEDIUM |
| 5E: Analytics | 5 | 14h | MEDIUM |
| **Total** | **25** | **45.5h** | - |

---

## Part 8: Agent Team Execution Plan

### Why Agent Team (Not Single Agent)

| Factor | Single Agent | Agent Team (7) |
|--------|-------------|----------------|
| Calendar time | ~6 days | **~2 days** |
| Parallel work | Sequential | Backend + Frontend + QC parallel |
| Code review | Self-review | **Opus code reviewer** catches issues |
| Testing | After all code | **Continuous QA** during development |
| Risk | One context window overflow | Isolated contexts per domain |

### Team Composition

```
/agent-team feature commissary-completion
```

| Teammate | Model | Role | Owns | Phase |
|----------|-------|------|------|-------|
| **project-manager** | Opus | Orchestrate team, unblock stuck agents, architecture decisions | Task list | All |
| **backend-bom** | Sonnet | BOM CRUD, production workflow, RM forecast | `hrms/api/commissary.py` (BOM section) | 5A, 5B |
| **backend-qc** | Sonnet | QC Form DocType, QI rejection, templates | `hrms/hr/doctype/bei_qc_form/`, `hrms/api/commissary.py` (QC section) | 5C |
| **backend-analytics** | Sonnet | Production DocType, shift tracking, planning dashboard | `hrms/hr/doctype/bei_production/`, `hrms/api/commissary.py` (analytics section) | 5E |
| **code-reviewer** | Opus | Security, performance, Frappe conventions review | Review PRs | After each phase |
| **deployer** | Sonnet | PRs, GitHub Actions, migrations, production verification | `.github/workflows/`, PR management | After review |
| **qa-tester** | Sonnet | E2E testing, bug tasks, regression verification | Test scripts | After deploy |

### Phase-Based Execution

```
┌─────────────────────────────────────────────────────────────────┐
│ WAVE 1: PARALLEL BACKEND (Day 1)                                │
│                                                                   │
│  backend-bom ──────→ 5A.1 BOM CRUD → 5A.2 Seed BOMs            │
│  backend-qc ───────→ 5C.1 QC DocType → 5C.2 QC APIs            │
│  backend-analytics ─→ 5D.1-5D.5 Cleanup (quick wins)           │
│                                                                   │
│  Synchronization: backend-bom finishes 5A.2 → unblocks 5A.3-6  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ WAVE 2: DEPENDENT BACKEND (Day 1-2)                             │
│                                                                   │
│  backend-bom ──────→ 5A.3 Manufacture type → 5A.4 Pre-check    │
│                      → 5A.5 Auto-deduct → 5A.6 Variant select  │
│  backend-qc ───────→ 5C.3 QI rejection → 5C.4 Templates        │
│  backend-analytics ─→ 5B.1 Seed RM → 5B.2-4 RM enhancements   │
│                                                                   │
│  Gate: Code review by Opus reviewer before deployment           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ WAVE 3: DEPLOY + TEST (Day 2)                                   │
│                                                                   │
│  deployer ─────────→ Create PR → Monitor CI → Merge → Migrate  │
│  qa-tester ────────→ /test-full-cycle commissary flows          │
│                                                                   │
│  Gate: ALL E2E tests pass before proceeding                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ WAVE 4: ANALYTICS & QC FRONTEND (Day 2-3)                       │
│                                                                   │
│  backend-analytics ─→ 5E.1 Production DocType → 5E.2-5 APIs    │
│  backend-qc ───────→ 5C.5 QC form frontend page                │
│  backend-bom ──────→ 5E.3 Production planning dashboard         │
│                                                                   │
│  Gate: Final code review + E2E test                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ WAVE 5: FINAL DEPLOY + VERIFICATION (Day 3)                     │
│                                                                   │
│  deployer ─────────→ Final PR → CI → Merge → Migrate           │
│  qa-tester ────────→ Full regression test                       │
│  project-manager ──→ Verify all tasks complete, shut down team  │
└─────────────────────────────────────────────────────────────────┘
```

### File Ownership (CRITICAL - Prevents Conflicts)

| Domain | Files | Owner |
|--------|-------|-------|
| BOM APIs | `hrms/api/commissary.py` lines 2300-2500 (BOM section) | backend-bom |
| QC DocType | `hrms/hr/doctype/bei_qc_form/**` | backend-qc |
| QC APIs | `hrms/api/commissary.py` lines 2100-2300 (QC section) | backend-qc |
| Production DocType | `hrms/hr/doctype/bei_production/**` | backend-analytics |
| Analytics APIs | `hrms/api/commissary.py` lines 2500+ (analytics) | backend-analytics |
| Cleanup tasks | `hrms/api/commissary.py` lines 1-100 (imports/helpers) | backend-analytics |
| BOM seed scripts | `scripts/seed_commissary_bom.py` | backend-bom |
| RM seed scripts | `scripts/seed_rm_master.py` | backend-analytics |
| QC form frontend | `../bei-tasks/app/dashboard/commissary/qc-forms/` | backend-qc |
| GitHub Actions | `.github/workflows/**` | deployer |

**CONFLICT PREVENTION:** Each backend agent owns a SECTION of commissary.py, not the whole file. They MUST NOT edit outside their section. If cross-section changes needed, coordinate via project-manager.

### Quality Gates

| Gate | When | Who | Criteria |
|------|------|-----|----------|
| API Contract | After Wave 1 | project-manager | All new endpoints documented |
| Code Review | After Wave 2 | code-reviewer (Opus) | No critical security/performance issues |
| CI Pass | After Wave 3 | deployer | GitHub Actions green |
| E2E Tests | After Wave 3 | qa-tester | All commissary flows pass |
| Final Review | After Wave 4 | code-reviewer (Opus) | Analytics + QC pages reviewed |
| Regression | After Wave 5 | qa-tester | Full /test-full-cycle pass |

---

## Part 9: Development Workflow (MANDATORY - /build Rules)

### For All Teammates

**For Python/API changes:**
1. Use `/local-frappe` to test changes BEFORE committing
2. Never commit untested Python code
3. Verify migrations work locally first

**For Commits:**
1. NEVER use `git commit` directly
2. ALWAYS use `/pr-deploy` (creates PR and triggers deployment)
3. Follow commit conventions: `feat:`, `fix:`, `refactor:`

**For Deployments:**
1. Poll using `scripts/wait_for_deployment.py` - NEVER stop at deployment gates
2. On timeout, create `[VERIFY]` task but continue working
3. Frappe migration: max 300s wait, 30s poll interval
4. Vercel build: max 120s wait, 15s poll interval

**Forbidden Patterns:**
- "PAUSED PENDING DEPLOYMENT" (use polling!)
- "Would you like me to continue?" (operate autonomously)
- Pushing directly to `production` branch
- Editing files outside your ownership domain

---

## Part 10: BOM Seed Data (Ready to Import)

### Frappe BOM Format

Each BOM below is ready to be created via the new `create_bom()` API or `bench console`.

```python
BOMS = [
    {
        "item": "FG007",
        "item_name": "Coconut Syrup",
        "quantity": 0.465,  # kg yield
        "uom": "Kg",
        "materials": [
            {"item_code": "Coconut Milk", "qty": 0.400, "uom": "Kg"},
            {"item_code": "Refined Sugar", "qty": 0.065, "uom": "Kg"},
            {"item_code": "Cornstarch", "qty": 0.010, "uom": "Kg"},
        ]
    },
    {
        "item": "FG009",
        "item_name": "Sago",
        "quantity": 41.414,  # kg yield
        "uom": "Kg",
        "materials": [
            {"item_code": "Filtered Water", "qty": 42.722, "uom": "Kg"},
            {"item_code": "Sago", "qty": 6.000, "uom": "Kg"},
            {"item_code": "Refined Sugar", "qty": 1.496, "uom": "Kg"},
            {"item_code": "Guar", "qty": 0.037, "uom": "Kg"},
            {"item_code": "Strawberry Red Color", "qty": 0.003, "uom": "Kg"},
            {"item_code": "Sodium Benzoate", "qty": 0.001, "uom": "Kg"},
            {"item_code": "Potassium Sorbate", "qty": 0.001, "uom": "Kg"},
        ]
    },
    {
        "item": "FG004",
        "item_name": "Buko Pandan Jelly",
        "quantity": 12.5,  # kg yield (from Pandan Green Jelly)
        "uom": "Kg",
        "materials": [
            {"item_code": "Filtered Water", "qty": 14.000, "uom": "Kg"},
            {"item_code": "Buko Pandan Crystal Gulaman", "qty": 0.720, "uom": "Kg"},
        ]
    },
    {
        "item": "FG012",
        "item_name": "Melted Ube/Spread",
        "quantity": 13.0,  # kg yield
        "uom": "Kg",
        "materials": [
            {"item_code": "Ube Halaya", "qty": 10.000, "uom": "Kg"},
            {"item_code": "Filtered Water", "qty": 4.000, "uom": "Kg"},
            {"item_code": "Sodium Benzoate", "qty": 0.004, "uom": "Kg"},
            {"item_code": "Potassium Sorbate", "qty": 0.004, "uom": "Kg"},
        ]
    },
    {
        "item": "FG014",
        "item_name": "Pistachio/Cashew Mix",
        "quantity": 2.94,  # kg yield
        "uom": "Kg",
        "materials": [
            {"item_code": "Cashew", "qty": 2.000, "uom": "Kg"},
            {"item_code": "Pistachio", "qty": 1.000, "uom": "Kg"},
        ]
    },
    {
        "item": "FG003",
        "item_name": "Rice Crispies",
        "quantity": 15.0,  # kg (30 pcs x 500g)
        "uom": "Kg",
        "materials": [
            {"item_code": "Rice Crispies (raw)", "qty": 15.000, "uom": "Kg"},
        ]
    },
    {
        "item": "FG020-ORIGINAL",
        "item_name": "Frozen Ice Milk (Traditional)",
        "quantity": 15.68,  # kg / 6.27 barrels
        "uom": "Kg",
        "materials": [
            {"item_code": "Nestle Cream", "qty": 2.000, "uom": "Kg"},
            {"item_code": "Condensed Milk", "qty": 3.000, "uom": "Kg"},
            {"item_code": "Evaporated Milk", "qty": 3.000, "uom": "Kg"},
            {"item_code": "Filtered Water", "qty": 8.000, "uom": "Kg"},
        ]
    },
    {
        "item": "FG020-GRIFFITH",
        "item_name": "Frozen Ice Milk (Griffith Powder)",
        "quantity": 15.68,  # kg / 6.27 barrels
        "uom": "Kg",
        "materials": [
            {"item_code": "Griffith Ice Milk Powder", "qty": 4.000, "uom": "Kg"},
            {"item_code": "Filtered Water", "qty": 12.000, "uom": "Kg"},
        ]
    },
]
```

---

## Part 11: Success Criteria

### Phase 5A: BOM (CRITICAL)
- [ ] All 8 BOMs created in Frappe and set as default for each FG item
- [ ] Production uses Manufacture type (not Material Receipt)
- [ ] Auto-deduction depletes RM stock on production completion
- [ ] "Can we produce?" check works with real stock levels
- [ ] FG020 formula variant selection works (Original vs Griffith)

### Phase 5B: Raw Materials
- [ ] 12 RM items seeded with supplier and reorder data
- [ ] RM alerts fire at < 2 days stock (per Bryan's "1 day" reorder level)
- [ ] Outsourced product PO automation configured

### Phase 5C: Quality
- [ ] BEI QC Form DocType created with 8 form types
- [ ] Temperature monitoring forms submittable via my.bebang.ph
- [ ] QI rejection auto-creates scrap/wastage stock entry
- [ ] QI templates created per FG item (pH, Brix, sensory)

### Phase 5D: Cleanup
- [ ] FG015 removed from active products
- [ ] `create_dispatch_transfer()` deprecated
- [ ] Internal helpers removed from @whitelist
- [ ] Storage temps updated to confirmed values

### Phase 5E: Analytics
- [ ] BEI Production DocType tracks batch metadata
- [ ] Shift-based productivity (kg/manhour) calculation works
- [ ] Production planning dashboard suggests what to produce based on DI + demand + RM availability
- [ ] Batch expiry alerts fire for products approaching shelf life

### Overall
- [ ] All 25 tasks completed
- [ ] Code reviewed by Opus (2 review cycles)
- [ ] E2E tests pass (qa-tester runs /test-full-cycle)
- [ ] Deployed to production
- [ ] No regressions in existing commissary functionality

---

## Part 12: Existing Infrastructure Reference (From Phases 1-4)

### Completed (Do NOT Rebuild)

| Component | Status | Details |
|-----------|--------|---------|
| Backend API | 50+ endpoints | `hrms/api/commissary.py` (2,866 lines) |
| Dispatch API | 7 endpoints | `hrms/api/dispatch.py` (290 lines) |
| 14 DocTypes | Built | Distribution, Hub, Quality, Inventory, Orders |
| 10 Frontend Pages | Built | Dashboard, Production, Inventory, Fulfillment, RM, Quality, Wastage, Expiring, Transfer, Work Orders |
| 5 Custom Fields on Item | Built | shelf_life, reorder_days, storage_temp_min/max, formula_variant |
| Delivery Routes | 15 routes | 7 North + 8 South, 50+ stores |
| External Hubs | 4 hubs | 3MD, JENTEC, RCS, PINNACLE |
| Days Inventory | API ready | `get_days_inventory()` with per-product thresholds |
| Shift Display | API ready | `get_current_shift()` |
| Productivity | API ready | `get_productivity_metrics()` |
| Weekly Summary | API ready | `get_weekly_summary()` (MANCOM format) |

---

## Appendix A: Commissary Finished Goods Reference (Updated)

| Code | Name | Category | Shelf Life | Storage | BOM Status |
|------|------|----------|------------|---------|------------|
| FG001 | Leche Flan | Outsourced (Max's) | 15 days | Chilled | N/A |
| FG002 | Banana Cinnamon | Outsourced (Xyzco) | - | - | N/A |
| FG003 | Rice Crispies | In-house | 180 days | Ambient | **COMPLETE** |
| FG004 | Buko Pandan Jelly | In-house | 15 days | Chilled | **COMPLETE** |
| FG005 | Vanilla White Jelly | In-house | 15 days | Chilled | Inferred |
| FG006 | Coconut Jelly | In-house | 14 days | Frozen (-18°C) | Inferred |
| FG007 | Coconut Syrup | In-house | 14 days | Chilled | **COMPLETE** |
| FG009 | Sago | In-house | 14 days | Chilled | **COMPLETE** |
| ~~FG010~~ | ~~Tapioca~~ | **DISCONTINUED** | - | - | - |
| FG012 | Melted Ube | In-house | 21 days | Chilled | **COMPLETE** |
| FG013 | Langka | Outsourced (Vanj's) | - | - | N/A |
| FG014 | Pistachio Mix | In-house | 60 days | Ambient | **COMPLETE** |
| ~~FG015~~ | ~~BP Sauce~~ | **DISCONTINUED** | - | - | - |
| FG016-19 | Flavored Syrups | Outsourced (Griffith) | - | - | N/A |
| FG020-ORIG | Frozen Milk (Traditional) | In-house | 60 days | Frozen (-18°C) | **COMPLETE** |
| FG020-GRIF | Frozen Milk (Griffith) | In-house (trial) | 60 days | Frozen (-18°C) | **COMPLETE** |

---

## Appendix B: Related Documents

| Document | Path |
|----------|------|
| Questionnaire Raw Extract | `scratchpad/commissary_completion_questionnaire_raw.txt` |
| Critical Missing Info (BOM responses) | `F:\Downloads\COMMISSARY_CRITICAL_MISSING_INFO_2026-02-03.docx` |
| Warehouse Interface Plan | `docs/plans/WAREHOUSE_SUPERVISOR_INTERFACE_PLAN_2026-01-31.md` |
| Agent Team Skill | `.claude/skills/agent-team/SKILL.md` |
| Agent Team Use Cases | `.claude/skills/agent-team/USE_CASES.md` |
| Duplication Audit Report | Part 6 of this document |
| ERP Migration Master Plan | `docs/plans/ERP_MIGRATION_MASTER_PLAN_2026-01-14.md` |
| Finance Module Plan (reference for /write-plan) | `docs/plans/2026-02-06-finance-accounting-module.md` |

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-02 | 1.0 | Initial plan, backend/frontend complete |
| 2026-02-03 | 2.0 | Added questionnaire responses, MANCOM analysis, blocked features, enhancement roadmap |
| 2026-02-03 | 2.1 | Added Part 10: Execution Plan with phase breakdown |
| 2026-02-03 | 2.2 | Execution complete: 7 new APIs, 2 new DocTypes, 5 custom fields |
| **2026-02-06** | **3.0** | **BOM UNBLOCKED: 7 new BOMs from DOCX. Duplication audit (85% already built). Agent Team execution plan (7 teammates). 25 tasks across 5 phases. QC forms + RM master + outsourced product data integrated. FG015 discontinued.** |

---

**Document Version:** 3.0
**Author:** Claude Code
**Execution Method:** Agent Team (7 teammates) via `/agent-team feature commissary-completion`
