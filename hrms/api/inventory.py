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
def submit_cycle_count(store=None, items=None, count_date=None):
    """Submit inventory cycle count.

    Bug fixes (C7):
    - Resolve store to warehouse (frontend sends branch code)
    - Use resolved warehouse for Bin lookup
    - insert with ignore_permissions=True (Store Staff needs to submit)
    - Returns user-friendly error instead of raw traceback
    """
    try:
        if not store:
            frappe.throw(_("Store is required"))

        if isinstance(items, str):
            items = json.loads(items)

        # Resolve branch name to warehouse name
        warehouse = _resolve_warehouse(store)
        if not warehouse:
            frappe.throw(_("Could not find Store: {0}").format(store))

        # Validate no negative quantities
        for item in items:
            if flt(item.get("counted_qty", 0)) < 0:
                frappe.throw(_("Counted quantity cannot be negative for item {0}").format(
                    item.get("item_code", "unknown")))

        doc = frappe.new_doc("BEI Cycle Count")
        doc.store = warehouse
        doc.count_date = count_date or nowdate()
        doc.counted_by = frappe.session.user

        total_variance = 0
        for item in items:
            # Get system qty from stock ledger - use resolved warehouse
            system_qty = frappe.db.get_value(
                "Bin",
                {"warehouse": warehouse, "item_code": item["item_code"]},
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
        doc.insert(ignore_permissions=True)
        return {"success": True, "name": doc.name, "total_variance": total_variance}

    except Exception as e:
        frappe.log_error(
            f"Cycle Count Error for store {store}: {str(e)}\n\n{frappe.get_traceback()}",
            "Cycle Count Submission Error"
        )
        return {"success": False, "error": _("Failed to submit cycle count. Please try again or contact support.")}


@frappe.whitelist()
def get_cycle_counts(store=None, date_from=None, date_to=None, status=None,
                     count_type=None, external_auditor=None, limit=20):
    """Get cycle count history with filtering."""
    limit = min(int(limit or 20), 500)
    filters = {}
    if store:
        filters["store"] = store
    if status:
        filters["status"] = status
    if count_type:
        filters["count_type"] = count_type
    if external_auditor:
        filters["external_auditor"] = external_auditor
    if date_from:
        filters["count_date"] = [">=", date_from]
    if date_to:
        if "count_date" in filters:
            filters["count_date"] = ["between", [date_from, date_to]]
        else:
            filters["count_date"] = ["<=", date_to]

    # External Auditors can only see their own counts
    if "External Auditor" in frappe.get_roles() and not external_auditor:
        filters["counted_by"] = frappe.session.user

    counts = frappe.get_all(
        "BEI Cycle Count",
        filters=filters,
        fields=["name", "store", "count_date", "status", "total_variance_value", "counted_by",
                "count_type", "external_auditor", "photo_evidence",
                "exported_to_cos_recon", "export_date",
                "rejection_reason", "resubmission_count"],
        order_by="count_date desc",
        limit=int(limit)
    )
    return {"counts": counts}


@frappe.whitelist()
def get_cycle_count(name):
    """Get single cycle count with items."""
    doc = frappe.get_doc("BEI Cycle Count", name)
    doc.check_permission("read")

    # External Auditors can only see their own counts
    if "External Auditor" in frappe.get_roles() and doc.counted_by != frappe.session.user:
        frappe.throw(_("You can only view your own cycle counts"), frappe.PermissionError)

    items = []
    for item in doc.items:
        item_meta = frappe.db.get_value("Item", item.item_code, ["item_name", "item_group"], as_dict=True) or {}
        items.append({
            "name": item.name,
            "item_code": item.item_code,
            "item_name": item_meta.get("item_name", ""),
            "item_group": item_meta.get("item_group", ""),
            "uom": item.uom,
            "system_qty": item.system_qty,
            "counted_qty": item.counted_qty,
            "counted_qty_whole": item.counted_qty_whole,
            "counted_qty_loose": item.counted_qty_loose,
            "conversion_factor": item.conversion_factor,
            "unit_cost": item.unit_cost,
            "variance_qty": item.variance_qty,
            "variance_value": item.variance_value,
            "remarks": item.remarks,
        })

    return {
        "name": doc.name,
        "store": doc.store,
        "count_date": str(doc.count_date),
        "count_type": doc.count_type,
        "status": doc.status,
        "counted_by": doc.counted_by,
        "verified_by": doc.verified_by,
        "external_auditor": doc.external_auditor,
        "photo_evidence": doc.photo_evidence,
        "exported_to_cos_recon": doc.exported_to_cos_recon,
        "export_date": str(doc.export_date) if doc.export_date else None,
        "total_variance_value": doc.total_variance_value,
        "rejection_reason": doc.rejection_reason,
        "resubmission_count": doc.resubmission_count,
        "items": items,
        "docstatus": doc.docstatus,
        "creation": str(doc.creation),
        "modified": str(doc.modified),
    }


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
def report_variance(store, item_code, system_qty=0, actual_qty=0,
                    variance_type=None, explanation=None, photo=None):
    """Report inventory variance.

    Bug fixes (C8):
    - Resolve store to warehouse
    - system_qty/actual_qty default to 0
    - variance_type defaults to 'Shortage' if not provided
    - photo converted via save_base64_image
    - insert with ignore_permissions=True
    - Returns user-friendly error
    """
    try:
        if not store or not item_code:
            frappe.throw(_("Store and item are required"))

        # Resolve branch name to warehouse name
        warehouse = _resolve_warehouse(store)
        if not warehouse:
            frappe.throw(_("Could not find Store: {0}").format(store))

        # Handle photo base64
        photo_url = None
        if photo:
            from hrms.api.store import save_base64_image
            photo_url = save_base64_image(photo, "BEI Inventory Variance", fieldname="photo_evidence")

        doc = frappe.new_doc("BEI Inventory Variance")
        doc.store = warehouse
        doc.variance_date = nowdate()
        doc.item_code = item_code
        doc.system_qty = flt(system_qty)
        doc.actual_qty = flt(actual_qty)
        doc.variance_qty = flt(actual_qty) - flt(system_qty)

        item_price = frappe.db.get_value("Item", item_code, "valuation_rate") or 0
        doc.variance_value = doc.variance_qty * item_price

        doc.variance_type = variance_type or ("Shortage" if doc.variance_qty < 0 else "Overage")
        doc.explanation = explanation or ""
        doc.reported_by = frappe.session.user
        doc.photo_evidence = photo_url
        doc.insert(ignore_permissions=True)
        return {"success": True, "name": doc.name}

    except Exception as e:
        frappe.log_error(
            f"Variance Report Error for store {store}: {str(e)}\n\n{frappe.get_traceback()}",
            "Variance Report Submission Error"
        )
        return {"success": False, "error": _("Failed to submit variance report. Please try again or contact support.")}


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
    """Request shelf life extension for an item.

    Bug fix (C9): Store OIC/Staff get permission error because BEI Shelf Life Extension
    DocType only allows System Manager and Stock User roles. Fix: use ignore_permissions=True
    since the API already has @frappe.whitelist() protection, and resolve store to warehouse.
    Also convert photo base64 to file URL.
    """
    try:
        if not store or not item_code:
            frappe.throw(_("Store and item are required"))

        # Resolve branch name to warehouse name
        warehouse = _resolve_warehouse(store)
        if not warehouse:
            frappe.throw(_("Could not find Store: {0}").format(store))

        # Handle photo base64
        photo_url = None
        if photo:
            from hrms.api.store import save_base64_image
            photo_url = save_base64_image(photo, "BEI Shelf Life Extension", fieldname="photo_evidence")

        doc = frappe.new_doc("BEI Shelf Life Extension")
        doc.store = warehouse
        doc.request_date = nowdate()
        doc.item_code = item_code
        doc.batch_no = batch_no
        doc.original_expiry = original_expiry
        doc.requested_expiry = requested_expiry
        doc.quantity = flt(quantity)
        doc.reason = reason
        doc.requested_by = frappe.session.user
        doc.photo_evidence = photo_url
        # C9 fix: ignore_permissions because DocType only allows Stock User/System Manager
        # but Store Staff/OIC need to submit shelf life checks
        doc.insert(ignore_permissions=True)

        return {"success": True, "name": doc.name}

    except Exception as e:
        frappe.log_error(
            f"Shelf Life Extension Error for store {store}: {str(e)}\n\n{frappe.get_traceback()}",
            "Shelf Life Extension Error"
        )
        return {"success": False, "error": _("Failed to submit shelf life check. Please try again or contact support.")}


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
        qty = item.get('quantity') or item.get('qty')
        remarks_parts.append(f"{item_name}: {qty} ({item['reason']})")
        if item.get("notes"):
            remarks_parts.append(f"  Notes: {item['notes']}")

    doc.remarks = "Store Return Request:\n" + "\n".join(remarks_parts)

    for item in items:
        qty = item.get('quantity') or item.get('qty')
        doc.append("items", {
            "item_code": item["item_code"],
            "qty": flt(qty),
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


# ============ STOCK COUNTING APIs (Phase 1) ============

def _map_item_group(item_group):
    """Map Frappe Item Group hierarchy to COS RECON categories."""
    mapping = {
        "Finished Goods": "FG",
        "Raw Materials": "RM",
        "Packaging Materials": "PM",
        "Consumables": "CS",
    }
    return mapping.get(item_group, "Other")


def _check_store_access(store):
    """Verify External Auditor has access to this store via BEI External Auditor Store Access."""
    if "External Auditor" not in frappe.get_roles():
        return  # Only check for External Auditors

    warehouse = _resolve_warehouse(store)
    if not warehouse:
        frappe.throw(_("Could not find Store: {0}").format(store))

    access = frappe.db.exists("BEI External Auditor Store Access", {
        "user": frappe.session.user,
        "warehouse": warehouse
    })
    if not access:
        frappe.throw(
            _("You do not have access to count at store {0}").format(store),
            frappe.PermissionError
        )


@frappe.whitelist()
def get_items_for_count(store, count_type=None):
    """Return items with recent stock movement, grouped by category."""
    # External Auditors: verify store access
    _check_store_access(store)

    warehouse = _resolve_warehouse(store)
    if not warehouse:
        frappe.throw(f"No warehouse found for store {store}")

    # Single batch query — avoids N+1 (161 queries → 1)
    items = frappe.db.sql("""
        SELECT DISTINCT
            i.name as item_code, i.item_name, i.item_group,
            i.stock_uom as uom, i.valuation_rate as unit_cost,
            COALESCE(bin.actual_qty, 0) as system_qty,
            COALESCE(ucd.conversion_factor, 1.0) as conversion_factor
        FROM `tabStock Ledger Entry` sle
        JOIN `tabItem` i ON i.name = sle.item_code
        LEFT JOIN `tabBin` bin ON bin.item_code = i.name AND bin.warehouse = %(warehouse)s
        LEFT JOIN `tabUOM Conversion Detail` ucd ON ucd.parent = i.name AND ucd.uom = i.stock_uom
        WHERE sle.warehouse = %(warehouse)s
          AND sle.posting_date >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
          AND i.is_stock_item = 1
        ORDER BY i.item_group, i.item_name
    """, {"warehouse": warehouse}, as_dict=1)

    # Fallback: if SLE is empty (pre-cutover or new store), return all stock items
    if not items:
        items = frappe.db.sql("""
            SELECT i.name as item_code, i.item_name, i.item_group,
                   i.stock_uom as uom, i.valuation_rate as unit_cost,
                   0 as system_qty, 1.0 as conversion_factor
            FROM `tabItem` i
            WHERE i.is_stock_item = 1
              AND i.item_group IN ('Raw Materials', 'Finished Goods', 'Packaging Materials', 'Consumables')
            ORDER BY i.item_group, i.item_name
        """, as_dict=1)

    # Group by category for frontend display
    grouped = {}
    for item in items:
        group = _map_item_group(item.item_group)
        grouped.setdefault(group, []).append(item)

    return {"items": items, "grouped": grouped, "warehouse": warehouse, "count": len(items)}


@frappe.whitelist()
def submit_cycle_count_v2(store, count_date, items, count_type="Store Monthly", photo=None):
    """Create cycle count with WHOLE + LOOSE quantities.

    Args:
        items: list of {item_code, counted_qty_whole, counted_qty_loose}
    """
    # Permission check
    if "External Auditor" in frappe.get_roles():
        _check_store_access(store)  # Verify auditor assigned to this store

    if isinstance(items, str):
        items = json.loads(items)

    # Resolve warehouse
    warehouse = _resolve_warehouse(store)
    if not warehouse:
        frappe.throw(_("Could not find Store: {0}").format(store))

    # Duplicate detection: block if same store+date+type already submitted
    existing = frappe.db.exists("BEI Cycle Count", {
        "store": warehouse, "count_date": count_date,
        "count_type": count_type, "docstatus": 1
    })
    if existing:
        frappe.throw(f"Cycle count already submitted for {store} on {count_date} ({count_type})")

    doc = frappe.new_doc("BEI Cycle Count")
    doc.store = warehouse
    doc.count_date = count_date
    doc.count_type = count_type
    doc.counted_by = frappe.session.user

    if "External Auditor" in frappe.get_roles():
        doc.external_auditor = frappe.session.user

    # Handle photo upload (base64 data URL from frontend photo-capture component)
    if photo:
        from hrms.api.store import save_base64_image
        photo_url = save_base64_image(photo, "BEI Cycle Count", fieldname="photo_evidence")
        doc.photo_evidence = photo_url

    for item_data in items:
        doc.append("items", {
            "item_code": item_data["item_code"],
            "counted_qty_whole": item_data.get("counted_qty_whole", 0),
            "counted_qty_loose": item_data.get("counted_qty_loose", 0.0),
        })
    # validate() computes counted_qty, unit_cost, variance automatically

    doc.insert()
    doc.submit()
    return {"name": doc.name, "status": "Submitted", "items_count": len(doc.items)}


@frappe.whitelist()
def save_cycle_count_draft(store, count_date, items, count_type="Store Monthly", photo=None, name=None):
    """Save cycle count as draft (not submitted). Supports create and update."""
    if "External Auditor" in frappe.get_roles():
        _check_store_access(store)

    if isinstance(items, str):
        items = json.loads(items)

    warehouse = _resolve_warehouse(store)
    if not warehouse:
        frappe.throw(_("Could not find Store: {0}").format(store))

    if name:
        # Update existing draft
        doc = frappe.get_doc("BEI Cycle Count", name)
        if doc.docstatus != 0:
            frappe.throw(_("Cannot update a submitted cycle count"))
        doc.items = []
    else:
        doc = frappe.new_doc("BEI Cycle Count")

    doc.store = warehouse
    doc.count_date = count_date
    doc.count_type = count_type
    doc.counted_by = frappe.session.user
    doc.status = "Draft"

    if "External Auditor" in frappe.get_roles():
        doc.external_auditor = frappe.session.user

    if photo:
        from hrms.api.store import save_base64_image
        photo_url = save_base64_image(photo, "BEI Cycle Count", fieldname="photo_evidence")
        doc.photo_evidence = photo_url

    for item_data in items:
        doc.append("items", {
            "item_code": item_data["item_code"],
            "counted_qty_whole": item_data.get("counted_qty_whole", 0),
            "counted_qty_loose": item_data.get("counted_qty_loose", 0.0),
        })

    doc.save()
    return {"name": doc.name, "status": "Draft", "items_count": len(doc.items)}


@frappe.whitelist()
def export_count_to_cos_recon(cycle_count_name):
    """Generate COS RECON Excel and attach to cycle count record."""
    import openpyxl
    from frappe.utils.file_manager import save_file
    from hrms.utils.cos_recon_schema import ACTIVE_VERSION

    doc = frappe.get_doc("BEI Cycle Count", cycle_count_name)
    doc.check_permission("read")

    filename = f"COS_RECON_{doc.store}_{doc.count_date}.xlsx"

    # Idempotency: return existing export if already done
    if doc.exported_to_cos_recon and doc.export_date:
        existing = frappe.get_all("File", {"attached_to_name": doc.name, "file_name": ["like", "COS_RECON%"]}, ["file_url"])
        if existing:
            return {"file_url": existing[0].file_url, "filename": filename, "already_exported": True}

    # Prefetch all item data in one query (fixes N+1)
    item_codes = [item.item_code for item in doc.items]
    item_data = {}
    if item_codes:
        for d in frappe.get_all("Item",
            filters={"name": ["in", item_codes]},
            fields=["name", "item_name", "item_group", "description"]):
            item_data[d.name] = d

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = doc.store

    # Write headers from versioned schema
    col_map = {}
    for col_def in ACTIVE_VERSION["columns"]:
        col_idx = ord(col_def["col"]) - ord("A") + 1  # C=3, D=4, etc.
        ws.cell(row=1, column=col_idx, value=col_def["header"])
        col_map[col_def["field"]] = col_idx

    # Write items sorted by category
    row = 2
    for item in sorted(doc.items, key=lambda x: _map_item_group(
            (item_data.get(x.item_code) or {}).get("item_group", ""))):
        meta = item_data.get(item.item_code) or {}
        ws.cell(row=row, column=col_map["item_code"], value=item.item_code)
        ws.cell(row=row, column=col_map["item_name"], value=meta.get("item_name", ""))
        ws.cell(row=row, column=col_map["description"], value=meta.get("description", ""))
        ws.cell(row=row, column=col_map["grams"], value=0)  # TODO: populate from item properties when available
        ws.cell(row=row, column=col_map["uom"], value=item.uom)
        ws.cell(row=row, column=col_map["counted_qty_whole"], value=item.counted_qty_whole or 0)
        ws.cell(row=row, column=col_map["counted_qty_loose"], value=item.counted_qty_loose or 0.0)
        ws.cell(row=row, column=col_map["unit_cost"], value=item.unit_cost or 0.0)
        ws.cell(row=row, column=col_map["total_cost"], value=(item.counted_qty or 0) * (item.unit_cost or 0))
        row += 1

    # Save to bytes and attach via File DocType
    from io import BytesIO
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    file_doc = save_file(filename, buffer.read(), "BEI Cycle Count", doc.name, is_private=1)

    # Update flags atomically
    frappe.db.set_value("BEI Cycle Count", doc.name, {
        "exported_to_cos_recon": 1,
        "export_date": frappe.utils.today()
    })

    return {"file_url": file_doc.file_url, "filename": filename}
