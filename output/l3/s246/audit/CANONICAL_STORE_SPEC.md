# Canonical Store Master-Data Spec (S246 Phase 1A)

**Status:** v1.0
**Date:** 2026-05-11
**Scope:** EVERY field that must be set on Company / Warehouse / Customer / Supplier / Account for a BEI store to be operationally complete in Frappe ERPNext.
**Why this exists:** the 2026-05-11 L3 sweep (PR #745) found that 0 of 49 stores produce the canonical dual-entry. Root cause: there was no written master-data checklist. Each sprint fixed a slice; new gaps surfaced each time. This spec is that checklist.
**Binding:** the extended `scripts/verify_canonical_structure.py` (v2 mode, S246 Phase 1A.4) asserts every REQUIRED field across all 49 stores.

---

## Spec organization

Three categories:
- **REQUIRED** — store breaks something measurable if missing. Verifier fails on missing REQUIRED.
- **RECOMMENDED** — store works but a UX/ops gap exists. Verifier WARNs on missing RECOMMENDED.
- **DEFAULTED** — ERPNext auto-creates; no manual action needed. Verifier reports presence only.

---

## 1. Per-store Company

The billing + P&L entity. One per store. Name pattern: `<STORE LABEL> - <LEGAL ENTITY NAME>` (e.g. `SM TANZA - BEBANG MEGA INC.`).

| Field | Category | Value pattern | Rationale (what breaks if missing) |
|---|---|---|---|
| `name` | REQUIRED | `<STORE LABEL> - <LEGAL ENTITY>` exact pattern | Canonical model assumes this. Resolver, sweep, all downstream code reads this. |
| `abbr` | REQUIRED | 2-5 letter store abbreviation (e.g. `ARGW`, `SMM`, `BKI`) | Account names embed this (`1104210 - ... - ARGW`). Without abbr, account creation fails. |
| `parent_company` | REQUIRED-conditional | Legal entity parent name when multi-store parent exists; NULL when standalone (OPC-owned) | Determines if store inherits parent's TIN or uses own. Affects S206 labor cost-sharing intercompany routing. |
| `default_currency` | REQUIRED | `"PHP"` | Mismatch breaks `validate_party_account_currency` on PI/SI submit (S238 hotfix #2 incident). |
| `cost_center` | REQUIRED | `Main - <ABBR>` (canonical) | Used by S238 PI generator's `_resolve_per_store_cost_center` fallback. NULL throws → silent PI generation failure (DEFECT A from sweep). |
| `enable_perpetual_inventory` | REQUIRED | `1` (consistent across all 49) | When 0, ERPNext skips auto-stock-accounting → no GL on stock movements → DEFECT D (silent no-GL on "PASS" stores). |
| `stock_received_but_not_billed` | REQUIRED | Per-store SRBNB account name | GR/IR clearing account. S246 Option 3-corrected: SE.expense_account = SRBNB; PI.expense_account = SRBNB. Without it, PI insertion throws (DEFECT B). |
| `default_inventory_account` | RECOMMENDED | Per-store inventory account | Used by ERPNext's stock posting fallback when Warehouse.account is missing. Belt-and-suspenders. |
| `stock_adjustment_account` | RECOMMENDED | Per-store stock-adj account | Used by Material Receipt's default Cr if `expense_account` not set on SE item. With Option 3-corrected we explicitly set SRBNB, so this is fallback safety. |
| `default_receivable_account` | DEFAULTED | `Debtors - <ABBR>` (auto-created) | Used as PI's debit-to fallback. |
| `default_payable_account` | DEFAULTED | `Creditors - <ABBR>` (auto-created) | Used as PI's credit-to fallback for non-S238 PIs. |
| `entity_category` | REQUIRED | `"Store"` | Filters the 49 store Companies vs holding entities (BFC, L77). Verifier and resolver rely on this. |
| `operational_status` | REQUIRED | `"Active"` (live) or `"Pre-opening"` (setup) | Excludes Permanently Closed / Dormant from active reports. |
| `store_ownership_type` | REQUIRED | `"JV" \| "Managed Franchise" \| "Full Franchise" \| "Company Owned"` | Tax treatment + reporting. Affects BIR filings. |
| `tax_id` | REQUIRED-conditional | Own BIR TIN if standalone legal entity; NULL if inherits from parent | Without correct TIN, SI prints wrong TIN → BIR non-compliance. |

---

## 2. Per-store Warehouse

The orderable warehouse that the UI picks. One per store. Docname == per-store Company name (canonical: same string).

| Field | Category | Value pattern | Rationale |
|---|---|---|---|
| `name` (docname) | REQUIRED | EXACT same string as `Company.name` | Canonical model. The PI/SE generators look up Warehouse by Company name. |
| `warehouse_name` | REQUIRED | `<STORE LABEL>` (short form, e.g. `"SM TANZA"`) | Human-readable label in the UI. |
| `company` | REQUIRED | The per-store Company (NOT the parent) | Per-store P&L roll-up depends on this. If pointing to parent, all of the store's GL goes to the parent's P&L. |
| `account` | REQUIRED (post-S246) | `1104210 - Inventory-from-Commissary - <ABBR>` (or canonical pattern) | When `update_stock=1` SE posts inventory, ERPNext uses `Warehouse.account` as the Dr side. NULL → uses `Company.default_inventory_account` as fallback. Setting per-store ensures the Inventory-from-Commissary account is hit. |
| `is_group` | REQUIRED | `0` (non-group orderable) | Group warehouses don't accept Stock Entries. |
| `disabled` | REQUIRED | `0` | Disabled warehouses don't appear in UI. |
| `custom_area_supervisor` | REQUIRED | The actual Area Supervisor user (e.g. `test.area@bebang.ph` in L3, real supervisor in prod) | Used by S198 store-ordering RBAC. |
| `default_in_transit_warehouse` | RECOMMENDED | Per-store in-transit warehouse OR a global commissary one | For two-step stock transfers. |

---

## 3. Per-store Billing Customer (external-facing, BIR-compliant)

One per store. Docname == per-store Company name.

| Field | Category | Value pattern | Rationale |
|---|---|---|---|
| `name` (docname) | REQUIRED | EXACT same string as `Company.name` | Canonical model. S238 PI generator filter: `frappe.db.exists("Company", doc.customer)`. |
| `customer_name` | REQUIRED | Same string as Company name | Display label. |
| `tax_id` | REQUIRED-conditional | Legal entity BIR TIN (parent's TIN if multi-store, own TIN if standalone) | Printed on SI. BIR non-compliance if missing or wrong. |
| `is_internal_customer` | REQUIRED | `0` | S206 Internal Customer filter excludes this from labor JE routing. |
| `customer_group` | RECOMMENDED | `"BEI Stores"` or similar | Reporting / dashboards. |
| `territory` | RECOMMENDED | Per-store territory (NCR, Cavite, Bulacan, etc.) | Geographic reporting. |

---

## 4. Per-store Internal Customer (S206 labor cost-sharing ONLY)

One per store. Docname == `<STORE LABEL> (Internal)`.

| Field | Category | Value pattern | Rationale |
|---|---|---|---|
| `name` (docname) | REQUIRED | `<STORE LABEL> (Internal)` | Distinct from billing Customer. |
| `customer_name` | REQUIRED | Same string | Display label. |
| `represents_company` | REQUIRED | The per-store Company | S206 matches Internal Customers by this field. |
| `is_internal_customer` | REQUIRED | `1` | Filters out from regular SI workflow. |
| `tax_id` | REQUIRED | NULL | Internal docs don't need TIN. Setting one would mislead readers. |

**HARD RULE:** Internal Customers MUST NEVER appear on a regular Sales Invoice. S206 labor JEs only.

---

## 5. Per-store Accounts (under the Company's CoA)

Five accounts per store. Account number is fixed across all stores; only the abbreviation suffix varies.

| Account Number | Category | Pattern | Type | Root | Rationale |
|---|---|---|---|---|---|
| `1104210` | REQUIRED | `1104210 - Inventory-from-Commissary - <ABBR>` | Stock | Asset | Where commissary-supplied inventory lands. Used by SE `Warehouse.account` mapping (post-S246 Phase 4b). |
| `1106210` | REQUIRED | `1106210 - Input VAT - BKI Inter-Co - <ABBR>` | Tax | Asset | Where the store's claimable Input VAT from BKI inter-company sales lands. Used by PI tax mirror. |
| `2103210` | REQUIRED | `2103210 - AP-Trade-BKI - <ABBR>` | Payable | Liability | Where the store's liability to BKI lands. Used by PI `credit_to`. |
| Stock Received But Not Billed | REQUIRED (post-S246) | `Stock Received But Not Billed - <ABBR>` (or `1402000 - Stock Received But Not Billed - <ABBR>` if numbering convention adopted) | Stock Received But Not Billed | Liability | GR/IR clearing account. SE Cr → PI Dr → nets to zero. Without this, Option 3-corrected JE chain breaks. |
| Stock Adjustment | RECOMMENDED | `Stock Adjustment - <ABBR>` | Stock Adjustment | Expense or Liability | Used by ERPNext for Material Receipt Cr default (if SE item.expense_account NULL). With Option 3-corrected we explicitly set SRBNB, so this is fallback. |

---

## 6. BKI Trade Supplier (global, with per-Company `accounts[]` entries)

One Supplier doc globally. Per-Company entries in `accounts[]` child table.

| Field | Category | Value pattern | Rationale |
|---|---|---|---|
| `name` | REQUIRED | `"BEBANG KITCHEN INC. - Trade"` | Hardcoded in `bki_store_pi_generator.BKI_TRADE_SUPPLIER`. |
| `disabled` | REQUIRED | `0` | Disabled suppliers can't be set on PI. |
| `is_internal_supplier` | REQUIRED | `0` | Per ICT-001..006 (CFO Butch's stance, still valid). MUST NOT be 1 — would conflict with `inter_company_invoice_reference` (S238 hotfix #3 incident). |
| `default_currency` | REQUIRED | `"PHP"` | Mirrors buyer Company currency. |
| `supplier_group` | REQUIRED | `"Services"` or canonical group | Reporting / RBAC. |
| `accounts[]` per buyer Company | REQUIRED (post-S246) | One row per of 49 buyer Companies. `company` = buyer Company name. `account` = that Company's `2103210` account. | When a Finance user manually edits a PI, ERPNext uses `Supplier.accounts[company].account` as the default `credit_to`. Without this row, the field is blank → wrong account picked → wrong GL. |

---

## 7. BEI Settings (global Single doctype)

System-wide toggles + naming series.

| Field | Category | Value | Rationale |
|---|---|---|---|
| `bki_sales_naming_series` | REQUIRED | `"BKI-SI-.YYYY.-.#####"` | Used by autoname hook to generate SI names like `BKI-SI-2026-00981-1`. |
| `enable_bki_store_pi_generator` | REQUIRED (NEW S246) | `1` (default) | Kill switch for PI generator. v1.0 plan referenced it but field didn't exist → no kill switch. S246 Phase 3C installs it. |
| `enable_bki_store_stock_entry_generator` | REQUIRED (NEW S246) | `1` (default) | Kill switch for SE generator. NEW S246. Used by Phase 6 cleanup to disable generators during 839-SI cleanup. |
| `bki_markup_*`, `bki_output_*`, `bki_ewt_*` | EXISTS | Various | Other BKI-related config, not S246 scope. |

---

## 8. Custom Fields (global, installed via fixtures or `frappe.custom_field.create_custom_field`)

Cross-doctype links and BEI-specific fields.

| Doctype | Fieldname | Category | Type | Rationale |
|---|---|---|---|---|
| Sales Invoice | `custom_bei_store_order` | REQUIRED | Link to BEI Store Order | Links SI to the originating store order. Used by SI autoname hook. |
| Purchase Invoice | `bki_si_reference` | REQUIRED | Link to Sales Invoice | Natural-key link from store-side PI back to BKI's SI. Used by cascade-cancel. |
| Stock Entry | `bki_si_reference` | REQUIRED (NEW S246) | Link to Sales Invoice | Natural-key link from store-side SE back to BKI's SI. NEW S246. Mirrors PI. |
| Sales Invoice | `bei_legal_entity` | REQUIRED (S192) | Data | Seller's legal entity (BKI for these flows). |
| Sales Invoice | `bei_store_label` | REQUIRED (S203) | Data | Store label (short form, e.g. "ARANETA GATEWAY"). |
| Purchase Invoice | `bei_legal_entity` | REQUIRED (S192) | Data | Buyer's legal entity per ICT-003 (NOT seller's). Used by per-entity P&L reports. |
| Purchase Invoice | `bei_store_label` | REQUIRED (S203) | Data | Mirror of SI's store_label. |

---

## 9. doc_events Hook Wiring (`hrms/hooks.py`)

| Doctype | Event | Handler(s) | Category | Rationale |
|---|---|---|---|---|
| Sales Invoice | `autoname` | `hrms.api.bki_si_naming.set_bki_si_name` | REQUIRED | BKI SI naming hook. |
| Sales Invoice | `on_submit` | [PI generator, SE generator (post-S246)] **MUST be a list, not a string** | REQUIRED | Triggers paired doc generation. v1.0 plan miss: existing entry is a STRING, naive append breaks BKI billing. S246 P3B.6 explicit STRING→LIST conversion. |
| Sales Invoice | `on_cancel` | [SE cascade FIRST (reverse-creation), PI cascade SECOND] **MUST be a list** | REQUIRED | Cascade-cancel paired docs. |
| Purchase Invoice | `validate` | `hrms.api.bki_store_pi_generator.lock_posting_date_on_bki_paired_pi` | REQUIRED | PFRS posting-date lock. |
| Stock Entry | `validate` | `hrms.api.bki_store_stock_entry_generator.lock_posting_date_on_bki_paired_se` | REQUIRED (NEW S246) | PFRS posting-date lock for SE. NEW S246 Phase 3B.7b. |

---

## Roll-up: per-store completeness equation

A store is **fully canonical** iff:
- All 15 REQUIRED Company fields set with valid values
- All 7 REQUIRED Warehouse fields set
- All 4 REQUIRED Customer fields set
- All 5 REQUIRED Internal Customer fields set
- All 4 REQUIRED Account rows exist on the Company's CoA (1104210, 1106210, 2103210, SRBNB)
- BKI Trade Supplier has an `accounts[]` row for this Company

A store is **operationally usable but with gaps** iff:
- All REQUIRED set; one or more RECOMMENDED missing.

A store is **broken** iff:
- Any REQUIRED missing or wrong.

Verifier v2 mode (Phase 1A.4) reports the count per category per store.

---

## Coverage matrix (v1.0 snapshot from 2026-05-11 probe)

From `output/l3/billing-sweep-2026-05-11/evidence/probe_result.json` + `perp_result.json`:

| Field | Stores with REQUIRED met | Stores with gap |
|---|---|---|
| `Company.cost_center` | 45 | 4 (ROA, SMM, SMMM, SMS — DEFECT A) |
| `Company.enable_perpetual_inventory = 1` | 36 | 13 (silently OFF — DEFECT D) |
| `Company.stock_received_but_not_billed` | 2 | 47 (DEFECT B) |
| `Warehouse.account` | 0 | 49 (DEFECT C — uncovered post-Option 3) |
| `BKI Trade Supplier.accounts[buyer]` | 0 | 49 (UX gap for Finance UI) |
| `enable_bki_store_pi_generator` field | 0 | 49 (field doesn't exist — NEW S246 Phase 3C) |
| `Stock Entry.bki_si_reference` Custom Field | 0 | NEW S246 Phase 3C.4 |

**Roll-up:** 0 of 49 stores are fully canonical today. Post-S246 Phase 4b: all 49 should be.
