---
canonical_sprint_id: S120
status: GO
branch: s120-item-master-price-sync
depends_on: null
created: 2026-03-25
completed_date: null
execution_summary: null
total_work_units: 42
---

# S120: Item Master Price Sync & Cleanup

## Problem Statement

The procurement workflow is broken because:

1. **252 items have pricing in the Compliance App but `standard_rate=0` in Frappe** — so `get_contracted_price()` returns nothing and POs are created with ₱0.
2. **The `Item Price` table has only 8 records** out of 463 items — it was never populated.
3. **35 items in the Compliance App don't exist in Frappe at all** — users type free-text item codes (e.g., "SAGO") because the PR form doesn't enforce Item master lookup.
4. **63 items are completely stale** — zero stock, no movement in 30 days, not in the Compliance App, never received. These are test items, decommissioned products, and orphans.
5. **The PO detail page has no edit capability** — once a PO is created with ₱0, there's no way to fix the price without database surgery.

**Reported by:** luwi@bebang.ph (PR-2026-03022 → PO-2026-03023, SAGO at ₱0)
**Root cause analysis:** `tmp/item_master_full_analysis.csv` (463 rows with full status)

## Data Sources (Ground Truth)

| Source | ID/Path | Items | Pricing | Freshness |
|--------|---------|-------|---------|-----------|
| Compliance App Item List | Google Sheet `1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q` tab "Item List" | 365 | VAT inc + VAT ex + VAT remarks | Updated by procurement team |
| Compliance App PO Items | Same sheet, tab "PO Items" | 2013 line items, 291 unique items | Unit Cost per PO | Transaction history |
| Compliance App GR Items | Same sheet, tab "GR Items" | 2267 line items, 230 unique items | — | Receiving history |
| SKU Master (local) | `data/Procurement_Database/FORENSIC_EXTRACTION/Copy of Compliance App Database__SKU_Master.csv` | 92 | Cost column | Stale (Sep 2025) |
| Ian's Price List | Google Sheet `1piMVW6nH7l_8lsXFqJ-LBZUbbXhyXgzvJPpLjo3LUNA` tab "ADJUSTED PRICE" | ~400 | Current adjusted prices | Updated daily |
| Frappe Item master | `hq.bebang.ph` Item DocType | 463 | `valuation_rate` (241 have >0), `standard_rate` (all 0) | Live |
| Frappe Item Price | `hq.bebang.ph` Item Price DocType | 8 records | Only test items | Essentially empty |

### Price Resolution Priority (most recent wins)
1. **Compliance App PO Items** — most recent PO unit cost for each item (transaction-based)
2. **Compliance App Item List** — `Unit Price (Vat ex)` (maintained by procurement team)
3. **Frappe `valuation_rate`** — from stock reconciliations (already loaded for 241 items)
4. **Ian's Adjusted Price List** — warehouse-maintained prices

## Scope

### Phase 0: Data Extraction & Analysis (4 units)

**CRITICAL: `tmp/` files are NOT in git.** A cold-start agent must re-extract before proceeding.

| Task | Units | Details |
|------|-------|---------|
| 0.1 Extract Compliance App data from Google Sheets | 2 | Run: `python tmp/s120_extract_compliance_data.py` (committed to repo). This script pulls 4 tabs from Google Sheet `1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q` into CSVs: "Item List" → `tmp/compliance_item_list.csv`, "PO Items" → `tmp/compliance_po_items.csv`, "GR Items" → `tmp/compliance_gr_items.csv`, "Suppliers" → `tmp/compliance_suppliers.csv`. Uses service account `credentials/task-manager-service.json` with `subject='sam@bebang.ph'`. |
| 0.2 Run cross-reference analysis | 1 | Run: `python tmp/item_analysis.py` (committed to repo). Reads the CSVs from 0.1 + Frappe API, produces `tmp/item_master_full_analysis.csv` with columns: item_code, item_name, item_group, frappe_valuation_rate, frappe_standard_rate, compliance_price_vat_inc, compliance_price_vat_ex, compliance_vat_remarks, current_stock, has_30d_movement, in_compliance_app, has_po_history, has_gr_history, status (ACTIVE/DORMANT_BUT_KNOWN/STALE_REMOVE). **Frappe API creds:** Script uses Doppler automatically (`doppler secrets get FRAPPE_API_KEY/FRAPPE_API_SECRET --project bei-erp --config dev`). Frappe URL: `https://hq.bebang.ph`. |
| 0.3 Validate extraction counts | 1 | Compliance Item List should have ~365 items, PO Items ~2013, GR Items ~2267, Frappe Items ~463. If counts differ significantly from these baselines, investigate before proceeding. |

**Gate:** `tmp/item_master_full_analysis.csv` must exist with valid status column before Phase 1.

### Phase 1: Import Missing Items into Frappe (6 units)

**[BUILD]** Create the 35 Compliance App items that don't exist in Frappe.

| Task | Units | Details |
|------|-------|---------|
| 1.1 Extract 35 missing item codes from `tmp/item_master_full_analysis.csv` (status=not in Frappe) | 1 | Map Compliance App fields → Frappe Item fields: item_code, item_name, stock_uom, item_group |
| 1.2 Create Items via Frappe API (`frappe.client.insert`) | 2 | Use `Item` DocType. Set `is_stock_item=1` for raw materials/finished goods, `is_stock_item=0` for services/equipment |
| 1.3 Validate all 35 items exist in Frappe | 1 | Query `frappe.client.get_list` and compare |
| 1.4 Map item_group from Compliance App "Category" to Frappe Item Groups | 2 | Full category mapping: `Raw Material` → `Raw Materials`, `Raw Materials` → `Raw Materials`, `Commissary` → `Finished Goods`, `PER USAGE QTY` → `Consumables`, `Cleaning Supplies` → `Consumables`, `Office Supplies` → `Consumables`, `OFFICE SUPPLIES` → `Consumables`, `KALINISAN` → `Consumables`, `Packaging Materials` → `Packaging Materials`, `Tools & Equipment` → `Fixed Assets`, `TOOLS & EQUIPMENT` → `Fixed Assets`, `Smallwares` → `Consumables`, empty category → `Products`. Create missing Item Groups via API if needed. |

### Phase 2: Bulk Price Import (10 units)

**[BUILD]** Populate `standard_rate` on Items AND create `Item Price` records.

| Task | Units | Details |
|------|-------|---------|
| 2.1 Build price resolution script | 3 | For each item: (1) get most recent PO unit cost from Compliance App PO Items, (2) fall back to Compliance App Item List `Unit Price (Vat ex)`, (3) fall back to Frappe `valuation_rate`. Score by recency. |
| 2.2 Update `standard_rate` on all Items that have a resolved price | 2 | Use `frappe.client.set_value` for each item. Only update if current `standard_rate` is 0. |
| 2.3 Create `Item Price` records (Standard Buying price list) | 3 | For each item with a resolved price, create an `Item Price` record with `buying=1`, `price_list=Standard Buying`, `valid_from=2026-03-25`. This is what `get_contracted_price()` queries. |
| 2.4 Verify price counts | 2 | Query `Item Price` count, verify > 300 records. Spot-check 10 items against Compliance App. |

### Phase 3: Disable Stale Items (4 units)

**[BUILD]** Disable 63 stale items (zero stock, no 30d movement, not in Compliance App).

| Task | Units | Details |
|------|-------|---------|
| 3.1 Review stale list from `tmp/item_master_full_analysis.csv` (status=STALE_REMOVE) | 1 | 63 items: 39 Products, 7 Services, 10 TEST-*, 7 others. Do NOT delete — set `disabled=1` so they don't appear in dropdowns. |
| 3.2 Disable via API | 2 | `frappe.client.set_value(doctype='Item', name=item_code, fieldname='disabled', value=1)` |
| 3.3 Verify disabled items don't appear in PR/PO item selectors | 1 | Test via API query with `disabled=0` filter |

### Phase 4: PR Form — Force Item Master Selection (8 units)

**[BUILD]** The PR creation form must use Item master codes, not free text.

| Task | Units | Details |
|------|-------|---------|
| 4.1 Add item search/autocomplete API endpoint | 3 | `hrms.api.procurement.search_items(query, category)` — returns items from Item master (disabled=0) with name, code, UOM, standard_rate. **HARD BLOCKER:** Must search by item_name AND item_code (user types "SAGO", should find FG009). |
| 4.2 Update PR creation form to use item selector | 3 | Replace free-text item_code input with autocomplete that queries the new endpoint. Show item_name, item_code, UOM, and price. Auto-fill `estimated_unit_cost` from `standard_rate`. |
| 4.3 PR→PO conversion: use resolved price | 2 | Update `convert_to_po()` to use `standard_rate` as fallback when `get_contracted_price()` returns None. The price chain: contracted_rate → standard_rate → valuation_rate → 0 (with warning). |

### Phase 5: PO Inline Price Editing (8 units)

**[BUILD]** Allow editing item prices on Draft and Pending Approval POs.

| Task | Units | Details |
|------|-------|---------|
| 5.1 Add `update_po_item_price` API endpoint | 3 | `hrms.api.procurement.update_po_item_price(po_name, item_name, unit_cost)` — updates unit_cost, recalculates amount and grand_total. Only for Draft/Pending status POs. |
| 5.2 Make PO detail items table editable for Draft POs | 3 | Unit Price cell becomes an inline input when PO status is Draft or Pending Mae Approval. On blur/change, call the update API and refresh totals. |
| 5.3 Add "Return to Draft" button for Pending Approval POs | 2 | When Mae sees a ₱0 PO, she should be able to send it back to Draft (not just Reject). Add `return_to_draft` method on BEI Purchase Order. |

### Phase 6: Closeout (2 units)

| Task | Units | Details |
|------|-------|---------|
| 6.1 Update plan YAML status to COMPLETED, update SPRINT_REGISTRY.md | 1 | `git add -f docs/plans/...` |
| 6.2 Sentry observability for new endpoints | 1 | `set_backend_observability_context()` on `search_items`, `update_po_item_price` |

## Design Rationale (For Cold-Start Agents)

### Why this exists
Luwi creates PRs with free-text item codes ("SAGO") that don't match the Item master (FG009). The Item Price table was never populated (8 records for 463 items), so `get_contracted_price()` always returns None. POs are created with ₱0 and can't be edited. This blocks all procurement operations.

### Why bulk import from Compliance App
The Compliance App (AppSheet) is the **operational procurement system** that BEI has been using since Sep 2025. It has 365 items with pricing, 2013 PO line items with unit costs, and 2267 GR receiving records. This is the richest price data source. The SKU Master CSV (92 items) is a subset and stale.

### Why not delete stale items
Frappe Item records may be referenced by existing Stock Ledger Entries, Material Requests, or Purchase Orders. Deleting them would break referential integrity. Setting `disabled=1` hides them from dropdowns while preserving history.

### Why inline editing on PO detail (not a separate edit page)
The PO detail page is where Mae reviews and approves. If she sees ₱0, she needs to fix it right there — not navigate to a separate edit page, change values, save, navigate back, then approve.

### Price resolution scoring
Most recent PO unit cost wins because it reflects the actual negotiated price paid to the supplier. Compliance App Item List price is second because it's maintained by the procurement team. Frappe `valuation_rate` is third because it's computed from stock movements and may not reflect purchase price.

## Requirements Regression Checklist

- [ ] Are all 35 missing items created in Frappe with correct item_group and UOM?
- [ ] Are Item Price records created for Standard Buying price list?
- [ ] Does `get_contracted_price()` now return a price for common items (SAGO, CRUSHED GRAHAM, etc.)?
- [ ] Are 63 stale items disabled (not deleted)?
- [ ] Does the PR form use Item master autocomplete (no free text)?
- [ ] Does PR creation auto-fill `estimated_unit_cost` from standard_rate?
- [ ] Can PO item prices be edited inline on the detail page for Draft POs?
- [ ] Does the PO submission block ₱0 items? (Already deployed — verify still works)
- [ ] Does every new `@frappe.whitelist()` endpoint call `set_backend_observability_context()`?

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| test.commissary@bebang.ph | Create PR: type "SAGO" in item field → select FG009 from autocomplete → qty=1 | Item auto-fills: FG009, SAGO, KG, price shows | Item search not working |
| test.commissary@bebang.ph | Submit PR for approval | PR status changes to Pending Approval, estimated cost > 0 | Price not auto-filling |
| test.commissary@bebang.ph | Approve PR → Convert to PO with supplier "1T1MI3" | PO created with unit_cost > 0 (from Item Price) | Price resolution chain broken |
| test.commissary@bebang.ph | Open PO detail → click Unit Price cell → change to 500 → tab out | Price updates, total recalculates | Inline editing not working |
| test.commissary@bebang.ph | Submit PO for approval | PO status changes to Pending Mae Approval | Submission validation broken |
| test.commissary@bebang.ph | Search for disabled item (e.g., S084-RM-LIVE-TEST) in PR form | Item should NOT appear in autocomplete | Disabled filter not working |

## Autonomous Execution Contract

- **completion_condition:**
  - Item Price records > 300 (from current 8)
  - 35 missing items created
  - 63 stale items disabled
  - PR form uses Item master autocomplete
  - PO detail page supports inline price editing for Draft POs
  - Plan YAML status updated to COMPLETED and pushed
  - SPRINT_REGISTRY.md updated and pushed
- **stop_only_for:**
  - Missing credentials/access
  - Destructive approval (bulk disable) — proceed after single confirmation
  - Item Group mapping ambiguity — use best match, document in closeout
- **continue_without_pause_through:** audit → execute → pr_creation → deploy → e2e → closeout
- **blocker_policy:**
  - programmatic → fix and continue
  - environment/runtime → debug, research, continue
  - business-data/policy → pause
- **signoff_authority:** single-owner (Sam Karazi)
- **canonical_closeout_artifacts:**
  - `tmp/item_master_full_analysis.csv`
  - `tmp/price_import_results.json`
  - `output/l3/s120/form_submissions.json`
  - `docs/plans/SPRINT_REGISTRY.md`

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s120-item-master-price-sync origin/production`. NEVER write code on production.
3. **Execute Phase 0 first** — extract data from Google Sheets and run `python tmp/item_analysis.py`. The `tmp/` CSVs are NOT in git — you must re-extract them. See Phase 0 tasks for exact Google Sheet IDs, tab names, and API patterns.
4. Read `tmp/item_master_full_analysis.csv` to understand the current state.
5. Read `tmp/compliance_item_list.csv` and `tmp/compliance_po_items.csv` for price data.
6. Start Phase 1 (import missing items) — this unblocks everything else.

### Key Files Already in Repo
- `tmp/item_analysis.py` — the analysis script (reads Compliance CSVs + Frappe API, produces `item_master_full_analysis.csv`)
- `credentials/task-manager-service.json` — Google API service account
- `hrms/api/procurement.py` — backend procurement endpoints (contains `get_contracted_price()`)
- `hrms/hr/doctype/bei_purchase_order/bei_purchase_order.py` — PO DocType (contains `submit_for_approval()`)
- `hrms/hr/doctype/bei_purchase_requisition/bei_purchase_requisition.py` — PR DocType (contains `convert_to_po()`)

### Key Files in bei-tasks Repo (F:\Dropbox\Projects\bei-tasks)
- `app/dashboard/procurement/purchase-orders/[id]/page.tsx` — PO detail page (Phase 5: needs inline price editing)
- `app/dashboard/procurement/purchase-orders/new/page.tsx` — PO creation form (reference for form patterns)
- `app/dashboard/procurement/purchase-requisitions/[id]/page.tsx` — PR detail page (has Convert to PO dialog)
- `app/dashboard/procurement/purchase-requisitions/new/page.tsx` — **PR creation form (Phase 4: replace free-text item_code with autocomplete)**
- `app/api/procurement/[...slug]/route.ts` — procurement API route handler (normalizers, routing table — add new routes here)
- `hooks/use-procurement.ts` — React hooks for procurement data (add new hooks here)

### Scripts Committed for This Sprint
- `tmp/s120_extract_compliance_data.py` — Phase 0 extraction (Google Sheets → CSVs)
- `tmp/item_analysis.py` — Phase 0 analysis (CSVs + Frappe API → `item_master_full_analysis.csv`)
- `tmp/s120_fact_check.py` — Verification script (23 assertions, all PASS)

## Execution Workflow

- Test Python changes: `/local-frappe`
- Deploy changes: `/deploy-frappe`
- Full workflow: `/agent-kickoff`
- E2E testing: `/e2e-test` or `/test-full-cycle`
