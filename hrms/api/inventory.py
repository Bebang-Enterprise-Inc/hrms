# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
Inventory API
Handles cycle counts, variances, and shelf life extensions
"""

import frappe
from frappe import _
from frappe.utils import nowdate, flt
import json


@frappe.whitelist()
def submit_cycle_count(store, items, count_date=None):
    """Submit inventory cycle count."""
    if not store:
        frappe.throw(_("Store is required"))

    if isinstance(items, str):
        items = json.loads(items)

    # Validate no negative quantities
    for item in items:
        if flt(item.get("counted_qty", 0)) < 0:
            frappe.throw(_("Counted quantity cannot be negative for item {0}").format(
                item.get("item_code", "unknown")))

    doc = frappe.new_doc("BEI Cycle Count")
    doc.store = store
    doc.count_date = count_date or nowdate()
    doc.counted_by = frappe.session.user

    total_variance = 0
    for item in items:
        # Get system qty from stock ledger
        system_qty = frappe.db.get_value(
            "Bin",
            {"warehouse": store, "item_code": item["item_code"]},
            "actual_qty"
        ) or 0

        row = doc.append("items", {
            "item_code": item["item_code"],
            "system_qty": system_qty,
            "counted_qty": flt(item["counted_qty"]),
            "variance_qty": flt(item["counted_qty"]) - system_qty,
            "remarks": item.get("remarks")
        })

        # Calculate variance value
        item_price = frappe.db.get_value("Item", item["item_code"], "valuation_rate") or 0
        row.variance_value = row.variance_qty * item_price
        total_variance += row.variance_value

    doc.total_variance_value = total_variance
    doc.status = "Submitted"
    doc.insert()
    return {"success": True, "name": doc.name, "total_variance": total_variance}


@frappe.whitelist()
def get_cycle_counts(store=None, date_from=None, date_to=None, status=None, limit=20):
    """Get cycle count history."""
    limit = min(int(limit or 20), 500)
    filters = {}
    if store:
        filters["store"] = store
    if status:
        filters["status"] = status
    if date_from:
        filters["count_date"] = [">=", date_from]
    if date_to:
        if "count_date" in filters:
            filters["count_date"] = ["between", [date_from, date_to]]
        else:
            filters["count_date"] = ["<=", date_to]

    counts = frappe.get_all(
        "BEI Cycle Count",
        filters=filters,
        fields=["name", "store", "count_date", "status", "total_variance_value", "counted_by",
                "rejection_reason", "resubmission_count"],
        order_by="count_date desc",
        limit=int(limit)
    )
    return {"counts": counts}


@frappe.whitelist()
def approve_cycle_count(count_name):
    """Approve a submitted cycle count."""
    allowed_roles = ["Area Supervisor", "Store Supervisor", "System Manager"]
    if not any(r in frappe.get_roles(frappe.session.user) for r in allowed_roles):
        frappe.throw(_("Not authorized to approve cycle counts"), frappe.PermissionError)

    doc = frappe.get_doc("BEI Cycle Count", count_name)

    if doc.status not in ["Submitted", "Resubmitted"]:
        frappe.throw(_("Only submitted cycle counts can be approved"))

    doc.status = "Verified"
    doc.approved_by = frappe.session.user
    doc.approved_at = nowdate()
    doc.save()

    return {"success": True, "message": _("Cycle count approved")}


@frappe.whitelist()
def reject_cycle_count(count_name, rejection_reason):
    """Reject a submitted cycle count with a reason."""
    allowed_roles = ["Area Supervisor", "Store Supervisor", "System Manager"]
    if not any(r in frappe.get_roles(frappe.session.user) for r in allowed_roles):
        frappe.throw(_("Not authorized to reject cycle counts"), frappe.PermissionError)

    if not rejection_reason:
        frappe.throw(_("Rejection reason is required"))

    doc = frappe.get_doc("BEI Cycle Count", count_name)

    if doc.status not in ["Submitted", "Resubmitted"]:
        frappe.throw(_("Only submitted cycle counts can be rejected"))

    doc.status = "Rejected"
    doc.rejection_reason = rejection_reason
    doc.save()

    return {"success": True, "message": _("Cycle count rejected")}


@frappe.whitelist()
def resubmit_cycle_count(count_name, items):
    """
    Resubmit a rejected cycle count with corrected counts.
    Creates a new cycle count document linked to the original.
    """
    if isinstance(items, str):
        items = json.loads(items)

    original = frappe.get_doc("BEI Cycle Count", count_name)

    if original.status != "Rejected":
        frappe.throw(_("Only rejected cycle counts can be resubmitted"))

    # Create new cycle count as resubmission
    doc = frappe.new_doc("BEI Cycle Count")
    doc.store = original.store
    doc.count_date = nowdate()
    doc.counted_by = frappe.session.user
    doc.original_count = original.name
    doc.resubmission_count = (original.resubmission_count or 0) + 1

    total_variance = 0
    for item in items:
        system_qty = frappe.db.get_value(
            "Bin",
            {"warehouse": original.store, "item_code": item["item_code"]},
            "actual_qty"
        ) or 0

        row = doc.append("items", {
            "item_code": item["item_code"],
            "system_qty": system_qty,
            "counted_qty": flt(item["counted_qty"]),
            "variance_qty": flt(item["counted_qty"]) - system_qty,
            "remarks": item.get("remarks")
        })

        item_price = frappe.db.get_value("Item", item["item_code"], "valuation_rate") or 0
        row.variance_value = row.variance_qty * item_price
        total_variance += row.variance_value

    doc.total_variance_value = total_variance
    doc.status = "Resubmitted"
    doc.insert()

    # Update original to indicate it was resubmitted
    original.db_set("notes", f"Resubmitted as {doc.name} on {nowdate()}\n" + (original.notes or ""))

    return {
        "success": True,
        "name": doc.name,
        "total_variance": total_variance,
        "message": _("Cycle count resubmitted successfully")
    }


@frappe.whitelist()
def report_variance(store, item_code, system_qty, actual_qty, variance_type, explanation, photo=None):
    """Report inventory variance."""
    if not store or not item_code:
        frappe.throw(_("Store and item are required"))

    doc = frappe.new_doc("BEI Inventory Variance")
    doc.store = store
    doc.variance_date = nowdate()
    doc.item_code = item_code
    doc.system_qty = flt(system_qty)
    doc.actual_qty = flt(actual_qty)
    doc.variance_qty = flt(actual_qty) - flt(system_qty)

    item_price = frappe.db.get_value("Item", item_code, "valuation_rate") or 0
    doc.variance_value = doc.variance_qty * item_price

    doc.variance_type = variance_type
    doc.explanation = explanation
    doc.reported_by = frappe.session.user
    doc.photo_evidence = photo
    doc.insert()
    return {"success": True, "name": doc.name}


@frappe.whitelist()
def get_variances(store=None, status=None, limit=20):
    """Get inventory variances."""
    limit = min(int(limit or 20), 500)
    filters = {}
    if store:
        filters["store"] = store
    if status:
        filters["status"] = status

    variances = frappe.get_all(
        "BEI Inventory Variance",
        filters=filters,
        fields=[
            "name", "store", "item_code", "variance_qty",
            "variance_value", "variance_type", "status"
        ],
        order_by="creation desc",
        limit=int(limit)
    )
    return {"variances": variances}


@frappe.whitelist()
def request_shelf_extension(store, item_code, original_expiry, requested_expiry,
                            quantity, reason, batch_no=None, photo=None):
    """Request shelf life extension for an item."""
    if not store or not item_code:
        frappe.throw(_("Store and item are required"))

    doc = frappe.new_doc("BEI Shelf Life Extension")
    doc.store = store
    doc.request_date = nowdate()
    doc.item_code = item_code
    doc.batch_no = batch_no
    doc.original_expiry = original_expiry
    doc.requested_expiry = requested_expiry
    doc.quantity = flt(quantity)
    doc.reason = reason
    doc.requested_by = frappe.session.user
    doc.photo_evidence = photo
    doc.insert()

    return {"success": True, "name": doc.name}


@frappe.whitelist()
def approve_shelf_extension(extension_name, approved_expiry=None, rejection_reason=None, approve=True):
    """Approve or reject shelf life extension."""
    allowed_roles = ["Area Supervisor", "Store Supervisor", "System Manager"]
    if not any(r in frappe.get_roles(frappe.session.user) for r in allowed_roles):
        frappe.throw(_("Not authorized to approve shelf life extensions"), frappe.PermissionError)

    doc = frappe.get_doc("BEI Shelf Life Extension", extension_name)

    if approve:
        doc.status = "Approved"
        doc.approved_by = frappe.session.user
        doc.approved_expiry = approved_expiry or doc.requested_expiry
    else:
        doc.status = "Rejected"
        doc.approved_by = frappe.session.user
        doc.rejection_reason = rejection_reason

    doc.save()
    return {"success": True, "status": doc.status}


# ============ RETURNS APIs ============

def _resolve_warehouse(store_or_branch):
    """Resolve a branch name to full warehouse name."""
    if not store_or_branch:
        return None

    if frappe.db.exists("Warehouse", store_or_branch):
        return store_or_branch

    warehouse_with_company = f"{store_or_branch} - BEI"
    if frappe.db.exists("Warehouse", warehouse_with_company):
        return warehouse_with_company

    warehouse = frappe.db.get_value("Warehouse", {"warehouse_name": store_or_branch}, "name")
    if warehouse:
        return warehouse

    return None


@frappe.whitelist()
def get_returnable_items(store=None):
    """
    Get items that can be returned from a store.
    Returns items with current stock in the store's warehouse.
    """
    warehouse = _resolve_warehouse(store) if store else None

    if warehouse:
        # Get items with stock in this warehouse
        items = frappe.db.sql("""
            SELECT
                b.item_code as id,
                i.item_name as name,
                i.item_group,
                i.stock_uom as uom,
                b.actual_qty as stock_qty
            FROM `tabBin` b
            JOIN `tabItem` i ON i.name = b.item_code
            WHERE b.warehouse = %s
            AND b.actual_qty > 0
            AND i.disabled = 0
            ORDER BY i.item_group, i.item_name
        """, warehouse, as_dict=True)
    else:
        # Get all stock items if no store specified
        items = frappe.get_all(
            "Item",
            filters={"is_stock_item": 1, "disabled": 0},
            fields=["name as id", "item_name as name", "item_group", "stock_uom as uom"]
        )

    return {"items": items}


@frappe.whitelist()
def get_return_reasons():
    """Get list of valid return reasons."""
    # Return from master data if exists, otherwise hardcoded list
    reasons = [
        {"value": "expired", "label": "Expired/Near Expiry"},
        {"value": "damaged", "label": "Damaged Packaging"},
        {"value": "quality", "label": "Quality Issue"},
        {"value": "overstock", "label": "Overstock/Slow Moving"},
        {"value": "recall", "label": "Product Recall"},
        {"value": "other", "label": "Other"},
    ]
    return {"reasons": reasons}


@frappe.whitelist()
def submit_return_request(store, items, photo=None):
    """
    Submit a return request to commissary.
    Items should be a list of {item_code, quantity, reason, notes}
    """
    allowed_roles = ["Store Supervisor", "Store Staff", "Area Supervisor", "System Manager"]
    if not any(r in frappe.get_roles(frappe.session.user) for r in allowed_roles):
        frappe.throw(_("Not authorized to submit return requests"), frappe.PermissionError)

    if not store:
        frappe.throw(_("Store is required"))

    warehouse = _resolve_warehouse(store)
    if not warehouse:
        frappe.throw(_("Invalid store: {0}").format(store))

    if isinstance(items, str):
        items = json.loads(items)

    if not items or len(items) == 0:
        frappe.throw(_("At least one item is required"))

    # Create Stock Entry for Material Transfer (store -> commissary/scrap)
    doc = frappe.new_doc("Stock Entry")
    doc.stock_entry_type = "Material Issue"  # Issue from store
    doc.company = "Bebang Enterprise Inc."
    doc.custom_return_request = 1  # Custom flag to identify returns
    doc.custom_return_from_store = warehouse
    doc.custom_return_photo = photo
    doc.set_posting_time = 1
    doc.posting_date = nowdate()
    doc.posting_time = frappe.utils.nowtime()

    # Build remarks from return details
    remarks_parts = []
    for item in items:
        item_name = frappe.db.get_value("Item", item["item_code"], "item_name") or item["item_code"]
        remarks_parts.append(f"{item_name}: {item['quantity']} ({item['reason']})")
        if item.get("notes"):
            remarks_parts.append(f"  Notes: {item['notes']}")

    doc.remarks = "Store Return Request:\n" + "\n".join(remarks_parts)

    for item in items:
        doc.append("items", {
            "item_code": item["item_code"],
            "qty": flt(item["quantity"]),
            "s_warehouse": warehouse,
            "custom_return_reason": item["reason"],
            "custom_return_notes": item.get("notes")
        })

    doc.insert()
    doc.submit()

    return {
        "success": True,
        "name": doc.name,
        "message": _("Return request submitted successfully")
    }


@frappe.whitelist()
def get_return_requests(store=None, status=None, limit=20):
    """Get return request history for a store."""
    limit = min(int(limit or 20), 500)
    filters = {}

    # Bug fix C8: Check if custom columns exist before filtering
    if frappe.db.has_column("Stock Entry", "custom_return_request"):
        filters["custom_return_request"] = 1
    if store:
        warehouse = _resolve_warehouse(store)
        if warehouse and frappe.db.has_column("Stock Entry", "custom_return_from_store"):
            filters["custom_return_from_store"] = warehouse

    if status:
        filters["docstatus"] = 1 if status == "submitted" else 0

    # Get safe fields list based on column existence
    fields = ["name", "posting_date", "docstatus", "remarks", "total_outgoing_value as value"]
    if frappe.db.has_column("Stock Entry", "custom_return_from_store"):
        fields.insert(2, "custom_return_from_store as store")

    returns = frappe.get_all(
        "Stock Entry",
        filters=filters,
        fields=fields,
        order_by="posting_date desc",
        limit=int(limit)
    )

    # Add item count
    for ret in returns:
        ret["item_count"] = frappe.db.count("Stock Entry Detail", {"parent": ret["name"]})
        ret["status"] = "Submitted" if ret["docstatus"] == 1 else "Draft"

    return {"returns": returns}
