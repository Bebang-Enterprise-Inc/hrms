# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""
BEI Store Ordering API
Handles store order submission, approval, and delivery receipt generation for my.bebang.ph
"""

import frappe
from frappe import _
from frappe.utils import today, now, getdate, get_time, nowdate, now_datetime


# P0-10: Import centralized RBAC role sets
from hrms.utils.scm_roles import (
    ORDERING_STORE_ROLES, ORDERING_WAREHOUSE_ROLES, ORDERING_APPROVAL_ROLES,
    check_scm_permission as _check_ordering_permission
)


def _get_suggested_qty(store, item_code):
    """
    Compute suggested qty: AVG(qty_requested) from last 3 BEI Store Orders
    for this store+item, multiplied by 1.2 safety factor.
    Returns 0 if no history exists.
    """
    result = frappe.db.sql("""
        SELECT AVG(soi.qty_requested) as avg_qty
        FROM `tabBEI Store Order Item` soi
        INNER JOIN `tabBEI Store Order` so ON soi.parent = so.name
        WHERE so.store = %s
          AND soi.item_code = %s
          AND so.docstatus = 1
          AND so.status NOT IN ('Cancelled')
        ORDER BY so.order_date DESC
        LIMIT 3
    """, (store, item_code), as_dict=True)

    if result and result[0].avg_qty:
        return round(result[0].avg_qty * 1.2, 3)
    return 0.0


def _get_last_order_qty(store, item_code):
    """Get qty_requested from the most recent order for this store+item."""
    result = frappe.db.sql("""
        SELECT soi.qty_requested
        FROM `tabBEI Store Order Item` soi
        INNER JOIN `tabBEI Store Order` so ON soi.parent = so.name
        WHERE so.store = %s
          AND soi.item_code = %s
          AND so.docstatus = 1
        ORDER BY so.order_date DESC
        LIMIT 1
    """, (store, item_code), as_dict=True)

    return result[0].qty_requested if result else 0.0


@frappe.whitelist()
def get_orderable_items(store, date=None):
    """
    Get item catalog for the store.

    Args:
        store (str): Warehouse name (store)
        date (str, optional): Order date (defaults to today)

    Returns:
        dict: {"items": [...], "store": str, "date": str}
    """
    _check_ordering_permission(ORDERING_STORE_ROLES, "view orderable items")

    order_date = date or today()

    # Get all active items that can be ordered (items with item_group set)
    items = frappe.db.sql("""
        SELECT
            i.name as item_code,
            i.item_name,
            i.stock_uom as uom,
            i.description as packaging_description,
            i.item_group as cargo_category
        FROM `tabItem` i
        WHERE i.disabled = 0
          AND i.is_stock_item = 1
        ORDER BY i.item_group, i.item_name
    """, as_dict=True)

    # Source warehouse for stock check (commissary/main warehouse)
    source_warehouse = frappe.db.get_single_value("Stock Settings", "default_warehouse") or "Main Warehouse - BK"

    enriched = []
    for item in items:
        available_stock = frappe.db.get_value(
            "Bin",
            {"item_code": item.item_code, "warehouse": source_warehouse},
            "actual_qty"
        ) or 0.0

        suggested_qty = _get_suggested_qty(store, item.item_code)
        last_order_qty = _get_last_order_qty(store, item.item_code)

        enriched.append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "uom": item.uom,
            "packaging_description": item.packaging_description or "",
            "cargo_category": item.cargo_category or "",
            "suggested_qty": suggested_qty,
            "available_stock": available_stock,
            "is_oos": available_stock <= 0,
            "last_order_qty": last_order_qty,
        })

    return {
        "items": enriched,
        "store": store,
        "date": order_date,
    }


@frappe.whitelist()
def validate_order_schedule(store, date=None):
    """
    Validate whether ordering is allowed for the store and date.

    Args:
        store (str): Warehouse name (store)
        date (str, optional): Order date (defaults to today)

    Returns:
        dict: {"allowed": bool, "reason": str, "next_delivery_day": str}
    """
    _check_ordering_permission(ORDERING_STORE_ROLES, "validate order schedule")

    order_date = date or today()

    # Check cutoff time: orders must be submitted before 11:59 AM
    current_time = get_time(now_datetime().strftime("%H:%M:%S"))
    cutoff_time = get_time("11:59:00")

    # If ordering for today and past cutoff, disallow
    if getdate(order_date) == getdate(today()) and current_time > cutoff_time:
        return {
            "allowed": False,
            "reason": "Ordering cutoff was 11:59 AM",
            "next_delivery_day": "",
        }

    # Delivery schedule matrix will be added later — always allow for now
    return {
        "allowed": True,
        "reason": "",
        "next_delivery_day": "",
    }


@frappe.whitelist()
def submit_order(store, items, cargo_category, delivery_date=None, is_emergency=0, notes=""):
    """
    Submit a store order.

    Args:
        store (str): Warehouse name (store)
        items (list): [{item_code, qty_requested, deviation_reason?}]
        cargo_category (str): FC | DRY | FM
        delivery_date (str, optional): Requested delivery date
        is_emergency (int): 1 if emergency order (bypasses cutoff check)
        notes (str): Optional order notes

    Returns:
        dict: {"name": order_name, "status": status}
    """
    _check_ordering_permission(ORDERING_STORE_ROLES, "submit an order")

    # Parse items if passed as JSON string
    if isinstance(items, str):
        import json
        items = json.loads(items)

    order_date = today()

    # Cutoff check (skip for emergency orders)
    if not int(is_emergency):
        schedule = validate_order_schedule(store, order_date)
        if not schedule.get("allowed"):
            frappe.throw(schedule.get("reason", "Ordering is not allowed at this time"))

    # Duplicate check: no existing non-cancelled order for store + date + category
    existing = frappe.db.exists("BEI Store Order", {
        "store": store,
        "order_date": order_date,
        "cargo_category": cargo_category,
        "status": ["not in", ["Cancelled"]],
    })
    if existing:
        frappe.throw(
            _("An order already exists for {0} on {1} for category {2}: {3}").format(
                store, order_date, cargo_category, existing
            )
        )

    # Determine is_bulk_order: bulk if total qty_requested > threshold or >10 items
    is_bulk_order = 1 if len(items) > 10 else 0

    doc = frappe.get_doc({
        "doctype": "BEI Store Order",
        "naming_series": "BEI-ORD-.YYYY.-.#####",
        "store": store,
        "order_date": order_date,
        "delivery_date": delivery_date,
        "cargo_category": cargo_category,
        "is_emergency": int(is_emergency),
        "is_bulk_order": is_bulk_order,
        "notes": notes,
        "status": "Draft",
        "submitted_by": frappe.session.user,
        "items": [],
    })

    for item_data in items:
        item_code = item_data.get("item_code")
        qty_requested = float(item_data.get("qty_requested", 0))

        if not item_code or qty_requested <= 0:
            frappe.throw(_("Invalid item or quantity for item: {0}").format(item_code))

        suggested_qty = _get_suggested_qty(store, item_code)
        last_order_qty = _get_last_order_qty(store, item_code)

        # Get item details
        item_name, uom, unit_price = frappe.db.get_value(
            "Item", item_code, ["item_name", "stock_uom", "standard_rate"]
        ) or (item_code, "Nos", 0.0)

        doc.append("items", {
            "item_code": item_code,
            "item_name": item_name,
            "uom": uom,
            "unit_price": unit_price or 0.0,
            "qty_requested": qty_requested,
            "suggested_qty": suggested_qty,
            "last_order_qty": last_order_qty,
            "deviation_reason": item_data.get("deviation_reason", ""),
        })

    # insert() triggers validate() → compute_deviations() + set_approval_status()
    doc.insert(ignore_permissions=True)

    return {
        "name": doc.name,
        "status": doc.status,
    }


def _generate_dr_internal(order_name, order=None):
    """
    Internal DR generation without permission check.
    Called from approve_order() which already verified permissions.
    """
    if not order:
        order = frappe.get_doc("BEI Store Order", order_name)

    # Generate DR number: DR + 7-digit auto-increment
    try:
        result = frappe.db.sql(
            "SELECT MAX(CAST(SUBSTRING(name, 3) AS UNSIGNED)) FROM `tabBEI Delivery Receipt`"
        )
        last_num = result[0][0] if result and result[0][0] else 0
    except Exception:
        last_num = 0

    dr_number = "DR{:07d}".format(last_num + 1)

    # Log the DR generation as a comment on the order
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "BEI Store Order",
        "reference_name": order_name,
        "content": _("Delivery Receipt generated: {0}").format(dr_number),
    }).insert(ignore_permissions=True)

    # Send GChat notification to store (pattern from dispatch.py)
    try:
        _send_order_notification(
            store=order.store,
            message=_("Delivery Receipt {0} has been generated for your order {1}. "
                      "Delivery scheduled for {2}.").format(
                dr_number, order_name, order.delivery_date or "TBD"
            )
        )
    except Exception as e:
        frappe.log_error(f"GChat notification failed for DR {dr_number}: {e}", "Ordering API")

    return {
        "dr_number": dr_number,
        "items_count": len(order.items),
    }


@frappe.whitelist()
def generate_dr(order_name):
    """
    Generate a Delivery Receipt for an approved order.

    Args:
        order_name (str): BEI Store Order name

    Returns:
        dict: {"dr_number": str, "items_count": int}
    """
    _check_ordering_permission(ORDERING_WAREHOUSE_ROLES, "generate delivery receipt")

    order = frappe.get_doc("BEI Store Order", order_name)

    if order.status != "Approved":
        frappe.throw(
            _("Cannot generate DR for order {0} — status is '{1}', must be 'Approved'").format(
                order_name, order.status
            )
        )

    return _generate_dr_internal(order_name, order)


@frappe.whitelist()
def get_order_review_queue(date=None, status=None):
    """
    Get all BEI Store Orders for review, optionally filtered by date and status.

    Args:
        date (str, optional): Filter by order_date (defaults to today)
        status (str, optional): Filter by status

    Returns:
        dict: {"orders": [...], "total": int}
    """
    _check_ordering_permission(ORDERING_WAREHOUSE_ROLES, "view order review queue")

    filter_date = date or today()

    # Build WHERE clause
    conditions = ["so.order_date = %(date)s", "so.docstatus < 2"]
    params = {"date": filter_date}

    if status:
        conditions.append("so.status = %(status)s")
        params["status"] = status

    where_clause = " AND ".join(conditions)

    orders = frappe.db.sql(f"""
        SELECT
            so.name,
            so.store,
            so.order_date,
            so.delivery_date,
            so.cargo_category,
            so.status,
            so.is_bulk_order,
            so.is_emergency,
            so.submitted_by,
            COUNT(soi.name) as items_count,
            SUM(soi.amount) as total_amount,
            SUM(CASE WHEN soi.deviation_pct != 0 THEN 1 ELSE 0 END) as deviation_count
        FROM `tabBEI Store Order` so
        LEFT JOIN `tabBEI Store Order Item` soi ON soi.parent = so.name
        WHERE {where_clause}
        GROUP BY so.name
        ORDER BY
            CASE so.status WHEN 'Pending Approval' THEN 0 ELSE 1 END,
            so.store ASC
    """, params, as_dict=True)

    return {
        "orders": orders,
        "total": len(orders),
    }


@frappe.whitelist()
def approve_order(order_name, adjustments=None):
    """
    Approve a pending store order, optionally adjusting quantities.

    Args:
        order_name (str): BEI Store Order name
        adjustments (list, optional): [{item_code, qty_approved}]

    Returns:
        dict: {"status": "Approved", "dr_number": str}
    """
    _check_ordering_permission(ORDERING_APPROVAL_ROLES, "approve orders")

    # Parse adjustments if passed as JSON string
    if isinstance(adjustments, str):
        import json
        adjustments = json.loads(adjustments)

    order = frappe.get_doc("BEI Store Order", order_name)

    if order.status != "Pending Approval":
        frappe.throw(
            _("Cannot approve order {0} — status is '{1}', must be 'Pending Approval'").format(
                order_name, order.status
            )
        )

    # Apply quantity adjustments if provided
    if adjustments:
        adjustment_map = {adj["item_code"]: float(adj["qty_approved"]) for adj in adjustments}
        for item in order.items:
            if item.item_code in adjustment_map:
                item.qty_approved = adjustment_map[item.item_code]

    order.status = "Approved"
    order.approved_by = frappe.session.user
    order.approved_at = now()
    order.save(ignore_permissions=True)

    # Auto-trigger DR generation after approval (using internal function
    # to avoid permission conflict — approve_order already checked permissions)
    dr_result = _generate_dr_internal(order_name, order)

    return {
        "status": "Approved",
        "dr_number": dr_result.get("dr_number"),
    }


@frappe.whitelist()
def reject_order(order_name, reason):
    """
    Reject a pending store order.

    Args:
        order_name (str): BEI Store Order name
        reason (str): Rejection reason

    Returns:
        dict: {"status": "Cancelled"}
    """
    _check_ordering_permission(ORDERING_APPROVAL_ROLES, "reject orders")

    if not reason:
        frappe.throw(_("A rejection reason is required"))

    order = frappe.get_doc("BEI Store Order", order_name)

    if order.status != "Pending Approval":
        frappe.throw(
            _("Cannot reject order {0} — status is '{1}', must be 'Pending Approval'").format(
                order_name, order.status
            )
        )

    order.status = "Cancelled"
    order.save(ignore_permissions=True)

    # Add comment with rejection reason
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "BEI Store Order",
        "reference_name": order_name,
        "content": _("Order rejected by {0}. Reason: {1}").format(
            frappe.session.user, reason
        ),
    }).insert(ignore_permissions=True)

    # Send GChat notification to store
    try:
        store_name = order.store
        _send_order_notification(
            store=store_name,
            message=_("Your order {0} was rejected: {1}").format(order_name, reason)
        )
    except Exception as e:
        frappe.log_error(f"GChat notification failed for rejected order {order_name}: {e}", "Ordering API")

    return {"status": "Cancelled"}


def _send_order_notification(store, message):
    """
    Send a GChat notification to the store.
    Pattern follows dispatch.py _send_delivery_notification.
    Silently fails if Google Chat integration is not configured.
    """
    try:
        from hrms.api.google_chat import send_message_to_space
        # Look up store's notification space from Warehouse custom fields or config
        space_id = frappe.db.get_value("Warehouse", store, "custom_gchat_space") or None
        if space_id:
            send_message_to_space(space_id, message)
    except ImportError:
        # Google Chat module not available — log and skip
        frappe.log_error(f"GChat not configured. Skipped notification for store {store}", "Ordering API")
    except Exception as e:
        raise e
