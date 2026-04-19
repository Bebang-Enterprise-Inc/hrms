# STORE / COMPANY CANONICAL MODEL — Single Source of Truth

**Last updated:** 2026-04-19 (Sam Karazi, CEO)
**Scope:** All BEI store records in Frappe — Company, Warehouse, Customer, Cost Center
**Binding:** MANDATORY. Agents violating this rule cause multi-day cleanups.

---

## THE LAW

For every BEI store there is **EXACTLY ONE** of each of the following records. No exceptions.

### 1. ONE per-store Company (the billing + P&L entity)

- `name` = `<STORE LABEL> - <LEGAL ENTITY NAME>` (e.g. `SM TANZA - BEBANG MEGA INC.`)
- `entity_category` = `"Store"`
- `parent_company` = the legal entity parent (e.g. `BEBANG MEGA INC.`) when the legal entity owns multiple stores. May be NULL when the store IS its own legal entity (OPC-owned, sole-franchisee).
- `operational_status` = `"Active"` (or `"Pre-opening"` during setup)
- `store_ownership_type` = one of `"JV" | "Managed Franchise" | "Full Franchise" | "Company Owned"`
- `tax_id` = store's own BIR TIN if it's a separate legal entity, else NULL (inherits from parent)

### 2. ONE Warehouse (orderable, the one the UI picks)

- `name` (docname) = `<STORE LABEL> - <LEGAL ENTITY NAME>` — **same string as the per-store Company name**
- `warehouse_name` = `<STORE LABEL>` (human-readable, e.g. `"SM TANZA"`)
- `company` = **the per-store Company** (NOT the parent — this is what makes per-store P&L roll up correctly)
- `is_group` = `0`
- `disabled` = `0`
- `custom_area_supervisor` = the actual Area Supervisor user (e.g. `test.area@bebang.ph` in L3, real supervisor in prod)

### 3. ONE Billing Customer (the external-facing BIR-compliant Customer)

- `name` (docname) = `<STORE LABEL> - <LEGAL ENTITY NAME>` — same string as per-store Company
- `customer_name` = `<STORE LABEL> - <LEGAL ENTITY NAME>` — same string
- `tax_id` = the BIR TIN to print on the SI. For multi-store parents: use the parent's TIN. For standalone stores: use the store's own TIN.
- `is_internal_customer` = `0`
- Billing address points to the store's physical location

### 4. ONE Internal Customer (for S206 labor cost-sharing ONLY)

- `name` = `<STORE LABEL> (Internal)` (e.g. `SM TANZA (Internal)`)
- `customer_name` = `<STORE LABEL> (Internal)` — same string
- `represents_company` = **the per-store Company** (this is how S206 matches)
- `is_internal_customer` = `1`
- `tax_id` = NULL (internal paired-JEs don't need a TIN)
- **MUST NEVER BE USED FOR REGULAR SALES INVOICES**

---

## THE ABSOLUTE RULES

### Rule 1 — No duplicates, EVER

If a record matching the canonical name already exists for a store, UPDATE it. Never create a parallel record. Before creating any Company / Warehouse / Customer, run:

```bash
python scripts/verify_canonical_structure.py --store "<STORE_NAME>"
```

If it prints `[CANONICAL OK]`, you don't need to create anything. If it prints `[VIOLATION]`, read the report and fix the specific violation — do not layer on a new record.

### Rule 2 — No deletions (disable, don't delete)

Master records with transactional history (any doctype that appears in GL Entries, Stock Ledger Entries, Customer Ledger, etc.) are never deleted by agents. Set `disabled=1` instead. The only exception is Sam-approved migration sprints that include explicit SQL post-audit.

### Rule 3 — Naming is immutable

- Per-store Company name, Warehouse docname, Billing Customer docname: all three are the SAME string. If you rename one, you rename all three together in a single transaction via `scripts/canonical/rename_store.py`.
- Warehouse `warehouse_name` field is the human-readable short form (e.g. `"SM TANZA"`) and matches the store label portion of the docname.
- Internal Customer name = `<STORE LABEL> (Internal)` — never change this suffix pattern.

### Rule 4 — The resolver trusts the model, not fallbacks

The canonical resolver is `resolve_store_buyer_entity` in `hrms/utils/supply_chain_contracts.py`. It does exactly ONE thing: look up a Customer whose `customer_name` equals the Warehouse's Company. That's step 1. No fallbacks.

The 4-step fallback that existed before 2026-04-19 was a bridge during migration. It is being retired. Agents who add new fallbacks to work around master-data bugs will have their PR reverted and will be asked to fix the master data instead.

**The resolver explicitly skips `is_internal_customer=1` Customers** when scanning by `represents_company`. Internal Customers exist only for labor journals, never for SIs.

### Rule 5 — Payroll + labor cost-sharing are load-bearing

- S206 Internal Customers MUST exist for every per-store Company.
- Their `represents_company` field MUST NOT be modified.
- Their presence MUST NOT block billing (Rule 4 above keeps them out of SI creation).
- If you need to rename a per-store Company: use `scripts/canonical/rename_store.py` which cascades to the Internal Customer's `represents_company` atomically.

### Rule 6 — No ad-hoc SQL on master records

Agents must use the canonical scripts in `scripts/canonical/`. If your sprint needs a mutation these scripts don't cover, propose a new canonical script in your plan first, get Sam's approval, then add it to the toolbox.

Canonical scripts:
- `scripts/canonical/create_new_store.py` — onboard a new store
- `scripts/canonical/rename_store.py` — atomic rename across Company + Warehouse + both Customers + CostCenter
- `scripts/canonical/retire_store.py` — disable (not delete) a closed store
- `scripts/canonical/transfer_store.py` — reassign a store to a different parent entity
- `scripts/verify_canonical_structure.py` — read-only audit

### Rule 7 — Plan files must cite this guide

Any sprint plan that touches Company / Warehouse / Customer master data MUST include the line:

> **Canonical model reference:** `docs/STORE_COMPANY_CANONICAL.md`

And list every record the sprint will create/update/disable. Failure to cite blocks the plan-audit gate.

### Rule 8 — BEI ERP is in BUILD phase

Destructive master-data cleanup executes NOW. Do not defer to payroll, billing, or BIR cycles unless Sam explicitly flags a specific event as a freeze. See memory: `bei-build-phase-not-production.md`.

---

## THE AUTHORITATIVE REGISTRY

The current state of all 49 stores lives at:

```
data/_CONSOLIDATED/STORE_CANONICAL_STATE_YYYY-MM-DD.csv
```

Regenerated after every migration. Treat as read-only between regenerations. Regenerate with:

```bash
python scripts/canonical_scan_store_state.py
```

---

## ANTIPATTERNS (WHAT NOT TO DO)

These are real incidents from April 2026. If you find yourself typing one of these, STOP.

1. **Creating a warehouse named `<PARENT> - <STORE> - <ABBR>` (S188 pattern).** This duplicates an existing `<STORE> - <PARENT>` warehouse. The old warehouse stays; the new one confuses the UI. Fix: update the existing warehouse, don't create a new one.

2. **Creating a Customer for billing whose `customer_name` doesn't exactly match the per-store Company name.** The resolver can't find it. SI creation falls through to a fallback path that bills the wrong entity. Fix: customer_name === per-store Company name, always.

3. **Reusing an S206 Internal Customer for billing.** It has no TIN. SI fails BIR compliance. Fix: create a separate billing Customer (Rule 3 above).

4. **Adding a new fallback step to the resolver.** This hides master-data bugs. Fix: fix the master data.

5. **Deleting a warehouse/customer/company to "clean up."** Breaks GL. Fix: `disabled=1`.

6. **Ad-hoc SQL like `UPDATE tabWarehouse SET company='X' WHERE name='Y';`** Skips the canonical scripts' safety checks. Fix: use `scripts/canonical/*.py`.

---

## CANONICAL STATE FOR SM TANZA (REFERENCE EXAMPLE)

```
Per-store Company: SM TANZA - BEBANG MEGA INC.
  parent_company:   BEBANG MEGA INC.
  entity_category:  Store
  tax_id:           (inherits from parent)

Warehouse:         SM TANZA - BEBANG MEGA INC.
  warehouse_name:   SM TANZA
  company:          SM TANZA - BEBANG MEGA INC.
  custom_area_supervisor: test.area@bebang.ph

Billing Customer:  SM TANZA - BEBANG MEGA INC.
  customer_name:    SM TANZA - BEBANG MEGA INC.
  tax_id:           010-885-436-00000 (parent's TIN)
  is_internal_customer: 0

Internal Customer: SM TANZA (Internal)
  represents_company: SM TANZA - BEBANG MEGA INC.
  is_internal_customer: 1
  tax_id:           NULL
```

SI result on store order delivery:
```
SI.company              = BEBANG KITCHEN INC. (BKI, the issuer)
SI.customer             = SM TANZA - BEBANG MEGA INC.
SI.tax_id               = 010-885-436-00000
SI.bei_legal_entity     = BEBANG KITCHEN INC.
SI rolls up P&L to      SM TANZA - BEBANG MEGA INC. Company (per-store P&L)
Parent P&L aggregates   via Company.parent_company chain
```
