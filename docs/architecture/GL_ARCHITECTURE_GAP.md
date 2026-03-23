# GL Architecture Gap: BEI Custom DocTypes vs Frappe Standard GL

**Date:** 2026-03-23
**Sprint:** S100 — SCM Operational Hardening
**Status:** Documentation only — no code changes

---

## 1. The Dual-DocType Architecture

BEI uses a **dual-layer** system for procurement:

| Layer | DocTypes | Purpose | Creates GL Entries? |
|-------|----------|---------|-------------------|
| BEI Workflow Layer | BEI Purchase Order, BEI Goods Receipt, BEI Invoice, BEI Payment Request | Workflow tracking, approvals, 3-way matching | **NO** |
| Frappe Standard Layer | Purchase Order, Purchase Receipt, Purchase Invoice, Payment Entry, Journal Entry | GL accounting, stock ledger, tax reports | **YES** |

### Why this architecture exists

1. Frappe's standard procurement flow doesn't support BEI's multi-level approval (Mae + Butch + CEO)
2. BEI needed custom fields (3PL flags, commissary dispatch, match exceptions) that couldn't be cleanly added to standard DocTypes
3. The BEI layer was built first for operational tracking; Frappe GL integration was added later

### The bridge

- `BEI Purchase Order.create_frappe_purchase_order()` creates a standard Frappe PO on approval
- `warehouse.py:create_purchase_receipt()` creates a Frappe Purchase Receipt for stock movement
- `BEI Payment Request.create_frappe_payment_entry()` creates a Frappe Payment Entry on payment processing
- `procurement.py:create_ewt_journal_voucher()` creates JEs for EWT withholding

---

## 2. GL Gaps Identified

### Gap 1: BEI Goods Receipt does NOT create stock entries

**Current:** `create_goods_receipt()` only creates a `BEI Goods Receipt` document.
**Expected:** A Frappe Purchase Receipt should be created to move stock into the warehouse.
**Impact:** Inventory valuation in Frappe is incorrect until `create_purchase_receipt()` is explicitly called (separate flow in warehouse.py).
**Risk:** If warehouse staff use the GR flow but skip the Purchase Receipt step, stock is "received" in BEI tracking but invisible in Frappe stock ledger.

### Gap 2: No GR/IR Clearing accrual at goods receipt

**Current:** The GR/IR Clearing account (1104005) is only used in advance clearing JVs.
**Expected:** Standard 3-way match flow: On GR, debit Inventory and credit GR/IR Clearing. On Invoice, debit GR/IR Clearing and credit AP.
**Impact:** The GR/IR Clearing account balance does not reflect actual goods received but not yet invoiced.

### Gap 3: Input VAT not recorded at GR

**Current:** Input VAT (1105103) is only posted during advance clearing, not during standard goods receipt.
**Expected:** VAT should be claimable when goods are received (or when invoice is matched, depending on BIR interpretation).
**Impact:** Input VAT claims may not align with BIR filing periods.

### Gap 4: BEI Invoice does NOT create Frappe Purchase Invoice

**Current:** `create_invoice()` only creates a `BEI Invoice`. The bridge to Frappe Purchase Invoice exists but must be explicitly triggered.
**Impact:** AP aging, purchase register, and BIR reports don't reflect BEI invoices until the bridge is run.

### Gap 5: No automatic GL on payment processing

**Current:** `BEI Payment Request.create_frappe_payment_entry()` exists but is not automatically called on payment approval.
**Impact:** Payments may be processed operationally but not reflected in Frappe GL.

---

## 3. Recommended Path Forward

### Option A: Tighter Auto-Bridge (Recommended)

Add automatic GL creation at each stage:
1. On `BEI Goods Receipt` creation -> auto-create Frappe Purchase Receipt
2. On `BEI Invoice` creation -> auto-create Frappe Purchase Invoice
3. On `BEI Payment Request` fully approved -> auto-create Frappe Payment Entry

**Pros:** Minimal architecture change, GL stays current
**Cons:** Performance impact of creating 2 docs per operation

### Option B: Merge DocTypes (Long-term)

Replace BEI custom DocTypes with extended Frappe standard DocTypes using custom fields.

**Pros:** Single source of truth
**Cons:** Major migration effort, potential regression in approval workflows

### Option C: Nightly Reconciliation (Stopgap)

Run a daily cron that reconciles BEI docs with Frappe GL and creates missing entries.

**Pros:** No runtime impact
**Cons:** GL is always 1 day behind, complex error handling

### Recommendation

**Option A** for the next sprint, with **Option C** as an immediate safety net. Option B requires a dedicated architecture sprint with extensive testing.

---

## 4. Accounting Impact Summary

| BEI Operation | Frappe GL Impact | Current Status |
|--------------|-----------------|----------------|
| Create BEI PO | Creates Frappe PO (on approval) | Working |
| Create BEI GR | Should create Purchase Receipt | GAP — manual step required |
| Create BEI Invoice | Should create Purchase Invoice | GAP — manual step required |
| Approve Payment | Should create Payment Entry | GAP — method exists but not auto-called |
| EWT Withholding | Creates Journal Entry | Working |
| Advance Clearing | Creates Journal Entry | Working |

---

## 5. Cross-Check SQL Queries

See `docs/architecture/GL_RECONCILIATION_RUNBOOK.md` for SQL queries to verify GL consistency.
