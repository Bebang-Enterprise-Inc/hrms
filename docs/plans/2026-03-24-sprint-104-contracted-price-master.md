---
canonical_sprint_id: S104
display: Sprint 104
status: DEPLOYED
branch: s104-contracted-price-master
lane: single
created_date: 2026-03-24
deployed_at: 2026-03-24
backend_pr: 330
completed_date:
execution_summary: PR #330 created. 3 new DocTypes, 8 new endpoints, migration patch. Awaiting governor merge + L3.
depends_on: S099
---

# S104 — Contracted Price Master & Procurement Price Integrity

**Goal:** Make every item price in the procurement workflow come from a verified, contracted price list — not from whatever the last PO happened to say. Prevent price manipulation by grounding all prices in a controlled, auditable source of truth.

**Origin:** S099 L3 review (2026-03-24). Sam flagged that `get_item_last_price()` auto-fills from previous PO history, which is vulnerable to manipulation — if someone creates a PO with a wrong price, that wrong price becomes the default for all future POs.

**Evidence files:**
- `data/Procurement_Database/FORENSIC_EXTRACTION/Copy of Compliance App Database__SKU_Master.csv` — 92 items with negotiated costs
- Frappe has 462 Items, 681 POs, but ZERO Item Prices and ZERO Price Lists

---

## Design Rationale (For Cold-Start Agents)

### Why this exists
The procurement team is testing the ERP and entering purchase orders. Currently:
- **No contracted price list exists in Frappe.** The SKU Master with 92 negotiated costs lives in an AppSheet workbook CSV, not in Frappe.
- **S099's `get_item_last_price()` looks up the last PO price** — this is dangerous because a single bad PO poisons all future price lookups.
- **The price variance check (10%) compares against PO history too** — so if prices drift gradually through bad POs, the system adapts to the drift instead of catching it.
- **The team needs a single place to update prices** when suppliers renegotiate — not scattered across 681 POs.

### Why this architecture
- **Frappe Item Price is the right tool.** It's built-in, supports per-supplier pricing, has a `Price List` concept, handles currency, and integrates with Purchase Order creation. We don't need to invent anything.
- **"Standard Buying" price list** — Frappe's convention for purchase prices. One price list, many items, optional per-supplier overrides.
- **Contracted price = source of truth.** PO history becomes reference-only context ("last PO was P80.24") shown as a hint, not the default value.
- **Price variance check should compare against contracted price**, not PO history average. A 10% deviation from the contracted rate is meaningful. A 10% deviation from an average of potentially wrong POs is noise.

### Key trade-offs
- **Import all 92 SKU Master items vs. only items with active suppliers:** Import all 92. The SKU Master is the canonical item list. Items without suppliers still need a base cost for budgeting.
- **Per-supplier pricing vs. single price per item:** Start with single price per item (from SKU Master). Add per-supplier overrides as Phase 2 when the team has negotiated supplier-specific rates. Frappe Item Price supports both.
- **Auto-fill contracted price vs. show as reference:** Auto-fill the contracted price into the PO item cost field. Show PO history as a secondary reference label. The contracted price is the trusted source — the user should have to override it, not enter it from scratch.
- **Allow price override vs. hard block:** Allow override with a mandatory reason field (same pattern as existing price variance override). The contracted price is the default, but procurement needs flexibility for spot buys, promotions, and emergency purchases.

### Key trade-off: Block auto-create of items
Currently, `_get_or_create_item()` in `bei_purchase_order.py` silently creates a Frappe Item when a PO references an item code that doesn't exist. This is dangerous — anyone can introduce new items into the system with no approval, no contracted price, and no validation. This sprint blocks that behavior and replaces it with a formal New Item Request workflow requiring CPO approval with a contracted price and supporting documentation. The 462 existing items in Frappe remain usable. Only NEW items going forward require the onboarding flow.

### Known limitations
- The SKU Master CSV has 92 items. Frappe has 462 items. The remaining ~370 items don't have contracted prices yet. For those, the system falls back to no auto-fill (user enters manually). The price variance check uses PO history average as fallback.
- Per-supplier pricing (different prices from different suppliers for the same item) is not in this sprint. The SKU Master doesn't have supplier-level pricing.
- The SKU Master CSV may have stale prices. The team needs to verify/update them after import.
- The 462 existing items were NOT created through the approval workflow. They are grandfathered in. The onboarding gate only applies to new items going forward.

---

## Scope

### Phase A: Frappe Price List + Item Price Setup (8 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| A1 | BUILD | Migration script | Create "Standard Buying" Price List in Frappe (`buying=1, selling=0, enabled=1, currency=PHP`). | 1 |
| A2 | BUILD | Migration script | Import 92 items from SKU Master CSV into Frappe Item Price. Map: `item_code` -> Item Price `item_code`, `Cost` -> `price_list_rate`, `UOM` -> `uom`, price_list="Standard Buying". Validate each item_code exists in Frappe Item master before inserting. Log skipped items. | 4 |
| A3 | BUILD | `procurement.py` | Create `get_contracted_price(item_code, supplier=None)` endpoint. Priority: (1) Supplier-specific Item Price, (2) Standard Buying Item Price, (3) None. Returns `contracted_rate`, `price_list`, `last_updated`. | 2 |
| A4 | FIX | `procurement.py` | Update `get_item_last_price()` to also return `contracted_price` from the new endpoint. **HARD BLOCKER (AUDIT-5):** Keep backward-compatible response — include BOTH `last_price` (alias for `last_po_price`) AND `contracted_price`. Do NOT rename or remove `last_price` — the S099 frontend reads it. Response: `{last_price, contracted_price, last_po_price, avg_90d_price, source}`. | 1 |

### Phase B: Wire Contracted Price Into PO Creation (8 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| B1 | FIX | `procurement.py` + `bei_purchase_requisition.py` | In `_normalize_purchase_order_payload()`, look up contracted price for each item BEFORE the totals calculation loop. If contracted price exists and item has no `unit_cost` or `unit_cost=0`, inject contracted price. **HARD BLOCKER (AUDIT-1):** Also fix `convert_to_po()` in `bei_purchase_requisition.py:144` — it copies `estimated_unit_cost` directly. Must look up contracted price and use it if available (overriding the PR estimate). | 4 |
| B2 | FIX | `bei_purchase_order.py` | In `check_price_variance_blocks()`, compare item `unit_cost` against **contracted price** (not PO history average). If no contracted price exists for the item, fall back to PO history average (current behavior). This means the 10% variance check is against the negotiated rate, not against potentially drifted PO history. | 3 |
| B3 | FIX | `bei-tasks/.../purchase-requisitions/new/page.tsx` | Change auto-price behavior: (1) On item select/blur, call `get_item_last_price` which now returns both contracted and PO prices. (2) Auto-fill the `estimated_rate` field (NOT `unit_cost` — **AUDIT-2: the PR form field is `estimated_rate`**) with `contracted_price` if available. (3) Show PO history as a reference label: "(last PO: P80.24)" below the field. (4) If no contracted price, leave blank for manual entry — do NOT auto-fill from PO history. | 2 |

### Phase C: Price Change Approval Workflow (10 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| C0 | BUILD | `bei_price_change_log.json` | **New DocType: BEI Price Change Log** (child-table-style, standalone). Fields: `item_code` (Link->Item), `before_price` (Currency), `after_price` (Currency), `change_type` (Select: Initial Price/Price Update/Supplier Renegotiation), `reason` (Small Text), `supporting_document` (Attach), `approved_by` (Link->User), `approved_date` (Datetime), `price_change_request` (Link->BEI Price Change Request, optional). **AUDIT-3 fix: This DocType was referenced but never defined.** | 2 |
| C1 | BUILD | `bei_price_change_request.json` | **New DocType: BEI Price Change Request.** Fields: `item_code` (Link->Item), `current_price` (Currency, read-only), `requested_price` (Currency, reqd), `reason` (Small Text, reqd), `supporting_document` (Attach — supplier quote, renegotiation memo, or market evidence), `requested_by` (Link->User, read-only, auto-set), `status` (Select: Draft/Pending CPO Approval/Approved/Rejected, default Draft), `approved_by` (Link->User, read-only), `approved_date` (Datetime, read-only), `rejection_reason` (Small Text). **HARD BLOCKER:** Price changes without CPO approval and written documentation are forbidden. | 4 |
| C2 | BUILD | `bei_price_change_request.py` | Controller: on submit, set status to "Pending CPO Approval" and notify Mae. `approve()` method checks `frappe.session.user == cpo_approver_email` (from BEI Settings), then **CREATES A NEW Item Price record** with `price_list_rate=requested_price`, `valid_from=today`, `valid_upto=today+price_validity_days`. The OLD Item Price record is expired by setting its `valid_upto=yesterday`. **AUDIT-4 fix: Do NOT overwrite — version prices so history is preserved.** Also creates a `BEI Price Change Log` entry. `reject()` requires reason. | 3 |
| C3 | BUILD | `procurement.py` | Create `request_price_change(item_code, new_price, reason, document)` endpoint. Creates a BEI Price Change Request. Only users with "Purchase Manager" or "System Manager" role can call. Sentry instrumented. | 2 |
| C4 | BUILD | `procurement.py` | Create `approve_price_change(name, comment)` and `reject_price_change(name, reason)` endpoints. Approval checks identity against `cpo_approver_email` from BEI Settings. | 1 |

### Phase D: Price Override Audit Trail on POs (6 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| D1 | BUILD | `bei_po_item.json` | Add `contracted_unit_cost` (read-only Currency) and `price_override_reason` (Small Text, mandatory when unit_cost != contracted_unit_cost, **`allow_on_submit=1`** — AUDIT-6 fix so override reasons can be recorded even after PO submission) to BEI PO Item. When PO is created, stamp `contracted_unit_cost` from Item Price lookup. | 3 |
| D2 | FIX | `procurement.py` | In `create_purchase_order()`, after normalization, for each item: look up contracted price, set `contracted_unit_cost`. If `unit_cost != contracted_unit_cost` and no `price_override_reason`, throw validation error: "Price differs from contracted rate (P{contracted}). Please provide an override reason." | 2 |
| D3 | FIX | Sentry | Add `set_backend_observability_context()` to all new endpoints: `get_contracted_price`, `request_price_change`, `approve_price_change`, `reject_price_change`. | 1 |

### Phase E: Item Price Validity + Effective Dates (4 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| E1 | FIX | Migration script | When importing Item Prices in A2, set `valid_from=today`, `valid_upto=today+90 days`. Add `price_validity_days` field to BEI Settings (default 90). | 2 |
| E2 | FIX | `procurement.py` | In `get_contracted_price()`, filter Item Price by `valid_from <= today AND (valid_upto IS NULL OR valid_upto >= today)`. Expired prices should NOT be returned — they force the user to enter manually and trigger a price change request. | 2 |

### Phase F: Item Onboarding Control (12 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| F1 | BUILD | `bei_item_request.json` | **New DocType: BEI Item Request.** Fields: `item_code` (Data, reqd), `item_name` (Data, reqd), `item_group` (Select: Raw Material/Finished Goods/Packaging Material/Consumables/Supplies, reqd), `stock_uom` (Link->UOM, reqd), `description` (Small Text), `contracted_unit_cost` (Currency, reqd — first price must be set at onboarding), `cost_justification` (Small Text, reqd — supplier quote reference or market evidence), `supporting_document` (Attach, reqd — supplier price list, quote, or contract), `supplier` (Link->BEI Supplier — which supplier provides this item), `requested_by` (Link->User, read-only, auto-set), `status` (Select: Draft/Pending CPO Approval/Approved/Rejected, default Draft), `approved_by` (Link->User, read-only), `approved_date` (Datetime, read-only), `rejection_reason` (Small Text). **HARD BLOCKER:** New items without CPO approval and a contracted price are forbidden in POs. | 4 |
| F2 | BUILD | `bei_item_request.py` | Controller: on submit, set status to "Pending CPO Approval" and notify Mae. `approve()` method checks `frappe.session.user == cpo_approver_email`, then: (1) creates Frappe Item with the approved item_code, item_name, item_group, stock_uom, is_stock_item=1, is_purchase_item=1; (2) creates Item Price in "Standard Buying" with `contracted_unit_cost` as the rate, valid_from=today, valid_upto=today+`price_validity_days`; (3) creates BEI Price Change Log entry as "Initial Price". `reject()` requires reason. | 4 |
| F3 | BUILD | `procurement.py` | Create `request_new_item(data)` and `approve_item_request(name)` / `reject_item_request(name, reason)` endpoints. CPO identity check on approval. Sentry instrumented. | 2 |
| F4 | FIX | `bei_purchase_order.py` + `erp_sync.py` | **Block auto-create for NEW items only.** In `_get_or_create_item()`, if the item doesn't exist in Frappe, throw: "Item {code} does not exist. Submit a New Item Request for CPO approval before adding it to a PO." **AUDIT-2 fix:** The existing 462 items are grandfathered — this only blocks truly new item codes that don't exist yet. **AUDIT-4 fix:** Also update `erp_sync.py` to use `price_override_reason` instead of `price_variance_override` for its legacy bypass field, so the field name matches the new validation in D2. | 3 |

### Phase G: Verification + Closeout (7 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| G1 | VERIFY | Production | Verify: create PO for item with contracted price -> cost auto-fills -> matches SKU Master -> price variance checks against contracted rate. | 1 |
| G2 | VERIFY | Production | Verify: create PO with different price than contracted -> system requires override reason -> override reason saved on PO item. | 1 |
| G3 | VERIFY | Production | Verify: submit price change request -> Mae approves -> Item Price updated -> next PO uses new price. | 1 |
| G4 | VERIFY | Production | Verify: non-Mae user tries to approve price change -> rejected with "Only CPO can approve". | 1 |
| G5 | VERIFY | Production | Verify: create PO with non-existent item code -> system blocks with "Submit a New Item Request" message (no auto-create). | 1 |
| G6 | VERIFY | Production | Verify: submit new item request with price + document -> Mae approves -> Item created in Frappe + Item Price created -> PO can now use the item with approved price. | 1 |
| G7 | BUILD | Closeout | Update plan status, sprint registry, commit evidence. | 1 |

**Total: 57 work units across 7 phases.**

> **Scope history:** Started at 27 units (4 phases). First audit added price change approval (+14 → 41 units, 6 phases). CEO feedback added item onboarding control (+12 → 53 units, 7 phases). Second audit (2 parallel agents, code-verified) found 7 CRITICAL gaps: PR-to-PO bypass, missing Price Change Log DocType, price overwrite instead of version, erp_sync field mismatch, API response shape break, allow_on_submit missing, field name mismatch. Amendments added +4 → 57 units. Still within single-session ceiling (< 80).

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| test.procurement@bebang.ph | Create PO for item RM001 (Crushed Graham, contracted P188.16) with no explicit price | PO item unit_cost auto-filled with P188.16, contracted_unit_cost=P188.16, no override required | A3/B1 contracted price lookup failed |
| test.procurement@bebang.ph | Create PO for item RM001 with unit_cost=P200.00 (above contracted) | System requires price_override_reason. Enter "Supplier price increase pending contract update". PO saves. | D2 validation not working |
| test.procurement@bebang.ph | Create PO for item RM001 with unit_cost=P200.00 and NO override reason | System rejects: "Price differs from contracted rate (P188.16)" | D2 validation bypassed |
| test.procurement@bebang.ph | Create PO for item with no contracted price (e.g., TEST-SAGO) | unit_cost field is blank, no contracted_unit_cost, no override required | B1 fallback broken |
| test.procurement@bebang.ph | Create PO for RM001 at P210 (>10% above P188.16 contracted) | Price variance block fires: "exceeds 10% variance from contracted rate" | B2 variance check still using PO history |
| test.hr@bebang.ph | Call get_contracted_price for RM001 | Returns contracted_rate=188.16, price_list="Standard Buying" | A3 endpoint broken |
| test.procurement@bebang.ph | Submit price change request: RM001 from P188.16 to P195.00, reason="Q2 supplier increase", attach supplier quote | Request created with status "Pending CPO Approval", Mae notified | C1/C3 price change request broken |
| test.procurement@bebang.ph | Try to approve price change request (wrong user) | Rejected: "Only mae@bebang.ph can approve price changes" | C2 identity check missing |
| mae@bebang.ph (or simulated) | Approve price change request for RM001 | Item Price updated to P195.00, BEI Price Change Log created with before=188.16/after=195.00/approver/date/reason | C2 approval flow broken |
| test.procurement@bebang.ph | Create PO for RM001 after price change approved | PO auto-fills with new contracted price P195.00 | E2 expired price still returned |
| test.procurement@bebang.ph | Create PO with item code "NEW-ITEM-001" that doesn't exist in Frappe | System rejects: "Item NEW-ITEM-001 does not exist. Submit a New Item Request." (no silent auto-create) | F4 auto-create block not working |
| test.procurement@bebang.ph | Submit new item request: code=NEW-ITEM-001, name="Test New Item", group=Raw Material, UOM=Kg, cost=P150, attach supplier quote | Request created with "Pending CPO Approval" | F1/F3 item request broken |
| test.procurement@bebang.ph | Try to approve item request (wrong user) | Rejected: "Only CPO can approve new items" | F2 identity check missing |
| mae@bebang.ph (or simulated) | Approve item request for NEW-ITEM-001 | Frappe Item created + Item Price P150 in Standard Buying + Price Change Log "Initial Price" | F2 approval flow broken |
| test.procurement@bebang.ph | Create PO for NEW-ITEM-001 after approval | PO auto-fills with contracted price P150.00, item exists in Frappe | Full onboarding flow broken |

Evidence files required before closeout:
```
output/l3/S104/form_submissions.json
output/l3/S104/api_mutations.json
output/l3/S104/state_verification.json
```

---

## Requirements Regression Checklist

- [ ] Does PO creation auto-fill unit_cost from contracted price (Item Price), not PO history?
- [ ] Does the PR form show contracted price as the default, with PO history as reference-only label?
- [ ] Does the PR form leave the price field blank (not auto-fill from PO history) when no contracted price exists?
- [ ] Does price variance check compare against contracted price, not PO history average?
- [ ] Does price variance fall back to PO history average when no contracted price exists?
- [ ] Is price_override_reason mandatory when unit_cost differs from contracted_unit_cost?
- [ ] Is contracted_unit_cost stamped as read-only on every PO item at creation time?
- [ ] Were all 92 SKU Master items imported into Frappe Item Price with valid_from and valid_upto?
- [ ] Does the "Standard Buying" price list exist with buying=1, PHP currency?
- [ ] Does get_contracted_price() check supplier-specific price first, then Standard Buying?
- [ ] Does get_contracted_price() filter by valid_from/valid_upto (no expired prices)?
- [ ] Can ONLY mae@bebang.ph (CPO from BEI Settings) approve price change requests?
- [ ] Does every price change request require a reason AND supporting document (attach)?
- [ ] Does price change approval update the actual Item Price record?
- [ ] Is a BEI Price Change Log entry created on every approval with before/after/approver/date/reason?
- [ ] Can a non-CPO user approve a price change? (Must be NO)
- [ ] Is _get_or_create_item() blocked from silently creating Items? (Must throw for NEW codes, allow EXISTING 462 items)
- [ ] Does new item request require item_code, name, group, UOM, contracted price, justification, and supporting document?
- [ ] Can ONLY CPO approve new item requests?
- [ ] Does item request approval create both the Frappe Item AND the Item Price in one step?
- [ ] Does item request approval create a Price Change Log entry with "Initial Price"?
- [ ] Can a PO reference an item that was never approved through the onboarding flow? (Must be NO for new items)
- [ ] Does every new @frappe.whitelist() call set_backend_observability_context()?
- [ ] Does `convert_to_po()` in bei_purchase_requisition.py look up contracted price (not just copy estimated_unit_cost)?
- [ ] Does the PR form auto-fill `estimated_unit_cost` (not `unit_cost`) with contracted price?
- [ ] Does `BEI Price Change Log` DocType exist with before_price, after_price, approver, date, reason, document fields?
- [ ] Does price change approval CREATE a new Item Price record (with valid_from=today) instead of overwriting the old one?
- [ ] Does `_get_or_create_item()` allow existing 462 items but block truly new item codes?
- [ ] Does `get_item_last_price()` keep backward-compatible response shape (include both `last_price` and `last_po_price`)?
- [ ] Is `price_override_reason` on BEI PO Item set with `allow_on_submit=1`?
- [ ] Does `erp_sync.py` use the same field name (`price_override_reason`) for its legacy bypass?

---

## Autonomous Execution Contract

- completion_condition:
  - All 4 phases complete
  - All L3 scenarios pass
  - 92 items imported into Frappe Item Price
  - Plan YAML status updated to COMPLETED
  - SPRINT_REGISTRY.md updated
  - All evidence files present in output/l3/S104/
- stop_only_for:
  - Missing credentials/access
  - SKU Master item codes don't match Frappe Item codes (data quality issue)
  - Business-policy decision on price override rules
- continue_without_pause_through:
  - code -> test -> PR creation -> governor review -> deploy -> L2-L4 -> closeout
- blocker_policy:
  - programmatic -> fix and continue
  - data mismatch (SKU codes vs Frappe items) -> log mismatches, import what matches, continue
  - business-data/policy -> pause
- signoff_authority: single-owner (Sam)

---

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s104-contracted-price-master origin/production`. NEVER write code on production.
3. Read `data/Procurement_Database/FORENSIC_EXTRACTION/Copy of Compliance App Database__SKU_Master.csv` for the 92 items to import.
4. Read `hrms/api/procurement.py` — find `get_item_last_price()` and `_normalize_purchase_order_payload()`.
5. Read `hrms/hr/doctype/bei_purchase_order/bei_purchase_order.py` — find `check_price_variance_blocks()`.
6. Read `.claude/rules/sentry-observability.md` for Sentry pattern.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

## Execution Workflow
- Test Python changes: `/local-frappe`
- Deploy changes: `/deploy-frappe`
- Full workflow: `/agent-kickoff`
- E2E testing: `/e2e-test` or `/test-full-cycle`
