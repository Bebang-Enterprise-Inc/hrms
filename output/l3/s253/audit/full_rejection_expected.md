# Phase 4.6 Full Rejection — Expected Behavior (Pre-Step)
**Date:** 2026-05-21
**Source code reference:** `hrms/api/warehouse.py:complete_warehouse_receiving` lines 785-869

## Determination

**Expected branch:** **Branch A — SI NOT created (BIR-compliant)**

## Source evidence

`warehouse.py:855-868`:

```python
if not accepted_items:
    if any(flt(item_data.get("rejected_qty", 0)) > 0 for item_data in items):
        # Full rejection — no stock entry needed, just update status
        receiving.receiving_date = now_datetime()
        receiving.received_by_user = frappe.session.user
        receiving.remarks = remarks or receiving.remarks
        receiving.status = "With Issues"
        receiving.save(ignore_permissions=True)
        frappe.db.commit()
        return {
            "success": True,
            "data": {"receiving_name": receiving.name, "status": "fully_rejected"},
            "message": f"All items rejected for {receiving.name}",
        }
    frappe.throw(_("No accepted quantity to receive into warehouse"))
```

When **all received items are rejected** (`rejected_qty == received_qty` for every line, making `accepted_qty = 0`), the function:

1. Detects `accepted_items` is empty
2. Detects at least one item has `rejected_qty > 0` (confirming explicit rejection, not zero-receipt)
3. Sets WR `status = "With Issues"`
4. Saves WR + commits
5. **RETURNS EARLY** — no `Stock Entry` is created
6. Since SI creation is downstream of Stock Entry creation (S198 chain: SE submit → SI auto-create on BKI books), **no Sales Invoice is created either**
7. No paired PI/SE generated (the S247 hook chain requires a submitted SI)

## Why this is BIR-compliant

A zero-value commercial invoice violates Philippine BIR rules (a Sales Invoice must have a valid taxable amount). By NOT creating an SI on full rejection, BEI avoids:
- Producing a non-compliant zero-value SI
- Polluting the BIR-filed SI sequence with refund-equivalent invoices
- Mismatching the SI sequence numbering between the buyer side and BKI's books

## Phase 4.6 spec assertion

The S253 spec's full rejection test asserts:
- `WR.status == "With Issues"` (or equivalent — check Sales Invoice query returns empty)
- `queryDocs("Sales Invoice", {custom_bei_store_order: orderId, docstatus: 1})` returns `[]`
- No paired PI exists (`queryDocs("Purchase Invoice", {bki_si_reference: <hypothetical>})` returns `[]`)
- No paired SE exists (same query for Stock Entry)

If the spec observes any of these violated (especially "Zero-value SI created"), the test marks `pass=false` and writes a DEFECT entry — but per the code reading above, this branch is unreachable on the current production code.

## Confidence

**HIGH** — the early-return guard is unambiguous. The code path is `accepted_items.empty AND any.rejected_qty>0 → return without SE/SI`.

## Disposition

- ✅ Phase 4.6 spec assertion configured for Branch A
- ✅ No DEFECT entry needed (BIR-compliant path is the production behavior)
- ✅ Phase 4 spec ready to execute against ARANETA in the next session
