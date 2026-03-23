# GL Reconciliation Runbook

**Date:** 2026-03-23
**Purpose:** Manual verification that BEI tracking docs match Frappe GL state

---

## 1. BEI POs Without Frappe POs

```sql
-- Find approved BEI POs that don't have a linked Frappe PO
SELECT name, po_no, supplier_name, grand_total, status, mae_approval, butch_approval
FROM `tabBEI Purchase Order`
WHERE status IN ('Approved', 'Sent to Supplier', 'Partially Received', 'Fully Received')
  AND (frappe_po IS NULL OR frappe_po = '')
ORDER BY modified DESC;
```

**Action:** Run `BEIPurchaseOrder.create_frappe_purchase_order()` for each.

---

## 2. BEI GRs Without Frappe Purchase Receipts

```sql
-- Find BEI Goods Receipts that have no corresponding Frappe Purchase Receipt
SELECT gr.name, gr.purchase_order, gr.receipt_date, gr.status,
       gr.total_received_qty, gr.total_amount
FROM `tabBEI Goods Receipt` gr
WHERE gr.status IN ('Submitted', 'Approved', 'Inspected', 'Accepted')
  AND NOT EXISTS (
    SELECT 1 FROM `tabPurchase Receipt` pr
    WHERE pr.bei_goods_receipt = gr.name
       OR (pr.supplier = (SELECT supplier_name FROM `tabBEI Purchase Order` WHERE name = gr.purchase_order)
           AND pr.posting_date = DATE(gr.receipt_date))
  )
ORDER BY gr.receipt_date DESC;
```

**Action:** Create Purchase Receipt via warehouse receiving flow.

---

## 3. BEI Invoices Without Frappe Purchase Invoices

```sql
-- Find BEI Invoices without linked Frappe Purchase Invoice
SELECT inv.name, inv.supplier, inv.supplier_name, inv.invoice_date,
       inv.grand_total, inv.status, inv.frappe_purchase_invoice
FROM `tabBEI Invoice` inv
WHERE inv.status NOT IN ('Draft', 'Cancelled')
  AND (inv.frappe_purchase_invoice IS NULL OR inv.frappe_purchase_invoice = '')
ORDER BY inv.invoice_date DESC;
```

**Action:** Create Frappe Purchase Invoice for each.

---

## 4. BEI Payments Without Frappe Payment Entries

```sql
-- Find paid BEI Payment Requests without linked Frappe Payment Entry
SELECT pr.name, pr.supplier_name, pr.payment_amount, pr.payment_date,
       pr.status, pr.frappe_payment_entry
FROM `tabBEI Payment Request` pr
WHERE pr.status = 'Paid'
  AND (pr.frappe_payment_entry IS NULL OR pr.frappe_payment_entry = '')
ORDER BY pr.payment_date DESC;
```

**Action:** Run `BEIPaymentRequest.create_frappe_payment_entry()` for each.

---

## 5. AP Balance Cross-Check

```sql
-- Compare BEI supplier outstanding vs Frappe GL AP balance
SELECT
    s.name as supplier,
    s.supplier_name,
    s.total_outstanding as bei_outstanding,
    COALESCE((
        SELECT SUM(gle.credit - gle.debit)
        FROM `tabGL Entry` gle
        WHERE gle.party_type = 'Supplier'
          AND gle.party = s.frappe_supplier
          AND gle.account LIKE '2101%'
          AND gle.is_cancelled = 0
    ), 0) as frappe_ap_balance
FROM `tabBEI Supplier` s
WHERE s.status = 'Active'
  AND s.total_outstanding != 0
ORDER BY ABS(s.total_outstanding) DESC
LIMIT 50;
```

**Expected:** `bei_outstanding` and `frappe_ap_balance` should match within rounding tolerance.

---

## 6. Stock Valuation Cross-Check

```sql
-- Compare BEI GR accepted quantities vs Frappe stock balance
SELECT
    gri.item_code,
    SUM(gri.accepted_qty) as bei_accepted,
    (SELECT SUM(actual_qty) FROM `tabBin` WHERE item_code = gri.item_code) as frappe_stock
FROM `tabBEI GR Item` gri
JOIN `tabBEI Goods Receipt` gr ON gri.parent = gr.name
WHERE gr.status NOT IN ('Draft', 'Cancelled')
GROUP BY gri.item_code
HAVING bei_accepted != COALESCE((SELECT SUM(actual_qty) FROM `tabBin` WHERE item_code = gri.item_code), 0)
ORDER BY ABS(bei_accepted - COALESCE((SELECT SUM(actual_qty) FROM `tabBin` WHERE item_code = gri.item_code), 0)) DESC
LIMIT 20;
```

---

## Schedule

Run queries 1-4 **daily** to catch gaps within 24 hours.
Run queries 5-6 **weekly** for balance verification.

Consider automating as a scheduled task (future sprint).
