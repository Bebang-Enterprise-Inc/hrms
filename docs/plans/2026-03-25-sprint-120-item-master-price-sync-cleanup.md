---
canonical_sprint_id: S120
status: GO
branch: s120-item-master-price-sync
depends_on: null
created: 2026-03-25
completed_date: null
execution_summary: null
total_work_units: 44
---

# S120: Item Master Price Sync & Cleanup

## Problem Statement

The procurement workflow is broken because:

1. **252 items have pricing in the Compliance App but `standard_rate=0` in Frappe** — so `get_contracted_price()` returns nothing and POs are created with ₱0.
2. **The `Item Price` table has only 8 records** out of 463 items — it was never populated.
3. **35 items in the Compliance App don't exist in Frappe at all** — users type free-text item codes (e.g., "SAGO") because the PR form doesn't enforce Item master lookup.
4. **63 items are completely stale** — zero stock, no movement in 30 days, not in the Compliance App, never received. These are test items, decommissioned products, and orphans.
5. **The PO detail page has no edit capability** — once a PO is created with ₱0, there's no way to fix the price without database surgery.

**Reported by:** luwi@bebang.ph (2026-03-25)
**Root cause analysis:** `tmp/item_master_full_analysis.csv` (463 rows with full status)

### Screenshots (Evidence from This Session)
- `F:\Downloads\image (100).png` — Luwi's PO-2026-03023 detail page showing: ₱0.00 grand total, stray "0" values, no edit button, "Approval Status0" display bug
- `F:\Downloads\image (98).png` and `image (99).png` — Jay's warehouse transfer error (separate issue, already fixed)

### What Luwi Experienced (User Story)

1. Luwi (procurement staff) created **PR-2026-03022** for 1 sack of SAGO via my.bebang.ph.
2. She typed "SAGO" as the item code — the PR form accepted it as free text. The real Frappe Item code is `FG009` (SAGO, KG) or `PR024` (SAGO LIBERTY, SACK). Because she typed a non-existent code, no price was resolved → `estimated_unit_cost: 0`.
3. The PR was **approved with ₱0** — no validation blocked it.
4. She converted the PR to **PO-2026-03023** (supplier: 1 To 1 Marketing, Inc.). The conversion called `get_contracted_price("SAGO", "1T1MI3")` which returned `None` (item "SAGO" has no Item Price record, and only 8 Item Price records exist total). Fallback `estimated_unit_cost` was also 0. PO created with **₱0.00 grand total**.
5. The PO was submitted for Mae's approval — the ₱0 validation we added earlier today wasn't deployed yet at that point.
6. Luwi tried to **edit the price on the PO** but there is **no edit button** on the PO detail page. The items table is completely read-only. She is stuck.
7. The PO detail page also shows **stray "0" values** next to "Approval Status" and in the header — caused by Frappe's `docstatus` and `idx` fields leaking into the React render (fix deployed earlier today, but she's seeing a cached version).

### What Luwi Needs After This Sprint

- Type "SAGO" in the PR form → autocomplete shows FG009 (SAGO) and PR024 (SAGO LIBERTY) with prices
- Select the item → price auto-fills from Item Price / standard_rate
- PR→PO conversion carries the price through
- If price is wrong on PO, she can click the Unit Price cell and edit it inline
- PO cannot be submitted for approval with ₱0 items (already deployed, verify it still works)

### Fixes Already Deployed (Earlier Today, Before This Sprint)

These were hotfixes pushed directly to production before this plan was written:

1. **Serial and Batch Bundle error** — `hrms/api/warehouse.py`: stopped passing legacy `batch_no` on stock transfers (commit `46648c015`)
2. **HTML in error messages** — `lib/error-handler.ts`: strip HTML tags from Frappe validation errors, detect insufficient stock pattern (commit `02df85b`)
3. **PO submission blocks ₱0** — `bei_purchase_order.py`: `submit_for_approval()` now validates item prices (commit `84166ac2b`)
4. **Stray 0s in PO/PR responses** — `hrms/api/procurement.py`: strip `docstatus`, `idx`, `owner` etc. from API responses (commit `84166ac2b`)
5. **PR item normalizer** — `route.ts`: added `estimated_unit_cost` to field lookup chain (commit `fc25ca4`)

The executing agent should verify these are still in production before starting. If any were reverted, re-apply them on the sprint branch.

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

### Phase 5: PO Price Edit with Approval Gate (10 units)

**[BUILD]** Allow editing item prices on POs with mandatory reason + CPO approval trigger.

**LOCKED POLICY (Sam Karazi, 2026-03-25):** Price fields are NOT free-text inputs. They display the auto-filled price as read-only. To change, user clicks an "Edit Price" button which reveals the input + mandatory reason field. Any price edit triggers Mae's approval regardless of PO amount. See `memory/procurement-data-policy.md`.

| Task | Units | Details |
|------|-------|---------|
| 5.1 Add `update_po_item_price` API endpoint | 3 | `hrms.api.procurement.update_po_item_price(po_name, item_idx, new_price, reason)` — updates unit_cost, recalculates amount and grand_total. Requires `reason` (non-empty string). Logs price change with old_price, new_price, reason, changed_by, timestamp. Sets `price_override=1` flag on the PO which forces Mae's approval regardless of amount threshold. Only for non-final status POs (NOT Approved/Sent/Received/Cancelled). Sentry instrumented. |
| 5.2 PO detail price display — read-only with Edit button | 3 | Unit Price cell shows the price as **read-only text** (not an input). Next to it, a small pencil icon / "Edit" label. Clicking it: (1) replaces the read-only text with an editable input pre-filled with current price, (2) shows a "Reason for price change" text field below (mandatory), (3) shows Save/Cancel buttons. On Save → calls `update_po_item_price` API → refreshes totals → collapses back to read-only. **HARD BLOCKER:** Price must NEVER be a plain editable text field. The edit interaction must be deliberate (click to reveal). |
| 5.3 Add "Return to Draft" button for Pending Approval POs | 2 | When Mae sees a ₱0 PO, she should be able to send it back to Draft (not just Reject). Add `return_to_draft` method on BEI Purchase Order. |
| 5.4 Price change visible in approval view | 2 | When Mae reviews a PO that has `price_override=1`, show a banner: "Price was changed by [user] — [old] → [new]. Reason: [text]". She can see exactly what was changed and why before approving. |

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

### CRITICAL NOTES FROM PROCUREMENT DEEP-DIVE (2026-03-25 session)

**Note 1: S104 Contracted Price Master already exists — don't duplicate.**
Sprint S104 (completed 2026-03-24) built a `BEI Contracted Price` DocType with 92 item prices and CPO price-change approval. The `get_contracted_price()` function queries BEI Contracted Price FIRST, then falls back to Frappe's standard `Item Price`. This sprint (S120) populates `Item Price` records — that's correct (it fills the fallback layer). Do NOT touch `BEI Contracted Price` data. The two systems work together:
- `BEI Contracted Price` = CPO-approved negotiated prices (92 items, requires Mae's approval to change)
- `Item Price` (Standard Buying) = bulk reference prices from Compliance App history (252+ items)
- Resolution order: `BEI Contracted Price` → `Item Price` → `standard_rate` → `valuation_rate` → 0

**Note 2: After import, Frappe becomes the price SSOT — stop syncing prices from Compliance App.**
The sheets-receiver currently syncs Compliance App data daily (PO Items, GR Items, Suppliers). After this sprint imports prices into Frappe, the price source of truth moves FROM the Compliance App TO Frappe. Future POs created in my.bebang.ph will have correct prices from Item Price records. The Compliance App sync should continue for historical/audit data but should NOT overwrite Frappe Item Prices. Verify that `sync_procurement_purchase_orders` does not touch `Item Price` or `standard_rate` — if it does, add a guard.

**Note 3: 80% of POs are exact duplicates (same supplier + same items).**
Data analysis of 561 POs from the Compliance App shows 455 (80%) are exact duplicates of prior POs. The top repeat: MATHEW GENERAL MERCHANDISE with the same 30 items ordered 20 times. This means the Item Price import has outsized impact — fixing prices for the top 50 items by frequency covers ~90% of all PO line items. Sprint S122 will add PO Templates/Reorder to eliminate the repetitive form-filling.

**Note 4: PO approval flow has an extra step the system doesn't implement yet.**
The real AppSheet approval matrix shows Luwi REVIEWS POs before Mae approves. The current system skips Luwi's review. S120's inline editing should allow edits during both "Draft" AND future "Pending Review" status (S123 will add the review step). When adding the status check for inline editing, use `status NOT IN ("Approved", "Sent to Supplier", "Fully Received", "Cancelled")` rather than `status IN ("Draft", "Pending Mae Approval")` — this future-proofs for new statuses.

**Note 5: Hardcode validations to prevent recurring data quality issues.**
The root cause of Luwi's bug is that the system ALLOWED bad data in at every step. This sprint must add validation gates that make it IMPOSSIBLE to create bad procurement data:
1. **PR creation:** item_code MUST exist in Item master (no free text) — Phase 4 handles this
2. **PR creation:** estimated_unit_cost MUST be > 0 when item has a known price — add validation
3. **PO creation/conversion:** unit_cost MUST be > 0 — already deployed, verify
4. **PO submission:** grand_total MUST be > 0 — already deployed, verify
5. **Item Price record:** MUST have valid_from date and price_list — Phase 2 handles this
6. **Future-proof:** Add a scheduled job that scans for Items with `standard_rate=0` and `disabled=0` and alerts procurement team weekly — prevents new items from being created without prices

## Requirements Regression Checklist

- [ ] Are all 35 missing items created in Frappe with correct item_group and UOM?
- [ ] Are Item Price records created for Standard Buying price list?
- [ ] Does `get_contracted_price()` now return a price for common items (SAGO, CRUSHED GRAHAM, etc.)?
- [ ] Are 63 stale items disabled (not deleted)?
- [ ] Does the PR form use Item master autocomplete (no free text)?
- [ ] Does PR creation auto-fill `estimated_unit_cost` from standard_rate?
- [ ] Is the PO price field READ-ONLY by default (not a plain editable input)?
- [ ] Does clicking "Edit Price" reveal an input + mandatory reason field?
- [ ] Does price edit trigger Mae's approval regardless of PO amount?
- [ ] Is the price change (old→new + reason) visible in Mae's approval view?
- [ ] Does the PO submission block ₱0 items? (Already deployed — verify still works)
- [ ] Does PR creation block items that don't exist in Item master? (No free text allowed)
- [ ] Does PR creation warn when estimated_unit_cost is 0 for an item that has a known price?
- [ ] Does `get_contracted_price()` check BEI Contracted Price FIRST, then Item Price? (Don't break S104)
- [ ] Does the sheets-receiver sync NOT overwrite Item Price or standard_rate? (Frappe is now SSOT for prices)
- [ ] Does inline PO editing use a permissive status check (not hardcoded to Draft only) to future-proof for Pending Review?
- [ ] Does every new `@frappe.whitelist()` endpoint call `set_backend_observability_context()`?

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| test.commissary@bebang.ph | Create PR: type "SAGO" in item field → select FG009 from autocomplete → qty=1 | Item auto-fills: FG009, SAGO, KG, price shows | Item search not working |
| test.commissary@bebang.ph | Submit PR for approval | PR status changes to Pending Approval, estimated cost > 0 | Price not auto-filling |
| test.commissary@bebang.ph | Approve PR → Convert to PO with supplier "1T1MI3" | PO created with unit_cost > 0 (from Item Price) | Price resolution chain broken |
| test.commissary@bebang.ph | Open PO detail → verify price is read-only text (NOT editable input) | Price shows as text, not input field | Price field is free-text (policy violation) |
| test.commissary@bebang.ph | Click "Edit Price" pencil icon → input appears + reason field | Price input + "Reason for price change" text field shown | Edit interaction missing |
| test.commissary@bebang.ph | Enter new price 500, reason "Supplier increased rate" → Save | Price updates, total recalculates, reason saved | Update API broken |
| mae@bebang.ph | Open PO with price override → see price change banner | Shows "Price changed by [user]: ₱84 → ₱500. Reason: Supplier increased rate" | Approval view missing change context |
| test.commissary@bebang.ph | Submit PO for approval | PO status changes to Pending Mae Approval | Submission validation broken |
| test.commissary@bebang.ph | Search for disabled item (e.g., S084-RM-LIVE-TEST) in PR form | Item should NOT appear in autocomplete | Disabled filter not working |

## Autonomous Execution Contract

- **completion_condition:**
  - Item Price records > 300 (from current 8)
  - 35 missing items created
  - 63 stale items disabled
  - PR form uses Item master autocomplete
  - PO detail page supports read-only price with Edit Price button + reason field
  - Sentry observability on all new `@frappe.whitelist()` endpoints
  - L3 evidence files committed: `git add -f output/l3/s120/ && git push`
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
  - `output/l3/s120/api_mutations.json`
  - `output/l3/s120/state_verification.json`
  - `docs/plans/SPRINT_REGISTRY.md`

Evidence files required before closeout (release manager gate will reject PR without these):
```
output/l3/s120/form_submissions.json
output/l3/s120/api_mutations.json
output/l3/s120/state_verification.json
```
Agent MUST `git add -f output/l3/s120/ && git push` after L3 testing.

## Remote-Truth Baseline

| Repo | Branch | HEAD SHA |
|------|--------|---------|
| hrms | production | `d94f1fdc6` |
| bei-tasks | main | (check with `git log --oneline -1` in bei-tasks) |

## Known Limitations

- Google Sheets API rate limit: 60 reads/min per user. Phase 0 extraction may need delays between tabs.
- Frappe API throttling: bulk `set_value` calls may hit rate limits during Phase 2 (252 items). Use 200ms delay between calls.
- `tmp/` files are NOT in git — cold-start agent must re-extract (Phase 0) before proceeding.
- The PR creation form is in `bei-tasks` repo (separate from `hrms`). Phase 4-5 require changes in BOTH repos — two PRs needed.
- Compliance App Google Sheet may be edited by procurement team during extraction — snapshot timing matters.

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
