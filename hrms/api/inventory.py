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
def submit_cycle_count(store, items):
    """Submit inventory cycle count."""
    if not store:
        frappe.throw(_("Store is required"))

    if isinstance(items, str):
        items = json.loads(items)

    doc = frappe.new_doc("BEI Cycle Count")
    doc.store = store
    doc.count_date = nowdate()
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
        fields=["name", "store", "count_date", "status", "total_variance_value", "counted_by"],
        order_by="count_date desc",
        limit=int(limit)
    )
    return {"counts": counts}


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
