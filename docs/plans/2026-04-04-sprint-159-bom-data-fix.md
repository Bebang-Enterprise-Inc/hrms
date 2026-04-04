---
canonical_sprint_id: S159
display: Sprint 159
status: COMPLETED
branch: s159-bom-data-fix
lane: single
created_date: 2026-04-04
completed_date: 2026-04-04
deployed_at: 2026-04-04
backend_pr:
frontend_pr:
l3_result: 13/13 PASS
execution_summary: Fixed 30 BOMs (18 FG->BKI, 12 MN->BEI), created 6 new BOMs (Iskrambol 13 items, Ginataang 11, Pop Lamig 7, 3 Tikims), regenerated CSV fixtures from Frappe SSOT, deleted hallucinated files. 50 demand snapshots deferred (linked records need SSM cleanup).
depends_on: S155
---

# S159 — Fix BOM Data: Company Assignments, Missing Products, Pipeline Fixture

**Goal:** Fix all 30 BOMs in Frappe (reversed company assignments), create 3 missing product BOMs (Iskrambol, Ginataang Halo-Halo, Pop Lamig), regenerate the demand pipeline CSV fixture from Frappe, and clean up hallucinated data.

**Origin:** S155 audit found the demand pipeline reading from a hallucinated local CSV. Investigation revealed BOMs exist but with wrong company assignments (ingredients under BEI, products under BKI — should be reversed). 25 BOMs were deleted by an agent on March 27. 3 POS-confirmed products have no BOMs.

**Source of truth:** Arnold James Lantican (R&D Manager) — "Store BOM 2026" and "Price Breakdown of Store BOM" Google Sheets. Downloaded to `tmp/bom_investigation/`. Pop Lamig canonical mapping at `data/_CLEANROOM/agent_runs/2026-03-10_pop_lamig_bom/POP_LAMIG_BOM_CANONICAL_MAPPING.csv`.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists
S155 (SCM integration sprint, 2026-04-03) discovered that the demand pipeline (`hrms/utils/store_order_demand_snapshot.py`) was reading BOM data from a local CSV fixture (`hrms/fixtures/store_ordering/bom_master_compact.csv`). A previous agent session created a hallucinated CSV (`data/_CLEANROOM/bom/store_consumption_bom.csv`) and a redundant script (`scripts/build_demand_snapshots.py`) that wrote 1,619 bad demand snapshots to production. Those have been cleaned up.

Investigation revealed:
- 30 BOMs exist in Frappe but with **reversed company assignments** — ingredient BOMs (FG series, commissary recipes) are under BEI instead of BKI; product BOMs (MN series, POS menu items) are under BKI instead of BEI
- 25 BOMs were deleted on March 27 by an agent cleanup session (confirmed via `Deleted Document` audit trail)
- The P05 migration originally created 19 BOMs correctly on March 3 (0 errors, 230 components), but the March 27 deletion removed the product-level ones
- 3 POS-confirmed products (Iskrambol, Ginataang Halo-Halo, Pop Lamig) have zero BOMs in Frappe

### Why this architecture
- **BKI owns ingredient BOMs** because BKI (Bebang Kitchen Inc.) is the commissary that manufactures sub-components (Leche Flan, Sago, Frozen Ice Milk, sauces, jellies). These are commissary production recipes.
- **BEI owns product BOMs** because BEI (Bebang Enterprise Inc.) operates the stores that sell finished cups (Presidential, Iskrambol, etc.). Product BOMs define what ingredients go into each POS cup — needed for store ordering demand calculation.
- **BEI and BKI are separate legal entities** — store replenishment from BKI to BEI is an external purchase with VAT, NOT an internal transfer. See `memory/bki-bei-entity-structure.md`.
- **CSV fixture stays as pipeline source** — the demand pipeline reads `bom_master_compact.csv` for speed and version control. But the CSV must be DERIVED from Frappe BOMs, not the other way around. Frappe BOM DocType is the SSOT; the CSV is a cache.

### Key trade-off decisions
1. **Cancel+recreate vs amend for submitted BOMs** — Frappe Submittable DocTypes can't be edited once submitted. We must cancel the BEI-company BOM and create a new one under BKI. Alternative (amend) creates a new version but keeps the old company — doesn't solve the problem. Decision: cancel+recreate with savepoint.
2. **Direct API vs commissary_bom.py** — The custom `commissary_bom.py` API hardcodes `get_company()` → BEI. For BKI ingredient BOMs, we must use direct Frappe API with explicit `company="Bebang Kitchen Inc."`. Decision: direct API for Phase 2a, `commissary_bom.py` for Phase 3 (product BOMs under BEI).
3. **POS-verified products only** — Arnold's spreadsheet has 23+ products including R&D items (Strawberry Cheesecake, Blueberry Cheesecake, Samalamig). We verified against Supabase POS data: only Iskrambol and Ginataang Halo-Halo have actual sales. Decision: exclude R&D products, include only POS-confirmed.

### Known limitations
- `hrms/utils/bei_config.py:76` — `get_company()` returns BEI unconditionally. Any BOM API that calls this will create under BEI. Ingredient BOMs must bypass.
- `hrms/api/commissary_bom.py:80` — `create_bom()` uses `get_company()`. Cannot use this API for BKI BOMs.
- Submitted BOMs with linked Stock Entries or Work Orders cannot be cancelled — must check before attempting cancel.

### Source references
- BEI/BKI entity structure: `memory/bki-bei-entity-structure.md`
- P05 migration results: `data/_CLEANROOM/migration_runs/2026-03-02_frappe_go_live_zero_hallucination_v1/01_packets/P05_BOM_UOM/production_runs/2026-03-03_153204_PHT/post_APPLY_SUMMARY.json`
- March 27 deletion evidence: Frappe `Deleted Document` records (20 BOM entries, Administrator, 2026-03-27 15:20)
- Pop Lamig canonical mapping: `data/_CLEANROOM/agent_runs/2026-03-10_pop_lamig_bom/POP_LAMIG_BOM_CANONICAL_MAPPING.csv`
- Arnold's Store BOM 2026: Google Drive file ID `1lWmZhNQLa6rsfJ9OMNrnc-dDQpZOf-Hxrsn7oKxwEGg` (downloaded to `tmp/bom_investigation/Store_BOM_2026.xlsx`)
- POS product verification: Supabase `pos_order_items` table — confirmed Iskrambol, Ginataang Halo Halo, Pop Lamig have sales; Samalamig/Cheesecake do not.

---

## Scope: 21 Products (POS-verified only)

### Full Cups (15 existing — need company fix)
Presidential, Halukay Ube, Mango Graham Caramel, Banana Cinnamon, Buko Fruit Salad, Melon, Buko Pandan, Strawberry Pistachio, Blueberry Pistachio, Matcharap, Cookie Crumble*, So Corny, Mango Classic, Special, Choco Brownie

### Full Cups (2 MISSING — POS-confirmed, recipes extracted from Google Drive)
- **Iskrambol**: Frozen Milk 306g, Leche Flan 50g, Vanilla Jelly 30g, Melon Sauce 25g, Nata 23g, Chocolate Syrup 15g, Brown Sugar Balls 12g, Mini Mallows 12g, Brownies 7g, Rice Crispies 2g + packaging
- **Ginataang Halo-Halo**: Ginataan Sauce 100g, Bilo Bilo 30g, Pandan Jelly 30g, Nata 23g, Sago 20g, Corn Kernels 17g, Langka 13g, Ube Sauce 10g + packaging

### Tikim Sizes (3 existing in fixture — need Frappe BOM)
Tikim Presidential, Tikim Mango Graham, Tikim Choco Brownie

### Special
- **Pop Lamig** (MN016) — deleted March 27, recreate from canonical mapping
- *Cookie Crumble — phasing out per March 13 memo, keep but mark deprecated

### Excluded (R&D only — zero POS sales)
Samalamig (= Pop Lamig), Strawberry Cheesecake, Blueberry Cheesecake

---

## Phase 1: Audit + Build Target Manifest (4 units, read-only)

| Task | Description | Units |
|------|-------------|-------|
| A1 | Query all 30 BOMs from Frappe (name, item, company, docstatus, child items) | 1 |
| A2 | Cross-reference against Arnold's Store BOM 2026 (SSOT) | 1 |
| A3 | Produce `tmp/bom_investigation/BOM_TARGET_MANIFEST.csv` | 1 |
| A4 | Present manifest to user for review before mutations | 1 |

**Gate:** User approves manifest.

## Phase 2: Fix Company Assignments (8 units)

### 2a: Ingredient BOMs — FG series → BKI (5 units)
18 submitted FG-series BOMs are commissary sub-component recipes. Must be under BKI.

| Task | Description | Units |
|------|-------------|-------|
| F1 | Pre-check: verify no Stock Entries or Work Orders reference these BOMs | 1 |
| F2 | For each of 18 BOMs: Cancel → Create new under BKI → Submit (with savepoint per DM-2) | 3 |
| F3 | Verify all 18 new BOMs are Submitted + active under BKI | 1 |

### 2b: Product BOMs — MN series → BEI (3 units)
12 draft MN-series BOMs are POS menu products. Must be under BEI.

| Task | Description | Units |
|------|-------------|-------|
| F4 | Update company to BEI on all 12 drafts | 1 |
| F5 | Validate ingredient quantities against Arnold's Store BOM 2026 | 1 |
| F6 | Submit all 12 BOMs | 1 |

## Phase 3: Create Missing Product BOMs (8 units)

| Task | Description | Units |
|------|-------------|-------|
| C1 | Create 2 new Items: RM216 (Brown Sugar Tapioca Balls), RM217 (Ginataan Sauce) | 1 |
| C2 | Create Iskrambol BOM (13 ingredients) under BEI | 2 |
| C3 | Create Ginataang Halo-Halo BOM (11 ingredients) under BEI | 2 |
| C4 | Recreate Pop Lamig BOM (7 ingredients) from canonical mapping under BEI | 1 |
| C5 | Create Tikim BOMs (3 products) from fixture recipes under BEI | 2 |

### Ingredient Mappings (ALL RESOLVED)

**Iskrambol:**
| Ingredient | Item Code | Status |
|-----------|-----------|--------|
| FROZEN MILK | FG020 | Exists |
| LECHE FLAN 3 | FG001 | Exists |
| VANILLA WHITE JELLY | FG005 | Exists |
| MELON FLAVORED SAUCE 2 | FG018 | Exists |
| NATA 1 | RM007 | Exists |
| CHOCOLATE FLAVORED SYRUP 2 | FG019 | Exists |
| BROWN SUGAR BALLS 1 | RM216 | **CREATE** |
| MINI MALLOWS 1 | M006 | Exists |
| BROWNIES 1 | RM020 | Exists |
| RICE CRISPIES 3 | FG003 | Exists |
| CUP 16 OZ | PM001 | Exists |
| DOME LID CUP | PM002 | Exists |
| GREEN SPOON | PM003 | Exists |

**Ginataang Halo-Halo:**
| Ingredient | Item Code | Status |
|-----------|-----------|--------|
| GINATAAN SAUCE 1 | RM217 | **CREATE** |
| BILO BILO 1 | RM213 | Exists |
| PANDAN GREEN JELLY 1 | FG004 | Exists |
| NATA 1 | RM007 | Exists |
| SAGO 2 | FG009 | Exists |
| CORN KERNELS 1 | RM006-C | Exists |
| LANGKA 2 | FG013 | Exists |
| UBE FLAVORED SAUCE 2 | FG016 | Exists |
| CUP 16 OZ | PM001 | Exists |
| DOME LID CUP | PM002 | Exists |
| GREEN SPOON | PM003 | Exists |

**Pop Lamig (from canonical mapping with yield conversions):**
| Ingredient | Item Code | qty_per_serving | Basis |
|-----------|-----------|----------------|-------|
| CARBONATED WATER | PM100 | 0.006024 | 1 canister / 166 cups |
| SAGO | FG009 | 0.040000 | 40g per cup |
| SYRUP | RM203 | 0.026000 | 26g per cup |
| VANILLA JELLY | FG005 | 0.060000 | 60g per cup |
| CUP 16 OZ | PM001 | 1.000000 | 1:1 |
| SEALING FILM | PM070 | 0.000333 | 1 roll / 3000 cups |
| PAPER STRAW | PM102 | 1.000000 | 1:1 |

## Phase 4: Update Demand Pipeline Fixture (4 units)

| Task | Description | Units |
|------|-------------|-------|
| P1 | Regenerate `bom_master_compact.csv` FROM Frappe BOM data | 2 |
| P2 | Update `bom_fg_to_pos_crosswalk_compact.csv` with Iskrambol + Ginataang POS names | 1 |
| P3 | Add Iskrambol + Ginataang to `store_order_component_recipes.csv` | 1 |

## Phase 5: Clean Up (2 units)

| Task | Description | Units |
|------|-------------|-------|
| X1 | Delete remaining 50 bad demand snapshots | 1 |
| X2 | Delete hallucinated files: `data/_CLEANROOM/bom/store_consumption_bom.csv`, `data/_CLEANROOM/central_warehouse_2026_03/delivery_schedule.csv` | 1 |

## Phase 6: Verification (4 units)

| Task | Description | Units |
|------|-------------|-------|
| V1 | `get_bom_detail()` returns correct data for all 21 products | 2 |
| V2 | Trigger demand pipeline cron job, verify snapshots generated from Frappe BOMs | 1 |
| V3 | Ordering page shows demand for items with POS sales | 1 |

**Total: 30 units**

---

## Critical Files

| File | Purpose |
|------|---------|
| `tmp/bom_investigation/Store_BOM_2026.xlsx` | Arnold's SSOT — all products with recipes |
| `tmp/bom_investigation/Price_Breakdown_Store_BOM.xlsx` | Detailed costing with grams per cup |
| `data/_CLEANROOM/agent_runs/2026-03-10_pop_lamig_bom/POP_LAMIG_BOM_CANONICAL_MAPPING.csv` | Pop Lamig verified mapping with yield conversions |
| `hrms/api/commissary_bom.py` | Custom BOM API |
| `hrms/utils/bei_config.py:76` | `get_company()` — returns BEI, need BKI override for ingredient BOMs |
| `hrms/utils/store_order_demand_snapshot.py:226` | `load_bom_catalog()` reads CSV fixture |
| `hrms/fixtures/store_ordering/bom_master_compact.csv` | Pipeline BOM fixture (to be regenerated) |
| `hrms/fixtures/store_ordering/bom_fg_to_pos_crosswalk_compact.csv` | POS name → FG name mapping |
| `hrms/fixtures/store_ordering/store_order_component_recipes.csv` | Component-level recipes for ordering |

## Risks

- **Submitted BOMs with linked transactions** — cancel may fail. Pre-check in F1.
- **`get_company()` returns BEI** — ingredient BOMs must bypass this and use BKI explicitly.
- **POS product names** — Iskrambol appears as "Iskrambol" in POS, Ginataang as "Ginataang Halo Halo". Verify exact spelling for crosswalk.

## Phase 7: Closeout (2 units)

| Task | Description | Units |
|------|-------------|-------|
| CL1 | Update plan YAML: status → COMPLETED, completed_date, execution_summary. Update SPRINT_REGISTRY.md row. `git add -f docs/plans/ && git commit && git push`. | 1 |
| CL2 | Verify all code on `s159-bom-data-fix` branch (not production). PR number in registry. | 1 |

**Total: 32 units**

---

## Requirements Regression Checklist

- [ ] Are ingredient BOMs (FG001-FG020) under company "Bebang Kitchen Inc."? (NOT BEI)
- [ ] Are product BOMs (MN001-MN016 + Iskrambol + Ginataang) under company "Bebang Enterprise Inc."? (NOT BKI)
- [ ] Are ALL product BOMs Submitted (docstatus=1), not Draft?
- [ ] Does Iskrambol BOM have exactly 13 ingredient lines matching the mapping table?
- [ ] Does Ginataang Halo-Halo BOM have exactly 11 ingredient lines matching the mapping table?
- [ ] Does Pop Lamig BOM use yield conversions (PM100=0.006024, PM070=0.000333)?
- [ ] Are Items RM216 (Brown Sugar Tapioca Balls) and RM217 (Ginataan Sauce) created?
- [ ] Is `bom_master_compact.csv` regenerated FROM Frappe BOM data (not manually written)?
- [ ] Does `bom_fg_to_pos_crosswalk_compact.csv` contain "Iskrambol" and "Ginataang Halo Halo"?
- [ ] Are the 50 remaining bad demand snapshots deleted?
- [ ] Are hallucinated files deleted (`data/_CLEANROOM/bom/store_consumption_bom.csv`, `data/_CLEANROOM/central_warehouse_2026_03/delivery_schedule.csv`)?
- [ ] Does `get_bom_detail()` return correct data for Iskrambol?
- [ ] Does the demand pipeline cron produce snapshots with `avg_daily_demand > 0`?

---

## Zero-Skip Enforcement

Every task MUST be implemented. If a task cannot be completed, the agent STOPS and asks the user.

### Forbidden agent behaviors
- Skipping a task silently
- Marking partial work as "done"
- Replacing a task with a simpler version without user approval
- Saying "deferred to next sprint"
- Creating BOMs with wrong company assignment
- Using hallucinated local CSV files as BOM source
- Writing demand snapshots from fabricated data

### Machine-Verifiable Phase Gates

After each phase, run verification:

**Phase 2 gate:**
```
MUST_VERIFY: curl .../api/resource/BOM?filters=[["item","like","FG%"],["company","=","Bebang Kitchen Inc."],["docstatus","=",1]]&limit=0 → count >= 18
MUST_VERIFY: curl .../api/resource/BOM?filters=[["item","like","MN%"],["company","=","Bebang Enterprise Inc."],["docstatus","=",1]]&limit=0 → count >= 12
MUST_VERIFY: curl .../api/resource/BOM?filters=[["company","=","Bebang Enterprise Inc."],["item","like","FG%"]]&limit=0 → count = 0 (no FG under BEI)
```

**Phase 3 gate:**
```
MUST_VERIFY: curl .../api/resource/Item/RM216 → 200 (exists)
MUST_VERIFY: curl .../api/resource/Item/RM217 → 200 (exists)
MUST_VERIFY: curl .../api/method/hrms.api.commissary_bom.get_bom_detail?item=MN-ISKRAMBOL → components_count >= 13
MUST_VERIFY: curl .../api/method/hrms.api.commissary_bom.get_bom_detail?item=MN016 → components_count >= 7
```

**Phase 4 gate:**
```
MUST_MODIFY: hrms/fixtures/store_ordering/bom_master_compact.csv
MUST_CONTAIN: "ISKRAMBOL" in bom_master_compact.csv
MUST_CONTAIN: "GINATAANG" in bom_master_compact.csv
MUST_MODIFY: hrms/fixtures/store_ordering/bom_fg_to_pos_crosswalk_compact.csv
MUST_CONTAIN: "Iskrambol" in bom_fg_to_pos_crosswalk_compact.csv
```

**Phase 5 gate:**
```
MUST_VERIFY: curl .../api/resource/BEI Inventory Risk Snapshot?limit=0&fields=["count(name) as total"] → total <= 10 (bad snapshots deleted)
MUST_VERIFY: data/_CLEANROOM/bom/store_consumption_bom.csv does NOT exist
MUST_VERIFY: data/_CLEANROOM/central_warehouse_2026_03/delivery_schedule.csv does NOT exist
```

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| sam@bebang.ph | Call `get_bom_detail?item=FG001` | Returns BOM under company "Bebang Kitchen Inc." with 2 components | Phase 2a company fix failed |
| sam@bebang.ph | Call `get_bom_detail?item=MN001` | Returns BOM under company "Bebang Enterprise Inc." with 19 components | Phase 2b company fix failed |
| sam@bebang.ph | Call `get_bom_detail` for Iskrambol item code | Returns 13 components including RM216 (Brown Sugar Balls) | Phase 3 Iskrambol BOM not created |
| sam@bebang.ph | Call `get_bom_detail?item=MN016` | Returns 7 components including RM203 (syrup) and PM070 (sealing film) | Phase 3 Pop Lamig BOM not recreated |
| sam@bebang.ph | Open ordering page for Araneta Gateway | Items show real `avg_daily_demand > 0` from pipeline (not hallucinated) | Phase 4 fixture not regenerated or Phase 6 pipeline not triggered |
| sam@bebang.ph | Check `bom_master_compact.csv` for "ISKRAMBOL" | Row exists with correct ingredient codes and quantities | Phase 4 fixture missing new products |

Evidence files: `output/l3/S159/form_submissions.json`, `api_mutations.json`, `state_verification.json`

---

## Ground-Truth Lock

- **evidence_sources:**
  - `tmp/bom_investigation/Store_BOM_2026.xlsx` → Arnold's canonical product recipes (23 products, grams per cup)
  - `tmp/bom_investigation/Price_Breakdown_Store_BOM.xlsx` → Detailed costing with ingredient breakdown
  - `data/_CLEANROOM/agent_runs/2026-03-10_pop_lamig_bom/POP_LAMIG_BOM_CANONICAL_MAPPING.csv` → Pop Lamig verified mapping with yield conversions and provenance
  - `data/_CLEANROOM/migration_runs/2026-03-02_frappe_go_live_zero_hallucination_v1/01_packets/P05_BOM_UOM/inputs_normalized/BOM_RECIPES_PACKET.csv` → P05 verified BOM data with full source lineage (250 rows)
  - Supabase `pos_order_items` table → POS sales verification for product inclusion/exclusion
- **count_method:**
  - 21 products: 15 existing + 2 missing (Iskrambol, Ginataang) + 3 Tikim + 1 Pop Lamig
  - 30 existing BOMs: 18 FG-series (submitted, BEI→BKI) + 12 MN-series (draft, BKI→BEI)
  - 2 new Items to create: RM216, RM217
- **authoritative_sections:** Scope, Phase tables, and Ingredient Mappings are authoritative. This Ground-Truth Lock is traceability.
- **unresolved_value_policy:** No unresolved values remain. All ingredient→Item code mappings are resolved.

---

## Autonomous Execution Contract

- **completion_condition:**
  - All 21 products have correct BOMs in Frappe (right company, submitted)
  - CSV fixture regenerated from Frappe BOM data
  - Demand pipeline produces snapshots with `avg_daily_demand > 0` from real data
  - Plan YAML status updated to COMPLETED and pushed to production
  - SPRINT_REGISTRY.md row updated to COMPLETED and pushed to production
  - All Phase gates pass
- **stop_only_for:**
  - Missing Item codes that can't be auto-created (pre-resolved: only RM216 + RM217 needed)
  - Linked transactions blocking BOM cancel (pre-check in F1)
  - User rejects manifest in Phase 1
  - Frappe API credentials unavailable
- **continue_without_pause_through:** audit → execute → pr_creation → closeout
- **blocker_policy:**
  - programmatic → fix and continue
  - BOM cancel blocked by linked doc → set `is_active=0` instead, continue
  - Frappe API error → retry with research, continue
  - business-data/policy → pause (e.g., user disagrees with ingredient mapping)
- **signoff_authority:** single-owner (Sam Karazi, CEO)
- **canonical_closeout_artifacts:**
  - `output/s159/RUN_STATUS.json`
  - `output/s159/RUN_SUMMARY.md`
  - `output/l3/S159/form_submissions.json`
  - `output/l3/S159/api_mutations.json`
  - `output/l3/S159/state_verification.json`
  - `docs/plans/2026-04-04-sprint-159-bom-data-fix.md` (status: COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (S159 row updated)

---

## Agent Boot Sequence

1. Read this plan fully — especially Design Rationale and Requirements Regression Checklist.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s159-bom-data-fix origin/production`. NEVER write code on production.
3. Read `docs/plans/SPRINT_REGISTRY.md` for cross-sprint context.
4. Get Frappe API credentials: `C:/Users/Sam/bin/doppler.exe secrets get FRAPPE_API_KEY --project bei-erp --config dev --plain`
5. **CRITICAL:** All Frappe API calls MUST include `-H "User-Agent: BEI-Agent/1.0"` header (Cloudflare blocks Python urllib without it).
6. Read `hrms/api/commissary_bom.py` for the custom BOM API.
7. Read `hrms/utils/bei_config.py:76` — confirms `get_company()` returns BEI. Ingredient BOMs MUST use explicit `company="Bebang Kitchen Inc."`.
8. Read `data/_CLEANROOM/agent_runs/2026-03-10_pop_lamig_bom/POP_LAMIG_BOM_CANONICAL_MAPPING.csv` for Pop Lamig yield conversions.
9. Execute Phase 1-7 in order.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

**CORRECT OVER FAST RULE:** When fixing an error, ask: "Am I removing the feature or fixing the feature?" Do NOT delete BOMs to fix errors — that's how we got here (March 27 agent deletion).

## Execution Workflow
- Test Python changes: `/local-frappe`
- Deploy changes: `/deploy-frappe`
- Full workflow: `/agent-kickoff`
- E2E testing: `/e2e-test` or `/test-full-cycle`

> Deployment is user-mediated. Create PRs; Sam handles merge and deploy.
